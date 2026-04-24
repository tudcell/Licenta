import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { ErrorState } from "../../../components/states/ErrorState";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { useAuthStore } from "../../../stores/authStore";

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
    <Card>
      <CardHeader className="space-y-3">
        <div className="inline-flex w-fit items-center rounded-md border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground">
          Secure access
        </div>
        <CardTitle className="text-lg font-semibold">Blockchain Audit Console</CardTitle>
        <CardDescription>Sign in with your API credentials to access the monitoring interface.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="grid gap-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </div>

          <Button type="submit" className="mt-1 w-full" disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </Button>
        </form>

        {localError ? <ErrorState title="Validation error" message={localError} /> : null}
        {error ? <ErrorState message={error} /> : null}
      </CardContent>
    </Card>
  );
}


