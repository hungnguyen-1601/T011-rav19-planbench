/** Reading one episode's answer: which episode, whose answer, what it says.
 *
 * The rules that produce a verdict live on the platform and are tested
 * there. What is tested here is the reading, and each of these has an
 * obvious wrong version that would look right on screen:
 *
 * - fall back to whichever episode the replay opened on, and explain an
 *   episode nobody pointed at;
 * - check the answer against the request rather than against the
 *   selection, and show episode A's finding under episode B's heading;
 * - offer the model button on a page where the model cannot be asked.
 */

import { describe, expect, it } from "vitest";

import {
  answersCurrentSelection,
  contrastStrength,
  detectionSeconds,
  hasDirection,
  mayAskTheModel,
  orderedDiagnoses,
  selectedEpisode,
  sideOf,
  verdictHeadlineKey,
  type EpisodeDetection,
  type EpisodeVerdict,
  type EpisodeVerdictView,
} from "../episodeVerdict";

const CAVEAT =
  "One episode. There is no confidence interval on a single sample, and this " +
  "is not the run's verdict: the decision card ranks candidates over every " +
  "episode that was run.";

function verdict(overrides: Partial<EpisodeVerdict> = {}): EpisodeVerdict {
  return {
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
    ...overrides,
  };
}

function view(overrides: Partial<EpisodeVerdictView> = {}): EpisodeVerdictView {
  return {
    verdict: verdict(),
    diagnoses: [
      {
        candidate_id: "B",
        outcome: null,
        detections: [],
        planning_attempts: null,
        no_path_attempts: null,
        first_no_path_tick: null,
      },
      {
        candidate_id: "A",
        outcome: null,
        detections: [],
        planning_attempts: null,
        no_path_attempts: null,
        first_no_path_tick: null,
      },
    ],
    contrasts: [],
    ruled_out: [],
    floor: { abstained: true, proposals: [], bearings: {} },
    omissions: [],
    candidate_a: "A",
    candidate_b: "B",
    episode_context_id: "ep-004",
    ...overrides,
  };
}

describe("which episode the panel is about", () => {
  it("is nothing until a reader points at one", () => {
    // The replay opens on the first episode so the canvases are not
    // blank. Nobody chose it, and explaining it would answer a question
    // that was never asked — with the same confidence as one that was.
    expect(selectedEpisode({ episodeId: "ep-001", origin: "default" })).toBeNull();
  });

  it("is the one a reader chose", () => {
    expect(selectedEpisode({ episodeId: "ep-004", origin: "user" })).toBe("ep-004");
  });

  it("is nothing when the selection was cleared", () => {
    expect(selectedEpisode({ episodeId: "", origin: "user" })).toBeNull();
  });
});

describe("whether an answer still describes what is on screen", () => {
  it("accepts the answer to the current selection", () => {
    expect(
      answersCurrentSelection(view(), {
        episode: "ep-004",
        candidateA: "A",
        candidateB: "B",
      }),
    ).toBe(true);
  });

  it("refuses an answer about another episode", () => {
    // A reader clicking through three episodes must not see the first
    // one's finding under the third one's heading, and the request that
    // started earliest lands last often enough for this to matter.
    expect(
      answersCurrentSelection(view(), {
        episode: "ep-009",
        candidateA: "A",
        candidateB: "B",
      }),
    ).toBe(false);
  });

  it("refuses an answer about another pair", () => {
    expect(
      answersCurrentSelection(view(), {
        episode: "ep-004",
        candidateA: "A",
        candidateB: "C",
      }),
    ).toBe(false);
  });

  it("refuses everything once the selection is cleared", () => {
    expect(
      answersCurrentSelection(view(), { episode: null, candidateA: "A", candidateB: "B" }),
    ).toBe(false);
  });

  it("has nothing to show before the first answer", () => {
    expect(
      answersCurrentSelection(null, { episode: "ep-004", candidateA: "A", candidateB: "B" }),
    ).toBe(false);
  });
});

describe("what the headline says", () => {
  it("names a winner when the episode was scored", () => {
    expect(verdictHeadlineKey(verdict())).toBe("episodeVerdict.headline.utility");
  });

  it("says a record is missing rather than that the two were equal", () => {
    // The most tempting mistake in the whole feature: no row means the
    // candidate never ran the episode, was eliminated before it, or was
    // not recorded — none of which is losing, and none of which is a tie.
    const missing = verdict({
      basis: "not_comparable",
      winner: null,
      loser: null,
      undecided_reason: "B has no row for this episode",
    });
    expect(verdictHeadlineKey(missing)).toBe("episodeVerdict.headline.notComparable");
  });

  it("keeps a tie apart from an undecidable episode", () => {
    const tie = verdict({ winner: null, loser: null, tie: true, undecided_reason: "within" });
    const undecidable = verdict({
      basis: "undecidable",
      winner: null,
      loser: null,
      undecided_reason: "neither was scored",
    });
    expect(verdictHeadlineKey(tie)).toBe("episodeVerdict.headline.tie");
    expect(verdictHeadlineKey(undecidable)).toBe("episodeVerdict.headline.undecidable");
  });

  it("knows when nothing may be stated against a side", () => {
    expect(hasDirection(verdict())).toBe(true);
    expect(hasDirection(verdict({ winner: null, loser: null, tie: true }))).toBe(false);
  });
});

describe("how findings are read", () => {
  it("marks the two detection kinds as carrying a mechanism", () => {
    expect(contrastStrength("detection_only_on_loser")).toBe("support");
    expect(contrastStrength("detection_worse_on_loser")).toBe("support");
  });

  it("marks a component difference as context", () => {
    // Read as support it licenses the move this whole layer refuses:
    // pick any known weakness of the losing component and call it the
    // reason, with nothing having fired at all.
    expect(contrastStrength("component_differs")).toBe("context");
    expect(contrastStrength("outcome_differs")).toBe("context");
    expect(contrastStrength("divergence_precedes_outcome")).toBe("context");
  });

  it("puts the winner's diagnosis first", () => {
    expect(orderedDiagnoses(view()).map((item) => item.candidate_id)).toEqual(["A", "B"]);
  });

  it("leaves the order alone when no side won", () => {
    const undecided = view({ verdict: verdict({ winner: null, loser: null, tie: true }) });
    expect(orderedDiagnoses(undecided).map((item) => item.candidate_id)).toEqual(["B", "A"]);
  });
});

describe("seeking to a detection", () => {
  const detection = (window: EpisodeDetection["window"]): EpisodeDetection => ({
    type: "stuck_cluster",
    candidate_id: "B",
    episode_context_id: "ep-004",
    window,
    measurements: {},
  });

  it("uses the moment the window opened", () => {
    expect(
      detectionSeconds(detection({ start_m: 12, end_m: 14, start_s: 8.5, end_s: 12.6 })),
    ).toBe(8.5);
  });

  it("refuses to guess when nothing recorded a window", () => {
    // Seeking to a moment nothing recorded would move the playhead
    // somewhere arbitrary and tell the reader that was the place.
    expect(detectionSeconds(detection(null))).toBeNull();
  });

  it("knows which canvas a candidate is on", () => {
    expect(sideOf(view(), "A")).toBe("a");
    expect(sideOf(view(), "B")).toBe("b");
    expect(sideOf(view(), "C")).toBeNull();
  });
});

describe("whether the model may be asked", () => {
  it("is closed while the platform keeps it closed", () => {
    expect(mayAskTheModel({ mode: "off", isAdmin: true, episode: "ep-004" })).toBe(false);
    expect(mayAskTheModel({ mode: "shadow", isAdmin: true, episode: "ep-004" })).toBe(false);
  });

  it("is closed to a reader who is not an administrator in preview", () => {
    expect(
      mayAskTheModel({ mode: "internal_preview", isAdmin: false, episode: "ep-004" }),
    ).toBe(false);
    expect(mayAskTheModel({ mode: "internal_preview", isAdmin: true, episode: "ep-004" })).toBe(
      true,
    );
  });

  it("is closed when no episode was chosen", () => {
    // A control that appears and then refuses is worse than one that
    // was never there.
    expect(mayAskTheModel({ mode: "internal_preview", isAdmin: true, episode: null })).toBe(
      false,
    );
  });
});
