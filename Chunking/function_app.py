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


def extract_sentences_from_page(page_number, pdf_path, nlp_model):
    
    """Estrazione delle frasi da una singola pagina del PDF usando spaCy."""
    
    document = fitz.open(pdf_path) # Apertura del PDF all'interno di ciascun processo
    
    page = document.load_page(page_number) # Estrazione della pagina dal PDF
    text = page.get_text()  # Estrazione del testo da una pagina
    doc = nlp_model(text)   # Elaborazione del testo con il modello spaCy
    
    document.close() # Chiusura del documento
    
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

def process_pdf(pdf_path, nlp_model):
    
    """Elaborazione del PDF e restituzione di tutte le frasi."""
    
    document = fitz.open(pdf_path)  # Apertura del PDF per ottenere il numero delle pagine
    num_pages = document.page_count
    document.close() # Chiusura del documento una volta ottenuto il numero delle pagine
    
    all_units = []

    with ProcessPoolExecutor() as executor:
        
        # Estrazione delle frasi da ciascuna pagina del PDF in parallelo: ciascun processo riceve il nuemro della pagina e il percorso del PDF
        sentences_per_page = list(executor.map(
            extract_sentences_from_page, 
            range(num_pages),
            [pdf_path] * num_pages,  # Passaggio del percorso PDF a ogni processo
            [nlp_model] * num_pages  # Passaggio del modello NLP a ogni processo
        ))
        
        # Unione delle frase estratte in un'unica lista
        all_sentences = [sentence for page_sentences in sentences_per_page for sentence in page_sentences]
        
        # Creazione delle unità di testo
        all_units = create_text_units(all_sentences)
    
    return all_units

@app.route(route="http_trigger_chunking")
def http_trigger_chunking(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Python HTTP trigger function processed a request.')
    
    # Percorso del PDF da analizzare
    pdf_path = r"C:\Users\rdell\OneDrive - Politecnico di Torino\Desktop\Reply9\METIS\Chunking\Red_Hat_Enterprise_Linux-8-8.0_Release_Notes-en-US.pdf"
    
    # Creazione delle unità di testo a partire dal PDF
    text_units = process_pdf(pdf_path, nlp_en)
    
    # Stampa delle unità di testo create
    for index, unit in enumerate(text_units):
        logger.info(f"Unità {index+1}: {unit}")
    
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