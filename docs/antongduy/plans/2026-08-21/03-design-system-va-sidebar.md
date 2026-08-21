# Plan 3 — Design system + Sidebar toàn app

Ngày lập: 2026-08-21 · Trạng thái: **chờ An duyệt**
Nguồn: [note đánh giá](../../notes/2026-08-21/tongduyan_danh-gia-ui-trang-decision-detail.md) mục B, C và QA #4, #11, #15, #16, #19–#25.

## Mục tiêu

Dựng một hệ thiết kế có thang, rồi kéo mọi trang về hệ đó. Sidebar nằm trong plan
này vì nó là chrome dùng chung, không thuộc trang nào.

## Ngoài phạm vi

- Nội dung / cấu trúc trang decision detail → Plan 2.
- Defect token, i18n, focus → Plan 1.
- Dark theme **không** được thiết kế lại. Chỉ giữ nó chạy được sau khi đổi token.

## Phụ thuộc

Plan 1 xong (T2 định nghĩa `--font-mono`, plan này thay stack của nó bằng webfont).

**Quan hệ với Plan 2**: giai đoạn A (**A2–A4**, thuần khai báo) là điều kiện cho
Plan 2. Nạp font (B0) và toàn bộ B, C, D chạy **sau** Plan 2.

```
Plan 1 ──► Plan 3 A2–A4 (token, zero-diff) ──► Plan 2 (trang demo) ──► Plan 3 B0/B/C/D
```

---

## Giai đoạn A — Thêm token. Không đổi một pixel nào.

Chỉ **khai báo**. Chưa chỗ nào dùng, nên không trang nào đổi hình — **zero-diff
thật**, kiểm được bằng screenshot. Nạp font (trước là A1) đổi mặt chữ toàn app
nên **đã chuyển xuống giai đoạn B thành B0** — nhờ vậy Plan 2 chỉ cần phụ thuộc
A2–A4 và không phải nuốt thay đổi font trước ngày demo.

### A2 — Thang spacing / radius / typography

Thêm vào `:root` chung (ngoài các block `[data-theme]` — không đổi theo theme):

```css
--space-1: 4px;  --space-2: 8px;  --space-3: 12px;
--space-4: 16px; --space-5: 24px; --space-6: 32px; --space-7: 48px;

--radius-sm: 4px; --radius-md: 6px; --radius-lg: 8px;

--fs-caption: 11px; --fs-sm: 12px;  --fs-body: 13px;
--fs-label:   14px; --fs-value: 16px; --fs-h3: 18px; --fs-h1: 24px;

--shadow-pop: 0 4px 12px rgba(20,24,31,.10);   /* dark: rgba(0,0,0,.45) */
```

### A3 — Tách `--candidate-a/b` khỏi `--accent`

`globals.css:2018-2023`

Hiện `--candidate-a: var(--accent)`. Xanh dương vừa nghĩa "link/tương tác" vừa
nghĩa "Candidate A".

```css
/* light */  --candidate-a: #5267c9; --candidate-b: #087f6a;
/* dark  */  --candidate-a: #8fa5ff; --candidate-b: #50c7ad;
```
Giữ `--candidate-a-soft` / `--candidate-b-soft` (Plan 2 bỏ nền tô cột nhưng
`.candidate-card-head` ở `globals.css:2049` còn dùng).

### A4 — Ba biến thể `.notice`

`globals.css:1112` hiện một class duy nhất, nền vàng, dùng cho cả ba mức.

Giữ `.notice` gốc **không đổi** ở giai đoạn A (để không phá 23 chỗ đang dùng),
**thêm**:
```css
.notice--info     { background: var(--panel-2);  border-color: var(--border); }
.notice--warn     { background: var(--warn-soft); border-color: color-mix(in srgb, var(--warn) 35%, transparent); }
.notice--critical { background: var(--err-soft);  border-color: var(--err); }
```
Giai đoạn B mới đổi `.notice` mặc định thành trung tính và gán biến thể cho từng
chỗ dùng.

**Nghiệm thu giai đoạn A**: chụp màn 6 trang trước/sau — **không khác một pixel**.

---

## Giai đoạn B — Áp dụng. Đây là phần đổi hình.

Chạy **sau** Plan 2. Chạm mọi trang, cần kiểm mắt từng trang.

### B0 — Nạp font (chuyển từ A1 xuống)

`apps/web/src/app/layout.tsx`

```ts
import { Be_Vietnam_Pro, JetBrains_Mono } from "next/font/google";

const sans = Be_Vietnam_Pro({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans-loaded", display: "swap",
});
const mono = JetBrains_Mono({
  subsets: ["latin"], weight: ["400", "500", "600"],
  variable: "--font-mono-loaded", display: "swap",
});
```
Gắn `${sans.variable} ${mono.variable}` vào `<html className>`.

**Hợp đồng token — đã chốt ở Plan 1 T6, làm đúng theo, không bàn lại**:
`next/font` sinh token tên riêng `--font-*-loaded` (hai tên này nằm trong
`NEXT_FONT_PROVIDED` của `tokens.test.ts`). Token **công khai** vẫn khai trong
`globals.css`, giờ **sửa giá trị** thành alias — không xoá khai báo:
```css
--font-sans: var(--font-sans-loaded, Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif);
--font-mono: var(--font-mono-loaded, ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace);
```
Nhờ đó test token luôn thấy `--font-sans`/`--font-mono` được khai trong
`globals.css` — không plan nào phải nới test, và môi trường không tải được
Google Fonts rơi về stack hệ thống một cách tường minh.

**`subsets` phải có `"vietnamese"`.** Thiếu nó thì dấu rơi về font hệ thống giữa
chừng và lệch baseline. Đây là lý do chọn Be Vietnam Pro: nó được vẽ cho tiếng
Việt, dấu trên nguyên âm có mũ (`ế ồ ữ`) không chồng ở 12px.

### B1 — Base

```css
html, body {
  font-family: var(--font-sans);
  font-size: var(--fs-body);     /* 13px, từ 14px */
  line-height: 1.5;              /* tối thiểu 1.4 cho chữ có dấu */
}
```
Hạ base 13px là thứ tạo ra "semi-compact". Nó **thu nhỏ mọi trang cùng lúc** —
kiểm kỹ các trang nhiều chữ (`/system`, `/agent`, `/library`).

### B2 — `main.content` giới hạn bề rộng

`globals.css:372`
```css
main.content {
  max-width: 1440px; margin-inline: auto;
  padding: var(--space-5) var(--space-6) var(--space-7);
}
```
Một dòng, nhưng đây là fix P0 số 4 trong note: ở 1920 không có nó thì cột giá trị
phình lên 480px quanh một con số 6 ký tự.

Kiểm riêng các trang có canvas (`/maps`, `/simulate`, `/deployments`) — chúng có
thể đang dựa vào bề rộng không giới hạn.

### B3 — Topbar bỏ backdrop-filter

`globals.css:388-390` — `background: color-mix(...)` + `backdrop-filter: blur(8px)`.
Trên light theme cho ra một dải mờ đục và một compositing layer, không giải quyết
gì. Đổi `background: var(--bg)`, giữ viền dưới.

### B4 — Button

`globals.css:670-690`

- Cao `32px` cố định, `padding: 0 var(--space-3)`, `--radius-md`, `--fs-body`, `600`
- `:hover` → `background: var(--hover)`. **Bỏ `border-color: var(--accent)`**
  (`globals.css:679`) — nó làm mọi nút trông như đang focus
- Bốn biến thể: `default` / `.primary` / `.ghost` / `.danger`
- `:focus-visible` → `outline: 2px solid var(--accent); outline-offset: 2px`

### B5 — Badge

`globals.css:768-790`, `931`

`border-radius: 10px` trên chữ 11px thành viên thuốc. Đổi `--radius-sm` (4px),
cao 20px, `--fs-sm`. Bốn biến thể: `neutral` / `ok` / `warn` / `err`.

Bỏ icon trong badge trừ khi badge đó là kết luận duy nhất của cả panel.
**Ảnh hưởng rộng** — badge dùng khắp app.

### B6 — Panel

`globals.css:665-670` — `--radius-lg`, `padding: var(--space-4)`,
`margin-bottom: var(--space-5)`, **không shadow**.

Rà `.dashboard-page .stat-card` (`globals.css:1444-1472`) đang có
`--dashboard-card-shadow` và `transform: translateY` khi hover. Bỏ cả hai.

### B7 — `.notice` gán biến thể

Đổi `.notice` mặc định sang trung tính, rồi đi hết 23 chỗ dùng
(`candidates`, `decisions/[id]`, `deployments`, `library`, `page.tsx`, `scenarios`,
`scenarios/[id]`, `DeploymentForm`, `TrafficEditor`) gán đúng mức.

Luật: `--critical` chỉ cho thứ **vô hiệu hoá mọi số bên dưới**. `--warn` cho
phạm vi hẹp. Mặc định cho thông tin.

### B8 — Input, tabs

- Input/select: cao 32px, `--radius-md`, focus ring `0 0 0 3px var(--accent-soft)`
- Tabs (`apps/web/src/components/Tabs.tsx`): underline, **không pill**.
  Active `box-shadow: inset 0 -2px 0 var(--accent)`

---

## Giai đoạn C — Sidebar

### C1 — Bỏ mô tả khỏi rail

`apps/web/src/components/Sidebar.tsx:61`, `:84`

```tsx
const description = item.descriptionKey ? t(item.descriptionKey) : null;
...
{description ? <span className="sidebar-desc">{description}</span> : null}
```

14 mục × 1 câu ⇒ rail 60% văn xuôi, mục cuối rơi dưới fold.

**Sửa**: bỏ `<span className="sidebar-desc">`. Đưa `description` vào `title` của
`<a>`. **Giữ nguyên `descriptionKey` trong `navigation.ts` và giữ nguyên toàn bộ
khoá `nav.desc.*`** — chữ không mất, chỉ đổi chỗ.

Xoá `.sidebar-desc` (`globals.css:322-329`) và rule collapsed liên quan.

### C2 — Bốn nhóm còn ba

`apps/web/src/lib/navigation.ts:53-147`

| Hiện tại | Đổi thành |
|---|---|
| `nav.section.doing` — "What you are doing" | `nav.section.workspace` — "Workspace" |
| `nav.section.materials` — "Materials" | `nav.section.results` — "Resources" |
| `nav.section.retiring` — "Being replaced" | **bỏ nhóm**, dồn vào Resources |
| `nav.section.account` | giữ |

Ba khoá thay thế **đã có sẵn** ở `en.json:75-77` và `vi.json:75-77`, đang không
dùng. Không cần thêm khoá.

`nav.section.results` hiện là "Results" / "Kết quả" — đổi text thành
"Resources" / "Tài nguyên" cho khớp nội dung nhóm, giữ nguyên tên khoá.

**"Being replaced" nói thẳng với giám khảo rằng sản phẩm dở dang.** Nhãn điều
hướng phải là danh từ chỉ nơi chốn.

### C3 — Chip `Legacy`

Thêm `legacy?: boolean` vào `NavItem` (`navigation.ts:13-30`). Bật cho
`/algorithms`, `/benchmarks`, `/leaderboard`, `/scenarios`.

`Sidebar.tsx` render `<span className="badge badge--neutral rail-legacy">` canh
phải. Khoá i18n mới: `nav.legacy` (`Legacy` / `Cũ`).

Xoá hack CSS `opacity: .85` theo href (`globals.css:333-337`) — nó đang hard-code
ba đường dẫn vào stylesheet.

### C4 — Kích thước rail

`globals.css:200-215`, `:56-58`

`--sidebar-width: 264px` → `232px`. Mỗi mục cao `32px`, `padding: 0 var(--space-2)`.
Bỏ `<p className="tagline">` trong `.sidebar-brand` (`Sidebar.tsx:50`) — chuyển
`app.tagline` xuống trang `/system`.

Kết quả: 14 mục × 32 + 3 tiêu đề nhóm ≈ 520px, vừa một màn 13".

### C5 — Test

`apps/web/src/components/__tests__/shell.test.tsx` và
`apps/web/src/lib/__tests__/navigation.test.ts` đang khẳng định cấu trúc 4 nhóm
và sự có mặt của description. **Cả hai sẽ đỏ.** Sửa test cùng lượt, không sửa sau.

---

## Giai đoạn D — Quét sạch và chặn tái phát

### D1 — Giá trị lệch thang

```bash
grep -nE '(padding|margin|gap): *[0-9]+px' globals.css   # ngoài 0/4/8/12/16/24/32/48
grep -nE 'font-size: *[0-9]+\.[0-9]'                     # 14.5px, 12.5px
grep -nE 'border-radius: *(10|12|14|16)px'
```
Đổi từng chỗ về token gần nhất. Chỗ nào cố ý lệch thang thì để lại comment nói rõ.

### D2 — Bỏ hết `!important`

`grep -n '!important' globals.css`. Mỗi ca truy về nguyên nhân (thường là inline
style, như `.comparison-grid` mà Plan 2 T4 đã xử).

### D3 — Test chặn tái phát

Mở rộng `tokens.test.ts` (Plan 1 T6):
- Mọi `padding`/`margin`/`gap` px thuộc thang, hoặc nằm trong danh sách miễn trừ có tên
- Không `font-size` nửa pixel
- `border-radius` chỉ thuộc {4, 6, 8, 50%}
- Không `linear-gradient`
- `box-shadow` chỉ trong danh sách selector cho phép

Danh sách miễn trừ là một mảng có tên trong test, không phải regex lỏng — thêm
một ngoại lệ phải sửa test, tức là phải cố ý.

---

## Nghiệm thu cả plan

- [ ] Chỉ **một** stack sans và **một** stack mono trong toàn bộ `globals.css`
- [ ] `Ữ Ế Ộ Ỡ Ợ ự ệ ỗ ẫ ằ` render đủ dấu ở 11 / 12 / 13 / 14 / 16 / 24px
- [ ] Chuyển EN ⇄ VI trên 6 trang chính — không nhãn nào tràn hoặc cắt
- [ ] Sidebar: 14 mục vừa một màn 13" (768px cao), không cuộn
- [ ] Không nhãn điều hướng nào kể trạng thái dự án
- [ ] `grep -n '!important' globals.css` → rỗng
- [ ] `grep -n 'linear-gradient' globals.css` → rỗng
- [ ] `box-shadow` chỉ ở popover / tooltip / menu / `inset` của active nav
- [ ] Chiều cao control thống nhất 32px: button, input, select, tab, hàng bảng
- [ ] Contrast AA: `--muted` trên `--panel` và trên `--panel-2`; chữ 11px cũng phải ≥ 4.5:1
- [ ] Dark theme còn chạy được — không dùng lại thiết kế, chỉ không vỡ
- [ ] `npm run typecheck` + test đã sửa ở C5 xanh

## Rủi ro

| Rủi ro | Mức | Xử lý |
|---|---|---|
| Giai đoạn B chạm mọi trang | **Cao** | Chia commit theo trang, không theo class. Duyệt mắt từng trang trước khi sang trang sau |
| Hạ base 13px làm vỡ trang nhiều chữ | **Cao** | Kiểm `/system`, `/agent`, `/library` ngay sau B1. Nếu vỡ thì giữ 14px cho các trang đó bằng một class trên `main` |
| B2 phá layout trang có canvas | Trung bình | `/maps`, `/simulate`, `/deployments` kiểm riêng. Cho phép opt-out bằng `main.content--wide` |
| C5 hai file test đỏ | Thấp | Đã biết trước. Sửa cùng lượt |
| B5 đổi badge ảnh hưởng khắp app | Trung bình | Badge chỉ đổi radius và chiều cao, không đổi màu — sai lệch nếu có sẽ nhỏ và nhìn ra ngay |
| Google Fonts không tải được ở môi trường demo | Trung bình | `display: "swap"` + fallback `Inter, ui-sans-serif, system-ui`. Nếu demo offline thì self-host font, quyết trước ngày demo |

## Không commit

Làm xong dừng lại, báo cáo. An tự commit.
