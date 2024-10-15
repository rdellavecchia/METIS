import azure.functions as func
import logging
import os
import fitz # PyMuPDF
import spacy
import redis
from concurrent.futures import ProcessPoolExecutor

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

# Caricamento del modello per l'italiano
nlp_it = spacy.load('it_core_news_sm')
# Caricamento del modello per l'inglese
nlp_en = spacy.load('en_core_web_sm')


def extract_sentences_from_page(page, nlp_model):
    """Estrae le frasi da una singola pagina del PDF usando spaCy."""
    text = page.get_text()  # Estrai il testo dalla pagina
    doc = nlp_model(text)   # Processa il testo con il modello spaCy
    return [sent.text for sent in doc.sents]  # Ritorna le frasi processate

def process_pdf(pdf_path, nlp_model):
    """Processa il PDF e restituisce tutte le frasi."""
    document = fitz.open(pdf_path)  # Apri il PDF
    all_sentences = []

    for page_num in range(document.page_count):  # Itera su ogni pagina del PDF
        page = document[page_num]
        sentences = extract_sentences_from_page(page, nlp_model)  # Estrai le frasi da questa pagina
        all_sentences.extend(sentences)  # Aggiungi le frasi all'elenco totale

    document.close()  # Chiudi il PDF
    return all_sentences

@app.route(route="http_trigger_chunking")
def http_trigger_chunking(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Python HTTP trigger function processed a request.')
    
    # Percorso del PDF da analizzare
    pdf_path = r"C:\Users\rdell\OneDrive - Politecnico di Torino\Desktop\Reply9\METIS\Chunking\Red_Hat_Enterprise_Linux-8-8.0_Release_Notes-en-US.pdf"
    
    # Estrazione delle frasi a partire dal PDF
    sentences = process_pdf(pdf_path, nlp_en)
    
    # Iterazione su tutte le frasi estrette e log di ogni frase
    for sent in sentences:
        logger.info(sent)
    
    # Connessione a Redis
    client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, ssl=True)
    
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
            pdf_relh8_files.append(filename)
    
    # Scansione della documentazione di Red Hat 9
    for filename in os.listdir(directory_relh9_path):
        if filename.endswith('.pdf'):
            pdf_relh9_files.append(filename)
    
    # Scansione della documentazione di Windows Server
    for filename in os.listdir(directory_ws_path):
        if filename.endswith('.pdf'):
            pdf_ws_files.append(filename)
    
    # Test della connessione
    try:
        
        if client.ping():
            logger.info("Connessione a Redis riuscita!")
            return func.HttpResponse("Connessione a Redis riuscita! Ciao Raffaele, benvenuto!", status_code=200)
        
    except Exception as e:
        
        logger.error(f"Errore di connessione: {e}")
        return func.HttpResponse(f"Errore di connessione: {e}", status_code=500)