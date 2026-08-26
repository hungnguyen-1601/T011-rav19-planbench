/** Paging the episode table.
 *
 * Every case here is invisible on a run with five episodes, which is
 * every run anyone has looked at so far — and the reason the table was
 * built without paging in the first place.
 */

import { describe, expect, it } from "vitest";

import {
  EPISODES_PER_PAGE,
  clampPage,
  pageCount,
  pageOf,
  pageSlice,
  pageWindow,
} from "@/lib/episodePages";

const rows = (n: number) => Array.from({ length: n }, (_, index) => index);

describe("how many pages", () => {
  it("counts a partial last page", () => {
    expect(pageCount(11)).toBe(3);
  });

  it("gives an empty list one page, not none", () => {
    // "Page 1 of 0" is a control that cannot be rendered.
    expect(pageCount(0)).toBe(1);
  });

  it("does not add an empty page on an exact multiple", () => {
    expect(pageCount(EPISODES_PER_PAGE * 4)).toBe(4);
  });
});

describe("which page holds a row", () => {
  it("puts the first rows on page one", () => {
    expect(pageOf(0)).toBe(0);
    expect(pageOf(EPISODES_PER_PAGE - 1)).toBe(0);
  });

  it("rolls over on the boundary", () => {
    expect(pageOf(EPISODES_PER_PAGE)).toBe(1);
  });

  it("treats a row that is not in the list as the first page", () => {
    // `indexOf` returns -1 for an episode filtered out from under the
    // selection; jumping to page -1 would leave the strip with no
    // active tab.
    expect(pageOf(-1)).toBe(0);
  });
});

describe("when the list shrinks under the reader", () => {
  it("clamps a page past the new end", () => {
    // Turning on "only episodes somebody failed" while on page 7 of 12
    // can leave two pages. Page 7 of two is a blank table, which reads
    // as a run with no episodes.
    expect(clampPage(6, 8)).toBe(1);
  });

  it("never goes below the first page", () => {
    expect(clampPage(-3, 40)).toBe(0);
  });

  it("slices the clamped page rather than returning nothing", () => {
    expect(pageSlice(rows(8), 6)).toEqual([5, 6, 7]);
  });
});

describe("slicing a page", () => {
  it("takes exactly one page of rows", () => {
    expect(pageSlice(rows(30), 2)).toEqual([10, 11, 12, 13, 14]);
  });

  it("takes what is left on a partial last page", () => {
    expect(pageSlice(rows(12), 2)).toEqual([10, 11]);
  });

  it("returns nothing for an empty list", () => {
    expect(pageSlice([], 0)).toEqual([]);
  });
});

describe("the strip of page numbers", () => {
  it("offers every page when they fit", () => {
    expect(pageWindow(0, 15)).toEqual([0, 1, 2]);
  });

  it("caps the strip rather than growing one tab per page", () => {
    // Three hundred episodes is sixty pages. Sixty tabs is the same
    // problem the paging was added to solve.
    expect(pageWindow(30, 300)).toHaveLength(7);
  });

  it("centres on the current page in the middle of a long run", () => {
    expect(pageWindow(30, 300)).toEqual([27, 28, 29, 30, 31, 32, 33]);
  });

  it("keeps its width at the start instead of showing fewer tabs", () => {
    // A window that slid symmetrically would show four tabs on page 1
    // and seven in the middle, so the control would change size as the
    // reader moved through it.
    expect(pageWindow(0, 300)).toEqual([0, 1, 2, 3, 4, 5, 6]);
  });

  it("keeps its width at the end too", () => {
    expect(pageWindow(59, 300)).toEqual([53, 54, 55, 56, 57, 58, 59]);
  });

  it("always contains the current page", () => {
    for (const page of [0, 1, 7, 29, 58, 59]) {
      expect(pageWindow(page, 300)).toContain(page);
    }
  });
});
