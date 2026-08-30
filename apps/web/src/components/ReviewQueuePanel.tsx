"use client";

/** What is waiting on a review, in the order somebody can act on it.
 *
 * **Four piles, and the server decides which is which.** A run held by
 * you, a run addressed to you, a run open to anybody, and a run you
 * sent. Which pile a given request lands in depends on who is asking —
 * the same row is `mine` to its holder and `pool` to everybody else —
 * so the split arrives from the API rather than being re-derived here.
 *
 * The `sent` pile is the engineer's half of the same table, and it is
 * deliberately not actionable: the only question an engineer has about a
 * run they sent is whether anybody picked it up, and offering them a
 * button here would be offering one the server refuses.
 *
 * **Claiming happens here; acknowledging and signing do not.** A queue
 * is a place to take work, and taking is one click that risks nothing —
 * a claim can be released. Saying you have read the evidence, and
 * signing off on it, are acts about a specific run's contents and belong
 * on that run's page, where the evidence is.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { CAPABILITIES, can, useSession } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import {
  cancelSubmission,
  claimReview,
  fetchReviewQueue,
  releaseReview,
  type QueueItem,
  type ReviewQueue,
} from "@/lib/decisions";

const EMPTY: ReviewQueue = { mine: [], directed: [], pool: [], sent: [] };

function when(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function Pile({
  titleKey,
  noteKey,
  items,
  children,
}: {
  titleKey: string;
  noteKey: string;
  items: QueueItem[];
  children: (item: QueueItem) => React.ReactNode;
}) {
  const { t } = useTranslation();
  // A pile with nothing in it is not drawn. Four empty headings tell a
  // reader four times that there is nothing to do.
  if (items.length === 0) return null;
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>
          {t(titleKey)} <span className="badge muted-badge">{items.length}</span>
        </h3>
      </div>
      <p className="muted small">{t(noteKey)}</p>
      <ul className="queue-list">
        {items.map((item) => (
          <li key={item.run_id}>
            <div className="row" style={{ justifyContent: "space-between", gap: 12 }}>
              <div>
                <Link href={`/decisions/${item.run_id}`}>
                  <code>{item.run_id.slice(0, 12)}</code>
                </Link>
                <div className="muted small">
                  {item.task_profile_id} · {when(item.created_at)}
                </div>
                {item.request_comment ? (
                  <div className="muted small">{item.request_comment}</div>
                ) : null}
              </div>
              <div className="row" style={{ gap: 8, alignItems: "center" }}>
                {children(item)}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ReviewQueuePanel() {
  const { t } = useTranslation();
  const session = useSession();
  const [queue, setQueue] = useState<ReviewQueue>(EMPTY);
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      setQueue(await fetchReviewQueue());
      setFailed(null);
    } catch (caught) {
      setFailed(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const act = async (runId: string, work: () => Promise<unknown>) => {
    setBusy(runId);
    setFailed(null);
    try {
      await work();
      await reload();
    } catch (caught) {
      setFailed(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  };

  const reviews = can(session?.user, CAPABILITIES.runReview);
  const total = queue.mine.length + queue.directed.length + queue.pool.length + queue.sent.length;

  if (loading) return <p className="muted">{t("common.loading")}</p>;

  return (
    <>
      {failed ? <div className="error-box">{failed}</div> : null}

      {total === 0 ? (
        <div className="panel">
          <EmptyState
            icon="inbox"
            title={t(reviews ? "queue.empty.reviewer.title" : "queue.empty.engineer.title")}
            body={t(reviews ? "queue.empty.reviewer.body" : "queue.empty.engineer.body")}
            actionHref="/decisions"
            actionLabel={t("nav.decisions")}
          />
        </div>
      ) : null}

      <Pile titleKey="queue.mine" noteKey="queue.mine.note" items={queue.mine}>
        {(item) => (
          <>
            {/* Whether the holder has opened it. A queue that showed only
                who holds a review would report a run as being dealt with
                while its holder has read nothing. */}
            <span className={`badge ${item.acknowledged ? "ok" : "warn"}`}>
              {t(item.acknowledged ? "queue.read" : "queue.unread")}
            </span>
            <Link href={`/decisions/${item.run_id}`} className="button primary">
              {t("queue.open")}
            </Link>
            <button
              type="button"
              disabled={busy === item.run_id}
              onClick={() => act(item.run_id, () => releaseReview(item.run_id))}
            >
              {t("queue.release")}
            </button>
          </>
        )}
      </Pile>

      <Pile titleKey="queue.directed" noteKey="queue.directed.note" items={queue.directed}>
        {(item) => (
          <button
            type="button"
            className="primary"
            disabled={busy === item.run_id}
            onClick={() => act(item.run_id, () => claimReview(item.run_id))}
          >
            {t("queue.claim")}
          </button>
        )}
      </Pile>

      <Pile titleKey="queue.pool" noteKey="queue.pool.note" items={queue.pool}>
        {(item) => (
          <button
            type="button"
            disabled={busy === item.run_id}
            onClick={() => act(item.run_id, () => claimReview(item.run_id))}
          >
            {t("queue.claim")}
          </button>
        )}
      </Pile>

      <Pile titleKey="queue.sent" noteKey="queue.sent.note" items={queue.sent}>
        {(item) => (
          <>
            <span className="badge">{t(`queue.state.${item.submission}`)}</span>
            {/* Withdrawing your own request is the one act an owner has
                here, and only while nobody has taken it: pulling work out
                from under somebody reading it is a different thing, and
                the server refuses it. */}
            {item.submission === "submitted" ? (
              <button
                type="button"
                disabled={busy === item.run_id}
                onClick={() => act(item.run_id, () => cancelSubmission(item.run_id))}
              >
                {t("queue.withdraw")}
              </button>
            ) : null}
          </>
        )}
      </Pile>
    </>
  );
}
