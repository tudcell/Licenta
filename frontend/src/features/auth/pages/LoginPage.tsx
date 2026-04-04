import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { ErrorState } from "../../../components/states/ErrorState";
import { useAuthStore } from "../../../stores/authStore";
import "../../../styles/pages/login.css";

interface LocationState {
  from?: string;
}

function getSafeRedirectTarget(candidate: string | undefined): string {
  if (!candidate || !candidate.startsWith("/")) {
    return "/dashboard";
  }
  return candidate;
}

export function LoginPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const status = useAuthStore((state) => state.status);
  const error = useAuthStore((state) => state.error);
  const login = useAuthStore((state) => state.login);

  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [localError, setLocalError] = useState<string | null>(null);

  const loading = status === "authenticating";

  const from = getSafeRedirectTarget((location.state as LocationState | undefined)?.from);

  useEffect(() => {
    if (status === "authenticated") {
      navigate(from, { replace: true });
    }
  }, [from, navigate, status]);

  if (status === "authenticated") {
    return <Navigate to={from} replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLocalError(null);

    if (!username.trim() || !password) {
      setLocalError("Username and password are required.");
      return;
    }

    try {
      await login({ username: username.trim(), password });
    } catch {
      // Error is normalized in store and exposed through state.error.
    }
  };

  return (
    <div className="login-page">
      <h1>Blockchain Audit Console</h1>
      <p className="muted">Sign in with your API credentials to access the monitoring interface.</p>

      <form className="form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Username</span>
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        </label>

        <label className="field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </label>

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>

      {localError ? <ErrorState title="Validation error" message={localError} /> : null}
      {error ? <ErrorState message={error} /> : null}
    </div>
  );
}


