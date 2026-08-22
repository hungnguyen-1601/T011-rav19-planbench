"use client";

/** Downloading the Markdown report (F09).
 *
 * Not an `<a href>`. The export is authenticated like every other read
 * and the token lives in an `Authorization` header, which a plain link
 * cannot send — a link would either 401 or force the token into the URL,
 * where it would end up in history and in every proxy log on the way.
 *
 * So the browser fetches the body itself, turns it into a Blob, and
 * drives a synthetic anchor. The object URL is always revoked — a Blob
 * that is still referenced is held for the life of the document, and
 * somebody exporting twenty reports to compare them would keep all
 * twenty — but revoked on the next tick rather than immediately, because
 * some browsers have not started reading the URL by the time `click()`
 * returns and would save an empty file.
 */

import { API_BASE } from "./api";
import { clearSession, loadSession } from "./auth";
import { filenameFromDisposition } from "./charts";

/** Fetch a Markdown report and save it. Throws with the API's message.
 *
 * Takes the path rather than an id: the mechanism — authenticated fetch,
 * Blob, synthetic anchor, revoked object URL — is the same wherever the
 * document comes from, and it was written once for benchmarks. That flow
 * retired; this did not.
 */
export async function downloadReportMarkdown(path: string, fallbackName: string): Promise<string> {
  const session = loadSession();
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    headers: session ? { Authorization: `Bearer ${session.token}` } : {},
    cache: "no-store",
  });
  if (!response.ok) {
    if (response.status === 401) clearSession();
    let message = response.statusText;
    try {
      const body = await response.json();
      message = body?.error?.message ?? message;
    } catch {
      // The error body is JSON even though the success body is not; a
      // non-JSON failure keeps the status text.
    }
    throw new Error(message);
  }
  const filename = filenameFromDisposition(
    response.headers.get("content-disposition"),
    fallbackName,
  );
  const url = URL.createObjectURL(await response.blob());
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  return filename;
}

/** The selection run as Markdown — every run, ranked or not.
 *
 * Available before approval on purpose: this describes what was
 * measured, and reading it is the act approval follows (HĐ-14).
 */
export function downloadDecisionReport(runId: string): Promise<string> {
  return downloadReportMarkdown(`/decisions/${encodeURIComponent(runId)}/report.md`, runId);
}
