import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FeedbackForm } from "./FeedbackForm";

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

describe("FeedbackForm", () => {
  it("submits a message and shows the recorded confirmation", async () => {
    mockFetchOnce(201, {
      id: 42,
      submitted_by: "alice",
      category: "bug",
      message: "it broke",
      status: "open",
      resolution_note: null,
      resolved_by: null,
      submitted_at: "2026-08-18T00:00:00+00:00",
      resolved_at: null,
    });
    const user = userEvent.setup();
    render(<FeedbackForm baseUrl="http://test" />);

    await user.type(screen.getByLabelText(/message/i), "it broke");
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/feedback #42 recorded/i));
  });

  it("clears the message field after a successful submission", async () => {
    mockFetchOnce(201, {
      id: 1,
      submitted_by: "alice",
      category: "bug",
      message: "x",
      status: "open",
      resolution_note: null,
      resolved_by: null,
      submitted_at: "2026-08-18T00:00:00+00:00",
      resolved_at: null,
    });
    const user = userEvent.setup();
    render(<FeedbackForm baseUrl="http://test" />);

    const messageBox = screen.getByLabelText(/message/i);
    await user.type(messageBox, "x");
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(messageBox).toHaveValue(""));
  });

  it("shows a specific message when the account lacks permission (403 forbidden)", async () => {
    mockFetchOnce(403, {
      error: { code: "forbidden", message: "missing permission: platform.feedback.submit", correlation_id: null, details: null },
    });
    const user = userEvent.setup();
    render(<FeedbackForm baseUrl="http://test" />);

    await user.type(screen.getByLabelText(/message/i), "hello");
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/cannot submit feedback/i));
  });

  it("disables the submit button until a message is entered", async () => {
    render(<FeedbackForm baseUrl="http://test" />);
    expect(screen.getByRole("button", { name: /submit/i })).toBeDisabled();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/message/i), "a");
    expect(screen.getByRole("button", { name: /submit/i })).toBeEnabled();
  });
});
