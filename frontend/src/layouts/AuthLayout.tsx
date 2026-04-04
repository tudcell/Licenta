import { Outlet } from "react-router-dom";

export function AuthLayout() {
  return (
    <main className="auth-layout">
      <section className="auth-card">
        <Outlet />
      </section>
    </main>
  );
}

