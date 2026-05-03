# Secure Blockchain Audit System with ML Anomaly Detection

A production-minded audit platform that combines:
- an immutable single-node blockchain ledger for cryptographic event integrity,
- ECDSA-signed transactions for non-repudiation,
- and real-time machine learning (Isolation Forest) anomaly detection for risk scoring.

It is implemented as a Flask app factory backend (`src/api/app.py`) plus a React/Vite frontend (`frontend/`).

**Table of Contents**
- [1) What This Project Solves](#1-what-this-project-solves)
- [2) Core Capabilities](#2-core-capabilities)
- [3) System Architecture](#3-system-architecture)
- [4) Single-Node Design](#4-single-node-design)
- [5) Repository Layout](#5-repository-layout)
- [6) Understanding JWT Authentication](#6-understanding-jwt-authentication)
- [7) Complete Transaction Lifecycle](#7-complete-transaction-lifecycle)
- [8) Blockchain Operations](#8-blockchain-operations)
- [9) Anomaly Detection Deep Dive](#9-anomaly-detection-deep-dive)
- [10) Cryptographic Components](#10-cryptographic-components)
- [11) Data Persistence & Stores](#11-data-persistence--stores)
- [12) API Surface (Full Reference)](#12-api-surface-full-reference)
- [13) Realtime Alerts (Socket.IO)](#13-realtime-alerts-socketio)
- [14) Setup & Run](#14-setup--run)
- [15) Configuration](#15-configuration)
- [16) Testing](#16-testing)
- [17) Dashboard & UI](#17-dashboard--ui)
- [18) Operational Notes & Troubleshooting](#18-operational-notes--troubleshooting)
- [19) Known Limitations & Scope](#19-known-limitations--scope)

---

## 1) What This Project Solves

### The Problem

Traditional audit logs stored in mutable databases can be:
- **Modified**: Privileged attackers can rewrite history.
- **Deleted**: Logs can be wiped to cover tracks.
- **Corrupted**: Accidental or malicious data loss.
- **Not scalable for review**: Humans cannot analyze thousands of transactions in real-time.

### The Solution

This system hardens auditability by:

1. **Cryptographic Immutability**: Events are stored in a chain of cryptographically linked blocks. Once written, modification requires breaking all subsequent blocks—computationally infeasible.
2. **Non-Repudiation**: Every transaction is signed using ECDSA (same curve as Bitcoin). Signers cannot deny authorship.
3. **Automated Anomaly Detection**: An Isolation Forest ML model analyzes transactional context in real-time, automatically flagging suspicious patterns without human lag.
4. **Searchable Metadata**: SQLite index ensures fast queries without scanning the entire chain every time.

### Real-World Uses

- **Compliance & Regulatory**: Immutable audit trail for PCI-DSS, SOX, HIPAA.
- **Incident Response**: Rich context (anomaly scores, feature explanations) helps security teams investigate faster.
- **Internal Fraud Prevention**: Detect unusual user behavior (time, amount, pattern deviations).

---

## 2) Core Capabilities

- **Immutable blockchain ledger** with single-node Proof-of-Work mining (difficulty configurable).
- **ECDSA-signed transactions** (SECP256K1 curve); signature verification enforced.
- **Merkle-root-based block integrity** for efficient transaction inclusion proofs.
- **Isolation Forest anomaly scoring** with 25+ context-aware features (temporal, behavioral, risk).
- **Alert generation and resolution workflow** persisted in SQLite for durability.
- **JWT authentication** with role-based authorization (`admin`, `operator`, `viewer`).
- **In-memory route-level rate limits** protecting sensitive operations.
- **Snapshot backup/restore** for blockchain, wallets, metadata DB, and ML model.
- **Realtime alert/mine events** via Socket.IO namespace `/alerts`.
- **React/Vite frontend dashboard** for real-time blockchain, transaction, alert, and ops views.

---

## 3) System Architecture

### Layered Design

The codebase follows clean layering validated by `test_architecture_layers.py`:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                            │
│         Dashboard (React/Vite) + REST API + WebSocket           │
│                                                                  │
│  User interaction. Dashboard provides visual interface.          │
│  REST API allows programmatic access. WebSocket enables          │
│  real-time push notifications without polling.                   │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BUSINESS LOGIC LAYER                         │
│      Transaction Analyzer + Mining + Alert Resolution            │
│                                                                  │
│  Core decision rules. Decides if transactions are suspicious.    │
│  Routes the analysis (mempool vs. index), manages mining.        │
│  No direct persistence concerns.                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DOMAIN LAYER                                  │
│      Blockchain, Wallets, Features, Anomaly Detector             │
│                                                                  │
│  Pure domain entities (Block, Transaction, Wallet).              │
│  ML feature extraction and detector.                              │
│  No external dependency imports.                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   INFRASTRUCTURE LAYER                            │
│        SQLite MetadataStore + Blockchain JSON Files              │
│                                                                  │
│  Adapters for persistence. JSON serialization for blockchain.    │
│  SQLite queries for metadata (users, alerts, indexes).           │
└─────────────────────────────────────────────────────────────────┘
```

### Key Services (Flask App Factory Initialization)

`create_app()` in `src/api/app.py` wires:
- **Blockchain**: In-process chain + mempool, PoW mining, JSON persistence.
- **WalletManager**: Cryptographic key storage (wallets/ JSON files, optionally encrypted).
- **TransactionAnalyzer**: Signature verification + ML scoring + blockchain submission.
- **MetadataStore**: SQLite for users, alerts, transaction index, token revocation.
- **AnomalyService**: Model training, alert lifecycle, demo data generation.
- **TransactionService**: Transaction creation, RBAC enforcement, wallet resolution.
- **BlockchainService**: Chain queries, mining orchestration, mempool views.
- **AuditService**: Integrity checks, backups/restore, exports.
- **AuthService**: User registration, password hashing (salted SHA256), token lifecycle.
- **WalletService**: Wallet CRUD with ownership rules.
- **Flask Extensions**: JWT (with token blacklist), Socket.IO, CORS.

All services are accessed via the typed helper `get_app_ctx()` in `src/api/app_context.py`.

---

## 4) Single-Node Design

This is a **monolithic (single-node) blockchain implementation**, not a distributed system.

### What This Means

- **All state is in-process** within a single Flask instance.
- **No peer-to-peer networking**, no block/transaction gossip protocol.
- **No distributed consensus** (no Byzantine Fault Tolerance, PoS, or multi-node mining).
- Blocks are mined sequentially by a single administrator.
- Immutability is enforced by **cryptography + access control**, not by network redundancy.

### When This Is Appropriate

✓ Proof-of-concept audit systems for compliance demos.  
✓ Educational blockchain implementations.  
✓ Single-organization audit trails where access is controlled and cryptographic proofs are sufficient.  
✗ Not suitable for public/trustless multi-party scenarios.

### Migration Path for Multi-Node

To extend to distributed deployment:
- Add P2P networking layer (e.g., libp2p, custom gossip).
- Implement consensus mechanism (PoS, BFT, etc.).
- Handle block fork resolution and state synchronization.

---

## 5) Repository Layout

```text
licenta_ml_fixed/
├── main.py                             # Entry point (Flask server startup)
├── requirements.txt                    # Python dependencies
├── test_api.py                         # Main regression/smoke tests
├── test_architecture_layers.py         # Layer dependency guardrails
├── test_role_access_control.py         # RBAC behavior tests
├── test_transaction_audit_statistics.py # Audit stats validation
├── AGENTS.md                           # Developer context (architectural notes)
├── WORKFLOW.md                         # (Legacy; see README for current)
├── README.md                           # This file
│
├── src/
│   ├── api/
│   │   ├── app.py                   # Flask app factory + extension setup
│   │   ├── app_context.py           # Typed runtime context helper
│   │   ├── responses.py             # Standardized API response format
│   │   ├── rate_limit.py            # In-memory per-route rate limiter
│   │   ├── database.py              # SQLite MetadataStore
│   │   ├── extensions.py            # Flask-JWT, Flask-SocketIO
│   │   └── routes/
│   │       ├── auth_routes.py       # Login, refresh, logout, register
│   │       ├── blockchain_routes.py # Chain views, mining, health
│   │       ├── transaction_routes.py # Transaction creation/analysis
│   │       ├── wallet_routes.py     # Wallet CRUD, details
│   │       ├── anomaly_routes.py    # ML training, alert lifecycle
│   │       ├── audit_routes.py      # Integrity, export, backups
│   │       └── __init__.py
│   │
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── blockchain.py        # Blockchain, Block, BlockchainConfig
│   │   │   ├── transaction.py       # Transaction, TransactionType enum
│   │   │   └── wallet.py            # Wallet, WalletManager
│   │   └── ml/
│   │       ├── anomaly_detector.py  # Isolation Forest wrapper
│   │       └── feature_extractor.py # Transaction → feature vectors
│   │
│   ├── service/
│   │   ├── auth_service.py          # Auth use-cases + password hashing
│   │   ├── transaction_service.py   # Transaction lifecycle
│   │   ├── wallet_service.py        # Wallet ownership rules
│   │   ├── blockchain_service.py    # Mining + chain queries
│   │   ├── anomaly_service.py       # ML training + alert lifecycle
│   │   ├── audit_service.py         # Audits + backups
│   │   ├── transaction_analyzer.py  # Signature verification + analysis
│   │   ├── exceptions.py            # ServiceError
│   │   └── __init__.py
│   │
│   ├── infrastructure/
│   │   ├── metadata_store.py        # SQLite adapter (users, alerts, index)
│   │   └── __init__.py
│   │
│   ├── repository/
│   │   ├── analysis_state_repository.py # Stateful analysis tracking
│   │   └── __init__.py
│   │
│   └── utils/
│       ├── data_generator.py         # Test data: normal + anomaly txs
│       ├── training_data_generator.py # Synthetic txs for ML training
│       ├── pagination.py             # Pagination helpers
│       ├── password_security.py      # Salted password hashing
│       ├── snapshot_manager.py       # Backup/restore zips
│       └── reset_blockchain.py       # Dev utility: clear state
│
├── frontend/
│   ├── package.json                  # Node dependencies
│   ├── vite.config.ts                # Vite build config
│   ├── index.html                    # Entry HTML
│   ├── src/
│   │   ├── App.tsx                   # Main React component
│   │   ├── main.tsx                  # ReactDOM mount
│   │   ├── components/               # Reusable UI components
│   │   ├── features/                 # Feature modules (auth, dashboard, etc)
│   │   ├── services/                 # API client wrappers
│   │   ├── stores/                   # Zustand state (if used)
│   │   ├── hooks/                    # Custom React hooks
│   │   ├── types/                    # TypeScript domain types
│   │   └── router/                   # React Router setup
│   └── dist/                         # Built static assets (post-build)
│
└── data/
    ├── blockchain/
    │   ├── chain.json                # Serialized blockchain
    │   ├── mempool.json              # Pending transactions
    │   └── metadata.json             # Blockchain metadata
    ├── wallets/
    │   ├── admin.json                # Admin wallet (private key if set)
    │   ├── bob.json
    │   └── *.json                    # Per-user wallets
    ├── training_wallets/             # Demo training profiles
    ├── backups/
    │   └── snapshot_*.zip            # Timestamped snapshots
    ├── audit_metadata.db             # SQLite: users, alerts, indexes
    └── ml_model.pkl                  # Trained Isolation Forest
```

---

## 6) Understanding JWT Authentication

### How JWT Flow Works

**Step 1: User logs in**
```
POST /api/auth/login
{
  "username": "admin",
  "password": "admin123"
}
```

Server verifies password against salted hash in `users` table.

**Step 2: Server issues tokens**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGc...",
    "refresh_token": "eyJhbGc...",
    "user": { "username": "admin", "role": "admin", "wallet_name": "admin" }
  }
}
```

- **Access token**: Short-lived (1 hour). Includes `sub` (username), `role`, `wallet_name`, `exp`, `iat`, `jti` (unique ID).
- **Refresh token**: Long-lived (30 days). Used only to obtain new access token.

**Step 3: Client uses access token**

For every API request:
```
Authorization: Bearer eyJhbGc...
GET /api/blockchain
```

Server validates token signature without DB lookup.

**Step 4: Token refresh**

When access token expires:
```
POST /api/auth/refresh
Authorization: Bearer eyJhbGc... (refresh token)
```

Returns new access token.

### JWT Payload (Claims)

```json
{
  "sub": "admin",           // Subject: who token belongs to
  "role": "admin",          // Authorization role
  "wallet_name": "admin",   // Associated wallet
  "exp": 1709750400,        // Expiration (Unix timestamp)
  "iat": 1709746800,        // Issued at
  "jti": "abc123def..."     // Unique ID (for revocation/blacklist)
}
```

### Role-Based Access Control (RBAC)

| Role | Capabilities |
|------|---|
| **admin** | User admin, backups/restore/export, training, mining, transaction creation. Full system access. |
| **operator** | Submit transactions, mine blocks, train/retrain ML detector, resolve alerts. Most operational actions. |
| **viewer** | Read-only: view blockchain, transactions, alerts, statistics. Cannot modify state. |

### Password Security

Passwords are **never stored in plain text**. Instead:

```python
# User registration:
salt = generate_random_string(32)
hash = SHA256(salt + password)
stored = f"{salt}:{hash}"

# User login:
stored_salt, stored_hash = stored.split(":")
computed_hash = SHA256(stored_salt + entered_password)
if computed_hash == stored_hash:
    # Password matches
```

The salt prevents attackers from using precomputed rainbow tables.

---

## 7) Complete Transaction Lifecycle

### What is a Transaction?

In this audit system, a transaction represents any auditable event:
- User login from IP address.
- Data access (read/write/modify/delete).
- Financial transfer.
- Config/permission changes.
- User account creation/deletion.

Unlike cryptocurrency, transactions don't move money—they record *who did what, when, from where*.

### Transaction Data Structure

```json
{
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "transaction_type": "TRANSFER",
  "sender_address": "a1b2c3d4e5f6789012345678901234567890",
  "timestamp": "2026-03-06T14:30:00.000000Z",
  "data": {
    "recipient": "9876543210fedcba9876543210fedcba12345678",
    "amount": 1500.00,
    "currency": "RON"
  },
  "metadata": {
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0..."
  },
  "signature": "304402203f5a8b2c1d...",
  "public_key": "04a1b2c3d4e5f6...",
  "flagged": false
}
```

| Field | Purpose |
|---|---|
| `transaction_id` | UUID; unique identifier. |
| `transaction_type` | Enum (LOGIN, TRANSFER, DATA_READ, CONFIG_CHANGE, etc). |
| `sender_address` | Derived from public key (first 40 chars of SHA256). |
| `timestamp` | ISO 8601 UTC. |
| `data` | Event-specific: {recipient, amount, currency} for TRANSFER; {resource_id, action} for DATA_READ, etc. |
| `metadata` | Context: IP, user agent, risk level. |
| `signature` | ECDSA signature of the transaction. |
| `public_key` | Public key for verifying signature. |

### Transaction Types Supported

**Authentication Events:**
- `LOGIN` – Successful login
- `LOGOUT` – Logout
- `LOGIN_FAILED` – Failed login (brute-force detection)
- `ACCESS_GRANTED` / `ACCESS_DENIED` – Resource access control

**Data Events:**
- `DATA_READ` – User read data
- `DATA_WRITE` – User wrote new data
- `DATA_MODIFY` – User modified data
- `DATA_DELETE` – User deleted data

**Administrative Events:**
- `CONFIG_CHANGE` – System config modified
- `PERMISSION_CHANGE` – User permissions changed
- `USER_CREATED` / `USER_DELETED` – Account lifecycle

**Financial (Demo):**
- `TRANSFER` – Money transfer

### The Complete Journey: Step-by-Step

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: CREATION                                                │
│                                                                  │
│  Client calls POST /api/transaction with type + data.           │
│  Request authenticated via JWT; RBAC enforced.                  │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: WALLET RESOLUTION & SIGNING                             │
│                                                                  │
│  Wallet is looked up or auto-created. Transaction is            │
│  signed using the wallet's private key.                         │
│  Signature proves sender identity + tx integrity.               │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: SIGNATURE VERIFICATION                                  │
│                                                                  │
│  TransactionAnalyzer verifies signature using public key.        │
│  If invalid → REJECTED (indexed as REJECTED, is_flagged=true).  │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                         (if valid)
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: FEATURE EXTRACTION                                      │
│                                                                  │
│  ML feature extractor converts tx to 25+ dimensional vector:     │
│  - Temporal: hour_sin, hour_cos, day_sin, day_cos, is_weekend   │
│  - Amount: amount, amount_log, is_high_amount                    │
│  - Behavioral: sender_tx_count_last_hour, activity_spike_ratio  │
│  - Etc.                                                           │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: ANOMALY SCORING (if model trained)                      │
│                                                                  │
│  Isolation Forest scores: -0.5 (anomalous) to +0.5 (normal).    │
│  Threshold -0.1 by default. Features triggering anomaly are     │
│  extracted for explanation.                                      │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
         SCORE >= -0.1 (NORMAL)   SCORE < -0.1 (ANOMALY)
                    │                     │
                    ▼                     ▼
    ┌──────────────────────────┐  ┌──────────────────────────┐
    │ Status: PENDING          │  │ Status: FLAGGED          │
    │ is_flagged: false        │  │ is_flagged: true         │
    │ Indexed in SQLite        │  │ Indexed in SQLite        │
    │ Alert saved to alerts DB │  │ Alert saved to alerts DB │
    │                          │  │ SocketIO: anomaly_detected│
    └──────────┬───────────────┘  └──────────┬────────────────┘
               │                             │
               └──────────────┬──────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 6: MEMPOOL                                                 │
│                                                                  │
│  Valid transaction (signed, analyzed) sits in mempool           │
│  waiting for administrator-triggered mining.                    │
│  Both PENDING and FLAGGED transactions go to mempool.           │
│  (No quarantine queue in current implementation.)                │
└──────────────────────────────┬─────────────────────────────────┘
                               │
        (OR on invalid sig/failure)
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
    ┌──────────────────────────┐  ┌──────────────────────────┐
    │ Status rejected/error    │  │ Transaction persists in  │
    │ Not added to mempool     │  │ transactions_index with  │
    │ SQLite shows REJECTED    │  │ its signature failure    │
    └──────────────────────────┘  │ or analysis rejection    │
                                  └──────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 7: MINING                                                  │
│                                                                  │
│  Admin/operator calls POST /api/mine.                            │
│  Mining batches mempool txs into a block, solves PoW puzzle.     │
│  Block is added to immutable chain and persisted to chain.json.  │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 8: BLOCKCHAIN (PERMANENT)                                  │
│                                                                  │
│  Block index updated in SQLite (block_index, tx_status=MINED).  │
│  is_flagged field preserved (anomalies remain flagged).         │
│  Each block refs prev block hash (immutable chain).              │
│  SocketIO: block_mined event emitted.                            │
└─────────────────────────────────────────────────────────────────┘
```

### Current Behavior (No Quarantine)

Unlike older designs, **flagged transactions are NOT quarantined for approval**. Instead:
- Valid but suspicious transactions are marked `FLAGGED` and go directly to mempool.
- They will be mined into the blockchain on the next mining operation.
- Alerts are stored in SQLite; admins review them post-hoc (or in real-time via Socket.IO).
- This design allows rapid event capture while still providing anomaly context for review.

---

## 8) Blockchain Operations

### What is a Block?

A block groups multiple transactions into an immutable unit. Each block:

```
┌─────────────────────────────────────────────────────────────────┐
│                       BLOCK #5                                   │
├─────────────────────────────────────────────────────────────────┤
│ HEADER:                                                           │
│   index: 5                                                        │
│   timestamp: "2026-03-06T14:35:00Z"                              │
│   previous_hash: "0000abc123def456..."  ← Links to block #4      │
│   merkle_root: "789xyz..."              ← Hash of all txs        │
│   nonce: 12847                          ← Mining solution        │
│   difficulty: 3                         ← PoW difficulty         │
│   block_hash: "0000def789..."           ← This block's hash      │
├─────────────────────────────────────────────────────────────────┤
│ TRANSACTIONS:                                                     │
│   - LOGIN: alice from 192.168.1.1                                │
│   - TRANSFER: bob → carol, 500 RON                               │
│   - DATA_READ: dave accessed resource XYZ                        │
│   ... (up to max_transactions_per_block=50)                      │
├─────────────────────────────────────────────────────────────────┤
│ COMPUTED:                                                         │
│   block_hash_valid: true                                         │
│   pow_valid: true (starts with 000)                              │
└─────────────────────────────────────────────────────────────────┘
```

### How Blocks Link (Immutability)

Each block contains the hash of the previous block, creating an unbreakable chain:

```
┌─────────────┐  previous_hash=ABC  ┌─────────────┐
│  BLOCK #0   ├───────────────────→ │  BLOCK #1   │
│ hash: ABC   │                      │ hash: DEF   │
└─────────────┘                      └─────────────┘

If someone modifies Block #0:
  → Block #0's new hash ≠ ABC
  → Block #1's previous_hash still points to ABC
  → Chain is broken = tampering detected!
```

### Mining: Proof-of-Work

Mining solves a computational puzzle to create blocks. The puzzle: find a nonce such that `SHA256(block_data || nonce)` starts with N zeros.

```
Target: "000" (difficulty=3, so 3 leading zeros)

Attempt 1: nonce=0 → hash="a7f3b2c1e8d9..." ❌
Attempt 2: nonce=1 → hash="3e9d8f7a2b1c..." ❌
...
Attempt 12847: nonce=12847 → hash="0000def789..." ✓

Proof = Block with nonce=12847 whose hash starts with "000".
```

**Why?** Making block creation expensive makes rewriting history expensive. An attacker would need to redo all the work.

### Merkle Trees: Efficient Proofs

Merkle Tree allows efficient proof that a transaction belongs to a block without checking all transactions:

```
                    ┌─────────────┐
                    │ Merkle Root │
                    │ = Hash(all) │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
         ┌────┴────┐               ┌────┴────┐
         │Hash(1-2)│               │Hash(3-4)│
         └────┬────┘               └────┬────┘
              │                         │
         ┌────┴────┐               ┌────┴────┐
      ┌──┴──┐  ┌──┴──┐          ┌──┴──┐  ┌──┴──┐
      │TX1  │  │TX2  │          │TX3  │  │TX4  │
      └─────┘  └─────┘          └─────┘  └─────┘
```

### Chain Validation

`GET /api/blockchain/validate` checks:
1. **Chain linkage**: Each block's `previous_hash` matches the prior block's `block_hash`.
2. **Block integrity**: Recomputed hash matches stored hash.
3. **Proof-of-Work**: Each block's hash starts with the required difficulty prefix.
4. **Signatures**: Every transaction's signature is valid.

---

## 9) Anomaly Detection Deep Dive

### Why Machine Learning?

Rule-based systems (e.g., "flag transfers > $10k") are easy to circumvent and miss complex patterns.

ML can detect subtle combinations: a $500 transfer might be normal during business hours but suspicious if:
- It's at 3 AM AND
- The user hasn't logged in for 6 months AND
- It's going to a new recipient AND
- There were 5 failed login attempts before.

### Isolation Forest

**Key idea**: Anomalies are "few and different." They are easier to separate from normal data.

```
Normal points (clustered):           Some anomalies:
  ○ ○ ○                                  
 ○ ○ ○ ○                                 ●  ← Quick to isolate
  ○ ○ ○                                  
 ○ ○ ○ ○
  ○ ○ ○
Hard to isolate any single normal point
```

The algorithm builds many random binary trees, isolating points recursively. Points that isolate quickly are likely anomalies.

### Feature Extraction (25+ Features)

`src/domain/ml/feature_extractor.py` converts each transaction into a numerical vector with:

**Temporal Features:**
- `hour_sin`, `hour_cos` – Cyclical hour encoding.
- `day_sin`, `day_cos` – Cyclical day-of-week encoding.
- `is_weekend`, `is_night` – Binary flags.

**Transaction Type Flags:**
- `is_auth_event`, `is_data_event`, `is_transfer_event`, `is_admin_event`, `is_failure_event` – Grouped categories.

**Amount Features:**
- `amount`, `amount_log` – Raw and log-scaled.
- `is_high_amount` – Boolean flag (> threshold).

**Behavioral Features (sender):**
- `sender_tx_count_last_hour`, `sender_tx_count_last_day` – Activity windows.
- `sender_amount_sum_last_hour`, `sender_amount_sum_last_day` – Cumulative amounts.
- `activity_spike_ratio` – Last hour / smoothed daily average.
- `time_since_last_tx` – Gap from last sender activity.
- `has_prior_tx` – Boolean (sender has history).

**Receiver Features:**
- `receiver_tx_count_last_hour`, `receiver_tx_count_last_day` – Recipient activity.
- `receiver_amount_sum_last_day` – Recipient cumulative amount.

**Risk Features:**
- `risk_level_encoded` – Enum: low/medium/high/critical → 0/1/2/3.
- `is_failed_attempt` – Boolean.

### Training the Model

`POST /api/anomaly/train` with `mode=blockchain` or `mode=synthetic`:

**Blockchain mode:**
- Gathers all transactions from chain.
- Extracts features → normalizes → fits Isolation Forest.
- Saves model to `ml_model.pkl`.

**Synthetic mode:**
- Generates 100–5000 synthetic "normal" transactions.
- Trains model on synthetic data.

### Model Persistence

At startup, if `ml_model.pkl` exists, it's loaded. No retraining required on restart.

---

## 10) Cryptographic Components

### ECDSA Signatures (SECP256K1)

Every transaction is signed using the sender's private key:

```
SIGNING:
  tx_data = {transaction_id, type, amount, ...}
  hash = SHA256(tx_data)
  signature = ECDSA_sign(hash, private_key)

VERIFICATION:
  hash = SHA256(tx_data)
  valid = ECDSA_verify(signature, hash, public_key)
```

### Wallet Structure

A wallet is a keypair + metadata:

```python
class Wallet:
    name: str                  # e.g., "alice"
    private_key: bytes         # SECRET
    public_key: bytes          # PUBLIC
    
    @property
    def address(self):
        # 40-char address derived from public key
        return SHA256(public_key)[:40]
```

### SHA-256 Hashing

Used throughout:
- **Block hashes**: Links blocks.
- **Merkle root**: Summarizes all txs in a block.
- **Password hashing**: Stores user passwords securely.

Properties:
- **Deterministic**: Same input → same output.
- **One-way**: Cannot reverse.
- **Collision-resistant**: Extremely rare.
- **Fixed size**: 64 hex chars (256 bits).

---

## 11) Data Persistence & Stores

### Storage Layout

| Component | Storage | Format | Path |
|---|---|---|---|
| Blockchain chain | JSON file | Serialized blocks | `data/blockchain/chain.json` |
| Mempool | JSON file | Pending txs | `data/blockchain/mempool.json` |
| User wallets | JSON files | Keypairs | `data/wallets/{name}.json` |
| Metadata DB | SQLite | Relational | `data/audit_metadata.db` |
| ML model | Pickle | Trained model | `data/ml_model.pkl` |
| Snapshots | ZIP archives | Backups | `data/backups/snapshot_*.zip` |

### SQLite Schema

**`users` table:**
- `id`, `username` (UNIQUE), `password_hash`, `role`, `wallet_name`, `is_active`, `created_at`, `last_login`

**`transaction_index` table:**
- `transaction_id` (PRIMARY KEY), `block_index`, `sender_address`, `transaction_type`, `amount`, `tx_status`, `is_flagged`, `ml_score`, `ml_reason`, `timestamp`

**`alerts` table:**
- `id`, `transaction_id`, `alert_type`, `severity`, `anomaly_score`, `explanation`, `is_resolved`, `created_at`, `resolved_at`, `resolved_by`

**`revoked_tokens` table:**
- `id`, `jti` (UNIQUE), `revoked_at`

---

## 12) API Surface (Full Reference)

All responses use standardized format (`src/api/responses.py`).

### Auth Endpoints

**POST /api/auth/login**
- Rate limit: 20/min per IP
- Returns: `access_token`, `refresh_token`, `user`

**POST /api/auth/refresh**
- Returns: New `access_token`

**POST /api/auth/logout**
- Effect: Token added to blacklist

**POST /api/auth/register** (admin only)
- Rate limit: 30/min per IP

**POST /api/auth/register-viewer** (public self-registration)
- Rate limit: 20/min per IP

### Blockchain Endpoints

**GET /api/health** (public)
- Response: Status, height, mempool size, detector status

**GET /api/blockchain**
- Pagination: `page`, `per_page`

**GET /api/blockchain/stats**
- Response: Height, tx counts, alert stats

**GET /api/blockchain/validate**
- Response: `is_valid`, `error`, `height`

**POST /api/mine** (admin/operator only)
- Rate limit: 20/min per IP
- Effect: Mine mempool → create block
- Socket.IO: Emits `block_mined`

### Transaction Endpoints

**GET /api/transactions**
- Filters: `type`, `sender`, `status`, `flagged`
- Pagination: `page`, `per_page`

**POST /api/transaction** (admin/operator only)
- Rate limit: 120/min per IP
- Returns: Transaction + analysis
- Socket.IO: Emits `anomaly_detected` if flagged

**GET /api/transaction/<id>**
- Returns: Proof or indexed data

### Anomaly & Alerts

**POST /api/anomaly/train** (admin/operator only)
- Rate limit: 10/min
- Returns: Training stats

**GET /api/alerts**
- Filters: `severity`, `resolved`
- Pagination: `page`, `per_page`

**PUT /api/alerts/<id>/resolve** (admin/operator only)
- Effect: Mark alert resolved

### Audit & Backups

**POST /api/audit/backup** (admin only)
- Rate limit: 5/min
- Effect: Create snapshot
- Status: 201 Created

**POST /api/audit/restore** (admin only)
- Rate limit: 3/min
- Effect: Restore from snapshot

---

## 13) Realtime Alerts (Socket.IO)

Namespace: `/alerts` (JWT-authenticated).

### Connection

```javascript
const socket = io('http://127.0.0.1:5000/alerts', {
  auth: { token: "eyJhbGc..." }
});
```

### Server Events

| Event | When | Data |
|---|---|---|
| `connected` | Client connects | `{ message, timestamp }` |
| `anomaly_detected` | Suspicious tx | `{ alert_id, transaction_id, explanation, score }` |
| `block_mined` | Mining succeeds | `{ block_index, transaction_count, anomalies_found }` |

---

## 14) Setup & Run

### Prerequisites

- Python 3.9+
- Node.js 18+

### Backend Installation (PowerShell)

```powershell
cd C:\Users\tudor\PycharmProjects\licenta_ml_fixed
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Frontend Installation

```powershell
cd frontend
npm install
```

### Running Backend

```powershell
python main.py
```

Server at `http://127.0.0.1:5000/`.

### Running Frontend (Dev)

```powershell
cd frontend
npm run dev
```

### Default Credentials (Dev Only)

- Username: `admin`
- Password: `admin123`

---

## 15) Configuration

Environment variables:

| Variable | Default | Note |
|---|---|---|
| `APP_ENV` | `development` | Set to `production` for stricter checks |
| `JWT_SECRET_KEY` | (dev: auto-generated) | Required in production |
| `ADMIN_PASSWORD` | `admin123` | Dev only; set strong password in production |
| `DATA_DIR` | `data` | Base data folder |
| `METADATA_DB` | `data/audit_metadata.db` | SQLite path |
| `ML_MODEL_PATH` | `data/ml_model.pkl` | Model file |
| `SNAPSHOT_RETENTION_COUNT` | `20` | Backup cap |
| `HOST` | `127.0.0.1` | Bind host |
| `PORT` | `5000` | Bind port |

### Production Example

```powershell
$env:APP_ENV = "production"
$env:JWT_SECRET_KEY = "your-long-random-secret-key"
$env:ADMIN_PASSWORD = "strong-password"
python main.py
```

---

## 16) Testing

### Main Regression (API Smoke Test)

```powershell
python test_api.py
```

Covers: auth, RBAC, pagination, txs, detector, mining, backups, rate limiting.

### Additional Tests

```powershell
python test_architecture_layers.py
python test_role_access_control.py
python test_transaction_audit_statistics.py
```

---

## 17) Dashboard & UI

React/Vite frontend at `/` (or frontend dev URL).

### Key Screens

- **Login** – Authenticate
- **Dashboard** – Overview, key actions
- **Blockchain** – Paginated blocks
- **Transactions** – Filtered tx list
- **Alerts** – Anomaly management
- **Wallets** – Wallet management

---

## 18) Operational Notes & Troubleshooting

- **Test data mutates state**: Use disposable test data.
- **Snapshot restore needs restart**: App must reload in-memory state.
- **Port in use**: `main.py` checks availability; change `PORT` env var if needed.
- **Blockchain re-indexing**: On startup, existing txs indexed into SQLite.
- **Rate limiting**: In-memory per IP + operation; survives requests but not app restart.

---

## 19) Known Limitations & Scope

- **Single-node only**: No P2P, no distributed consensus.
- **No labeled ML training**: Isolation Forest unsupervised; benefits from historical "normal" data.
- **Cold-start ML**: New systems should generate synthetic data or wait for history.
- **Wallet key management**: Loss of `WALLET_ENCRYPTION_KEY` = loss of wallets.

---

For detailed architectural decisions, see `AGENTS.md`. For historical workflow context, see `WORKFLOW.md` (note: quarantine system references are deprecated).

