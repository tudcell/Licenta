import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { cn } from "../lib/utils";
import { useAppStore } from "../stores/appStore";
import { useAuthStore } from "../stores/authStore";
import type { UserRole } from "../types";

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
    <div className={cn("grid min-h-screen transition-[grid-template-columns] duration-300 ease-out", sidebarOpen ? "md:grid-cols-[272px_1fr]" : "md:grid-cols-1")}>
      <aside
        className={cn(
          "border-border/70 bg-card/85 backdrop-blur-xl transition-all duration-300 ease-out md:sticky md:top-0 md:h-screen",
          sidebarOpen ? "flex flex-col gap-6 border-r px-4 py-5 opacity-100" : "hidden opacity-0",
        )}
      >
        <Link to="/dashboard" className="rounded-lg border border-border/60 bg-background/50 px-4 py-3">
          <p className="text-lg font-semibold tracking-tight">Audit Console</p>
          <p className="text-xs text-muted-foreground">Blockchain monitoring</p>
        </Link>
        <nav className="grid gap-1.5">
          {visibleLinks.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  "rounded-lg border px-3 py-2.5 text-sm font-medium",
                  isActive
                    ? "border-primary/40 bg-primary/15 text-foreground shadow-[inset_0_1px_0_hsl(var(--primary)/0.3)]"
                    : "border-transparent text-muted-foreground hover:border-border/70 hover:bg-muted/45 hover:text-foreground",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-4 border-b border-border/70 bg-background/85 px-4 py-3 backdrop-blur-xl md:px-6">
          <Button type="button" variant="outline" onClick={toggleSidebar} className="min-w-[112px]">
            {sidebarOpen ? "Hide menu" : "Show menu"}
          </Button>
          <div className="flex items-center gap-2 rounded-full border border-border/70 bg-card/75 px-2.5 py-1.5">
            <span className="px-1 text-sm text-muted-foreground">{user?.username}</span>
            <Badge variant="outline" className="rounded-full border-border/70 bg-muted/40 uppercase">
              {user?.role}
            </Badge>
            <Button type="button" variant="destructive" size="sm" onClick={onLogout}>
              Logout
            </Button>
          </div>
        </header>

        <section className="page-enter p-4 md:p-6 lg:p-8">
          <Outlet />
        </section>
      </div>
    </div>
  );
}

