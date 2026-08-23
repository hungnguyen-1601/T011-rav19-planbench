/** Copying the run's id, and what the button says afterwards.
 *
 * **The write function comes in as a parameter.** Reaching for
 * `navigator.clipboard` inside would put the only interesting part of
 * this — what happens when the write is refused — behind a global that
 * does not exist in Node, and this repo has no jsdom, so it would be
 * behind nothing a test can reach.
 *
 * Refusal is ordinary, not exceptional. The clipboard API rejects
 * outside a secure context, when the document is not focused, and
 * whenever the permission is denied; a page opened from `file://` fails
 * every time. So the failure has an outcome rather than an exception,
 * and the caller renders it.
 */

export type CopyOutcome = "copied" | "failed";

/** Never rejects. A rejected promise here would surface as an unhandled
 *  rejection in the console of a page whose only fault was that the
 *  reader has clipboard access switched off. */
export async function copyDecisionId(
  id: string,
  write: (text: string) => Promise<void>,
): Promise<CopyOutcome> {
  try {
    await write(id);
    return "copied";
  } catch {
    return "failed";
  }
}

/** How long the button stays changed before returning to its label.
 *
 * Long enough to be read, short enough that a reader who copies twice
 * sees the second confirmation as a new event rather than as the first
 * one still lingering.
 */
export const COPY_FEEDBACK_MS = 4000;

/** The key the button shows for each state. `null` while idle — the
 *  button then shows the id and nothing else. */
export function copyStateKey(outcome: CopyOutcome | null): string | null {
  if (outcome === "copied") return "decisions.detail.copied";
  if (outcome === "failed") return "decisions.detail.copyFailed";
  return null;
}
