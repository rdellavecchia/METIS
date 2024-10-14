import azure.functions as func
import logging
import fitz  # PyMuPDF
import re  # Espressioni regolari
import os  # Gestione delle cartelle
import hashlib  # Per calcolare SHA-256
import json  # Per creare il file JSON
import httpx  # Per scaricare il PDF da un URL
from datetime import datetime  # Per ottenere il timestamp

# Configurazione del logger di Windows Server
def configure_logger():
    logger = logging.getLogger("PDFExtractor")
    if not logger.handlers:  # Evita duplicati
        logger.setLevel(logging.INFO)

        log_directory = './scraping_logs'
        os.makedirs(log_directory, exist_ok=True)

        info_handler = logging.FileHandler(os.path.join(log_directory, 'scraping.log'), encoding='utf-8')
        error_handler = logging.FileHandler(os.path.join(log_directory, 'error.log'), encoding='utf-8')

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        info_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)

        info_handler.setLevel(logging.INFO)
        error_handler.setLevel(logging.ERROR)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        logger.addHandler(info_handler)
        logger.addHandler(error_handler)
        logger.addHandler(console_handler)

    return logger

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Inizializzazione del logger
logger = configure_logger()

def calculate_sha256(file_path: str) -> str:
    """Calcola l'hash SHA-256 di un file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):  # Blocchi più grandi per file grandi
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def download_pdf(url: str, output_file: str):
    """Scarica il PDF da un URL e lo salva localmente."""
    try:
        # Utilizzo di httpx per scaricare il PDF
        with httpx.Client() as client:
            response = client.get(url)
            response.raise_for_status()  # Solleva un'eccezione se la richiesta non ha successo

            with open(output_file, 'wb') as f:
                f.write(response.content)
        
    except httpx.RequestError as e:
        logger.error(f"Errore durante il download del PDF: {e}")
        raise

def save_pages_to_new_pdf(doc: fitz.Document, start_page: int, end_page: int, output_pdf: str):
    """Salva un intervallo di pagine da un documento PDF esistente in un nuovo PDF."""
    try:
        new_doc = fitz.open()

        for page_num in range(start_page, end_page):
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
        
        new_doc.save(output_pdf)
    except fitz.FitzError as e:
        logger.error(f"Errore di Fitz nel salvataggio del nuovo PDF: {e}")
    except Exception as e:
        logger.error(f"Errore nel salvare le pagine nel nuovo PDF: {e}")
    finally:
        if 'new_doc' in locals():
            new_doc.close()

def load_previous_checksum(json_file: str, pdf_document: str) -> str:
    """Carica il checksum precedente dal file JSON, se esiste."""
    if os.path.exists(json_file):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                for document in data["documents"]:
                    if document["file_name"] == os.path.basename(pdf_document):
                        return document["checksum"]
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Errore nel caricamento del checksum precedente: {e}")
    return None

def get_current_timestamp() -> str:
    """Ritorna il timestamp corrente in formato ISO 8601."""
    return datetime.now().isoformat()

@app.route(route="http_trigger_windows_server")
def http_trigger_windows_server(req: func.HttpRequest) -> func.HttpResponse:
    """Funzione trigger HTTP per elaborare il PDF."""
    logger.info('Inizio dell\'estrazione del testo da un PDF e suddivisione in parti basate su "Article" e data...')
    
    # URL del PDF da scaricare
    pdf_url = "https://learn.microsoft.com/pdf?url=https%3A%2F%2Flearn.microsoft.com%2Fen-us%2Fwindows-server%2Fget-started%2Ftoc.json"
    pdf_document = "windows-server-get-started.pdf"  # Nome del file locale in cui salvare il PDF scaricato
    json_output_file = "checksum_pdfWindowsServer.json"  # Salva nella root
    output_directory = "documentsWinServer"
    
    os.makedirs(output_directory, exist_ok=True)

    # Caricamento del checksum precedente
    previous_checksum = load_previous_checksum(json_output_file, pdf_document)

    # Download del PDF dal link
    download_pdf(pdf_url, pdf_document)

    # Calcolo del checksum del PDF scaricato
    current_checksum = calculate_sha256(pdf_document)

    # Controllo del checksum
    if previous_checksum == current_checksum:
        logger.info("Il PDF non è cambiato. Nessun aggiornamento necessario.")
        return func.HttpResponse(
            "Il file PDF non è cambiato. Nessun aggiornamento eseguito.",
            status_code=200
        )
    else:
        logger.info("Il checksum del PDF è cambiato. Aggiornamento necessario.")

    output_files = []
    start_page = None
    current_page = 0

    try:
        doc = fitz.open(pdf_document)
        num_pages = doc.page_count

        # Regex per trovare "Article •" seguito da una data
        date_pattern = re.compile(r"Article\s+•\s+\d{1,2}/\d{1,2}/\d{4}")

        # Dati per il file JSON
        json_data = {
            "total_documents": 0,
            "documents": []
        }

        json_data["documents"].append({
            "file_name": os.path.basename(pdf_document),
            "checksum": current_checksum,
            "timestamp": get_current_timestamp()
        })

        while current_page < num_pages:
            try:
                page = doc.load_page(current_page)
                text = page.get_text()

                if date_pattern.search(text):
                    if start_page is None:
                        start_page = current_page
                    else:
                        output_pdf = os.path.join(output_directory, f"Windows_Server_{len(output_files) + 1}.pdf")
                        save_pages_to_new_pdf(doc, start_page, current_page, output_pdf)
                        output_files.append(output_pdf)

                        # Calcolo del checksum per il nuovo PDF
                        pdf_checksum = calculate_sha256(output_pdf)
                        json_data["documents"].append({
                            "file_name": os.path.basename(output_pdf),
                            "checksum": pdf_checksum,
                            "timestamp": get_current_timestamp()  # Aggiunge il timestamp corrente
                        })
                        
                        start_page = current_page

            except fitz.FitzError as e:
                logger.error(f"Errore di Fitz nel caricare la pagina {current_page + 1}: {e}")
            except Exception as e:
                logger.error(f"Errore sconosciuto nella pagina {current_page + 1}: {e}")

            current_page += 1

        # Salvataggio delle pagine rimanenti, se necessario
        if start_page is not None:
            output_pdf = os.path.join(output_directory, f"Windows_Server_{len(output_files) + 1}.pdf")
            save_pages_to_new_pdf(doc, start_page, num_pages, output_pdf)
            output_files.append(output_pdf)

            # Calcolo del checksum per l'ultimo PDF
            pdf_checksum = calculate_sha256(output_pdf)
            json_data["documents"].append({
                "file_name": os.path.basename(output_pdf),
                "checksum": pdf_checksum,
                "timestamp": get_current_timestamp()
            })

        # Aggiornamento del conteggio totale dei documenti
        json_data["total_documents"] = len(json_data["documents"])

        # Scrittura del file JSON nella cartella di root
        with open(json_output_file, "w") as json_file:
            json.dump(json_data, json_file, indent=4)
        
    finally:
        if 'doc' in locals():
            doc.close()

    logger.info('Fine dell\'estrazione del testo da un PDF e suddivisione in parti basate su "Article" e data...')
    
    return func.HttpResponse(
        f"Creati {len(output_files)} file PDF: {', '.join([os.path.basename(f) for f in output_files])}. File JSON creato: {json_output_file}",
        status_code=200
    )
