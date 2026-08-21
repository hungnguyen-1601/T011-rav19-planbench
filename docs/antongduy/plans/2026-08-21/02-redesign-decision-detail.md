# Plan 2 — Redesign trang Decision Detail

Ngày lập: 2026-08-21 · Trạng thái: **chờ An duyệt**
Mock đã duyệt luật tô: [tongduyan_mock-decision-detail.html](../../notes/2026-08-21/tongduyan_mock-decision-detail.html)
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
| **Plan 3 giai đoạn A2–A4** (thang token, candidate color, notice variant — **không gồm A1 nạp font**) | Cần `--space-*`, `--radius-*`, `--fs-*`, `--candidate-a/b`, `.notice--*` tồn tại. A2–A4 thuần khai báo, zero pixel. A1 (webfont) đổi mặt chữ toàn app nên KHÔNG được là điều kiện của plan này — Plan 3 đã chuyển A1 xuống giai đoạn B |

Nếu An muốn Plan 2 chạy trước Plan 3 A2–A4: được, nhưng phải hard-code giá trị
rồi quay lại thay bằng token — thêm một lượt sửa. Không khuyến nghị.

---

## Task

### T1 — `SampleBanner` → một dòng, card chỉ khi bất thường

`apps/web/src/app/decisions/[id]/page.tsx:1140-1178`

Hiện render ba `Figure` vô điều kiện. Với run bình thường ra ba số `30` giống hệt
nhau ở 26px.

**Sửa**: bỏ `.stat-grid`. Render một dòng `.sample-line` trong `page-head`:
`<b>{n_episodes}</b> episodes measured · meets N_min (<b>{n_min}</b>)`.

Mệnh đề `· ran the full request` **chỉ** khi đủ cả ba điều kiện — run cũ thiếu
`n_episodes_requested` không được tự nhận chạy đủ:
```ts
sample.n_episodes_requested !== undefined
  && sample.n_episodes >= sample.n_episodes_requested
  && !sample.interrupted
```

**Precedence notice — tối đa MỘT notice**, không xếp chồng:
1. `n_episodes < n_min_required` → `.notice--critical`. Nếu đồng thời
   `interrupted` thì nội dung critical **kèm luôn** ý bị ngắt
   (khoá i18n riêng cho ca gộp) — không render notice thứ hai.
2. ngược lại, `interrupted` → `.notice--warn`.
3. `coverage(run) < 1` → không phải notice, thêm mệnh đề `· coverage {x}%`
   vào dòng sample.

Khoá i18n mới: `decisions.sample.line.full`, `decisions.sample.line.meetsNMin`,
`decisions.sample.belowNMinInterrupted` (ca gộp).

**Nghiệm thu**: run 30/30/30 → một dòng, không card, không notice. Run
`n=18, n_min=30, interrupted` → đúng **một** `.notice--critical` nói cả hai ý.
Run cũ không có `n_episodes_requested` → dòng sample không có mệnh đề "ran the
full request".

---

### T2 — Header cột: config làm tiêu đề, bỏ ô icon

`page.tsx:203-215` · CSS `globals.css:3413-3425`

Hiện `<h4>{candidate.stack_label}</h4>` 15px và `<code>{local_controller_config}</code>`
10px muted. Cả hai cột đều `astar+dwa`, nên tiêu đề không phân biệt được gì.

**Sửa**:
- `<span class="letter">Candidate A</span>` — `--fs-caption`, muted
- `<span class="config">{local_controller_config}</span>` — `--fs-label`, 600, màu `--candidate-a/b`
- `<span class="stack">{stack_label} · {local_observation_class}</span>` — `--fs-sm`, muted
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
- Thêm vào `.marks` của header cột: `<span class="badge badge--ok">G1–G6 cleared</span>`
  hoặc `<span class="badge badge--err">blocked at {blocking_gates.join(", ")}</span>`.
  Dùng lại `candidate.cleared_gates` / `candidate.blocking_gates` đang có.
- Lưới 6 ô chuyển vào `<details class="gates">` đặt **cuối panel**, sau lưới metric.
  Summary: `Feasibility gate detail` + badge tổng hợp.
- Bỏ hàng `.comparison-grid-foot` khỏi lưới chính.

**Nghiệm thu**: đọc header cột là biết ứng viên có hợp lệ không, chưa cần cuộn.

---

### T4 — Lưới: `--cols`, bỏ inline style, bỏ `!important`, thêm cột Δ

`page.tsx:200` · CSS `globals.css:3402`, `3462`

Hiện JSX set `style={{ gridTemplateColumns: ... }}` inline, buộc media query
900px phải dùng `!important` để thắng.

**Sửa**:
```tsx
<div className="comparison-grid" style={{ "--cols": candidates.length } as CSSProperties}>
```
```css
.comparison-grid {
  display: grid;
  grid-template-columns:
    minmax(260px, 420px)
    repeat(var(--cols, 2), minmax(150px, 260px))
    var(--delta-col, 0px);
  justify-content: start;
}
```
Media query 900px ghi đè bình thường, **xoá `!important`**.

`--cols` và `--delta-col` là token do JSX cung cấp — **phải có mặt trong mảng
`JSX_PROVIDED` của `tokens.test.ts`** (Plan 1 T6 đã khai sẵn cả hai). Nếu đặt
tên khác lúc implement thì sửa mảng đó cùng lượt, không tắt test.

**`--delta-col` phải được set từ JSX** — CSS chỉ có fallback `0px`, quên set là
cột Δ tồn tại trong DOM nhưng rộng 0:
```tsx
style={{
  "--cols": candidates.length,
  "--delta-col": candidates.length === 2 ? "minmax(96px, 140px)" : "0px",
} as CSSProperties}
```
Header và cell Δ **chỉ render khi đúng hai candidate** — không render rồi giấu
bằng width.

**Cột Δ** — chỉ khi `candidates.length === 2`:
- Giá trị `Δ (B−A)`, `--font-mono`, `--fs-body`, muted, canh phải
- Dùng dấu trừ U+2212 (`−`), không dùng hyphen
- Tính từ `MetricRow.values` — **trường này ĐÃ tồn tại**
  (`candidateMetrics.ts:36`, `values: (number | null)[]`). Không thêm trường
  `raw` — sẽ thành hai nguồn dữ liệu trùng nhau. Không parse lại `text`.
- Một trong hai `values` là `null` → ô Δ trống, không phải `0`
- Metric `direction: "none"` (chỉ `replans` — lưu ý `distinctEpisodes` khai
  `"higher"` ở `candidateMetrics.ts:162`, không phải "không hướng") vẫn hiện Δ,
  chỉ là muted
- Ẩn dưới 900px (`display: none`) — nó là cột duy nhất tái tạo được từ hai cột kia

**Δ phải format theo từng metric, không in `values` thô** — đây là phần việc
thật của T4 thay cho trường `raw` đã bỏ:
- Rate lưu `0.7` nhưng hiển thị `70.0 %` ⇒ Δ `0.02` phải in `+2.0 pp`
  (percentage point), không phải `+0.02`
- Latency 2 chữ số thập phân · clearance 3 chữ số · count nguyên

Cách làm: mở rộng `MetricRow` trong `candidateMetrics.ts` (module thuần, không
i18n):
```ts
interface MetricRow {
  values: (number | null)[];
  text: string[];
  unit?: string;        // T5 dùng: "ms", "m", "s", "%", "MB"
  deltaText?: string;   // Δ đã format đúng thang hiển thị, U+2212, dấu +/−
}
```
`deltaText` tính trong cùng helper đã biết cách format từng metric (`asRate`,
`asCount`, …) — mỗi kiểu format sẵn có thêm một nhánh delta.

**Nghiệm thu**: ở 1920 cột giá trị không vượt 260px. Ở 899px cột Δ biến mất, hai
cột candidate còn đọc được. Run 3 candidate → không có header/cell Δ nào trong
DOM. Δ của success rate in `pp`, không in số thô. `grep -n '!important'
globals.css` giảm đúng 1 dòng.

**Responsive <900px — THAY rule cũ, không chỉ xoá `!important`**: rule hiện tại
(`globals.css:3462`) ép toàn lưới về **một cột** (xếp chồng candidate). Mock đã
duyệt giữ gutter + các cột candidate cạnh nhau và chỉ bỏ Δ. Rule mới thay thế:
```css
@media (max-width: 900px) {
  .comparison-grid {
    grid-template-columns: minmax(0, 1fr) repeat(var(--cols, 2), minmax(110px, 1fr));
  }
  .comparison-delta { display: none; }
}
```
Chỉ xoá `!important` mà giữ rule một-cột thì layout dưới 900px vẫn khác mock.

---

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
Metric **không có** đơn vị (`collisions`, `distinctEpisodes`, `replans`) vẫn
render slot `.unit` **rỗng** — bỏ slot là số của hàng đó nhảy sang phải, phá
thẳng cột dọc.

Cần `MetricRow.unit` từ T4 để tách.

**Nghiệm thu**: đặt `0.470 m` trên `22.5 s` trên `17.89 ms` trên `0` (không đơn
vị) — dấu thập phân và hàng đơn vị của **các hàng khác nhau** đều thẳng cột.

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
- **Mỗi cell candidate** hai dòng:
  `≤ 10.0 %`
  `0 / 30 episodes` — đếm của **chính** candidate đó (candidate dừng sớm hiện
  `0 / 18`, không mượn 30 của bên kia)
- Giữ nguyên tooltip — nó nói thêm chứ không nói thay

Khoá i18n mới: `decisions.compare.sub.collisionBound` (gutter),
`decisions.compare.cell.collisionBound` (cell, nhận 2 tham số).

**Nghiệm thu**: đọc hàng đó không hover vẫn hiểu 10% không phải xác suất đo
được. Dựng run có candidate `stopped_early` → cell của nó hiện đúng mẫu số riêng.

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
- Dòng meta thêm `<button class="btn btn--ghost">` copy `run.id`, hiện id dạng
  `<code>` 12px trong nút

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

**Đây là thay đổi kiến trúc nhỏ chạm `AppShell`** — nếu An thấy quá tay so với
lợi ích thì bỏ T11, không ảnh hưởng task nào khác.

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
T4 (candidateMetrics: raw + unit)   ← làm trước, T5/T8/T13 đều cần
  ├─ T5  giá trị canh phải + đơn vị
  ├─ T8  bỏ em-dash
  └─ T13 dòng tóm tắt
T2 → T3      header cột rồi gate
T1, T6, T7, T9, T10, T12   độc lập, chạy song song được
T11          cuối, hoặc bỏ
```

## Nghiệm thu cả plan

- [ ] Đối chiếu từng vùng với mock đã duyệt ở 1920 / 1440 / 1024 / 900 / 620 / 390
- [ ] `npx vitest run` phần `decisions` và `candidateMetrics` — xanh
- [ ] `npm run typecheck`
- [ ] Không còn `—` trong lưới so sánh
- [ ] Không còn chữ xanh lá ở cột giá trị; badge `cleared` vẫn xanh lá
- [ ] Dấu thập phân thẳng cột trong cùng một cột
- [ ] `grep -n '!important' globals.css` giảm đúng 1
- [ ] EN và VI đều không tràn dòng ở gutter 260px
- [ ] Tab qua toàn trang theo đúng thứ tự đọc

## Rủi ro

| Rủi ro | Mức | Xử lý |
|---|---|---|
| T4 đổi kiểu `MetricRow` — có test đang khẳng định `text: string[]` | **Cao** | Thêm trường mới, giữ `text`. Không xoá field cũ trong cùng một lượt |
| T3 giấu gate vào `<details>` bị đọc là "giấu thông tin" | Trung bình | Badge tổng hợp ở header cột luôn hiện, `<details>` chỉ chứa chi tiết 6 ô |
| T11 chạm `AppShell` ⇒ ảnh hưởng mọi trang | Trung bình | Tách commit riêng, hoặc bỏ hẳn T11 |
| Mock chưa phủ các panel dưới ⇒ trang nửa mới nửa cũ | **Cao** | Chấp nhận cho demo. Plan 3 giai đoạn B kéo phần còn lại về cùng hệ |

## Không commit

Làm xong dừng lại, báo cáo. An tự commit.
