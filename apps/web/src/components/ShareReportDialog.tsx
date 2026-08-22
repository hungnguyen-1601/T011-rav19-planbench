"use client";

/** Handing the run to somebody by email, without pretending to send it.
 *
 * **There is no email provider behind this, and the dialog says so.**
 * The obvious build — a To field, a Send button, a green tick — would be
 * a lie the first time somebody used it, and the kind of lie that is
 * only discovered when a reviewer says they never received anything. So
 * the button opens the reader's own mail client with everything filled
 * in, the banner above it explains that, and the confirmation says "the
 * email client is open", never a claim that the mail went.
 *
 * The attachment is fetched rather than described. Stating a size is a
 * claim, and the only honest way to make it is to hold the bytes — which
 * also means the "download it" button costs nothing, because `mailto:`
 * cannot carry a file and the reader has to attach it themselves.
 */

import { useEffect, useRef, useState } from "react";

import { useTranslation } from "@/lib/i18n";
import { fetchDecisionWorkbook, saveBlob, type FetchedReport } from "@/lib/reports";
import { useDismiss } from "@/lib/useDismiss";

/** Deliberately loose. A stricter pattern rejects addresses that are
 *  legal under RFC 5322 — plus-tags, quoted locals, new top-level
 *  domains — and a form that refuses a working address is worse than one
 *  that lets a typo through to a bounce the sender will see. */
const LOOKS_LIKE_EMAIL = /^\S+@\S+\.\S+$/;

/** What one `mailto:` can carry before clients start truncating. Not a
 *  standard: IE capped at 2083 and several clients still sit near there,
 *  so this is the conservative floor rather than any one limit. */
const MAILTO_LIMIT = 1800;

function splitAddresses(raw: string): string[] {
  return raw
    .split(/[,;\s]+/)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Recipients {
  /** Chips already committed. */
  addresses: string[];
  /** What is still being typed. */
  draft: string;
}

const EMPTY: Recipients = { addresses: [], draft: "" };

function AddressField({
  label,
  value,
  onChange,
  invalidLabel,
  autoFocus,
  disabled,
}: {
  label: string;
  value: Recipients;
  onChange: (next: Recipients) => void;
  invalidLabel: string;
  autoFocus?: boolean;
  disabled?: boolean;
}) {
  const commit = (raw: string) => {
    const found = splitAddresses(raw);
    if (found.length === 0) return onChange({ ...value, draft: "" });
    // Pasting a whole list splits in one go rather than one chip per
    // keystroke — the commonest way these get filled in is a paste.
    const merged = [...value.addresses];
    for (const entry of found) if (!merged.includes(entry)) merged.push(entry);
    onChange({ addresses: merged, draft: "" });
  };

  return (
    <div className="field share-field">
      <span>{label}</span>
      <div className="share-chips">
        {value.addresses.map((address) => {
          const bad = !LOOKS_LIKE_EMAIL.test(address);
          return (
            <span
              key={address}
              className={bad ? "share-chip share-chip--invalid" : "share-chip"}
              title={bad ? invalidLabel : undefined}
              aria-invalid={bad || undefined}
            >
              {address}
              <button
                type="button"
                aria-label={`${invalidLabel} ${address}`}
                disabled={disabled}
                onClick={() =>
                  onChange({
                    ...value,
                    addresses: value.addresses.filter((entry) => entry !== address),
                  })
                }
              >
                ×
              </button>
            </span>
          );
        })}
        <input
          type="text"
          value={value.draft}
          autoFocus={autoFocus}
          disabled={disabled}
          onChange={(event) => onChange({ ...value, draft: event.target.value })}
          onBlur={(event) => commit(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === "," || event.key === " ") {
              event.preventDefault();
              commit(value.draft);
            }
          }}
        />
      </div>
    </div>
  );
}

export function ShareReportDialog({
  runId,
  subject: initialSubject,
  message: initialMessage,
  onClose,
}: {
  runId: string;
  subject: string;
  message: string;
  onClose: () => void;
}) {
  const { t, locale } = useTranslation();
  const [to, setTo] = useState<Recipients>(EMPTY);
  const [cc, setCc] = useState<Recipients>(EMPTY);
  const [showCc, setShowCc] = useState(false);
  const [subject, setSubject] = useState(initialSubject);
  const [message, setMessage] = useState(initialMessage);
  const [attach, setAttach] = useState(true);
  const [file, setFile] = useState<FetchedReport | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [handedOff, setHandedOff] = useState(false);
  const dialog = useRef<HTMLDivElement>(null);

  useDismiss(true, onClose, dialog);

  // Fetched once when the dialog opens, not when the box is ticked: the
  // size is part of what the reader is being asked to confirm, so it has
  // to be on screen before they decide.
  useEffect(() => {
    let live = true;
    fetchDecisionWorkbook(runId, locale)
      .then((fetched) => live && setFile(fetched))
      .catch((caught) => {
        if (!live) return;
        setFileError(caught instanceof Error ? caught.message : String(caught));
      });
    return () => {
      live = false;
    };
  }, [runId, locale]);

  const addresses = [...to.addresses, ...splitAddresses(to.draft)];
  const ccAddresses = [...cc.addresses, ...splitAddresses(cc.draft)].filter(
    (entry) => !addresses.includes(entry),
  );
  const invalid = [...addresses, ...ccAddresses].filter(
    (entry) => !LOOKS_LIKE_EMAIL.test(entry),
  );
  const ready = addresses.length > 0 && invalid.length === 0;

  const body = attach && file ? `${message}\n\n${t("share.bodyAttachNote")}` : message;
  const truncated = body.length > MAILTO_LIMIT;
  // Named for what it is — the text handed to the client — rather than
  // for an act that does not happen here. A variable claiming a send is
  // the first step towards a label claiming one.
  const handoffBody = truncated
    ? `${body.slice(0, MAILTO_LIMIT)}\n${t("share.bodyTruncated")}`
    : body;

  const open = () => {
    const query = new URLSearchParams({ subject, body: handoffBody });
    if (ccAddresses.length > 0) query.set("cc", ccAddresses.join(","));
    window.location.href = `mailto:${addresses.join(",")}?${query.toString()}`;
    setHandedOff(true);
  };

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={t("share.title")}
    >
      <div className="modal share-modal" ref={dialog}>
        <h3 style={{ marginTop: 0 }}>{t("share.title")}</h3>

        {handedOff ? (
          <>
            {/* Never a claim that the mail went. Nothing here posted
                anything: the reader's own client is open with the text
                in it, and the file is still on this side of the
                handoff. */}
            <p>{t("share.opened")}</p>
            <p className="muted" style={{ fontSize: 12 }}>
              {t("share.openedAttachHint")}
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              {file ? (
                <button
                  className="primary"
                  type="button"
                  onClick={() => saveBlob(file.blob, file.filename)}
                >
                  {t("share.downloadFile")}
                </button>
              ) : null}
              <button type="button" onClick={onClose}>
                {t("common.close")}
              </button>
            </div>
          </>
        ) : (
          <>
            {fileError ? <div className="error-box">{fileError}</div> : null}

            <AddressField
              label={t("share.to")}
              value={to}
              onChange={setTo}
              invalidLabel={t("share.invalidAddress")}
              autoFocus
            />
            {showCc ? (
              <AddressField
                label={t("share.cc")}
                value={cc}
                onChange={setCc}
                invalidLabel={t("share.invalidAddress")}
              />
            ) : (
              <button type="button" onClick={() => setShowCc(true)}>
                {t("share.addCc")}
              </button>
            )}

            <label className="field">
              {t("share.subject")}
              <input
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
                onBlur={() => !subject.trim() && setSubject(initialSubject)}
              />
            </label>

            <label className="field">
              {t("share.message")}
              <textarea
                rows={5}
                value={message}
                onChange={(event) => setMessage(event.target.value)}
              />
            </label>

            <fieldset className="share-attachments">
              <legend>{t("share.attachments")}</legend>
              <label>
                <input
                  type="checkbox"
                  checked={attach}
                  onChange={(event) => setAttach(event.target.checked)}
                  disabled={file === null}
                />
                <span>{t("share.attachExcel")}</span>
                <span className="muted">
                  {file
                    ? `${file.filename} · ${formatSize(file.blob.size)}`
                    : fileError
                      ? t("share.attachUnavailable")
                      : t("share.attachLoading")}
                </span>
              </label>
              {/* Disabled with a reason rather than clickable and then
                  refused. There is no share link to grant access to, so
                  the checkbox has nothing to describe. */}
              <label title={t("share.linkUnavailableWhy")}>
                <input type="checkbox" checked={false} disabled readOnly />
                <span>{t("share.includeLink")}</span>
                <span className="muted">{t("share.linkUnavailable")}</span>
              </label>
            </fieldset>

            <div className="notice notice--warn share-mode">{t("share.demoNotice")}</div>
            {truncated ? (
              <p className="muted" style={{ fontSize: 12 }}>
                {t("share.willTruncate")}
              </p>
            ) : null}

            <div style={{ display: "flex", gap: 8 }}>
              <button className="primary" type="button" disabled={!ready} onClick={open}>
                {t("share.openClient")}
              </button>
              {truncated ? (
                <button
                  type="button"
                  onClick={() => void navigator.clipboard?.writeText(body)}
                >
                  {t("share.copyBody")}
                </button>
              ) : null}
              <button type="button" onClick={onClose}>
                {t("common.cancel")}
              </button>
            </div>
            {addresses.length === 0 ? (
              <p className="muted" style={{ fontSize: 12 }}>
                {t("share.needRecipient")}
              </p>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
