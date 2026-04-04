import { createBrowserRouter, Navigate } from "react-router-dom";

import { AuthLayout } from "../layouts/AuthLayout";
import { AppLayout } from "../layouts/AppLayout";
import { LoginPage } from "../features/auth/pages/LoginPage";
import { DashboardPage } from "../features/dashboard/pages/DashboardPage";
import { TransactionsPage } from "../features/transactions/pages/TransactionsPage";
import { TransactionDetailPage } from "../features/transactions/pages/TransactionDetailPage";
import { BlockchainPage } from "../features/blockchain/pages/BlockchainPage";
import { BlockDetailPage } from "../features/blockchain/pages/BlockDetailPage";
import { AlertsPage } from "../features/alerts/pages/AlertsPage";
import { WalletsPage } from "../features/wallets/pages/WalletsPage";
import { AuditPage } from "../features/audit/pages/AuditPage";
import { NotFoundPage } from "../features/shared/pages/NotFoundPage";
import { RequireAuth } from "./guards/RequireAuth";
import { RequireRole } from "./guards/RequireRole";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Navigate to="/dashboard" replace />,
  },
  {
    path: "/login",
    element: <AuthLayout />,
    children: [{ index: true, element: <LoginPage /> }],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/dashboard", element: <DashboardPage /> },
          { path: "/transactions", element: <TransactionsPage /> },
          { path: "/transactions/:id", element: <TransactionDetailPage /> },
          { path: "/blockchain", element: <BlockchainPage /> },
          { path: "/blockchain/:index", element: <BlockDetailPage /> },
          { path: "/alerts", element: <AlertsPage /> },
          { path: "/wallets", element: <WalletsPage /> },
          {
            element: <RequireRole roles={["admin", "operator"]} />,
            children: [{ path: "/audit", element: <AuditPage /> }],
          },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);

