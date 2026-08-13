import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** Phase B — the replanning switch on the benchmark form.
 *
 * It used to be on `/simulate` too. That page became the test bench,
 * whose whole value is that what you watch is what a comparison will
 * run — and `run_contract_episode` runs with replanning off, so a switch
 * there would offer a stack no measured episode uses. The claim did not
 * disappear with the switch: it moved, inverted, to
 * `test-bench.test.tsx`, which asserts the control is **absent** and
 * says why.
 *
 * Node without jsdom, so these are source-level assertions like the other
 * page tests. They pin the three things a refactor is most likely to
 * lose, each of which fails silently rather than loudly:
 *
 *  1. The rule actually reaches the request body. A switch wired to
 *     nothing looks identical on screen.
 *  2. It defaults to off. Replanning changes what the global planner is
 *     allowed to see (P02), so nobody may end up with it on by inheriting
 *     a remembered form state.
 *  3. The user is told the run will be slow. A blocked robot waits out
 *     the whole stuck window before it gets a new path, and unexplained
 *     that reads as the app having frozen.
 */

const APP = join(__dirname, "..");
const CONTROLS = readFileSync(
  join(APP, "..", "components", "ReplanningControls.tsx"),
  "utf8",
);
const BENCHMARKS = readFileSync(join(APP, "benchmarks", "page.tsx"), "utf8");
const API = readFileSync(join(APP, "..", "lib", "api.ts"), "utf8");
const EN = JSON.parse(
  readFileSync(join(APP, "..", "lib", "i18n", "locales", "en.json"), "utf8"),
) as Record<string, string>;
const VI = JSON.parse(
  readFileSync(join(APP, "..", "lib", "i18n", "locales", "vi.json"), "utf8"),
) as Record<string, string>;

const KEYS = [
  "replanning.enable",
  "replanning.hint",
  "replanning.maxReplans",
  "replanning.slowWarning",
  "replanning.benchmarkScope",
  "metrics.replanCount",
  "detail.replanAt",
];

describe("both pages use one control, not two copies", () => {
  it("is rendered by the benchmark form", () => {
    expect(BENCHMARKS).toContain("<ReplanningControls");
  });

  it("tells the benchmark form it is a sweep-wide rule", () => {
    /* The component still distinguishes the two scopes — a per-run
       simulation and a sweep-wide rule are different promises and the
       copy differs accordingly. One caller uses it today; that is a
       caller count, not a reason to collapse the distinction. */
    expect(BENCHMARKS).toContain('scope="benchmark"');
    expect(CONTROLS).toContain("replanning.benchmarkScope");
  });
});

describe("the switch is off unless somebody turns it on", () => {
  it("the benchmark form initialises to NO_REPLANNING", () => {
    expect(BENCHMARKS).toContain("useState<ReplanningConfig>(NO_REPLANNING)");
  });

  it("NO_REPLANNING is disabled with no budget", () => {
    expect(CONTROLS).toContain(
      "export const NO_REPLANNING: ReplanningConfig = { enabled: false, max_replans: 0 };",
    );
  });

  it("the form does not persist the choice across loads", () => {
    // `persisted.ts` is how this app remembers a setting. Replanning
    // must not be remembered — see the P02 reasoning above.
    expect(BENCHMARKS).not.toMatch(/persisted[\s\S]{0,200}replanning/i);
  });

  it("a disabled rule is omitted from the payload rather than sent", () => {
    // Sending `{enabled: false}` would be harmless today, but omitting
    // it is what keeps an untouched form from ever changing a
    // benchmark's conditions checksum.
    expect(API).toContain("...(replanning?.enabled ? { replanning } : {})");
    expect(BENCHMARKS).toContain("...(replanning.enabled ? { replanning } : {})");
  });
});

describe("the rule reaches the server", () => {
  it("createSimulation takes it and puts it in the body", () => {
    expect(API).toMatch(/createSimulation:.*replanning\?: ReplanningConfig/s);
  });

  it("createSimulation still accepts one, because the old flow sends it", () => {
    /* `/benchmarks` is still live and still the only page with the
       switch. The client keeping the parameter is what lets that page
       work unchanged while the test bench deliberately never sends
       one. */
    expect(API).toContain("...(replanning?.enabled ? { replanning } : {})");
  });
});

describe("turning it on cannot produce a switch that does nothing", () => {
  it("enabling carries a budget of at least one", () => {
    // The server rejects enabled with a budget of zero. The UI must not
    // be able to construct that state at all.
    expect(CONTROLS).toContain("max_replans: Math.max(1, value.max_replans)");
    expect(CONTROLS).toContain('min={1}');
  });
});

describe("the cost is stated before the run, not discovered during it", () => {
  it("the warning renders only while the switch is on", () => {
    expect(CONTROLS).toMatch(/value\.enabled \?[\s\S]*replanning\.slowWarning/);
  });

  it("every key exists in both locales", () => {
    for (const key of KEYS) {
      expect(EN[key], `en.json missing ${key}`).toBeTruthy();
      expect(VI[key], `vi.json missing ${key}`).toBeTruthy();
    }
  });
});
