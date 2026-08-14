import { useEffect, useState } from "react";
import type { PolicyEdgeDto, PolicyNodeDto, ValidationIssue, VersionContent } from "./api/algoritmClient";
import { createAlgoritmClient } from "./api/algoritmClient";

// The accessible outline/table alternative to a canvas editor
// (FR-ALG-07, master plan §12.5). Every interactive element here is a
// native <table>/<form>/<button>/<label> -- no custom drag targets, no
// keyboard trap -- which is what makes this reachable via Tab/Enter/Space
// without extra ARIA choreography. This is a complete, real form of the
// builder, not a degraded stand-in for a canvas the master plan also
// names but this session did not build (recorded in
// docs/decisions/OPEN-QUESTIONS.md, task 5.D close-out).

export interface PolicyOutlineProps {
  client: ReturnType<typeof createAlgoritmClient>;
  versionId: number;
}

interface NodeFormState {
  node_key: string;
  node_type: string;
  title: string;
  purpose: string;
  owner: string;
  execution_mode: string;
}

const EMPTY_NODE_FORM: NodeFormState = {
  node_key: "",
  node_type: "human",
  title: "",
  purpose: "",
  owner: "",
  execution_mode: "manual",
};

interface EdgeFormState {
  from_node_key: string;
  to_node_key: string;
  condition_label: string;
}

const EMPTY_EDGE_FORM: EdgeFormState = { from_node_key: "", to_node_key: "", condition_label: "" };

export function PolicyOutline({ client, versionId }: PolicyOutlineProps) {
  const [content, setContent] = useState<VersionContent | null>(null);
  const [issues, setIssues] = useState<ValidationIssue[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nodeForm, setNodeForm] = useState<NodeFormState>(EMPTY_NODE_FORM);
  const [edgeForm, setEdgeForm] = useState<EdgeFormState>(EMPTY_EDGE_FORM);

  async function reload() {
    try {
      setError(null);
      const loaded = await client.getVersionContent(versionId);
      setContent(loaded);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [versionId]);

  async function handleAddNode(event: React.FormEvent) {
    event.preventDefault();
    const payload: PolicyNodeDto = { ...nodeForm };
    try {
      setError(null);
      await client.addNodes(versionId, [payload]);
      setNodeForm(EMPTY_NODE_FORM);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleAddEdge(event: React.FormEvent) {
    event.preventDefault();
    const payload: PolicyEdgeDto = {
      from_node_key: edgeForm.from_node_key,
      to_node_key: edgeForm.to_node_key,
      condition_label: edgeForm.condition_label.trim() === "" ? null : edgeForm.condition_label,
    };
    try {
      setError(null);
      await client.addEdges(versionId, [payload]);
      setEdgeForm(EMPTY_EDGE_FORM);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleValidate() {
    try {
      setError(null);
      const result = await client.validate(versionId);
      setIssues(result.issues);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const issuesByNodeKey = new Map<string | null, ValidationIssue[]>();
  for (const issue of issues ?? []) {
    const key = issue.node_key ?? null;
    const existing = issuesByNodeKey.get(key) ?? [];
    existing.push(issue);
    issuesByNodeKey.set(key, existing);
  }

  return (
    <section aria-label="Policy graph outline">
      {error !== null && <p role="alert">{error}</p>}
      {content === null ? (
        <p>Loading…</p>
      ) : (
        <>
          <h2>Version {content.version.version_number}</h2>
          <p>
            Status: <strong>{content.version.status}</strong>
          </p>

          <h3>Nodes</h3>
          <table>
            <caption>Policy nodes for this version</caption>
            <thead>
              <tr>
                <th scope="col">Key</th>
                <th scope="col">Type</th>
                <th scope="col">Title</th>
                <th scope="col">Owner</th>
                <th scope="col">Validation issues</th>
              </tr>
            </thead>
            <tbody>
              {content.nodes.map((node) => {
                const nodeKey = String(node.node_key);
                const nodeIssues = issuesByNodeKey.get(nodeKey) ?? [];
                return (
                  <tr key={nodeKey}>
                    <td>{nodeKey}</td>
                    <td>{String(node.node_type)}</td>
                    <td>{String(node.title)}</td>
                    <td>{String(node.owner)}</td>
                    <td>
                      {nodeIssues.length === 0
                        ? "—"
                        : nodeIssues.map((issue, index) => (
                            <div key={index} role="alert">
                              {issue.code}: {issue.message}
                            </div>
                          ))}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <form onSubmit={handleAddNode} aria-label="Add node">
            <h4>Add node</h4>
            <div>
              <label htmlFor="node_key">Node key</label>
              <input
                id="node_key"
                value={nodeForm.node_key}
                onChange={(e) => setNodeForm({ ...nodeForm, node_key: e.target.value })}
                required
              />
            </div>
            <div>
              <label htmlFor="node_type">Node type</label>
              <select
                id="node_type"
                value={nodeForm.node_type}
                onChange={(e) => setNodeForm({ ...nodeForm, node_type: e.target.value })}
              >
                <option value="human">human</option>
                <option value="rule">rule</option>
                <option value="gate">gate</option>
                <option value="data_quality">data_quality</option>
              </select>
            </div>
            <div>
              <label htmlFor="node_title">Title</label>
              <input
                id="node_title"
                value={nodeForm.title}
                onChange={(e) => setNodeForm({ ...nodeForm, title: e.target.value })}
                required
              />
            </div>
            <div>
              <label htmlFor="node_purpose">Purpose</label>
              <input
                id="node_purpose"
                value={nodeForm.purpose}
                onChange={(e) => setNodeForm({ ...nodeForm, purpose: e.target.value })}
                required
              />
            </div>
            <div>
              <label htmlFor="node_owner">Owner</label>
              <input
                id="node_owner"
                value={nodeForm.owner}
                onChange={(e) => setNodeForm({ ...nodeForm, owner: e.target.value })}
                required
              />
            </div>
            <div>
              <label htmlFor="node_execution_mode">Execution mode</label>
              <input
                id="node_execution_mode"
                value={nodeForm.execution_mode}
                onChange={(e) => setNodeForm({ ...nodeForm, execution_mode: e.target.value })}
                required
              />
            </div>
            <button type="submit">Add node</button>
          </form>

          <h3>Edges</h3>
          <table>
            <caption>Policy edges for this version</caption>
            <thead>
              <tr>
                <th scope="col">From</th>
                <th scope="col">To</th>
                <th scope="col">Condition</th>
              </tr>
            </thead>
            <tbody>
              {content.edges.map((edge, index) => (
                <tr key={index}>
                  <td>{String(edge.from_node_key)}</td>
                  <td>{String(edge.to_node_key)}</td>
                  <td>{edge.condition_label === null || edge.condition_label === undefined ? "—" : String(edge.condition_label)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <form onSubmit={handleAddEdge} aria-label="Add edge">
            <h4>Add edge</h4>
            <div>
              <label htmlFor="edge_from">From node key</label>
              <input
                id="edge_from"
                value={edgeForm.from_node_key}
                onChange={(e) => setEdgeForm({ ...edgeForm, from_node_key: e.target.value })}
                required
              />
            </div>
            <div>
              <label htmlFor="edge_to">To node key</label>
              <input
                id="edge_to"
                value={edgeForm.to_node_key}
                onChange={(e) => setEdgeForm({ ...edgeForm, to_node_key: e.target.value })}
                required
              />
            </div>
            <div>
              <label htmlFor="edge_condition">Condition label (optional)</label>
              <input
                id="edge_condition"
                value={edgeForm.condition_label}
                onChange={(e) => setEdgeForm({ ...edgeForm, condition_label: e.target.value })}
              />
            </div>
            <button type="submit">Add edge</button>
          </form>

          <button type="button" onClick={handleValidate}>
            Validate
          </button>
          {issues !== null && issues.length === 0 && <p>No validation issues.</p>}
        </>
      )}
    </section>
  );
}
