/** What the episode panel shows, and what it must never show.
 *
 * `renderToStaticMarkup` covers first render, which is where every
 * claim in this panel is made. The three that matter:
 *
 * - a diagnosis never appears under the heading about the difference,
 *   because a fault on the side that won explains nothing about the
 *   other side's loss;
 * - the caveat is printed verbatim, so a sentence saying "this is one
 *   episode, not the run" cannot be softened on its way to the reader;
 * - an episode nobody chose is not explained.
 */

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { EpisodeVerdictPanel, type VerdictSlot } from "@/components/EpisodeVerdictPanel";
import type { EpisodeVerdictView } from "@/lib/episodeVerdict";

const CAVEAT =
  "One episode. There is no confidence interval on a single sample, and this " +
  "is not the run's verdict: the decision card ranks candidates over every " +
  "episode that was run.";

function view(overrides: Partial<EpisodeVerdictView> = {}): EpisodeVerdictView {
  return {
    verdict: {
      episode_context_id: "ep-004",
      candidate_a: "A",
      candidate_b: "B",
      basis: "episode_decision_utility",
      winner: "A",
      loser: "B",
      tie: false,
      utility_a: { value: 0.87, unit: "utility", denominator: 1 },
      utility_b: { value: 0.71, unit: "utility", denominator: 1 },
      delta_utility: { value: 0.16, unit: "utility", denominator: 1 },
      undecided_reason: "",
      caveat: CAVEAT,
    },
    diagnoses: [
      {
        candidate_id: "A",
        outcome: {
          candidate_id: "A",
          success: true,
          failure_reason: null,
          collision_count: 0,
          min_clearance: 0.44,
          travel_time_s: 21,
          p99_latency_ms: 6.1,
          replan_count: 1,
          decision_utility: 0.87,
        },
        detections: [
          {
            type: "near_miss_cluster",
            candidate_id: "A",
            episode_context_id: "ep-004",
            window: { start_m: 3, end_m: 4, start_s: 2.5, end_s: 3.1 },
            measurements: { min_clearance_m: 0.08 },
          },
        ],
        planning_attempts: null,
        no_path_attempts: null,
        first_no_path_tick: null,
      },
      {
        candidate_id: "B",
        outcome: {
          candidate_id: "B",
          success: true,
          failure_reason: null,
          collision_count: 0,
          min_clearance: 0.19,
          travel_time_s: 33,
          p99_latency_ms: 19.4,
          replan_count: 4,
          decision_utility: 0.71,
        },
        detections: [
          {
            type: "stuck_cluster",
            candidate_id: "B",
            episode_context_id: "ep-004",
            window: { start_m: 12, end_m: 12, start_s: 8.5, end_s: 12.6 },
            measurements: { stopped_seconds: 4.1 },
          },
        ],
        planning_attempts: 6,
        no_path_attempts: 2,
        first_no_path_tick: 148,
      },
    ],
    contrasts: [
      {
        kind: "detection_only_on_loser",
        against_candidate_id: "B",
        subject: "local_controller",
        proposition_type: "local_minimum_entrapment",
        detail: "stuck_cluster fired on B and not on A",
        evidence_refs: [],
        measurements: {},
      },
    ],
    ruled_out: [
      {
        kind: "detection_only_on_loser",
        reason: "only_on_winner",
        detail: "near_miss_cluster fired on A, which won this episode",
      },
    ],
    floor: { abstained: false, proposals: [], bearings: {} },
    omissions: [],
    candidate_a: "A",
    candidate_b: "B",
    episode_context_id: "ep-004",
    ...overrides,
  };
}

const ready = (over: Partial<EpisodeVerdictView> = {}): VerdictSlot => ({
  state: "ready",
  view: view(over),
});

const html = (slot: VerdictSlot, episodeSelected = true) =>
  renderToStaticMarkup(
    <EpisodeVerdictPanel slot={slot} episodeSelected={episodeSelected} />,
  );

describe("before an episode is chosen", () => {
  it("asks for one rather than explaining the one the replay opened on", () => {
    const markup = html({ state: "idle" }, false);
    expect(markup).toContain("Choose an episode");
    expect(markup).not.toContain("took this episode");
  });
});

describe("when the episode was scored", () => {
  it("names the winner", () => {
    expect(html(ready())).toContain("A took this episode");
  });

  it("prints the caveat exactly as the platform wrote it", () => {
    // A caveat the client may reword is a caveat the client may dilute.
    expect(html(ready())).toContain("is not the run&#x27;s verdict");
  });

  it("keeps the winner's own fault out of the difference section", () => {
    const markup = html(ready());
    const contrastHeading = markup.indexOf("Differences that may bear on it");
    const nearMiss = markup.indexOf("came close to an obstacle");
    expect(nearMiss).toBeGreaterThan(-1);
    expect(nearMiss).toBeLessThan(contrastHeading);
  });

  it("says what it looked at and did not offer", () => {
    expect(html(ready())).toContain("Looked at and not offered");
  });

  it("marks a supporting difference apart from context", () => {
    expect(html(ready())).toContain("Relevant");
  });

  it("never claims the model explained anything", () => {
    const markup = html(ready());
    expect(markup).not.toMatch(/AI (explains|giải thích)/i);
    expect(markup).not.toContain("why A won");
  });
});

describe("when the episode named no side", () => {
  it("says so instead of listing differences against nobody", () => {
    const markup = html(
      ready({
        verdict: {
          ...view().verdict,
          winner: null,
          loser: null,
          tie: true,
          undecided_reason: "the two are within the preregistered margin of 0.005 utility",
        },
        contrasts: [],
      }),
    );
    expect(markup).toContain("Neither side took this episode");
    expect(markup).toContain("this episode named no loser");
  });

  it("says a missing record is not a defeat", () => {
    const markup = html(
      ready({
        verdict: {
          ...view().verdict,
          basis: "not_comparable",
          winner: null,
          loser: null,
          undecided_reason: "B has no row for this episode",
        },
        contrasts: [],
      }),
    );
    expect(markup).toContain("cannot be compared");
  });
});

describe("when the run cannot answer", () => {
  it("shows the reason rather than an empty panel", () => {
    const markup = html({ state: "unavailable", message: "this run ranked nobody" });
    expect(markup).toContain("this run ranked nobody");
  });
});
