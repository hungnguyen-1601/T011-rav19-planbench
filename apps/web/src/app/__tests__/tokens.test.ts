/** Every `var(--x)` in the stylesheet resolves to something.
 *
 * Three bugs of one shape shipped before this file existed:
 * `--text-muted` on the hint mark, `--font-mono` on two code blocks, and
 * `--fg` on the latency playhead. None of them threw, none showed up in
 * a build log, and none was visible in review — a custom property that
 * was never declared is *invalid at computed-value time*, which means
 * the declaration is quietly dropped and the element inherits, or falls
 * back, or renders transparent. The failure looks like a design choice.
 *
 * So this does not test those three. It tests the shape: the set of
 * tokens the stylesheet reads must be a subset of the set it declares,
 * plus a short list of names that provably come from somewhere else.
 *
 * **Fallbacks are not exempt.** `var(--fg, #111827)` is where the worst
 * of the three hid: it had an answer for the missing token, so it never
 * looked broken, and the playhead spent its life drawing a near-black
 * line on a near-black canvas. A fallback makes a missing token quieter,
 * not more correct.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Custom properties set from JSX `style={{ ... }}`, never in CSS.
 *
 * Adding to this list is how a token legitimately escapes the rule, and
 * it is deliberately a list rather than a pattern: widening it is an
 * edit a reviewer sees.
 */
const JSX_PROVIDED = ["--cols", "--delta-col"];

/** Emitted by `next/font` under the name given as its `variable:`.
 *
 * The contract with the font work: the **public** tokens (`--font-sans`,
 * `--font-mono`) are always declared in `globals.css`, and a webfont
 * only changes their *value* to `var(--font-*-loaded, <stack>)`. So the
 * loaded names appear here, the public ones never need to, and no later
 * plan has to loosen this test to land a typeface.
 */
const NEXT_FONT_PROVIDED = ["--font-sans-loaded", "--font-mono-loaded"];

const ALLOWED = new Set([...JSX_PROVIDED, ...NEXT_FONT_PROVIDED]);

const CSS = readFileSync(
  join(process.cwd(), "src", "app", "globals.css"),
  "utf8",
);

/** The stylesheet with every comment removed.
 *
 * Load-bearing, not tidiness: this file documents its tokens in prose,
 * and a `--foo:` written inside a comment would otherwise count as a
 * declaration and vouch for a token nothing declares. The same applies
 * in reverse to a `var(--x)` quoted in a comment, which must not count
 * as a use.
 */
export function withoutComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

export function declaredTokens(css: string): Set<string> {
  return new Set(
    [...withoutComments(css).matchAll(/(--[A-Za-z0-9_-]+)\s*:/g)].map((m) => m[1]),
  );
}

export function referencedTokens(css: string): Set<string> {
  return new Set(
    [...withoutComments(css).matchAll(/var\(\s*(--[A-Za-z0-9_-]+)/g)].map((m) => m[1]),
  );
}

describe("the token contract", () => {
  it("declares every token it reads", () => {
    const declared = declaredTokens(CSS);
    const missing = [...referencedTokens(CSS)]
      .filter((token) => !declared.has(token) && !ALLOWED.has(token))
      .sort();
    expect(missing, `undeclared tokens: ${missing.join(", ")}`).toEqual([]);
  });

  it("reads enough tokens for that to mean something", () => {
    /* A regex that silently stopped matching would make the check above
       pass by finding nothing at all. */
    expect(referencedTokens(CSS).size).toBeGreaterThan(50);
    expect(declaredTokens(CSS).size).toBeGreaterThan(50);
  });
});

describe("what the reader counts", () => {
  it("does not accept a declaration written inside a comment", () => {
    /* The whole reason comments are stripped first. Without it this
       stylesheet's own prose would vouch for tokens nothing declares. */
    expect(declaredTokens("/* --ghost: red; */ .a { color: var(--ghost); }")).toEqual(
      new Set(),
    );
  });

  it("does not count a use written inside a comment", () => {
    expect(referencedTokens("/* see var(--ghost) */ .a { color: red; }")).toEqual(
      new Set(),
    );
  });

  it("still counts a use that carries a fallback", () => {
    /* `var(--fg, #111827)` is exactly the form that hid a real bug. */
    expect(referencedTokens(".a { stroke: var(--fg, #111827); }")).toEqual(
      new Set(["--fg"]),
    );
  });

  it("counts a declaration and a use of the same name independently", () => {
    const css = ":root { --x: 1px; } .a { margin: var(--x); }";
    expect(declaredTokens(css)).toEqual(new Set(["--x"]));
    expect(referencedTokens(css)).toEqual(new Set(["--x"]));
  });
});
