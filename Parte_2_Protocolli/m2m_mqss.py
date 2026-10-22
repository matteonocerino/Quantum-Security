"""
m2m_mqss.py — Simulazione e grafici M2M-MQSS in un unico file
Basato su: Tsai et al., EPJ Quantum Technology 12, 99 (2025)

PROTOCOLLO: Multiparty-to-Multiparty Mediated Quantum Secret Sharing
  - TP  (Trusted Party quantistico, ma NON fidato): genera e distribuisce il graph state
  - N Dealers (Alice_1..Alice_N): utenti classici, generano collettivamente il segreto
  - M Agents  (Bob_1..Bob_M)   : utenti classici, ricostruiscono il segreto cooperando

Capacita' quantistiche richieste ai partecipanti (ambiente ristretto):
  1. Misura in Z-basis
  2. Operazione di Hadamard (H)
  Il TP non puo' apprendere nulla della master key grazie alla struttura del graph state.

Uso:
    python3 m2m_mqss.py           # esegue simulazione, salva tutto in results.json, genera grafici
    python3 m2m_mqss.py --plot    # carica results.json e rigenera solo i grafici (istantaneo)
"""

import sys
import json
import random
import os

import netsquid as ns
from netsquid.qubits import qubitapi as qapi

import matplotlib
matplotlib.use('Agg')   # backend non interattivo, salva su file PNG
import matplotlib.pyplot as plt

# ──────────────────────────────────────────────
#  COSTANTE — file dove vengono salvati i dati
# ──────────────────────────────────────────────
DATA_FILE = 'results.json'


# ═══════════════════════════════════════════════════════════════
#  SEZIONE 1 — COSTRUZIONE DEL COMPLETE GRAPH STATE
# ═══════════════════════════════════════════════════════════════

def create_complete_graph_state(n_qubits):
    """
    Genera un complete graph state a n_qubits qubit usando NetSquid.

    Un complete graph state e' costruito in due passi:
      1. Inizializza ogni qubit in |+> = H|0> (superposizione uniforme)
      2. Applica un gate CZ (controlled-Z) su ogni coppia (i, j) con i < j
         => in un grafo completo, ogni nodo e' connesso a tutti gli altri

    Questa struttura garantisce la proprieta' di correlazione fondamentale
    del protocollo M2M-MQSS (Eq. 5 del paper):
        XOR(tutti i risultati) = bt = t mod 2
    dove x_count = 2t + 1 (numero dispari di misure in X-basis).

    Parametri:
        n_qubits : numero totale di qubit = N_dealers + M_agents

    Restituisce:
        qubit_list : lista di qubit NetSquid nel graph state
    """
    qubit_list = []
    for _ in range(n_qubits):
        q, = qapi.create_qubits(1)
        qapi.operate(q, ns.H)        # |0> -> |+>
        qubit_list.append(q)

    # Applica CZ su ogni coppia — complete graph = tutti connessi con tutti
    for i in range(n_qubits):
        for j in range(i + 1, n_qubits):
            qapi.operate([qubit_list[i], qubit_list[j]], ns.CZ)

    return qubit_list


# ═══════════════════════════════════════════════════════════════
#  SEZIONE 2 — MODELLO DI RUMORE DEL CANALE
# ═══════════════════════════════════════════════════════════════

def apply_channel_noise(qubit, noise_type='none', noise_rate=0.0):
    """
    Applica rumore al qubit durante la trasmissione dal TP al partecipante.

    Modelli supportati:

    'depolar' — Depolarizing noise:
        Con probabilita' noise_rate, applica casualmente uno dei tre gate
        di Pauli: X (bit flip), Y (bit+phase flip), Z (phase flip),
        ciascuno con probabilita' noise_rate/3.
        E' il modello di rumore piu' generale e realistico.

    'dephase' — Dephasing noise (T2):
        Con probabilita' noise_rate, applica solo il gate Z (phase flip).
        Modella la perdita di coerenza di fase senza errori di bit.
        Tipico di memorie quantistiche con breve tempo di coerenza T2.

    'none' — Canale ideale:
        Nessun rumore applicato. Usato come riferimento per verificare
        la correttezza del protocollo.

    Parametri:
        qubit      : qubit NetSquid su cui applicare il rumore
        noise_type : 'depolar' | 'dephase' | 'none'
        noise_rate : probabilita' di errore in [0.0, 1.0]
    """
    if noise_type == 'none' or noise_rate == 0.0:
        return

    r = random.random()

    if noise_type == 'depolar':
        if r < noise_rate / 3:
            qapi.operate(qubit, ns.X)       # errore X (bit flip)
        elif r < 2 * noise_rate / 3:
            qapi.operate(qubit, ns.Y)       # errore Y (bit + phase flip)
        elif r < noise_rate:
            qapi.operate(qubit, ns.Z)       # errore Z (phase flip)

    elif noise_type == 'dephase':
        if r < noise_rate:
            qapi.operate(qubit, ns.Z)       # solo errore di fase


# ═══════════════════════════════════════════════════════════════
#  SEZIONE 3 — SINGOLO ROUND DEL PROTOCOLLO M2M-MQSS
# ═══════════════════════════════════════════════════════════════

def run_single_round(n_dealers, n_agents, noise_type='none', noise_rate=0.0):
    """
    Esegue un singolo round del protocollo M2M-MQSS.

    Passi del protocollo (corrispondenti al paper Tsai et al. 2025):

    Step 1 — Generazione e distribuzione (TP):
        Il TP genera un complete graph state di (N+M) qubit e invia
        un qubit a ciascun partecipante tramite il canale quantistico.
        Durante la trasmissione viene applicato il rumore del canale.

    Step 2 — Misura dei partecipanti:
        Ogni partecipante sceglie casualmente:
          - Z-basis  (choice=0): misura direttamente in Z
          - X-basis  (choice=1): applica H poi misura in Z
        La scelta e' indipendente tra tutti i partecipanti.

    Step 3 — Selezione dei round validi:
        Il round e' utile SOLO se il numero di partecipanti che hanno
        scelto X-basis e' DISPARI (x_count % 2 == 1).
        Questo garantisce la proprieta' di correlazione del graph state.

    Step 4 — Verifica della correlazione (check bit):
        In un round valido con x_count = 2t+1, deve valere:
            XOR(tutti i risultati) = bt = t mod 2
        Se questa condizione e' violata, c'e' stato un errore
        (rumore o eavesdropping).

    Parametri:
        n_dealers  : numero di dealers (Alice_1..Alice_N)
        n_agents   : numero di agents  (Bob_1..Bob_M)
        noise_type : tipo di rumore del canale
        noise_rate : intensita' del rumore

    Restituisce:
        is_valid   : bool  — round utile (x_count dispari)
        error_flag : bool  — violazione della correlazione del graph state
        mr_dealers : list  — risultati di misura dei dealers [0/1]
        mr_agents  : list  — risultati di misura degli agents [0/1]
        t_coeff    : int   — coefficiente t con x_count = 2t+1
    """
    n_total = n_dealers + n_agents

    # Step 1: TP genera il complete graph state e lo distribuisce
    graph_qubits = create_complete_graph_state(n_total)
    for q in graph_qubits:
        apply_channel_noise(q, noise_type=noise_type, noise_rate=noise_rate)

    # Step 2: ogni partecipante sceglie la base e misura
    choices = []    # 0 = Z-basis, 1 = X-basis
    results = []    # risultati di misura in {0, 1}

    for q in graph_qubits:
        choice = random.randint(0, 1)
        choices.append(choice)

        if choice == 1:
            qapi.operate(q, ns.H)   # X-basis: applica H prima di misurare

        m, _ = qapi.measure(q, observable=ns.Z)
        results.append(1 if m else 0)   # True/False -> 1/0

    # Step 3: controlla se il round e' valido (x_count dispari)
    x_count = sum(choices)
    if x_count % 2 == 0:
        return False, False, [], [], 0   # round scartato

    # Calcola il coefficiente t e il bit bt
    t_coeff = (x_count - 1) // 2
    bt = t_coeff % 2

    # Separa i risultati tra dealers e agents
    mr_dealers = results[:n_dealers]
    mr_agents  = results[n_dealers:]

    # Step 4: verifica la correlazione del graph state (Eq. 5 del paper)
    # XOR di tutti i risultati deve essere uguale a bt
    xor_all = 0
    for r in results:
        xor_all ^= r
    error_flag = (xor_all != bt)   # True = errore rilevato

    return True, error_flag, mr_dealers, mr_agents, t_coeff


# ═══════════════════════════════════════════════════════════════
#  SEZIONE 4 — PROTOCOLLO COMPLETO SU N ROUNDS
# ═══════════════════════════════════════════════════════════════

def run_protocol(n_dealers, n_agents, n_rounds=1000,
                 noise_type='none', noise_rate=0.0, check_ratio=0.5):
    """
    Esegue il protocollo M2M-MQSS completo per n_rounds round totali.

    Dopo aver raccolto tutti i round validi, li divide in:
      - Check bits  (check_ratio, default 50%): usati per rilevare errori/eavesdropping
      - Key bits    (1 - check_ratio):          usati per costruire la master key

    L'error rate viene calcolato sui check bits come:
        error_rate = n_errori / n_check

    In un sistema reale, se error_rate > soglia (tipicamente ~11%),
    la sessione viene abortita per sospetto eavesdropping.

    Parametri:
        n_dealers   : numero di dealers
        n_agents    : numero di agents
        n_rounds    : numero totale di round da eseguire
        noise_type  : tipo di rumore ('depolar', 'dephase', 'none')
        noise_rate  : intensita' del rumore [0.0, 1.0]
        check_ratio : frazione di round validi usati come check bit

    Restituisce dizionario con:
        error_rate   : tasso di errore sui check bit
        valid_rounds : numero di round validi (x_count dispari)
        key_bits     : numero di bit disponibili per la chiave
        success_rate : valid_rounds / n_rounds
    """
    valid_rounds = 0
    all_valid    = []   # accumula (error_flag, mr_dealers, mr_agents, t_coeff)

    for _ in range(n_rounds):
        is_valid, error_flag, mr_d, mr_a, t = run_single_round(
            n_dealers, n_agents,
            noise_type=noise_type,
            noise_rate=noise_rate
        )
        if not is_valid:
            continue    # round scartato (x_count pari)
        valid_rounds += 1
        all_valid.append((error_flag, mr_d, mr_a, t))

    if valid_rounds == 0:
        return {'error_rate': 0.0, 'valid_rounds': 0,
                'key_bits': 0, 'success_rate': 0.0}

    # Split check/key bits
    n_check = int(valid_rounds * check_ratio)
    n_key   = valid_rounds - n_check

    # Calcola error rate sui check bit
    errors     = sum(1 for (ef, _, _, _) in all_valid[:n_check] if ef)
    error_rate = errors / n_check if n_check > 0 else 0.0

    return {
        'error_rate'  : error_rate,
        'valid_rounds': valid_rounds,
        'key_bits'    : n_key,
        'success_rate': valid_rounds / n_rounds
    }


# ═══════════════════════════════════════════════════════════════
#  SEZIONE 5 — ESPERIMENTI
# ═══════════════════════════════════════════════════════════════

def run_all_experiments(n_rounds=2000):
    """
    Esegue tutti e quattro gli esperimenti e restituisce i risultati
    in un dizionario serializzabile in JSON.

    Esperimento 1: Error rate vs noise rate
        Fissa N=2 dealers, M=2 agents e varia il noise rate da 0 a 0.30.
        Confronta depolarizing e dephasing.
        Mostra dove il protocollo supera la soglia di sicurezza.

    Esperimento 2: Scalabilita' al variare dei partecipanti
        Fissa noise_rate=0.05 e varia (N, M) da (1,1) a (5,5).
        Confronta canale ideale, depolarizing e dephasing.
        Mostra come l'error rate cresce con il numero di partecipanti.

    Esperimento 3: Demo correttezza del recupero della master key
        Dimostra che in canale ideale la master key viene recuperata
        perfettamente dagli agents combinando i loro risultati con
        i valori annunciati dai dealers.

    Esperimento 4: Impatto del rumore sul recupero della master key
        Confronta visivamente il recupero della chiave in tre scenari:
        canale ideale, rumore moderato e rumore alto.
    """
    results = {}

    # ── Esperimento 1: error rate vs noise rate ──────────────────────────
    print("\n[1/4] Esperimento 1: Error rate vs Noise rate (N=2, M=2)...")
    noise_rates = [0.00, 0.01, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30]
    dep_errors, deph_errors = [], []

    for nr in noise_rates:
        d = run_protocol(2, 2, n_rounds=n_rounds, noise_type='depolar', noise_rate=nr)
        p = run_protocol(2, 2, n_rounds=n_rounds, noise_type='dephase', noise_rate=nr)
        dep_errors.append(round(d['error_rate'], 4))
        deph_errors.append(round(p['error_rate'], 4))
        print(f"  noise={nr:.2f} | depolar={d['error_rate']:.4f} | dephase={p['error_rate']:.4f}")

    results['exp1'] = {
        'noise_rates': noise_rates,
        'dep_errors' : dep_errors,
        'deph_errors': deph_errors,
        'n_rounds'   : n_rounds,
    }

    # ── Esperimento 2: scalabilita' ──────────────────────────────────────
    print("\n[2/4] Esperimento 2: Scalabilita' (noise_rate=0.05)...")
    configs = [(1,1), (2,2), (3,3), (4,4), (5,5)]
    ideal_e, dep_e, deph_e, key_bits_list = [], [], [], []

    for (nd, na) in configs:
        i = run_protocol(nd, na, n_rounds=n_rounds, noise_type='none',    noise_rate=0.0)
        d = run_protocol(nd, na, n_rounds=n_rounds, noise_type='depolar', noise_rate=0.05)
        p = run_protocol(nd, na, n_rounds=n_rounds, noise_type='dephase', noise_rate=0.05)
        ideal_e.append(round(i['error_rate'], 4))
        dep_e.append(round(d['error_rate'], 4))
        deph_e.append(round(p['error_rate'], 4))
        key_bits_list.append(d['key_bits'])
        print(f"  N={nd},M={na} | ideal={i['error_rate']:.4f} | "
              f"depolar={d['error_rate']:.4f} | dephase={p['error_rate']:.4f} | "
              f"key_bits={d['key_bits']}")

    results['exp2'] = {
        'participants': [n+m for n,m in configs],
        'labels'      : [f'N={n},M={m}' for n,m in configs],
        'ideal_e'     : ideal_e,
        'dep_e'       : dep_e,
        'deph_e'      : deph_e,
        'key_bits'    : key_bits_list,
        'noise_rate'  : 0.05,
        'n_rounds'    : n_rounds,
    }

    # ── Esperimento 3: demo recupero master key ───────────────────────────
    print("\n[3/4] Esperimento 3: Demo recupero master key (N=2, M=2, 16 bit)...")
    n_d, n_a, key_len = 2, 2, 16

    # Ogni dealer genera una sub-key casuale
    sub_keys = [[random.randint(0,1) for _ in range(key_len)] for _ in range(n_d)]

    # La master key e' lo XOR di tutte le sub-keys dei dealers
    master_key = [0] * key_len
    for sk in sub_keys:
        for b in range(key_len):
            master_key[b] ^= sk[b]

    # Strutture per raccogliere i dati del protocollo
    dealer_enc   = [[] for _ in range(n_d)]    # E_i = K_i XOR S_i (annunciati pubblicamente)
    agent_shares = [[] for _ in range(n_a)]    # risultati di misura degli agents
    t_seq        = []                           # sequenza dei coefficienti t

    # Raccoglie key_len bit validi dal protocollo
    bits_ok = 0
    while bits_ok < key_len:
        is_valid, _, mr_d, mr_a, t = run_single_round(n_d, n_a, 'none', 0.0)
        if not is_valid:
            continue
        for i in range(n_d):
            dealer_enc[i].append(sub_keys[i][bits_ok] ^ mr_d[i])
        for j in range(n_a):
            agent_shares[j].append(mr_a[j])
        t_seq.append(t)
        bits_ok += 1

    # Recupero della master key da parte degli agents:
    # K_master = XOR(E_i) XOR XOR(S_Bobj) XOR bt
    recovered = []
    for pos in range(key_len):
        xor_enc    = 0
        for i in range(n_d):
            xor_enc ^= dealer_enc[i][pos]       # XOR dei valori annunciati
        xor_agents = 0
        for j in range(n_a):
            xor_agents ^= agent_shares[j][pos]  # XOR dei risultati degli agents
        bt = t_seq[pos] % 2                     # bit di correzione bt
        recovered.append(xor_enc ^ xor_agents ^ bt)

    match = (recovered == master_key)
    print(f"  Master key   : {master_key}")
    print(f"  Recovered key: {recovered}")
    print(f"  Recupero corretto: {'SI' if match else 'NO'}")

    results['exp3'] = {
        'master_key'   : master_key,
        'recovered_key': recovered,
        'match'        : match,
    }

    # ── Esperimento 4: impatto rumore sul recupero chiave ─────────────────
    print("\n[4/4] Esperimento 4: Impatto rumore sul recupero chiave (N=2, M=2)...")
    n_d, n_a = 2, 2
    scenarios_cfg = [
        ('Canale ideale\n(noise=0.00)',   'none',    0.00),
        ('Rumore moderato\n(noise=0.05)', 'depolar', 0.05),
        ('Rumore alto\n(noise=0.15)',     'depolar', 0.15),
    ]

    # Genera una master key fissa uguale per tutti e tre gli scenari
    random.seed(99)
    sub_keys_4 = [[random.randint(0,1) for _ in range(key_len)] for _ in range(n_d)]
    master_key_4 = [0] * key_len
    for sk in sub_keys_4:
        for b in range(key_len):
            master_key_4[b] ^= sk[b]

    scenarios_results = []
    for (label, noise_type, noise_rate) in scenarios_cfg:
        random.seed(42)   # seed fisso per riproducibilita'
        dealer_enc_4   = [[] for _ in range(n_d)]
        agent_shares_4 = [[] for _ in range(n_a)]
        t_seq_4        = []
        bits_ok = 0

        while bits_ok < key_len:
            is_valid, _, mr_d, mr_a, t = run_single_round(
                n_d, n_a, noise_type=noise_type, noise_rate=noise_rate)
            if not is_valid:
                continue
            for i in range(n_d):
                dealer_enc_4[i].append(sub_keys_4[i][bits_ok] ^ mr_d[i])
            for j in range(n_a):
                agent_shares_4[j].append(mr_a[j])
            t_seq_4.append(t)
            bits_ok += 1

        recovered_4 = []
        for pos in range(key_len):
            xor_e = 0
            for i in range(n_d): xor_e ^= dealer_enc_4[i][pos]
            xor_a = 0
            for j in range(n_a): xor_a ^= agent_shares_4[j][pos]
            recovered_4.append(xor_e ^ xor_a ^ (t_seq_4[pos] % 2))

        n_errors   = sum(1 for a, b in zip(master_key_4, recovered_4) if a != b)
        error_rate = n_errors / key_len
        print(f"  {label.replace(chr(10), ' ')}: "
              f"errori={n_errors}/{key_len}, error_rate={error_rate:.2f}")

        scenarios_results.append({
            'label'     : label,
            'noise_type': noise_type,
            'noise_rate': noise_rate,
            'recovered' : recovered_4,
            'n_errors'  : n_errors,
            'error_rate': error_rate,
        })

    results['exp4'] = {
        'master_key': master_key_4,
        'scenarios' : scenarios_results,
    }

    return results


# ═══════════════════════════════════════════════════════════════
#  SEZIONE 6 — GENERAZIONE GRAFICI
# ═══════════════════════════════════════════════════════════════

def make_plots(data):
    """
    Genera tutti i grafici PNG dai dati degli esperimenti.

    plot_noise_sweep.png    — Exp1: error rate vs noise rate
    plot_scalability.png    — Exp2: error rate vs numero partecipanti
    plot_keybits.png        — Exp2: key bits prodotti per configurazione
    plot_summary.png        — Exp3: recupero master key + confronto canali
    plot_noisy_recovery.png — Exp4: impatto del rumore sul recupero chiave
    """
    plt.rcParams.update({
        'figure.facecolor' : 'white',
        'axes.facecolor'   : '#f8f9fa',
        'axes.grid'        : True,
        'grid.alpha'       : 0.4,
        'axes.spines.top'  : False,
        'axes.spines.right': False,
        'font.size'        : 11,
        'axes.titlesize'   : 13,
        'axes.labelsize'   : 11,
        'legend.fontsize'  : 10,
        'lines.linewidth'  : 2.0,
        'lines.markersize' : 7,
    })
    C = {'dep': '#e63946', 'deph': '#457b9d', 'ideal': '#2d6a4f', 'error': '#f4a261'}

    e1 = data['exp1']
    e2 = data['exp2']
    e3 = data['exp3']
    e4 = data['exp4']

    # ── Grafico 1: Error rate vs Noise rate ──────────────────────────────
    # Mostra come l'error rate cresce al crescere del rumore.
    # La soglia dell'11% e' la tipica soglia di sicurezza QKD:
    # sopra quella soglia si sospetta eavesdropping e la sessione va abortita.
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(e1['noise_rates'], e1['dep_errors'],
            color=C['dep'], marker='o', label='Depolarizing noise')
    ax.plot(e1['noise_rates'], e1['deph_errors'],
            color=C['deph'], marker='s', linestyle='--', label='Dephasing noise')
    ax.axhline(0.11, color='gray', linestyle=':', lw=1.5,
               label='Soglia sicurezza (11%)')
    ax.axhspan(0, 0.11, alpha=0.07, color='green')
    ax.text(0.21, 0.025, 'Zona sicura', color='green', fontsize=9)
    ax.set_xlabel('Noise Rate')
    ax.set_ylabel('Error Rate')
    ax.set_title(f'M2M-MQSS: Error Rate vs Noise Rate\n'
                 f'(N=2 dealers, M=2 agents, {e1["n_rounds"]} rounds)')
    ax.legend()
    ax.set_xlim([-0.01, 0.32])
    ax.set_ylim([-0.01, 0.50])
    fig.tight_layout()
    fig.savefig('plot_noise_sweep.png', dpi=150, bbox_inches='tight')
    print("Salvato: plot_noise_sweep.png")
    plt.close(fig)

    # ── Grafico 2: Scalabilita' ───────────────────────────────────────────
    # Mostra come l'error rate cresce al crescere del numero di partecipanti.
    # In canale ideale resta sempre a 0 (correttezza del protocollo).
    # Con rumore cresce perche' ogni qubit aggiuntivo porta ulteriore errore.
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(e2['participants'], e2['ideal_e'],
            color=C['ideal'], marker='^', label='Canale ideale')
    ax.plot(e2['participants'], e2['dep_e'],
            color=C['dep'], marker='o',
            label=f'Depolarizing (p={e2["noise_rate"]})')
    ax.plot(e2['participants'], e2['deph_e'],
            color=C['deph'], marker='s', linestyle='--',
            label=f'Dephasing (p={e2["noise_rate"]})')
    ax.axhline(0.11, color='gray', linestyle=':', lw=1.5,
               label='Soglia sicurezza (11%)')
    ax.set_xlabel('Numero totale partecipanti (N dealers + M agents)')
    ax.set_ylabel('Error Rate')
    ax.set_title(f'M2M-MQSS: Scalabilita\' al variare dei partecipanti\n'
                 f'(noise_rate={e2["noise_rate"]}, {e2["n_rounds"]} rounds)')
    ax.set_xticks(e2['participants'])
    ax.set_xticklabels(e2['labels'], fontsize=9)
    ax.legend()
    fig.tight_layout()
    fig.savefig('plot_scalability.png', dpi=150, bbox_inches='tight')
    print("Salvato: plot_scalability.png")
    plt.close(fig)

    # ── Grafico 3: Key bits prodotti ──────────────────────────────────────
    # Mostra quanti bit di chiave vengono prodotti per ogni configurazione.
    # Il numero e' stabile (~500 su 2000 rounds) perche' circa il 50% dei
    # round validi viene usato come check bit e l'altro 50% come key bits.
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(e2['labels'], e2['key_bits'],
                  color=[C['dep'] if i%2==0 else C['deph']
                         for i in range(len(e2['labels']))],
                  edgecolor='white', lw=1.5, alpha=0.85)
    for bar, val in zip(bars, e2['key_bits']):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + 5,
                str(val), ha='center', fontsize=10, fontweight='bold')
    ax.set_xlabel('Configurazione (N dealers, M agents)')
    ax.set_ylabel('Key bits prodotti')
    ax.set_title(f'M2M-MQSS: Key bits per configurazione\n'
                 f'({e2["n_rounds"]} rounds, noise_rate={e2["noise_rate"]} depolarizing)')
    ax.set_ylim([0, max(e2['key_bits']) * 1.2])
    fig.tight_layout()
    fig.savefig('plot_keybits.png', dpi=150, bbox_inches='tight')
    print("Salvato: plot_keybits.png")
    plt.close(fig)

    # ── Grafico 4: Summary — correttezza e confronto canali ───────────────
    # Sinistra: confronto bit a bit tra master key e recovered key.
    #   In canale ideale devono essere identiche (recupero perfetto).
    # Destra: error rate per tipo di canale (N=2, M=2).
    #   Mostra che con rumore moderato (p=0.05) il protocollo e' ancora
    #   vicino alla soglia di sicurezza dell'11%.
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    mk      = e3['master_key']
    rk      = e3['recovered_key']
    bit_pos = list(range(len(mk)))

    axes[0].step(bit_pos, mk, where='mid',
                 color=C['ideal'], lw=2, label='Master key')
    axes[0].step(bit_pos, rk, where='mid',
                 color=C['dep'], lw=2, linestyle='--', label='Recovered key')
    axes[0].set_xlabel('Bit position')
    axes[0].set_ylabel('Bit value')
    axes[0].set_title('Recupero master key\n(canale ideale)')
    axes[0].legend()
    axes[0].set_yticks([0, 1])
    axes[0].set_ylim([-0.2, 1.4])

    cats    = ['Ideale\n(noise=0)', 'Depolar\n(p=0.05)', 'Dephase\n(p=0.05)']
    # Prende i valori N=2,M=2 dall'esperimento 2 (indice 1)
    e_vals  = [e2['ideal_e'][1], e2['dep_e'][1], e2['deph_e'][1]]
    bcolors = [C['ideal'], C['dep'], C['deph']]

    bars2 = axes[1].bar(cats, e_vals,
                        color=bcolors, edgecolor='white', lw=1.5, alpha=0.85)
    axes[1].axhline(0.11, color='gray', linestyle=':', lw=1.5,
                    label='Soglia sicurezza')
    for bar, val in zip(bars2, e_vals):
        axes[1].text(bar.get_x() + bar.get_width()/2,
                     bar.get_height() + 0.003,
                     f'{val:.4f}', ha='center', fontsize=10)
    axes[1].set_ylabel('Error Rate')
    axes[1].set_title('Error rate per tipo di canale\n(N=2, M=2)')
    axes[1].set_ylim([0, 0.16])
    axes[1].legend()

    fig.suptitle('M2M-MQSS: Correttezza e sicurezza del protocollo',
                 fontsize=13, fontweight='bold')
    fig.tight_layout()
    fig.savefig('plot_summary.png', dpi=150, bbox_inches='tight')
    print("Salvato: plot_summary.png")
    plt.close(fig)

    # ── Grafico 5: Impatto rumore sul recupero chiave ─────────────────────
    # Tre pannelli sovrapposti — uno per scenario.
    # I bit errati vengono evidenziati in arancione.
    # Mostra visivamente come il rumore degrada la qualita' del recupero.
    master_key = e4['master_key']
    scenarios  = e4['scenarios']
    key_len    = len(master_key)
    bit_pos    = list(range(key_len))

    fig, axes = plt.subplots(3, 1, figsize=(12, 9))
    colors = [C['ideal'], C['deph'], C['dep']]

    for ax, scenario, color in zip(axes, scenarios, colors):
        recovered  = scenario['recovered']
        n_errors   = scenario['n_errors']
        error_rate = scenario['error_rate']
        label      = scenario['label']

        # Traccia master key
        ax.step(bit_pos, master_key, where='mid',
                color='#333333', lw=2, label='Master key', zorder=3)

        # Evidenzia i bit errati in arancione
        for pos in range(key_len):
            if master_key[pos] != recovered[pos]:
                ax.axvspan(pos - 0.5, pos + 0.5, alpha=0.25,
                           color=C['error'], zorder=1)

        # Traccia recovered key
        ax.step(bit_pos, recovered, where='mid',
                color=color, lw=2, linestyle='--',
                label=f'Recovered key ({n_errors} errori)', zorder=2)

        ax.set_title(label, fontsize=11, fontweight='bold')
        ax.set_ylabel('Bit value')
        ax.set_yticks([0, 1])
        ax.set_ylim([-0.3, 1.5])
        ax.set_xlim([-0.5, key_len - 0.5])
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.text(0.02, 0.85, f'Error rate: {error_rate:.0%}',
                transform=ax.transAxes, fontsize=10,
                color='red' if error_rate > 0 else 'green',
                fontweight='bold')

    axes[-1].set_xlabel('Bit position')
    fig.suptitle('M2M-MQSS: Impatto del rumore sul recupero della master key\n'
                 '(N=2 dealers, M=2 agents, 16 bit)',
                 fontsize=13, fontweight='bold')
    fig.tight_layout()
    fig.savefig('plot_noisy_recovery.png', dpi=150, bbox_inches='tight')
    print("Salvato: plot_noisy_recovery.png")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    """
    Modalita' di esecuzione:

    python3 m2m_mqss.py
        Esegue tutti e quattro gli esperimenti, salva i risultati
        in results.json e genera i 5 grafici PNG.

    python3 m2m_mqss.py --plot
        Salta la simulazione, carica i dati da results.json
        e rigenera i grafici (istantaneo).
    """
    plot_only = '--plot' in sys.argv

    # Inizializza NetSquid con il formalismo a matrice densita' (DM).
    # DM e' necessario per simulare correttamente stati misti e rumore.
    # Scala come O(2^2n) in memoria — adeguato per pochi qubit (<=10).
    ns.sim_reset()
    ns.set_qstate_formalism(ns.QFormalism.DM)

    if plot_only:
        # Modalita' --plot: carica dati gia' salvati
        if not os.path.exists(DATA_FILE):
            print(f"[ERRORE] {DATA_FILE} non trovato.")
            print("Esegui prima: python3 m2m_mqss.py")
            sys.exit(1)
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        print(f"[OK] Dati caricati da {DATA_FILE}")
    else:
        # Modalita' normale: esegue tutti gli esperimenti e salva
        print("=" * 60)
        print("  M2M-MQSS Simulation — NetSquid")
        print("  Tsai et al., EPJ Quantum Technology 12, 99 (2025)")
        print("=" * 60)
        data = run_all_experiments(n_rounds=2000)
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n[OK] Tutti i dati salvati in {DATA_FILE}")

    # Genera i grafici in entrambe le modalita'
    print("\nGenerazione grafici...")
    make_plots(data)
    print("\n[OK] Grafici pronti:")
    print("  plot_noise_sweep.png    — Error rate vs noise rate")
    print("  plot_scalability.png    — Scalabilita' al variare dei partecipanti")
    print("  plot_keybits.png        — Key bits prodotti per configurazione")
    print("  plot_summary.png        — Correttezza recupero + confronto canali")
    print("  plot_noisy_recovery.png — Impatto rumore sul recupero chiave")