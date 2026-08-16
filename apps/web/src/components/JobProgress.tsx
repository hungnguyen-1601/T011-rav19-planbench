"use client";

/** Background benchmark job: live progress and cooperative cancel.
 *
 * Polls while the job is queued or running and stops as soon as it
 * reaches a terminal state — a timer that keeps firing against a
 * finished job is just load with no new information.
 */

import { useCallback, useEffect, useState } from "react";
import { ErrorMessage } from "@/components/ErrorMessage";
import { StateBadge } from "@/components/StateBadge";
import { authFetch } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import type { JobState, JobStatus } from "@/lib/platformTypes";

const ACTIVE: JobState[] = ["queued", "running"];
const POLL_MS = 1000;

export interface JobProgressProps {
  benchmarkId: string;
  /** Called when the job leaves an active state, so the page can refresh. */
  onFinished?: (job: JobStatus) => void;
  canCancel?: boolean;
}

export function JobProgress({ benchmarkId, onFinished, canCancel = true }: JobProgressProps) {
  const { t } = useTranslation();
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const poll = useCallback(async () => {
    try {
      return await authFetch<JobStatus>(`/benchmarks/${benchmarkId}/job`);
    } catch {
      // 404 simply means no job was ever started for this benchmark.
      return null;
    }
  }, [benchmarkId]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const tick = async () => {
      const next = await poll();
      if (cancelled) return;
      setJob(next);
      if (next && ACTIVE.includes(next.state)) {
        timer = setTimeout(tick, POLL_MS);
      } else if (next) {
        onFinished?.(next);
      }
    };

    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [poll, onFinished]);

  if (!job) return null;

  const percent = job.total > 0 ? Math.round((job.progress / job.total) * 100) : 0;
  const active = ACTIVE.includes(job.state);

  return (
    <div className="panel">
      <h3>{t("job.title")}</h3>
      <div className="toolbar">
        <StateBadge state={job.state} />
        <span className="muted">
          {t("job.episodes", { done: job.progress, total: job.total })}
        </span>
        {job.message ? <span className="muted">— {job.message}</span> : null}
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label={t("job.progress")}
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`progress-fill${active ? " progress-active" : ""}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      {job.error ? <ErrorMessage error={job.error} /> : null}
      {error ? <ErrorMessage error={error} /> : null}
      {canCancel && active ? (
        <button
          type="button"
          className="secondary"
          onClick={async () => {
            try {
              setJob(
                await authFetch<JobStatus>(`/benchmarks/${benchmarkId}/job/cancel`, {
                  method: "POST",
                }),
              );
              setError(null);
            } catch (err) {
              setError(err instanceof Error ? err.message : String(err));
            }
          }}
        >
          {t("job.cancel")}
        </button>
      ) : null}
      {active ? (
        <p className="muted">{t("job.cancelHint")}</p>
      ) : null}
    </div>
  );
}
