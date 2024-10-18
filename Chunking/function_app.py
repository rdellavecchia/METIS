import azure.functions as func
import logging
import os
import json
import redis
import spacy
import fitz # PyMuPDF
from time import time

# Configurazione per connettersi a un'istanza di Azure Cache for Redis
REDIS_HOST = os.getenv('REDIS_HOST', 'metis.redis.cache.windows.net')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6380))  # Porta SSL
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', 'S1DHsgrmOCZSCaGw5tW9Yh01bg64v9g7YAzCaFEbFsA=')  # Primary Key

# Configurazione del logger di Windows Server
def configure_logger():
    logger = logging.getLogger("Chunking")
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

# Caricamento del sentencizer per l'italiano
nlp_it = spacy.blank('it')
nlp_it.add_pipe("sentencizer")
nlp_it.max_length = 2000000
# Caricamento del sentencizer per l'inglese
nlp_en = spacy.blank('en')
nlp_en.add_pipe("sentencizer")
nlp_en.max_length = 2000000

def extract_sentences_from_text(text, nlp_model):
    """Estrazione delle frasi da un blocco di testo usando spaCy."""
    doc = nlp_model(text)   # Elaborazione del testo con il sentencizer spaCy
    return [sent.text for sent in doc.sents]  # Ritorno delle frasi processate

def create_text_units(sentences, unit_size=3):
    """Creazione delle unità di testo costituite da `unit_size` frasi contigue."""
    units = []
    buffer = []
    
    for sentence in sentences:
        buffer.append(sentence)
        if len(buffer) >= unit_size:
            unit = " ".join(buffer[:unit_size]) # Creazione dell'unità unendo le prime `unit_size` frasi del buffer
            units.append(unit)
            buffer.pop(0) # Rimozione della prima frase dal buffet (shift)
    
    return units

def extract_text_from_pdf(pdf_path):
    """Estrazione del testo da un PDF usando PyMuPDF."""
    try:
        #Apertura del PDF con PyMuPDF
        with fitz.open(pdf_path) as pdf_document:
            text = ""
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num) # Caricamento della pagina corrente
                text += page.get_text()  # Estrazione del testo
        return text
    except Exception as e:
        logger.error(f"Errore nell'estrazione del testo dal PDF {pdf_path}: {e}")
        return ""
        
def process_single_pdf(pdf_path, nlp_model):
    """Elaborazione del PDF e rilascio della memoria non appena completata."""
    logger.info(f"Estrazione del contenuto dal PDF: {os.path.basename(pdf_path)}")
    
    # Estrazione del testo dal PDF e restituzione di tutte le unità
    text = extract_text_from_pdf(pdf_path)
    
    if not text:
        logger.error(f"Nessun testo trovato nel PDF {pdf_path}")
        return[]
    
    # Segmentazione del testo in frasi con spaCy
    sentences = extract_sentences_from_text(text, nlp_model)
    
    # Liberazione della memoria utilizzata dal testo appena processato
    del text
    
    # Crazione delle unità di testo
    all_units = create_text_units(sentences)
    
    # Liberazione della memoria utilizzata dalle frasi una volta create le unità di testo
    del sentences
    
    return all_units

def process_units(pdf_path, client, nlp_model, logger):
    '''Elaborazione di un singolo PDF, segmentazione del testo in frasi, salvataggio del risultato su Redis.'''
    try:
        cached_result = client.get(pdf_path)
        if cached_result:
            logger.info(f"Risultato recuperato da Redis per {pdf_path}")
            return f"Recuperato da cache: {pdf_path}", json.loads(cached_result)
        
        units = retry(process_single_pdf, retries=3, delay=2, pdf_path=pdf_path, nlp_model=nlp_model) # Estrazione delle frasi    
        client.set(pdf_path, str(units)) # Caching dei risultati in Redis
        return f"Elaborazione completata per il PDF: {pdf_path}", units
    
    except Exception as e:
        logger.error(f"Errore nell'elaborazione del PDF {pdf_path}: {e}")
        return f"Errore per {pdf_path}: {e}", []

def save_all_units_to_single_json(all_units, output_filename):
    """Salva tutte le unità estratte da più PDF in un singolo file JSON."""
    try:
        # Creazione della directory per il file JSON, se non esiste
        os.makedirs('./documentation_units', exist_ok=True)
        
        # Path del file JSON
        json_filepath = os.path.join('./documentation_units', output_filename)
        
        # Struttura delle unità con numero e testo
        unit_data = [{"numero_unità": i + 1, "testo_unità": unit} for i, unit in enumerate(all_units)]
        
        # Salvataggio delle unità in un file JSON
        with open(json_filepath, 'w', encoding='utf-8') as json_file:
            json.dump(unit_data, json_file, ensure_ascii=False, indent=4)
        
        logger.info(f"File JSON unico salvato: {json_filepath}")
    
    except Exception as e:
        logger.error(f"Errore nel salvataggio del file JSON unico: {e}")

def process_documentation(pdf_files, client, nlp_model, logger, doc_name):
    '''Funzione per processare la documentazione passata come parametro.'''
    logger.info(f"Avvio dell'elaborazione della documentazione di {doc_name} ...")
    start_time = time()  # Inizio del timer

    results = [] # Per memorizzare i risultati di elaborazione
    messages = []  # Per memorizzare i messaggi di elaborazione
    all_units = []  # Per memorizzare tutte le unità generate dai PDF

    for pdf in pdf_files:
        try:
            result, units = process_units(pdf, client, nlp_model, logger)
            results.append((result, units))
            messages.append(result)
            all_units.extend(units)
        except redis.ConnectionError as conn_err:
            logger.error(f"Errore di connessione a Redis per il PDF {pdf}: {conn_err}")
        except fitz.FileDataError as file_err:
            logger.error(f"Errore durante la lettura del PDF {pdf}: {file_err}")
        except Exception as e:
            logger.error(f"Errore sconosciuto durante l'elaborazione del PDF {pdf}: {e}")

    try:
        # Salvataggio di tutte le unità in un unico file JSON
        save_all_units_to_single_json(all_units, f'all_units_{doc_name.lower()}.json')
    except IOError as io_err:
        logger.error(f"Errore nel salvataggio del file JSON per {doc_name}: {io_err}")
    except Exception as e:
        logger.error(f"Errore sconosciuto nel salvataggio delle unità di {doc_name}: {e}")    

    end_time = time()  # Fine del timer
    total_time = end_time - start_time

    logger.info(f"Tempo totale di esecuzione per l'elaborazione della documentazione di {doc_name}: {total_time} secondi")
    logger.info(f"Fine dell'elaborazione della documentazione di {doc_name}")

def retry(func, retries=3, delay=2, *args, **kwargs):
    """Funzione di utilità per tentare nuovamente una funzione in caso di errore."""
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(f"Tentativo {attempt + 1} fallito: {e}. Riprovo tra {delay} secondi...")
                time.sleep(delay)
            else:
                logger.error(f"Fallimento dopo {retries} tentativi: {e}")
                raise

@app.route(route="http_trigger_chunking")
def http_trigger_chunking(req: func.HttpRequest) -> func.HttpResponse:
    
    # Connessione a Redis
    client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, ssl=True)
    
    # Pulizia della cache di Redis
    client.flushdb() # Pulizia del database Redis
    
    # Documentazione di Red Hat 8
    directory_relh8_path = r"C:\Users\rdell\OneDrive - Politecnico di Torino\Desktop\Reply9\METIS\Scraping\RedHat8\src\functions\documentsRelH8"
    # Documentazione di Red Hat 9
    directory_relh9_path = r"C:\Users\rdell\OneDrive - Politecnico di Torino\Desktop\Reply9\METIS\Scraping\RedHat9\src\functions\documentsRelH9"
    # Documentazione di Windows Server
    directory_ws_path = r"C:\Users\rdell\OneDrive - Politecnico di Torino\Desktop\Reply9\METIS\Scraping\WindowsServer\documentsWinServer"
    
    # Lista dei PDF Red Hat 8
    pdf_relh8_files = []
    # Lista dei PDF Red Hat 9
    pdf_relh9_files = []
    # Lista dei PDF Windows Server
    pdf_ws_files = []
    
    # Scansione della documentazione di Red Hat 8
    for filename in os.listdir(directory_relh8_path):
        if filename.endswith('.pdf'):
            pdf_relh8_files.append(os.path.join(directory_relh8_path, filename))
    
    # Scansione della documentazione di Red Hat 9
    for filename in os.listdir(directory_relh9_path):
        if filename.endswith('.pdf'):
            pdf_relh9_files.append(os.path.join(directory_relh9_path, filename))
    
    # Scansione della documentazione di Windows Server
    for filename in os.listdir(directory_ws_path):
        if filename.endswith('.pdf'):
            pdf_ws_files.append(os.path.join(directory_ws_path, filename))
    
    # Elaborazione di ciascun PDF della documentazione Red Hat 8
    process_documentation(pdf_relh8_files, client, nlp_en, logger, "Red Hat 8")

    # Elaborazione di ciascun PDF della documentazione Red Hat 9 (solo dopo Red Hat 8)
    # process_documentation(pdf_relh9_files, client, nlp_en, logger, "Red Hat 9")

    # Elaborazione di ciascun PDF della documentazione di Windows Server (solo dopo Red Hat 9)
    # process_documentation(pdf_ws_files, client, nlp_en, logger, "Windows Server")
    
    # Test della connessione
    try:
        
        if client.ping():
            logger.info("Connessione a Redis riuscita!")
            return func.HttpResponse("Connessione a Redis riuscita! Ciao Raffaele, benvenuto!", status_code=200)
        
    except Exception as e:
        
        logger.error(f"Errore di connessione: {e}")
        return func.HttpResponse(f"Errore di connessione: {e}", status_code=500)