/** The three properties the guide's plumbing has to keep.
 *
 * All three are about things that fail *quietly*: a page the export never
 * writes, a chunk that quietly contains both languages, and a language
 * switch that quietly throws the reader back to the top of the guide.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { GUIDE, GUIDE_SLUGS } from "../../../content/guide/manifest";
import { GUIDE_MODULES } from "../../../content/guide/modules";
import { generateStaticParams } from "../guide/[slug]/page";

const web = join(__dirname, "..", "..", "..");
const read = (relative: string) => readFileSync(join(web, relative), "utf-8");

describe("the export knows every article (T6)", () => {
  it("builds one page per manifest entry, and no others", () => {
    expect(generateStaticParams()).toEqual(GUIDE_SLUGS.map((slug) => ({ slug })));
  });

  it("has a module for every slug, in both languages", () => {
    // A slug in the manifest with no module is a page that builds and
    // then renders nothing; a module with no manifest entry is a file
    // nobody can reach. Both are silent.
    expect(Object.keys(GUIDE_MODULES.vi).sort()).toEqual([...GUIDE_SLUGS].sort());
    expect(Object.keys(GUIDE_MODULES.en).sort()).toEqual([...GUIDE_SLUGS].sort());
  });

  it("gives every article a slug that is safe in a URL", () => {
    for (const article of GUIDE) {
      expect(article.slug).toMatch(/^[a-z0-9-]+$/);
    }
  });
});

describe("only the language being read is fetched (T8)", () => {
  const registry = read("content/guide/modules.ts");

  it("imports articles by a written path, never a built one", () => {
    // `import(`./${locale}/${slug}.mdx`)` hands the bundler a directory,
    // and it answers by packing every article of both languages into one
    // chunk. The page still works, so nothing here would go red — the
    // reader just downloads twenty-two articles to read one.
    expect(registry).not.toMatch(/import\(\s*`/);
    for (const slug of GUIDE_SLUGS) {
      expect(registry).toContain(`import("./vi/${slug}.mdx")`);
      expect(registry).toContain(`import("./en/${slug}.mdx")`);
    }
  });

  it("keeps every .mdx import dynamic, and all of them in one file", () => {
    // A static `import x from "…/overview.mdx"` anywhere else puts that
    // article in the importer's chunk regardless of what the registry
    // does.
    const sources = [
      "content/guide/manifest.ts",
      "src/app/guide/[slug]/GuideArticle.tsx",
      "src/app/guide/[slug]/page.tsx",
      "src/mdx-components.tsx",
    ];
    for (const source of sources) {
      expect(read(source)).not.toMatch(/^\s*import\s+[^(]*\.mdx"/m);
    }
    expect(registry).not.toMatch(/^\s*import\s+[^(]*\.mdx"/m);
  });

  it("calls dynamic() once per article, at module scope", () => {
    // Called during render it returns a new component type each time, so
    // React remounts the article and the skeleton flashes back.
    expect(read("src/app/guide/[slug]/GuideArticle.tsx")).not.toContain("dynamic(");
    // The options have to be spelled out at every call — the compiler
    // reads them without running the file, so a shared `const options`
    // fails the build. Counting them is what stops a later article from
    // being added without `ssr: false` and prerendering in English.
    const inline = registry.split("ssr: false,").length - 1;
    expect(inline).toBe(GUIDE_SLUGS.length * 2);
  });
});

describe("switching language does not move the reader (T9)", () => {
  it("cannot navigate: the article component has no router call", () => {
    // The slug is language-neutral and section ids are identical across
    // both files, so a language switch is a change of module and nothing
    // else. A `router.push` here would send a reader standing on
    // `/guide/gates#g2` back to the top of some other page.
    const article = read("src/app/guide/[slug]/GuideArticle.tsx");
    expect(article).not.toContain("useRouter");
    expect(article).not.toContain("router.");
    expect(article).not.toContain("window.location");
  });

  it("offers the same slugs in both languages", () => {
    // If a slug existed in one language only, switching while reading it
    // would empty the page — a 404 with none of a 404's honesty.
    expect(Object.keys(GUIDE_MODULES.vi).sort()).toEqual(Object.keys(GUIDE_MODULES.en).sort());
  });

  // What is *not* checked here: that the prose actually changes, and that
  // `router.refresh()` in the language switcher does not loop. Both need
  // a browser — this suite renders to static markup with no DOM — so they
  // are P6's manual pass on the desktop build, not a claim made here.
});
