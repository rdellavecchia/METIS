# METIS - Retrieval-Augmented Generation Chatbot

## Descrizione del Progetto

**METIS** è un chatbot avanzato, sviluppato per offrire supporto tecnico intelligente e strategie efficaci per affrontare sfide tecniche quotidiane. Ispirato alla divinità greca della saggezza, METIS combina l'intelligenza artificiale con la documentazione tecnica ufficiale, garantendo risposte accurate, aggiornate e personalizzate. Il sistema è stato progettato per assistere in attività di routine, risoluzione di problemi, configurazioni e aggiornamenti software.

Il core di METIS è basato sull'approccio **Retrieval-Augmented Generation (RAG)**, che consente di superare le limitazioni dei modelli di linguaggio pre-addestrati collegandoli a fonti di conoscenza esterne, ottimizzando così la pertinenza e l'accuratezza delle risposte.

## Architettura del Sistema

METIS utilizza un'architettura a più fasi per garantire un'elaborazione efficiente delle query utente e una generazione di risposte di alta qualità:

1. **Acquisizione dei Documenti**: Una sonda automatizzata raccoglie documentazione tecnica da fonti ufficiali (ad esempio, documentazione Red Hat) e repository.
   
2. **Chunking e Embedding**: I documenti raccolti sono suddivisi in segmenti gestibili (chunk). Ogni chunk viene poi trasformato in un vettore numerico utilizzando modelli AI, rendendo possibile l'indicizzazione e la ricerca vettoriale.

3. **Archiviazione nel Database Vettoriale**: Gli embedding sono memorizzati in un database vettoriale (Redis VSS), ottimizzato per la ricerca e il recupero rapido di informazioni rilevanti.

4. **Gestione della Query**: Quando l'utente invia una query, questa viene scomposta dal sistema in sotto-domande, che vengono indirizzate al database appropriato. 

5. **Ottimizzazione e Risposta**: Utilizzando un meccanismo di fusione del recupero ordinato (**Ranked Retrieval Fusion**), i risultati delle query vengono ottimizzati per garantire la massima precisione. Il modello AI genera poi una risposta dettagliata basata su queste informazioni, fornendo all'utente un link diretto alla documentazione da cui sono state tratte le informazioni.

## Caratteristiche Principali

### Retrieval-Augmented Generation (RAG)
METIS utilizza il processo di **RAG** per combinare la potenza dei modelli AI con la ricchezza delle fonti esterne, permettendo di:
- Superare le limitazioni di accuratezza e aggiornamento dei modelli di linguaggio pre-addestrati.
- Integrare in modo efficiente informazioni recenti provenienti da fonti ufficiali.

### Redis VSS per la Ricerca di Similarità
Il cuore del sistema di ricerca è **Redis Vector Similarity Search (VSS)**, che consente di eseguire ricerche vettoriali su larga scala con alte prestazioni. Redis VSS ottimizza la ricerca di documenti tecnici o informazioni simili a quelli forniti nelle query utente, basandosi su:

- **Ricerca di Somiglianza**: Redis VSS permette di trovare vettori simili utilizzando metriche come la distanza euclidea o il coseno.
- **Indicizzazione Efficiente**: Utilizzo di algoritmi avanzati per eseguire ricerche rapide su grandi dataset di documenti tecnici.
- **Supporto per Embedding AI**: Gestisce embedding generati da modelli AI come quelli di OpenAI, per l'analisi del linguaggio naturale e applicazioni di ricerca semantica.

### Link Diretti alla Documentazione
Il sistema è in grado di generare link diretti alle sezioni pertinenti della documentazione originale. Quando una query restituisce un risultato, oltre alla risposta generata dall'AI, viene fornito un link alla fonte esatta da cui sono tratte le informazioni.

#### Vantaggi:
- **Accesso Immediato**: Collegamenti diretti a documenti specifici.
- **Affidabilità Maggiore**: Accesso a documentazione ufficiale sempre aggiornata.
- **Supporto Contestuale**: Risposte accompagnate da fonti di riferimento verificate.

### Routing Gerarchico
Il **routing gerarchico** migliora la gestione delle query utente, smistandole su più livelli per identificare la categoria di documentazione più appropriata:
- **Main Router**: Smista la query generale e la indirizza alla documentazione pertinente.
- **Router Secondari**: Analizzano il contesto specifico e restituiscono la sezione esatta della documentazione per risposte più dettagliate.

### Pulsante di Interruzione della Generazione
Gli utenti possono interrompere la generazione delle risposte del chatbot, migliorando il controllo e l'efficienza delle interazioni:
- **Controllo dell’Interazione**: Gli utenti possono fermare risposte lunghe o non pertinenti.
- **Miglioramento dell'Esperienza Utente**: Aumenta la sensazione di partecipazione attiva nella conversazione con il chatbot.

### Aggiornamento Dinamico del Database
Il database viene aggiornato automaticamente mediante una sonda periodica che verifica la presenza di nuove versioni o aggiornamenti nelle fonti tecniche (ad esempio, documentazione o patch). Questa funzione garantisce:
- **Aggiornamento Costante**: Dati sempre aggiornati.
- **Efficienza Automatica**: Minimizza l'intervento umano per mantenere il database allineato.

### Apprendimento Continuo Basato su Feedback
METIS integra un sistema di apprendimento continuo che ottimizza i risultati basandosi sul feedback degli utenti:
- **Personalizzazione delle Risposte**: I suggerimenti futuri sono adattati alle preferenze dell'utente.
- **Prevenzione di Manipolazioni Maligne**: Il feedback è tracciato per singolo utente, impedendo interferenze negative nel sistema generale.

## Metriche di Monitoraggio

Il monitoraggio delle prestazioni del sistema avviene tramite metriche chiave:
- **Precisione e Rilevanza (F1 Score)**: Combinazione di precisione e richiamo per misurare l’accuratezza delle risposte.
- **Tempo Medio di Risposta**: Per valutare l’efficienza del sistema.
- **Miglioramento Continuo**: Analisi di come le metriche migliorano nel tempo grazie all’integrazione del feedback.

## Integrazione con Sistemi di Ticketing

METIS si integra con i sistemi di ticketing aziendali per:
- **Elaborazione Automatica delle Risposte ai Ticket**: METIS genera risposte preliminari alle richieste degli utenti, che possono includere guide, soluzioni o documentazione utile.
- **Supporto agli Operatori**: Gli operatori ricevono una guida risolutiva dettagliata per affrontare il problema in modo più efficiente.
- **Ottimizzazione dei Tempi di Risposta**: Riduce il tempo necessario per risolvere i ticket e migliora la qualità del servizio.

## Requisiti

- **Redis VSS** per la gestione del database vettoriale e la ricerca di similarità.
- **Azure Cache for Redis** (opzionale): Per potenziare le prestazioni e integrare il sistema in ambienti cloud.
