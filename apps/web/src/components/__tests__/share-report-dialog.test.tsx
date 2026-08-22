/** Sharing the run by email, and the one thing this dialog must not do.
 *
 * **There is no email provider behind it.** The obvious build — a To
 * field, a Send button, a green tick — would be a lie the first time
 * somebody used it, and the kind that is only discovered when a reviewer
 * says they never received anything. So the last test in the first
 * block scans the source for the words that would make that claim, and
 * it is the assertion the rest of this file exists to protect.
 *
 * Source-level like the other page tests: the dialog sits behind a fetch
 * for the attachment, so a first paint would only show a loading state.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const COMPONENTS = join(process.cwd(), "src", "components");
const DIALOG = readFileSync(join(COMPONENTS, "ShareReportDialog.tsx"), "utf8");
const DETAIL = readFileSync(
  join(process.cwd(), "src", "app", "decisions", "[id]", "page.tsx"),
  "utf8",
);
const CSS = readFileSync(join(process.cwd(), "src", "app", "globals.css"), "utf8");
const REPORTS = readFileSync(join(process.cwd(), "src", "lib", "reports.ts"), "utf8");

const EN = en as Record<string, string>;
const VI = vi as Record<string, string>;

describe("it does not pretend to have sent anything", () => {
  it("names the action for what it is", () => {
    expect(EN["share.openClient"]).toBe("Open email client");
    expect(VI["share.openClient"]).toBe("Mở ứng dụng email");
  });

  it("says out loud that no provider is connected", () => {
    expect(EN["share.demoNotice"]).toContain("No email provider is connected");
    expect(EN["share.demoNotice"]).toContain("nothing is sent from here");
    expect(VI["share.demoNotice"]).toContain("Chưa nối nhà cung cấp email");
  });

  it("confirms the client opened rather than that the mail went", () => {
    expect(EN["share.opened"]).toContain("email client is open");
    expect(EN["share.opened"]).not.toMatch(/\bsent\b/i);
    expect(VI["share.opened"]).not.toContain("Đã gửi");
  });

  it("has no button, label or state anywhere that claims a send", () => {
    /* The assertion the rest of this file exists to protect. A future
       edit that adds a `setSent(true)` or a "Sent" label fails here
       before it reaches a reader who then believes the mail went. */
    const claims = /\b(sent|isSent|setSent|đã gửi|Đã gửi)\b/;
    expect(DIALOG).not.toMatch(claims);

    /* One exception, named rather than pattern-matched around: the
       banner uses the word to *deny* it. Asserting the denial keeps the
       exemption from quietly widening into a claim. */
    expect(EN["share.demoNotice"]).toContain("nothing is sent from here");
    expect(VI["share.demoNotice"]).toContain("không có gì được gửi đi từ đây");

    for (const key of Object.keys(EN).filter((entry) => entry.startsWith("share."))) {
      if (key === "share.demoNotice") continue;
      expect(EN[key], key).not.toMatch(/\bsent\b/i);
      expect(VI[key], key).not.toContain("Đã gửi");
    }
  });

  it("tells the reader the file is not attached and hands it over", () => {
    /* `mailto:` cannot carry a file. Saying so, and putting the download
       one click away, is the difference between a workaround and a trap. */
    expect(EN["share.openedAttachHint"]).toContain("cannot carry a file");
    expect(DIALOG).toContain("saveBlob(file.blob, file.filename)");
  });
});

describe("the dialog is an overlay, not a page", () => {
  it("is a labelled modal that Escape and the backdrop close", () => {
    expect(DIALOG).toContain('role="dialog"');
    expect(DIALOG).toContain('aria-modal="true"');
    expect(DIALOG).toContain("aria-label={t(\"share.title\")}");
    /* The same hook the drawer and every menu use — one written
       separately is one that ends up missing the Escape key. */
    expect(DIALOG).toContain("useDismiss(true, onClose, dialog)");
  });

  it("does not navigate", () => {
    expect(DIALOG).not.toContain("useRouter");
    expect(DIALOG).not.toContain("<Link");
  });

  it("focuses the first field it wants filled", () => {
    expect(DIALOG).toContain("autoFocus");
  });
});

describe("addresses", () => {
  it("splits on the separators people actually paste", () => {
    expect(DIALOG).toContain("/[,;\\s]+/");
    expect(DIALOG).toContain('event.key === "Enter"');
  });

  it("keeps the check loose enough not to refuse a working address", () => {
    /* A stricter pattern rejects plus-tags, quoted locals and new
       top-level domains. A form that refuses a real address is worse
       than one that lets a typo through to a bounce the sender sees. */
    expect(DIALOG).toContain("/^\\S+@\\S+\\.\\S+$/");
  });

  it("marks the bad chip rather than the whole field", () => {
    expect(DIALOG).toContain("share-chip--invalid");
    expect(DIALOG).toContain("aria-invalid");
    expect(CSS).toContain(".share-chip--invalid");
  });

  it("refuses to open the client with no recipient", () => {
    expect(DIALOG).toContain("const ready = addresses.length > 0 && invalid.length === 0");
    expect(DIALOG).toContain("disabled={!ready}");
    expect(EN["share.needRecipient"]).toBeTruthy();
  });

  it("drops an address repeated between To and CC without complaining", () => {
    expect(DIALOG).toContain("(entry) => !addresses.includes(entry)");
  });
});

describe("what is being sent", () => {
  it("states the real size, which means holding the real bytes", () => {
    /* There is no honest way to state a size without the file. Fetching
       it also makes the download button free — nothing is fetched twice. */
    expect(DIALOG).toContain("fetchDecisionWorkbook(runId, locale)");
    expect(DIALOG).toContain("formatSize(file.blob.size)");
    expect(REPORTS).toContain("export function fetchDecisionWorkbook");
  });

  it("names the file the export would actually save", () => {
    expect(DIALOG).toContain("file.filename");
  });

  it("disables the link option with a reason instead of failing on click", () => {
    expect(DIALOG).toContain('title={t("share.linkUnavailableWhy")}');
    expect(DIALOG).toContain("disabled readOnly");
    expect(EN["share.linkUnavailableWhy"]).toContain("no share link");
  });

  it("prefills subject and message and leaves both editable", () => {
    expect(DETAIL).toContain("function sharePrefill(");
    expect(DIALOG).toContain("setSubject(event.target.value)");
    expect(DIALOG).toContain("setMessage(event.target.value)");
    /* Blur restores the default rather than sending an empty subject. */
    expect(DIALOG).toContain("setSubject(initialSubject)");
  });

  it("writes the unranked case as its own sentence", () => {
    /* "Recommended: not measured" reads as a broken template. "Nobody
       was ranked, here is why" is the actual result. */
    expect(DETAIL).toContain('t("share.subjectPrefillUnranked"');
    expect(EN["share.messagePrefillUnranked"]).toContain("no recommendation");
  });
});

describe("a message longer than a mailto can carry", () => {
  it("cuts it visibly rather than silently", () => {
    /* Silent truncation is text lost with nobody told. */
    expect(DIALOG).toContain("const MAILTO_LIMIT");
    expect(DIALOG).toContain("t(\"share.bodyTruncated\")");
    expect(EN["share.bodyTruncated"]).toContain("truncated");
  });

  it("offers the full text another way", () => {
    expect(DIALOG).toContain("navigator.clipboard?.writeText(body)");
    expect(EN["share.copyBody"]).toBeTruthy();
  });
});

describe("where the button lives", () => {
  it("sits beside the export buttons, not behind a menu", () => {
    /* Sending the run on is the same kind of act as saving it, at the
       same moment — the reader has just decided it is worth passing on. */
    const block = DETAIL.slice(
      DETAIL.indexOf('<div className="decision-export">'),
      DETAIL.indexOf("function ObservationNotice"),
    );
    expect(block).toContain('t("share.button")');
    expect(block).toContain("<ShareReportDialog");
  });
});

describe("both languages", () => {
  it("carries every share string in Vietnamese as well as English", () => {
    const missing = Object.keys(EN)
      .filter((key) => key.startsWith("share."))
      .filter((key) => !VI[key]);
    expect(missing).toEqual([]);
  });

  it("keeps the placeholders identical across the two", () => {
    const holes = (value: string) => (value.match(/\{\w+\}/g) ?? []).sort();
    for (const key of Object.keys(EN).filter((entry) => entry.startsWith("share."))) {
      expect(holes(VI[key]), key).toEqual(holes(EN[key]));
    }
  });
});

describe("styling", () => {
  it("takes its spacing and colour from the palette", () => {
    const block = CSS.slice(CSS.indexOf(".share-modal"), CSS.indexOf(".conclusion-bar"));
    expect(block).toContain("var(--space-");
    expect(block).toContain("var(--border)");
    expect(block).not.toMatch(/#[0-9a-f]{3,8}\b/i);
  });
});
