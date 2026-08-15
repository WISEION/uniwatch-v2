import { useState } from "react";
import { AuthApiError, createAuthClient, type LoginResult } from "./api/authClient";

// Native <form> only -- no custom keyboard handling, same accessibility
// discipline PolicyOutline.tsx already applies (FR-ALG-07/FR-UX-02). The
// server's own error message is shown inline next to the form, not a
// generic toast, mirroring PolicyOutline.tsx's inline validation-issue
// display.

export interface LoginProps {
  baseUrl: string;
  onAuthenticated: (result: LoginResult) => void;
}

export function Login({ baseUrl, onAuthenticated }: LoginProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const client = createAuthClient({ baseUrl });
      const result = await client.login(username, password);
      onAuthenticated(result);
    } catch (err) {
      if (err instanceof AuthApiError) {
        setError(err.code === "account_locked" ? "Account is temporarily locked. Try again later." : err.message);
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Sign in">
      <h2>Sign in</h2>
      <div>
        <label htmlFor="login_username">Username</label>
        <input
          id="login_username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          required
        />
      </div>
      <div>
        <label htmlFor="login_password">Password</label>
        <input
          id="login_password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
      </div>
      <button type="submit" disabled={submitting}>
        Sign in
      </button>
      {error !== null && <p role="alert">{error}</p>}
    </form>
  );
}
