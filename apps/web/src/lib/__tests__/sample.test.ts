/** The sample line, and the single notice under it.
 *
 * The case that matters most is the first one: a run below N_min must
 * not print `meets N_min` and leave the correction to a notice. That was
 * the shape of the original bug — the line and the box under it saying
 * opposite things, with the line winning because it is what a skimming
 * reader reads.
 */

import { describe, expect, it } from "vitest";

import type { RunSample } from "@/lib/decisions";
import {
  BELOW_N_MIN,
  MEETS_N_MIN,
  noticeKey,
  sampleLine,
  sampleNotice,
} from "@/lib/sample";

const sample = (over: Partial<RunSample> = {}): RunSample => ({
  n_episodes: 30,
  n_min_required: 30,
  episode_context_ids: [],
  ...over,
});

describe("the N_min clause", () => {
  it("says it meets N_min only when it does", () => {
    expect(sampleLine(sample()).nMinKey).toBe(MEETS_N_MIN);
    expect(sampleLine(sample({ n_episodes: 31 })).nMinKey).toBe(MEETS_N_MIN);
  });

  it("says below N_min when the run fell short", () => {
    const line = sampleLine(sample({ n_episodes: 18 }));
    expect(line.nMinKey).toBe(BELOW_N_MIN);
    /* The whole point of the separate key: the reader gets both numbers,
       because "N_min required: 30" alone does not say how short it fell. */
    expect(line.params).toEqual({ n: 18, min: 30 });
  });

  it("never selects the meets key on a short run, interrupted or not", () => {
    for (const interrupted of [true, false, undefined]) {
      expect(sampleLine(sample({ n_episodes: 18, interrupted })).nMinKey).not.toBe(
        MEETS_N_MIN,
      );
    }
  });
});

describe("the full-request clause", () => {
  it("is claimed only with all three conditions", () => {
    expect(
      sampleLine(sample({ n_episodes_requested: 30 })).ranFullRequest,
    ).toBe(true);
  });

  it("is withheld from a run stored before the field existed", () => {
    /* Absent is not "covered everything". A run that cannot say what it
       asked for must not get credit for having asked for what it got. */
    expect(sampleLine(sample()).ranFullRequest).toBe(false);
  });

  it("is withheld when the run was interrupted, however many landed", () => {
    expect(
      sampleLine(sample({ n_episodes_requested: 30, interrupted: true }))
        .ranFullRequest,
    ).toBe(false);
  });

  it("is withheld when fewer episodes landed than were asked for", () => {
    expect(
      sampleLine(sample({ n_episodes: 24, n_episodes_requested: 30 }))
        .ranFullRequest,
    ).toBe(false);
  });
});

describe("the coverage clause", () => {
  it("is absent at full coverage — a clause saying 100% earns nothing", () => {
    expect(sampleLine(sample(), 1).coveragePercent).toBeNull();
  });

  it("is absent when coverage is unknown, which is not the same as complete", () => {
    expect(sampleLine(sample(), undefined).coveragePercent).toBeNull();
  });

  it("rounds to a whole percent when short", () => {
    expect(sampleLine(sample(), 0.6).coveragePercent).toBe(60);
    expect(sampleLine(sample(), 24 / 30).coveragePercent).toBe(80);
  });

  it("is dropped when it would restate the N_min clause", () => {
    /* Run cb323e9d542b, real: 245 measured, 300 requested, N_min 300.
       Both clauses describe the same shortfall — one as `245/300`, one
       as `82%` — on the line whose whole purpose is to stop printing one
       number three times. */
    const line = sampleLine(
      sample({ n_episodes: 245, n_episodes_requested: 300, n_min_required: 300 }),
      245 / 300,
    );
    expect(line.nMinKey).toBe(BELOW_N_MIN);
    expect(line.coveragePercent).toBeNull();
  });

  it("keeps both when they are genuinely different facts", () => {
    /* Asked for 400, N_min is 30, got 20: "below N_min (20/30)" and
       "coverage 5%" answer different questions. */
    const line = sampleLine(
      sample({ n_episodes: 20, n_episodes_requested: 400, n_min_required: 30 }),
      20 / 400,
    );
    expect(line.nMinKey).toBe(BELOW_N_MIN);
    expect(line.coveragePercent).toBe(5);
  });

  it("keeps coverage on a run that met N_min but not the request", () => {
    /* Not short, so the N_min clause says "meets" and carries no
       shortfall — coverage is then the only thing saying one exists. */
    const line = sampleLine(
      sample({ n_episodes: 30, n_episodes_requested: 40, n_min_required: 30 }),
      30 / 40,
    );
    expect(line.nMinKey).toBe(MEETS_N_MIN);
    expect(line.coveragePercent).toBe(75);
  });
});

describe("notice precedence — at most one", () => {
  it("shows nothing for an ordinary run", () => {
    expect(sampleNotice(sample())).toBeNull();
    expect(noticeKey(sampleNotice(sample()))).toBeNull();
  });

  it("shows the interrupted warning when the sample is still big enough", () => {
    expect(sampleNotice(sample({ interrupted: true }))).toBe("warn");
  });

  it("shows critical when below N_min", () => {
    expect(sampleNotice(sample({ n_episodes: 18 }))).toBe("critical");
  });

  it("folds both facts into one notice rather than stacking two", () => {
    /* Two boxes of the same shape read as two problems of equal weight.
       They are not: below N_min voids the numbers, interrupted explains
       how the run got there. */
    const notice = sampleNotice(sample({ n_episodes: 18, interrupted: true }));
    expect(notice).toBe("belowNMinInterrupted");
    expect(noticeKey(notice)?.variant).toBe("notice--critical");
  });

  it("gives every non-null notice a key and a variant", () => {
    for (const n of ["critical", "belowNMinInterrupted", "warn"] as const) {
      const entry = noticeKey(n);
      expect(entry?.key, n).toBeTruthy();
      expect(entry?.variant, n).toMatch(/^notice--/);
    }
  });
});
