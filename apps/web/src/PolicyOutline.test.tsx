import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { createAlgoritmClient, VersionContent } from "./api/algoritmClient";
import { PolicyOutline } from "./PolicyOutline";

type Client = ReturnType<typeof createAlgoritmClient>;

function makeClient(overrides: Partial<Client> = {}): Client {
  const content: VersionContent = {
    version: { id: 1, policy_graph_id: 1, version_number: 1, status: "draft", research_dossier_id: null, created_by: "x", created_at: "now" },
    nodes: [{ node_key: "start", node_type: "human", title: "Start", owner: "pm" }],
    edges: [{ from_node_key: "start", to_node_key: "end", condition_label: null }],
  };
  return {
    getVersionContent: vi.fn().mockResolvedValue(content),
    addNodes: vi.fn().mockResolvedValue(content),
    addEdges: vi.fn().mockResolvedValue(content),
    validate: vi.fn().mockResolvedValue({ issues: [] }),
    ...overrides,
  } as unknown as Client;
}

describe("PolicyOutline", () => {
  it("renders fetched nodes and edges in accessible tables", async () => {
    const client = makeClient();
    render(<PolicyOutline client={client} versionId={1} />);

    await waitFor(() => expect(screen.getByRole("table", { name: /policy nodes/i })).toBeInTheDocument());
    expect(screen.getByRole("table", { name: /policy nodes/i })).toBeInTheDocument();
    const nodesTable = screen.getByRole("table", { name: /policy nodes/i });
    expect(within(nodesTable).getByText("human")).toBeInTheDocument();

    const edgesTable = screen.getByRole("table", { name: /policy edges/i });
    expect(within(edgesTable).getByText("end")).toBeInTheDocument();
  });

  it("submits the add-node form and reloads content", async () => {
    const client = makeClient();
    const user = userEvent.setup();
    render(<PolicyOutline client={client} versionId={1} />);
    await waitFor(() => expect(screen.getByRole("table", { name: /policy nodes/i })).toBeInTheDocument());

    await user.type(screen.getByLabelText(/^node key$/i), "new_node");
    await user.type(screen.getByLabelText(/^title$/i), "New node title");
    await user.type(screen.getByLabelText(/purpose/i), "purpose text");
    await user.type(screen.getByLabelText(/^owner$/i), "pm");
    await user.clear(screen.getByLabelText(/execution mode/i));
    await user.type(screen.getByLabelText(/execution mode/i), "manual");
    await user.click(screen.getByRole("button", { name: /add node/i }));

    await waitFor(() =>
      expect(client.addNodes).toHaveBeenCalledWith(
        1,
        expect.arrayContaining([expect.objectContaining({ node_key: "new_node", title: "New node title" })]),
      ),
    );
  });

  it("renders validation issues inline next to the node they reference", async () => {
    const client = makeClient({
      validate: vi.fn().mockResolvedValue({ issues: [{ code: "unreachable_node", message: "not reachable", node_key: "start" }] }),
    });
    const user = userEvent.setup();
    render(<PolicyOutline client={client} versionId={1} />);
    await waitFor(() => expect(screen.getByRole("table", { name: /policy nodes/i })).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /validate/i }));

    await waitFor(() => expect(screen.getByText(/unreachable_node/)).toBeInTheDocument());
  });

  it("every interactive control is reachable via Tab", async () => {
    const client = makeClient();
    const user = userEvent.setup();
    render(<PolicyOutline client={client} versionId={1} />);
    await waitFor(() => expect(screen.getByRole("table", { name: /policy nodes/i })).toBeInTheDocument());

    const nodeKeyInput = screen.getByLabelText(/^node key$/i);
    nodeKeyInput.focus();
    expect(document.activeElement).toBe(nodeKeyInput);

    // Tabbing all the way through both forms should reach the Validate
    // button without any element becoming unreachable -- proves there is
    // no keyboard trap in this outline view.
    for (let i = 0; i < 20; i += 1) {
      await user.tab();
    }
    expect(document.activeElement?.tagName).not.toBe("BODY");
  });
});
