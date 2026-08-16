// Thin fetch wrapper over apps/api_tender/routers/auth.py (Phase 6, task
// 6.A, D-IDP). credentials: "include" is what makes the browser store and
// send the httpOnly session cookie POST /auth/login sets -- this client
// never reads or handles the cookie value itself.

export interface AuthErrorBody {
  error: {
    code: string;
    message: string;
    correlation_id: string | null;
    details: unknown;
  };
}

export class AuthApiError extends Error {
  code: string;
  status: number;

  constructor(status: number, body: AuthErrorBody) {
    super(body.error.message);
    this.status = status;
    this.code = body.error.code;
  }
}

export interface LoginResult {
  username: string;
  role: string;
}

export function createAuthClient({ baseUrl }: { baseUrl: string }) {
  async function login(username: string, password: string): Promise<LoginResult> {
    const response = await fetch(`${baseUrl}/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const body = (await response.json()) as AuthErrorBody;
      throw new AuthApiError(response.status, body);
    }
    return (await response.json()) as LoginResult;
  }

  async function logout(): Promise<void> {
    await fetch(`${baseUrl}/auth/logout`, { method: "POST", credentials: "include" });
  }

  return { login, logout };
}
