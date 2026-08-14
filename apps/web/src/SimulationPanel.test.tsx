import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { createAlgoritmClient, SimulationRun } from "./api/algoritmClient";
import { SimulationPanel } from "./SimulationPanel";

type Client = ReturnType<typeof createAlgoritmClient>;

const RUN: SimulationRun = {
  id: 42,
  policy_version_id: 1,
  compared_against_version_id: null,
  case_set_label: "manual-run",
  case_source: "synthetic_vendor",
  case_count: 1,
  completed_count: 1,
  awaiting_human_count: 0,
  undetermined_count: 0,
  terminal_distribution: { approved: 1 },
  reason_code_distribution: { ok: 1 },
  monetary_range: null,
  monetary_amount_uncurrencied_count: 0,
  run_by: "pm",
  run_at: "now",
  notes: null,
};

function makeClient(): Client {
  return {
    simulate: vi.fn().mockResolvedValue(RUN),
    getCaseTraces: vi.fn().mockResolvedValue({
      items: [
        {
          kind: "trace",
          case_id: "case-1",
          status: "completed",
          path: ["start", "approved"],
          terminal_node_key: "approved",
          reason_codes: ["ok"],
          final_state: { amount: 100 },
        },
      ],
    }),
  } as unknown as Client;
}

describe("SimulationPanel", () => {
  it("runs a simulation and shows the terminal distribution", async () => {
    const client = makeClient();
    const user = userEvent.setup();
    render(<SimulationPanel client={client} versionId={1} />);

    await user.click(screen.getByRole("button", { name: /run simulation/i }));

    await waitFor(() => expect(screen.getByText(/run #42 results/i)).toBeInTheDocument());
    expect(client.simulate).toHaveBeenCalledWith(1, "manual-run", "synthetic_vendor", [{ case_id: "case-1", inputs: {} }]);
    expect(screen.getAllByText("approved").length).toBeGreaterThan(0);
  });

  it("expands a case row to show its execution trace (why accepted)", async () => {
    const client = makeClient();
    const user = userEvent.setup();
    render(<SimulationPanel client={client} versionId={1} />);

    await user.click(screen.getByRole("button", { name: /run simulation/i }));
    await waitFor(() => expect(screen.getByText(/run #42 results/i)).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /show trace/i }));
    expect(screen.getByText(/start → approved/)).toBeInTheDocument();
  });

  it("shows an error for invalid case JSON instead of calling the API", async () => {
    const client = makeClient();
    const user = userEvent.setup();
    render(<SimulationPanel client={client} versionId={1} />);

    const textarea = screen.getByLabelText(/cases \(json array\)/i);
    await user.clear(textarea);
    await user.type(textarea, "not json");
    await user.click(screen.getByRole("button", { name: /run simulation/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/not valid json/i);
    expect(client.simulate).not.toHaveBeenCalled();
  });
});
