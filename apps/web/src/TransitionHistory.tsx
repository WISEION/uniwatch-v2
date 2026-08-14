import { useEffect, useState } from "react";
import type { TransitionRecord } from "./api/algoritmClient";
import { createAlgoritmClient } from "./api/algoritmClient";

// Approval history / rollback rehearsal log (master plan §12.5,
// FR-ALG-13/14) -- reads packages/algorithm/policy_store.py's
// append-only policy_version_transitions directly. Read-only by design:
// this history is never edited from the UI.

export interface TransitionHistoryProps {
  client: ReturnType<typeof createAlgoritmClient>;
  versionId: number;
}

export function TransitionHistory({ client, versionId }: TransitionHistoryProps) {
  const [transitions, setTransitions] = useState<TransitionRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    client
      .listTransitions(versionId)
      .then((result) => setTransitions(result.items))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [client, versionId]);

  return (
    <section aria-label="Transition history">
      <h3>Transition history</h3>
      {error !== null && <p role="alert">{error}</p>}
      {transitions !== null && (
        <table>
          <caption>Append-only lifecycle transitions for this version</caption>
          <thead>
            <tr>
              <th scope="col">From</th>
              <th scope="col">To</th>
              <th scope="col">Changed by</th>
              <th scope="col">Changed at</th>
              <th scope="col">Reason</th>
            </tr>
          </thead>
          <tbody>
            {transitions.map((t) => (
              <tr key={t.id}>
                <td>{t.from_status}</td>
                <td>{t.to_status}</td>
                <td>{t.changed_by}</td>
                <td>{t.changed_at}</td>
                <td>{t.reason ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
