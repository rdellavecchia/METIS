# Planning

### **Fase 1: Acquisizione dei Documenti** (8 giorni)

- **Attività**: Implementare la sonda per raccogliere la documentazione tecnica, come Red Hat 8, direttamente dal sito ufficiale. Strutturare un sistema di raccolta dati periodico per mantenere la documentazione aggiornata.
- **Output**: Sonda funzionante che raccoglie e scarica automaticamente la documentazione necessaria.
- **Tempo stimato**: 8 giorni.

### **Fase 2: Processo di Chunking e Creazione degli Embedding** (18 giorni)

- **Attività**:
    1. Implementare il sistema per suddividere la documentazione raccolta in chunk di dimensioni gestibili.
    2. Parallelizzare l'estrazione dei metadati per collegare i chunk ai link originali.
    3. Integrare le API di ChatGPT per generare embedding vettoriali dai chunk e collegarli ai metadati.
- **Output**: Sistema di chunking operativo con embedding generati e collegati ai relativi metadati.
- **Tempo stimato**: 10 giorni per il chunking e l'estrazione dei metadati, 8 giorni per la creazione degli embedding.

### **Fase 3: Migrazione del Database Vettoriale nel Cloud** (10 giorni)

- **Attività**: Gestire la migrazione del database vettoriale nel cloud utilizzando Azure Cache for Redis con Redis VSS. Configurare e testare il sistema per ottimizzare le prestazioni in termini di velocità, disponibilità e costi.
- **Output**: Database vettoriale migrato nel cloud con prestazioni ottimizzate.
- **Tempo stimato**: 10 giorni.

### **Fase 4: Archiviazione nel Database Vettoriale** (10 giorni)

- **Attività**:
    1. Implementare il sistema di memorizzazione degli embedding generati nel database vettoriale (es. Redis VSS).
    2. Ottimizzare le query per un'interrogazione efficiente degli embedding, mantenendo i collegamenti diretti alla documentazione originale.
- **Output**: Embedding archiviati e pronti per essere interrogati con link diretti ai documenti.
- **Tempo stimato**: 10 giorni.

### **Fase 5: Ottimizzazione Routing Gerarchico** (12 giorni)

- **Attività**: Configurare e ottimizzare il modulo di Routing AI per gestire le query degli utenti. Il sistema utilizzerà un main router per smistare le query e router secondari per individuare la sezione della documentazione più pertinente.
- **Output**: Sistema di routing gerarchico funzionante e ottimizzato.
- **Tempo stimato**: 12 giorni.

### **Fase 6: Ottimizzazione tramite RRF (Ranked Retrieval Fusion)** (10 giorni)

- **Attività**: Implementare e testare l'algoritmo RRF per aggregare e ottimizzare i risultati delle query, migliorando la precisione e la rilevanza delle risposte fornite agli utenti.
- **Output**: RRF integrato e funzionante nel flusso di gestione delle query.
- **Tempo stimato**: 10 giorni.

### **Fase 7: Implementazione di una Interfaccia Grafica (UI)** (4 giorni)

- **Attività**: Implementare un'interfaccia utente per migliorare l'interazione e facilitare la raccolta di feedback dagli utenti. La UI sarà integrata con il sistema di ticketing e ottimizzata per Microsoft Teams.
- **Output**: UI integrata e operativa per interazione e raccolta feedback.
- **Tempo stimato**: 4 giorni.

### **Fase 8: Pulsante per Interrompere i Messaggi** (5 giorni)

- **Attività**: Aggiungere un pulsante per permettere agli utenti di interrompere la generazione dei messaggi da parte del chatbot durante la conversazione. Testare la funzionalità per garantire una migliore esperienza utente.
- **Output**: Pulsante di interruzione operativo.
- **Tempo stimato**: 5 giorni.

### **Fase 9: Apprendimento Tramite Feedback** (12 giorni)

- **Attività**: Implementare un sistema per raccogliere il feedback dagli utenti. Costruire un meccanismo di apprendimento automatico basato sui feedback per adattare e migliorare i risultati forniti dal sistema nel tempo.
- **Output**: Sistema di apprendimento basato sul feedback integrato e operativo.
- **Tempo stimato**: 12 giorni.

### **Fase 10: Introduzione delle Metriche di Monitoraggio** (4 giorni)

- **Attività**: Definire e implementare metriche per monitorare la precisione (ad es. F1 score), l'efficienza (tempo medio di risposta), e l'apprendimento del sistema basato sul feedback degli utenti.
- **Output**: Sistema di monitoraggio delle metriche integrato e funzionante.
- **Tempo stimato**: 4 giorni.

### **Fase 11: Integrazione con il Sistema di Ticketing** (7 giorni)

- **Attività**: Collegare il sistema di ticketing esistente al chatbot per generare risposte preliminari automatiche, migliorando la gestione dei ticket e ottimizzando il flusso di lavoro tra utenti e operatori.
- **Output**: Sistema di ticketing integrato e funzionante.
- **Tempo stimato**: 7 giorni.

| **Fase del Progetto** | **Descrizione** | **Giorni Stimati** |
| --- | --- | --- |
| **1. Acquisizione dei Documenti** | Implementare la sonda per raccogliere la documentazione tecnica (es. Red Hat 8) dal sito ufficiale e strutturare il sistema di raccolta dati periodico. | 8 giorni |
| **2. Processo di Chunking** | Implementare il sistema per suddividere la documentazione in chunk gestibili, e parallelizzare con l'estrazione dei metadati per collegare i link originali. | 10 giorni |
| **3. Creazione degli Embedding** | Integrare le API di ChatGPT per generare embedding vettoriali dai chunk e collegarli ai metadati per salvare le embedding con i link diretti alla documentazione. | 8 giorni |
| **4. Migrazione del Database Vettoriale nel Cloud** | Gestire la migrazione del database vettoriale nel cloud (Azure Cache for Redis, Redis VSS), configurando e testando le performance del sistema in termini di velocità, disponibilità e costo. | 10 giorni |
| **5. Archiviazione nel Database Vettoriale** | Implementare la memorizzazione degli embedding nel database vettoriale (es. Redis VSS), e ottimizzare le query per l'interrogazione. | 10 giorni |
| **6. Ottimizzazione Routing Gerarchico** | Configurare e ottimizzare il modulo di Routing AI, con il main router per smistare la query e i router secondari per individuare la sezione più pertinente della documentazione. | 12 giorni |
| **7. RRF (Ranked Retrieval Fusion)** | Implementare e testare l'algoritmo RRF per ottimizzare i risultati aggregati in modo efficiente, bilanciando precisione e rilevanza. | 10 giorni |
| 8. Implementazione di una interfaccia grafica | Implementare un'interfaccia utente per migliorare l'interazione e la raccolta del feedback, integrata con il sistema di ticketing e ottimizzata per Teams. | 4 giorni |
| **9. Pulsante per interrompere i messaggi** | Aggiungere e testare il pulsante di interruzione durante la generazione dei messaggi da parte del chatbot per migliorare l'esperienza utente. | 5 giorni |
| **10. Apprendimento tramite feedback** | Implementare il sistema di raccolta feedback dagli utenti e costruire un meccanismo di apprendimento per adattare i risultati alle preferenze personali di ciascun utente. | 12 giorni |
| **11. Introduzione delle metriche di monitoraggio** | Definire, implementare e testare metriche di precisione (F1 score), efficienza (tempo medio di risposta), e monitorare l'apprendimento del sistema tramite i feedback degli utenti nel tempo. | 4 giorni |
| **12. Integrazione con il sistema di ticketing** | Integrare il sistema di ticketing per ottimizzare la gestione dei ticket, generando risposte preliminari tramite il chatbot e inviandole all'operatore responsabile del ticket. | 7 giorni |