import azure.functions as func
import logging
import redis

#  Configurazione per connettersi a un'istanza di Azure Cache for Redis
redis_host = 'metis.redis.cache.windows.net'
redis_port = 6380  # Porta SSL
redis_password = 'S1DHsgrmOCZSCaGw5tW9Yh01bg64v9g7YAzCaFEbFsA=' # Primary Key

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="http_trigger_chunking")
def http_trigger_chunking(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # Connessione a Redis
    client = redis.StrictRedis(host=redis_host, port=redis_port, password=redis_password, ssl=True)
    
    # Test della connessione
    try:
        
        if client.ping():
            logging.info("Connessione a Redis riuscita!")
            return func.HttpResponse("Connessione a Redis riuscita! Ciao Raffaele, benvenuto!", status_code=200)
        
    except Exception as e:
        
        logging.error(f"Errore di connessione: {e}")
        return func.HttpResponse(f"Errore di connessione: {e}", status_code=500)