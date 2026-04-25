import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { ErrorState } from "../../../components/states/ErrorState";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { authService, normalizeApiError } from "../../../services";

export function RegisterPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSuccessMessage(null);

    const normalizedUsername = username.trim();
    if (!normalizedUsername || !password || !confirmPassword) {
      setError("Username, password, and confirm password are required.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await authService.registerViewer({ username: normalizedUsername, password });
      setSuccessMessage(`Viewer account '${result.user.username}' was created. You can now sign in.`);
      setPassword("");
      setConfirmPassword("");
    } catch (submitError) {
      setError(normalizeApiError(submitError).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="inline-flex w-fit items-center rounded-md border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground">
          Viewer onboarding
        </div>
        <CardTitle className="text-lg font-semibold">Create viewer account</CardTitle>
        <CardDescription>Register a read-only viewer user for role-based access demonstration.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="grid gap-2">
            <Label htmlFor="register-username">Username</Label>
            <Input
              id="register-username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              placeholder="viewer_demo"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="register-password">Password</Label>
            <Input
              id="register-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="register-confirm-password">Confirm password</Label>
            <Input
              id="register-confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
            />
          </div>

          <Button type="submit" className="mt-1 w-full" disabled={submitting}>
            {submitting ? "Creating account..." : "Create viewer account"}
          </Button>
        </form>

        {successMessage ? <p className="rounded-md border border-border bg-muted px-3 py-2 text-sm">{successMessage}</p> : null}
        {error ? <ErrorState message={error} /> : null}

        <div className="text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to="/login" className="text-primary hover:underline">
            Sign in
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}


