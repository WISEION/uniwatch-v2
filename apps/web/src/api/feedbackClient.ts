// Thin fetch wrapper over apps/api_tender/routers/pilot_feedback.py (Phase
// 6, task 6.D). credentials: "include" carries the session cookie set by
// authClient's login -- this client never handles the cookie value itself.

export interface FeedbackApiErrorBody {
  error: {
    code: string;
    message: string;
    correlation_id: string | null;
    details: unknown;
  };
}

export class FeedbackApiError extends Error {
  code: string;
  status: number;

  constructor(status: number, body: FeedbackApiErrorBody) {
    super(body.error.message);
    this.status = status;
    this.code = body.error.code;
  }
}

export type FeedbackCategory = "bug" | "question" | "feature_request" | "other";

export interface SubmittedFeedback {
  id: number;
  submitted_by: string;
  category: FeedbackCategory;
  message: string;
  status: "open" | "resolved";
  resolution_note: string | null;
  resolved_by: string | null;
  submitted_at: string;
  resolved_at: string | null;
}

export function createFeedbackClient({ baseUrl }: { baseUrl: string }) {
  async function submit(category: FeedbackCategory, message: string): Promise<SubmittedFeedback> {
    const response = await fetch(`${baseUrl}/pilot-feedback`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ category, message }),
    });
    if (!response.ok) {
      const body = (await response.json()) as FeedbackApiErrorBody;
      throw new FeedbackApiError(response.status, body);
    }
    return (await response.json()) as SubmittedFeedback;
  }

  return { submit };
}
