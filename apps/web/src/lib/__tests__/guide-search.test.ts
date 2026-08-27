/** Typing without tones has to find the heading that has them.
 *
 * This is not a nicety. Vietnamese is routinely typed unaccented, and a
 * guide whose search only matches perfectly accented input is a search
 * that fails for the people it was written for.
 */

import { describe, expect, it } from "vitest";

import { fold, matches, search, type SearchTarget } from "../guideSearch";

const TARGETS: SearchTarget[] = [
  { href: "/guide/operation", title: "Bảy bước vận hành" },
  { href: "/guide/operation#deployment", title: "Khai deployment", context: "Bảy bước vận hành" },
  { href: "/guide/gates#g2", title: "G2 — Va chạm", context: "Cổng đánh giá" },
];

describe("folding", () => {
  it("drops tone marks", () => {
    expect(fold("Bảy bước vận hành")).toBe("bay buoc van hanh");
  });

  it("flattens đ, which NFD leaves alone", () => {
    /* `đ` is its own letter rather than `d` plus a mark, so decomposing
       does not touch it — and somebody typing `do` for `đo` would find
       nothing without this line. */
    expect(fold("Đo đạc")).toBe("do dac");
  });

  it("lowercases and trims", () => {
    expect(fold("  Khai DEPLOYMENT ")).toBe("khai deployment");
  });
});

describe("matching", () => {
  it("finds an accented heading from unaccented typing", () => {
    /* Two, not one: the article and the section that belongs to it. A
       query naming an article is a request for the article *and* its
       parts — the same rule that lets somebody who remembers only the
       article find a heading inside it. */
    expect(search(TARGETS, "bay buoc")).toHaveLength(2);
    expect(search(TARGETS, "van hanh")[0].href).toBe("/guide/operation");
  });

  it("finds it from the accented spelling too", () => {
    expect(search(TARGETS, "vận hành")[0].href).toBe("/guide/operation");
  });

  it("matches a heading through the article it belongs to", () => {
    /* Somebody who remembers the article but not the heading still has
       to land somewhere useful. */
    expect(search(TARGETS, "cong danh gia")[0].href).toBe("/guide/gates#g2");
  });

  it("treats an empty query as no filter rather than no results", () => {
    expect(matches(TARGETS[0], "   ")).toBe(true);
  });

  it("does not match text that is only in the article body", () => {
    /* The honest limit, pinned so nobody later assumes otherwise: this
       searches headings. The empty state has to keep saying so. */
    expect(search(TARGETS, "conditions_checksum")).toHaveLength(0);
  });
});
