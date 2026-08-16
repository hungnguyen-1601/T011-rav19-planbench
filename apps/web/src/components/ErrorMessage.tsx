"use client";

import Link from "next/link";
import { useTranslation } from "@/lib/i18n";
import { toUserMessage } from "@/lib/errorUtils";

export interface ErrorMessageProps {
  error: unknown;
  onRetry?: () => void;
  className?: string;
  style?: React.CSSProperties;
}

export function ErrorMessage({ error, onRetry, className = "", style }: ErrorMessageProps) {
  const { t } = useTranslation();
  if (!error) return null;

  const formatted = toUserMessage(error, t);

  return (
    <div
      className={`error-box ${className}`.trim()}
      role="alert"
      aria-live="assertive"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "12px",
        flexWrap: "wrap",
        ...style,
      }}
      data-testid="standard-error-message"
    >
      <span>{formatted.message}</span>

      {formatted.cta ? (
        <span style={{ marginLeft: "auto" }}>
          {formatted.cta.action === "retry" && onRetry ? (
            <button type="button" className="secondary small" onClick={onRetry}>
              {formatted.cta.label}
            </button>
          ) : formatted.cta.href ? (
            <Link href={formatted.cta.href} className="button-link small">
              {formatted.cta.label}
            </Link>
          ) : null}
        </span>
      ) : null}
    </div>
  );
}
