# Tamper-Evident Audit Log with ML Anomaly Detection

A single-node audit-logging system that combines **cryptographic integrity**
(ECDSA-signed transactions chained into Merkle-rooted blocks) with **real-time
anomaly detection** (Isolation Forest + data-driven rule penalties). Built as
a Flask backend (`src/api/app.py`) plus a React/Vite dashboard (`frontend/`).

The goal isn't "build a blockchain"; it's to make security-relevant events
**non-repudiable, append-only, and triaged in real time** for an internal
operations team.

---

## Table of contents

1. [What it solves](#1-what-it-solves)
2. [Capabilities](#2-capabilities)
3. [Threat model](#3-threat-model)
4. [Architecture](#4-architecture)
5. [Repository layout](#5-repository-layout)
6. [Setup & run](#6-setup--run)
7. [Configuration](#7-configuration)
8. [Authentication & RBAC](#8-authentication--rbac)
9. [Transaction lifecycle](#9-transaction-lifecycle)
10. [Blockchain operations](#10-blockchain-operations)
11. [Anomaly detection](#11-anomaly-detection)
12. [Cryptographic components](#12-cryptographic-components)
13. [Persistence](#13-persistence)
14. [API surface](#14-api-surface)
15. [Realtime alerts](#15-realtime-alerts)
16. [Testing](#16-testing)
17. [Operational notes](#17-operational-notes)
18. [Limitations & future work](#18-limitations--future-work)

---

## 1) What it solves

**Problem.** Traditional audit logs sit in mutable databases. A privileged
insider — or an attacker who escalates to the same privilege — can rewrite
them to cover their tracks. Even when logs are intact, humans cannot scan
thousands of entries fast enough to spot subtle misuse.

**Solution.** This system addresses both halves:

1. **Tamper evidence.** Every event is signed (ECDSA, SECP256K1 curve), then
   chained into Merkle-rooted blocks with proof-of-work. Modifying a single
   field anywhere in the history requires re-mining every subsequent block
   *and* forging signatures that don't reuse known public keys — both
   detectable cheaply at audit time.
2. **Automated triage.** An Isolation Forest scores each new event against
   25 behavioural features (temporal, amount, sender history, receiver
   history, risk level). A small **rule layer** with **data-driven weights**
   adds explanatory penalties for known suspicious patterns. Suspicious
   events are surfaced via WebSocket the instant they're submitted.

**Use cases.** Internal audit trails for compliance demos, incident-response
forensics, and detecting unusual user behaviour in environments where the
operator is in the threat model.

---

## 2) Capabilities

- Append-only, hash-chained ledger with proof-of-work mining (configurable
  difficulty).
- ECDSA signatures (SECP256K1), private keys never leave `KeyPair` —
  exposed only via `wallet.sign_transaction(tx)` or an explicit
  persistence-only `export_private_key_hex()` escape hatch.
- Merkle inclusion proofs per transaction (verifiable client-side).
- Hybrid anomaly scoring: Isolation Forest + adaptive threshold + 17
  named penalty predicates whose weights are **learned** from the
  training distribution on every fit, then persisted with the model.
- JWT auth with refresh tokens, scrypt-hashed passwords, role-based
  authorization (`admin`, `operator`, `viewer`).
- Wallet encryption with mandatory Fernet, supporting **key rotation**
  via `WALLET_ENCRYPTION_LEGACY_KEYS`; wallets persisted under a rotated
  key are auto-re-encrypted at next read.
- Snapshot backup/restore for the chain, wallets, SQLite metadata, and
  trained ML model.
- Realtime alerts on a SocketIO `/alerts` namespace (`anomaly_detected`,
  `block_mined`).
- Architectural guardrails enforced as tests
  (`test_architecture_layers.py`).

---

## 3) Threat model

Stating who the system protects against — and who it *doesn't* — is the
single best thing you can do before reading the rest.

| Adversary | What stops them |
|---|---|
| External attacker without auth | Network + JWT auth + filesystem permissions |
| Authenticated user (any role) | RBAC + signed transactions; cannot edit history via the API |
| Malicious operator with API access | Cannot reach `chain.json` or `data/wallets/`; can only submit signed events |
| **Server admin, naive tamper** | Caught at next process start (`JsonBlockchainRepository.load()` recomputes Merkle roots and refuses to start with a broken chain) |
| **Server admin who recomputes hashes consistently** | **Not caught.** They can produce a self-consistent forgery because the data and the integrity hashes live on the same disk under the same permissions. Mitigations belong in "future work": HSM-signed block hashes, anchoring chain roots to a public log, or moving to a multi-node deployment. |
| Server admin who also has `WALLET_ENCRYPTION_KEY` | Full forge capability. Game over. Operate the encryption key out of band. |

The system is **tamper-evident** under the first four rows and explicitly
not tamper-resistant against the last two.

---

## 4) Architecture

The codebase is organized into four layers with **strict, test-enforced
direction of dependency**: domain ← service ← infrastructure (and api as
the delivery boundary).

```
┌──────────────────────────────────────────────────────────────────────┐
│  api/                                                                │
│    routes/ (auth, transactions, wallets, blockchain, anomaly, audit) │
│    bootstrap/ (config, jwt, wiring, seeding, frontend, sockets)      │
│    error_handlers, security (Principal builder), responses           │
└──────────────────────────────┬───────────────────────────────────────┘
                               │  depends on
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  service/                                                            │
│    AuthService, WalletService, TransactionService,                   │
│    BlockchainService, AnomalyService, IntegrityService,              │
│    BackupService, DemoService                                        │
│    (analysis sub-services: Ingestion, Mining, Audit, Training)       │
└────────────────┬───────────────────────────┬─────────────────────────┘
                 │ depends on                │ depends on
                 ▼                           ▼
┌─────────────────────────────────┐ ┌────────────────────────────────┐
│  domain/                        │ │  infrastructure/               │
│    entities/  (Blockchain,      │ │    persistence/                │
│      Block, Transaction,        │ │      sqlite/  (4 focused       │
│      Wallet, AuditReport)       │ │        repositories +          │
│    ml/  (AnomalyDetector,       │ │        connection helper)      │
│      FeatureExtractor)          │ │      json/    (BlockchainRepo, │
│    policies/  (DigitalSignature,│ │        WalletRepo)             │
│      MerkleTree, HashUtils,     │ │      pickle_model_store        │
│      transaction_payload)       │ │    messaging/  (SocketIOEventBus)│
│    authorization, errors,       │ │                                │
│    events, value_objects        │ │  Pure adapter code: no service │
│                                 │ │  or api imports.               │
│  Pure types, no I/O, no Flask.  │ │                                │
└─────────────────────────────────┘ └────────────────────────────────┘
```

### Why this matters

- **Domain is framework-independent.** `Blockchain`, `Wallet`, and
  `AnomalyDetector` know nothing about Flask, SQLite, JSON files, or
  pickle. You can unit-test the domain without standing up a database.
- **Services orchestrate, they don't persist directly.** `AuthService`
  takes a `UserRepository` and a `TokenBlocklistRepository`; it doesn't
  know SQLite exists. Swap the adapter and the service code is
  unchanged.
- **One job per service.** Each service has a narrow, named
  responsibility. Authorization, persistence, and orchestration stay
  separated.

### `Principal` flows end-to-end

The frontend sends a JWT. `src/api/security.py::current_principal()`
builds a `Principal(username, role)` value object from JWT claims. Every
service method that needs authorization takes `principal: Principal` and
calls `principal.require(Role.ADMIN, Role.OPERATOR)`. There is one
shared guard helper, and one place where the JWT becomes a domain
concept.

### Errors are domain-typed, not HTTP-coded

Services raise domain errors (`ValidationError`, `AuthError`,
`ForbiddenError`, `NotFoundError`, `ConflictError`, `InternalError`).
A single Flask error handler in `src/api/error_handlers.py` maps each
class to an HTTP status. Routes contain no `try/except` boilerplate.

### Composition root

`src/api/bootstrap/wiring.py` is the only place where adapters are
constructed and wired into services. `build_services(app, socketio)` is
split into five typed phases (`_resolve_paths`, `_build_adapters`,
`_build_domain`, `_build_analysis`, `_attach_services`) so it stays
under 50 lines per helper.

---

## 5) Repository layout

```
licenta_ml_fixed/
├── main.py                              # Entry point: dev server + port check
├── requirements.txt
├── README.md                            # ← you are here
│
├── src/
│   ├── api/
│   │   ├── app.py                       # Flask app factory (~90 lines)
│   │   ├── app_context.py               # Typed access to attached services
│   │   ├── security.py                  # current_principal() from JWT
│   │   ├── error_handlers.py            # DomainError → api_error mapping
│   │   ├── responses.py                 # api_success / api_error helpers
│   │   ├── rate_limit.py                # In-memory per-route limiter
│   │   ├── extensions.py                # JWT + SocketIO instances
│   │   ├── bootstrap/
│   │   │   ├── config.py                # JWT/wallet keys, CORS parsing
│   │   │   ├── wiring.py                # build_services() composition root
│   │   │   ├── seeding.py               # Admin user + tx index seed
│   │   │   ├── jwt.py                   # JWT lifecycle callbacks
│   │   │   ├── sockets.py               # /alerts namespace handlers
│   │   │   └── frontend.py              # SPA + asset routes
│   │   └── routes/
│   │       ├── auth_routes.py
│   │       ├── transaction_routes.py
│   │       ├── wallet_routes.py
│   │       ├── blockchain_routes.py
│   │       ├── anomaly_routes.py
│   │       └── audit_routes.py
│   │
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── transaction.py           # Transaction, TransactionType, TransactionStatus
│   │   │   ├── block.py                 # Block, GenesisBlock
│   │   │   ├── blockchain.py            # Blockchain (pure: no I/O)
│   │   │   ├── wallet.py                # Wallet (no private_key property), WalletManager
│   │   │   └── audit_report.py
│   │   ├── ml/
│   │   │   ├── anomaly_detector.py      # IsolationForest + learned weights
│   │   │   └── feature_extractor.py     # 25 features, sliding-window state
│   │   ├── policies/
│   │   │   ├── digital_signature.py     # ECDSA + KeyPair.sign(data)
│   │   │   ├── merkle_tree.py
│   │   │   ├── hashing.py
│   │   │   ├── training_data_policy.py  # is_clean_candidate predicate
│   │   │   └── transaction_payload.py   # parse + per-type validation
│   │   ├── authorization.py             # Role enum, Principal, require()
│   │   ├── errors.py                    # DomainError hierarchy
│   │   ├── events.py                    # DomainEvent + EventBus port
│   │   └── value_objects.py             # RiskLevel
│   │
│   ├── service/
│   │   ├── auth_service.py
│   │   ├── transaction_service.py
│   │   ├── wallet_service.py
│   │   ├── blockchain_service.py
│   │   ├── anomaly_service.py           # Train/retrain, alert lifecycle
│   │   ├── integrity_service.py         # check_integrity, export_audit_log
│   │   ├── backup_service.py            # Snapshot CRUD
│   │   ├── demo_service.py              # /api/demo/generate
│   │   ├── analysis_state.py            # Shared in-memory cache for the analysis sub-services
│   │   ├── transaction_audit_service.py
│   │   ├── transaction_ingestion_service.py
│   │   ├── mining_analysis_service.py
│   │   └── detector_training_service.py
│   │
│   ├── infrastructure/
│   │   ├── persistence/
│   │   │   ├── sqlite/
│   │   │   │   ├── connection.py        # Shared SqliteConnection helper
│   │   │   │   ├── schema.py            # CREATE TABLE bootstrap
│   │   │   │   ├── transaction_index_repository.py
│   │   │   │   ├── alert_repository.py
│   │   │   │   ├── user_repository.py
│   │   │   │   └── token_blocklist_repository.py
│   │   │   ├── json/
│   │   │   │   ├── blockchain_repository.py   # Atomic JSON writes for chain + mempool
│   │   │   │   └── wallet_repository.py       # Mandatory Fernet, key-rotation aware
│   │   │   └── pickle_model_store.py
│   │   └── messaging/
│   │       └── socketio_event_bus.py    # SocketIOEventBus adapter
│   │
│   ├── utils/
│   │   ├── data_generator.py            # Demo traffic
│   │   ├── training_data_generator.py   # Synthetic training set
│   │   ├── evaluate_detector.py         # Reproducible detector evaluation (seeded)
│   │   ├── test_factories.py            # TransactionFactory (demo helpers)
│   │   ├── pagination.py
│   │   ├── password_security.py         # scrypt password hashing
│   │   ├── snapshot_manager.py          # ZIP backup/restore
│   │   └── reset_blockchain.py
│   │
│   └── tests/
│       ├── test_api.py                          # 35 integration checks (Flask test client)
│       ├── test_architecture_layers.py          # Layer-direction guardrails
│       ├── test_role_access_control.py          # RBAC behaviour
│       └── test_transaction_audit_statistics.py # Audit stats correctness
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── App.tsx
│       ├── components/                  # Shadcn-style UI primitives
│       ├── features/                    # Pages: dashboard, auth, transactions, wallets, alerts, audit, blockchain
│       ├── services/                    # API clients (axios wrappers)
│       ├── stores/                      # Zustand auth store
│       ├── hooks/
│       ├── types/
│       └── router/
│
└── data/                                # Generated at first run
    ├── blockchain/
    │   ├── chain.json
    │   ├── mempool.json
    │   └── metadata.json
    ├── wallets/
    │   └── *.json                       # Fernet-encrypted private keys
    ├── audit_metadata.db                # SQLite: users, alerts, tx_index, revoked_tokens
    ├── ml_model.pkl                     # Trained IsolationForest + learned weights
    └── backups/
        └── snapshot_*.zip
```

---

## 6) Setup & run

### Prerequisites

- Python 3.10+
- Node.js 18+ (for the frontend)
- Windows, macOS, or Linux

### Backend — first time

**Windows (PowerShell):**

```powershell
cd <project-root>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux:**

```bash
cd <project-root>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend — first time

```bash
cd frontend
npm install
npm run build      # produces frontend/dist/ which the Flask app serves at /
cd ..
```

For active frontend development use `npm run dev` instead — Vite serves the
SPA on `http://localhost:5173/` and proxies `/api/*` to the Flask backend
on `:5000`.

### Run the backend

```bash
python main.py
```

You'll see something like:

```
  Open dashboard: http://127.0.0.1:5000/
  WebSocket: ws://127.0.0.1:5000/alerts
  Default login: admin / admin123 (development only)
```

The dev server auto-creates an `admin` user with password `admin123` on
first start. **Don't ship this to production** — see [Configuration](#7-configuration).

### Reset to a clean state

The whole `data/` directory is regenerated on every startup. To start
fresh:

```bash
rm -rf data/        # macOS / Linux
Remove-Item data -Recurse -Force   # PowerShell
```

This wipes the chain, wallets, users, alerts, and the trained ML model.
Useful for demos.

---

## 7) Configuration

All configuration is environment-variable driven.

| Variable | Default (dev) | Production behaviour | Purpose |
|---|---|---|---|
| `APP_ENV` | `development` | set to `production` | Strict-mode toggle |
| `JWT_SECRET_KEY` | `dev-insecure-change-me-please-set-jwt-secret-key` | **must be set** explicitly, or `RuntimeError` | Signs JWTs |
| `WALLET_ENCRYPTION_KEY` | matches the dev JWT default for back-compat | **must be set** explicitly, or `RuntimeError` | Encrypts wallet private keys at rest |
| `WALLET_ENCRYPTION_LEGACY_KEYS` | (none) | comma-separated list | Read-only fallback keys for migrating wallets after rotation |
| `ADMIN_PASSWORD` | `admin123` | refuses `admin123` in production | Bootstraps the first admin |
| `DATA_DIR` | `data` | any | Base data folder |
| `METADATA_DB` | `data/audit_metadata.db` | any path | SQLite location |
| `ML_MODEL_PATH` | `data/ml_model.pkl` | any path | Trained model location |
| `SNAPSHOT_RETENTION_COUNT` | `20` | any int ≥ 1 | Snapshot cap |
| `CORS_ORIGINS` | `localhost:5000,127.0.0.1:5000,localhost:5173,127.0.0.1:5173` | comma-separated allowlist | API CORS origins |
| `HOST` | `127.0.0.1` | any | Bind host |
| `PORT` | `5000` | any | Bind port |

### Production startup example

```bash
export APP_ENV=production
export JWT_SECRET_KEY="$(openssl rand -hex 32)"
export WALLET_ENCRYPTION_KEY="$(openssl rand -hex 32)"
export ADMIN_PASSWORD="$(openssl rand -base64 24)"
export DATA_DIR=/var/lib/audit
python main.py
```

### Wallet key rotation (no data loss)

Wallets are encrypted with the active `WALLET_ENCRYPTION_KEY`. To rotate:

1. Set the new key as `WALLET_ENCRYPTION_KEY`.
2. Set the previous key as `WALLET_ENCRYPTION_LEGACY_KEYS` (comma-separated
   list if rotating multiple times).
3. Restart. The first time each wallet is read, the loader tries the active
   key, then each legacy key; on success it logs a warning and re-encrypts
   the wallet under the active key. After every wallet has been read once,
   you can drop the legacy entry.

A `key_version` integer is written into each wallet JSON so future
operators can audit which key encrypted what.

---

## 8) Authentication & RBAC

### Login flow

```
POST /api/auth/login   { username, password }
   ↓
   verify_password() against scrypt-hashed value in users table
   ↓
   issue access_token (1 h) + refresh_token (30 days)
   ↓
client sends Authorization: Bearer <access_token> on every API call
```

Tokens carry `{ sub, role, wallet_name, exp, iat, jti }`.
Logout adds the `jti` to a revoked-tokens table; subsequent uses of that
exact token are rejected even before expiry.

### Password hashing — scrypt

`src/utils/password_security.py` uses Python's `hashlib.scrypt` with
N=2¹⁴, r=8, p=1, 64-byte derived key, and a 16-byte random salt.
Stored format:
`scrypt:N:r:p:base64(salt):base64(derived_key)`. Verification is
constant-time via `hmac.compare_digest`.

### Roles

| Role | Capabilities |
|---|---|
| `admin` | Everything: user admin, backups, restore, audit export, training, mining, transaction creation, alert resolution |
| `operator` | Submit transactions, mine blocks, train/retrain detector, resolve alerts |
| `viewer` | Read-only: blockchain, transactions, alerts, statistics |

### Centralized authorization

Routes never read raw role strings. Each route calls
`current_principal()` (which reads the JWT) and passes the resulting
`Principal` to a service. Services call `principal.require(Role.ADMIN, …)`
which raises `ForbiddenError`. The error handler renders a 403 with
`error_code: "FORBIDDEN"`.

### Public viewer signup

`POST /api/auth/register-viewer` is unauthenticated by design — it lets
anyone create a viewer-tier account. It's rate-limited to 20/min per IP.
For a tighter deployment, gate it behind an admin-issued invite token or
remove it entirely.

---

## 9) Transaction lifecycle

### What's a transaction here

Not money — an **auditable event**. Supported types are grouped:

- **Auth:** `LOGIN`, `LOGOUT`, `LOGIN_FAILED`, `ACCESS_GRANTED`, `ACCESS_DENIED`
- **Data:** `DATA_READ`, `DATA_WRITE`, `DATA_MODIFY`, `DATA_DELETE`
- **Admin:** `CONFIG_CHANGE`, `PERMISSION_CHANGE`, `USER_CREATED`, `USER_DELETED`
- **Financial (demo):** `TRANSFER`
- `CUSTOM`

### Status enum

`TransactionStatus`: `PENDING`, `FLAGGED`, `MINED`, `REJECTED`. No magic
strings anywhere in the code — every status transition uses the enum
value.

### Step-by-step

```
   POST /api/transaction
      ↓
1. Schema validation
      domain/policies/transaction_payload.py: parse_transaction_request()
      Per-type checks: TRANSFER requires recipient + amount > 0,
      LOGIN requires ip_address, etc.

2. Authorization
      principal.require(Role.ADMIN, Role.OPERATOR)
      Service looks up user; verifies the requested wallet belongs to
      them (admins can use any wallet).
      The wallet MUST already exist — no auto-create. Caller submits
      to /api/wallet first if needed.

3. Sign
      wallet.sign_transaction(tx)
      Internally: KeyPair.sign(get_signable_data()) - private key never
      leaves KeyPair.

4. Ingest
      TransactionIngestionService.add_transaction(tx)
      verify_signature() → snapshot history → score with detector →
      blockchain.add_transaction(tx) → blockchain_repo.save() (atomic
      JSON write) → cache the AuditReport in AnalysisState

5. Index + alert
      tx_status: REJECTED | PENDING | FLAGGED depending on signature +
      anomaly result. Indexed in SQLite (transaction_index). If
      suspicious, a row is written to alerts and a SocketIO
      'anomaly_detected' event is published on /alerts.

6. Mining (admin/operator-triggered)
      POST /api/mine
      MiningAnalysisService takes everything in the mempool, builds a
      Block, runs proof-of-work, appends to chain, persists, updates
      tx_status to MINED. SocketIO emits 'block_mined'.
```

### Design notes

- **Wallet creation is explicit.** Submitting a transaction with an
  unknown `wallet_name` returns `WALLET_NOT_FOUND`; clients call
  `/api/wallet` first.
- **No quarantine queue.** Suspicious transactions are flagged
  (`tx_status = FLAGGED`) but go to the mempool and get mined
  normally. They remain searchable and minable. Reviewers triage via
  the alerts dashboard, not via approval gates.

---

## 10) Blockchain operations

### Block structure

```
┌─────────────────────────────────────────────────────────┐
│  HEADER                                                  │
│    index, timestamp, previous_hash, merkle_root,         │
│    nonce, difficulty                                     │
│    block_hash = SHA-256(header)                          │
├─────────────────────────────────────────────────────────┤
│  BODY                                                    │
│    transactions (≤ max_transactions_per_block, default 50│
│    in dev wiring; configurable via BlockchainConfig)     │
└─────────────────────────────────────────────────────────┘
```

### Mining (proof-of-work)

```python
target = "0" * difficulty       # default difficulty=3 in dev wiring
while True:
    h = sha256(serialize(header))
    if h.startswith(target):
        return h                # block accepted
    nonce += 1
```

`difficulty=3` is symbolic for a single-node demo — finding a valid hash
takes a few thousand attempts on average. Set higher in production for
stronger rewrite cost.

### Merkle inclusion proofs

Each block stores a Merkle root computed from the SHA-256 of every
transaction. Clients fetching a single transaction via
`GET /api/transaction/<id>` receive a logarithmic-size **proof** they
can verify locally against the block's `merkle_root` without
re-downloading the whole block.

### Validation

`GET /api/blockchain/validate` (and the on-load check in
`JsonBlockchainRepository.load`) verify, in one pass:

1. Each block's stored `block_hash` matches recomputing the header.
2. Each `block_hash` starts with the required difficulty prefix.
3. Each block's `previous_hash` matches the prior block's `block_hash`.
4. Each transaction's signature verifies against its embedded
   public key.
5. The Merkle root recomputed from current transactions matches the
   stored `merkle_root`.

A failure aborts startup with a descriptive `ValueError` ("Persisted
chain failed validation: Invalid integrity for block #N"). The system
refuses to run on a tampered chain rather than silently masking it.

---

## 11) Anomaly detection

### Why a hybrid model

A pure rule engine is easy to evade and miss combinations. A pure
black-box model is hard to explain and hard to defend in audit. The
hybrid layer is small enough to read in one sitting and produces
human-readable explanations for each flagged event.

```
final_score = isolation_forest_score - rule_penalty
flagged = (final_score < adaptive_threshold)
```

### Isolation Forest

- 300 trees, contamination 0.02, deterministic via fixed
  `random_state=42`.
- 25 feature dimensions per transaction, computed by
  `FeatureExtractor`:
  - **Temporal** (cyclical sin/cos for hour and day, weekend, night flags)
  - **Type flags** (auth/data/transfer/admin/failure)
  - **Amount** (raw, log-scaled, high-amount boolean)
  - **Sender behaviour** (counts and sums over last hour/day, rapidity,
    activity_spike_ratio)
  - **Receiver behaviour** (counts and sums)
  - **Risk** (`risk_level_encoded`, `is_failed_attempt`)
- **Adaptive threshold**: at training time the detector picks the
  percentile-N of the training-data score distribution
  (`contamination * 100`, clamped to `[1, 10]`). The effective
  threshold is `max(static, adaptive)` — this prevents a fluke
  training set from pushing the threshold too lax.

### Learned penalty weights

The rule layer has 17 named predicates (`is_night`, `is_weekend`,
`is_failed_attempt`, `amount_above_high`, `activity_spike`,
`receiver_inactive`, …). Each predicate's **weight** — how much it bumps
the penalty — is recomputed every time `fit()` runs:

```python
weight(P) = max(0, median(model_score) - median(model_score | P))
clipped at _MAX_LEARNED_PENALTY = 0.20
```

In words: how far below the population's median IsolationForest score
does the subset where this predicate fires sit. A predicate that doesn't
correlate with anomaly contributes 0 (no penalty). Predicates with fewer
than 5 positive samples in training fall back to safe baseline defaults
to avoid noise on tiny groups.

The learned weights are stored alongside the model (`to_state`,
`from_state`) and exposed via `training_stats["penalty_weights"]` in
the dashboard.

### What "ML-only" looks like

When the human-readable rule list doesn't match anything but the
IsolationForest still scores below threshold, the explanation reads
*"isolated by the ML baseline"*. Those are the cases where the model
caught a multi-feature combination that no single rule could express
— exactly what the model is for.

### Training endpoints

- `POST /api/anomaly/train` (admin/operator)
  - `mode: "synthetic"` — train on 100–5000 synthetic normal events
    generated by `TrainingDataGenerator`. Used when the chain is
    cold-started.
  - `mode: "blockchain"` — train on the chain's actual contents,
    filtered by `TrainingDataPolicy.is_clean_candidate` (drops events
    with `risk_level >= HIGH`, drops `LOGIN_FAILED`/`ACCESS_DENIED`/
    `DATA_DELETE`, drops anything tagged as anomaly).
- `POST /api/anomaly/retrain` (admin/operator) — sliding-window
  retrain over the most recent 2000 non-flagged indexed transactions.

The trained model is pickled to `data/ml_model.pkl` and reloaded on
every server start.

---

## 12) Cryptographic components

### ECDSA (SECP256K1)

Same elliptic curve as Bitcoin. Per-transaction signing:

```
sign:
   message = canonical_json(get_signable_data())
   sig = ECDSA.sign(private_key, SHA-256(message))
verify:
   sig == ECDSA.verify(public_key, SHA-256(message), sig)
```

`get_signable_data()` excludes the `signature` and `public_key` fields
to avoid signing the signature itself.

### Address derivation

`address = SHA-256(public_key)[:40]` — a stable, short identifier for a
wallet. Not reversible.

### Wallet private-key handling

Private keys live exclusively inside `KeyPair`. Two ways to use them:

- `wallet.sign_transaction(tx)` — the normal path. Returns a signed
  transaction without exposing the key.
- `wallet.export_private_key_hex()` — the explicitly-named
  persistence-only escape hatch. Only `JsonWalletRepository.save()`
  calls it, and immediately wraps the bytes in Fernet encryption
  before writing to disk.

`Wallet` deliberately doesn't expose `private_key` as a property, so a
misbehaving logger or a naïve `to_dict()` cannot leak the key.

### Fernet at rest

Wallet JSON files store the private key as
`encrypted_private_key`, with `key_storage: "fernet"` and
`key_version: 1`. The Fernet key is derived from
`SHA-256(WALLET_ENCRYPTION_KEY)` base64-encoded. Encryption is
mandatory: `JsonWalletRepository.__init__` refuses to construct without
an encryption key, and there is no code path that saves a plaintext
private key to disk.

### Hashing

SHA-256 is used for: block hashes, Merkle leaves, address derivation,
canonical-JSON hashing of signable data. `HashUtils.hash_object`
serializes with `sort_keys=True` to make hashes deterministic across
runs.

---

## 13) Persistence

| Data | Adapter | Format | Path |
|---|---|---|---|
| Chain + mempool | `JsonBlockchainRepository` | atomic JSON writes | `data/blockchain/{chain,mempool,metadata}.json` |
| Wallets | `JsonWalletRepository` | per-wallet JSON, Fernet-encrypted private key | `data/wallets/{name}.json` |
| Indexed tx metadata | `TransactionIndexRepository` | SQLite | `data/audit_metadata.db` table `transaction_index` |
| Alerts | `AlertRepository` | SQLite | same DB, table `alerts` |
| Users | `UserRepository` | SQLite | same DB, table `users` |
| Revoked tokens | `TokenBlocklistRepository` | SQLite | same DB, table `revoked_tokens` |
| ML model | `PickleModelStore` | pickle | `data/ml_model.pkl` |
| Snapshots | `snapshot_manager` | ZIP archive | `data/backups/snapshot_*.zip` |

### Atomicity

`JsonBlockchainRepository._atomic_json_write` writes to a tempfile,
`fsync()`s, then `os.replace()` to the target. A crash mid-write leaves
the previous file intact.

### Snapshot scope

A snapshot zips together the blockchain JSON files, the wallets folder,
the SQLite database, and the trained model. Restoring overwrites all
four atomically. Restore returns `restart_required: true` because
in-memory state (loaded chain, loaded model) doesn't auto-refresh —
the operator must restart the process.

---

## 14) API surface

All responses use a standardized envelope:

```jsonc
// success
{ "success": true, "timestamp": "...", "data": { ... }, "pagination": { ... } }
// error
{ "success": false, "error": { "message": "...", "status_code": 400, "code": "VALIDATION_ERROR", "details": [ ... ] } }
```

Pagination params on list endpoints: `?page=1&per_page=20`.

### Auth

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/api/auth/login` | public | rate-limit 20/min |
| POST | `/api/auth/refresh` | refresh-token | |
| POST | `/api/auth/logout` | any | revokes the JWT's `jti` |
| POST | `/api/auth/register` | admin | rate-limit 30/min |
| POST | `/api/auth/register-viewer` | public | rate-limit 20/min |

### Blockchain

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/health` | public | height, mempool size, alerts unresolved |
| GET | `/api/blockchain` | viewer+ | paginated blocks |
| GET | `/api/blockchain/stats` | viewer+ | |
| GET | `/api/blockchain/validate` | viewer+ | re-runs full chain validation |
| GET | `/api/block/<index>` | viewer+ | |
| POST | `/api/mine` | admin/operator | rate-limit 20/min, emits `block_mined` |
| GET | `/api/mempool` | viewer+ | paginated |

### Transactions

| Method | Path | Role | Filters |
|---|---|---|---|
| GET | `/api/transactions` | viewer+ | `transaction_id`, `type`, `sender`, `status`, `flagged` |
| GET | `/api/transaction/<id>` | viewer+ | returns Merkle proof + index record |
| POST | `/api/transaction` | admin/operator | rate-limit 120/min, emits `anomaly_detected` if flagged |
| GET | `/api/transaction/analyze/<id>` | viewer+ | live re-score with current model |

### Wallets

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/wallets` | viewer+ | viewer sees only their own wallet |
| POST | `/api/wallet` | any auth | admin can `assign_to_user` to bind to someone else |
| GET | `/api/wallet/<name>` | viewer+ | viewer must own it |

### Anomaly

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/api/anomaly/train` | admin/operator | rate-limit 10/min |
| POST | `/api/anomaly/retrain` | admin/operator | rate-limit 5/min, sliding-window |
| GET | `/api/anomaly/stats` | viewer+ | model + analysis statistics |
| GET | `/api/alerts` | viewer+ | filters: `severity`, `resolved` |
| PUT | `/api/alerts/<id>/resolve` | admin/operator | |
| POST | `/api/demo/generate` | admin/operator | seeds a configurable mix of normal + anomalous events |

### Audit

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/audit/integrity` | viewer+ | re-runs in-memory chain validation |
| GET | `/api/audit/export` | admin | downloadable JSON dump of chain + alerts (cached values, see `IntegrityService.export_audit_log`) |
| GET | `/api/audit/backups` | admin | |
| POST | `/api/audit/backup` | admin | rate-limit 5/min |
| POST | `/api/audit/restore` | admin | rate-limit 3/min, requires restart to reload in-memory state |
| GET | `/api/audit/backups/<name>/download` | admin | streams the snapshot zip |

---

## 15) Realtime alerts

Namespace: `/alerts`. JWT auth is enforced on connect.

```javascript
import { io } from "socket.io-client";

const socket = io("http://127.0.0.1:5000/alerts", {
  auth: { token: accessToken },
});

socket.on("connected", ({ message, timestamp }) => { /* ... */ });
socket.on("anomaly_detected", ({ alert_id, transaction_id, status, score, explanation, timestamp }) => { /* ... */ });
socket.on("block_mined", ({ block_index, transaction_count, anomalies_found, timestamp }) => { /* ... */ });
```

The frontend dashboard subscribes to this namespace and updates the
alerts panel without refresh. Filtering by `severity` is currently
client-side only.

---

## 16) Testing

### Unit and architecture tests (pytest)

```bash
python -m pytest src/tests -q
```

Covers:

- **Layer guardrails** — `domain/` cannot import `service/`, `infrastructure/`,
  or `api/`; `service/` cannot import `api/`; `infrastructure/` cannot
  import `service/` or `api/`; `api/routes/` cannot reach into
  `infrastructure/` directly. These are regex import-scan checks, not
  behaviour tests, but they're cheap and have caught real regressions.
- **RBAC** — viewer cannot create transactions, sees only owned wallets;
  admin/operator can.
- **Audit statistics** — full reports drive the stats, not only alerts;
  rehydration after restart works against a stub blockchain.

### Integration smoke

```bash
rm -rf data/        # or Remove-Item data -Recurse -Force
python -m src.tests.test_api
```

35 sequential checks: auth flow, RBAC, pagination, transaction creation,
filter wiring, transfer-validation defaults, mining, snapshot
backup/list/restore/download, retention pruning, refresh, logout,
revocation. Exit 0 = all pass.

### Reproducible detector evaluation

```bash
python -m src.utils.evaluate_detector
```

Trains the detector on seeded synthetic traffic, scores a held-out mix of
200 normal and 50 anomalous events, and prints the confusion matrix plus
precision, recall and F1. Seeded end-to-end, so the numbers reproduce
exactly on every run.

---

## 17) Operational notes

- **First start indexes the existing chain.** If `data/blockchain/`
  exists from a previous run, the server reads it, validates it
  (refusing to start on tamper), then idempotently re-indexes any
  transactions missing from `transaction_index`.
- **Snapshot restore needs a restart.** The restore endpoint replaces
  files on disk but in-memory state doesn't auto-reload. The response
  carries `restart_required: true` to make this explicit.
- **Port already in use.** `main.py` checks for a free `HOST:PORT`
  before starting and exits with a clear message instead of a less-clear
  Werkzeug stack trace.
- **Rate limits are in-memory.** They survive across requests within
  one process, not across restarts. For multi-process deployments swap
  the limiter for a Redis-backed one.
- **Logging.** All backend logs go to stdout under the
  `blockchain_audit` logger. There's no file rotation built in.

---

## 18) Limitations & future work

Known limitations, stated explicitly:

- **Single-node ledger.** Not P2P, no consensus, no fork resolution. Threat
  model is "internal operator", not "public adversary". Mitigation: HSM-
  signed block hashes, anchoring chain roots to a public log, or a real
  consensus layer.
- **JSON persistence is O(N) per write.** Every transaction rewrites the
  full `chain.json`. Fine up to ~10k transactions; would need block-file
  splits or a real DB to scale further.
- **ML evaluation is reflexive on synthetic data.** The demo anomalies
  are generated by patterns the rule layer was designed to catch; the
  IsolationForest also catches them, but the evaluation isn't an
  unbiased measurement of model quality. A real-world labelled dataset
  is needed to characterize precision/recall properly.
- **No unit-of-work across stores.** A failure between the JSON
  blockchain save and the SQLite index update can leave the two
  inconsistent. Compensation is manual (re-running `seed_metadata_index`
  after restart re-derives the index from the chain). Real fix: a
  transactional outbox.
- **`feature_extractor.py` is large** (~600 lines). Could be split into
  `transaction_features.py`, `feature_extractor.py`,
  `behavior_window.py`. Out of scope for the current iteration.
- **No drift detection.** The model is retrained manually. A KS-test on
  the score distribution against the training distribution would be a
  cheap "the world has changed" alarm.
- **Per-user baselines aren't modelled.** A high-velocity service
  account is judged against the same population baseline as a sleepy
  human admin. A hierarchical model (one detector per user, or
  per-role) would catch *individual* deviation, which is closer to
  what real audit teams want.
