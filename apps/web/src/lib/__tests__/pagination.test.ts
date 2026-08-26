/** Paging a filtered list — the arithmetic, without a browser.
 *
 * The three things this has to get right are the three that do not
 * show up on a list of four rows:
 *
 * - **Ten means ten.** A page that quietly returns eleven or nine is
 *   invisible until somebody counts, and by then the reader has drawn a
 *   conclusion from a table they believe is complete.
 * - **An empty list is page 1 of 1**, not page 1 of 0. Zero pages is
 *   arithmetic nobody can stand on: `clampPage` would return -1 and the
 *   slice would start at a negative offset.
 * - **A changed filter starts again at page 1.** Standing on page 4 and
 *   narrowing the list to eight rows otherwise leaves a blank table,
 *   which reads as "nothing matched" — the wrong answer, delivered
 *   confidently.
 *
 * The reset rule is a pure function (`pagerStateFor`) precisely so it
 * can be checked here: this repo has no jsdom, so the hook that uses it
 * cannot be driven through a filter change in a test.
 */

import { describe, expect, it } from "vitest";

import {
  DEFAULT_PER_PAGE,
  clampPage,
  pageCount,
  pageOf,
  pagerStateFor,
  pageSlice,
  pageWindow,
} from "@/lib/pagination";

const rows = (count: number): number[] => Array.from({ length: count }, (_, index) => index);

describe("how many pages a list has", () => {
  it("pages ten at a time by default", () => {
    expect(DEFAULT_PER_PAGE).toBe(10);
  });

  it("is always at least one page, even with nothing in the list", () => {
    /* "Page 1 of 0" is not a position anybody can be in, and every
       clamp below it produces a negative slice offset. */
    expect(pageCount(0)).toBe(1);
    expect(clampPage(0, 0)).toBe(0);
    expect(pageSlice([], 0)).toEqual([]);
  });

  it("does not open a second page for an exact ten", () => {
    expect(pageCount(10)).toBe(1);
    expect(pageCount(11)).toBe(2);
    expect(pageCount(40)).toBe(4);
    expect(pageCount(41)).toBe(5);
  });

  it("honours a page size other than the default", () => {
    /* The episode table pages five at a time through this same
       arithmetic. */
    expect(pageCount(11, 5)).toBe(3);
    expect(pageSlice(rows(11), 2, 5)).toEqual([10]);
  });
});

describe("which rows a page holds", () => {
  it("cuts at exactly ten, and the last page keeps the remainder", () => {
    const list = rows(23);
    expect(pageSlice(list, 0)).toEqual(rows(10));
    expect(pageSlice(list, 1)).toHaveLength(10);
    expect(pageSlice(list, 1)[0]).toBe(10);
    expect(pageSlice(list, 2)).toEqual([20, 21, 22]);
  });

  it("never drops or repeats a row across the pages", () => {
    /* The failure this catches is an off-by-one in the offset, which
       shows up as one run missing from a forty-run list — and nothing
       on screen says a row is missing. */
    const list = rows(37);
    const walked = [0, 1, 2, 3].flatMap((page) => pageSlice(list, page));
    expect(walked).toEqual(list);
  });

  it("clamps a page past the end onto the last one rather than going blank", () => {
    const list = rows(23);
    expect(clampPage(9, list.length)).toBe(2);
    expect(pageSlice(list, 9)).toEqual([20, 21, 22]);
    expect(clampPage(-3, list.length)).toBe(0);
  });

  it("says which page holds a given row", () => {
    expect(pageOf(0)).toBe(0);
    expect(pageOf(9)).toBe(0);
    expect(pageOf(10)).toBe(1);
    expect(pageOf(-1)).toBe(0);
  });
});

describe("a numbered strip keeps its width at both ends", () => {
  it("offers the same count of pages wherever the reader stands", () => {
    for (const page of [0, 3, 20, 29]) {
      expect(pageWindow(page, 300, 10)).toHaveLength(7);
    }
  });

  it("never offers more pages than exist", () => {
    expect(pageWindow(0, 12, 10)).toEqual([0, 1]);
  });
});

describe("changing the filter goes back to the first page", () => {
  it("keeps the page while the list is the same list", () => {
    const remembered = { page: 3, key: "all|all|all" };
    /* Identity, not just equality: the hook writes state back only when
       this returns something new, and a fresh object every render would
       be an infinite loop. */
    expect(pagerStateFor(remembered, "all|all|all")).toBe(remembered);
  });

  it("drops to page 1 the moment the key changes", () => {
    /* Page 4 of a forty-run list, then "ranked only" leaves eight runs:
       without this the reader sees an empty table and reads it as "no
       ranked runs", which is the opposite of true. */
    expect(pagerStateFor({ page: 3, key: "all|all|all" }, "wh1|ranked|all")).toEqual({
      page: 0,
      key: "wh1|ranked|all",
    });
  });

  it("resets on any of the filters, not only the first", () => {
    const remembered = { page: 2, key: "wh1|all|all" };
    for (const key of ["wh1|ranked|all", "wh1|all|reviewed", "|all|all"]) {
      expect(pagerStateFor(remembered, key).page).toBe(0);
    }
  });
});
