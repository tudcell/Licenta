# Blockchain Audit System - Complete Workflow Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Authentication Flow](#authentication-flow)
4. [Transaction Lifecycle](#transaction-lifecycle)
5. [Blockchain Operations](#blockchain-operations)
6. [Anomaly Detection System](#anomaly-detection-system)
7. [Quarantine System](#quarantine-system)
8. [Cryptographic Components](#cryptographic-components)
9. [API Endpoints Reference](#api-endpoints-reference)
10. [WebSocket Events](#websocket-events)
11. [Data Persistence](#data-persistence)
12. [Dashboard Features](#dashboard-features)

---

## System Overview

### What is this system?

This application is a **blockchain-based audit logging system** combined with **machine learning anomaly detection**. It serves as a secure, tamper-proof record of events (like user logins, data access, financial transfers) while automatically detecting suspicious activities.

### Why use blockchain for auditing?

Traditional audit logs stored in databases can be modified, deleted, or corrupted. By using blockchain technology, every audit event becomes **immutable** - once recorded, it cannot be changed without breaking the entire chain. This provides:

- **Tamper evidence**: Any modification is immediately detectable
- **Non-repudiation**: Events are cryptographically signed, proving who created them
- **Transparency**: The complete history is verifiable by anyone with access
- **Decentralization potential**: Can be extended to multiple nodes for redundancy

### Why add machine learning?

Human auditors cannot review thousands of transactions in real-time. The system uses an **Isolation Forest** algorithm to automatically flag unusual patterns, such as:

- Transactions at unusual hours (2-5 AM)
- Unusually large amounts
- Rapid succession of transactions (potential attacks)
- Activity from users who rarely transact
- Failed login attempts followed by successful ones

### Core Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Blockchain** | Immutable storage of audit events | Custom Python implementation |
| **ML Detector** | Automatic anomaly detection | Scikit-learn Isolation Forest |
| **Quarantine** | Human review of flagged transactions | Custom queue system |
| **REST API** | External interface for applications | Flask |
| **WebSocket** | Real-time alerts | Flask-SocketIO |
| **Authentication** | Secure access control | JWT tokens |

---

## Architecture

### How the system is organized

The codebase follows a layered architecture where each layer has a specific responsibility:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                            │
│         Dashboard (HTML/JS) + REST API + WebSocket              │
│                                                                  │
│  This layer handles user interaction. The dashboard provides    │
│  a visual interface, while the API allows programmatic access.  │
│  WebSocket enables real-time notifications without polling.     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BUSINESS LOGIC LAYER                         │
│      Transaction Analyzer + Quarantine Manager + Mining         │
│                                                                  │
│  This layer contains the core business rules. It decides        │
│  whether transactions are suspicious, manages the quarantine    │
│  workflow, and handles the blockchain mining process.           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA ACCESS LAYER                           │
│        Blockchain Storage + SQLite + ML Model Files             │
│                                                                  │
│  This layer manages persistence. The blockchain is stored as    │
│  JSON files, metadata lives in SQLite, and the trained ML       │
│  model is serialized using Python's pickle format.              │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure Explained

```
src/
├── api/                      # Everything related to the web interface
│   ├── app.py               # The main Flask application factory
│   ├── extensions.py        # Shared Flask extensions (JWT, WebSocket)
│   ├── database.py          # SQLite operations for metadata
│   ├── auth.py              # Password hashing and verification
│   ├── responses.py         # Standardized API response format
│   └── routes/              # Each file handles a group of endpoints
│       ├── auth_routes.py       # Login, logout, registration
│       ├── blockchain_routes.py # View chain, mine blocks
│       ├── transaction_routes.py# Create and view transactions
│       ├── quarantine_routes.py # Review suspicious transactions
│       ├── wallet_routes.py     # Manage user wallets
│       ├── anomaly_routes.py    # ML training and alerts
│       └── audit_routes.py      # Integrity checks and exports
│
├── blockchain/              # The blockchain implementation
│   ├── block.py            # Defines what a block contains
│   ├── blockchain.py       # Manages the chain of blocks
│   ├── transaction.py      # Defines what a transaction contains
│   ├── wallet.py           # Manages cryptographic keys
│   └── quarantine.py       # Holds suspicious transactions
│
├── crypto/                  # Cryptographic utilities
│   ├── digital_signature.py # Signs and verifies transactions
│   ├── hashing.py          # SHA-256 hash functions
│   └── merkle_tree.py      # Efficient transaction verification
│
├── ml/                      # Machine learning components
│   ├── anomaly_detector.py # The Isolation Forest model
│   ├── feature_extractor.py# Converts transactions to numbers
│   └── transaction_analyzer.py # Coordinates the analysis
│
└── utils/
    └── data_generator.py   # Creates test data for demos
```

---

## Authentication Flow

### Understanding JWT Authentication

JSON Web Tokens (JWT) are used to authenticate users without storing session data on the server. Here's how the flow works:

**Step 1: User logs in**

The user sends their username and password to the login endpoint. The server verifies the password against a stored hash (not the plain password - that would be insecure).

**Step 2: Server issues tokens**

If credentials are valid, the server creates two tokens:
- **Access token**: Short-lived (1 hour), used for API requests
- **Refresh token**: Long-lived (30 days), used only to get new access tokens

**Step 3: Client uses access token**

For every API request, the client includes the access token in the Authorization header. The server validates this token without needing to look up session data.

**Step 4: Token refresh**

When the access token expires, the client uses the refresh token to get a new access token without requiring the user to log in again.

### Visual representation of the auth flow

```
USER                           SERVER                         DATABASE
 │                               │                               │
 │  "I want to log in"           │                               │
 │  username: admin              │                               │
 │  password: admin123           │                               │
 │──────────────────────────────>│                               │
 │                               │  "Let me check the database"  │
 │                               │──────────────────────────────>│
 │                               │                               │
 │                               │  User found, here's the hash  │
 │                               │<──────────────────────────────│
 │                               │                               │
 │                               │  Hash matches! Create tokens  │
 │                               │                               │
 │  Here are your tokens:        │                               │
 │  - access_token (1 hour)      │                               │
 │  - refresh_token (30 days)    │                               │
 │<──────────────────────────────│                               │
 │                               │                               │
 │  Later: "Show me the blockchain"                              │
 │  Authorization: Bearer <access_token>                         │
 │──────────────────────────────>│                               │
 │                               │  Token valid! Here's the data │
 │  [blockchain data]            │                               │
 │<──────────────────────────────│                               │
```

### What's inside a JWT token?

A JWT token contains three parts separated by dots: `header.payload.signature`

The payload contains claims about the user:

```python
# Example payload (decoded from a real token)
{
    "sub": "admin",           # Who this token belongs to
    "role": "admin",          # What they're allowed to do
    "wallet_name": "admin",   # Their associated wallet
    "exp": 1709750400,        # When the token expires (Unix timestamp)
    "iat": 1709746800,        # When the token was issued
    "jti": "abc123..."        # Unique ID (for revocation)
}
```

### Role-Based Access Control

Not all users can do everything. The system defines three roles:

| Role | What they can do |
|------|------------------|
| **admin** | Everything: create users, mine blocks, train ML, export data, approve quarantine |
| **operator** | Most operations: create transactions, mine blocks, train ML, review quarantine |
| **viewer** | Read-only access: view blockchain, transactions, alerts, statistics |

### How passwords are stored securely

Passwords are never stored in plain text. Instead, the system uses salted hashing:

```python
# When a user creates an account:
salt = generate_random_string(32)       # e.g., "a1b2c3d4..."
hash = SHA256(salt + password)          # e.g., "9f86d0..."
stored = f"{salt}:{hash}"               # e.g., "a1b2c3d4...:9f86d0..."

# When a user logs in:
stored_salt, stored_hash = stored.split(":")
computed_hash = SHA256(stored_salt + entered_password)
is_valid = (computed_hash == stored_hash)
```

The salt prevents attackers from using precomputed "rainbow tables" to crack passwords.

---

## Transaction Lifecycle

### What is a transaction?

In this system, a transaction represents any auditable event. Unlike cryptocurrency blockchains where transactions move money, this system records audit events like:

- User logged in from IP 192.168.1.100
- User accessed sensitive document XYZ
- User transferred $5000 to account ABC
- Configuration setting changed from A to B

### The complete journey of a transaction

Let's follow a transaction from creation to permanent storage:

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: CREATION                                                │
│                                                                  │
│  A user or system creates a transaction through the API.        │
│  The transaction includes: type, data, timestamp, and the       │
│  sender's identity.                                              │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: SIGNING                                                 │
│                                                                  │
│  The sender's wallet signs the transaction using their private  │
│  key. This proves the transaction came from them and hasn't     │
│  been modified. The signature is attached to the transaction.   │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: SIGNATURE VERIFICATION                                  │
│                                                                  │
│  Before processing, the system verifies the signature using     │
│  the sender's public key. If invalid, the transaction is        │
│  rejected immediately - it might be forged or corrupted.        │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: FEATURE EXTRACTION                                      │
│                                                                  │
│  The ML system extracts numerical features from the             │
│  transaction: What hour is it? How much money? How many         │
│  transactions has this user made recently? These numbers        │
│  feed into the anomaly detector.                                │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: ANOMALY DETECTION                                       │
│                                                                  │
│  The Isolation Forest model scores the transaction. A negative  │
│  score indicates anomaly (the more negative, the more unusual). │
│  The threshold is -0.1 by default.                              │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│  NORMAL (score >= -0.1)      │  │  ANOMALY (score < -0.1)      │
│                              │  │                              │
│  Transaction goes directly   │  │  Transaction is placed in   │
│  to the mempool (waiting     │  │  quarantine for human review │
│  area for mining).           │  │  before it can proceed.      │
└──────────────┬───────────────┘  └──────────────┬───────────────┘
               │                                  │
               │                    ┌─────────────┴─────────────┐
               │                    │                           │
               │                    ▼                           ▼
               │         ┌──────────────────┐        ┌──────────────────┐
               │         │  ADMIN APPROVES  │        │  ADMIN REJECTS   │
               │         │                  │        │                  │
               │         │  Transaction     │        │  Transaction is  │
               │         │  moves to        │        │  permanently     │
               │         │  mempool         │        │  discarded       │
               │         └────────┬─────────┘        └──────────────────┘
               │                  │
               └────────┬─────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 6: MEMPOOL                                                 │
│                                                                  │
│  The mempool is a waiting area. Transactions sit here until    │
│  an administrator triggers mining. Think of it as a staging    │
│  area before permanent commitment.                               │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 7: MINING                                                  │
│                                                                  │
│  Mining groups mempool transactions into a block. The system   │
│  must solve a computational puzzle (Proof-of-Work) to create   │
│  the block. This makes it expensive to tamper with history.    │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 8: BLOCKCHAIN (PERMANENT)                                  │
│                                                                  │
│  The block is added to the chain. Each block references the    │
│  previous block's hash, creating an unbreakable link. Any      │
│  modification to a past block would change its hash, breaking  │
│  all subsequent blocks.                                          │
└─────────────────────────────────────────────────────────────────┘
```

### Types of transactions supported

The system supports various audit event types:

**Authentication Events:**
- `LOGIN` - User successfully logged in
- `LOGOUT` - User logged out
- `LOGIN_FAILED` - Failed login attempt (important for detecting brute force attacks)

**Access Events:**
- `ACCESS_GRANTED` - User was allowed to access a resource
- `ACCESS_DENIED` - User was denied access (potential unauthorized access attempt)

**Data Events:**
- `DATA_READ` - User read data (audit trail for sensitive information)
- `DATA_WRITE` - User wrote new data
- `DATA_MODIFY` - User modified existing data
- `DATA_DELETE` - User deleted data (critical for compliance)

**Administrative Events:**
- `CONFIG_CHANGE` - System configuration was modified
- `PERMISSION_CHANGE` - User permissions were changed
- `USER_CREATED` - New user account created
- `USER_DELETED` - User account deleted

**Financial (Demo):**
- `TRANSFER` - Money transfer between accounts

### Transaction data structure

Here's what a transaction looks like internally:

```python
{
    "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
    "transaction_type": "TRANSFER",
    "sender_address": "a1b2c3d4e5f6789012345678901234567890",
    "timestamp": "2026-03-06T14:30:00.000000",
    "data": {
        "recipient": "9876543210fedcba9876543210fedcba12345678",
        "amount": 1500.00,
        "currency": "RON"
    },
    "metadata": {
        "ip_address": "192.168.1.100",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    },
    "signature": "304402203f5a8b2c1d...",
    "public_key": "04a1b2c3d4e5f6..."
}
```

Let's break down each field:
- **transaction_id**: A unique identifier (UUID) for this specific transaction
- **transaction_type**: What kind of event this represents
- **sender_address**: Who created this transaction (derived from their public key)
- **timestamp**: When the transaction was created
- **data**: Event-specific information (varies by type)
- **metadata**: Additional context (IP address, browser, etc.)
- **signature**: Cryptographic proof that the sender created this
- **public_key**: Used to verify the signature

---

## Blockchain Operations

### What is a block?

A block is a container that groups multiple transactions together. Think of it like a page in a ledger book - once the page is full and signed, you move to the next page. Each block contains:

1. **Header**: Metadata about the block
2. **Body**: The actual transactions
3. **Computed fields**: Values calculated from the above

### Block structure explained

```
┌─────────────────────────────────────────────────────────────────┐
│                          BLOCK #5                                │
├─────────────────────────────────────────────────────────────────┤
│  HEADER (metadata about this block)                              │
│                                                                  │
│  index: 5                                                        │
│    → Position in the chain (0 = genesis, 1 = first, etc.)       │
│                                                                  │
│  timestamp: "2026-03-06T14:35:00"                               │
│    → When this block was created                                │
│                                                                  │
│  previous_hash: "0000abc123def456..."                           │
│    → Hash of block #4 (creates the chain link)                  │
│                                                                  │
│  merkle_root: "789xyz..."                                       │
│    → Single hash representing ALL transactions                  │
│                                                                  │
│  nonce: 12847                                                   │
│    → The number that solved the mining puzzle                   │
│                                                                  │
│  difficulty: 4                                                   │
│    → How hard the puzzle was (4 leading zeros required)         │
├─────────────────────────────────────────────────────────────────┤
│  BODY (the actual content)                                       │
│                                                                  │
│  transactions: [                                                 │
│    Transaction 1: LOGIN by alice at 14:30                       │
│    Transaction 2: TRANSFER $500 by bob at 14:31                 │
│    Transaction 3: DATA_READ by carol at 14:32                   │
│    ... (up to max_transactions_per_block)                       │
│  ]                                                               │
├─────────────────────────────────────────────────────────────────┤
│  COMPUTED (calculated from header)                               │
│                                                                  │
│  block_hash: "0000def789..."                                    │
│    → SHA-256 of the entire header                               │
│    → Starts with "0000" because difficulty = 4                  │
└─────────────────────────────────────────────────────────────────┘
```

### How blocks link together

The "chain" in blockchain comes from each block containing the hash of the previous block:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  BLOCK #0   │     │  BLOCK #1   │     │  BLOCK #2   │
│  (Genesis)  │     │             │     │             │
│             │     │             │     │             │
│ hash: ABC   │◄────│ prev: ABC   │◄────│ prev: DEF   │
│             │     │ hash: DEF   │     │ hash: GHI   │
└─────────────┘     └─────────────┘     └─────────────┘

If someone tries to modify Block #1:
  → Block #1's hash changes (no longer DEF)
  → Block #2's "previous_hash" no longer matches
  → The chain is broken and the tampering is detected!
```

### Mining: The Proof-of-Work process

Mining is the process of adding a new block to the chain. It requires solving a computational puzzle that's easy to verify but hard to solve.

**The puzzle**: Find a number (nonce) such that when combined with the block data and hashed, the result starts with a certain number of zeros.

```
Target: Hash must start with "0000" (difficulty = 4)

Attempt 1:
  nonce = 0
  hash(block_data + "0") = "a7f3b2c1e8d9..." 
  Does not start with "0000" ❌

Attempt 2:
  nonce = 1
  hash(block_data + "1") = "3e9d8f7a2b1c..."
  Does not start with "0000" ❌

... (thousands of attempts) ...

Attempt 12847:
  nonce = 12847
  hash(block_data + "12847") = "0000abc1def2..."
  Starts with "0000" ✓ SUCCESS!
```

The code looks like this:

```python
def mine(self, difficulty=4):
    target = "0" * difficulty  # e.g., "0000" for difficulty 4
    
    while True:
        self.nonce += 1
        self.block_hash = sha256(self.header + str(self.nonce))
        
        if self.block_hash.startswith(target):
            return  # Puzzle solved!
```

**Why do this?** Making blocks expensive to create (in computational terms) makes it expensive to rewrite history. An attacker would need to redo all the work for every block they want to change.

### The Merkle Tree: Efficient transaction verification

A Merkle Tree is a data structure that allows efficient verification of transaction inclusion. Instead of checking every transaction, you can verify a single transaction belongs to a block with just a few hashes.

```
                    ┌─────────────┐
                    │ Merkle Root │
                    │  = Hash of  │
                    │  everything │
                    └──────┬──────┘
                           │
             ┌─────────────┴─────────────┐
             │                           │
       ┌─────┴─────┐               ┌─────┴─────┐
       │  Hash of  │               │  Hash of  │
       │  TX1+TX2  │               │  TX3+TX4  │
       └─────┬─────┘               └─────┬─────┘
             │                           │
       ┌─────┴─────┐               ┌─────┴─────┐
       │           │               │           │
   ┌───┴───┐   ┌───┴───┐       ┌───┴───┐   ┌───┴───┐
   │Hash of│   │Hash of│       │Hash of│   │Hash of│
   │  TX1  │   │  TX2  │       │  TX3  │   │  TX4  │
   └───────┘   └───────┘       └───────┘   └───────┘
```

**Example verification**: To prove TX2 is in the block, you only need:
1. Hash of TX1 (the sibling)
2. Hash of TX3+TX4 (the uncle)
3. The Merkle Root

The verifier computes upward and checks if the result matches the Merkle Root stored in the block header.

### Chain validation: Detecting tampering

The system can verify the entire blockchain's integrity at any time:

```python
def validate_chain(self):
    for i in range(1, len(self.chain)):
        current_block = self.chain[i]
        previous_block = self.chain[i - 1]
        
        # Check 1: Is the chain properly linked?
        if current_block.previous_hash != previous_block.block_hash:
            return False, f"Block {i}: Chain broken - previous hash mismatch"
        
        # Check 2: Is the block's hash correct?
        if current_block.block_hash != current_block.calculate_hash():
            return False, f"Block {i}: Hash doesn't match content (tampering?)"
        
        # Check 3: Was the mining puzzle actually solved?
        required_prefix = "0" * current_block.difficulty
        if not current_block.block_hash.startswith(required_prefix):
            return False, f"Block {i}: Proof-of-Work invalid"
        
        # Check 4: Are all transactions properly signed?
        for tx in current_block.transactions:
            if not tx.verify_signature():
                return False, f"Block {i}: Invalid transaction signature"
    
    return True, None  # All checks passed!
```

---

## Anomaly Detection System

### Why use machine learning for anomaly detection?

Rule-based systems (like "flag transactions over $10,000") are easy to circumvent and miss complex patterns. Machine learning can detect subtle combinations of factors that indicate fraud.

For example, a $500 transfer might be perfectly normal during business hours but suspicious if:
- It's at 3 AM AND
- The user hasn't logged in for 6 months AND
- It's going to a new recipient AND
- There were 5 failed login attempts just before

The ML model learns what "normal" looks like and flags deviations.

### Understanding Isolation Forest

Isolation Forest is an unsupervised learning algorithm designed specifically for anomaly detection. Here's the intuition:

**Key insight**: Anomalies are "few and different." They are easier to separate from the rest of the data.

Imagine a 2D scatter plot with 100 points clustered together and 2 points far from the cluster. If you randomly draw lines to separate points, the isolated points get separated quickly, while the clustered points require many more cuts.

```
Normal points (clustered):        Anomaly (isolated):
    ○ ○ ○                              
   ○ ○ ○ ○                             ●  ← Easy to isolate!
    ○ ○ ○                       
   ○ ○ ○ ○                       
    ○ ○ ○                       
  Hard to isolate any single one
```

The algorithm builds many random "isolation trees" and measures how quickly each point gets isolated. Points that are isolated quickly are likely anomalies.

### Feature extraction: Converting transactions to numbers

Machine learning algorithms work with numbers, not with "LOGIN" or "alice". The feature extractor converts each transaction into a 13-dimensional vector:

| Feature | What it measures | Why it matters |
|---------|------------------|----------------|
| `hour_of_day` (0-23) | Time of transaction | 3 AM activity is unusual for offices |
| `day_of_week` (0-6) | Day of transaction | Weekend activity unusual for business |
| `is_weekend` (0 or 1) | Is it Saturday/Sunday? | Binary flag for weekend |
| `is_night` (0 or 1) | Is it 10 PM - 6 AM? | Night activity is often suspicious |
| `transaction_type_encoded` | Numeric code for type | Different types have different risks |
| `amount` | Raw amount value | Large amounts are higher risk |
| `amount_log` | log(amount + 1) | Normalized for ML (handles outliers) |
| `sender_tx_count_last_hour` | Recent activity | Burst of activity = potential attack |
| `sender_tx_count_last_day` | Daily activity | Unusually high volume |
| `time_since_last_tx` | Seconds since last | Very fast = automated attack? |
| `is_high_amount` (0 or 1) | Above threshold? | Flags large transfers |
| `risk_level_encoded` (0-3) | Low/Med/High/Critical | Access to sensitive resources |
| `is_failed_attempt` (0 or 1) | Was it a failed login? | Brute force detection |

### The detection pipeline

Here's how a transaction gets analyzed:

```
┌──────────────────────────────────────────────────────────────────┐
│  INPUT: Transaction                                               │
│                                                                   │
│  Type: TRANSFER                                                   │
│  Amount: $50,000                                                  │
│  Time: 03:15 AM                                                   │
│  Sender: alice (usually active 9-5)                               │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  FEATURE EXTRACTION                                               │
│                                                                   │
│  hour_of_day = 3                                                  │
│  is_night = 1                                                     │
│  amount = 50000.0                                                 │
│  amount_log = 10.82                                               │
│  is_high_amount = 1                                               │
│  sender_tx_count_last_hour = 0                                    │
│  time_since_last_tx = 86400 (24 hours)                           │
│  ... (other features)                                             │
│                                                                   │
│  Vector: [3, 3, 0, 1, 13, 50000, 10.82, 0, 1, 86400, 1, 0, 0]    │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  NORMALIZATION                                                    │
│                                                                   │
│  The StandardScaler transforms features to have zero mean and    │
│  unit variance. This prevents features with large values (like   │
│  amount) from dominating features with small values (like        │
│  is_night).                                                       │
│                                                                   │
│  Normalized: [-0.2, 0.5, -0.3, 2.1, 0.8, 3.5, 2.8, ...]         │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  ISOLATION FOREST PREDICTION                                      │
│                                                                   │
│  The model scores the transaction based on how easily it can    │
│  be isolated from normal transactions.                           │
│                                                                   │
│  Score: -0.342                                                    │
│                                                                   │
│  Interpretation:                                                  │
│    score > 0: Normal                                              │
│    score < -0.1: Anomaly (threshold is configurable)             │
│    More negative = More anomalous                                 │
│                                                                   │
│  Result: ANOMALY (score -0.342 < threshold -0.1)                 │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  EXPLANATION GENERATION                                           │
│                                                                   │
│  The system checks which features triggered the anomaly:         │
│                                                                   │
│  ✓ is_night = 1 → "night activity (hour=3)"                      │
│  ✓ is_high_amount = 1 → "unusually large amount (50000.00)"      │
│  ✓ time_since_last = 86400 → "first activity in 24 hours"        │
│                                                                   │
│  Final explanation:                                               │
│  "Anomaly detected: night activity (hour=3);                     │
│   unusually large amount (50000.00) [score: -0.342]"             │
└──────────────────────────────────────────────────────────────────┘
```

### Training the model

Before the model can detect anomalies, it must learn what "normal" looks like. This is called training:

```python
# Step 1: Gather historical transactions
transactions = blockchain.get_all_transactions()

# Step 2: Extract features from each
features = []
for tx in transactions:
    feature_vector = extractor.extract(tx)
    features.append(feature_vector.to_vector())

# Step 3: Create a matrix (rows = transactions, columns = features)
feature_matrix = numpy.array(features)

# Step 4: Normalize the features
scaler = StandardScaler()
normalized_matrix = scaler.fit_transform(feature_matrix)

# Step 5: Train the Isolation Forest
model = IsolationForest(
    contamination=0.1,      # Expect about 10% anomalies
    n_estimators=100,       # Use 100 decision trees
    random_state=42         # For reproducibility
)
model.fit(normalized_matrix)

# Step 6: Save for later use
model.save("ml_model.pkl")
```

### Model persistence

The trained model is automatically saved to disk after training. On application restart, it's loaded back:

```python
# At startup:
if file_exists("ml_model.pkl"):
    detector = AnomalyDetector.load("ml_model.pkl")
    print("Model loaded! Ready to detect anomalies.")
else:
    print("No model found. Please train the detector first.")
```

This means you don't need to retrain every time you restart the application.

---

## Quarantine System

### Why quarantine instead of reject?

False positives happen. A legitimate $50,000 CEO bonus at midnight might look suspicious but is perfectly valid. Instead of automatically rejecting (losing valid transactions) or automatically accepting (letting fraud through), the system quarantines for human review.

### Quarantine states explained

```
┌─────────────────────────────────────────────────────────────────┐
│                     PENDING                                      │
│                                                                  │
│  The transaction is waiting for an administrator to review it.  │
│  It cannot proceed to the blockchain in this state.             │
│                                                                  │
│  Contains:                                                       │
│  - The original transaction                                      │
│  - Anomaly score and explanation                                 │
│  - When it was quarantined                                       │
│  - (Review fields are empty)                                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
              ▼                                   ▼
┌─────────────────────────┐         ┌─────────────────────────┐
│        CLEARED          │         │        REJECTED         │
│                         │         │                         │
│  Administrator reviewed │         │  Administrator reviewed │
│  and APPROVED.          │         │  and REJECTED.          │
│                         │         │                         │
│  The transaction moves  │         │  The transaction is     │
│  to the mempool and     │         │  permanently discarded. │
│  will be mined into     │         │  It will never enter    │
│  the blockchain.        │         │  the blockchain.        │
│                         │         │                         │
│  Contains:              │         │  Contains:              │
│  - reviewed_by: "admin" │         │  - reviewed_by: "admin" │
│  - reviewed_at: time    │         │  - reviewed_at: time    │
│  - review_notes: "..."  │         │  - review_notes: "..."  │
└─────────────────────────┘         └─────────────────────────┘
```

### The review process

When an administrator reviews a quarantined transaction, they see:

1. **Full transaction details**: Type, amount, sender, timestamp
2. **Anomaly information**: Score, explanation, confidence level
3. **Feature breakdown**: All 13 features with their values
4. **Context**: Sender's recent history, similar past transactions

They then decide:
- **APPROVE**: "This is a false positive. The transaction is legitimate."
- **REJECT**: "This is suspicious/fraudulent. Do not allow it."

Both actions require notes explaining the decision (for audit purposes).

### Quarantine entry structure

```python
{
    "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
    
    "transaction": {
        # Full transaction data here
    },
    
    "anomaly_score": -0.342,
    "anomaly_explanation": "night activity (hour=3); unusually large amount",
    "confidence": 0.85,
    
    "quarantined_at": "2026-03-06T03:15:00.000000Z",
    "status": "PENDING",
    
    "reviewed_by": null,
    "reviewed_at": null,
    "review_notes": null
}
```

After review:

```python
{
    # ... same as above ...
    
    "status": "CLEARED",
    
    "reviewed_by": "admin",
    "reviewed_at": "2026-03-06T09:30:00.000000Z",
    "review_notes": "Verified with CEO - legitimate annual bonus payment"
}
```

---

## Cryptographic Components

### Digital Signatures: Proving authorship

Every transaction must be signed by its creator. This serves two purposes:

1. **Authentication**: Proves the transaction came from the claimed sender
2. **Integrity**: Proves the transaction hasn't been modified

The system uses **ECDSA** (Elliptic Curve Digital Signature Algorithm) with the **secp256k1** curve (the same curve used by Bitcoin).

### How signing works

```
┌─────────────────────────────────────────────────────────────────┐
│                        SIGNING PROCESS                           │
│                                                                  │
│  The sender has a private key (kept secret) and a public key   │
│  (shared with everyone). Only the private key can create        │
│  signatures that the public key can verify.                     │
└─────────────────────────────────────────────────────────────────┘

Step 1: Take the transaction data
         ┌──────────────────────────────────┐
         │  transaction_id: "abc123..."     │
         │  type: "TRANSFER"                │
         │  amount: 5000                    │
         │  timestamp: "2026-03-06T..."     │
         └──────────────────────────────────┘
                          │
                          ▼
Step 2: Hash the data (SHA-256)
         ┌──────────────────────────────────┐
         │  hash: "9f86d081884c7d659..."    │
         └──────────────────────────────────┘
                          │
                          ▼
Step 3: Sign with private key (ECDSA)
         ┌──────────────────────────────────┐
         │  private_key: "e8f7a6b5c4..."   │
         │         +                        │
         │  hash: "9f86d081884c7d659..."    │
         │         ↓                        │
         │  signature: "304402203f5a8b..."  │
         └──────────────────────────────────┘
```

### How verification works

```
┌─────────────────────────────────────────────────────────────────┐
│                     VERIFICATION PROCESS                         │
│                                                                  │
│  Anyone with the public key can verify the signature, but       │
│  cannot create new signatures (that requires the private key).  │
└─────────────────────────────────────────────────────────────────┘

Step 1: Receive the transaction with signature
         ┌──────────────────────────────────┐
         │  transaction data + signature    │
         └──────────────────────────────────┘
                          │
                          ▼
Step 2: Hash the transaction data (same as sender did)
         ┌──────────────────────────────────┐
         │  hash: "9f86d081884c7d659..."    │
         └──────────────────────────────────┘
                          │
                          ▼
Step 3: Verify using public key + signature + hash
         ┌──────────────────────────────────┐
         │  public_key: "04a1b2c3d4..."    │
         │  signature: "304402203f5a8b..."  │
         │  hash: "9f86d081884c7d659..."    │
         │         ↓                        │
         │  ECDSA.verify() = true/false     │
         └──────────────────────────────────┘

If true: Signature is valid, transaction is authentic
If false: Signature is invalid, transaction may be forged
```

### Wallet structure

A wallet is simply a container for a key pair:

```python
class Wallet:
    name: str                    # Human-readable name like "alice"
    private_key: bytes          # SECRET - used for signing
    public_key: bytes           # PUBLIC - shared with everyone
    
    @property
    def address(self):
        # The address is derived from the public key
        # It's the first 40 characters of SHA-256(public_key)
        # Example: "a1b2c3d4e5f6789012345678901234567890"
        return sha256(self.public_key)[:40]
```

**Security note**: The private key must NEVER be shared. Anyone with the private key can sign transactions as that user.

### SHA-256 Hashing

SHA-256 (Secure Hash Algorithm 256-bit) is used throughout the system:

- **Transaction hashes**: Unique identifier for each transaction
- **Block hashes**: Links blocks together
- **Merkle roots**: Summarizes all transactions in a block
- **Password hashes**: Stores passwords securely

Properties of SHA-256:
- **Deterministic**: Same input always produces same output
- **One-way**: Cannot reverse the hash to get the input
- **Collision-resistant**: Extremely hard to find two inputs with the same hash
- **Fixed size**: Always 64 hexadecimal characters (256 bits)

---

## API Endpoints Reference

### Authentication Endpoints

**POST /api/auth/login**
- Purpose: Authenticate and receive JWT tokens
- Authentication: None required
- Request body: `{"username": "admin", "password": "admin123"}`
- Response: Access token and refresh token

**POST /api/auth/refresh**
- Purpose: Get a new access token using refresh token
- Authentication: Refresh token required
- Response: New access token

**POST /api/auth/logout**
- Purpose: Invalidate current token
- Authentication: Access token required
- Effect: Token added to blacklist

**POST /api/auth/register**
- Purpose: Create a new user account
- Authentication: Admin role required
- Request body: `{"username": "newuser", "password": "pass123", "role": "operator"}`

### Blockchain Endpoints

**GET /api/health**
- Purpose: Check system status
- Authentication: None (public)
- Response: Blockchain height, mempool size, detector status

**GET /api/blockchain**
- Purpose: Retrieve blockchain with pagination
- Authentication: Any authenticated user
- Query params: `page`, `per_page`

**GET /api/blockchain/stats**
- Purpose: Get blockchain statistics
- Authentication: Any authenticated user
- Response: Transaction counts, block counts, alert statistics

**POST /api/mine**
- Purpose: Mine pending transactions into a new block
- Authentication: Admin or operator role
- Effect: Creates new block from mempool transactions

### Transaction Endpoints

**GET /api/transactions**
- Purpose: List transactions with filtering
- Authentication: Any authenticated user
- Query params: `page`, `per_page`, `type`, `sender`

**POST /api/transaction**
- Purpose: Create a new transaction
- Authentication: Any authenticated user
- Request body: Wallet name, transaction type, data
- Effect: Transaction analyzed and added to mempool or quarantine

**GET /api/transaction/{id}**
- Purpose: Get transaction details with Merkle proof
- Authentication: Any authenticated user

### Quarantine Endpoints

**GET /api/quarantine**
- Purpose: List quarantined transactions
- Authentication: Any authenticated user
- Query params: `status` (PENDING, CLEARED, REJECTED)

**PUT /api/quarantine/{id}/review**
- Purpose: Approve or reject quarantined transaction
- Authentication: Admin or operator role
- Request body: `{"action": "approve", "notes": "Verified as legitimate"}`

### Anomaly Detection Endpoints

**POST /api/anomaly/train**
- Purpose: Train the ML model on existing transactions
- Authentication: Admin or operator role
- Effect: Model trained and saved to disk

**GET /api/alerts**
- Purpose: List anomaly alerts
- Authentication: Any authenticated user
- Query params: `severity`, `resolved`

---

## WebSocket Events

### Connecting to the WebSocket

The WebSocket provides real-time updates without polling:

```javascript
// Connect to the alerts namespace
const socket = io("http://localhost:5000/alerts");

// Listen for connection confirmation
socket.on("connected", function(data) {
    console.log("Connected to real-time alerts");
});

// Listen for anomalies
socket.on("anomaly_detected", function(data) {
    showNotification("Anomaly detected: " + data.explanation);
});

// Listen for quarantine events
socket.on("transaction_quarantined", function(data) {
    showNotification("Transaction quarantined for review");
});
```

### Events sent by the server

| Event | When it's sent | What it contains |
|-------|----------------|------------------|
| `connected` | Client connects | Welcome message and timestamp |
| `anomaly_detected` | Anomaly found (not quarantined) | Alert ID, transaction ID, score, explanation |
| `transaction_quarantined` | Transaction blocked for review | Same as above, plus quarantine status |
| `block_mined` | New block created | Block index, transaction count |
| `quarantine_reviewed` | Admin approved/rejected | Transaction ID, action taken, reviewer |

---

## Data Persistence

### Where data is stored

| Data | Storage | Format | Purpose |
|------|---------|--------|---------|
| Blockchain | `blockchain_data/*.json` | JSON files | Immutable audit history |
| Quarantine | `blockchain_data/quarantine.json` | JSON | Pending suspicious transactions |
| Wallets | `wallets/*.json` | JSON | User key pairs |
| ML Model | `ml_model.pkl` | Python pickle | Trained anomaly detector |
| Users, Alerts | `audit_metadata.db` | SQLite | Fast queryable metadata |

### SQLite database tables

**users** - Stores user accounts
- username, password_hash, role, wallet_name, is_active, created_at, last_login

**alerts** - Stores anomaly alerts
- transaction_id, severity, anomaly_score, explanation, is_resolved, resolved_by

**transaction_index** - Fast transaction lookup
- transaction_id, block_index, sender_address, transaction_type, amount, timestamp

**revoked_tokens** - JWT blacklist
- jti (token ID), revoked_at

---

## Dashboard Features

### Statistics Overview

The dashboard header shows key metrics:
- **Blockchain Height**: How many blocks exist
- **Total Transactions**: Sum of all recorded events
- **Mempool Size**: Transactions waiting to be mined
- **Anomalies**: Total flagged transactions
- **Quarantine**: Pending human reviews
- **Detector**: Whether ML model is trained

### Available Actions

| Button | What it does | Who can use it |
|--------|--------------|----------------|
| Generate Demo Data | Creates test transactions | Any user |
| Mine Block | Processes mempool into new block | Admin, Operator |
| Train Detector | Trains ML on existing data | Admin, Operator |
| Export Audit | Downloads complete audit log | Admin only |
| Validate Chain | Checks blockchain integrity | Any user |

### Transaction Creation Form

Users can create transactions through the dashboard:
1. Select a wallet (sender identity)
2. Choose transaction type (LOGIN, TRANSFER, etc.)
3. Enter relevant data (amount for transfers)
4. Submit - transaction is signed, analyzed, and processed

### Data Tables

The dashboard displays:
- **Recent Transactions**: Latest activity across the system
- **Blockchain**: List of blocks with transaction counts
- **Quarantine**: Flagged transactions awaiting review
- **Alerts**: All detected anomalies with resolution status

### Real-Time Updates

The dashboard automatically updates when events occur:
- New transaction created
- Anomaly detected
- Block mined
- Quarantine item reviewed

Notifications appear as toast messages in the corner of the screen.

---

## Quick Start Guide

### Starting the application

```bash
# Navigate to project directory
cd c:\Users\tudor\PycharmProjects\Licenta

# Start the server
python main.py
```

The server starts at http://localhost:5000

### First-time setup

1. **Open the dashboard**: Navigate to http://localhost:5000
2. **Log in**: Use default credentials (admin / admin123)
3. **Generate data**: Click "Generate Demo Data" to create test transactions
4. **Train the detector**: Click "Train Detector" to enable anomaly detection
5. **Mine blocks**: Click "Mine Block" to commit transactions to the blockchain

### Creating your first transaction

1. Select a wallet from the dropdown
2. Choose "TRANSFER" as the type
3. Enter an amount (try 50000 for a large amount that might trigger anomaly detection)
4. Click "Create Transaction"
5. Check if it went to mempool (normal) or quarantine (suspicious)

### Reviewing quarantine

1. Go to the Quarantine tab
2. Click on a pending transaction
3. Review the anomaly explanation and feature values
4. Click "Approve" or "Reject"
5. Add notes explaining your decision
