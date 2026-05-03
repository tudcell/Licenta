import { Navigate, Outlet, useLocation } from "react-router-dom";

import { LoadingState } from "../../components/states/LoadingState";
import { useAuthStore } from "../../stores/authStore";

export function RequireAuth() {
  const location = useLocation();
  const status = useAuthStore((state) => state.status);
  const isBootstrapped = useAuthStore((state) => state.isBootstrapped);

  if (!isBootstrapped || status === "refreshing") {
    return <LoadingState message="Restoring your session..." />;
  }

  if (status !== "authenticated") {
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}${location.hash}` }} />;
  }

  return <Outlet />;
}

