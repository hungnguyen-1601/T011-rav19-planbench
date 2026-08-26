/** Deep links into the three routes the export cannot name.
 *
 * `/decisions/<id>` has no file of its own: the export writes one shell
 * under the sentinel and the API answers every id with it. So a reload
 * lands on a page whose router says the id is `_`, and the real id has
 * to come back out of the address bar. These two properties are what
 * make that work, and both are pure functions — the hook around them is
 * five lines of wiring, asserted on separately below.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  ROUTE_ID_SENTINEL,
  routeIdFromPathname,
  shellParams,
} from "@/lib/routeShell";

describe("the sentinel", () => {
  it("is the id the API expects each shell to be built under", () => {
    /* `SENTINEL` in apps/api/planbench_api/static_site.py. The two are
       one contract with no compiler between them: if this side changes,
       a deep link starts 404ing at runtime and nothing fails earlier. */
    const server = readFileSync(
      join(process.cwd(), "..", "api", "planbench_api", "static_site.py"),
      "utf8",
    );
    expect(server).toContain(`SENTINEL = "${ROUTE_ID_SENTINEL}"`);
  });

  it("is what generateStaticParams asks for, once", () => {
    expect(shellParams()).toEqual([{ id: ROUTE_ID_SENTINEL }]);
  });

  it("covers exactly the routes the API serves shells for", () => {
    const server = readFileSync(
      join(process.cwd(), "..", "api", "planbench_api", "static_site.py"),
      "utf8",
    );
    for (const route of ["decisions", "maps", "scenarios"]) {
      const page = readFileSync(
        join(process.cwd(), "src", "app", route, "[id]", "page.tsx"),
        "utf8",
      );
      expect(page, `${route} must export a shell`).toContain("generateStaticParams");
      expect(server, `${route} must be served as a shell`).toContain(`"${route}"`);
    }
  });
});

describe("reading the id back out of the path", () => {
  it("takes the last segment", () => {
    expect(routeIdFromPathname("/decisions/20750b0d9dbe")).toBe("20750b0d9dbe");
    expect(routeIdFromPathname("/maps/warehouse-a")).toBe("warehouse-a");
  });

  it("ignores a trailing slash, since the export can be served either way", () => {
    expect(routeIdFromPathname("/scenarios/aisle-3/")).toBe("aisle-3");
  });

  it("drops a query and a hash rather than making them part of the id", () => {
    expect(routeIdFromPathname("/decisions/abc?tab=gates")).toBe("abc");
    expect(routeIdFromPathname("/decisions/abc#evidence")).toBe("abc");
  });

  it("decodes what the browser encoded", () => {
    expect(routeIdFromPathname("/maps/warehouse%20a")).toBe("warehouse a");
  });

  it("gives nothing back for a path with no id, rather than a wrong one", () => {
    /* `""` is the value the pages guard their fetches on. Returning the
       route name here would send them looking for a record called
       "decisions". */
    expect(routeIdFromPathname("/")).toBe("");
  });
});

describe("the hook that uses them", () => {
  const HOOK = readFileSync(join(process.cwd(), "src", "lib", "useRouteId.ts"), "utf8");

  it("reads the address bar in an effect, never while rendering", () => {
    /* The shipped HTML was prerendered with the sentinel. Reading
       `location` during render makes the first client render disagree
       with the file it is hydrating, and React answers that by throwing
       the tree away and rendering everything again. */
    const effect = HOOK.slice(HOOK.indexOf("useEffect(() => {"), HOOK.indexOf("}, [servedFromShell])"));
    expect(effect).toContain("window.location.pathname");
    expect(HOOK.slice(0, HOOK.indexOf("useEffect(() => {"))).not.toContain("window.location");
  });

  it("only consults the address bar when the router says the shell served it", () => {
    /* On a client-side navigation the router already has the real id,
       and preferring the URL there would be a second source of truth
       for the same thing. */
    expect(HOOK).toContain("const servedFromShell = routed === ROUTE_ID_SENTINEL;");
    expect(HOOK).toContain("return servedFromShell ? fromLocation : routed;");
  });

  it("reports nothing rather than the sentinel while it resolves", () => {
    /* So a page can write `if (!id) return;` and never ask the API for
       a record called `_`. */
    expect(HOOK).toContain('const [fromLocation, setFromLocation] = useState("");');
  });

  it("is guarded by every page that fetches on the id", () => {
    for (const [route, file] of [
      ["decisions", "DecisionDetail.tsx"],
      ["maps", "MapEditor.tsx"],
      ["scenarios", "ScenarioEditor.tsx"],
    ]) {
      const source = readFileSync(
        join(process.cwd(), "src", "app", route, "[id]", file),
        "utf8",
      );
      expect(source, `${route} must use the hook`).toContain("useRouteId()");
      expect(source, `${route} must guard on the id`).toMatch(/if \(!(id|scenarioId)\) return;/);
    }
  });
});
