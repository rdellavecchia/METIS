const { app } = require('@azure/functions');
const fs = require("fs");
const path = require("path");
const axios = require('axios');
const puppeteer = require("puppeteer");
const winston = require("winston");
const crypto = require('crypto');

// Configurazione del logger di Red Hat 9
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.json()
    ),
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({ filename: './scraping_logs/scraping.log' }), // File di log per informazioni
        new winston.transports.File({ filename: './scraping_logs/error.log', level: 'error' }) // File di log per errori
    ],
});

let browser;

// Endpoint di attivazione HTTP
app.http('httpTriggerScraping', {
    methods: ['GET'], // Impostazione dei metodi consentiti
    authLevel: 'anonymous', // Impostazione del livello di autenticazione
    handler: async (request, context) => {

        try {
            logger.info("Richiesta ricevuta. Avvio processo di scraping...");

            /* Avvio dello scraping in background senza bloccare il client */
            scrapeAndDownloadDocuments();

            context.res = {
                status: 200,
                body: {
                    message: 'Scraping completato con successo.'
                },
                headers: {
                    'Content-Type': 'application/json'
                }
            };

        } catch (error) {
            let errorMessage = `Errore durante la richiesta: ${error.message}`;
            logger.error(errorMessage);
            context.res = {
                status: 500,
                body: {
                    message: 'Errore durante lo scraping',
                    error: errorMessage
                },
                headers: {
                    'Content-Type': 'application/json'
                }
            }; 
        }
    }
});

// Funzione per gestire lo scraping e il download
async function scrapeAndDownloadDocuments() {
    try {
        /* Avvio del browser Puppeteer */
        logger.info("Avvio del browser Puppeteer...");
        browser = await puppeteer.launch({
            headless: true,
            args: ['--start-maximized', '--window-size=1920,1080'],
            defaultViewport: null,
        });
        const page = await browser.newPage();

        /* Lettura e impostazione dei cookie */
        if (fs.existsSync('./cookies.json')) {
            const cookiesString = fs.readFileSync('./cookies.json', 'utf8');
            const cookies = JSON.parse(cookiesString);
            await page.setCookie(...cookies);
        } else {
            logger.error("Il file dei cookie non esiste. Impossibile procedere senza autenticazione.");
            throw new Error("File dei cookie non trovato.");
        }

        /* Navigazione alla pagina di documentazione RedHat 9 */
        logger.info("Navigazione alla pagina di documentazione...");
        await page.goto("https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9", { waitUntil: 'networkidle2' });

        /* Selezione degli elementi e iterazione con la pagina web */
        const sections = await page.$$eval("a[href*='/en/documentation/red_hat_enterprise_linux/9/html/']", links => {
            const uniqueLinks = new Set(links.map(link => link.href));
            return Array.from(uniqueLinks);
        });

        if (sections.length === 0) {
            const message = "Numero di sezioni trovate: 0";
            logger.error(message);
            throw new Error(message);
        } else {
            logger.info(`Numero di sezioni trovate: ${sections.length}`);
            sections.forEach(link => logger.info(`Trovato link alla sezione: ${link}`));
        }

        const downloadedFiles = [];

        /* Download dei PDF */
        for (const sectionLink of sections) {
            const page = await browser.newPage();
            try {
                // Navigazione al link della sezione
                logger.info(`Navigazione alla sezione: ${sectionLink}`);
                await page.goto(sectionLink, { waitUntil: 'networkidle2' });

                // Ricerca dell'elemento PDF nella pagina
                const pdfElement = await page.$("#pdf-download a");
                if (pdfElement) {
                    const pdfHref = await pdfElement.getProperty("href");
                    const pdfUrl = await pdfHref.jsonValue();
                    logger.info(`Trovato link PDF: ${pdfUrl}`);

                    // Download del PDF
                    const filePath = await downloadPDF(pdfUrl, path.join(__dirname, 'documentsRelH9'));
                    downloadedFiles.push(filePath);
                } else {
                    logger.warn("Elemento PDF non trovato in questa pagina.");
                }
            } catch (error) {
                logger.error(`Errore durante la navigazione o il download dalla sezione ${sectionLink}: ${error.message}`);
            } finally {
                await page.close();
            }
        }

        logger.info(`Scraping completato. PDF scaricati: ${downloadedFiles.length}`);

    } catch (error) {
        logger.error(`Errore durante lo scraping: ${error.message}`);
    } finally {
        if (browser) {
            await browser.close();
            logger.info("Browser chiuso con successo.");
        }
        context.done();
    }
}

// Funzione per scaricare il PDF
async function downloadPDF(pdfUrl, outputFolder) {
    /* Validazione dell'URL */
    if (!isValidUrl(pdfUrl)) {
        logger.error(`URL non valido: ${pdfUrl}`);
        throw new Error('URL non valido.');
    }

    /* Estrazione del nome del file e creazione del percorso */
    const fileName = path.basename(pdfUrl);
    const filePath = path.join(outputFolder, fileName);

    /* Creazione della cartella di output */
    if (!fs.existsSync(outputFolder)) {
        fs.mkdirSync(outputFolder, { recursive: true });
    }

    try {
        /* Tentativo di download del PDF con timeout */
        const response = await axios.get(pdfUrl, {
            responseType: 'stream',
            timeout: 10000, // Timeout di 10 secondi
        });

        /* Creazione dello stream per la scrittura */
        const writer = fs.createWriteStream(filePath);
        response.data.pipe(writer);

        /* Attendere il completamento dello stream mediante una promise */
        await new Promise((resolve, reject) => {
            writer.on('finish', async () => {
                logger.info(`PDF scaricato con successo: ${filePath}`);

                // Calcolo del checksum dopo il download
                try {
                    const checksum = await calculateChecksum(filePath);
                    await saveChecksumToJSON(fileName, checksum); // Salva il checksum nel file JSON
                    logger.info(`Checksum (SHA-256) del file ${fileName} salvato con successo nel file JSON.`);
                } catch (err) {
                    logger.error(`Errore durante il calcolo o il salvataggio del checksum: ${err.message}`);
                }

                resolve(filePath);
            });
            writer.on('error', (err) => {
                logger.error(`Errore durante la scrittura del PDF: ${err.message}`);
                reject(new Error(`Errore di scrittura: ${err.message}`));
            });
        });

        /* Restituzione del percorso del file scaricato */
        return filePath;

    } catch (error) {
        /* Gestione degli errori */
        if (error.response) {
            logger.error(`Errore durante il download del PDF: ${error.response.status} - ${error.response.statusText}`);
        } else if (error.code) {
            logger.error(`Errore di rete: ${error.code}`);
        } else {
            logger.error(`Errore sconosciuto: ${error.message}`);
        }

        /* Rilancio dell'errore per la gestione esterna */
        throw error;
    }
}

// Funzione per validare l'URL
function isValidUrl(url) {
    try {
        new URL(url);  // Tentativo di creare un oggetto URL
        return true;   // Se ha successo, l'URL è valido
    } catch (_) {
        return false;  // Se si verifica un errore, l'URL non è valido
    }
}

// Funzione per calcolare il checksum (hash) di un file
function calculateChecksum(filePath) {
    return new Promise((resolve, reject) => {
        const hash = crypto.createHash('sha256');
        const stream = fs.createReadStream(filePath);

        stream.on('data', (data) => hash.update(data));
        stream.on('end', () => resolve(hash.digest('hex')));
        stream.on('error', (err) => reject(err));
    });
}

// Funzione per salvare il checksum in un file JSON
async function saveChecksumToJSON(fileName, checksum) {
    const jsonFilePath = path.join(__dirname, 'checksum_pdfRelH9.json');
    let checksumData = { counter: 0 };

    /* Lettura del file JSON esistente, se presente */
    if (fs.existsSync(jsonFilePath)) {
        const data = fs.readFileSync(jsonFilePath, 'utf8');
        checksumData = JSON.parse(data);
        checksumData.counter += 1;
    } else {
        checksumData.counter = 1;
    }

    /* Creazione di un oggetto con il checksum e la data/ora attuale in formato ISO 8601 */
    const timestamp = new Date().toISOString();
    checksumData[fileName] = {
        checksum: checksum,
        timestamp: timestamp 
    };

    /* Scrittura dei dati aggiornati nel file JSON */
    fs.writeFileSync(jsonFilePath, JSON.stringify(checksumData, null, 4), 'utf8');
}
