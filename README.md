# Secure Blockchain Audit System with ML Anomaly Detection

A production-minded audit platform that combines:
- an immutable blockchain ledger for event integrity,
- cryptographic signing for non-repudiation,
- and machine learning anomaly detection for risk scoring in real time.

It is implemented as a Flask app factory backend (`src/api/app.py`) plus a React/Vite frontend (`frontend/`).

## Table of Contents

- [1) What This Project Solves](#1-what-this-project-solves)
- [2) Core Capabilities](#2-core-capabilities)
- [3) Architecture Overview](#3-architecture-overview)
- [4) Repository Layout](#4-repository-layout)
- [5) End-to-End Transaction Lifecycle](#5-end-to-end-transaction-lifecycle)
- [6) Data Persistence Boundaries](#6-data-persistence-boundaries)
- [7) Security Model](#7-security-model)
- [8) Machine Learning Pipeline](#8-machine-learning-pipeline)
- [9) API Surface](#9-api-surface)
- [10) Realtime Alerts (Socket.IO)](#10-realtime-alerts-socketio)
- [11) Setup and Run](#11-setup-and-run)
- [12) Configuration](#12-configuration)
- [13) Testing](#13-testing)
- [14) Operational Notes](#14-operational-notes)
- [15) Known Drift / Scope Notes](#15-known-drift--scope-notes)

## 1) What This Project Solves

Traditional audit logs in mutable storage can be altered or deleted by privileged actors.
This system hardens auditability and improves incident response by:

1. Writing events into a chain of cryptographically linked blocks.
2. Requiring digital signatures on transactions.
3. Running an anomaly detector to flag suspicious behavior.
4. Persisting searchable metadata and alerts in SQLite for fast querying.

This gives both immutability (for compliance/integrity) and operational visibility (for SOC workflows).

## 2) Core Capabilities

- Immutable blockchain ledger with Proof-of-Work mining.
- ECDSA-signed transactions (SECP256K1) and signature verification.
- Merkle-root-based block integrity.
- Isolation Forest anomaly scoring with feature extraction from event context.
- Alert generation and resolution workflow stored in SQLite.
- JWT authentication with role-based authorization (`admin`, `operator`, `viewer`).
- In-memory route-level rate limits on sensitive actions.
- Snapshot backup/restore for blockchain, wallets, metadata DB, and ML model.
- Realtime alert/mine events via Socket.IO (`/alerts` namespace).
- React frontend dashboard with blockchain, transactions, alerts, and operations views.

## 3) Architecture Overview

### Runtime Composition (Flask App Factory)

`create_app()` in `src/api/app.py` initializes and wires:
- `Blockchain`
- `WalletManager`
- `TransactionAnalyzer`
- `MetadataStore`
- Service layer (`AuthService`, `TransactionService`, `WalletService`, `BlockchainService`, `AnomalyService`, `AuditService`)
- Flask extensions (`JWT`, `Socket.IO`, `CORS`)

Runtime services are attached to the Flask app and accessed through typed helper `get_app_ctx()` in `src/api/app_context.py`.

### Layered Design

The project uses a layered structure validated by `test_architecture_layers.py`:
- `src/domain`: entities + core ML/domain logic.
- `src/service`: business use-cases and authorization rules.
- `src/infrastructure`: persistence adapter(s), mainly SQLite metadata store.
- `src/repository`: state repository (`analysis_state_repository.py`).
- `src/api`: web layer (routes, app factory, responses, rate-limit).

### Single-Node Design

This is a **monolithic (single-node) blockchain implementation**, not a distributed consensus system.
The blockchain exists as an in-process object attached to a single Flask instance.
All transactions, mining, and state are managed locally—there is no peer-to-peer synchronization, gossip protocol, or distributed consensus (e.g., no Proof-of-Stake or multi-node mining).

This simplification makes the system suitable for:
- Proof-of-concept audit logging.
- Compliance demos and educational purposes.
- Single-organization audit trails where immutability is enforced by access control and cryptographic proofs, not network redundancy.

For production deployment across multiple nodes, you would need to add:
- P2P networking for block/transaction propagation.
- Consensus mechanism (Byzantine Fault Tolerance, PoS, etc.).
- State synchronization and fork resolution.

## 4) Repository Layout

```text
licenta_ml_fixed/
├── main.py
├── requirements.txt
├── test_api.py
├── test_architecture_layers.py
├── test_role_access_control.py
├── test_transaction_audit_statistics.py
├── src/
│   ├── api/
│   │   ├── app.py
│   │   ├── app_context.py
│   │   ├── responses.py
│   │   ├── rate_limit.py
│   │   └── routes/
│   ├── domain/
│   │   ├── entities/
│   │   └── ml/
│   ├── service/
│   ├── infrastructure/
│   └── repository/
├── frontend/
│   ├── package.json
│   └── src/
└── data/
    ├── blockchain/
    ├── wallets/
    ├── backups/
    ├── audit_metadata.db
    └── ml_model.pkl
```

## 5) End-to-End Transaction Lifecycle

1. Client calls `POST /api/transaction`.
2. Request is authenticated with JWT; service-level RBAC is enforced.
3. Wallet is resolved/created and transaction is signed.
4. `TransactionAnalyzer.add_transaction()` verifies signature and scores anomaly (if model fitted).
5. If signature is invalid: transaction is rejected and indexed as `REJECTED`.
6. If valid: transaction goes to mempool and is indexed as:
   - `PENDING` (normal), or
   - `FLAGGED` (suspicious but still accepted in mempool).
7. `POST /api/mine` mines mempool to a block and indexed status becomes `MINED` (flag state retained).

Important: this codebase does not use a quarantine queue in current behavior.

## 6) Data Persistence Boundaries

| Concern | Path / Storage | Source |
|---|---|---|
| Blockchain chain/mempool/meta | `data/blockchain/{chain.json,mempool.json,metadata.json}` | `src/domain/entities/blockchain.py` |
| Wallet key files | `data/wallets/*.json` | `src/domain/entities/wallet.py` |
| Metadata, users, alerts, token revocation | `data/audit_metadata.db` (SQLite) | `src/infrastructure/metadata_store.py` |
| Trained ML model | `data/ml_model.pkl` (default) | `src/api/app.py`, `src/api/routes/anomaly_routes.py` |
| Snapshots | `data/backups/*.zip` | `src/service/audit_service.py`, `src/utils/snapshot_manager.py` |

### SQLite Tables (high level)

- `transaction_index`: indexed tx metadata (`tx_status`, `is_flagged`, `ml_score`, `ml_reason`, ...)
- `alerts`: anomaly alerts and resolution fields
- `users`: credentials metadata + role + wallet assignment
- `revoked_tokens`: JWT denylist (`jti`)

## 7) Security Model

### Authentication and Tokens

- Access and refresh JWTs are issued by `POST /api/auth/login`.
- Default access expiry: 1 hour.
- Default refresh expiry: 30 days.
- Logout revokes current token (`revoked_tokens` table).

### Roles

- `admin`: full access (user admin, backups/restore/export, training, mining, etc.)
- `operator`: operational actions (submit tx, mine, train/retrain detector, resolve alerts)
- `viewer`: read-focused access

Note: although many routes require JWT, service methods still enforce final role checks (defense in depth).

### Cryptographic Integrity

- SHA-256 for hashing.
- ECDSA signatures for transaction authenticity.
- Merkle roots inside block headers.
- Chain validation endpoint (`GET /api/blockchain/validate`) checks linkage and integrity.

### Rate Limiting

In-memory limiter (`src/api/rate_limit.py`) protects sensitive routes like login, registration, training, mining, backup/restore, and tx creation.

## 8) Machine Learning Pipeline

### Detector

- Unsupervised anomaly detection using Isolation Forest.
- Model persisted to disk (`ml_model.pkl`) and loaded at startup if present.

### Training Modes

`POST /api/anomaly/train` supports:
- `mode=blockchain`: uses clean historical transactions from chain.
- `mode=synthetic`: generates normal synthetic samples.

`POST /api/anomaly/retrain` retrains on recent non-flagged indexed transactions (sliding-window behavior).

### Feature Extraction

Feature extraction in `src/domain/ml/feature_extractor.py` includes:
- cyclical temporal encodings (`hour_sin`, `hour_cos`, `day_sin`, `day_cos`),
- transaction group flags (auth/data/transfer/admin/failure),
- amount and log-scaled amount,
- sender/receiver rolling-hour/day activity and sums,
- activity spike ratio with cold-start smoothing,
- time since last sender transaction,
- risk-level encoding and failure flags.

This yields a stable numeric vector used by the detector.

## 9) API Surface

All API responses use standardized wrappers from `src/api/responses.py`:
- success shape: `success`, `timestamp`, optional `data`, optional `pagination`
- error shape: `success=false`, `error.message`, `error.code`, `error.status_code`, optional `details`

### Health + Blockchain

- `GET /api/health` (public)
- `GET /api/blockchain`
- `GET /api/blockchain/stats`
- `GET /api/blockchain/validate`
- `GET /api/block/<index>`
- `POST /api/mine`
- `GET /api/mempool`

### Auth

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `POST /api/auth/register` (admin)
- `POST /api/auth/register-viewer` (public self-registration)

### Transactions + Wallets

- `GET /api/transactions`
- `GET /api/transaction/<transaction_id>`
- `POST /api/transaction`
- `GET /api/transaction/analyze/<transaction_id>`
- `GET /api/wallets`
- `POST /api/wallet`
- `GET /api/wallet/<name>`

### Anomaly + Alerts

- `POST /api/anomaly/train`
- `POST /api/anomaly/retrain`
- `GET /api/anomaly/stats`
- `GET /api/alerts`
- `PUT /api/alerts/<alert_id>/resolve`
- `POST /api/demo/generate`

### Audit + Backups

- `GET /api/audit/integrity`
- `GET /api/audit/export` (admin)
- `GET /api/audit/backups` (admin)
- `POST /api/audit/backup` (admin)
- `POST /api/audit/restore` (admin)
- `GET /api/audit/backups/<snapshot_name>/download` (admin)

## 10) Realtime Alerts (Socket.IO)

Namespace: `/alerts`

Server-side events include:
- `connected` (on successful authenticated socket connect)
- `anomaly_detected` (emitted when suspicious tx is created)
- `block_mined` (emitted after successful mining)
- `subscribed` (after `subscribe_alerts` event)

Connection requires a valid JWT token via:
- socket auth payload (`{ token: ... }`), or
- `Authorization: Bearer ...` header, or
- query param token fallback.

## 11) Setup and Run

### Prerequisites

- Python 3.9+
- Node.js 18+
- npm

### Backend Install (Windows PowerShell)

```powershell
cd C:\Users\tudor\PycharmProjects\licenta_ml_fixed
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Frontend Install

```powershell
cd C:\Users\tudor\PycharmProjects\licenta_ml_fixed\frontend
npm install
```

### Run Backend

```powershell
cd C:\Users\tudor\PycharmProjects\licenta_ml_fixed
python main.py
```

Backend serves API and dashboard entry route at `http://127.0.0.1:5000/`.

### Run Frontend Dev Server

```powershell
cd C:\Users\tudor\PycharmProjects\licenta_ml_fixed\frontend
npm run dev
```

If frontend is run separately, use the local Vite URL shown in terminal (typically `http://127.0.0.1:5173/`).

### Default Development Credentials

- Username: `admin`
- Password: `admin123`

This default is for development only. In production, set `ADMIN_PASSWORD` and `JWT_SECRET_KEY` explicitly.

## 12) Configuration

Environment variables used by the app:

| Variable | Purpose | Default / Note |
|---|---|---|
| `APP_ENV` | Environment mode | `development`; `production` enforces stronger startup checks |
| `JWT_SECRET_KEY` | JWT signing key | required in production |
| `ADMIN_PASSWORD` | bootstrap admin password | `admin123` only in dev |
| `DATA_DIR` | base data folder | `data` |
| `METADATA_DB` | SQLite file path | `data/audit_metadata.db` |
| `ML_MODEL_PATH` | model pickle path | `data/ml_model.pkl` |
| `SNAPSHOT_RETENTION_COUNT` | backup retention cap | `20` (or override in tests/config) |
| `CORS_ORIGINS` | comma-separated CORS allowlist | includes localhost backend/frontend |
| `HOST` | backend bind host | `127.0.0.1` |
| `PORT` | backend bind port | `5000` |
| `DEBUG` | Flask debug toggle | `True` by env string |
| `WALLET_ENCRYPTION_KEY` | wallet private key encryption key | defaults to JWT secret if unset |

### Minimal Production Example (PowerShell)

```powershell
$env:APP_ENV = "production"
$env:JWT_SECRET_KEY = "replace-with-long-random-secret"
$env:ADMIN_PASSWORD = "replace-with-strong-admin-password"
$env:HOST = "0.0.0.0"
$env:PORT = "5000"
python main.py
```

## 13) Testing

### Main Regression / API Smoke

```powershell
cd C:\Users\tudor\PycharmProjects\licenta_ml_fixed
python test_api.py
```

This script covers:
- auth + token flows,
- RBAC behavior,
- pagination contracts,
- transaction validation,
- detector training + stats,
- mining and status transitions (`FLAGGED` -> `MINED`),
- backup/list/download/restore validation,
- endpoint rate limiting.

### Additional Test Modules

- `test_architecture_layers.py`: dependency guardrails across layers.
- `test_role_access_control.py`: role/permission behavior.
- `test_transaction_audit_statistics.py`: transaction and audit statistics checks.

## 14) Operational Notes

- The test suite mutates local `data/` state; use disposable data for repeated testing.
- Snapshot restore endpoint returns a `restart_required` signal; restart app after restore to reload in-memory state.
- `main.py` refuses startup if requested host:port is already occupied.
- On startup, existing blockchain transactions are re-indexed in SQLite for consistent query performance.

## 15) Known Drift / Scope Notes

- `WORKFLOW.md` contains historical documentation that references a quarantine subsystem.
- Current implementation behavior is route/service code + tests in this repository.
- In current flow, suspicious but signature-valid transactions are marked `FLAGGED` and can still be mined.

---