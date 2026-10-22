# 🔐 Tecnologie Quantistiche per la Sicurezza - UNISA

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Qiskit](https://img.shields.io/badge/Qiskit-Aer-purple.svg)](https://qiskit.org/)
[![NetSquid](https://img.shields.io/badge/NetSquid-Simulation-green.svg)](https://netsquid.org/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-Machine_Learning-orange.svg)](https://scikit-learn.org/)

Questo repository contiene il progetto d'esame per il corso di **Tecnologie Quantistiche per la Sicurezza** (Laurea Magistrale in Sicurezza Informatica presso l'Università degli Studi di Salerno - UNISA). 

Il lavoro esplora l'applicazione pratica del Quantum Computing e del Quantum Machine Learning (QML) a problemi reali di cybersecurity, con un approccio critico focalizzato sui vantaggi teorici e le attuali limitazioni hardware (NISQ). Il progetto è suddiviso in due moduli.

---

## 📂 Struttura della Repository

*   **`Parte_1_Quantum_ML/`**: Analisi e classificazione di URL Phishing. Contiene il Jupyter Notebook, dataset, modelli `.pkl`, diagrammi, grafici e presentazione.
*   **`Parte_2_Protocolli/`**: Simulazione del protocollo M2M-MQSS. Contiene lo script NetSquid (`m2m_mqss.py`), log JSON dei risultati, diagrammi, grafici e presentazione.

---

## 🧠 Parte 1: Quantum-Enhanced Phishing URL Detector

La prima parte del progetto valuta empiricamente l'efficacia del Quantum Machine Learning nel rilevamento di attacchi phishing tramite l'analisi degli URL. L'obiettivo è confrontare le performance di classificatori quantistici rispetto a una robusta baseline classica per comprendere se e quando il QML offra vantaggi misurabili.

### Metodologia
*   **Dataset & Feature Engineering:** Estrazione custom di 5 feature di sicurezza (*URL_Length, Shannon_Entropy, Subdomain_Count, Special_Char_Count, Digit_Ratio*) da un dataset Kaggle di oltre 549.000 URL. I dati sono stati scalati e bilanciati a 2.000 campioni per adattarsi ai limiti dei simulatori quantistici.
*   **Modelli Quantistici:** Sono stati implementati un **QSVC** (Quantum Support Vector Classifier) con *FidelityQuantumKernel* e un **VQC** (Variational Quantum Classifier) con ottimizzatore COBYLA. Entrambi sfruttano una *ZZFeatureMap* per l'encoding dei dati.
*   **Baseline Classica:** Support Vector Machine (RBF), Logistic Regression e Random Forest.

### Risultati e Analisi Critica
Nell'attuale era NISQ, i modelli classici superano quelli quantistici su questo specifico task.
*   **Performance:** Il Random Forest ha ottenuto un ROC-AUC di 0.786, contro 0.540 del QSVC e 0.510 del VQC. 
*   **Ablation Study e Limiti Hardware:** L'aumento della profondità dell'entanglement ha peggiorato le performance a causa del fenomeno dei *Barren Plateaus* nel VQC. L'analisi della kernel matrix ha inoltre evidenziato il problema della *Concentration of Measure*, che ostacola l'individuazione di un iperpiano separatore nel QSVC.

---

## 🛡️ Parte 2: Multiparty-to-Multiparty Mediated Quantum Secret Sharing (M2M-MQSS)

La seconda parte affronta la protezione del Secret Sharing in ambienti Cloud distribuiti. Lo schema classico di Shamir è vulnerabile agli attacchi dei computer quantistici; il Quantum Secret Sharing (QSS) offre invece sicurezza "post-quantum by construction" basata sul teorema di no-cloning.

### Metodologia
*   **Protocollo:** Implementazione e validazione dello schema M2M-MQSS (Tsai et al., EPJ Quantum Technology 12, 99, 2025) in un ambiente semi-quantistico ristretto. I partecipanti classici (Dealers e Agents) necessitano solo di operazioni basilari (misurazione in Z-basis e gate di Hadamard).
*   **Simulatore:** Sviluppo in Python tramite la libreria **NetSquid**. È stato utilizzato il formalismo *Density Matrix* per modellare accuratamente gli stati misti e simulare canali quantistici affetti da rumore *Depolarizing* (errori X, Y, Z) e *Dephasing* (errori Z).

### Risultati Chiave
*   **Correttezza (Canale Ideale):** In assenza di rumore, gli Agents hanno recuperato la master key con il 100% di precisione (0 errori su 16 bit), dimostrando la solidità matematica della correlazione basata su Complete Graph State.
*   **Tolleranza al Rumore Moderato:** Con un noise rate del 5%, l'error rate si è attestato al 9.8% (Depolarizing) e 9.2% (Dephasing). Il protocollo resta funzionale e sicuro, non superando la soglia di tolleranza standard dell'11% tipica della QKD.
*   **Intercettazione Rilevata:** Con rumore introdotto al 15%, il tasso di errore è salito al 31%, permettendo agli utenti di individuare l'anomalia e abortire la sessione compromessa.

---

## 🚀 Come riprodurre il progetto

Tutto il codice è scritto in **Python 3.x**. 

*   **Parte 1:** Estrai il dataset dal file `.zip` prima dell'esecuzione. I modelli pre-addestrati e i dati scalati sono disponibili in formato `.pkl` per caricare e analizzare i risultati senza rieseguire le simulazioni quantistiche (che richiedono tempo).
*   **Parte 2:** È possibile lanciare `python3 m2m_mqss.py` per avviare una nuova simulazione su NetSquid, oppure usare il flag `--plot` per ricaricare i dati da `results.json` e rigenerare i grafici in tempo reale.

## ✍️ Autore
**Matteo Nocerino**  
*Studente di Laurea Magistrale in Sicurezza Informatica - Università degli Studi di Salerno.*
