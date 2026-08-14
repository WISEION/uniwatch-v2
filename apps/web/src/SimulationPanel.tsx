import { Fragment, useState } from "react";
import type { CaseTrace, SimulationCasePayload, SimulationRun } from "./api/algoritmClient";
import { createAlgoritmClient } from "./api/algoritmClient";

// FR-ALG-05's simulation/backtest surface, plus the "почему принято"
// (why accepted) execution-trace view master plan §12.5 asks for --
// built here as an expandable per-case row (path + final_state) rather
// than a canvas overlay, since there is no canvas in this session's scope.

export interface SimulationPanelProps {
  client: ReturnType<typeof createAlgoritmClient>;
  versionId: number;
}

const SAMPLE_CASES = JSON.stringify(
  [{ case_id: "case-1", inputs: {} }],
  null,
  2,
);

export function SimulationPanel({ client, versionId }: SimulationPanelProps) {
  const [caseSetLabel, setCaseSetLabel] = useState("manual-run");
  const [caseSource, setCaseSource] = useState("synthetic_vendor");
  const [casesJson, setCasesJson] = useState(SAMPLE_CASES);
  const [run, setRun] = useState<SimulationRun | null>(null);
  const [traces, setTraces] = useState<CaseTrace[] | null>(null);
  const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    let cases: SimulationCasePayload[];
    try {
      cases = JSON.parse(casesJson) as SimulationCasePayload[];
    } catch {
      setError("Case set is not valid JSON");
      return;
    }
    try {
      const result = await client.simulate(versionId, caseSetLabel, caseSource, cases);
      setRun(result);
      const caseTraces = await client.getCaseTraces(result.id);
      setTraces(caseTraces.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <section aria-label="Simulation panel">
      <h3>Simulation</h3>
      {error !== null && <p role="alert">{error}</p>}
      <form onSubmit={handleRun}>
        <div>
          <label htmlFor="case_set_label">Case set label</label>
          <input id="case_set_label" value={caseSetLabel} onChange={(e) => setCaseSetLabel(e.target.value)} required />
        </div>
        <div>
          <label htmlFor="case_source">Case source</label>
          <select id="case_source" value={caseSource} onChange={(e) => setCaseSource(e.target.value)}>
            <option value="synthetic_vendor">synthetic_vendor</option>
            <option value="frozen_real_tender">frozen_real_tender</option>
            <option value="historical_outcome">historical_outcome</option>
          </select>
        </div>
        <div>
          <label htmlFor="cases_json">Cases (JSON array)</label>
          <textarea id="cases_json" value={casesJson} onChange={(e) => setCasesJson(e.target.value)} rows={8} cols={60} />
        </div>
        <button type="submit">Run simulation</button>
      </form>

      {run !== null && (
        <div>
          <h4>Run #{run.id} results</h4>
          <p>
            {run.completed_count} completed / {run.awaiting_human_count} awaiting human / {run.undetermined_count}{" "}
            undetermined (of {run.case_count})
          </p>
          <table>
            <caption>Terminal distribution</caption>
            <thead>
              <tr>
                <th scope="col">Terminal node</th>
                <th scope="col">Count</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(run.terminal_distribution).map(([terminal, count]) => (
                <tr key={terminal}>
                  <td>{terminal}</td>
                  <td>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {traces !== null && (
            <table>
              <caption>Per-case results -- expand a case for its execution trace ("why accepted")</caption>
              <thead>
                <tr>
                  <th scope="col">Case</th>
                  <th scope="col">Status</th>
                  <th scope="col">Terminal</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {traces.map((trace) => (
                  <Fragment key={trace.case_id}>
                    <tr>
                      <td>{trace.case_id}</td>
                      <td>{trace.status ?? "—"}</td>
                      <td>{trace.terminal_node_key ?? "—"}</td>
                      <td>
                        <button
                          type="button"
                          onClick={() => setExpandedCaseId(expandedCaseId === trace.case_id ? null : trace.case_id)}
                        >
                          {expandedCaseId === trace.case_id ? "Hide trace" : "Show trace"}
                        </button>
                      </td>
                    </tr>
                    {expandedCaseId === trace.case_id && (
                      <tr>
                        <td colSpan={4}>
                          <p>Path: {(trace.path ?? []).join(" → ")}</p>
                          <p>Reason codes: {(trace.reason_codes ?? []).join(", ") || "—"}</p>
                          <pre>{JSON.stringify(trace.final_state ?? {}, null, 2)}</pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}
