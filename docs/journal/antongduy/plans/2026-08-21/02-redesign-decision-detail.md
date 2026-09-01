# Plan 2 — Redesign trang Decision Detail

Ngày lập: 2026-08-21 · Trạng thái: **đã duyệt, verify lại 2026-08-21, sẵn sàng chạy**
Mock: **[tongduyan_mock-decision-detail-v2.html](../../notes/2026-08-21/tongduyan_mock-decision-detail-v2.html)** — bản dựng *sau* sáu vòng review, khớp từng task dưới đây.

> Hai mock cũ hơn giữ lại làm đối chiếu, **không** phải bản để dựng theo:
> `tongduyan_mock-decision-detail.html` (v1) vẽ trước các vòng review nên còn
> mang `badge--ok`, sidebar 16 mục, `height` cứng và **không có hàng flags**;
> `tongduyan_mock-decision-evalframe.html` (v3) là một hướng thiết kế khác. An đã
> chốt lấy **`<table>` của v3** cho T4 và giữ v2 cho phần còn lại — xem mục
> "Quyết định về mock" ở cuối file.

Nguồn: [note đánh giá](../../notes/2026-08-21/tongduyan_danh-gia-ui-trang-decision-detail.md) mục A và D.

## Mục tiêu

Dựng lại header + panel `Comparison results` của `/decisions/[id]` theo mock đã
duyệt. Đây là màn hình mang đi demo, nên nó đi trước phần còn lại của app.

## Ngoài phạm vi

- Token, thang spacing, font, sidebar → Plan 3.
- Bug token/i18n/focus → Plan 1.
- `TracePanel`, `EvidencePanel`, `ConclusionPanel`, `Outcome`, `HumanActs`,
  `decision-sample-panel` (bảng episode) — **chưa động tới**. Chúng nằm dưới fold
  và không mang lỗi P0. Vẽ mock riêng sau nếu An muốn.

## Phụ thuộc

| Cần trước | Vì sao |
|---|---|
| **Plan 1 toàn bộ** | T5 (i18n host warning) là điều kiện để đưa cảnh báo vào hàng p99 mà không dính chữ tiếng Việt trên trang EN |
| **Plan 3 giai đoạn A2–A4** (thang token, candidate color, notice variant — **không gồm B0 nạp font**) | Cần `--space-*`, `--radius-*`, `--fs-*`, `--candidate-a/b`, `.notice--*` tồn tại. B0 (webfont) đổi mặt chữ toàn app nên KHÔNG được là điều kiện của plan này — Plan 3 đã chuyển nó xuống giai đoạn B |
| **`--font-sans` phải khai từ A2** | T5 dùng `font-family: var(--font-sans)` cho slot đơn vị. Nếu đợi tới B0 thì test token của Plan 1 T6 đỏ ngay lượt implement Plan 2. Không dùng `inherit` thay thế — slot đơn vị phải khác mặt chữ với cột số mono, đó là lý do nó tồn tại |

### Trạng thái phụ thuộc — đã kiểm 2026-08-21, **đủ hết**

| | Xong? | Ghi chú |
|---|---|---|
| Plan 1 T1–T7 | ✅ | bảy report trong `reports/2026-08-21/` |
| Plan 3 **A2** thang token | ✅ commit `4b4431e` | zero-diff, đã chứng minh trên stylesheet |
| Plan 3 **A3** candidate color | ✅ commit `7b287eb` | **đổi màu thật**, An đã kiểm light + dark |
| Plan 3 **A4** biến thể notice | ✅ commit `09265a3` | zero-diff, chưa component nào mang class |

Mười token Plan 2 cần (`--space-4`, `--radius-md`, `--fs-caption/sm/body/label`,
`--candidate-a/b`, `--font-sans`, `--font-mono`) đều đã khai, mỗi cái đúng một
lần. Plan 3 **tạm dừng từ B0** để nhường lượt cho plan này.

Một hệ quả về thứ tự vẫn còn giá trị: **A3 chạy trước T2** — T2 bỏ nền tô cột
candidate, nên nếu làm ngược lại thì có một quãng cột mang màu mới ở đúng chỗ sắp
bị xoá, và ảnh chụp quãng đó vô nghĩa. A3 đã xong trước, đúng thứ tự.

---

## Task

### T1 — `SampleBanner` → một dòng, card chỉ khi bất thường

`apps/web/src/app/decisions/[id]/page.tsx:1140-1178`

Hiện render ba `Figure` vô điều kiện. Với run bình thường ra ba số `30` giống hệt
nhau ở 26px.

**Sửa**: bỏ `.stat-grid`. Render một dòng `.sample-line` trong `page-head`.

**Mệnh đề N_min phải render CÓ ĐIỀU KIỆN.** Bản plan trước cố định chuỗi
`meets N_min (30)` cho mọi run — nên một run `n=18, n_min=30` sẽ **tự tuyên bố
đạt N_min ngay trên dòng tóm tắt**, rồi notice critical bên dưới nói ngược lại.
Notice không sửa được lời nói dối nằm trong chính dòng nó chú thích; người đọc
lướt chỉ đọc dòng đầu.

```ts
const short = sample.n_episodes < sample.n_min_required;
```

| Ca | Khoá | EN | VI |
|---|---|---|---|
| `!short` | `decisions.sample.line.meetsNMin` | `meets N_min ({min})` | `đạt N_min ({min})` |
| `short` | `decisions.sample.line.belowNMin` | `below N_min ({n}/{min})` | `dưới N_min ({n}/{min})` |

Ca `short` in **cả hai số** vì đó chính là thông tin còn thiếu: `N_min required:
30` một mình không nói run chạy được bao nhiêu.

Mệnh đề `· ran the full request` **chỉ** khi đủ cả ba điều kiện — run cũ thiếu
`n_episodes_requested` không được tự nhận chạy đủ:
```ts
sample.n_episodes_requested !== undefined
  && sample.n_episodes >= sample.n_episodes_requested
  && !sample.interrupted
```

**Precedence notice — tối đa MỘT notice**, không xếp chồng:
1. `short` → `.notice--critical`. Nếu đồng thời `interrupted` thì nội dung
   critical **kèm luôn** ý bị ngắt (khoá i18n riêng cho ca gộp) — không render
   notice thứ hai.
2. ngược lại, `interrupted` → `.notice--warn`.
3. `coverage(run) < 1` → không phải notice, thêm mệnh đề `· coverage {x}%`
   vào dòng sample.

Notice vẫn là chỗ **giải thích hậu quả** ("cận trên rủi ro còn lỏng hơn mức đã
khai"); dòng summary chỉ có một việc là **nói đúng trạng thái**.

Khoá i18n mới: `decisions.sample.line.full`, `decisions.sample.line.meetsNMin`,
`decisions.sample.line.belowNMin`, `decisions.sample.belowNMinInterrupted`
(ca gộp).

**Nghiệm thu**: run 30/30/30 → một dòng `meets N_min (30)`, không card, không
notice. Run `n=18, n_min=30` → dòng ghi `below N_min (18/30)`, **không** ghi
`meets`. Run `n=18, n_min=30, interrupted` → dòng `below N_min (18/30)` + đúng
**một** `.notice--critical` nói cả hai ý. Run cũ không có `n_episodes_requested`
→ dòng sample không có mệnh đề "ran the full request".

Test: bốn ca trên là bốn assertion trên hàm thuần `sampleLine()` /
`sampleNotice()` (xem mục Hạ tầng test), khẳng định ca `short` chọn khoá
`belowNMin` chứ **không** chọn `meetsNMin`.

---

### T2 — Header cột: trường KHÁC NHAU làm tiêu đề, bỏ ô icon

`page.tsx:203-215` · CSS `globals.css:3413-3425`

Hiện `<h4>{candidate.stack_label}</h4>` 15px và `<code>{local_controller_config}</code>`
10px muted. Trên phép so local-controller cả hai cột đều `astar+dwa`, nên tiêu đề
không phân biệt được gì.

> **Đính chính — bản trước chốt sai và nó hỏng trên phần lớn dữ liệu thật.**
> Bản trước viết "config làm tiêu đề" như một luật cố định, vì nó chỉ nhìn một
> loại run. Kiểm 16 run đang có trong DB:
>
> | `experiment_scope` | Trường khác nhau | Trường giống nhau | Số run |
> |---|---|---|---|
> | `local_controller_selection` | `local_controller_config` | `stack_label` | 6 |
> | `global_planner_selection` | **`stack_label`** | `local_controller_config` | **10** |
>
> Tương quan tuyệt đối, không ca lẫn — và đúng theo nghĩa của scope: scope khai
> **thành phần nào đang bị hoán đổi**.
>
> Nên "config làm tiêu đề" sẽ in `dwa_coarse` / `dwa_coarse` làm hai tiêu đề
> giống hệt nhau trên **10 trong 16 run** — đúng con bug T2 sinh ra để sửa, chỉ
> là lộn ngược. Run `20750b0d9dbe` mà An vừa xem là một trong 10 run đó.

**Sửa**:
- `<span class="letter">Candidate A</span>` — `--fs-caption`, muted
- **Tiêu đề là trường thực sự khác nhau giữa các candidate** — `--fs-label`, 600,
  màu `--candidate-a/b`:
  ```ts
  /** Trường phân biệt các candidate của run này.
   *
   * Suy từ DỮ LIỆU, không suy từ `experiment_scope`. Hai nguồn khớp nhau
   * trên cả 16 run đang có, nhưng scope là một lời khai còn dữ liệu là
   * thứ đang hiện trên màn hình — nếu chúng lệch nhau thì tiêu đề phải
   * theo cái người đọc nhìn thấy.
   */
  export function headingField(candidates: RunCandidate[]): "stack" | "config" {
    const stacks = new Set(candidates.map((c) => c.stack_label));
    // Hoà (một candidate, hoặc cả hai trường đều khác) → stack, như cũ.
    return stacks.size > 1 ? "stack" : "config";
  }
  ```
  Hàm thuần, test được trong Node: ca `local_controller_selection` → `"config"`,
  ca `global_planner_selection` → `"stack"`, ca một candidate → `"stack"`, ca cả
  hai trường đều khác → `"stack"`.
- Dòng phụ mang trường **còn lại** cộng `local_observation_class`, nên không
  thông tin nào mất đi dù tiêu đề chọn bên nào
- `<span class="stack">…</span>` — `--fs-sm`, muted. Nội dung là **trường không
  được chọn làm tiêu đề**, rồi tới `local_observation_class`:
  ```tsx
  const secondary = heading === "stack"
    ? candidate.local_controller_config
    : candidate.stack_label;
  const parts = [secondary, candidate.local_observation_class].filter(Boolean);
  // → "dwa_coarse · lidar_only"  hoặc  "astar+dwa · lidar_only"
  ```
  **`local_observation_class` là `string | null | undefined`** (`decisions.ts:117`)
  và bản hiện tại đã xử lý ca thiếu (`page.tsx:225`). `.filter(Boolean)` rồi
  `.join(" · ")` là để không ghép mù: ghép mù cho ra `astar+dwa · null`, hoặc —
  vì JSX nuốt `null` — cho ra `astar+dwa ·` cụt đuôi. Khi thiếu thì dòng phụ chỉ
  còn một phần, và badge `observationUnknown` ở hàng flags là nơi nói ra chuyện
  thiếu
- Bỏ `.candidate-result-icon` (`page.tsx:205`, CSS `3423`) — cùng icon `cpu` trên hai thứ khác nhau
- Bỏ nền tô cả cột (`.comparison-cell.candidate-a/b` ở `3405-3406`), thay bằng
  `border-top: 3px solid var(--candidate-a/b)` chỉ trên ô header

`local_observation_class` gộp vào dòng stack ⇒ hàng `.comparison-flags`
(`page.tsx:217-249`) chỉ còn nhiệm vụ hiện badge `stopped_early` và badge
`observationUnknown`. **Giữ cả hai** — chúng là finding, không phải trang trí.
Khi không có gì để hiện thì không render hàng.

**Nghiệm thu**: hai cột đọc ra `dwa_coarse` / `dwa_balanced` ngay. Chụp greyscale
vẫn phân biệt được nhờ chữ, không chỉ nhờ vạch màu.

---

### T3 — Trạng thái gate lên header cột, chi tiết vào `<details>`

`page.tsx:279-303` · CSS `globals.css:3450-3460`

Doc comment đầu file (`page.tsx:4-10`) nói gate chạy **trước** khi chấm điểm và
ứng viên trượt gate *"is not a choice"*. Nhưng lưới G1–G6 nằm dưới 12 hàng metric.

**Sửa**:
- Thêm vào `.marks` của header cột: `<span class="badge ok">G1–G6 cleared</span>`
  hoặc `<span class="badge err">blocked at {blocking_gates.join(", ")}</span>`.
  Dùng lại `candidate.cleared_gates` / `candidate.blocking_gates` đang có.

  **Dùng đúng class đang tồn tại: `.badge.ok` / `.badge.err`** (`globals.css:789`,
  `794`). **Không có** `.badge--ok` / `.badge--err` trong CSS hiện tại, và Plan 3
  A4 chỉ thêm biến thể `.notice--*`, không đụng tới badge. Viết class chưa tồn tại
  rồi trông chờ Plan 3 sau này vá hình là để lại một badge không style suốt quãng
  giữa hai plan — đúng quãng mang đi demo. Đổi convention badge sang `--` là việc
  của Plan 3 giai đoạn B, làm một lượt cho cả app.
- Lưới 6 ô chuyển vào `<details class="gates">` đặt **cuối panel**, sau lưới metric.
- Bỏ hàng `.comparison-grid-foot` khỏi lưới chính.

**Badge trên `<summary>` là badge TỔNG HỢP cho nhiều candidate — phải nói rõ
tỉ lệ, không được mượn trạng thái của một phía**:

| Trạng thái | Badge | Khoá |
|---|---|---|
| mọi candidate qua | `.badge.ok` · `2/2 candidates cleared` | `decisions.gates.summary.allCleared` |
| một phần trượt | `.badge.err` · `1 of 2 candidates blocked` | `decisions.gates.summary.someBlocked` |
| tất cả trượt | `.badge.err` · `2/2 candidates blocked` | `decisions.gates.summary.allBlocked` |

Một badge `cleared` duy nhất khi chỉ một phía đạt là **sai sự thật ở đúng chỗ
người đọc dùng để quyết định có mở `<details>` ra hay không** — tức là chỗ nó
gây hại nhất.

**Nghiệm thu**: đọc header cột là biết ứng viên có hợp lệ không, chưa cần cuộn.
Dựng run một candidate qua một candidate trượt → summary ghi `1 of 2 candidates
blocked`, badge đỏ, **không** ghi `cleared`.

---

### T4 — Lưới thành `<table>`, bỏ inline style, bỏ `!important`, thêm cột Δ

`page.tsx:200` · CSS `globals.css:3402`, `3462`

Hiện là một `display: grid` phẳng, `grid-template-columns` set inline trong JSX,
buộc media query 900px phải dùng `!important` để thắng.

> **An đã chốt: lấy cấu trúc bảng của mock v3, giữ nguyên luật tô của v2.**
> T6 (nền accent cho ô dẫn đầu), T3 (`.badge.ok` / `.badge.err`) và T13 (dòng
> tóm tắt) **không đổi**. Chỉ T4 đổi.

#### Vì sao bảng, không phải grid

Bản plan trước dùng CSS grid và vì thế phải kèm **một luật** (mọi hàng logic phải
phát đủ ô, hàng flags cần một ô Δ placeholder) và **một test** (đếm ô, chia hết
cho 4, đúng một `.cmp-delta--empty`). Cả hai tồn tại chỉ để bù cho một sự thật:
**grid phẳng không biết "hàng" là gì** — nó xếp con theo thứ tự, nên một hàng
thiếu ô sẽ kéo lệch mọi hàng sau nó.

`<table>` không có vấn đề đó. Một `<tr>` **là** một hàng. Hàng flags thiếu ô Δ thì
chỉ hàng đó ngắn đi, không hàng nào khác nhúc nhích. Nên:

| Bỏ được | Vì |
|---|---|
| luật `.comparison-delta--empty` | không còn chỗ để lệch |
| test "đếm ô chia hết cho 4" | test cho một lỗi không tồn tại nữa |
| `--cols` và `--delta-col` | số cột do `<th>`/`<td>` quyết định |
| `!important` ở `globals.css:3462` | không còn inline style để thắng |

**Hệ quả cho Plan 1 T6:** `JSX_PROVIDED = ["--cols", "--delta-col"]` trong
`tokens.test.ts` trở thành hai mục chết. **Xoá chúng cùng lượt này.** Một
allowlist có tên chỉ giữ được ý nghĩa khi mọi mục trong đó còn thật; để lại mục
chết là dạy người sau rằng thêm vào đó không tốn gì.

Bảng cũng là thứ đọc được bằng screen reader mà không phải dán `role="table"` lên
một đống `div`, và cho phép `<th scope="col">` — cái mà grid phẳng không có cách
nào diễn đạt.

#### Cấu trúc

```tsx
<div className="comparison-scroll">          {/* overflow-x: auto */}
  <table className="comparison-table">
    <thead>
      <tr>
        <th scope="col" className="comparison-gutter">{/* nhãn metric */}</th>
        {candidates.map((c, i) => (
          <th scope="col" key={c.candidate_id} className={`comparison-head candidate-${SIDES[i]}`}>…</th>
        ))}
        {hasDelta ? <th scope="col" className="comparison-delta">Δ (B−A)</th> : null}
      </tr>
    </thead>
    <tbody>
      {/* hàng flags — chỉ render khi có candidate nào mang flag */}
      {/* mười hàng metric */}
    </tbody>
  </table>
</div>
```

Hàng flags giờ là một `<tr>` bình thường và **không cần ô Δ**. Nếu muốn viền dưới
liền mạch thì cho nó một `<td>` rỗng — nhưng đó là chuyện thẩm mỹ, không phải
chuyện đúng sai, và bỏ quên nó không làm hỏng gì.

```css
.comparison-scroll { overflow-x: auto; }
.comparison-table  { width: 100%; border-collapse: collapse; min-width: 720px; }
.comparison-table th,
.comparison-table td { padding: 6px var(--space-4); border-bottom: 1px solid var(--border); }
.comparison-gutter { text-align: left; }
```

`min-width` trên bảng cộng `overflow-x: auto` trên vỏ: dưới ngưỡng đó bảng cuộn
ngang **bên trong khung của nó** thay vì đẩy cả trang cuộn ngang.

#### Cột Δ — chỉ khi đúng hai candidate

```ts
const hasDelta = candidates.length === 2;
```

Tính **một lần** rồi truyền xuống; header và mọi `<td>` Δ đều đọc nó. Ba
candidate → không có `<th>`/`<td>` Δ nào trong DOM, không phải render rồi giấu.

- Giá trị `Δ (B−A)`, `--font-mono`, `--fs-body`, muted, canh phải
- Dấu trừ **U+2212** (`−`), không phải hyphen
- Tính từ `MetricRow.values` — trường này **đã tồn tại**
  (`candidateMetrics.ts:36`). Không thêm trường `raw`, không parse lại `text`
- Một trong hai `values` là `null` → ô Δ **trống**, không phải `0`
- Metric `direction: "none"` (chỉ `replans` — lưu ý `distinctEpisodes` khai
  `"higher"` ở `candidateMetrics.ts:162`) vẫn hiện Δ, chỉ là muted
- Ẩn dưới 900px — nó là cột duy nhất tái tạo được từ hai cột kia

#### Δ phải format theo từng metric, không in `values` thô

Đây là phần việc thật của T4:

- Rate lưu `0.7` nhưng hiển thị `70.0 %` ⇒ Δ `0.02` phải in `+2.0 pp`
  (percentage point), không phải `+0.02`
- Latency 2 chữ số thập phân · clearance 3 chữ số · count nguyên

#### `MetricRow` — thêm `numberText`, giữ `text`

Chỉ thêm `unit` là chưa đủ để T5 tách được số khỏi đơn vị. `text` hiện mang **cả
hai**: `asMs` trả `"17.89 ms"`, `asMetres` trả `"0.470 m"`, `asPercent` trả
`"70.0 %"` (`candidateMetrics.ts:118-123`). T5 mà đổ `text` vào `.num` rồi render
thêm `.unit` sẽ ra `17.89 ms ms`. Và **không được cắt phần số bằng cách parse
`text`** — plan này cấm parse chuỗi đã format ở đây thì không thể mở lại ở T5.

```ts
interface MetricRow {
  values: (number | null)[];       // raw, để tính Δ và phân biệt null
  text: string[];                  // số + đơn vị, GIỮ NGUYÊN cho consumer cũ
  numberText: (string | null)[];   // chỉ phần số đã format
  unit?: string;                   // "ms" | "m" | "s" | "%" | "MB" | undefined
  deltaText?: string;              // Δ đã format, U+2212, dấu +/−
}
```

`text` **không đổi và không xoá** — rủi ro "Cao" ở bảng cuối plan nói đúng chỗ
này. Hai trường sinh ra từ **cùng một** helper, không phải hai đường tính
(`asMs` tách thành `msNumber(v) = v.toFixed(2)` rồi `asMs = v => msNumber(v) + " ms"`).

**Test khoá đúng các ca này** (`candidate-metrics.test.ts`):

| Đầu vào | `numberText` | `unit` |
|---|---|---|
| rate `0.7` | `"70.0"` | `"%"` |
| latency `17.891` | `"17.89"` | `"ms"` |
| clearance `0.47` | `"0.470"` | `"m"` |
| count `3` | `"3"` | `undefined` |
| `null` | `null` | không đổi |
| Δ rate `0.02` | `deltaText === "+2.0 pp"` | — |

Thêm một assertion bắt lỗi ghép đôi: với mọi row có `unit`, khẳng định
`numberText[i]` **không chứa** `unit` — đó chính là bug `17.89 ms ms` viết thành
test.

#### Trích `ComparisonGrid` ra component export được

`CandidateComparison` hiện là function **không export** trong `page.tsx:152`, nên
test không import riêng được; render cả `DecisionDetailPage` thì không dùng được
vì nó chạy qua route params, state và một `useEffect` fetch — first render của nó
chỉ ra trạng thái loading.

Đặt ở `apps/web/src/components/ComparisonGrid.tsx`:
```tsx
export function ComparisonGrid({ run, candidates }: { run: DecisionRun; candidates: RunCandidate[] }) { … }
```
Thuần props, không fetch, không route. `useTranslation()` bên trong vẫn chạy được
ngoài provider — `LocaleContext` rơi về `DEFAULT_LOCALE` (`i18n/index.ts:69-70`),
nên `renderToStaticMarkup(<ComparisonGrid … />)` ra HTML tiếng Anh thật, đúng
khuôn mẫu 8 file test đang dùng.

Việc này **vẫn cần** dù đã bỏ test đếm ô: nó là cách duy nhất khẳng định bằng
markup thật rằng hàng `no route found` in `not measured` chứ không in `—`, rằng
run 3 candidate không có `<th>` Δ nào, và rằng tiêu đề cột chọn đúng trường
(T2 `headingField`).

File test mới: `src/components/__tests__/comparison-grid.test.tsx`.

#### Responsive

Rule hiện tại (`globals.css:3462`) ép toàn lưới về **một cột** (xếp chồng
candidate) bằng `!important`. Thay hẳn:

```css
@media (max-width: 900px) {
  /* Δ đi trước — nó là cột duy nhất người đọc dựng lại được từ hai cột kia */
  .comparison-table .comparison-delta { display: none; }
  .comparison-table { min-width: 560px; }
}

@media (max-width: 620px) {
  .comparison-table th,
  .comparison-table td { padding-inline: var(--space-3); }
  .comparison-table { min-width: 460px; }
  .comparison-value { font-size: var(--fs-body); }
}
```

Trong bảng, `display: none` trên `<th>`/`<td>` là hợp lệ — hàng đơn giản còn ít ô
hơn, không có gì để lệch. Dưới 620px bảng cuộn ngang trong vỏ của nó; đó là hành
vi đúng cho một bảng số liệu trên màn hẹp, và tốt hơn hẳn việc bóp cột tới mức
config bị wrap gãy.

#### Nghiệm thu

- Ở 1920 cột giá trị không vượt 260px
- Ở 899px cột Δ biến mất, hai cột candidate còn đọc được
- Run 3 candidate → không có `<th>`/`<td>` Δ nào trong DOM
- Δ của success rate in `pp`, không in số thô
- `grep -n '!important' globals.css` giảm đúng 1
- `grep -n 'cols\|delta-col' apps/web/src/app/__tests__/tokens.test.ts` → rỗng
- Trang **không** cuộn ngang ở bất kỳ breakpoint nào; chỉ bảng cuộn

### T5 — Giá trị canh phải, đơn vị tách khỏi số

CSS `globals.css:3441-3447`

Hiện `text-align: center` vô hiệu hoá `font-variant-numeric: tabular-nums` đã bật
cùng chỗ: `7.85 ms` và `17.89 ms` lệch nhau một ký tự.

**Sửa**: canh phải **kèm slot đơn vị cố định** — right-align cả chuỗi trần chưa
đủ: `ms` rộng khác `m`, khác `MB`, nên dấu thập phân vẫn lệch giữa các hàng.
```css
.comparison-value {
  display: grid;
  grid-template-columns: 1fr 2.5em;   /* số | đơn vị */
  align-items: baseline;
}
.comparison-value .num  { text-align: right; }
.comparison-value .unit { font-family: var(--font-sans); font-size: var(--fs-sm);
                          color: var(--muted); padding-left: 3px; }
```
`var(--font-sans)` **đòi Plan 3 A2 khai token đó trước** — xem bảng Phụ thuộc.
Đừng thay bằng `inherit`: cột số dùng `--font-mono`, và cả điểm của slot đơn vị
là để `ms` không bị tính vào lưới tabular của con số.

Metric **không có** đơn vị (`collisions`, `distinctEpisodes`, `replans` —
`MetricRow.unit === undefined`) vẫn render slot `.unit` **rỗng** — bỏ slot là số
của hàng đó nhảy sang phải, phá thẳng cột dọc.

Cần `MetricRow.numberText` **và** `MetricRow.unit` từ T4:
```tsx
<span className="num">{metric.numberText[index]}</span>
<span className="unit">{metric.unit ?? ""}</span>
```
Không đọc `metric.text` ở component này nữa (nó đã gồm đơn vị), cũng không cắt
chuỗi.

**Nghiệm thu**: đặt `0.470 m` trên `22.5 s` trên `17.89 ms` trên `0` (không đơn
vị) — dấu thập phân và hàng đơn vị của **các hàng khác nhau** đều thẳng cột.
Không hàng nào in đơn vị hai lần.

---

### T6 — Ô dẫn đầu: nền accent, không phải chữ xanh lá

CSS `globals.css:3448`

`.comparison-value.is-best { color: var(--ok) }` trùng màu `.badge.ok` = "đạt gate".
Cùng một xanh nói hai điều.

**Sửa**: `background: var(--accent-soft); font-weight: 700;` — **bỏ `color`**.

**Luật tô giữ nguyên như hiện tại** (An đã chốt): tô mọi chênh lệch theo hướng
metric, không cần ngưỡng ý nghĩa. `leaders()` trong `candidateMetrics.ts` không đổi.

Giữ `<span className="sr-only"> ({t("running.leads")})</span>` đang có — thông tin
không được chỉ truyền bằng nền.

**Nghiệm thu**: ba ô được tô (clearance→B, duration→A, p99→A) đúng như bản hiện
tại. Không ô nào màu xanh lá. Badge `cleared` vẫn xanh lá.

---

### T7 — Cận trên va chạm: ngữ cảnh ra khỏi tooltip

`page.tsx:251-262` · i18n `en.json:1522`, `vi.json:1522`

`Collision probability, 95% upper bound = 10.0%` nằm hai hàng dưới
`Collisions observed = 0`. Lời giải thích (bound là 3/N) nằm trong
`decisions.compare.why.collisionBound` — chỉ hiện khi hover.

**Sửa — ngữ cảnh phải theo TỪNG candidate, không nằm chung ở gutter**: hai
candidate có thể chạy số episode khác nhau (early stop qua `stopped_early`).
Một dòng `0 collisions in 30 episodes` ở gutter — vùng dùng chung — sẽ mượn
sample của candidate này gán cho candidate kia.

- Gutter: nhãn giữ nguyên + dòng phụ `.cmp-sub` chỉ ghi phần đúng cho mọi cột:
  `rule of three`
- Giữ nguyên tooltip — nó nói thêm chứ không nói thay

**Cell KHÔNG phải lúc nào cũng có cận trên.** Hợp đồng G2
(`packages/decision/planbench_decision/gates.py:199`) nói thẳng:

> `upper_bound_95` là `None` một khi đã quan sát được va chạm: rule of three chỉ
> áp cho dữ liệu không-sự-kiện, và trích một cận trên bất chấp là *"arithmetic
> dressed as evidence"*.

Nên cell phải đọc **ba** trường từ `candidate.gates.G2` (payload đã có đủ,
`gates.py:382-395`) và rẽ hai nhánh:

| Trường | Nguồn |
|---|---|
| `observed` | `gates.G2.observed` |
| `n_distinct_episodes` | `gates.G2.n_distinct_episodes` |
| `upper_bound_95` | `gates.G2.upper_bound_95` |

```
upper_bound_95 !== null                 upper_bound_95 === null (có va chạm)
────────────────────────────            ────────────────────────────────────
≤ 10.0 %                                not applicable
0 / 30 distinct episodes                2 collisions / 30 distinct episodes
```

Ca thứ hai **không được** in `≤` (không có cận trên nào để nêu) và **cũng không
được** in `not measured` (phép đo có tồn tại và kết quả của nó rất rõ: đã va
chạm). Hai lỗi này ngược nhau nhưng cùng dẫn tới một hiểu sai — rằng ô đó trống
vì thiếu dữ liệu.

**Mẫu số bắt buộc là `n_distinct_episodes`**, không phải `n_runs`, không phải
`sample.n_episodes` của cả run, không phải `stopped_early.episodes_run`. Payload
G2 cố ý mang **cả hai** đếm, và comment tại `gates.py:386` ghi lý do: *"printing
only the row count is what produced a card claiming 3.0% from one episode driven
a hundred times."* Rule of three giả định mẫu độc lập; episode phát lại không
phải mẫu độc lập. Dùng sai mẫu số ở đây là in ra một cận trên chặt hơn sự thật.

Dùng `n_distinct_episodes` cũng tự giải quyết ca `stopped_early` — candidate dừng
sớm mang đếm phân biệt nhỏ hơn của chính nó, không mượn của bên kia.

Khoá i18n mới: `decisions.compare.sub.collisionBound` (gutter),
`decisions.compare.cell.collisionBoundClean` (2 tham số: `observed`, `n`),
`decisions.compare.cell.collisionBoundObserved` (2 tham số: `observed`, `n`),
`decisions.compare.cell.notApplicable`.

**Nghiệm thu**: đọc hàng đó không hover vẫn hiểu 10% không phải xác suất đo
được. Dựng run có candidate `stopped_early` → cell của nó hiện đúng mẫu số riêng.
Dựng candidate có `observed: 2, upper_bound_95: null` → cell ghi `not applicable`
+ `2 collisions / 30 distinct episodes`, **không** chứa ký tự `≤`, **không** chứa
`not measured`. Dựng candidate `n_runs: 100, n_distinct_episodes: 30` → mẫu số
in `30`.

---

### T8 — `—` thành `0` hoặc `not measured`

`apps/web/src/lib/candidateMetrics.ts`

Hàng `Episodes with no route found` hiện `—` cho cả hai cột. Không phân biệt
"bằng 0" với "không đo".

**Sửa — tầng chịu trách nhiệm dịch là COMPONENT, không phải `candidateMetrics`**:
`candidateMetrics.ts` là module thuần, không có `t()` — nhét chuỗi đã dịch vào
đó là sai tầng. `values[index] === null` là nguồn sự thật; component render:
```tsx
metric.values[index] === null
  ? <span className="not-measured">{t("common.notMeasured")}</span>
  : /* .num + .unit như T5 */
```
Giá trị `0` in `0`. Bỏ hẳn ký tự `—` khỏi cột giá trị (trong `text` của
`candidateMetrics` nó có thể còn — component không dùng `text` cho ca null nữa).

Khoá i18n mới: `common.notMeasured` (`not measured` / `không đo`).

**Nghiệm thu**: không còn `—` nào trong lưới so sánh.

---

### T9 — Host warning vào hàng p99

`page.tsx:325` (`HostWarning`) · CSS `globals.css:2132` (`.comparison-host-warning`)

Hiện là một dải vàng trên đầu bảng ⇒ trông như nó bôi bẩn mọi số. Thực tế G4 đọc
wall-clock nên nó chỉ bôi bẩn **một** hàng.

**Sửa**: bỏ `<HostWarning>` khỏi vị trí hiện tại. Render trong gutter của hàng
`p99` như `.cmp-warn`: icon cảnh báo 12px + text `--fs-sm` màu `--warn`.

Cần Plan 1 T5 để text ra đúng ngôn ngữ.

**Nghiệm thu**: cảnh báo nằm cạnh đúng số nó nói tới. Run có host đã ghim → không
hiện gì.

---

### T10 — Header trang: bỏ ô icon, thêm nút copy id

`page.tsx:95-103` · CSS `globals.css:2028-2033`

**Sửa**:
- Bỏ `.decision-page-icon` (ô 40px nền accent, `page.tsx:96`)
- Grid `auto 1fr auto` → `minmax(0,1fr) auto`
- Dòng meta thêm nút copy `run.id`, hiện id dạng `<code>` 12px trong nút

**Class: `.decision-copy-id` khai cục bộ TRONG plan này.** `globals.css` hiện
**không có** `.btn`, cũng không có `.btn--ghost`; button variant của Plan 3 nằm ở
giai đoạn B, chạy sau Plan 2. Viết `class="btn btn--ghost"` bây giờ cho ra một
nút không style suốt quãng giữa hai plan. Khai một class hẹp ngay tại đây (viền
`--border`, nền trong, `--radius-md`, `--fs-sm`, hover `--panel-2`); Plan 3 B gộp
nó vào hệ button chung khi hệ đó ra đời.

**Hành vi phải chốt, không để mở** — bản trước chỉ nói "thêm button copy":

| Mục | Chốt |
|---|---|
| API | `copyDecisionId(run.id, (t) => navigator.clipboard.writeText(t))` — helper thuần, xem mục Hạ tầng test. Không dùng `document.execCommand`, đã deprecated |
| Báo thành công | Nhãn nút đổi sang `Copied` / `Đã sao chép` trong **4 giây** rồi trả lại. `setTimeout` phải được clear ở cleanup của `useEffect` — bấm liên tục rồi rời trang là set state trên component đã unmount |
| Báo lỗi | Clipboard bị từ chối (không có permission, hoặc trang không phải secure context) → **giữ id vẫn nhìn thấy** trong `<code>` và hiện nhãn `Copy failed` / `Sao chép lỗi`. Bọc `try/catch`; **không để unhandled promise rejection** — `writeText` reject là chuyện thường, không phải bug |
| a11y | `aria-label={t("decisions.detail.copyId", { id: run.id })}` → `Copy decision ID 5753d464c9f6`. Nhãn trạng thái đổi trong vùng `aria-live="polite"` để screen reader nghe được kết quả; nút không được chỉ đổi màu |
| i18n | `decisions.detail.copyId`, `decisions.detail.copied`, `decisions.detail.copyFailed` |

Vì id vẫn hiển thị nguyên vẹn ở mọi trạng thái, ca lỗi vẫn dùng được: người đọc
bôi đen chép tay.

**Test** — trên helper thuần `copyDecisionId(id, write)`, không phải trên nút:
- `write` resolve → trả `"copied"`, và nhận đúng `run.id`
- `write` reject → trả `"failed"`, **không** ném ra ngoài (đây là assertion chống
  unhandled rejection, và nó chạy được trong Node)

Phần UI của nút — nhãn đổi, timer 4 giây, `aria-live` — **không test tự động
được**, vào checklist trình duyệt ở mục Nghiệm thu.

---

### T11 — Breadcrumb hiện tên, không hiện UUID

`apps/web/src/lib/navigation.ts:198-206`

`breadcrumbs(pathname)` là hàm thuần đường dẫn — nó **không thể** biết
`task_profile_id` của run. Comment ở `:195` nói rõ id được hiện verbatim có chủ ý
(không chạy qua từ điển). Đúng, nhưng "không dịch" khác "không thay được".

**Sửa — bắt buộc là context, prop không khả thi**: trang con không thể truyền
prop ngược lên `AppShell` do root layout dựng. Cách làm:
- `CrumbOverrideContext` với setter; provider đặt trong `Providers`/`AppShell`.
- Trang detail: `useEffect` set `sudden_stop_v5` khi run tải xong, và **cleanup
  trả `null` khi unmount / đổi route** — thiếu cleanup thì breadcrumb cũ lưu
  sang trang khác.
- Khi override là `null` (chưa tải, hoặc trang không set): hiện id như bây giờ.

**Chốt: T11 BẮT BUỘC, nằm trong phạm vi Plan 2.** Bản trước ghi *"nếu An thấy quá
tay thì bỏ"* — đó là để ngỏ một quyết định phạm vi cho người implement tự quyết
lúc đang code, và người đó sẽ quyết theo cái rẻ hơn. Mục tiêu plan này là **khớp
mock đã duyệt**, mà mock hiện tên profile chứ không hiện UUID; bỏ T11 tức là sửa
mục tiêu, không phải sửa một task.

Kèm theo đó, phần implement không còn chỗ nào để ngỏ:
- `CrumbOverrideContext` (value + setter) khai trong `Providers`; `AppShell` đọc.
- Trang detail set trong `useEffect` phụ thuộc `[run?.task_profile_id]`,
  **cleanup trả `null`**.

  **Field nằm ở `run.task_profile_id`, không phải `run.report.task_profile_id`**
  (`decisions.ts:270`). `report` là payload của bản chấm điểm; `task_profile_id`
  là cột của chính bản ghi run. Đọc sai đường dẫn cho ra `undefined` — và vì
  override `undefined` rơi về nhánh "hiện id như bây giờ", breadcrumb sẽ **im
  lặng không bao giờ đổi**, không lỗi, không cảnh báo. Đúng loại bug T11 sinh ra
  để sửa.
- Test `navigation.test.ts`: `breadcrumbs()` thuần không đổi hành vi.
- Phần còn lại của T11 (override có giá trị → hiện tên; `null` → hiện id; unmount
  → trả `null`) **không test tự động được** — xem mục Nghiệm thu, nó vào checklist
  trình duyệt.

Nếu An muốn cắt T11 thì **quyết trước lúc duyệt plan**, và khi đó phải sửa kèm:
mục Nghiệm thu bỏ dòng breadcrumb, và ghi chú lên mock rằng breadcrumb tạm giữ
UUID — để lần đối chiếu ảnh sau không báo đây là sai lệch.

---

### T12 — Copy

**Không đổi khoá `decisions.filter.ranked`** — nó còn được dùng làm option
filter ở trang list (`decisions/page.tsx:174`); đổi nó là đổi copy ngoài phạm vi
trang detail. Tạo khoá **mới** cho badge header trang detail:

| Khoá | EN | VI |
|---|---|---|
| `decisions.detail.recommendationIssued` (mới) | `Recommendation issued` | `Đã có khuyến nghị` |
| `decisions.detail.unranked` (mới, nếu chưa có khoá phù hợp) | `Unranked` | `Chưa xếp hạng` |

Badge ở `page.tsx:102` đổi sang khoá mới. Trang list giữ nguyên copy — muốn đổi
"Produced a card" ở filter thì là một quyết định riêng, hỏi An sau.

Nội dung badge trophy (`page.tsx:168`) **đã được Plan 1 T7 sửa** — mọi bề mặt
khuyến nghị in `{stack_label} · {local_controller_config}`. Ở đây chỉ còn việc
kiểu: badge dài hơn, kiểm không tràn ở header panel khi VI.

---

### T13 — Dòng tóm tắt đầu panel

Thêm `.cmp-summary` giữa `panel-head` và lưới:
`{configA} leads on {x} of {n} metrics, {configB} on {y}. The remaining {z} are ties.`

Đếm thuần từ `leaders()` đã có — **không phải một đường phán xét thứ hai**.

**Điều kiện render và luật đếm — câu A/B chỉ đúng trong ca A/B**:
- Chỉ render khi `candidates.length === 2`. Ba candidate trở lên: không render
  (câu "A dẫn x, B dẫn y" không có chỗ cho C).
- Mẫu số `n` chỉ gồm row có `direction !== "none"` **và** cả hai
  `values` khác `null`.
- Row bị loại vì thiếu dữ liệu **không** được đếm là tie — nó không vào mẫu số.
- `leaders().length === 0` chỉ tính là tie khi cả hai value tồn tại (đã bảo đảm
  bởi điều kiện mẫu số trên).

Khoá i18n mới: `decisions.compare.summary`.

**Nghiệm thu**: run 2 candidate đủ dữ liệu → câu đếm khớp số ô được tô. Run có
một metric null một bên → mẫu số giảm 1, không phải tie tăng 1. Run 3 candidate
→ không có dòng tóm tắt.

---

## Thứ tự chạy

```
Plan 3 A2 (gồm --font-sans) + A4      ← điều kiện, zero-pixel
Plan 3 A3 (đổi màu candidate)         ← điều kiện, CÓ đổi hình; chụp riêng
                                         trước khi T2 xoá nền tô cột
T4 (candidateMetrics: numberText + unit + deltaText;
    trích ComparisonGrid ra components/; grid -> <table>)
  ├─ T5  giá trị canh phải + đơn vị   (cần numberText + unit)
  ├─ T8  bỏ em-dash                   (cần values)
  └─ T13 dòng tóm tắt                 (cần values)
T2 → T3      header cột rồi gate
T1, T6, T7, T9, T10, T12   độc lập, chạy song song được
T11          cuối — bắt buộc, không phải tuỳ chọn
```

Mọi logic của T1, T3, T4, T7, T10, T13 viết vào `lib/` dạng **hàm thuần trước**,
component gọi sau — không phải để cho đẹp kiến trúc mà vì đó là **cách duy nhất
test được ở repo này**. Xem mục Hạ tầng test.

## Nghiệm thu cả plan

### Hạ tầng test — đọc trước khi viết một test nào

Bản trước kê test dạng "click nút, khẳng định nhãn đổi, unmount rồi kiểm cleanup"
trong `decisions-page.test.tsx`. **Không chạy được ở repo này.** `vitest.config.ts`
nói thẳng:

> The environment stays Node. There is no jsdom and no testing-library installed,
> so component assertions go through `renderToStaticMarkup` — real rendered HTML,
> no browser. That covers first render […]; **it does not cover clicking.**

`decisions-page.test.tsx` hiện tại cũng không render gì — nó `readFileSync` chính
`page.tsx` rồi khẳng định trên mã nguồn. Và `docs/KNOWN_LIMITATIONS.md:211` đã lập
sẵn quy ước cho đúng tình huống này: **tách phần quyết định ra hàm thuần rồi test
hàm đó**, phần tương tác đưa vào kiểm tay.

Nên mọi logic mới của plan này phải **ra khỏi component**, vào `lib/` dạng hàm
thuần không `t()`, không React:

| Task | Hàm thuần | Trả về |
|---|---|---|
| T1 | `sampleLine(sample)` | `SampleLineState` — **cả ba** quyết định của dòng, xem dưới |
| T1 | `sampleNotice(sample)` | `"critical" \| "belowNMinInterrupted" \| "warn" \| null` — luật precedence, đúng một kết quả |
| T3 | `gateSummary(candidates)` | `{ key, tone: "ok" \| "err", cleared, total }` |
| T4 | `comparisonRows()` mở rộng | `numberText`, `unit`, `deltaText` (đã có sẵn file test) |
| T4 | `hasDeltaColumn(candidates)` | `boolean` — một nguồn quyết định có render `<th>`/`<td>` Δ hay không |
| T7 | `collisionBoundCell(g2)` | `{ kind: "bound", bound, observed, n } \| { kind: "notApplicable", observed, n }` |
| T10 | `copyDecisionId(id, write)` | `Promise<"copied" \| "failed">` |
| T13 | `comparisonSummary(rows)` | `{ a, b, ties, total } \| null` |

**`sampleLine()` phải trả cả ba quyết định, không riêng khoá N_min.** T1 quyết
ba chuyện, và hai chuyện còn lại đúng là hai chuyện dễ sai nhất: *"được nói `ran
the full request` không"* (điều kiện ba vế, run cũ thiếu `n_episodes_requested`
không được tự nhận) và *"có hiện coverage không"*. Để chúng lại trong component
là để đúng phần dễ sai nằm ngoài tầm test.

```ts
interface SampleLineState {
  nMinKey: "decisions.sample.line.meetsNMin" | "decisions.sample.line.belowNMin";
  params: { n: number; min: number };
  ranFullRequest: boolean;          // đã gồm cả ba vế điều kiện
  coveragePercent: number | null;   // null = không thêm mệnh đề coverage
}
```
Component chỉ còn `t(state.nMinKey, state.params)` và hai câu `if`. Bốn ca nghiệm
thu của T1 chạy thẳng trên helper, không dựng component.

`copyDecisionId` **nhận hàm ghi qua tham số**, không đọc `navigator` bên trong:
```ts
export async function copyDecisionId(
  id: string,
  write: (text: string) => Promise<void>,
): Promise<"copied" | "failed"> {
  try { await write(id); return "copied"; } catch { return "failed"; }
}
```
Nhờ vậy hai nhánh resolve/reject test được trong Node, không cần `navigator`,
không cần mock global. Component chỉ còn một dòng
`copyDecisionId(run.id, (t) => navigator.clipboard.writeText(t))` — và cái `catch`
nuốt rejection nằm trong hàm đã được test, nên không còn unhandled rejection.

**Khẳng định trên markup thật thì hợp lệ** — `renderToStaticMarkup` phủ **first
render**, và cấu trúc bảng là chuyện của first render chứ không phải của click.
Nhưng nó **đòi bảng phải import được**, nên T4 kèm việc trích `ComparisonGrid` ra
`components/ComparisonGrid.tsx`. File test mới:
`src/components/__tests__/comparison-grid.test.tsx`.

Cái cần khẳng định ở đó, sau khi đổi sang `<table>`: hàng `no route found` in
`not measured` chứ không in `—`; run 3 candidate không có `<th>` Δ nào; tiêu đề
cột chọn đúng trường theo `headingField` (T2). **Test "đếm ô chia hết cho 4" của
bản trước đã bỏ** — nó canh một lỗi chỉ tồn tại trong grid phẳng.

### Lệnh

Máy chạy **Windows PowerShell**; dấu `\` xuống dòng kiểu bash là lỗi cú pháp ở
đây. Một dòng:

```powershell
npm.cmd test -- src/lib/__tests__/candidate-metrics.test.ts src/lib/__tests__/navigation.test.ts src/components/__tests__/comparison-grid.test.tsx src/app/__tests__/decisions-page.test.tsx src/app/__tests__/decision-prose.test.tsx src/app/__tests__/tokens.test.ts
```

Toàn bộ, trước khi báo xong:
```powershell
npm.cmd test
npm.cmd run typecheck
```

### Chỉ kiểm được bằng mắt — checklist trình duyệt

Không có jsdom nghĩa là **những mục này không có test nào canh**, nên chúng phải
nằm thành danh sách chứ không nằm trong đầu người implement:

- [ ] **T10** bấm nút copy → nhãn đổi `Copied`, dán ra ngoài đúng id
- [ ] **T10** nhãn tự trả lại sau 4 giây; bấm liên tục 3 lần không kẹt nhãn
- [ ] **T10** chặn quyền clipboard (hoặc mở qua `http://` không phải secure
      context) → nhãn `Copy failed`, id vẫn đọc được, **console không có
      unhandled rejection**
- [ ] **T10** screen reader đọc được thay đổi trạng thái (vùng `aria-live`)
- [ ] **T11** breadcrumb hiện `sudden_stop_v5` sau khi run tải xong
- [ ] **T11** rời sang trang khác → breadcrumb **không** còn giữ tên run cũ
      (đây là ca cleanup; thiếu cleanup thì lỗi chỉ hiện khi điều hướng)
- [ ] **T3** `<details>` mở/đóng được bằng bàn phím

**Đối chiếu mắt** — 1920 / 1440 / 1024 / 900 / 620 / 390:
- [ ] Mỗi vòng chụp xong **chạy Visual Verdict trước khi sửa tiếp**, lưu verdict
      state; không chồng hai vòng chỉnh lên một lần chụp. (Repo này **không có**
      `AGENTS.md` — luật đến từ skill `visual-verdict`, ghi rõ ở đây để lần sau
      không phải đi tìm.)
- [ ] 900px: cột Δ biến mất, hai cột candidate vẫn cạnh nhau (không xếp chồng)
- [ ] 620px và 390px: cột candidate sàn 84px, đơn vị xuống dòng, config không wrap gãy

**Kiểm nội dung**:
- [ ] Không còn `—` trong lưới so sánh
- [ ] Không còn chữ xanh lá ở cột giá trị; badge `cleared` vẫn xanh lá
- [ ] Dấu thập phân thẳng cột trong cùng một cột; không đơn vị nào in hai lần
- [ ] Không dòng nào ghi `meets N_min` khi `n < n_min`
- [ ] `grep -n '!important' globals.css` giảm đúng 1
- [ ] `grep -n 'badge--\|btn--' apps/web/src/app/decisions` không ra kết quả
      (không dùng class chưa tồn tại)
- [ ] EN và VI đều không tràn dòng ở gutter 260px
- [ ] Tab qua toàn trang theo đúng thứ tự đọc; nút copy đọc được bằng screen reader

## Rủi ro

| Rủi ro | Mức | Xử lý |
|---|---|---|
| T4 đổi kiểu `MetricRow` — có test đang khẳng định `text: string[]` | **Cao** | Thêm `numberText`, giữ `text`. Không xoá field cũ trong cùng một lượt |
| ~~Hàng flags thiếu ô Δ ⇒ lệch toàn lưới~~ | **đã triệt** | Không còn rủi ro: `<table>` có hàng thật, một `<tr>` ngắn không kéo hàng nào khác. Đây là lý do chính An chọn lấy bảng của v3 |
| T2 chọn sai trường làm tiêu đề | **Cao** | `headingField()` suy từ dữ liệu; 4 ca test. Bản plan trước chốt cứng "config" và sai trên 10/16 run |
| Trích `ComparisonGrid` khỏi `page.tsx` làm hỏng chỗ khác | Thấp | Thuần props, cắt nguyên khối; `page.tsx` chỉ còn dòng gọi. `npm.cmd run typecheck` bắt được ngay nếu thiếu prop |
| Dùng class chưa tồn tại (`badge--ok`, `btn--ghost`, `--font-sans`) rồi chờ Plan 3 vá | **Cao** | Đã chốt từng cái: badge dùng `.badge.ok/.err`, nút dùng `.decision-copy-id` cục bộ, `--font-sans` đẩy lên Plan 3 A2 |
| T3 giấu gate vào `<details>` bị đọc là "giấu thông tin" | Trung bình | Badge tổng hợp ở header cột luôn hiện, `<details>` chỉ chứa chi tiết 6 ô, và badge nói rõ tỉ lệ |
| T11 chạm `AppShell` ⇒ ảnh hưởng mọi trang | Trung bình | Tách commit riêng. Cắt T11 là quyết định của An **trước** lúc duyệt, không phải của implementer lúc code |
| **Không có jsdom** ⇒ clipboard, timer, cleanup context không có test nào canh | **Cao** | Logic ra hàm thuần; phần còn lại thành checklist trình duyệt có tên, không để trong đầu ai. Rủi ro thật còn lại: checklist bị bỏ qua lúc vội |
| A3 được tưởng là zero-pixel ⇒ đổi màu lọt vào giữa các thay đổi khác, không ai chụp riêng | Trung bình | Đã đính chính ở bảng Phụ thuộc và ở Plan 3; A3 chạy trước T2 và chụp riêng |
| Mock chưa phủ các panel dưới ⇒ trang nửa mới nửa cũ | **Cao** | Chấp nhận cho demo. Plan 3 giai đoạn B kéo phần còn lại về cùng hệ |

## Quyết định về mock — đã chốt 2026-08-21

**An chọn: giữ v2, lấy `<table>` của v3.** Bảng dưới ghi lại cả ba lựa chọn đã
cân, để lần sau không phải cân lại.

| Task | v2 | v3 — EvalFrame | **Đã chốt** |
|---|---|---|---|
| **T4** lưới | CSS grid + luật placeholder Δ + test đếm ô | `<table>` | **v3** — xem T4 |
| **T6** ô dẫn đầu | nền `--accent-soft` | đơn sắc + cột "Leads" | **v2** |
| **T3** badge gate | `.badge.ok` / `.badge.err` | `.state.pass` / `.state.fail` | **v2** |
| **T13** dòng tóm tắt | dòng dưới `panel-head` | pill cạnh tiêu đề | **v2** |

Lý do lựa chọn này đứng vững: nó lấy đúng **phần cấu trúc** của v3 — thứ triệt
được một lớp lỗi — mà không kéo theo phần **thẩm mỹ**, vốn sẽ đảo một quyết định
An đã chốt và chốt sớm vài giá trị của Plan 3 giai đoạn B.

Ghi chú gốc, giữ lại:

| Task | v2 — plan hiện tại | v3 — EvalFrame |
|---|---|---|
| **T4** lưới | CSS grid `--cols` / `--delta-col`, cộng **luật placeholder Δ** và test đếm ô | `<table>`. Một `<tr>` là hàng thật nên hàng flags **không thể** làm lệch lưới — luật placeholder và test đếm ô **không còn cần** |
| **T6** ô dẫn đầu | nền `--accent-soft` | đơn sắc: nền xám `--surface-2`, cộng một **cột "Leads"** ghi chữ `A` / `B` |
| **T3** badge gate | `.badge.ok` / `.badge.err` | `.state.pass` / `.state.fail` — chấm + chữ hoa, không phải chip tô |
| **T13** dòng tóm tắt | một dòng dưới `panel-head` | một `pill` bên phải tiêu đề mục |

Ba điều đáng cân nhắc, không phải chuyện thẩm mỹ:

1. **v3 đảo một quyết định An đã chốt.** T6 hiện ghi *"Luật tô giữ nguyên như hiện
   tại (An đã chốt): tô mọi chênh lệch theo hướng metric"*. v3 bỏ hẳn việc tô theo
   hướng — EvalFrame ghi rõ lý do: *"Neutral directional treatment keeps the UI
   monochrome while preserving decision clarity."*
2. **v3 giải quyết bug lệch lưới bằng cấu trúc**, không bằng luật. Đây là điểm
   mạnh thật của nó, không phải chuyện nhìn.
3. **v3 mang vài giá trị Plan 3 chưa chốt** — card bo `12px` trong khi A2 đã khai
   thang `{4, 6, 8}`; badge đổi convention sang `.state`. Dựng v3 bây giờ là chốt
   sớm mấy thứ đó thay cho Plan 3 giai đoạn B.

## Không commit

Làm xong dừng lại, báo cáo. An tự commit.
