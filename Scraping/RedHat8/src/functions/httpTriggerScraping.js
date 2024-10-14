const { app } = require('@azure/functions');
const fs = require("fs");
const path = require("path");
const axios = require('axios');
const puppeteer = require("puppeteer");
const winston = require("winston");
const crypto = require('crypto');

// Configurazione del logger di Red Hat 8
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
            logger.info("Richiesta ricevuta. Controllo dei checksum e avvio del processo di scraping...");

            /* Avvio del controllo dei checksum e dello scraping in background senza bloccare il client */
            await handleChecksumAndScraping();

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

// Funzione per verficare l'esisenza del file checksum_pdfRelH8.json
async function handleChecksumAndScraping() {
    const checksumFilePath = path.join(__dirname, 'checksum_pdfRelH8.json');

    /* Controllo dell'esistenza del file checksum_pdfRelH8.json */
    if (fs.existsSync(checksumFilePath)) {
        const checksumData = JSON.parse(fs.readFileSync(checksumFilePath, 'utf8'));

        if (Object.keys(checksumData).length === 1 && checksumData.counter === 0) {
            logger.warn("Il file checksum_pdfRelH8.json è vuoto. Avvio della sonda e creazione dei nuovi checksum...");
            await scrapeAndDownloadDocuments();
        }
        else {
            logger.info("Il file checksum_pdfRelH8.json non è vuoto. Avvio del confronto dei checksum...");
            await scrapeAndCompareChecksums(checksumData);
        }

    }
    else {
        logger.warn("Il file checksum non esiste. Creazione del file e avvio dello scraping...");
        await scrapeAndDownloadDocuments();
    }

}

// Funzione per gestire lo scraping e il confronto dei checksum
async function scrapeAndCompareChecksums(oldChecksumData) {
    try {
        /* Avvio del browser Puppeteer */
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

        /* Navigazione alla pagina di documentazione RedHat 8 */
        await page.goto("https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8", { waitUntil: 'networkidle2' });

        /* Selezione degli elementi e iterazione con la pagina web */
        const sections = await page.$$eval("a[href*='/en/documentation/red_hat_enterprise_linux/8/html/']", links => {
            const uniqueLinks = new Set(links.map(link => link.href));
            return Array.from(uniqueLinks);
        });

        if (sections.length === 0) {
            throw new Error("Nessuna sezione trovata");
        }

        const newChecksumData = { counter: 0 };
        const changedFiles = [];

        for (const sectionLink of sections) {
            const page = await browser.newPage();
            try {
                await page.goto(sectionLink, { waitUntil: 'networkidle2' });

                // Ricerca dell'elemento PDF nella pagina
                const pdfElement = await page.$("#pdf-download a");
                if (pdfElement) {
                    const pdfHref = await pdfElement.getProperty("href");
                    const pdfUrl = await pdfHref.jsonValue();

                    // Download del PDF
                    const filePath = await downloadPDF(pdfUrl, path.join(__dirname, 'documentsRelH8'));
                    
                    const checksum = await calculateChecksum(filePath);
                    const fileName = path.basename(pdfUrl);
                    newChecksumData.counter += 1;
                    newChecksumData[fileName] = {
                        checksum: checksum,
                        timestamp: new Date().toISOString()
                    };

                    // Confronto dei checksum
                    if (oldChecksumData[fileName] && oldChecksumData[fileName].checksum !== checksum) {
                        const pdfName = path.basename(fileName);
                        logger.info(`Il documento ${pdfName} è cambiato.`);
                        
                        // Download e sostituzione del documento aggiornato
                        const updated_file = await downloadPDF(pdfUrl, path.join(__dirname, 'documentsRelH8'));
                        const updated_pdfName = path.basename(updated_file);
                        changedFiles.push(updated_pdfName);
                    }

                } 

            } catch (error) {
                logger.error(`Errore durante la navigazione o il download dalla sezione ${sectionLink}: ${error.message}`);
            } finally {
                await page.close();
            }
        }

        // Log dei risultati del confronto
        if (changedFiles.length > 0) {
            logger.info(`Documenti cambiati: ${changedFiles.join(", ")}`);
        }
        else {
            logger.info("Nessun documento è stato modificato.");
        }

        // Aggiornamento del file checksum
        fs.writeFileSync(path.join(__dirname, 'checksum_pdfRelH8.json'), JSON.stringify(newChecksumData, null, 4), 'utf8');
        logger.info("Checksum aggiornati con successo.");

    } catch (error) {
        logger.error(`Errore durante lo scraping: ${error.message}`);
    } finally {
        if (browser) {
            await browser.close();
            logger.info("Browser chiuso con successo.");
        }
    }
}

// Funzione per gestire lo scraping e il download
async function scrapeAndDownloadDocuments() {
    try {
        /* Avvio del browser Puppeteer */
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

        /* Navigazione alla pagina di documentazione RedHat 8 */
        await page.goto("https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8", { waitUntil: 'networkidle2' });

        /* Selezione degli elementi e iterazione con la pagina web */
        const sections = await page.$$eval("a[href*='/en/documentation/red_hat_enterprise_linux/8/html/']", links => {
            const uniqueLinks = new Set(links.map(link => link.href));
            return Array.from(uniqueLinks);
        });

        if (sections.length === 0) {
            const message = "Numero di sezioni trovate: 0";
            logger.error(message);
            throw new Error(message);
        } else {
            logger.info(`Numero di sezioni trovate: ${sections.length}`);
        }

        const downloadedFiles = [];

        /* Download dei PDF */
        for (const sectionLink of sections) {
            const page = await browser.newPage();
            try {
                // Navigazione al link della sezione
                await page.goto(sectionLink, { waitUntil: 'networkidle2' });

                // Ricerca dell'elemento PDF nella pagina
                const pdfElement = await page.$("#pdf-download a");
                if (pdfElement) {
                    const pdfHref = await pdfElement.getProperty("href");
                    const pdfUrl = await pdfHref.jsonValue();

                    // Download del PDF
                    const filePath = await downloadPDF(pdfUrl, path.join(__dirname, 'documentsRelH8'));
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

                // Calcolo del checksum dopo il download
                try {
                    const checksum = await calculateChecksum(filePath);
                    await saveChecksumToJSON(fileName, checksum); // Salva il checksum nel file JSON
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
    const jsonFilePath = path.join(__dirname, 'checksum_pdfRelH8.json');
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
