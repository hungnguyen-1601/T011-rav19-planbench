"use client";

/** Review Inbox: what other members have asked you to look at, and what
 *  you have asked of them.
 *
 * Approving here is the same call the benchmark page makes, and the
 * backend applies the same checks either way. Buttons appear only for
 * pending requests addressed to you, but that is convenience — a request
 * answered from a stale tab is refused server-side.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/auth";
import {
  answerReview,
  cancelReview,
  commentOnReview,
  fetchInbox,
  fetchSent,
  type ReviewRequestView,
} from "@/lib/reviews";

function statusBadge(status: string): string {
  if (status === "approved") return "badge ok";
  if (status === "rejected" || status === "cancelled") return "badge warn";
  return "badge";
}

function when(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function RequestCard({
  view,
  incoming,
  onAnswer,
  onComment,
  onCancel,
  busy,
}: {
  view: ReviewRequestView;
  incoming: boolean;
  onAnswer: (id: string, decision: "approve" | "reject", comment: string) => void;
  onComment: (id: string, comment: string) => void;
  onCancel: (id: string) => void;
  busy: boolean;
}) {
  const [comment, setComment] = useState("");
  const { request } = view;
  const pending = request.status === "pending";
  const other = incoming ? view.requested_by : view.reviewer;

  return (
    <div className="panel" style={{ marginBottom: 12 }}>
      <div className="row-between">
        <div>
          <strong>
            <Link href={`/benchmarks/${request.benchmark_id}`}>
              {view.benchmark_name || request.benchmark_id}
            </Link>
          </strong>
          <div className="muted" style={{ fontSize: 12 }}>
            {incoming ? "From" : "Sent to"} {other?.nickname ?? "an unknown member"} ·{" "}
            {request.stage === "spec" ? "Spec review" : "Result review"} ·{" "}
            {when(request.created_at)}
          </div>
        </div>
        <span className={statusBadge(request.status)}>{request.status}</span>
      </div>

      {request.request_comment ? (
        <p style={{ marginTop: 10 }}>“{request.request_comment}”</p>
      ) : null}
      {request.review_comment ? (
        <pre className="review-comment">{request.review_comment}</pre>
      ) : null}

      {pending ? (
        <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
          <input
            placeholder={incoming ? "Comment (optional)" : "Add a comment"}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
          />
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {incoming ? (
              <>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => onAnswer(request.id, "approve", comment)}
                >
                  Approve
                </button>
                <button disabled={busy} onClick={() => onAnswer(request.id, "reject", comment)}>
                  Reject
                </button>
              </>
            ) : (
              <button disabled={busy} onClick={() => onCancel(request.id)}>
                Cancel request
              </button>
            )}
            <button
              disabled={busy || !comment.trim()}
              onClick={() => {
                onComment(request.id, comment);
                setComment("");
              }}
            >
              Add comment
            </button>
            <Link href={`/benchmarks/${request.benchmark_id}`} className="button-link">
              Open benchmark
            </Link>
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 10 }}>
          <Link href={`/benchmarks/${request.benchmark_id}`} className="button-link">
            Open benchmark
          </Link>
        </div>
      )}
    </div>
  );
}

export default function ReviewsPage() {
  const router = useRouter();
  const session = useSession();
  const [incoming, setIncoming] = useState<ReviewRequestView[]>([]);
  const [outgoing, setOutgoing] = useState<ReviewRequestView[]>([]);
  const [tab, setTab] = useState<"inbox" | "sent">("inbox");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [inbox, sent] = await Promise.all([fetchInbox(), fetchSent()]);
      setIncoming(inbox.requests);
      setOutgoing(sent);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    if (session === null) {
      router.replace("/login");
      return;
    }
    void reload();
  }, [session, router, reload]);

  const act = useCallback(
    async (work: () => Promise<unknown>) => {
      setBusy(true);
      setError(null);
      try {
        await work();
        await reload();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [reload],
  );

  if (!session) return <p className="muted">Loading…</p>;

  const shown = tab === "inbox" ? incoming : outgoing;
  const pendingCount = incoming.filter((view) => view.request.status === "pending").length;

  return (
    <>
      <h2>Reviews</h2>
      {error ? <div className="error-box">{error}</div> : null}

      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <button className={tab === "inbox" ? "primary" : ""} onClick={() => setTab("inbox")}>
          Inbox{pendingCount ? ` (${pendingCount})` : ""}
        </button>
        <button className={tab === "sent" ? "primary" : ""} onClick={() => setTab("sent")}>
          Sent
        </button>
      </div>

      {shown.length === 0 ? (
        <p className="muted">
          {tab === "inbox"
            ? "Nobody has asked you to review anything."
            : "You have not asked anyone for a review. Open a benchmark and use “Send for review”."}
        </p>
      ) : (
        shown.map((view) => (
          <RequestCard
            key={view.request.id}
            view={view}
            incoming={tab === "inbox"}
            busy={busy}
            onAnswer={(id, decision, comment) =>
              act(() => answerReview(id, decision, comment))
            }
            onComment={(id, comment) => act(() => commentOnReview(id, comment))}
            onCancel={(id) => act(() => cancelReview(id))}
          />
        ))
      )}
    </>
  );
}
