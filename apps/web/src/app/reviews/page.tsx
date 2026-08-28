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
import { AlgorithmQueuePanel } from "@/components/AlgorithmQueuePanel";
import { EmptyState } from "@/components/EmptyState";
import { ReviewQueuePanel } from "@/components/ReviewQueuePanel";
import { CAPABILITIES, can, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
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
  const { t } = useTranslation();
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
            {incoming ? t("reviews.from") : t("reviews.sentTo")}{" "}
            {other?.nickname ?? "—"} ·{" "}
            {request.stage === "spec" ? t("reviews.specReview") : t("reviews.resultReview")} ·{" "}
            {when(request.created_at)}
          </div>
        </div>
        <span className={statusBadge(request.status)} title={request.status}>
          {t(`reviews.status.${request.status}`)}
        </span>
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
            placeholder={
              incoming
                ? t("reviews.commentPlaceholder", { optional: t("common.optional") })
                : t("reviews.commentRequired")
            }
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
                  {t("reviews.approve")}
                </button>
                <button disabled={busy} onClick={() => onAnswer(request.id, "reject", comment)}>
                  {t("reviews.reject")}
                </button>
              </>
            ) : (
              <button disabled={busy} onClick={() => onCancel(request.id)}>
                {t("reviews.cancelRequest")}
              </button>
            )}
            <button
              disabled={busy || !comment.trim()}
              onClick={() => {
                onComment(request.id, comment);
                setComment("");
              }}
            >
              {t("reviews.addComment")}
            </button>
            <Link href={`/benchmarks/${request.benchmark_id}`} className="button-link">
              {t("reviews.openBenchmark")}
            </Link>
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 10 }}>
          <Link href={`/benchmarks/${request.benchmark_id}`} className="button-link">
            {t("reviews.openBenchmark")}
          </Link>
        </div>
      )}
    </div>
  );
}

export default function ReviewsPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const session = useSession();
  const [incoming, setIncoming] = useState<ReviewRequestView[]>([]);
  const [outgoing, setOutgoing] = useState<ReviewRequestView[]>([]);
  /* **Four tabs, two of them the old page.** Runs and algorithms are the
     work this deployment actually generates; inbox and sent are the
     benchmark-era request lane, still live and still answerable, kept under
     their own headings rather than merged in. Merging them would put two
     different kinds of request — one that carries a claim and one that does
     not — into one list under one set of buttons. */
  const [tab, setTab] = useState<"runs" | "algorithms" | "inbox" | "sent">("runs");
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

  if (!session) return <p className="muted">{t("common.loading")}</p>;

  const shown = tab === "inbox" ? incoming : outgoing;
  const reviewsAlgorithms = can(session.user, CAPABILITIES.algorithmPublish);
  const pendingCount = incoming.filter((view) => view.request.status === "pending").length;

  return (
    <>
      <div className="page-head">
        <div>
          <h2>{t("reviews.title")}</h2>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}

      <div className="toolbar" role="tablist">
        <button
          role="tab"
          aria-selected={tab === "runs"}
          className={tab === "runs" ? "primary" : ""}
          onClick={() => setTab("runs")}
        >
          {t("queue.tab.runs")}
        </button>
        {/* Offered only to somebody who could act on it. An engineer reading
            a list of algorithms waiting for a reviewer learns only that they
            cannot help. */}
        {reviewsAlgorithms ? (
          <button
            role="tab"
            aria-selected={tab === "algorithms"}
            className={tab === "algorithms" ? "primary" : ""}
            onClick={() => setTab("algorithms")}
          >
            {t("queue.tab.algorithms")}
          </button>
        ) : null}
        <button
          role="tab"
          aria-selected={tab === "inbox"}
          className={tab === "inbox" ? "primary" : ""}
          onClick={() => setTab("inbox")}
        >
          {t("reviews.inbox")}
          {pendingCount ? ` (${pendingCount})` : ""}
        </button>
        <button
          role="tab"
          aria-selected={tab === "sent"}
          className={tab === "sent" ? "primary" : ""}
          onClick={() => setTab("sent")}
        >
          {t("reviews.sent")}
        </button>
      </div>

      {tab === "runs" ? <ReviewQueuePanel /> : null}
      {tab === "algorithms" && reviewsAlgorithms ? <AlgorithmQueuePanel /> : null}

      {/* The legacy lane. Answering one of these is the same call the
          benchmark page makes, so it stays exactly as it was. */}
      {tab === "inbox" || tab === "sent" ? (
        <>
        {shown.length === 0 ? (
          <div className="panel">
            <EmptyState
              icon="inbox"
              title={tab === "inbox" ? t("reviews.empty.inbox.title") : t("reviews.empty.sent.title")}
              body={tab === "inbox" ? t("reviews.empty.inbox.body") : t("reviews.empty.sent.body")}
              actionHref={tab === "inbox" ? undefined : "/decisions"}
              actionLabel={tab === "inbox" ? undefined : t("nav.benchmarks")}
            />
          </div>
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
      ) : null}
    </>
  );
}
