import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { createAlgoritmClient } from "./api/algoritmClient";
import { TransitionHistory } from "./TransitionHistory";

type Client = ReturnType<typeof createAlgoritmClient>;

describe("TransitionHistory", () => {
  it("renders the append-only transition log", async () => {
    const client = {
      listTransitions: vi.fn().mockResolvedValue({
        items: [
          {
            id: 1,
            policy_version_id: 1,
            from_status: "risk_review",
            to_status: "approved",
            changed_by: "pm-1",
            changed_at: "2026-08-14T00:00:00Z",
            reason: null,
          },
        ],
      }),
    } as unknown as Client;

    render(<TransitionHistory client={client} versionId={1} />);

    await waitFor(() => expect(screen.getByText("approved")).toBeInTheDocument());
    expect(screen.getByText("risk_review")).toBeInTheDocument();
    expect(screen.getByText("pm-1")).toBeInTheDocument();
  });
});
