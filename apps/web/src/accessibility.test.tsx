import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type AxeCore from "axe-core";
import { App } from "./App";
import type { createAlgoritmClient, VersionContent } from "./api/algoritmClient";
import { PolicyOutline } from "./PolicyOutline";
import { SimulationPanel } from "./SimulationPanel";
import { TransitionHistory } from "./TransitionHistory";

// Phase 5, task 5.E (FR-UX-02, WCAG 2.2 AA): an automated axe-core scan of
// every screen this session's outline/table UI actually renders. 5.D's own
// plan explicitly deferred this ("a real automated accessibility scanner
// pass is 5.E's job, this task proves keyboard reachability of what it
// built") -- PolicyOutline.test.tsx already proved Tab-reachability;
// this file is the structural WCAG evidence on top of that.

// vitest-axe 0.1.0's ambient .d.ts augmentation does not resolve against
// this project's vitest 3.x `expect` types (a real gap in that package's
// published types, not this test) -- the matcher itself is registered and
// works correctly at runtime (src/vitest.setup.ts), confirmed by the real
// violation this exact check caught and got fixed (SimulationPanel.tsx's
// empty <th>, see docs/decisions/OPEN-QUESTIONS.md task 5.E entry). This
// helper isolates the one-line type-only workaround instead of scattering
// `as unknown` casts through every test.
function expectNoViolations(results: AxeCore.AxeResults): void {
  (expect(results) as unknown as { toHaveNoViolations(): void }).toHaveNoViolations();
}

type Client = ReturnType<typeof createAlgoritmClient>;

const CONTENT: VersionContent = {
  version: {
    id: 1,
    policy_graph_id: 1,
    version_number: 1,
    status: "draft",
    research_dossier_id: null,
    created_by: "pm",
    created_at: "now",
  },
  nodes: [{ node_key: "start", node_type: "human", title: "Start", owner: "pm" }],
  edges: [{ from_node_key: "start", to_node_key: "end", condition_label: null }],
};

describe("accessibility (axe)", () => {
  it("App's connection form has no automatically-detectable violations", async () => {
    const { container } = render(<App />);
    expectNoViolations(await axe(container));
  });

  it("PolicyOutline has no automatically-detectable violations once content and validation issues are shown", async () => {
    const client = {
      getVersionContent: vi.fn().mockResolvedValue(CONTENT),
      validate: vi.fn().mockResolvedValue({ issues: [{ code: "unreachable_node", message: "not reachable", node_key: "start" }] }),
    } as unknown as Client;
    const user = userEvent.setup();
    const { container } = render(<PolicyOutline client={client} versionId={1} />);
    await waitFor(() => expect(screen.getByRole("table", { name: /policy nodes/i })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /validate/i }));
    await waitFor(() => expect(screen.getByText(/unreachable_node/)).toBeInTheDocument());

    expectNoViolations(await axe(container));
  });

  it("SimulationPanel has no automatically-detectable violations with a run's results and an expanded trace shown", async () => {
    const client = {
      simulate: vi.fn().mockResolvedValue({
        id: 1,
        policy_version_id: 1,
        compared_against_version_id: null,
        case_set_label: "a11y-run",
        case_source: "synthetic_vendor",
        case_count: 1,
        completed_count: 1,
        awaiting_human_count: 0,
        undetermined_count: 0,
        terminal_distribution: { approved: 1 },
        reason_code_distribution: {},
        monetary_range: null,
        monetary_amount_uncurrencied_count: 0,
        run_by: "pm",
        run_at: "now",
        notes: null,
      }),
      getCaseTraces: vi.fn().mockResolvedValue({
        items: [{ kind: "trace", case_id: "case-1", status: "completed", path: ["start", "approved"], terminal_node_key: "approved", reason_codes: [], final_state: {} }],
      }),
    } as unknown as Client;
    const user = userEvent.setup();
    const { container } = render(<SimulationPanel client={client} versionId={1} />);
    await user.click(screen.getByRole("button", { name: /run simulation/i }));
    await waitFor(() => expect(screen.getByText(/run #1 results/i)).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /show trace/i }));

    expectNoViolations(await axe(container));
  });

  it("TransitionHistory has no automatically-detectable violations once the log is loaded", async () => {
    const client = {
      listTransitions: vi.fn().mockResolvedValue({
        items: [
          { id: 1, policy_version_id: 1, from_status: "risk_review", to_status: "approved", changed_by: "pm", changed_at: "now", reason: null },
        ],
      }),
    } as unknown as Client;
    const { container } = render(<TransitionHistory client={client} versionId={1} />);
    await waitFor(() => expect(screen.getByText("approved")).toBeInTheDocument());

    expectNoViolations(await axe(container));
  });
});
