import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ApiError } from "@/lib/api";
import { toUserMessage } from "@/lib/errorUtils";
import { translate } from "@/lib/i18n";

const EN = JSON.parse(
  readFileSync(join(__dirname, "..", "i18n", "locales", "en.json"), "utf8"),
) as Record<string, string>;

const VI = JSON.parse(
  readFileSync(join(__dirname, "..", "i18n", "locales", "vi.json"), "utf8"),
) as Record<string, string>;

const tEn = (key: string, vars?: Record<string, any>) => translate(EN, EN, key, vars);
const tVi = (key: string, vars?: Record<string, any>) => translate(VI, EN, key, vars);

describe("toUserMessage error standardization", () => {
  it("maps connection and network failures to actionable connection lost message (EN & VI)", () => {
    const error = new Error("Failed to fetch");

    const resEn = toUserMessage(error, tEn);
    expect(resEn.message).toBe("Simulation connection lost — Retry");
    expect(resEn.cta?.label).toBe("Retry");
    expect(resEn.cta?.action).toBe("retry");

    const resVi = toUserMessage(error, tVi);
    expect(resVi.message).toBe("Mất kết nối mô phỏng — Thử lại");
    expect(resVi.cta?.label).toBe("Thử lại");
  });

  it("maps WebSocket connection failures to connection error message", () => {
    const res = toUserMessage("WebSocket connection failed", tVi);
    expect(res.message).toBe("Mất kết nối mô phỏng — Thử lại");
    expect(res.cta?.action).toBe("retry");
  });

  it("maps missing PPO model errors to model selection / upload CTA", () => {
    const error = new ApiError(400, "NO_PPO_MODEL", "No PPO model selected");

    const resEn = toUserMessage(error, tEn);
    expect(resEn.message).toBe("No PPO model selected — Upload model or select A* + DWA");
    expect(resEn.cta?.label).toBe("Upload model");
    expect(resEn.cta?.href).toBe("/models");

    const resVi = toUserMessage(error, tVi);
    expect(resVi.message).toBe("Bạn chưa chọn model PPO — Tải model hoặc chọn A* + DWA");
    expect(resVi.cta?.label).toBe("Tải model");
  });

  it("maps unauthenticated / 401 errors to sign in required message", () => {
    const error = new ApiError(401, "UNAUTHORIZED", "Login required to perform action");

    const resEn = toUserMessage(error, tEn);
    expect(resEn.message).toBe("Sign in required to save scenario");
    expect(resEn.cta?.label).toBe("Sign in");
    expect(resEn.cta?.href).toBe("/login");

    const resVi = toUserMessage(error, tVi);
    expect(resVi.message).toBe("Bạn cần đăng nhập để lưu scenario");
    expect(resVi.cta?.label).toBe("Đăng nhập");
  });

  it("strips technical URLs and stack traces from unhandled technical errors", () => {
    const techError = new Error("Fetch error at http://localhost:8000/api/v1/internal\n  at StackTrace.func (file.js:10)");
    const res = toUserMessage(techError, tVi);
    expect(res.message).not.toContain("http://localhost:8000");
    expect(res.message).not.toContain("StackTrace");
    expect(res.message).toBe("Mất kết nối mô phỏng — Thử lại");
  });

  it("ensures all error message and CTA keys exist in both en.json and vi.json", () => {
    const keys = [
      "error.title",
      "error.connection",
      "error.noPpoModel",
      "error.loginRequired",
      "error.validation",
      "error.notFound",
      "error.general",
      "error.cta.retry",
      "error.cta.login",
      "error.cta.uploadModel",
      "error.cta.selectDwa",
    ];

    for (const key of keys) {
      expect(EN[key], `en missing ${key}`).toBeTruthy();
      expect(VI[key], `vi missing ${key}`).toBeTruthy();
    }
  });
});
