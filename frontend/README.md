# Blockchain Audit Frontend

React + TypeScript + Vite frontend for the Flask blockchain audit backend in this repository.

## Requirements

- Node.js 20+
- npm
- Backend running at `http://127.0.0.1:5000`

## Environment

Create `frontend/.env` (or copy `.env.example`):

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:5000
VITE_SOCKET_URL=http://127.0.0.1:5000
```

## Run Locally

### 1) Frontend dev server

```powershell
Set-Location "C:\Users\tudor\PycharmProjects\licenta_ml_fixed\frontend"
npm install
npm run dev
```

Open `http://localhost:5173`.

### 2) Build frontend

```powershell
Set-Location "C:\Users\tudor\PycharmProjects\licenta_ml_fixed\frontend"
npm run build
```

The backend can serve built assets from `frontend/dist`.

## Quality Checks

```powershell
Set-Location "C:\Users\tudor\PycharmProjects\licenta_ml_fixed\frontend"
npm run lint
npm run typecheck
npm run build
```

## Auth and Roles

- JWT login: `POST /api/auth/login`
- Refresh flow: Axios interceptor calls `POST /api/auth/refresh`
- Logout: `POST /api/auth/logout`
- Roles used in UI and guards: `admin`, `operator`, `viewer`
- Protected routing is handled via `RequireAuth` and `RequireRole`

## Frontend Route Map

- `/login`
- `/dashboard`
- `/transactions`
- `/transactions/:id`
- `/blockchain`
- `/blockchain/:index`
- `/alerts`
- `/wallets`
- `/audit` (admin/operator only)

## API Mapping (service modules)

- `src/services/authService.ts`
  - `POST /api/auth/login`
  - `POST /api/auth/refresh`
  - `POST /api/auth/logout`

- `src/services/blockchainService.ts`
  - `GET /api/health`
  - `GET /api/blockchain`
  - `GET /api/blockchain/stats`
  - `GET /api/blockchain/validate`
  - `GET /api/block/:index`
  - `POST /api/mine`
  - `GET /api/mempool`

- `src/services/transactionsService.ts`
  - `GET /api/transactions`
  - `GET /api/transaction/:id`
  - `POST /api/transaction`
  - `GET /api/transaction/analyze/:id`

- `src/services/alertsService.ts`
  - `GET /api/alerts`
  - `PUT /api/alerts/:id/resolve`

- `src/services/walletsService.ts`
  - `GET /api/wallets`
  - `POST /api/wallet`
  - `GET /api/wallet/:name`

- `src/services/auditService.ts`
  - `GET /api/audit/integrity`
  - `GET /api/audit/export`
  - `GET /api/audit/backups`
  - `POST /api/audit/backup`
  - `POST /api/audit/restore`
  - `GET /api/audit/backups/:snapshotName/download`

- `src/services/anomalyService.ts`
  - `GET /api/anomaly/stats`
  - `POST /api/anomaly/train`
  - `POST /api/demo/generate`

## Realtime

- Socket.IO namespace: `/alerts`
- Hook: `src/hooks/useAlertsSocket.ts`
- Refresh triggers used: `anomaly_detected`, `block_mined`

## Notes

- API error shape is normalized in `src/services/http.ts` using backend `api_error` envelope.
- Listing pages expect pagination metadata (`page`, `per_page`, `total`, `total_pages`, `has_next`, `has_prev`).

