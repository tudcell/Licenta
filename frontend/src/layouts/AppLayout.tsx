import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

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
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "" : "sidebar-collapsed"}`}>
        <Link to="/dashboard" className="brand-link">
          Audit Console
        </Link>
        <nav className="main-nav">
          {visibleLinks.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="main-content">
        <header className="topbar">
          <button type="button" className="btn btn-secondary" onClick={toggleSidebar}>
            {sidebarOpen ? "Hide menu" : "Show menu"}
          </button>
          <div className="topbar-user">
            <span>{user?.username}</span>
            <span className="role-pill">{user?.role}</span>
            <button type="button" className="btn btn-danger" onClick={onLogout}>
              Logout
            </button>
          </div>
        </header>

        <section className="page-content">
          <Outlet />
        </section>
      </div>
    </div>
  );
}

