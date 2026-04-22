import { Outlet } from "react-router-dom";

export function AuthLayout() {
  return (
    <main className="grid min-h-screen place-items-center bg-background p-6">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(800px_420px_at_20%_0%,hsl(var(--primary)/0.22),transparent_60%),radial-gradient(760px_380px_at_100%_100%,hsl(var(--accent)/0.25),transparent_62%)]" />
      <section className="w-full max-w-md">
        <Outlet />
      </section>
    </main>
  );
}

