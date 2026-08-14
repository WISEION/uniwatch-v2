// Thin fetch wrapper over apps/api_tender/routers/algoritm.py -- one
// function per route, no business logic here (the server is the source
// of truth for every check; this file only shapes the HTTP call).
//
// X-Dev-User is the same dev-only identity header
// apps/api_tender/deps.py::get_current_identity reads (D-IDP -- a real
// IdP integration -- is still an open decision per docs/CONTEXT.md); this
// client never invents a fallback identity.

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    correlation_id: string | null;
    details: unknown;
  };
}

export class AlgoritmApiError extends Error {
  code: string;
  status: number;
  details: unknown;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message);
    this.status = status;
    this.code = body.error.code;
    this.details = body.error.details;
  }
}

export interface PolicyVersion {
  id: number;
  policy_graph_id: number;
  version_number: number;
  status: string;
  research_dossier_id: number | null;
  created_by: string;
  created_at: string;
}

export interface PolicyNodeDto {
  node_key: string;
  node_type: string;
  title: string;
  purpose: string;
  owner: string;
  execution_mode: string;
  input_contract?: Record<string, string>;
  output_contract?: Record<string, string>;
  preconditions?: string[];
  evidence_requirements?: string[];
  reason_codes?: string[];
  test_cases?: Record<string, unknown>[];
  monitoring_metrics?: string[];
  timeout_seconds?: number | null;
  retry_policy?: Record<string, unknown> | null;
  fallback_node_key?: string | null;
  required_role?: string | null;
  financial_impact?: boolean;
  legal_impact?: boolean;
  model_or_policy_dependency?: string | null;
}

export interface PolicyEdgeDto {
  from_node_key: string;
  to_node_key: string;
  condition_label?: string | null;
}

export interface ValidationIssue {
  code: string;
  message: string;
  node_key: string | null;
}

export interface VersionContent {
  version: PolicyVersion;
  nodes: Record<string, unknown>[];
  edges: Record<string, unknown>[];
}

export interface TransitionRecord {
  id: number;
  policy_version_id: number;
  from_status: string;
  to_status: string;
  changed_by: string;
  changed_at: string;
  reason: string | null;
}

export interface SimulationCasePayload {
  case_id: string;
  inputs?: Record<string, unknown>;
  human_overrides?: Record<string, string>;
  monetary_amount?: string | null;
  monetary_currency?: string | null;
  actual_outcome_label?: string | null;
}

export interface SimulationRun {
  id: number;
  policy_version_id: number;
  compared_against_version_id: number | null;
  case_set_label: string;
  case_source: string;
  case_count: number;
  completed_count: number;
  awaiting_human_count: number;
  undetermined_count: number;
  terminal_distribution: Record<string, number>;
  reason_code_distribution: Record<string, number>;
  monetary_range: Record<string, unknown> | null;
  monetary_amount_uncurrencied_count: number;
  run_by: string;
  run_at: string;
  notes: string | null;
}

export interface CaseTrace {
  kind: string;
  case_id: string;
  status?: string;
  path?: string[];
  terminal_node_key?: string | null;
  reason_codes?: string[];
  undetermined_reason?: string | null;
  final_state?: Record<string, unknown>;
  actual_outcome_label?: string | null;
}

export interface AlgoritmClientOptions {
  baseUrl: string;
  username: string;
}

export function createAlgoritmClient({ baseUrl, username }: AlgoritmClientOptions) {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-Dev-User": username,
        ...(init?.headers ?? {}),
      },
    });
    if (!response.ok) {
      const body = (await response.json()) as ApiErrorBody;
      throw new AlgoritmApiError(response.status, body);
    }
    return (await response.json()) as T;
  }

  return {
    createPolicyGraph: (name: string, owner: string, description?: string) =>
      request<{ id: number; name: string; owner: string; description: string | null }>("/policy-graphs", {
        method: "POST",
        body: JSON.stringify({ name, owner, description: description ?? null }),
      }),

    listVersions: (graphId: number) => request<{ items: PolicyVersion[] }>(`/policy-graphs/${graphId}/versions`),

    createDraftVersion: (graphId: number, versionNumber: number) =>
      request<PolicyVersion>(`/policy-graphs/${graphId}/versions`, {
        method: "POST",
        body: JSON.stringify({ version_number: versionNumber }),
      }),

    getVersionContent: (versionId: number) => request<VersionContent>(`/policy-versions/${versionId}`),

    addNodes: (versionId: number, nodes: PolicyNodeDto[]) =>
      request<VersionContent>(`/policy-versions/${versionId}/nodes`, {
        method: "POST",
        body: JSON.stringify(nodes),
      }),

    addEdges: (versionId: number, edges: PolicyEdgeDto[]) =>
      request<VersionContent>(`/policy-versions/${versionId}/edges`, {
        method: "POST",
        body: JSON.stringify(edges),
      }),

    validate: (versionId: number) =>
      request<{ issues: ValidationIssue[] }>(`/policy-versions/${versionId}/validate`, { method: "POST" }),

    transition: (versionId: number, toStatus: string, reason?: string) =>
      request<PolicyVersion>(`/policy-versions/${versionId}/transition`, {
        method: "POST",
        body: JSON.stringify({ to_status: toStatus, reason: reason ?? null }),
      }),

    submitForApproval: (versionId: number, reason?: string) =>
      request<PolicyVersion>(`/policy-versions/${versionId}/submit-for-approval`, {
        method: "POST",
        body: JSON.stringify({ reason: reason ?? null }),
      }),

    activate: (versionId: number, reason?: string) =>
      request<PolicyVersion>(`/policy-versions/${versionId}/activate`, {
        method: "POST",
        body: JSON.stringify({ reason: reason ?? null }),
      }),

    killSwitch: (versionId: number, reason: string) =>
      request<PolicyVersion>(`/policy-versions/${versionId}/kill-switch`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),

    listTransitions: (versionId: number) =>
      request<{ items: TransitionRecord[] }>(`/policy-versions/${versionId}/transitions`),

    simulate: (versionId: number, caseSetLabel: string, caseSource: string, cases: SimulationCasePayload[]) =>
      request<SimulationRun>(`/policy-versions/${versionId}/simulate`, {
        method: "POST",
        body: JSON.stringify({ case_set_label: caseSetLabel, case_source: caseSource, cases }),
      }),

    getCaseTraces: (runId: number) => request<{ items: CaseTrace[] }>(`/simulation-runs/${runId}/case-traces`),
  };
}
