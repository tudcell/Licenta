# Sistem de Audit Securizat bazat pe Blockchain cu Detecție de Anomalii

## Descriere

Această lucrare implementează un sistem de audit securizat bazat pe blockchain, în care evenimentele sunt înregistrate sub forma unor tranzacții imuabile. Integritatea și autenticitatea datelor sunt garantate prin mecanisme criptografice consacrate:

- **Funcții hash criptografice (SHA-256)**
- **Structuri de tip Merkle Tree**
- **Semnături digitale ECDSA**

Peste acest jurnal criptografic imuabil se aplică metode de **Machine Learning nesupravegheat (Isolation Forest)** pentru detectarea comportamentelor anormale în fluxul de tranzacții.

## Arhitectură

```
┌─────────────────────────────────────────────────────────────────┐
│                    BLOCKCHAIN AUDIT SYSTEM                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Crypto     │  │  Blockchain  │  │   Machine Learning   │  │
│  ├──────────────┤  ├──────────────┤  ├──────────────────────┤  │
│  │ • SHA-256    │  │ • Block      │  │ • Feature Extractor  │  │
│  │ • ECDSA      │  │ • Chain      │  │ • Isolation Forest   │  │
│  │ • Merkle Tree│  │ • Transaction│  │ • Anomaly Detector   │  │
│  │              │  │ • Wallet     │  │ • Transaction        │  │
│  │              │  │              │  │   Analyzer           │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                         WEB API (Flask)                          │
├─────────────────────────────────────────────────────────────────┤
│                        Dashboard HTML                            │
└─────────────────────────────────────────────────────────────────┘
```

## Structura Proiectului

```
Licenta/
├── main.py                 # Entry point - pornește serverul
├── demo.py                 # Script demonstrativ (fără server)
├── requirements.txt        # Dependențe Python
├── README.md              # Această documentație
│
└── src/
    ├── crypto/            # Module criptografice
    │   ├── hashing.py         # Funcții hash SHA-256
    │   ├── digital_signature.py   # Semnături ECDSA
    │   └── merkle_tree.py     # Implementare Merkle Tree
    │
    ├── blockchain/        # Core blockchain
    │   ├── transaction.py     # Structura tranzacțiilor
    │   ├── block.py           # Structura blocurilor
    │   ├── blockchain.py      # Lanțul de blocuri
    │   └── wallet.py          # Portofel digital
    │
    ├── ml/                # Machine Learning
    │   ├── feature_extractor.py   # Extragere caracteristici
    │   ├── anomaly_detector.py    # Isolation Forest
    │   └── transaction_analyzer.py # Analizator complet
    │
    ├── api/               # Web API
    │   └── app.py             # Server Flask + Dashboard
    │
    └── utils/             # Utilități
        └── data_generator.py  # Generator date test
```

## Instalare

### Cerințe
- Python 3.9+
- pip

### Pași de instalare

```bash
# 1. Clonați sau navigați în directorul proiectului
cd C:\Users\tudor\PycharmProjects\Licenta

# 2. Creați un mediu virtual (opțional dar recomandat)
python -m venv .venv
.venv\Scripts\activate

# 3. Instalați dependențele
pip install -r requirements.txt
```

## Utilizare

### Pornire Server Web

```bash
python main.py
```

Deschideți browserul la `http://localhost:5000` pentru dashboard.

### Rulare Demo (fără server)

```bash
python demo.py
```

### API Endpoints

| Endpoint | Metodă | Descriere |
|----------|--------|-----------|
| `/api/health` | GET | Health check |
| `/api/blockchain` | GET | Întreg blockchain-ul |
| `/api/blockchain/stats` | GET | Statistici |
| `/api/transaction` | POST | Creează tranzacție |
| `/api/mine` | POST | Minează bloc nou |
| `/api/anomaly/train` | POST | Antrenează detector |
| `/api/alerts` | GET | Alerte anomalii |
| `/api/audit/export` | GET | Export jurnal audit |

## Componente Tehnice

### 1. Criptografie

#### Hash-uri SHA-256
- Asigură integritatea datelor
- Utilizate pentru înlănțuirea blocurilor
- Efect avalanșă - orice modificare schimbă complet hash-ul

#### Semnături Digitale ECDSA
- Curba eliptică SECP256K1 (aceeași cu Bitcoin)
- Asigură autenticitatea și non-repudierea
- Fiecare tranzacție este semnată de emitent

#### Merkle Tree
- Agregare criptografică a tranzacțiilor
- Permite verificarea eficientă a incluziunii (O(log n))
- Merkle Root în header-ul fiecărui bloc

### 2. Blockchain

#### Structura Blocului
```
Block
├── index
├── previous_hash      # Legătură cu blocul anterior
├── timestamp
├── merkle_root        # Hash agregat al tranzacțiilor
├── nonce              # Pentru Proof of Work
├── difficulty
├── transactions[]
└── block_hash         # Hash-ul întregului header
```

#### Proof of Work
- Dificultate configurabilă (număr de zerouri)
- Asigură costul adăugării de blocuri noi

### 3. Detecție Anomalii

#### Isolation Forest
- Algoritm de Machine Learning nesupravegheat
- Izolează anomaliile prin împărțiri aleatorii
- Anomaliile necesită mai puține împărțiri pentru izolare

#### Caracteristici Extrase
1. **Temporale**: ora, ziua, weekend, noapte
2. **Valoare**: sumă, log(sumă)
3. **Comportamentale**: frecvență, timp de la ultima tranzacție
4. **Risc**: nivel risc, încercări eșuate

#### Tipuri de Anomalii Detectate
- Sume neobișnuit de mari
- Activitate nocturnă
- Rafale de tranzacții (burst)
- Login-uri eșuate multiple
- Acces la resurse critice
- Activitate în weekend

## Exemple de Cod

### Creare Tranzacție Semnată

```python
from src.blockchain.wallet import Wallet
from src.blockchain.transaction import TransactionType

# Creează wallet
alice = Wallet(name="Alice")

# Creează și semnează tranzacție
tx = alice.create_transfer(
    recipient_address="bob_address",
    amount=100.0,
    currency="RON"
)

# Verifică semnătura
print(tx.verify_signature())  # True
```

### Detecție Anomalii

```python
from src.ml.anomaly_detector import AnomalyDetector
from src.utils.data_generator import DataGenerator

# Generează date
generator = DataGenerator(num_users=10)
training_data = generator.generate_normal_transactions(100)

# Antrenează detector
detector = AnomalyDetector(contamination=0.1)
detector.fit(training_data)

# Detectează anomalii
anomaly_tx = generator.generate_anomaly('high_amount')
result = detector.predict(anomaly_tx, training_data)

print(f"Este anomalie: {result.is_anomaly}")
print(f"Explicație: {result.explanation}")
```

## Licență

Proiect educațional pentru lucrare de licență.



