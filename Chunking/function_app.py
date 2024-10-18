import azure.functions as func
import logging
import os
import json
import redis
import spacy
import fitz # PyMuPDF
import numpy as np
from time import time
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Configurazione per connettersi a un'istanza di Azure Cache for Redis
REDIS_HOST = os.getenv('REDIS_HOST', 'metis.redis.cache.windows.net')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6380))  # Porta SSL
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', 'S1DHsgrmOCZSCaGw5tW9Yh01bg64v9g7YAzCaFEbFsA=')  # Primary Key

# Caricamento del sentencizer per l'italiano
nlp_it = spacy.blank('it')
nlp_it.add_pipe("sentencizer")
nlp_it.max_length = 2000000

# Caricamento del sentencizer per l'inglese
nlp_en = spacy.blank('en')
nlp_en.add_pipe("sentencizer")
nlp_en.max_length = 2000000

# Caricamento del modello di SentenceTransformer
embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

def configure_logger():
    """Configurazione del logger di sistema."""
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

# Inizializzazione del logger
logger = configure_logger()

def extract_sentences_with_indices(text, nlp_model):
    """Estrazione delle frasi con indice da un blocco di testo mediante il sentencizer spaCy."""
    doc = nlp_model(text)
    sentences_with_indices = []
    for i, sentence in enumerate(doc.sents):
        sentences_with_indices.append((i, sentence.text))
    return sentences_with_indices

def create_text_units_with_indices(sentences_with_indices, unit_size=3):
    """Creazione delle unità di testo con indice e associazione di `unit_size` frasi contigue."""
    units = []
    buffer = []
    for index, sentence in sentences_with_indices:
        buffer.append((index, sentence))
        if len(buffer) >= unit_size:
            unit = " ".join([s for _, s in buffer[:unit_size]])
            indices = [idx for idx, _ in buffer[:unit_size]]
            units.append({"text": unit, "indices": indices})
            buffer.pop(0)
    return units

def extract_text_from_pdf(pdf_path):
    """Estrazione del testo da un PDF mediante PyMuPDF."""
    try:
        with fitz.open(pdf_path) as pdf_document:
            text = ""
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num) 
                text += page.get_text()
        return text
    except Exception as e:
        logger.error(f"Errore durante l'estrazione del testo dal PDF {os.path.basename(pdf_path)}: {e}")
        return ""

def generate_embeddings(units, model):
    """Generazione (e associazione) degli embeddings per ciascuna unità (a ciascuna unità)."""
    texts = [unit['text'] for unit in units]
    embeddings = model.encode(texts, convert_to_tensor=True)
    for i, unit in enumerate(units):
        unit["combined_sentence_embedding"] = embeddings[i].tolist()
    return units

def calculate_distance(units):
    """Calcolo delle distanze tra embeddings consecutivi mediante la similarità del coseno"""
    distances = []
    
    for i in range(len(units) - 1):
        embedding_current = units[i]["combined_sentence_embedding"]
        embedding_next = units[i + 1]["combined_sentence_embedding"]
        
        similarity = cosine_similarity([embedding_current], [embedding_next])[0][0]
        distance = 1 - similarity
        distances.append(distance)
        
        units[i]["distance_to_next"] = distance

    return distances, units

def create_chunks_based_on_distances(units, distances, pdf_file, logger):
    """Creazione dei chunk sualla base della distanza e del 95° percentile."""
    breakpoint = np.percentile(distances, 95) # Calcolo del 95° percentile per determinel il breakpoint
    indices_above_threshold = [i for i, d in enumerate(distances) if d > breakpoint] # Ricerca degli indici in cui le distanze sono al di sopra della soglia
    logger.info(f"Trovati {len(indices_above_threshold)} chunk per {pdf_file}")
    
    chunks = []
    start_index = 0
    for x in indices_above_threshold:
        end_index = x  # Fine del chunk
        group = units[start_index:end_index + 1] # Raccolta delle frasi tra start_index ed end_index
        combined_text = ' '.join([d["text"] for d in group]) # Unione del testo del chunk
        chunks.append(combined_text.strip()) # Inserimento del chunk nella lista
        start_index = x + 1 # Aggiornamento dello start_index per il prossimo chunk
    
    if start_index < len(units):
        combined_text = ' '.join([d["text"] for d in units[start_index:]])
        chunks.append(combined_text.strip()) # Aggiunta dell'ultimo chunk nel momento in cui ci sono frasi rimanenti
    
    logger.info(f"Numero totale di chunk creati: {len(chunks)}")
    
    return chunks

def process_single_pdf(pdf_path, nlp_model):
    """Elaborazione del PDF e rilascio della memoria non appena completata."""
    text = extract_text_from_pdf(pdf_path) # Estrazione del testo dal PDF e restituzione di tutte le unità
    if not text:
        logger.error(f"Nessun testo trovato nel PDF {pdf_path}")
        return[]
    
    sentences = extract_sentences_with_indices(text, nlp_model) # Segmentazione del testo in frasi con spaCy
    del text # Liberazione della memoria utilizzata dal testo appena processato
    all_units = create_text_units_with_indices(sentences) # Crazione delle unità di testo
    del sentences # Liberazione della memoria utilizzata dalle frasi una volta create le unità di testo
    
    return all_units

def process_units(pdf_path, client, nlp_model, logger):
    """Elaborazione di un singolo PDF, generazione degli embeddings e creazione dei chunk."""
    try:
        cached_result = client.get(pdf_path)
        if cached_result:
            logger.info(f"Risultato recuperato da Redis per {pdf_path}")
            return f"Recuperato da cache: {pdf_path}", json.loads(cached_result)
        
        # Estrazione delle frasi dal PDF e generazione delle unità
        units = process_single_pdf(pdf_path, nlp_model)
        
        # Generazione degli embeddings
        units_with_embeddings = generate_embeddings(units, embedding_model)
        
        # Calcolo delle distanze tra gli embeddings consecutivi
        distances, units_with_distances = calculate_distance(units_with_embeddings)
        
        # Creazione dei chunk sulla base delle distanze ottenute
        chunks = create_chunks_based_on_distances(units_with_distances, distances, pdf_path, logger)
        
        # Caching dei chunk in Redis: `pdf_path` utilizzato come chiave per accedere ai chunk; `json.dumps(chunks)` converte la lista di chunk in una stringa JSON 
        client.set(pdf_path, json.dumps(chunks))
        
        return f"Elaborazione completata per il PDF: {pdf_path}", chunks
    
    except Exception as e:
        logger.error(f"Errore nell'elaborazione del PDF {pdf_path}: {e}")
        return f"Errore per {pdf_path}: {e}", []

def process_documentation(pdf_files, client, nlp_model, logger, doc_name):
    """Funzione per processare la documentazione passata come parametro."""
    start_time = time()  # Inizio del timer
    all_chunks = []

    for pdf in pdf_files:
        try:
            chunks = process_units(pdf, client, nlp_model, logger)
            all_chunks.extend(chunks)
        except redis.ConnectionError as conn_err:
            logger.error(f"Errore di connessione a Redis per il PDF {pdf}: {conn_err}")
        except fitz.FileDataError as file_err:
            logger.error(f"Errore durante la lettura del PDF {pdf}: {file_err}")
        except Exception as e:
            logger.error(f"Errore sconosciuto durante l'elaborazione del PDF {pdf}: {e}")
    
    logger.info(f"Elaborazione completata per {doc_name} in {time() - start_time} secondi")

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

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
    pdf_relh8_files = [os.path.join(directory_relh8_path, f) for f in os.listdir(directory_relh8_path) if f.endswith('.pdf')]
    # Lista dei PDF Red Hat 9
    pdf_relh9_files = [os.path.join(directory_relh9_path, f) for f in os.listdir(directory_relh9_path) if f.endswith('.pdf')]
    # Lista dei PDF Windows Server
    pdf_ws_files = [os.path.join(directory_ws_path, f) for f in os.listdir(directory_ws_path) if f.endswith('.pdf')]
    
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