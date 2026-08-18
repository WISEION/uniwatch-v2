import { useMemo, useState } from "react";
import { createAlgoritmClient } from "./api/algoritmClient";
import { createAuthClient, type LoginResult } from "./api/authClient";
import { downloadJson } from "./exportJson";
import { FeedbackForm } from "./FeedbackForm";
import { Login } from "./Login";
import { PolicyOutline } from "./PolicyOutline";
import { SimulationPanel } from "./SimulationPanel";
import { TransitionHistory } from "./TransitionHistory";

// АЛГОРИТМ outline/table builder (Phase 5, task 5.D). Canvas editor,
// version diff, and human-readable PDF/Markdown export are explicitly
// deferred -- see docs/decisions/OPEN-QUESTIONS.md's 2026-08-14 task 5.D
// entry. This is the outline/keyboard-accessible alternative form
// (FR-ALG-07), built as the complete UI this session, not a placeholder.
//
// Identity (Phase 6, task 6.A, D-IDP): a real login form gates access --
// the former free-text "Dev user" input is gone. algoritmClient's calls
// carry the session cookie the browser attaches automatically
// (credentials: "include"), not a client-supplied username header.

const DEFAULT_BASE_URL = "http://localhost:8001";

export function App() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [session, setSession] = useState<LoginResult | null>(null);
  const [versionIdInput, setVersionIdInput] = useState("");
  const [activeVersionId, setActiveVersionId] = useState<number | null>(null);

  const client = useMemo(() => createAlgoritmClient({ baseUrl }), [baseUrl]);

  function handleOpenVersion(event: React.FormEvent) {
    event.preventDefault();
    const parsed = Number.parseInt(versionIdInput, 10);
    if (!Number.isNaN(parsed)) {
      setActiveVersionId(parsed);
    }
  }

  async function handleExport() {
    if (activeVersionId === null) return;
    const [content, transitions] = await Promise.all([
      client.getVersionContent(activeVersionId),
      client.listTransitions(activeVersionId),
    ]);
    downloadJson(`policy-version-${activeVersionId}.json`, { ...content, transitions: transitions.items });
  }

  async function handleSignOut() {
    await createAuthClient({ baseUrl }).logout();
    setSession(null);
    setActiveVersionId(null);
  }

  if (session === null) {
    return (
      <main>
        <h1>АЛГОРИТМ — policy graph outline</h1>
        <div>
          <label htmlFor="base_url">API base URL</label>
          <input id="base_url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
        </div>
        <Login baseUrl={baseUrl} onAuthenticated={setSession} />
      </main>
    );
  }

  return (
    <main>
      <h1>АЛГОРИТМ — policy graph outline</h1>
      <p>
        Signed in as {session.username} ({session.role}){" "}
        <button type="button" onClick={handleSignOut}>
          Sign out
        </button>
      </p>

      <FeedbackForm baseUrl={baseUrl} />

      <form onSubmit={handleOpenVersion} aria-label="Open policy version">
        <div>
          <label htmlFor="version_id">Policy version id</label>
          <input id="version_id" value={versionIdInput} onChange={(e) => setVersionIdInput(e.target.value)} required />
        </div>
        <button type="submit">Open version</button>
      </form>

      {activeVersionId !== null && (
        <>
          <button type="button" onClick={handleExport}>
            Export version as JSON
          </button>
          <PolicyOutline client={client} versionId={activeVersionId} />
          <SimulationPanel client={client} versionId={activeVersionId} />
          <TransitionHistory client={client} versionId={activeVersionId} />
        </>
      )}
    </main>
  );
}
