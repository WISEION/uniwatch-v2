import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Login } from "./Login";

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Login", () => {
  it("submits valid credentials and calls onAuthenticated", async () => {
    mockFetchOnce(200, { username: "alice", role: "admin" });
    const onAuthenticated = vi.fn();
    const user = userEvent.setup();
    render(<Login baseUrl="http://test" onAuthenticated={onAuthenticated} />);

    await user.type(screen.getByLabelText(/username/i), "alice");
    await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith({ username: "alice", role: "admin" }));
  });

  it("shows an inline error for invalid credentials and does not call onAuthenticated", async () => {
    mockFetchOnce(401, { error: { code: "unauthenticated", message: "invalid username or password", correlation_id: null, details: null } });
    const onAuthenticated = vi.fn();
    const user = userEvent.setup();
    render(<Login baseUrl="http://test" onAuthenticated={onAuthenticated} />);

    await user.type(screen.getByLabelText(/username/i), "alice");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/invalid username or password/i));
    expect(onAuthenticated).not.toHaveBeenCalled();
  });

  it("shows a distinct message for a locked account", async () => {
    mockFetchOnce(401, { error: { code: "account_locked", message: "account is temporarily locked", correlation_id: null, details: null } });
    const user = userEvent.setup();
    render(<Login baseUrl="http://test" onAuthenticated={vi.fn()} />);

    await user.type(screen.getByLabelText(/username/i), "alice");
    await user.type(screen.getByLabelText(/password/i), "whatever");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/temporarily locked/i));
  });

  it("is fully reachable via keyboard alone (Tab through username, password, submit)", async () => {
    mockFetchOnce(200, { username: "alice", role: "admin" });
    const user = userEvent.setup();
    render(<Login baseUrl="http://test" onAuthenticated={vi.fn()} />);

    await user.tab();
    expect(screen.getByLabelText(/username/i)).toHaveFocus();
    await user.keyboard("alice");
    await user.tab();
    expect(screen.getByLabelText(/password/i)).toHaveFocus();
    await user.keyboard("correct horse battery staple");
    await user.tab();
    expect(screen.getByRole("button", { name: /sign in/i })).toHaveFocus();
  });
});
