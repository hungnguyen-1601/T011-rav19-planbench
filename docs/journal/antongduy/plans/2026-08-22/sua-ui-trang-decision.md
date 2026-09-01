# Plan: sửa UI trang `/decisions/[id]` theo brief Results / Algorithm Comparison

Ngày: 2026-08-22 · Nhánh `tongduyan_4` · **Trạng thái: ĐÃ DUYỆT** (An
duyệt 2026-08-22, chạy toàn bộ 6 lượt, commit sau mỗi lượt, full suite
chỉ chạy khi xong hết).

Nguồn: [tongduyan_ra-soat-ui-trang-decision.md](../../notes/2026-08-22/tongduyan_ra-soat-ui-trang-decision.md).
Ghi chú đó nêu vấn đề; file này chia thành việc chạy được, kèm file cụ
thể, key i18n, test và điều kiện nghiệm thu từng việc.

**Phạm vi:** chỉ web (`apps/web`). Không sửa backend, không sửa
`packages/decision`, không đổi schema. Mọi dữ liệu cần dùng đều đã có
sẵn trên `DecisionRun` phía client — đã kiểm tra ở §"Vật liệu có sẵn".

---

## Vật liệu có sẵn (đã đọc code, không phải giả định)

| Cần gì | Đã có ở đâu |
|---|---|
| Candidate qua hết cổng chưa | `candidate.cleared_gates: boolean` — dùng ở [gateSummary.ts:55](../../../../../apps/web/src/lib/gateSummary.ts#L55) |
| Bên nào dẫn mỗi metric | `leaders(row)` / `comparisonSummary()` ở [comparisonSummary.ts](../../../../../apps/web/src/lib/comparisonSummary.ts) |
| Hướng metric | `MetricRow.direction: Direction` ở [candidateMetrics.ts:39](../../../../../apps/web/src/lib/candidateMetrics.ts#L39) |
| Điểm, ΔU, CI95, n | `run.card.evidence` — đang render ở `CardPanel` |
| Phân loại verdict | `verdictOf()`, `runBadge()` ở [conclusion.ts:108](../../../../../apps/web/src/lib/conclusion.ts#L108) |
| Lý do không có card | `noCardReason()` ở [decisions.ts:856](../../../../../apps/web/src/lib/decisions.ts#L856) |
| Nhãn winner cho screen reader | đã có `sr-only` ở [ComparisonGrid.tsx:310](../../../../../apps/web/src/components/ComparisonGrid.tsx#L310) |

Điểm cuối quan trọng: **winner đã có nhãn chữ cho screen reader, chỉ
thiếu nhãn nhìn thấy được.** Việc T5 vì vậy là thêm cột hiển thị dùng
lại `standings()` sẵn có, không phải viết logic mới.

File sẽ đụng nhiều nhất:

- [page.tsx](../../../../../apps/web/src/app/decisions/%5Bid%5D/page.tsx) — 1539 dòng
- [ComparisonGrid.tsx](../../../../../apps/web/src/components/ComparisonGrid.tsx) — 383 dòng
- [globals.css](../../../../../apps/web/src/app/globals.css) — 4237 dòng, khối `.comparison-*` từ dòng 2531, `.conclusion-*` từ 4217
- `lib/i18n/locales/en.json` + `vi.json` — **luôn sửa cặp**

---

## T1 — Sửa mệnh đề sai của `Outcome` *(P0, độc lập, làm trước)*

**Vấn đề.** [decisions.ts:856](../../../../../apps/web/src/lib/decisions.ts#L856)
chỉ có ba nhánh, nhánh cuối là bao trọn:

```ts
if (run.ranked) return null;
if (run.report?.sample?.interrupted) return "interrupted";
if (run.report?.gate_only_deployment) return "gate_only";
return "no_survivors";
```

Run `sudden_stop_v5` có `astar+dwa` với `cleared_gates === true`, nhưng
rơi vào `no_survivors`, và chuỗi vi.json:809 in ra "Không candidate nào
qua đủ cổng" — **sai sự thật, ngay cạnh bảng ghi `G1–G6 đều đạt`.**

**Làm gì.**

1. `lib/decisions.ts`: thêm `"single_survivor"` vào `NoCardReason`; chèn
   nhánh trước `no_survivors`:
   ```ts
   const cleared = (run.report?.candidates ?? []).filter((c) => c.cleared_gates).length;
   if (cleared === 1) return "single_survivor";
   ```
2. `en.json` + `vi.json`, hai key mới:
   - `decisions.reason.single_survivor` — vi: "Chỉ một candidate qua đủ cổng"
   - `decisions.noCard.whatNext.single_survivor` — vi: "Việc cần làm:
     đăng ký thêm một candidate qua được cổng. Bên duy nhất còn lại
     không được gọi là bên thắng vì không có đối chứng nào để so."
3. `Outcome` không cần sửa — nó đã render theo `reason`.

**Test.** `lib/__tests__/decisions*.test.ts`: bốn case cho
`noCardReason` — interrupted, gate_only, cleared===1, cleared===0. Thêm
case cleared===2 nhưng `ranked===false` vẫn ra `no_survivors` (không có
card mà hai bên qua cổng là chuyện khác, không gộp vào đây).

**Nghiệm thu.** Mở `sudden_stop_v5`, panel đáy đọc "Chỉ một candidate
qua đủ cổng", không còn mâu thuẫn với cột bảng.

**Commit.** `TongDuyAn - Tell a run where exactly one candidate cleared every gate apart from one where none did, since the copy for the latter states the opposite of what the table beside it shows.`

---

## T2 — `DecisionSummary`: câu trả lời lên đỉnh *(P0, việc lớn nhất)*

**Vấn đề.** Điểm 87.7 / 31.3 và card việc-cần-làm nằm ở màn hình thứ 6.
Mục tiêu 5 giây fail.

**Làm gì.** Component mới `components/DecisionSummary.tsx`, chèn ngay
sau `<SampleNotice />` ở [page.tsx:148](../../../../../apps/web/src/app/decisions/%5Bid%5D/page.tsx#L148).

Bố cục 2 cột (760 / 368, gap 16):

*Cột trái — so sánh điểm.* Hai dòng, mỗi dòng: tên stack · điểm
`/100` · bar. Dùng lại `outOf100()` và `standings()` của
[conclusion.ts](../../../../../apps/web/src/lib/conclusion.ts) — **không
tính lại điểm**. Candidate bị chặn vẽ bar gạch chéo + chip `trượt G3`.

*Cột phải — recommendation card.* Nội dung theo `verdictOf(run)`:

| verdict | Tiêu đề | Dòng phụ |
|---|---|---|
| `recommended` | tên stack được khuyến nghị | `ΔU +x.xxx · CI95 [a, b] · n=30` |
| `near-equivalent` | "Hoà trong sai số" | số episode cần thêm nếu tính được |
| `no-card` | `t(decisions.reason.${reason})` | `t(decisions.noCard.whatNext.${reason})` |

**Hấp thụ, không nhân bản.** Sau khi có `DecisionSummary`:

- Xoá `<Outcome />` khỏi cây render (T1 vẫn cần vì `DecisionSummary`
  dùng chính `noCardReason`). Giữ `CardPanel` — nó là bảng sensitivity,
  đưa xuống dưới `EvidencePanel` với tiêu đề riêng.
- `ConclusionPanel` bỏ dòng headline lặp lại lý do; chỉ giữ phần
  breakdown objective.
- `ExplanationHeader` giữ nguyên, vẫn dính trên `EvidencePanel`.

Kết quả: lý do "không có khuyến nghị" nói **hai** lần (summary +
explainability) thay vì bốn.

**CSS.** Khối mới `.decision-summary*` đặt cạnh `.conclusion-*` trong
globals.css. Dùng lại token `--panel`, `--border`, `--accent` sẵn có,
không thêm biến màu mới.

**Test.** `app/__tests__/` — render run có card, run near-equivalent,
run no-card; assert mỗi trạng thái in đúng tiêu đề và ΔU/CI khi có.
Thêm một test đếm: chuỗi `decisions.noCard.whatNext.*` xuất hiện đúng
một lần trong DOM (chống tái phát nhân bản).

**Nghiệm thu.** Ở 1440×900, không cuộn, thấy được: hai điểm, bên dẫn,
ΔU (hoặc lý do vắng), khuyến nghị.

**Commit.** `TongDuyAn - Open the decision page on what the run concluded instead of on the evidence for it, and let the four places that each restated the missing recommendation collapse into the summary that now carries it.`

---

## T3 — `DecisionAdvice`: khuyến nghị theo use case *(P0)*

**Vấn đề.** Brief yêu cầu trả lời theo use case và nêu hybrid. Trang
hiện chỉ trả lời có/không.

**Làm gì.** `lib/decisionAdvice.ts` thuần, không JSX, dễ test:

```
qualified = candidates.filter(c => c.cleared_gates)

qualified.length === 0 → { kind: "none" }
qualified.length === 1 → { kind: "sole", candidateId }
qualified.length >= 2  →
   verdictOf() === near-equivalent → { kind: "tie" }
   một bên dẫn mọi objective       → { kind: "single", candidateId }
   dẫn chéo objective              → { kind: "hybrid", quality, realtime, split }
```

"Dẫn chéo" đọc từ `u_R/u_S/u_E/u_C` trên từng candidate: bên nào cao
hơn ở `U_R`+`U_S` là nhánh chất lượng, bên nào cao hơn ở `U_E`+`U_C`
là nhánh real-time. Cùng một bên thắng cả hai nhóm → `single`.

Render `components/DecisionAdvice.tsx`, ba thẻ ngang (371px ở 1440,
xếp dọc ở 1280):

| Thẻ | `sole` (run hiện tại) |
|---|---|
| Chất lượng / offline | `astar+dwa` — lựa chọn khả thi duy nhất, không phải bên thắng một cuộc so |
| Real-time / edge | Không có ứng viên. `rrtstar+dwa` trượt G3, không đề xuất kể cả khi latency tốt hơn |
| Cần cả hai | Không áp dụng — hybrid cần tối thiểu hai bên qua cổng |

Nhánh `hybrid` phải in **routing rule kiểm chứng được**, không phải chữ
"hybrid" trơ: "case có clearance dự báo dưới ngưỡng cảnh báo sang A,
case còn lại sang B", kèm một dòng chi phí vận hành hai stack.

**Test.** `lib/__tests__/decision-advice.test.ts`: năm nhánh, mỗi nhánh
một case. Riêng `hybrid` thêm case bên A thắng cả bốn objective để
khẳng định nó ra `single` chứ không ra `hybrid`.

**Nghiệm thu.** Mọi run — kể cả run bị chặn — đều in ba thẻ, không thẻ
nào để trống.

**Commit.** `TongDuyAn - Answer the question a reader actually arrives with, which is what to deploy for their own use case, rather than only whether this run happened to name a winner.`

---

## T4 — Hạ `TracePanel` xuống, collapse mặc định *(P0, rẻ)*

`TracePanel` là phần cao nhất trang mà đang ở slot 2. Chuyển xuống sau
`EvidencePanel`, bọc trong `<details>` đóng sẵn, summary ghi
`Xem lại một episode · 30 episode`.

Giữ nguyên hai ràng buộc đã có lý do trong comment ở page.tsx:
`SampleNotice` vẫn đứng đầu, `ExplanationHeader` vẫn dính ngay trên
`EvidencePanel`.

Thứ tự render sau T2+T3+T4:

```
SampleNotice · DecisionSummary · DecisionAdvice · CandidateComparison
· VisualComparison · TradeoffInsights · ExplanationHeader · EvidencePanel
· CardPanel · TracePanel (details) · HumanActs
```

**Nghiệm thu.** Chiều cao trang khi chưa mở gì giảm còn ≤ 3 màn ở 1440.

---

## T5 — Cột Winner + hướng metric trong bảng *(P0/P1)*

**Vấn đề.** Winner hiện chỉ mã hoá bằng màu con số. Có `sr-only` cho
screen reader nhưng người đọc mù màu vẫn mất tín hiệu. Và `+9.35 ms`,
`+0.1 MB`, `+17.5 s` đều là **xấu** mà không dấu hiệu nào nói vậy.

**Làm gì** — [ComparisonGrid.tsx](../../../../../apps/web/src/components/ComparisonGrid.tsx):

1. Thêm `<th scope="col">Thắng</th>` sau cột Δ. Ô in `A` / `B` / `hoà`
   / `—`, đọc thẳng từ `mark = standings(metric)` đã có ở `MetricLine`.
   Hàng `direction === "none"` in `—`, hàng có `null` in `—`.
2. Cột Metric: metric ngược chiều thêm mũi tên hướng nhỏ + tooltip
   "thấp hơn là tốt hơn". Đọc từ `MetricRow.direction`.
3. Caption dưới bảng: một dòng nói **vì sao không có cột weight** —
   weight gắn objective chứ không gắn metric, xem panel điểm số. Quyết
   định này đúng, chỉ đang im lặng.
4. `<thead>` sticky (`position: sticky; top: 0`) trong `.comparison-scroll`.
5. Căn phải theo dấu thập phân: `.comparison-value .num` dùng
   `font-variant-numeric: tabular-nums; text-align: right`, `.unit`
   width cố định.

**Test.** `components/__tests__/comparison-grid*.test.tsx`: hàng có
winner in đúng chữ; hàng `direction: "none"` in `—`; tổng số hàng in
`A` khớp con số trong câu tóm tắt phía trên bảng (chống lệch giữa hai
nguồn).

**Commit.** `TongDuyAn - Name the leader of each row in words beside the colour that already showed it, and mark the rows where a larger number is the worse one, since a plus sign reads as an improvement everywhere else on the page.`

---

## T6 — Bỏ xung đột màu identity với màu semantic *(P0, rẻ)*

**Vấn đề.** Cột A viền xanh dương, cột B viền **xanh lá**. B là bên
thua. Xanh lá đang vừa nghĩa "candidate B" vừa nghĩa "tốt".

**Làm gì** — globals.css, các rule `.candidate-a` / `.candidate-b`:

- Bỏ tint nền hai cột, hoặc đặt cả hai về `--panel-2`.
- Viền trên: A xanh dương, B **tím** (`--accent-2`, thêm nếu chưa có).
  Xanh lá và đỏ rút hoàn toàn khỏi identity candidate.
- Rà cả `.comparison-gate-owner.candidate-b` và các badge dùng cùng
  lớp.

**Nghiệm thu.** Grep `candidate-b` trong globals.css: không rule nào
tham chiếu token xanh lá.

---

## T7 — Localize khối contrast *(P1)*

**Vấn đề.** UI ở `vi` nhưng "Phép tương phản ủng hộ điều gì" in nguyên
câu tiếng Anh, bốn dòng. Nhãn cùng khối thì đã dịch — nghĩa là chuỗi
giải thích chưa vào bảng i18n.

**Làm gì.** Xác định chuỗi đến từ `run.report` (platform gửi) hay từ
`lib/evidence.ts` (client dựng). Cách xử lý đã có tiền lệ ngay trong
repo: `HostWarning` nhận **mã + số** từ platform rồi tự chọn chữ, và
fallback về câu nguyên văn khi gặp mã lạ
([page.tsx:284](../../../../../apps/web/src/app/decisions/%5Bid%5D/page.tsx#L284)).
Áp đúng khuôn đó.

- Nếu chuỗi do client dựng: đưa thẳng vào `en.json`/`vi.json`.
- Nếu do platform gửi: thêm bảng mã ở client, giữ fallback nguyên văn.
  **Không dịch máy chuỗi platform tại chỗ hiển thị.**

**Test.** Test quét: render trang ở locale `vi`, assert không node text
nào khớp `/\b(the|and|every|which)\b/` trong khối evidence.

---

## T8 — Đơn vị clearance nhất quán *(P1)*

Bảng ghi `0.470 m`, ô replay ghi `3.81 r`. Không phải bug: chuỗi gốc là
`"Worst clearance so far (robot radii)"`
([en.json:1492](../../../../../apps/web/src/lib/i18n/locales/en.json#L1492)),
cố ý dùng bán kính robot. Nhưng cùng khái niệm, cùng trang, hai đơn vị,
không chỗ nào nói vì sao.

**Chốt:** in cả hai ở ô replay — `0.470 m · 3.81 r` — và tooltip nói
bán kính robot là gì. Không đổi đơn vị của bảng.

---

## T9 — Nén row cảnh báo latency *(P1)*

Row "Độ trẻ planner, p99 gộp" cao ~110px vì `HostWarning` in bốn dòng
thẳng vào cell. Rút còn một dòng + `?` mở tooltip đầy đủ. Nội dung
không mất, chỉ đổi chỗ. Ràng buộc từ comment gốc vẫn giữ: cảnh báo nằm
**trong** row p99, không thành banner phủ cả bảng.

**Nghiệm thu.** Không row nào cao quá 60px.

---

## T10 — Detector table hiện tên candidate *(P1, rẻ)*

Cột Candidate in hash thô `29cdf6266a44`. Đổi sang tên
(`astar+dwa`) + hash mono nhỏ phía sau. Dùng lại
`recommendedCandidateLabel` / `candidateNames` sẵn có, tra theo
`candidate_id`.

---

## T11 — `TradeoffInsights` *(P2)*

`lib/tradeoffs.ts`: sinh 3–5 câu từ `MetricRow[]` + `leaders()`.

Quy tắc sinh:
- Bên A dẫn metric nhóm chất lượng, bên B dẫn nhóm tốc độ → một câu
  trade-off nêu đích danh cả hai metric và con số.
- Một bên dẫn sạch → một câu nói đúng điều đó, kèm số hàng.
- Hàng `không đo` nhiều → một câu nói phần nào chưa biết.
- Hàng có `threshold` mà cả hai đều sát ngưỡng → một câu cảnh báo.

Run hiện tại sẽ ra: "không có trade-off — `astar+dwa` dẫn ở cả 5 metric
có hướng, `rrtstar+dwa` không dẫn ở metric nào". Vẫn phải in.

**Test.** Bốn quy tắc, mỗi quy tắc một case; thêm case rỗng → không
render section chứ không render section trống.

---

## T12 — `VisualComparison` bars đã chuẩn hoá *(P2)*

Bar ngang 0–1 cho các metric có hướng, hai màu identity (sau T6: xanh
dương / tím). **Bắt buộc kèm chú thích cách chuẩn hoá.**

Chọn: min–max theo ngưỡng deployment khi metric có `threshold`, theo
max của cặp khi không có — và nói rõ cách nào trong chú thích của từng
nhóm. Metric không chuẩn hoá được thì **không vẽ**, đúng brief.

---

## T13 — Panel điểm số dễ đọc *(P2)*

- `u_R` / `u_S` / `u_E` / `u_C` in nhãn chữ: Thành công · An toàn ·
  Hiệu quả · Tính toán. Ký hiệu giữ lại làm `<code>` nhỏ phía sau.
- Bar candidate bị chặn: gạch chéo (`repeating-linear-gradient`), không
  chỉ đổi sang `--muted`. Xám đọc thành "điểm thấp", không đọc thành
  "không đủ tư cách".
- Thêm breakdown `weight × score = contribution`, cùng bộ số workbook
  Excel đang xuất.

---

## T14 — `ExportReport` lên header *(P2, rẻ)*

Hiện trôi giữa hai panel ở đáy, không tiêu đề section. Đưa lên
`.decision-detail-head` cạnh badge trạng thái. Giữ nguyên hành vi
Markdown / Excel / Share — chỉ đổi chỗ, không đổi logic.

---

## T15 — Hai chart latency chung scale *(P2)*

Hai chart cạnh nhau dài bằng nhau nhưng x-max 22.0s và 38.8s → đọc
thành "hai episode dài như nhau". Ép chung `xMax = max(cả hai)`, phần
dư của trục ngắn hơn vẽ nền trống. Sửa luôn hai nhãn trục y `54`/`50`
đè nhau. Bỏ ô "Đã đi được 0.0 %" khi `t === 0`.

Sửa ở [lib/latencyChart.ts](../../../../../apps/web/src/lib/latencyChart.ts) + component gọi nó.

---

## Thứ tự chạy và gom commit

| Lượt | Việc | Vì sao gom vậy |
|---|---|---|
| 1 | T1 | Độc lập hoàn toàn, sửa sai sự thật, merge được ngay |
| 2 | T6 → T5 | T6 dọn màu trước để T5 thêm cột Winner không kế thừa xung đột |
| 3 | T2 → T3 → T4 | Ba việc cùng đụng cây render page.tsx; tách ra là ba lần sửa cùng một khối |
| 4 | T7, T8, T9, T10 | P1 rời rạc, mỗi việc một commit nhỏ |
| 5 | T11, T12, T13 | Ba phần brief yêu cầu mà chưa có |
| 6 | T14, T15 | Dọn nốt |

Sau mỗi lượt: chạy test của **phần vừa sửa**, không chạy full suite.
Lượt 1–3 xong thì dừng, để An xem trước khi đi tiếp — đó là phần đổi
nhiều nhất về mặt nhìn.

**Không tự commit.** Làm xong từng lượt thì báo cáo, An tự commit.

---

## Nghiệm thu cả plan

Chép từ checklist của ghi chú, dùng làm điều kiện đóng:

**UX**
- [ ] 1440×900 không cuộn: thấy bên dẫn, ΔU, độ tin cậy, khuyến nghị
- [ ] Lý do không-khuyến-nghị nói đúng hai lần trên toàn trang
- [ ] Ba thẻ use case luôn có nội dung, kể cả run bị chặn
- [ ] `TracePanel` đóng mặc định
- [ ] Dưới 900px: summary → advice → bảng

**Visual QA**
- [ ] Không màu nào đứng một mình mang nghĩa
- [ ] Grep `candidate-b` trong globals.css không ra token xanh lá
- [ ] Không row bảng nào cao quá 60px
- [ ] `<thead>` sticky
- [ ] Số căn phải theo dấu thập phân
- [ ] Bo góc ≤ 8px, tối đa một lớp shadow mỏng, không gradient lớn
- [ ] Locale `vi` không còn câu tiếng Anh

**Data integrity**
- [ ] `noCardReason` phân biệt được cleared===1 và cleared===0
- [ ] Cột Winner cộng lại khớp câu tóm tắt "dẫn 5 trên 8 chỉ số có hướng"
- [ ] Contribution cộng lại đúng bằng utility trên card
- [ ] Metric ngược chiều tính winner đúng chiều
- [ ] Đơn vị clearance in cả `m` và `r`, không chỉ một
- [ ] Hai chart latency chung scale
- [ ] Detector table hiện tên candidate
