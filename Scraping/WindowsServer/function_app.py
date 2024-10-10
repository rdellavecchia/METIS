import azure.functions as func
import logging
import fitz  # PyMuPDF
import re  # Espressioni regolari
import os  # Gestione delle cartelle
import hashlib  # Per calcolare SHA-256
import json  # Per creare il file JSON

# Configurazione del logger di Windows Server
def configure_logger():
    logger = logging.getLogger("PDFExtractor")
    if not logger.handlers:  # Evita duplicati
        logger.setLevel(logging.INFO)

        log_directory = './scraping_logs'
        os.makedirs(log_directory, exist_ok=True)

        info_handler = logging.FileHandler(os.path.join(log_directory, 'scraping.log'))
        error_handler = logging.FileHandler(os.path.join(log_directory, 'error.log'))

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

def save_pages_to_new_pdf(doc: fitz.Document, start_page: int, end_page: int, output_pdf: str):
    """Salva un intervallo di pagine da un documento PDF esistente in un nuovo PDF."""
    try:
        new_doc = fitz.open()

        for page_num in range(start_page, end_page):
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
        
        new_doc.save(output_pdf)
        logger.info(f"Nuovo PDF salvato: {output_pdf}")
    except fitz.FitzError as e:
        logger.error(f"Errore di Fitz nel salvataggio del nuovo PDF: {e}")
    except Exception as e:
        logger.error(f"Errore nel salvare le pagine nel nuovo PDF: {e}")
    finally:
        if 'new_doc' in locals():
            new_doc.close()

@app.route(route="http_trigger_windows_server")
def http_trigger_windows_server(req: func.HttpRequest) -> func.HttpResponse:
    """Funzione trigger HTTP per elaborare il PDF."""
    logger.info('Inizio dell\'estrazione del testo da un PDF e suddivisione in parti basate su "Article" e data...')
    
    pdf_document = "windows-server-get-started.pdf"
    output_directory = "documentsWinServer"
    os.makedirs(output_directory, exist_ok=True)

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

        # Calcolo del checksum del PDF originale
        original_checksum = calculate_sha256(pdf_document)
        json_data["documents"].append({
            "file_name": os.path.basename(pdf_document),  # Salvattaggio del nome del file senza percorso
            "checksum": original_checksum
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
                            "file_name": os.path.basename(output_pdf),  # Salvattaggio del nome del file senza percorso
                            "checksum": pdf_checksum
                        })
                        
                        logger.info(f"Creato PDF: {output_pdf}")
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
                "file_name": os.path.basename(output_pdf),  # Salvattaggio del nome del file senza percorso
                "checksum": pdf_checksum
            })

            logger.info(f"Creato PDF: {output_pdf}")

        # Aggiornamento del conteggio totale dei documenti
        json_data["total_documents"] = len(json_data["documents"])

        # Scrittura del file JSON nella cartella di root
        json_output_file = "document_info.json"  # Salva nella root
        with open(json_output_file, "w") as json_file:
            json.dump(json_data, json_file, indent=4)

        logger.info(f'File JSON creato: {json_output_file}')
        
    finally:
        if 'doc' in locals():
            doc.close()

    logger.info('Fine dell\'estrazione del testo da un PDF e suddivisione in parti basate su "Article" e data...')
    
    return func.HttpResponse(
        f"Creati {len(output_files)} file PDF: {', '.join([os.path.basename(f) for f in output_files])}. File JSON creato: {json_output_file}",
        status_code=200
    )
