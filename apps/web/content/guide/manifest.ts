/** The guide's table of contents — one source, four readers.
 *
 * `generateStaticParams`, the sidebar, the search and prev/next all read
 * this. The alternative was frontmatter in each `.mdx`, which `@next/mdx`
 * does not parse without two more plugins, and which would force the
 * sidebar to import all eleven modules — that is, to pull every article's
 * prose into the landing page — just to learn their titles.
 *
 * **Section ids are written, never derived from the title.** Slugifying a
 * heading gives `#khai-deployment` in Vietnamese and `#declare-a-deployment`
 * in English: two ids for one place, so a link somebody pasted breaks for a
 * reader in the other language. The id is the same in both files; only the
 * title differs. `/guide/gates#g2` therefore means the same thing to
 * everyone.
 */

import type { Locale } from "@/lib/i18n/shared";

/** A string that exists in both languages. Titles only — prose is MDX. */
export type Bilingual = Record<Locale, string>;

export interface GuideSection {
  /** Written by the author, identical across locales. */
  id: string;
  title: Bilingual;
}

/** A group heading on the rail. Not a URL segment: the IA is flat. */
export type GuideGroup = "overview" | "operating" | "results" | "advanced" | "reference";

export interface GuideArticleMeta {
  slug: string;
  group: GuideGroup;
  /** Reading order across the whole guide, not within the group.
   *
   * Prev/next walks it end to end and crosses group boundaries: somebody
   * working through the guide should not have to go back to the rail to
   * learn what follows the last article of a group. The rail sorts by
   * the same number inside each group, so one ordering serves both. */
  order: number;
  title: Bilingual;
  /** Anchors inside the article. Pinned against the body by a test. */
  sections: GuideSection[];
  /** Tabs, when the parts genuinely answer one question side by side.
   *
   * Absent for an article read top to bottom. A hidden tab panel is
   * `hidden`, which browser find skips — so a sequence, where the reader
   * has to see that step five exists while reading step two, is never
   * tabbed. */
  tabs?: GuideSection[];
}

export const GUIDE: readonly GuideArticleMeta[] = [
  {
    slug: "overview",
    group: "overview",
    order: 10,
    title: { vi: "Tổng quan", en: "Overview" },
    sections: [
      { id: "he-thong-lam-gi", title: { vi: "Hệ thống làm gì", en: "What this is for" } },
      { id: "luong-tong-the", title: { vi: "Luồng tổng thể", en: "How the work flows" } },
      { id: "thuat-ngu", title: { vi: "Thuật ngữ", en: "The words used here" } },
    ],
  },
  {
    slug: "getting-started",
    group: "overview",
    order: 15,
    title: { vi: "Năm phút đầu", en: "The first five minutes" },
    sections: [
      { id: "muon-mot-thu-de-nhin", title: { vi: "Muốn một thứ để nhìn", en: "Something to look at" } },
      { id: "chay-phep-so-dau-tien", title: { vi: "Chạy phép so đầu tiên", en: "Run the first comparison" } },
      { id: "roi-doc-no", title: { vi: "Rồi đọc nó", en: "Then read it" } },
    ],
  },
  {
    slug: "operation",
    group: "operating",
    order: 20,
    title: { vi: "Bảy bước vận hành", en: "Seven steps" },
    sections: [
      { id: "buoc-1-ban-do", title: { vi: "1 — Bản đồ", en: "1 — The map" } },
      { id: "buoc-2-kich-ban", title: { vi: "2 — Kịch bản", en: "2 — The scenario" } },
      { id: "buoc-3-deployment", title: { vi: "3 — Khai triển khai", en: "3 — Declare the deployment" } },
      { id: "buoc-4-ung-vien", title: { vi: "4 — Ứng viên", en: "4 — The candidates" } },
      { id: "buoc-5-san-thu", title: { vi: "5 — Chạy thử một episode", en: "5 — Try one episode" } },
      { id: "buoc-6-phep-so", title: { vi: "6 — Chạy phép so", en: "6 — Run the comparison" } },
      { id: "buoc-7-doc-va-mang-ra", title: { vi: "7 — Đọc, và mang ra ngoài", en: "7 — Read it, and take it out" } },
    ],
  },
  {
    slug: "concepts",
    group: "results",
    order: 40,
    title: { vi: "Mười khái niệm", en: "Ten ideas" },
    sections: [
      { id: "ung-vien-la-mot-stack", title: { vi: "Ứng viên là một stack", en: "A candidate is a whole stack" } },
      { id: "ghep-cap-episode", title: { vi: "Ghép cặp episode", en: "Episodes are paired" } },
      { id: "checksum-dieu-kien", title: { vi: "Checksum điều kiện", en: "The conditions checksum" } },
      { id: "ma-deployment-la-danh-tinh", title: { vi: "Mã triển khai là danh tính", en: "A deployment id is an identity" } },
      { id: "nguong-doc-tu-deployment", title: { vi: "Ngưỡng đọc từ triển khai", en: "Thresholds come from the deployment" } },
      { id: "cong-khong-phai-diem", title: { vi: "Cổng không phải điểm số", en: "A gate is not a score" } },
      { id: "khong-va-cham-la-chan-tren", title: { vi: "Không va chạm là một chặn trên", en: "Zero collisions is an upper bound" } },
      { id: "sang-loc-mot-chieu", title: { vi: "Sàng lọc chỉ chứng minh một chiều", en: "Host screening proves one direction" } },
      { id: "khoang-tin-cay-vat-qua-0", title: { vi: "Khoảng tin cậy vắt qua 0", en: "An interval straddling zero" } },
      { id: "doi-mot-thanh-phan", title: { vi: "Đổi đúng một thành phần", en: "Change exactly one component" } },
    ],
  },
  {
    slug: "gates",
    group: "results",
    order: 50,
    title: { vi: "Sáu cổng khả thi", en: "The six feasibility gates" },
    sections: [],
    tabs: [
      { id: "g1", title: { vi: "G1 — Không tìm được đường", en: "G1 — No path found" } },
      { id: "g2", title: { vi: "G2 — Va chạm", en: "G2 — Collisions" } },
      { id: "g3", title: { vi: "G3 — Tỷ lệ thành công", en: "G3 — Success rate" } },
      { id: "g4", title: { vi: "G4 — Thời gian thực", en: "G4 — Real time" } },
      { id: "g5", title: { vi: "G5 — Bộ nhớ", en: "G5 — Memory" } },
      { id: "g6", title: { vi: "G6 — Quan sát cần có", en: "G6 — Required observations" } },
    ],
  },
  {
    slug: "evidence",
    group: "results",
    order: 60,
    title: { vi: "Bằng chứng đứng sau con số", en: "The evidence behind a number" },
    sections: [],
    tabs: [
      { id: "ghep-cap", title: { vi: "Ghép cặp", en: "Pairing" } },
      { id: "khoang-tin-cay", title: { vi: "Khoảng tin cậy", en: "Confidence intervals" } },
      { id: "thang-bang-chung", title: { vi: "Thang bằng chứng", en: "The evidence ladder" } },
    ],
  },
  {
    slug: "pages",
    group: "operating",
    order: 30,
    title: { vi: "Từng trang làm gì", en: "What each screen is for" },
    sections: [
      { id: "maps", title: { vi: "Bản đồ", en: "Maps" } },
      { id: "library", title: { vi: "Thư viện kịch bản", en: "Scenario library" } },
      { id: "deployments", title: { vi: "Triển khai", en: "Deployments" } },
      { id: "candidates", title: { vi: "Ứng viên", en: "Candidates" } },
      { id: "models", title: { vi: "Mô hình", en: "Models" } },
      { id: "simulate", title: { vi: "Sân thử", en: "Test bench" } },
      { id: "decisions", title: { vi: "Quyết định", en: "Decisions" } },
      { id: "reviews", title: { vi: "Duyệt", en: "Reviews" } },
      { id: "agent", title: { vi: "Trợ lý AI", en: "Assistant" } },
      { id: "settings-system", title: { vi: "Cài đặt và Hệ thống", en: "Settings and System" } },
    ],
  },
];

export const GUIDE_SLUGS: readonly string[] = GUIDE.map((article) => article.slug);

export function articleBySlug(slug: string): GuideArticleMeta | undefined {
  return GUIDE.find((article) => article.slug === slug);
}
