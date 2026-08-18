"use client";

/* The paper reader, mounted in two places on purpose.
 *
 * It lives on the assistant page because that is where a person looking
 * for "the AI reads my document" goes first, and it lives on the
 * candidates page because that is where the reading turns into a
 * registered candidate. One component, two entrances — the alternative
 * was a feature nobody could find from the page named after it.
 */

import { useRef, useState } from "react";

import { PluginDraftView } from "@/components/PluginDraftView";
import {
  draftPluginFromPaper,
  draftPluginFromPaperFile,
  extractCandidateFromPaper,
  extractCandidateFromPaperFile,
} from "@/lib/decisions";
import type { PaperExtraction, PluginDraft } from "@/lib/decisions";
import { useTranslation } from "@/lib/i18n";


/** Recover a candidate from what a paper reports.
 *
 * **Nothing here registers anything, and the separation is the point.**
 * The panel produces a reading of the paper; the form above registers a
 * candidate. Joining them into one button would hide the step where a
 * person checks that this is what the paper actually said, and every
 * number downstream would then rest on an extraction nobody read.
 *
 * Three parts of the output earn their space by being uncomfortable:
 * what the paper never stated, what this platform cannot express, and
 * how many quoted sentences turned out not to be in the text. A reading
 * that showed only the parameters it found would look far more complete
 * than it is.
 */
/** Kept beside the server's own list in `paper.SUPPORTED_UPLOADS`. The
 * browser filter is a courtesy; the server is the one that refuses. */
export const PAPER_FILE_TYPES = ".pdf,.txt,.md,.tex";

/** Kept level with `MAX_UPLOAD_BYTES` in the upload route.
 *
 * Checked in the browser as well as on the server, because the server
 * can only answer after the whole file has crossed the wire and been
 * spooled — which for a mis-picked video is minutes of upload to earn a
 * refusal that `file.size` gives instantly. */
export const MAX_PAPER_BYTES = 20 * 1024 * 1024;

/** Level with `MAX_PAPER_CHARS` on the server. Enforced on the textarea
 *  so a long paste stops at the limit instead of being accepted and
 *  then refused with a bare "invalid request" that names nothing. */
export const MAX_PAPER_CHARS = 60_000;

export function FromPaperPanel({ enabled }: { enabled: boolean }) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [result, setResult] = useState<PaperExtraction | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<string | null>(null);
  /* The source of the last successful read, kept so the plugin path can
     re-read the same document. The platform stores no paper, so if this
     component forgot it, "draft a plugin from that paper" would mean
     finding the file in the dialog again. */
  const [lastSource, setLastSource] = useState<{ file?: File; text?: string } | null>(null);
  const [plugin, setPlugin] = useState<PluginDraft | null>(null);
  const [building, setBuilding] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  // Both entry points funnel here so an upload and a paste cannot drift
  // into producing different-looking results from the same paper.
  async function run(read: () => Promise<PaperExtraction>) {
    setBusy(true);
    setError(null);
    // Cleared before the attempt, not after it succeeds. Leaving it
    // meant a failed second upload rendered the *previous* paper's
    // parameter table under the new file's name, above a notice telling
    // the reader to register it — the exact misattribution every quote
    // in that table exists to prevent.
    setResult(null);
    setPlugin(null);
    try {
      setResult(await read());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File) {
    if (file.size > MAX_PAPER_BYTES) {
      setResult(null);
      setUploaded(file.name);
      setError(t("paper.tooBig", { limit: String(MAX_PAPER_BYTES / (1024 * 1024)) }));
      return;
    }
    setUploaded(file.name);
    setText("");
    setLastSource({ file });
    await run(() => extractCandidateFromPaperFile(file));
  }

  return (
    <div className="panel">
      <h3>{t("paper.title")}</h3>
      <p className="muted">{t("paper.subtitle")}</p>

      <div className="toolbar">
        <input
          ref={picker}
          type="file"
          accept={PAPER_FILE_TYPES}
          style={{ display: "none" }}
          data-testid="paper-file"
          onChange={(event) => {
            const file = event.target.files?.[0];
            // Cleared so picking the same file twice fires again — a
            // reader who re-uploads after an error expects a retry.
            event.target.value = "";
            if (file) void upload(file);
          }}
        />
        <button disabled={!enabled || busy} onClick={() => picker.current?.click()}>
          {t("paper.upload")}
        </button>
        <span className="muted">
          {uploaded ? <code>{uploaded}</code> : t("paper.uploadHint")}
        </span>
      </div>

      <label className="field">
        {t("paper.text")}
        <textarea
          rows={8}
          value={text}
          maxLength={MAX_PAPER_CHARS}
          onChange={(event) => {
            setText(event.target.value);
            setUploaded(null);
          }}
          placeholder={t("paper.placeholder")}
          disabled={!enabled}
        />
      </label>

      <div className="toolbar">
        <button
          className="primary"
          disabled={!enabled || busy || !text.trim()}
          onClick={() => {
            setLastSource({ text });
            void run(() => extractCandidateFromPaper(text));
          }}
        >
          {busy ? t("paper.reading") : t("paper.read")}
        </button>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {result ? <PaperResult result={result} /> : null}

      {/* The way forward when the extractor refused: the Algorithm Host
          takes new methods as plugin bundles, so the same paper can be
          drafted into one. Offered whenever a read happened — a person
          may want the plugin even for a method a stack approximates —
          but it is the no-stack case this exists for. */}
      {result && lastSource ? (
        <div style={{ marginTop: 10 }}>
          <button
            type="button"
            disabled={building}
            onClick={() => {
              setBuilding(true);
              setError(null);
              const read = lastSource.file
                ? draftPluginFromPaperFile(lastSource.file)
                : draftPluginFromPaper(lastSource.text ?? "");
              read
                .then(setPlugin)
                .catch((caught) =>
                  setError(caught instanceof Error ? caught.message : String(caught)),
                )
                .finally(() => setBuilding(false));
            }}
          >
            {building ? t("plugin.building") : t("plugin.build")}
          </button>
          {!result.stack ? (
            <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>
              {t("plugin.newMethod")}
            </span>
          ) : null}
        </div>
      ) : null}
      {plugin ? (
        <div style={{ marginTop: 10 }}>
          <PluginDraftView draft={plugin} />
        </div>
      ) : null}
    </div>
  );
}

/** The reading itself, without the box around it.
 *
 * Exported because the assistant renders the same result inside a chat
 * bubble. Two renderings of one extraction would drift, and the reader
 * would have no way to know which one omitted something. */
export function PaperResult({ result }: { result: PaperExtraction }) {
  const { t } = useTranslation();

  if (result.refused) {
    return <div className="notice">{t("paper.refused")}: {result.refused}</div>;
  }

  return (
    <>
      {result.stack ? (
        <p>
          {t("paper.mapsTo")}: <code>{result.stack}</code>
          {result.candidate_id ? (
            <>
              {" · "}
              {t("paper.wouldRegisterAs")} <code>{result.candidate_id}</code>
            </>
          ) : null}
        </p>
      ) : (
        /* No stack is a verdict, not an empty result. Substituting the
           nearest planner would answer a different question. */
        <div className="notice">{t("paper.noStack")}</div>
      )}

      {result.errors.length > 0 ? (
        <div className="error-box">
          {t("paper.wouldNotValidate")}
          <ul>
            {result.errors.map((message, index) => (
              <li key={index}>{message}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Louder than the quote count, because it is the failure a reader
          cannot detect by looking: the parameters shown are real, and
          the ones in the missing third are simply absent. */}
      {result.chars_total > result.chars_read ? (
        <div className="error-box">
          {t("paper.truncated", {
            read: String(result.chars_read),
            total: String(result.chars_total),
          })}
        </div>
      ) : null}

      {result.unquoted > 0 ? (
        <div className="notice">
          {t("paper.unquoted", { count: String(result.unquoted) })}
        </div>
      ) : null}

      {result.parameters.length > 0 ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("paper.parameter")}</th>
                <th>{t("paper.value")}</th>
                <th>{t("paper.fromSentence")}</th>
              </tr>
            </thead>
            <tbody>
              {result.parameters.map((parameter) => (
                <tr key={parameter.name}>
                  <td>
                    <code>{parameter.name}</code>
                  </td>
                  <td className="num">{String(parameter.value)}</td>
                  <td>
                    <span className="muted">“{parameter.quote}”</span>
                    {parameter.note ? (
                      <>
                        <br />
                        <span className="muted" style={{ fontSize: 11 }}>
                          {parameter.note}
                        </span>
                      </>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {result.assumptions.length > 0 ? (
        <>
          <h4>{t("paper.assumptions")}</h4>
          <p className="muted" style={{ fontSize: 12 }}>{t("paper.assumptionsWhy")}</p>
          <ul>
            {result.assumptions.map((item, index) => (
              <li key={index} className="muted">
                {item}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {result.not_representable.length > 0 ? (
        <>
          <h4>{t("paper.notRepresentable")}</h4>
          <ul>
            {result.not_representable.map((item, index) => (
              <li key={index} className="muted">
                {item}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {result.claimed_conditions ? (
        <p className="muted" style={{ fontSize: 12 }}>
          {t("paper.claimedUnder")}: {result.claimed_conditions}
        </p>
      ) : null}

      <div className="notice">{t("paper.nextStep")}</div>
    </>
  );
}
