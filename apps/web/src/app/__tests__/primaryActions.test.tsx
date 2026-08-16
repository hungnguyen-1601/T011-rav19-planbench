import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const APP_DIR = join(__dirname, "..");
const COMPONENTS_DIR = join(__dirname, "..", "..", "components");

describe("Single Primary Action Enforcement per Screen & State", () => {
  it("enforces single primary action on /simulate (Chạy mô phỏng)", () => {
    const content = readFileSync(join(APP_DIR, "simulate", "page.tsx"), "utf8");
    // Matches className="primary"
    const primaryMatches = content.match(/className="primary"/g) || [];
    expect(primaryMatches.length).toBe(1);
    expect(content).toContain('t("simulate.runSimulation")');
  });

  it("enforces single primary action on /scenarios/[id] (Lưu scenario)", () => {
    const content = readFileSync(join(APP_DIR, "scenarios", "[id]", "page.tsx"), "utf8");
    const primaryMatches = content.match(/className="primary"/g) || [];
    expect(primaryMatches.length).toBe(1);
    expect(content).toContain('t("scenarios.save")');
  });

  it("enforces single primary action on /benchmarks list (Tạo nháp benchmark)", () => {
    const content = readFileSync(join(APP_DIR, "benchmarks", "page.tsx"), "utf8");
    const primaryMatches = content.match(/className="primary"/g) || [];
    expect(primaryMatches.length).toBe(1);
    expect(content).toContain('t("benchmarks.createDraft")');
  });

  it("enforces dynamic single primary action on /benchmarks/[id]", () => {
    const content = readFileSync(join(APP_DIR, "benchmarks", "[id]", "page.tsx"), "utf8");
    // Verify that primary class is conditionally applied so that only ONE button is primary per state
    expect(content).toContain('canRun(isOwner, state, requests) ? "primary" : undefined');
    expect(content).toContain(
      '!canRun(isOwner, state, requests) && canAcceptResult(isOwner, state, requests) ? "primary" : undefined',
    );
    // ExportPanel should use secondary, not primary
    expect(content).not.toContain('className="primary" disabled={busy} onClick={() => void download()}');
  });

  it("enforces single primary action on ModelUpload component (Tải model)", () => {
    const content = readFileSync(join(COMPONENTS_DIR, "ModelUpload.tsx"), "utf8");
    const primaryMatches = content.match(/className="primary"/g) || [];
    expect(primaryMatches.length).toBe(1);
    expect(content).toContain('t("models.upload")');
  });

  it("enforces single primary action on /reviews RequestCard (Duyệt request)", () => {
    const content = readFileSync(join(APP_DIR, "reviews", "page.tsx"), "utf8");
    // Tabs should use active class instead of primary class
    expect(content).not.toContain('tab === "inbox" ? "primary"');
    expect(content).not.toContain('tab === "sent" ? "primary"');
    const primaryMatches = content.match(/className="primary"/g) || [];
    expect(primaryMatches.length).toBe(1);
    expect(content).toContain('t("reviews.approve")');
  });
});
