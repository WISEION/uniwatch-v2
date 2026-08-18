import { useState } from "react";
import { createFeedbackClient, FeedbackApiError, type FeedbackCategory } from "./api/feedbackClient";

// Phase 6, task 6.D's "feedback queue for pilot users" result. Native
// <form> only, same accessibility discipline as Login.tsx/PolicyOutline.tsx
// (FR-ALG-07/FR-UX-02) -- server errors shown inline, not a toast.

export interface FeedbackFormProps {
  baseUrl: string;
}

const CATEGORIES: readonly FeedbackCategory[] = ["bug", "question", "feature_request", "other"];

export function FeedbackForm({ baseUrl }: FeedbackFormProps) {
  const [category, setCategory] = useState<FeedbackCategory>("bug");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submittedId, setSubmittedId] = useState<number | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const client = createFeedbackClient({ baseUrl });
      const result = await client.submit(category, message);
      setSubmittedId(result.id);
      setMessage("");
    } catch (err) {
      if (err instanceof FeedbackApiError) {
        setError(err.code === "forbidden" ? "Your account cannot submit feedback." : err.message);
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Send feedback">
      <h2>Send feedback</h2>
      <div>
        <label htmlFor="feedback_category">Category</label>
        <select id="feedback_category" value={category} onChange={(e) => setCategory(e.target.value as FeedbackCategory)}>
          {CATEGORIES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="feedback_message">Message</label>
        <textarea id="feedback_message" value={message} onChange={(e) => setMessage(e.target.value)} required />
      </div>
      <button type="submit" disabled={submitting || message.trim() === ""}>
        Submit
      </button>
      {error !== null && <p role="alert">{error}</p>}
      {submittedId !== null && <p role="status">Thanks -- feedback #{submittedId} recorded.</p>}
    </form>
  );
}
