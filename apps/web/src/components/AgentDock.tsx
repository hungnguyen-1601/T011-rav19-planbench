"use client";

/** The floating agent, and nothing behind it yet.
 *
 * **A placeholder that says it is one.** There is no model wired to this
 * and the send button will not pretend otherwise: a chat box that
 * accepts a question and answers with silence is worse than one that
 * says up front it is not connected, because the first leaves somebody
 * wondering whether their question was bad.
 *
 * **Floating rather than docked, deliberately.** A panel in the layout
 * takes width from the page whether or not anybody is talking to it, and
 * every canvas on this app is measured in pixels rather than
 * percentages — a shell that changes the content width changes what
 * `MissionCanvas` thinks a click means. Floating over the page costs the
 * layout nothing and can be dismissed with Escape.
 *
 * The launcher sits bottom-right because bottom-left already belongs to
 * the framework's own dev overlay, and two circles in one corner is one
 * corner nobody can use.
 */

import { useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { useTranslation } from "@/lib/i18n";
import { useDismiss } from "@/lib/useDismiss";

export function AgentDock() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);

  // Escape and an outside click both close it. The launcher is outside
  // the panel, so it is held in the same ref subtree — otherwise
  // clicking the button to close would register as an outside click,
  // close the panel, and then reopen it on the same gesture.
  const dockRef = useRef<HTMLDivElement | null>(null);
  useDismiss(open, () => setOpen(false), dockRef);

  return (
    <div className="agent-dock" ref={dockRef}>
      {open ? (
        <div
          className="agent-dock-panel"
          ref={panelRef}
          role="dialog"
          aria-label={t("agentDock.title")}
        >
          <header className="agent-dock-head">
            <span className="agent-dock-mark" aria-hidden="true">
              <Icon name="sparkles" size={16} />
            </span>
            <div>
              <strong>{t("agentDock.title")}</strong>
              <p className="muted small">{t("agentDock.subtitle")}</p>
            </div>
            <button
              type="button"
              className="agent-dock-close"
              aria-label={t("common.close")}
              onClick={() => setOpen(false)}
            >
              <Icon name="close" size={15} />
            </button>
          </header>

          {/* The transcript, empty and saying why rather than showing a
              spinner that will never resolve. */}
          <div className="agent-dock-log" role="log" aria-live="polite">
            <p className="muted">{t("agentDock.placeholder")}</p>
          </div>

          <form
            className="agent-dock-composer"
            onSubmit={(event) => {
              // Nothing to submit to. Handled rather than left to the
              // browser so a stray Enter does not reload the page.
              event.preventDefault();
            }}
          >
            <input
              type="text"
              disabled
              placeholder={t("agentDock.inputPlaceholder")}
              aria-label={t("agentDock.inputPlaceholder")}
            />
            <button type="submit" disabled>
              {t("agentDock.send")}
            </button>
          </form>
        </div>
      ) : null}

      <button
        type="button"
        className="agent-dock-launcher"
        aria-expanded={open}
        aria-label={t("agentDock.title")}
        title={t("agentDock.title")}
        onClick={() => setOpen((current) => !current)}
      >
        <Icon name={open ? "close" : "sparkles"} size={20} />
      </button>
    </div>
  );
}
