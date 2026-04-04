import { Navigate, Outlet } from "react-router-dom";

import { useAuthStore } from "../../stores/authStore";
import type { UserRole } from "../../types/auth";

interface RequireRoleProps {
  roles: UserRole[];
}

export function RequireRole({ roles }: RequireRoleProps) {
  const hasAnyRole = useAuthStore((state) => state.hasAnyRole);

  if (!hasAnyRole(roles)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}

