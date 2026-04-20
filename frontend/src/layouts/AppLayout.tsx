import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { cn } from "../lib/utils";
import { useAppStore } from "../stores/appStore";
import { useAuthStore } from "../stores/authStore";
import type { UserRole } from "../types/auth";

interface NavigationItem {
  path: string;
  label: string;
  roles: UserRole[];
}

const navigationItems: NavigationItem[] = [
  { path: "/dashboard", label: "Dashboard", roles: ["admin", "operator", "viewer"] },
  { path: "/transactions", label: "Transactions", roles: ["admin", "operator", "viewer"] },
  { path: "/blockchain", label: "Blockchain", roles: ["admin", "operator", "viewer"] },
  { path: "/alerts", label: "Alerts", roles: ["admin", "operator", "viewer"] },
  { path: "/wallets", label: "Wallets", roles: ["admin", "operator", "viewer"] },
  { path: "/audit", label: "Audit", roles: ["admin", "operator"] },
];

export function AppLayout() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const sidebarOpen = useAppStore((state) => state.sidebarOpen);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);

  const visibleLinks = navigationItems.filter((item) => user && item.roles.includes(user.role));

  const onLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="grid min-h-screen bg-muted/30 md:grid-cols-[260px_1fr]">
      <aside className={cn("flex flex-col gap-4 border-r bg-card p-4", sidebarOpen ? "" : "hidden")}>
        <Link to="/dashboard" className="text-lg font-bold tracking-tight">
          Audit Console
        </Link>
        <nav className="grid gap-1">
          {visibleLinks.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-h-screen flex-col">
        <header className="flex items-center justify-between gap-4 border-b bg-background px-4 py-3">
          <Button type="button" variant="outline" onClick={toggleSidebar}>
            {sidebarOpen ? "Hide menu" : "Show menu"}
          </Button>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">{user?.username}</span>
            <Badge variant="outline" className="uppercase">
              {user?.role}
            </Badge>
            <Button type="button" variant="destructive" onClick={onLogout}>
              Logout
            </Button>
          </div>
        </header>

        <section className="p-4 md:p-6">
          <Outlet />
        </section>
      </div>
    </div>
  );
}

