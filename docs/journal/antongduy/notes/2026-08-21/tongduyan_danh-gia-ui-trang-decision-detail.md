# Đánh giá UI trang Decision Detail — vì sao bị đọc là "AI-generated"

Ngày: 2026-08-21 · Phạm vi: `/decisions/[id]`, light theme, viewport ~1920×1080
Đây là **note (quan sát/đánh giá)**, không đổi dòng code nào.

Toàn bộ nhận xét bên dưới đã đối chiếu với code thật, không suy đoán từ ảnh.
File tham chiếu chính: `apps/web/src/app/globals.css` (3504 dòng, CSS thuần,
**không có Tailwind**), `apps/web/src/app/decisions/[id]/page.tsx` (1377 dòng),
`apps/web/src/components/Hint.tsx`, `packages/benchmark/planbench_benchmark/hostinfo.py`.

---

## A. Bảng QA

Severity: **P0** = ban giám khảo nhìn thấy trong 5 giây đầu và mất tin cậy ·
**P1** = làm đọc sai dữ liệu · **P2** = thẩm mỹ / nhất quán.

| # | Issue | Evidence (screenshot + code) | Sev | Vì sao mất uy tín | Fix cụ thể |
|---|---|---|---|---|---|
| 1 | **Banner tiếng Việt trên trang đang ở EN** | Dải vàng "Đo trên toàn bộ 20 nhân, không ghim…" trong khi topbar là `EN`. Chuỗi hard-code tiếng Việt tại `hostinfo.py:185-187`; `HostWarning` render nguyên văn (`page.tsx:325`) đúng như comment "a client that reworded it could water it down" | **P0** | Lẫn ngôn ngữ là dấu hiệu số 1 của sản phẩm chưa hoàn thiện. Giám khảo không đọc tiếng Việt sẽ thấy một khối chữ lạ ngay giữa bảng kết quả | Backend trả **structured** thay vì câu văn: `{code: "unpinned_host", cores: 20, unpinned_ms: 59.30, pinned_ms: 16.10}`. Frontend dịch qua i18n key `decisions.env.unpinned`. Giữ nguyên tính "không được diễn giải lại" bằng cách khoá số liệu, không khoá ngôn ngữ |
| 2 | **Hai cột cùng tên `astar+dwa`, thứ khác nhau lại nhỏ nhất** | Cột A và B đều `<h4>astar+dwa</h4>` 15px; khác biệt thật (`dwa_coarse` vs `dwa_balanced`) nằm ở `<code>` 10px muted. CSS: `globals.css:3420-3421` | **P0** | Cả trang tồn tại để phân biệt hai ứng viên, mà tên hiển thị lại giống hệt nhau. Người xem tưởng bảng lỗi | Đảo ngôi: `<h4>` = `dwa_coarse` / `dwa_balanced` (14px, 600). Stack `astar+dwa` xuống dòng phụ 12px muted. Có thể thêm **diff chip** chỉ liệt kê tham số khác nhau giữa hai config |
| 3 | **Token `--text-muted` không tồn tại → 20 dấu `?` đen đậm** | `globals.css:1135` `.hint-mark { color: var(--text-muted) }`. `grep -c -- '--text-muted:'` → **0**. Không có fallback ⇒ inherit `.comparison-label` (`color: var(--text)`, near-black `#14181f`) và `.hint-mark` tự đặt `font-weight: 700` | **P0** | Một cột 12 dấu `?` đen đậm chạy dọc bảng là tín hiệu "AI rắc icon trang trí" mạnh nhất trong ảnh. Đây là **bug**, không phải lựa chọn thiết kế | Đổi thành `color: var(--muted)`. Kèm hạ `font-weight: 600`, `opacity: .7`, và `opacity: 1` khi `:hover/:focus-visible` |
| 4 | **Không có `max-width` cho vùng nội dung** | `globals.css:372` `main.content { flex: 1; padding: 22px 26px 40px; }` — không giới hạn bề rộng | **P0** | Ở 1920px, mỗi cột giá trị rộng ~480px chỉ chứa 6 ký tự, canh giữa ⇒ con số cách nhãn của chính nó ~200px khoảng trắng. Mắt phải bắc cầu qua vùng trống, và trang trông như template chưa đổ dữ liệu | `main.content { max-width: 1440px; margin-inline: auto; }`. Riêng bảng so sánh giới hạn thêm: gutter `minmax(260px, 420px)`, mỗi cột candidate `minmax(150px, 260px)`, phần dư dồn vào cột trống bên phải chứ không giãn ô số |
| 5 | **Ba stat card cùng hiển thị `30`** | `SampleBanner` (`page.tsx:1147-1165`) render measured / requested / n_min vô điều kiện. Ảnh: 30 / 30 / 30 ở 26px | **P0** | Ba con số khổng lồ giống hệt nhau, chiếm 1/6 màn hình mà nói đúng một điều ("đủ mẫu"). Đây là "card trang trí" kinh điển | Trạng thái bình thường thu về **một dòng inline** ở header: `30 episodes · đủ N_min (30) · đã chạy hết yêu cầu`. Chỉ bung thành card khi có bất thường (`interrupted`, `n_episodes < n_min_required`, `coverage < 1`) — lúc đó card mới mang thông tin |
| 6 | **`--font-mono` không được định nghĩa** | Dùng ở `globals.css:1865` và `3111` dạng `var(--font-mono, monospace)`; không có dòng `--font-mono:` nào. Trong khi `.comparison-value` (`3446`) hard-code stack khác: `ui-monospace,SFMono-Regular,Consolas,monospace` | P1 | Hai font mono khác nhau trong cùng một trang. Trên Windows `monospace` ra Courier New — lệch hẳn so với Consolas ở bảng | Định nghĩa `--font-mono: ui-monospace, "JetBrains Mono", SFMono-Regular, Consolas, monospace` ở `:root`; mọi chỗ dùng token, xoá stack hard-code |
| 7 | **`Collision probability, 95% upper bound = 10.0%` đặt ngay dưới `Collisions observed = 0`** | Hai hàng cách nhau một hàng. Giải thích ("bound là 3/N, số thấp nghĩa là nhiều bằng chứng hơn chứ không phải robot an toàn hơn") nằm trong `decisions.compare.why.collisionBound` — **giấu sau dấu `?`** | **P0** | Giám khảo đọc lướt sẽ hiểu "hệ này có 10% khả năng va chạm" trong khi thực tế là 0 va chạm / 30 episode. Đây là hiểu sai **ngược dấu**, tệ hơn là không hiển thị | Đổi nhãn thành `Cận trên xác suất va chạm (quy tắc 3/N)` và in giá trị kèm ngữ cảnh trực tiếp: `≤ 10.0%  (0/30)`. Không để lời giải thích quyết định đúng/sai nằm sau hover |
| 8 | **Canh giữa cột số ⇒ dấu thập phân không thẳng hàng** | `globals.css:3441-3447` `.comparison-value { text-align: center }` dù đã bật `font-variant-numeric: tabular-nums`. Ảnh: `7.85 ms` vs `17.89 ms` lệch một ký tự; `0.470` vs `0.494` | P1 | `tabular-nums` được bật rồi bị canh giữa vô hiệu hoá. Phần mềm đo lường mà cột số không thẳng là mất điểm chuyên môn ngay | Canh phải, thêm `padding-right` đủ để không dính viền. Nếu An vẫn muốn khối số nằm giữa ô: bọc `<span>` canh phải rồi `justify-self: center` cho span — khối nằm giữa nhưng chữ số vẫn thẳng cột |
| 9 | **Tô xanh "thắng" cho chênh lệch 0.1 s, không có khoảng tin cậy** | `22.5 s` xanh vs `22.6 s`; `0.470` vs `0.494` m. `leaders()` trong `candidateMetrics.ts` chỉ so giá trị thô | P1 | Đây là công cụ **benchmark**. Tô thắng cho chênh lệch dưới mức nhiễu là over-claim — đúng thứ một giám khảo kỹ thuật sẽ bắt bẻ đầu tiên | Chỉ tô khi chênh lệch vượt ngưỡng có ý nghĩa (CI không chồng nhau, hoặc `|Δ| > ε` theo từng metric). Dưới ngưỡng: hiển thị cả hai trung tính + chip `≈ ngang nhau`. Kèm cột `Δ` thay vì chỉ tô màu |
| 10 | **Xanh lá `--ok` mang hai nghĩa** | `.comparison-value.is-best { color: var(--ok) }` (3448) trùng màu với `.badge.ok` = "đạt gate / recommended" (776) | P1 | Cùng một xanh vừa nói "vượt chuẩn an toàn" vừa nói "nhỉnh hơn 0.1 giây". Semantic bị pha loãng | Giữ `--ok` **chỉ cho pass/fail**. "Dẫn đầu metric" dùng nền `--accent-soft` + `font-weight: 700`, không dùng màu chữ |
| 11 | **Xanh dương vừa là link vừa là Candidate A** | `globals.css:2018` `--candidate-a: var(--accent)`; `a { color: var(--accent) }` (166) | P1 | Nền xanh nhạt của cột A gợi ý "vùng tương tác", nhưng nó chỉ là nhãn danh tính | Tách: `--candidate-a: var(--indigo)`, `--candidate-b: var(--teal)`. Trả `--accent` về đúng một việc: tương tác. Đồng thời **bỏ nền tô cả cột**, chỉ giữ một vạch 3px màu candidate ở đầu cột |
| 12 | **`—` không có chú giải** | Hàng `Episodes with no route found` cho cả hai cột đều `—` | P1 | Không phân biệt được "bằng 0" với "không đo". Trong bảng đánh giá an toàn, đó là hai kết luận khác nhau | Nếu là 0 thì in `0`. Nếu không đo được thì in `không đo` (12px, `--muted`), không dùng ký hiệu |
| 13 | **Vị trí Gate mâu thuẫn với hợp đồng do chính trang tuyên bố** | Doc comment đầu `page.tsx:4-10`: gate chạy **trước** khi chấm điểm, ứng viên trượt gate "is not a choice". Nhưng lưới G1–G6 nằm ở **đáy** bảng, dưới 12 hàng metric | P1 | Thứ tự trên màn hình đảo ngược thứ tự trong lập luận. Người đọc gặp điểm số trước điều kiện hợp lệ | Đưa trạng thái gate lên **ngay dưới header mỗi cột**, dạng một dòng gọn: `G1–G6 · đạt` hoặc `chặn ở G4`. Lưới chi tiết 6 ô để trong `<details>` mở được |
| 14 | **`.notice` chỉ có một kiểu (vàng) cho ba mức nghiêm trọng khác nhau** | `globals.css:1112` một class duy nhất. Dùng cho `sample.interrupted`, `sample.belowNMin`, và host warning | P1 | "Mẫu dưới N_min" **vô hiệu hoá mọi số** bên dưới; "host chưa ghim CPU" chỉ ảnh hưởng **một** metric. Cùng màu vàng ⇒ người đọc học cách bỏ qua cả hai | Ba biến thể: `.notice--info` (viền `--border`, nền `--panel-2`), `.notice--warn`, `.notice--critical` (viền `--err`). Cảnh báo phạm vi hẹp thì gắn **vào đúng hàng** nó nói tới (host warning thuộc hàng p99), không đặt trên đầu bảng |
| 15 | **Sidebar 60% là văn xuôi** | `.sidebar-desc` (`globals.css:322`) + 14 khoá `nav.desc.*` (`en.json:1139-1154`). Ví dụ: "Try one episode before spending hours", "Where things stand" | P1 | Đây là **copy hướng dẫn** được ship thành chrome vĩnh viễn. Nó tốn 2 dòng/mục, đẩy mục cuối xuống dưới fold, và là dấu hiệu AI-slop rõ nhất về mặt copy | Bỏ mô tả khỏi rail. Chuyển thành `title`/tooltip, hoặc hiện **chỉ cho mục đang hover**. Rail còn lại: icon + nhãn, 32px/hàng, cả 14 mục vừa một màn |
| 16 | **Tiêu đề nhóm sidebar là lời kể quy trình** | `nav.section.doing` = "WHAT YOU ARE DOING", `nav.section.retiring` = "BEING REPLACED" (`en.json:1136-1138`) | P1 | "BEING REPLACED" nói thẳng với giám khảo rằng sản phẩm đang dở dang. Nhãn điều hướng phải là **danh từ chỉ nơi chốn**, không phải trạng thái dự án | `Workflow` / `Tài nguyên` / `Tài khoản` (ba khoá `nav.section.workspace/results/account` đã có sẵn ở `en.json:75-77`, đang không dùng). Mục cũ: giữ trong nhóm chính, gắn chip `Legacy` nhỏ |
| 17 | **Badge `Produced a card`** | `en.json:794` | P2 | Câu nói về nội bộ hệ thống, không nói về kết quả. Người ngoài không biết "card" là gì | `Đã có khuyến nghị` / `Chưa xếp hạng`. Thuật ngữ "Decision Card" chỉ dùng ở nơi giải thích được |
| 18 | **Breadcrumb hiện UUID thô** | `Decisions / 5753d464c9f6` | P2 | Không phải tên. Không giúp định vị | `Decisions / sudden_stop_v5` — trùng H1 nhưng đó là mục đích của breadcrumb. UUID để trong nút copy nhỏ |
| 19 | **Năm bán kính bo góc + một hình tròn trong một khung nhìn** | `.panel` 8 (665) · `.stat-card` 10 (1246) · `.decision-page-icon` 10 (2033) · `.badge` 10 (768) · `.comparison-gate-grid > div` 6 (3452) · `button` 6 (672) · `.notice` 6 (1112) · `.hint-mark` 50% (1131) | P2 | Không có thang. Badge `border-radius: 10px` trên chữ 11px thành viên thuốc — cộng với 8 pill trong ảnh là dấu hiệu "quá nhiều pill" | Ba bậc: `--radius-sm: 4px` (badge, chip, input) · `--radius-md: 6px` (button, notice, cell) · `--radius-lg: 8px` (panel). Bỏ hoàn toàn 10px và 50% |
| 20 | **Padding lệch lưới 8px** | `.comparison-cell` `8px 14px` (3404) · `.panel` `16px` (668) · `.comparison-results-head` `14px 16px` (2133) · `main.content` `22px 26px 40px` (373) · `.stat-card` `14px 16px` (1250) | P2 | 14 / 22 / 26 không thuộc thang nào. Mắt không đọc ra con số nhưng đọc ra sự "gần đúng" | Thang cứng 4/8/12/16/24/32. `main.content` `24px 32px 40px`; `.comparison-cell` `10px 16px`; head `12px 16px` |
| 21 | **Cỡ chữ nửa pixel** | `.comparison-label` `14.5px` (3436) · `.comparison-limit` `12.5px` (3439) | P2 | `14.5px` là dấu vết chỉnh-tay-từng-nấc, không phải thang typography | Thang: 11 / 12 / 13 / 14 / 16 / 20 / 24. Label 14px/600, limit 12px/400 |
| 22 | **Icon trang trí không mang thông tin** | `.decision-page-icon` ô 40px nền accent (2033); `.candidate-result-icon` ô 34px mỗi cột (3423) — **cùng icon `cpu` cho cả hai** candidate | P2 | Icon giống nhau trên hai thứ khác nhau = trang trí thuần tuý. Chiếm chỗ ở đúng vùng đắt nhất của header | Bỏ cả hai. Nếu muốn giữ dấu hiệu cột: vạch màu 3px ở cạnh trên cột, không phải ô icon |
| 23 | **Chiều cao hàng không compact cũng không thoáng** | `8px` dọc + label `14.5px`/1.35 ⇒ ~37px/hàng × 12 hàng | P2 | Ở laptop 13", lưới gate bị đẩy khỏi màn hình đầu | Hàng 32px (`padding: 6px 16px`, label 14px/1.3). 12 hàng tiết kiệm ~60px — đủ để dòng gate lên trên fold |
| 24 | **`!important` chống lại inline style của chính mình** | `page.tsx:200` set `style={{gridTemplateColumns}}`; `globals.css:3462` phải dùng `grid-template-columns: ... !important` để override ở <900px | P2 | Không thấy trên ảnh nhưng là mùi code: inline style buộc mọi responsive rule phải leo thang | Đổi sang CSS custom property: JSX set `style={{"--cols": n}}`, CSS đọc `repeat(var(--cols), …)`. Media query ghi đè bình thường, không cần `!important` |
| 25 | **Font hệ điều hành, không có webfont** | `globals.css:162` `ui-sans-serif, system-ui, -apple-system, "Segoe UI"` | P2 | Trên Windows ra Segoe UI. Dấu tiếng Việt (đặc biệt tổ hợp trên chữ hoa: `Ố`, `Ề`, `Ữ`) ở 10–11px của eyebrow/`<code>` bị sát nhau và cụt. Ngoài ra "font mặc định OS" chính là dấu hiệu app chưa qua tay designer | `Be Vietnam Pro` (thiết kế riêng cho tiếng Việt, dấu rõ ở cỡ nhỏ) làm chính, `Inter` fallback. Nạp qua `next/font/google`, subset `latin` + `vietnamese`, `display: "swap"` |

### Phân định: lỗi thẩm mỹ vs lỗi UX/thông tin

**Lỗi UX / thông tin / workflow** (làm người dùng hiểu sai hoặc không làm được việc):
`#1` lẫn ngôn ngữ · `#2` không phân biệt được hai ứng viên · `#7` hiểu ngược
xác suất va chạm · `#9` over-claim thắng thua · `#12` `—` mơ hồ ·
`#13` gate sai vị trí trong lập luận · `#14` mọi cảnh báo cùng một mức ·
`#15` `#16` sidebar kể quy trình thay vì điều hướng · `#17` `#18` copy nội bộ.

**Lỗi thẩm mỹ / hệ thống thiết kế** (không sai thông tin, nhưng làm mất uy tín):
`#3` `#4` `#5` `#6` `#8` `#10` `#11` `#19`–`#25`.

Đáng chú ý: `#3`, `#4`, `#5`, `#6` **thuộc nhóm thẩm mỹ nhưng ở mức P0**, vì
chúng là thứ đập vào mắt trong 5 giây đầu — và ba trong bốn cái là **bug**
(token không tồn tại) chứ không phải quyết định thiết kế.

### Dấu hiệu AI-slop xác nhận có trong ảnh

| Dấu hiệu | Có? | Bằng chứng |
|---|---|---|
| Gradient / glow lạm dụng | **Không** | Không có `linear-gradient` nào trong vùng này. Điểm cộng |
| Shadow lạm dụng | **Không** | `--shadow` chỉ dùng cho hint bubble và dashboard card |
| Quá nhiều card / pill | **Có** | 3 stat card thừa (`#5`) + 8 pill trong một khung nhìn: `Produced a card`, `astar+dwa` (trophy), `Recommended`, `lidar_only` ×2, `EN`. Badge `border-radius: 10px` trên chữ 11px |
| Bo góc quá lớn | **Một phần** | Không có 16–24px, nhưng 5 giá trị khác nhau + `50%` — vấn đề là **thiếu thang**, không phải quá tròn |
| Khoảng trắng vô nghĩa | **Có, nặng** | `#4` — không `max-width`, cột giá trị 480px chứa 6 ký tự |
| Copy sáo rỗng | **Có, nặng** | `#15` `#16` `#17` — "Where things stand", "Try one episode before spending hours", "WHAT YOU ARE DOING", "BEING REPLACED" |
| Icon trang trí | **Có** | `#3` (20 dấu `?` đen đậm do bug) + `#22` (cùng icon `cpu` cho hai candidate khác nhau) |
| Màu không có semantic | **Có** | `#10` xanh lá hai nghĩa · `#11` xanh dương vừa link vừa candidate A · bảng token có 10 hue (`purple/cyan/indigo/teal/goal/orange/…`) trong khi trang này chỉ cần 4 |
| Dữ liệu giả | **Không** | Số liệu thật từ sweep. Điểm cộng lớn |
| Chart thiếu đơn vị / ngữ cảnh | **Một phần** | Bảng có đơn vị đầy đủ (`%`, `m`, `s`, `ms`, `MB`) — tốt. Nhưng thiếu **ngữ cảnh diễn giải**: `#7` (bound 3/N), `#9` (không có Δ hay CI), `#12` (`—`) |

---

## B. Design direction

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│ Topbar 52px — sticky, viền dưới 1px, KHÔNG backdrop-blur     │
├────────────┬─────────────────────────────────────────────────┤
│ Rail 232px │  main: max-width 1440px, margin-inline auto     │
│ sticky     │  padding 24px 32px 48px                         │
│ icon+nhãn  │                                                 │
│ 32px/hàng  │  Bố cục hai cột từ ≥1280px:                     │
│ không mô tả│    [ nội dung chính  minmax(0,1fr) ]            │
│            │    [ cột phụ cố định 320px ]  gap 24px          │
└────────────┴─────────────────────────────────────────────────┘
```

Bỏ `backdrop-filter: blur(8px)` trên topbar (`globals.css:388`): trên light
theme nó chỉ tạo một dải mờ đục, tốn compositing, không giải quyết vấn đề nào.
Thay bằng nền đặc `--bg` + viền dưới.

### Grid & spacing

Thang 4px, chỉ dùng các bậc sau — không có giá trị nào ngoài danh sách:

```css
--space-1: 4px;   --space-2: 8px;    --space-3: 12px;
--space-4: 16px;  --space-5: 24px;   --space-6: 32px;  --space-7: 48px;
```

Xoá mọi `14px`, `22px`, `26px`, `18px`, `9px`, `10px` đang có trong padding.

### Typography

Nạp trong `layout.tsx`:

```ts
import { Be_Vietnam_Pro, JetBrains_Mono } from "next/font/google";

const sans = Be_Vietnam_Pro({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});
const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});
```

`Be Vietnam Pro` được vẽ riêng cho tiếng Việt — dấu thanh trên nguyên âm có mũ
(`ế`, `ồ`, `ữ`) không chồng lên nhau ở 12px, chỗ Inter phải nén. Inter làm
fallback cho môi trường không tải được webfont.

Thang chữ — **7 bậc, không có nửa pixel**:

| Token | px / line-height / weight | Dùng cho |
|---|---|---|
| `--fs-caption` | 11 / 1.4 / 600, `letter-spacing .06em`, uppercase | Eyebrow, nhãn cột, section title |
| `--fs-sm` | 12 / 1.45 / 400 | Ngưỡng, chú thích, badge |
| `--fs-body` | 13 / 1.5 / 400 | Văn bản phụ, notice |
| `--fs-label` | 14 / 1.4 / 600 | Nhãn metric trong gutter |
| `--fs-value` | 16 / 1.2 / 600, mono, tabular | Giá trị metric |
| `--fs-h3` | 18 / 1.3 / 600 | Tiêu đề panel |
| `--fs-h1` | 24 / 1.25 / 650 | Tên phép so |

Body mặc định `13px` (đang là 14px) — semi-compact như brief yêu cầu.

### Color tokens (light)

Cắt bảng màu từ 10 hue xuống **4 vai trò + 2 danh tính**. Giữ nguyên nền tảng
`--bg` / `--panel` / `--border` / `--text` / `--muted` hiện có, chúng đã đúng.

```css
:root[data-theme="light"] {
  /* Nền — giữ nguyên, đang tốt */
  --bg:            #f6f7f9;
  --panel:         #ffffff;
  --panel-2:       #f1f3f6;
  --border:        #e3e7ee;   /* nhạt hơn #d8dde6: viền phải lùi lại */
  --border-strong: #c4ccd8;
  --text:          #14181f;
  --muted:         #5a6472;

  /* Tương tác — CHỈ dùng cho link, focus, nút chính. Không dùng làm nhãn */
  --accent:         #1f6feb;
  --accent-contrast:#ffffff;
  --accent-soft:    rgba(31,111,235,.08);

  /* Trạng thái — CHỈ dùng cho pass/fail/cảnh báo. Không dùng cho "dẫn đầu" */
  --ok:   #1a7f37;  --ok-soft:   rgba(26,127,55,.10);
  --warn: #9a6700;  --warn-soft: rgba(154,103,0,.10);
  --err:  #cf222e;  --err-soft:  rgba(207,34,46,.09);

  /* Danh tính candidate — tách khỏi --accent (xem QA #11) */
  --candidate-a: #5267c9;  --candidate-a-soft: rgba(82,103,201,.06);
  --candidate-b: #087f6a;  --candidate-b-soft: rgba(8,127,106,.06);
}
```

Ngừng dùng `--purple / --cyan / --goal / --orange / --info` trên trang này.
Giữ chúng trong file cho các trang khác, nhưng trang decision không tham chiếu.

### Radius & border & shadow

```css
--radius-sm: 4px;   /* badge, chip, input, ô gate */
--radius-md: 6px;   /* button, notice, cell */
--radius-lg: 8px;   /* panel */
--border-w: 1px;
--shadow-pop: 0 4px 12px rgba(20,24,31,.10);  /* CHỈ cho popover/tooltip/menu */
```

Panel **không có shadow**. Phân tách bằng viền 1px trên nền `--bg` xám nhạt.
Đây là điểm phân biệt giữa "deep-tech" và "SaaS landing page".

---

## C. Component rules

### Button

| Biến thể | Nền | Chữ | Viền | Dùng khi |
|---|---|---|---|---|
| `primary` | `--accent` | `--accent-contrast` | none | Một hành động chính duy nhất mỗi màn (Duyệt) |
| `default` | `--panel` | `--text` | `1px --border` | Hành động phụ (Xuất Excel, Xuất báo cáo) |
| `ghost` | trong suốt | `--muted` | none | Trong toolbar, trong hàng bảng |
| `danger` | `--panel` | `--err` | `1px --err` | Thu hồi duyệt |

Chung: cao **32px**, `padding: 0 12px`, `--radius-md`, `--fs-body`, `font-weight: 600`.
`:hover` = `--hover` overlay, **không đổi màu viền** (hiện tại `button:hover`
đổi viền sang `--accent` ở `globals.css:679` — làm mọi nút trông như đang focus).
`:focus-visible` = `outline: 2px solid --accent; outline-offset: 2px`.
`:disabled` = `opacity: .5`, không đổi màu.

### Input / Select

Cao 32px, `padding: 0 10px`, viền `1px --border`, `--radius-md`, nền `--panel`.
Focus: viền `--accent` + `box-shadow: 0 0 0 3px var(--accent-soft)`.
Label 12px/600 `--muted`, cách input 4px. Lỗi: viền `--err` + dòng 12px `--err` phía dưới.

### Table so sánh — quy tắc riêng, đây là component quan trọng nhất trang

- Gutter **canh trái**, `--fs-label`, `color: --text`.
- Giá trị **canh phải**, `--font-mono`, `--fs-value`, `tabular-nums`.
- Hàng cao **32px** (`padding: 6px 16px`).
- Viền: **chỉ đường ngang** `1px --border`. Không viền dọc giữa các cột
  (bỏ `.comparison-cell + .comparison-cell { border-left }` ở `globals.css:3411`).
  Cột đã được phân biệt bằng vạch màu ở header rồi.
- **Không tô nền cả cột.** Thay bằng vạch `3px` màu candidate ở cạnh trên header cột.
- Zebra: `tr:nth-child(even) { background: --panel-2 }` với alpha rất thấp.
  Chọn zebra **hoặc** viền ngang, không dùng cả hai.
- Đơn vị đi cùng giá trị, `--fs-sm`, `--muted`, cách số 2px: `7.85`+` ms`.
- Ngưỡng (`limit 50`) nằm ở gutter dưới nhãn, `--fs-sm --muted` — đúng như hiện tại.
- Ô "dẫn đầu": `background: --accent-soft`, `font-weight: 700`. **Không đổi màu chữ.**
- Ô "ngang nhau" (dưới ngưỡng ý nghĩa): không nhấn gì cả, thêm chip `≈` ở gutter.
- Sticky: hàng header cột `position: sticky; top: 52px`.

### Tabs

Underline, không phải pill. Cao 36px, `padding: 0 12px`, `--fs-body`.
Active: `color --text`, `font-weight: 600`, `box-shadow: inset 0 -2px 0 --accent`.
Inactive: `--muted`. Container có viền dưới `1px --border` chạy suốt.

### Card / Panel

`background --panel`, `border 1px --border`, `--radius-lg`, `padding --space-4`,
`margin-bottom --space-5`. **Không shadow.** Header panel: `padding --space-3
--space-4`, viền dưới `1px --border`, tiêu đề `--fs-h3`, hành động dồn phải.

Một card chỉ tồn tại khi nó **nhóm** nhiều thứ. Một con số đơn lẻ không cần card
(xem QA #5).

### Badge

Cao 20px, `padding: 0 6px`, `--radius-sm`, `--fs-sm`, `font-weight: 600`.
Bốn kiểu duy nhất: `neutral` (nền `--panel-2`, chữ `--muted`), `ok`, `warn`, `err`
— mỗi kiểu là `*-soft` nền + màu chữ tương ứng.
**Không icon trong badge** trừ khi badge đó là kết luận duy nhất của cả panel.

### Hint (`?`)

`color: --muted`, `font-weight: 600`, `opacity: .55`, không viền tròn — dùng
`ⓘ` outline 12px hoặc chữ `?` không khung. `:hover/:focus-visible` → `opacity: 1`,
`color: --accent`. Đổi `role="button"` thành `<button type="button">` thật.

### Chart (Recharts, đã có sẵn trong dependency)

- Lưới: chỉ đường ngang, `stroke: --border`, `strokeDasharray: "2 4"`.
- Trục: `--fs-sm --muted`. Trục Y **luôn có đơn vị** ở nhãn trục, không ở từng tick.
- Đường: `strokeWidth: 2`, màu `--candidate-a` / `--candidate-b` — cùng màu với cột bảng.
- **Không** `<defs><linearGradient>` để tô dưới đường. Nếu cần vùng: `fillOpacity: .06` màu đặc.
- Tooltip: nền `--panel`, viền `1px --border`, `--radius-md`, `--shadow-pop`,
  giá trị mono tabular.
- Legend nằm **trên** chart, canh trái, dạng chip 12px — không nằm dưới, không canh giữa.
- Mọi chart phải có: đơn vị, số mẫu (`n=30`), và khoảng thời gian.

### States

| State | Quy tắc |
|---|---|
| **Loading** | Skeleton đúng hình dạng nội dung sẽ tới (hàng 32px, nền `--panel-2`, `--radius-sm`). **Không spinner**, không chữ "Đang tải…" — hiện tại `page.tsx:91` trả `<p className="muted">` trần |
| **Empty** | Một dòng nói chuyện gì (`--fs-body --text`) + một dòng nói làm gì tiếp (`--fs-sm --muted`) + một nút `default`. Không illustration, không icon lớn |
| **Error** | Nền `--err-soft`, viền `1px --err`, `--radius-md`. Câu đầu = chuyện gì xảy ra bằng lời người. Câu hai = mã lỗi/chi tiết trong `<code> --fs-sm`. Kèm nút "Thử lại" |
| **Success** | Chip inline `ok` cạnh thứ vừa đổi, tự tắt sau 4s. Không toast toàn màn cho hành động cục bộ |
| **Warning phạm vi hẹp** | Gắn vào chính hàng/ô nó nói tới (host warning → hàng p99), không nổi lên đầu bảng |
| **Warning phạm vi toàn trang** | `.notice--critical` ngay dưới H1, viền `--err`. Chỉ dành cho thứ vô hiệu hoá mọi số bên dưới (`n < n_min`) |

---

## D. Mô tả màn hình redesign — đủ chi tiết để implement

> Mọi giá trị dưới đây là **tuyệt đối**. Không suy diễn thêm style, không thêm
> gradient, không thêm shadow, không thêm icon ngoài danh sách được nêu.

### D.0 Điều kiện tiên quyết (làm trước, đây là bug fix)

1. `globals.css:1135` — `var(--text-muted)` → `var(--muted)`.
2. `:root` thêm `--font-sans` / `--font-mono`; `globals.css:3446` bỏ stack mono hard-code, dùng `var(--font-mono)`.
3. `hostinfo.py:185-187` — trả object có khoá, không trả câu tiếng Việt. Thêm `decisions.env.unpinned` vào cả `en.json` và `vi.json`.
4. `main.content` — thêm `max-width: 1440px; margin-inline: auto;`.

### D.1 Sidebar (rail)

Rộng **232px** (từ 264px). Nền `--panel`, viền phải `1px --border`.
Padding `--space-3`.

- **Brand**: ô 28px `--radius-md`, nền `--accent-soft`, icon 16px `--accent`.
  Cạnh nó `PlanBench` 14px/600. **Bỏ dòng tagline** "AMR/AGV planning benchmark
  — simulation only" — chuyển xuống trang System Information.
- **Nhóm**: tiêu đề `--fs-caption --muted`, `padding: 0 8px 4px`,
  `margin-top --space-3`. Ba nhóm: `Workflow` · `Tài nguyên` · `Tài khoản`
  (dùng lại `nav.section.workspace/results/account` đã có ở `en.json:75-77`).
- **Mục**: cao **32px**, `padding: 0 8px`, `gap 10px`, `--radius-md`,
  icon 16px, nhãn `--fs-body`. **Bỏ `.sidebar-desc`** — nội dung `nav.desc.*`
  chuyển sang thuộc tính `title`.
- **Active**: nền `--accent-soft`, chữ `--accent`, `font-weight: 600`,
  `box-shadow: inset 2px 0 0 --accent` (giữ nguyên, đang đúng — không chỉ dựa vào màu).
- **Mục legacy** (`/benchmarks`, `/leaderboard`, `/scenarios`): ở lại nhóm
  `Tài nguyên`, gắn badge `neutral` chữ `Cũ` canh phải. **Bỏ nhóm "BEING REPLACED"**.

Kết quả: 14 mục × 32px + 3 tiêu đề nhóm ≈ 520px — vừa trọn một màn 13".

### D.2 Header trang

Grid `auto 1fr auto`, `gap --space-3`, `padding-bottom --space-4`,
viền dưới `1px --border`, `margin-bottom --space-5`.

- **Bỏ** `.decision-page-icon` (ô 40px accent) — QA #22.
- Cột 1: eyebrow `COMPARISON DETAIL` `--fs-caption --muted`, dưới nó
  `<h1>sudden_stop_v5</h1>` `--fs-h1`.
- Dòng meta `--fs-sm --muted`: `local_controller_selection · 2026-08-21 03:07 ·
  <a>All runs</a> · <button ghost>Copy ID</button>`. UUID **không** hiển thị thô.
- Cột 3: badge `ok` `Đã có khuyến nghị` hoặc `neutral` `Chưa xếp hạng`.
- **Dòng mẫu inline** ngay dưới meta, `--fs-sm`, thay cho 3 stat card:
  `30 episode · đủ N_min (30) · chạy đủ yêu cầu`.
  Chỉ khi có bất thường mới render `.notice--critical` riêng.

### D.3 Panel `Kết quả so sánh` — trọng tâm

`.panel`, `padding: 0`, `overflow: hidden`.

**Header panel** (`padding --space-3 --space-4`, viền dưới `1px --border`):
trái là eyebrow `BẰNG CHỨNG THEO CANDIDATE` + `<h3>Kết quả so sánh</h3>`;
phải là badge `ok` `Khuyến nghị: dwa_coarse` — **tên config, không phải tên stack**,
vì cả hai cột đều là `astar+dwa` (QA #2).

**Header cột** (`padding --space-3 --space-4`):
```
┌─ vạch 3px --candidate-a ────────────┐
│ CANDIDATE A                          │  --fs-caption --muted
│ dwa_coarse                           │  --fs-label, --text
│ astar+dwa · lidar_only               │  --fs-sm --muted
│ [badge ok] Khuyến nghị               │  chỉ ở cột được chọn
│ [badge ok] G1–G6 đạt                 │  QA #13 — gate lên đây
└──────────────────────────────────────┘
```
Không icon `cpu`. Không tô nền cả cột. Vạch màu ở **cạnh trên** header là dấu
hiệu duy nhất phân biệt cột.

**Lưới**:
```css
grid-template-columns:
  minmax(260px, 420px)              /* gutter */
  repeat(var(--cols), minmax(150px, 260px));
justify-content: start;             /* phần dư dồn phải, không giãn ô số */
```
JSX set `style={{ "--cols": candidates.length }}` — **không** set
`gridTemplateColumns` inline (QA #24).

**Hàng metric** (cao 32px, `padding: 6px 16px`):
- Gutter: nhãn `--fs-label`, dấu `?` `--muted` `opacity .55`, ngưỡng xuống dòng `--fs-sm --muted`.
- Giá trị: canh **phải**, `--font-mono --fs-value`, `tabular-nums`; đơn vị `--fs-sm --muted` cách 2px.
- Dẫn đầu **có ý nghĩa**: nền `--accent-soft` + `font-weight: 700`. Không đổi màu chữ.
- Ngang nhau: không nhấn; chip `≈` `--fs-sm --muted` ở cuối gutter.
- Chỉ viền ngang `1px --border`. Không viền dọc.

**Hàng đặc biệt — cận trên va chạm** (QA #7):
nhãn `Cận trên xác suất va chạm (quy tắc 3/N)`, giá trị `≤ 10.0%`,
dưới nó dòng `--fs-sm --muted`: `0 va chạm / 30 episode`.

**Host warning** (QA #1, #14): **không** đặt trên đầu bảng. Đặt thành dòng phụ
trong gutter của hàng `Độ trễ planner, p99 gộp`, `--fs-sm`, `color --warn`,
kèm icon cảnh báo 12px: `Đo trên host chưa ghim CPU — giá trị có thể cao hơn thực tế`.

**Chi tiết gate**: `<details>` cuối panel, summary `Chi tiết 6 gate` `--fs-body`.
Bên trong là lưới 6 ô như hiện tại nhưng `--radius-sm`, `padding --space-2`.

### D.4 Responsive

| Breakpoint | Thay đổi |
|---|---|
| ≥1440px | `main` khoá `max-width: 1440px`, căn giữa |
| 1024–1439 | Cột phụ 320px xuống dưới nội dung chính |
| 900–1023 | Rail thu về `--sidebar-width-collapsed` (68px), icon-only |
| <900 | Rail thành drawer (đã có). Bảng so sánh: một candidate mỗi lần, có tab chọn candidate ở đầu bảng — **thay cho** cách xếp chồng hiện tại, vì xếp chồng làm mất hẳn khả năng so sánh |
| <560 | Padding `--space-3`. Cột giá trị `min-width: 0`, cho phép wrap đơn vị xuống dòng |

---

## E. Checklist nghiệm thu

### Alignment
- [ ] Mọi số trong một cột canh phải; dấu thập phân thẳng hàng khi so `7.85` với `17.89`
- [ ] Nhãn metric ở gutter thẳng baseline với giá trị cùng hàng
- [ ] Header cột, hàng cờ, hàng metric, hàng gate dùng chung một lưới — không lưới lồng lưới
- [ ] Eyebrow, H1 và dòng meta thẳng lề trái với cạnh trái panel bên dưới
- [ ] Icon 16px trong rail thẳng trục dọc với nhau ở cả trạng thái mở và thu gọn

### Padding & spacing
- [ ] `grep -nE '(padding|margin|gap): *[0-9]+px' globals.css` — không còn giá trị ngoài 0/4/8/12/16/24/32/48
- [ ] `grep -nE 'font-size: *[0-9]+\.[0-9]' globals.css` — **rỗng** (không còn 14.5px, 12.5px)
- [ ] `grep -nE 'border-radius: *(10|12|14|16|50%)' globals.css` — chỉ còn 50% cho avatar
- [ ] Mọi hàng bảng cao đúng 32px; đo bằng DevTools, không ước lượng

### Responsive
- [ ] 1920 / 1440 / 1280 / 1024 / 900 / 768 / 560 / 390 — không có scroll ngang ở bất kỳ mức nào
- [ ] Ở 1920, bề rộng cột giá trị **không** vượt 260px
- [ ] Ở <900, đổi candidate bằng tab và cả hai vẫn so được — không chỉ xếp chồng
- [ ] Rail thu gọn: tooltip hiện đủ nhãn, không cắt

### Keyboard & focus
- [ ] Tab đi hết trang theo đúng thứ tự đọc, không bẫy focus trong hint bubble
- [ ] Mọi phần tử focus được có `outline: 2px solid --accent; outline-offset: 2px` — hiện `.hint-mark:focus-visible` đang đặt `outline: none` (`globals.css:1148`), **phải sửa**
- [ ] `Hint` là `<button type="button">` thật, không phải `<span role="button">`
- [ ] `Esc` đóng hint bubble và trả focus về mark
- [ ] Skip-link hoạt động và hiện rõ khi focus

### Contrast (WCAG AA)
- [ ] `--muted #5a6472` trên `--panel #ffffff` = **5.9:1** — đạt AA cho chữ thường
- [ ] `--muted` trên `--panel-2 #f1f3f6` = **5.4:1**
- [ ] Chữ 11px của eyebrow phải ≥ 4.5:1 (cỡ nhỏ **không** được hưởng ngưỡng 3:1)
- [ ] `--ok #1a7f37` trên `--ok-soft` — kiểm bằng công cụ, không ước lượng
- [ ] Vạch màu candidate ≥ 3:1 so với `--panel` (là đồ hoạ mang thông tin)
- [ ] Không có thông tin nào **chỉ** truyền bằng màu: "dẫn đầu" phải có `font-weight` hoặc `sr-only` kèm (hiện đã có `sr-only`, giữ lại)

### Hiển thị tiếng Việt
- [ ] Nạp `Be Vietnam Pro` subset `["latin","vietnamese"]` — thiếu subset `vietnamese` sẽ fallback giữa chừng và dấu bị lệch baseline
- [ ] Kiểm chuỗi dấu nặng nhất ở **mọi** cỡ chữ dùng trong app: `Ữ Ế Ộ Ỡ Ợ ự ệ ỗ ẫ ằ` — 11px, 12px, 13px, 14px, 16px, 24px
- [ ] `line-height` tối thiểu **1.4** cho chữ có dấu; 1.2 làm dấu chạm dòng trên
- [ ] `letter-spacing` dương trên uppercase (`--fs-caption`) không làm dấu tách rời chữ cái
- [ ] Chuyển EN ⇄ VI: **không** còn chuỗi hard-code nào từ backend. Kiểm trực tiếp banner host warning
- [ ] Nhãn VI dài hơn EN ~20% — kiểm hàng `Cận trên xác suất va chạm (quy tắc 3/N)` không wrap 3 dòng ở gutter 260px
- [ ] `<html lang>` đổi theo locale (đã đúng ở `layout.tsx:32`)

### Consistency
- [ ] Chỉ **một** stack sans và **một** stack mono trong toàn bộ file CSS
- [ ] `grep -n 'var(--' globals.css` — mọi token được tham chiếu đều có định nghĩa ở `:root`. Viết test cho việc này, vì `--text-muted` và `--font-mono` đã lọt lưới
- [ ] `--accent` không xuất hiện ở bất kỳ chỗ nào mang nghĩa "danh tính" thay vì "tương tác"
- [ ] `--ok` không xuất hiện ở chỗ nào nghĩa là "nhỉnh hơn" thay vì "đạt"
- [ ] Badge chỉ có 4 biến thể; đếm số badge trong một khung nhìn ≤ 4
- [ ] Không `linear-gradient` nào trong `globals.css`
- [ ] `box-shadow` chỉ xuất hiện ở popover/tooltip/menu và ở `inset` của active nav
- [ ] Không còn `!important` nào trong `globals.css`
- [ ] Chiều cao control thống nhất 32px: button, input, select, tab, hàng bảng

### Nội dung / thông tin
- [ ] Không có card nào chứa đúng một con số mà con số đó không bất thường
- [ ] Mọi giá trị có đơn vị; `—` được thay bằng `0` hoặc `không đo`
- [ ] Mỗi "thắng" được tô đều vượt ngưỡng ý nghĩa; dưới ngưỡng hiển thị `≈`
- [ ] Trạng thái gate đọc được **trước** khi đọc điểm số
- [ ] Không nhãn điều hướng nào kể trạng thái dự án ("Being replaced")
