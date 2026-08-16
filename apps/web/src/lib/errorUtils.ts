"use client";

/** Shared utility to convert raw API / network errors into user-friendly localized messages with CTAs.
 *
 * Strips raw stack traces, backend URLs, and technical error dumps to ensure end-users
 * never see unhandled technical error messages.
 */

export interface ErrorCTA {
  label: string;
  href?: string;
  action?: "retry" | "login" | "uploadModel" | "selectDwa" | string;
}

export interface UserFormattedError {
  title: string;
  message: string;
  cta?: ErrorCTA;
}

export type TranslateFn = (key: string, vars?: Record<string, any>) => string;

export function toUserMessage(
  error: unknown,
  t: TranslateFn,
  _context?: string,
): UserFormattedError {
  if (!error) {
    return {
      title: t("error.title"),
      message: t("error.general"),
    };
  }

  let messageStr = "";
  let statusCode = 0;
  let errorCode = "";

  if (error instanceof Error) {
    messageStr = error.message;
    if ("status" in error && typeof (error as any).status === "number") {
      statusCode = (error as any).status;
    }
    if ("code" in error && typeof (error as any).code === "string") {
      errorCode = (error as any).code;
    }
  } else if (typeof error === "string") {
    messageStr = error;
  } else if (error && typeof error === "object") {
    messageStr = String((error as any).message ?? "");
  }

  const lower = messageStr.toLowerCase();

  // 1. Connection or stream failure
  if (
    lower.includes("fetch") ||
    lower.includes("network") ||
    lower.includes("connection") ||
    lower.includes("websocket") ||
    lower.includes("econnrefused") ||
    statusCode === 502 ||
    statusCode === 503 ||
    statusCode === 504 ||
    errorCode === "NETWORK_ERROR"
  ) {
    return {
      title: t("error.title"),
      message: t("error.connection"),
      cta: {
        label: t("error.cta.retry"),
        action: "retry",
      },
    };
  }

  // 2. Missing PPO model
  if (
    lower.includes("ppo") ||
    lower.includes("model_id") ||
    lower.includes("no model") ||
    lower.includes("model missing") ||
    errorCode === "NO_PPO_MODEL" ||
    errorCode === "MODEL_NOT_FOUND"
  ) {
    return {
      title: t("error.title"),
      message: t("error.noPpoModel"),
      cta: {
        label: t("error.cta.uploadModel"),
        href: "/models",
      },
    };
  }

  // 3. Login / Authentication required
  if (
    lower.includes("unauthorized") ||
    lower.includes("login") ||
    lower.includes("unauthenticated") ||
    statusCode === 401 ||
    errorCode === "UNAUTHORIZED"
  ) {
    return {
      title: t("error.title"),
      message: t("error.loginRequired"),
      cta: {
        label: t("error.cta.login"),
        href: "/login",
      },
    };
  }

  // 4. Validation error
  if (statusCode === 400 || statusCode === 422 || errorCode === "VALIDATION_ERROR") {
    return {
      title: t("error.title"),
      message: t("error.validation"),
    };
  }

  // 5. Resource not found
  if (statusCode === 404 || errorCode === "NOT_FOUND") {
    return {
      title: t("error.title"),
      message: t("error.notFound"),
    };
  }

  // Fallback: sanitized user error message (ensuring no URLs or stack traces are leaked)
  const containsUrlOrTrace = /http:|https:|\bat\b|stack|trace|Internal/i.test(messageStr);
  const safeMessage = containsUrlOrTrace || !messageStr.trim() ? t("error.general") : messageStr;

  return {
    title: t("error.title"),
    message: safeMessage,
  };
}
