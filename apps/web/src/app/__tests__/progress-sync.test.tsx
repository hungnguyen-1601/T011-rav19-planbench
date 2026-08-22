/** The progress-sync panel, rendered.
 *
 * `renderToStaticMarkup` is what this suite has — no jsdom, no
 * testing-library (see `vitest.config.ts`), so a click cannot be
 * simulated. First render still answers the question that matters here:
 * can a reader be shown arc-length-aligned panels *without* the
 * sentence saying the two runs were there at different times.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ProgressSync } from "@/components/ProgressSync";
import type { ReplaySyncView, RunCandidate } from "@/lib/decisions";
import { initialPlayback } from "@/lib/playback";

const WARNING =
  "same place is not the same situation: the two runs reached this point at different times.";

function view(overrides: Partial<ReplaySyncView> = {}): ReplaySyncView {
  return {
    episode_context_id: "ctx",
    candidate_a: "winner",
    candidate_b: "runner_up",
    plan: {
      reference: { points: [], quality: "degraded_candidate_path" },
      rows: [
        { progress_m: 0, time_a: 0, time_b: 0, cross_track_a: 0, cross_track_b: 0 },
        { progress_m: 4, time_a: 4, time_b: 9, cross_track_a: 0, cross_track_b: 1.2 },
      ],
      backward_samples_a: 0,
      backward_samples_b: 0,
      warning: WARNING,
    },
    divergence: {
      sustained: {
        kind: "sustained_cross_track",
        progress_m: 3.25,
        time_a: 3.2,
        time_b: 7.1,
        separation_m: 0.6,
        event: null,
        side: null,
      },
      anchors: [
        {
          kind: "event",
          progress_m: 2,
          time_a: 2,
          time_b: 4,
          separation_m: null,
          event: "replan",
          side: "b",
        },
      ],
    },
    reference_source_candidate_id: "winner",
    ...overrides,
  };
}

const CANDIDATES: RunCandidate[] = [
  {
    candidate_id: "winner",
    stack_label: "A* + DWA",
    local_controller_config: "dwa",
    gates: {},
    cleared_gates: true,
    blocking_gates: [],
    n_distinct_episodes: 30,
    success_rate: 1,
    pooled_p99_latency_ms: 20,
  },
];

function render(node: React.ReactElement): string {
  return renderToStaticMarkup(node);
}

describe("progress-sync panel", () => {
  it("cannot show the rows without the caveat that qualifies them", () => {
    const html = render(
      <ProgressSync
        sync={{ state: "ready", view: view() }}
        scan={initialPlayback}
        span={4}
        onScan={() => {}}
        candidates={CANDIDATES}
      />,
    );

    expect(html).toContain("same place is not the same situation");
  });

  it("says the projection was degraded and whose path was the ruler", () => {
    const html = render(
      <ProgressSync
        sync={{ state: "ready", view: view() }}
        scan={initialPlayback}
        span={4}
        onScan={() => {}}
        candidates={CANDIDATES}
      />,
    );

    // The candidate that supplied the line has zero offset everywhere,
    // so a reader comparing the curves has to know which is the ruler.
    expect(html).toContain("A* + DWA");
    expect(html).toContain("badge warn");
  });

  it("offers both the sustained parting and the event anchors", () => {
    const html = render(
      <ProgressSync
        sync={{ state: "ready", view: view() }}
        scan={initialPlayback}
        span={4}
        onScan={() => {}}
        candidates={CANDIDATES}
      />,
    );

    expect(html).toContain("3.3 m");
    expect(html).toContain("replan (B)");
  });

  it("shows a failure as a failure rather than an empty chart", () => {
    const html = render(
      <ProgressSync
        sync={{ state: "error", message: "traces are from different episodes" }}
        scan={initialPlayback}
        span={0}
        onScan={() => {}}
        candidates={CANDIDATES}
      />,
    );

    expect(html).toContain('role="alert"');
    expect(html).toContain("different episodes");
  });
});
