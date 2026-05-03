import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  ArrowRightLeft,
  Bell,
  Blocks,
  LayoutDashboard,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import type { ComponentType } from "react";

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
  icon: ComponentType<{ className?: string }>;
}

const navigationItems: NavigationItem[] = [
  { path: "/dashboard", label: "Dashboard", roles: ["admin", "operator", "viewer"], icon: LayoutDashboard },
  { path: "/transactions", label: "Transactions", roles: ["admin", "operator", "viewer"], icon: ArrowRightLeft },
  { path: "/blockchain", label: "Blockchain", roles: ["admin", "operator", "viewer"], icon: Blocks },
  { path: "/alerts", label: "Alerts", roles: ["admin", "operator", "viewer"], icon: Bell },
  { path: "/wallets", label: "Wallets", roles: ["admin", "operator", "viewer"], icon: Wallet },
  { path: "/audit", label: "Audit", roles: ["admin", "operator"], icon: ShieldCheck },
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
    <div className={cn("grid min-h-screen bg-background transition-[grid-template-columns] duration-300 ease-out", sidebarOpen ? "md:grid-cols-[236px_minmax(0,1fr)]" : "md:grid-cols-1")}>
      <aside
        className={cn(
          "border-r border-border bg-card/70 transition-all duration-300 ease-out md:sticky md:top-0 md:h-screen",
          sidebarOpen ? "flex flex-col gap-4 p-3 opacity-100" : "hidden opacity-0",
        )}
      >
        <Link to="/dashboard" className="rounded-md border border-border bg-background px-3 py-2.5">
          <p className="text-sm font-semibold tracking-tight">Audit Console</p>
          <p className="text-xs text-muted-foreground">Blockchain monitoring</p>
        </Link>
        <nav className="grid gap-1">
          {visibleLinks.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  "flex h-9 items-center gap-2 rounded-md border border-transparent px-2.5 text-sm text-muted-foreground",
                  isActive
                    ? "border-border bg-background text-foreground"
                    : "hover:bg-muted/70 hover:text-foreground",
                )
              }
            >
              <item.icon className="h-4 w-4" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-4 border-b border-border bg-background/95 px-4 py-2.5 md:px-6">
          <Button type="button" variant="ghost" size="icon" onClick={toggleSidebar} aria-label={sidebarOpen ? "Hide menu" : "Show menu"}>
            {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
          </Button>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">{user?.username}</span>
            <Badge variant="outline" className="px-2 uppercase">
              {user?.role}
            </Badge>
            <Button type="button" variant="ghost" size="sm" onClick={onLogout} className="gap-1.5">
              <LogOut className="h-3.5 w-3.5" />
              Logout
            </Button>
          </div>
        </header>

        <section className="page-enter p-4 md:p-6">
          <Outlet />
        </section>
      </div>
    </div>
  );
}

