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

import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Custom properties set from JSX `style={{ ... }}`, never in CSS.
 *
 * Adding to this list is how a token legitimately escapes the rule, and
 * it is deliberately a list rather than a pattern: widening it is an
 * edit a reviewer sees.
 */
/* Nothing at present. `--cols` and `--delta-col` lived here while the
   comparison grid was a flat CSS grid fed its column count from an
   inline style; it is a `<table>` now and sizes its own columns, so
   the entries went with the thing that supplied them. An allowlist
   keeps its meaning only while every entry in it is still real. */
const JSX_PROVIDED: string[] = [];

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

describe("the font contract", () => {
  /* Comments stripped, for the same reason the stylesheet's are: this
     file's own prose names `next/font/google` and quotes `display:
     "swap"` while explaining why they are or are not used, and an
     assertion that matched documentation rather than code would pass or
     fail on how the change was described. */
  const stripComments = (source: string) =>
    source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(?<![:"'`])\/\/.*$/gm, "");
  const LAYOUT = stripComments(
    readFileSync(join(process.cwd(), "src", "app", "layout.tsx"), "utf8"),
  );

  it("loads the faces from files in the repo, not over the network", () => {
    /* `next/font/google` fetches at *build* time. The runtime is
       offline-safe either way because it self-hosts afterwards, but no
       CSS fallback can rescue a build that produced no CSS — and a demo
       build has to be reproducible on a machine with no network. */
    expect(LAYOUT).toContain('from "next/font/local"');
    expect(LAYOUT).not.toContain("next/font/google");
  });

  it("keeps the public tokens declared here, aliasing the loaded ones", () => {
    /* The contract this test file has enforced since before the fonts
       existed: `--font-sans` and `--font-mono` are always declared in
       `globals.css`, and a webfont only changes their *value*. Nothing
       had to loosen to land a typeface. */
    const declared = declaredTokens(CSS);
    expect(declared.has("--font-sans")).toBe(true);
    expect(declared.has("--font-mono")).toBe(true);
    for (const loaded of NEXT_FONT_PROVIDED) {
      expect(CSS, loaded).toContain(`var(${loaded},`);
      expect(LAYOUT, loaded).toContain(`variable: "${loaded}"`);
    }
  });

  it("keeps a real fallback behind each alias", () => {
    /* The face has to arrive over the wire even when self-hosted. With
       no fallback the page paints in whatever the browser defaults to,
       which on Windows is Times New Roman under a UI built for a
       geometric sans. */
    expect(CSS).toContain("var(--font-sans-loaded, ui-sans-serif, system-ui, -apple-system,");
    expect(CSS).toContain("var(--font-mono-loaded, ui-monospace, SFMono-Regular,");
  });

  it("swaps rather than blocking on the font", () => {
    /* `display: "block"` leaves a blank paragraph for as long as the
       face takes — a page that looks broken rather than plain. */
    expect(LAYOUT.match(/display: "swap"/g)).toHaveLength(2);
  });

  it("ships every weight it declares, and declares every weight it ships", () => {
    /* A `src` entry pointing at a file nobody committed fails the build;
       a committed file nobody references is weight the reader downloads
       and never sees. */
    const fonts = join(process.cwd(), "src", "app", "fonts");
    const shipped = readdirSync(fonts).filter((name) => name.endsWith(".woff2")).sort();
    const referenced = [...LAYOUT.matchAll(/\.\/fonts\/([\w-]+\.woff2)/g)]
      .map((match) => match[1])
      .sort();
    expect(referenced).toEqual(shipped);
    expect(shipped.length).toBeGreaterThan(0);
  });

  it("records where every binary came from", () => {
    /* A font with no provenance is a file nobody dares replace: no way
       to tell which release it is, whether it carries the Vietnamese
       glyphs, or whether somebody swapped one. */
    const readme = readFileSync(join(process.cwd(), "src", "app", "fonts", "README.md"), "utf8");
    const fonts = join(process.cwd(), "src", "app", "fonts");
    for (const name of readdirSync(fonts).filter((f) => f.endsWith(".woff2"))) {
      expect(readme, name).toContain(name);
      const hash = createHash("sha256")
        .update(readFileSync(join(fonts, name)))
        .digest("hex");
      expect(readme, `${name}: manifest hash is stale`).toContain(hash);
    }
    expect(readme).toContain("OFL-1.1");
  });
});

describe("the base every unstyled element inherits", () => {
  /* Line endings normalised first: this file is checked out with CRLF,
     so an anchor written with `\n` finds nothing — and `slice(-1, …)`
     then returns an empty string rather than throwing, so every
     assertion below would pass against nothing at all. The guard is
     there because that is exactly how it failed the first time. */
  const base = () => {
    const flat = CSS.replace(/\r\n/g, "\n");
    const at = flat.indexOf("\nhtml,\nbody {");
    expect(at, "the base rule is no longer where this test looks").toBeGreaterThan(-1);
    return withoutComments(flat.slice(at, flat.indexOf("\n}", at)));
  };

  it("gives body text a line-height Vietnamese can live at", () => {
    /* There was no global `line-height`, so body text ran at the
       browser default — about 1.15–1.2 depending on the face's metrics.
       At that spacing `ế`, `ữ` and `ộ` put a mark on top of a mark and
       collide with the line above. This is a floor for the alphabet,
       not a preference. */
    expect(base()).toContain("line-height: 1.5");
  });

  it("takes its size from the scale rather than a loose number", () => {
    expect(base()).toContain("font-size: var(--fs-body)");
    expect(base()).not.toMatch(/font-size: *\d+px/);
  });

  it("leaves no font-size measured in rem", () => {
    /* Those were the only declarations that moved when the base changed,
       and they moved the wrong way: two of the three fell below
       `--fs-caption`, the smallest step the scale defines, on text
       carrying Vietnamese diacritics. Every size in this file is now
       pinned, so changing the base cannot silently shrink one component
       past the floor. */
    expect(withoutComments(CSS)).not.toMatch(/font-size: *[\d.]+rem/);
  });

});

describe("what !important is still allowed to do", () => {
  /* Not "there is none". Three rules need it and always will: inside a
     `prefers-reduced-motion` block, `transition: none` has to beat the
     transition each component declares for itself, and that override is
     the entire mechanism. Deleting them hands the animation back to the
     one reader who asked for it to stop, silently — nobody who sets that
     preference is looking at a screenshot. */
  const flat = CSS.replace(/\r\n/g, "\n");
  const code = withoutComments(flat);

  /** Every `@media (prefers-reduced-motion: reduce) { … }` block. */
  const reducedMotion = () => {
    const blocks: string[] = [];
    const marker = "@media (prefers-reduced-motion: reduce)";
    for (let at = code.indexOf(marker); at !== -1; at = code.indexOf(marker, at + 1)) {
      let depth = 0;
      let i = code.indexOf("{", at);
      const start = i;
      for (; i < code.length; i += 1) {
        if (code[i] === "{") depth += 1;
        else if (code[i] === "}") {
          depth -= 1;
          if (depth === 0) break;
        }
      }
      blocks.push(code.slice(start, i));
    }
    return blocks;
  };

  it("allows it only where a reader asked for motion to stop", () => {
    const total = (code.match(/!important/g) ?? []).length;
    const inside = reducedMotion().reduce(
      (count, block) => count + (block.match(/!important/g) ?? []).length,
      0,
    );
    expect(total).toBeGreaterThan(0);
    expect(inside, `${total - inside} outside a reduced-motion block`).toBe(total);
  });

  it("finds the blocks it claims to be reading", () => {
    /* Without this the check above passes trivially the day the media
       query is reworded and the matcher stops matching. */
    expect(reducedMotion().length).toBeGreaterThanOrEqual(3);
  });
});
