# Báo cáo: đã sửa UI trang `/decisions/[id]` theo plan

Ngày: 2026-08-22 · Nhánh `tongduyan_4` · **Đã chạy hết 6 lượt, 15 việc.**

Plan: [sua-ui-trang-decision.md](../../plans/2026-08-22/sua-ui-trang-decision.md)
(An duyệt cùng ngày). Ghi chú gốc:
[tongduyan_ra-soat-ui-trang-decision.md](../../notes/2026-08-22/tongduyan_ra-soat-ui-trang-decision.md).

Bảy commit, `881f21d`..`c63aca5`.

| Lượt | Commit | Việc |
|---|---|---|
| — | `881f21d` | Ghi chú rà soát + plan đã duyệt |
| 1 | `46cd764` | T1 — tách `single_survivor` khỏi `no_survivors` |
| 2 | `c96ecae` | T6 màu identity, T5 cột Winner + hướng metric |
| 3 | `5d21da9` | T2 `DecisionSummary`, T3 `DecisionAdvice`, T4 hạ replay |
| 4 | `dfd380f` | T7 localize, T8 đơn vị clearance, T9 nén row, T10 tên candidate |
| 5 | `1e40a39` | T11 trade-off, T12 bars chuẩn hoá, T13 panel điểm |
| 6 | `c63aca5` | T14 export lên header, T15 chung scale chart |

---

## Ba thứ hoá ra khác với lúc lập plan

Ghi ra vì chúng đổi cách hiểu vấn đề, không chỉ đổi cách sửa.

### 1. Tint cột không đến từ CSS của bảng

Ghi chú nói "cột B viền xanh lá, nền xanh lá". Trong `globals.css`,
khối CSS của bảng có hẳn một comment **"No column-wide tint"** và đúng
là không có rule nào set nền cho `.comparison-cell`.

Tint đến từ chỗ khác: `.candidate-a` / `.candidate-b` là **selector
trần**, viết cho card chọn candidate ở trang list, và nó bắt mọi phần
tử mang class đó — kể cả `<td className="comparison-cell candidate-b">`
cách nó 1400 dòng. Comment kia nói thật về khối của nó và vẫn sai về
màn hình.

Test cũ khoá đúng cái sai đó:

```js
expect(CSS).not.toContain(".comparison-cell.candidate-b {");
```

Selector này chưa từng tồn tại, nên test xanh trong khi tint vẫn hiện.
Đã scope hai rule vào `.candidate-card` và thêm test khoá selector trần.

### 2. Winner đã có nhãn — cho screen reader

`MetricLine` đã in `sr-only` "(leads)"/"(trails)" bên cạnh mỗi số, và
`standings()` đã tính sẵn lead/trail/none. Người mất tín hiệu là
**người sáng mắt bị mù màu**: đỏ và xanh là toàn bộ thứ họ có.

Nên T5 nhẹ hơn dự kiến — cột Winner đọc lại `mark` sẵn có, không viết
logic mới. Điều kiện "hàng này có phải phép so không" cố ý dùng đúng
hai điều kiện của `comparisonSummary`, và có test khoá: số hàng in `A`
phải khớp câu "dẫn 5 trên 8" phía trên bảng.

### 3. `Outcome` là hai component dính làm một

Nó render bảng sensitivity khi có card, và thông báo không-khuyến-nghị
khi không có — rẽ nhánh trên đúng một điều kiện mà cả trang xoay quanh.
Đó là lý do kết luận nằm ở màn hình thứ sáu: nửa "thông báo" bị nửa
"bảng số" kéo xuống đáy.

Đã tách: thông báo thành một nhánh của `DecisionSummary` trên đỉnh,
`CardPanel` render thẳng dưới `EvidencePanel`.

---

## Từng việc

### T1 — `single_survivor` *(lỗi đúng/sai)*

[decisions.ts:856](../../../../apps/web/src/lib/decisions.ts#L856) chỉ có ba
nhánh, nhánh cuối bao trọn. Docstring viết `no_survivors` nghĩa là
"fewer than two candidates cleared" — nhưng chuỗi hiển thị của nó nói
"Không candidate nào qua đủ cổng". Run có đúng một bên qua cổng đọc ra
câu phủ định chính bảng cách đó ba dòng.

Thêm nhánh đếm `cleared_gates`, thêm hai key mỗi locale. Cập nhật
`REASON_TONE` (Record vét cạn, thiếu là lỗi TypeScript) và
`runOutcome` trong `explainPanel.ts` — taxonomy của explain panel hỏi
"có phép so nào không", cả hai trường hợp đều không, nên chúng chung
outcome ở đó và chỉ khác nhau ở câu chữ.

Test: 4 case cho `noCardReason`, gồm case hai bên qua cổng mà vẫn không
có card — **không** được mượn câu một-bên.

### T2 — `DecisionSummary`

Component mới. Hai điểm + bar, cạnh card khuyến nghị. Dùng lại
`outOf100`, `standings`, `verdictOf`, `marginIsConclusive` — không tính
lại điểm ở đâu cả.

Card đọc theo `verdictOf`: có card thì in ΔU · CI95 · n; near-equivalent
thì nói hoà; no-card thì in lý do + việc cần làm, **một lần trên toàn
trang** (có test đếm đúng bằng 1).

Khoảng tin cậy cắt qua 0 thì đổi câu chú thích và tô cảnh báo — ΔU mà
run không chứng minh được, in trần, là cách một lần tung đồng xu đọc
thành phát hiện.

Câu nguyên văn của platform (`why_no_card`, `gate_only_deployment`)
theo lên cùng, không rơi mất theo panel cũ.

### T3 — `DecisionAdvice`

`lib/decisionAdvice.ts` thuần, năm nhánh: `none` · `sole` · `tie` ·
`single` · `hybrid`. Cắt objective hai-và-hai: `U_R`+`U_S` là phần
robot **đạt được**, `U_E`+`U_C` là phần nó **tiêu tốn** — cùng lát cắt
mà `tradeoffs.ts` dùng, nên thẻ khuyến nghị và insight không thể nói
ngược nhau.

Hai chỗ dễ sai, đều có test khoá:
- Run không có `objectives` (bản cũ) → ra `single` theo utility, **không**
  bịa hybrid từ hai giá trị null.
- Một bên dẫn cả hai nửa → `single`, không phải `hybrid`.

Ba thẻ luôn có nội dung. Run `sudden_stop_v5` ra `sole`: thẻ chất lượng
là `astar+dwa`, hai thẻ còn lại nói "Không có" kèm lý do và nêu đích
danh `rrtstar+dwa (G3)`.

### T4 — vị trí replay *(sửa lại sau khi An xem)*

Ban đầu làm đúng plan: `<details>` đóng sẵn, chuyển xuống sau
`EvidencePanel`. **An báo mất canvas so sánh realtime.** Đã trả lại.

Lập luận cũ đúng một nửa. Đúng ở chỗ: replay không được đứng trước
những panel nói run kết luận gì — người vào xem kết quả gặp bộ chọn 30
episode trước tiên là sai. Sai ở chỗ: xem hai candidate chạy cạnh nhau
**là cách An đọc run này**, không phải bước kiểm tra làm sau; đóng lại
và đẩy xuống bốn màn hình thì đọc thành đã mất.

Vị trí chốt: **một section riêng ngay dưới `CandidateComparison`**,
trên `TradeoffInsights`. Lần đầu trả lại tôi để nó dưới
`TradeoffInsights` để bảng và phần đọc bảng dính nhau — An bảo không,
canvas là phần riêng và đứng trước. `TradeoffInsights` xuống dưới
replay, và đọc hợp lý hơn ở đó: nó tóm tắt cả bảng lẫn hai canvas.

Mở sẵn (`open`), vẫn là `<details>` nên xem xong gấp lại được, số
episode nằm trên summary để biết bên trong có gì khi đã gấp.

Thứ tự render hiện tại:

```
SampleNotice · DecisionSummary · DecisionAdvice · CandidateComparison
· TracePanel(details, open) · TradeoffInsights · ExplanationHeader
· EvidencePanel · ConclusionPanel · CardPanel · HumanActs
```

Hai ràng buộc cũ giữ nguyên: `SampleNotice` đứng đầu, `ExplanationHeader`
dính ngay trên `EvidencePanel` (test cấm chèn component nào vào giữa).

### T5 — cột Winner + hướng metric

Cột `Thắng` in `A` / `B` / `hoà` / `—`. `—` mang `title` nói vì sao —
"hoà" và "chưa từng là phép so" là hai sự thật khác nhau, một glyph cho
cả hai là đúng lỗi mà ô giá trị đã tránh với `chưa đo` vs `0`.

Mũi tên ↑/↓ cạnh tên metric. Sáu trên mười hàng thắng bằng số nhỏ hơn,
và `+9.35 ms` đọc như cải thiện với người chưa biết điều đó.

Caption dưới bảng nói **vì sao không có cột weight**, thay vì im lặng.

`<thead>` sticky, số căn phải theo dấu thập phân (`.num` đã có
`text-align: right`, thêm nền cho thead vì sticky cell mặc định trong suốt).

### T6 — màu

`--candidate-b` từ `--teal` (`#087f6a`) sang `--purple`. Teal đứng cạnh
`--ok` (`#1a7f37`) là hai màu xanh lá, một nghĩa "candidate B", một
nghĩa "số tốt hơn". Trên run này B là bên bị loại và cả cột nó nhuộm
xanh lá — màu nói ngược với badge ngay trên đầu cột.

Cộng với việc scope selector trần (mục 1 ở trên). Test khoá: không token
`--ok`/`--err`/`--teal` nào được làm identity candidate.

### T7 — localize khối contrast

Nguồn: [contrast.py:212](../../../../packages/explanation/planbench_explanation/contrast.py#L212)
— prose ghép trong Python. Badge dịch được vì nó khoá trên `verdict`;
câu dưới thì không vì nó là văn bản.

Áp khuôn `hostWarningView`: `latticeReason()` trả về key + subject cho
ba verdict tái tạo được, trả về nguyên văn cho verdict còn lại và cho
verdict lạ.

**`interaction_not_isolated` cố ý giữ nguyên văn.** Reason của nó liệt
kê các component mà hiện tượng đi theo, và danh sách đó không tồn tại ở
đâu khác trong payload — nó được ghép thẳng vào câu. Tự viết lại ở
client thì hoặc mất danh sách (là phần lớn nội dung), hoặc phải parse
ngược ra khỏi câu, tệ hơn là in nguyên.

### T8 — đơn vị clearance

`3.81 r` **không phải bug** — `"Worst clearance so far (robot radii)"`,
cố ý. Vấn đề là ô kế bên ghi `0.990 m` và bảng ghi `0.470 m`.

`trace.robot_radius_m` có trong payload nên quy đổi được thật: ô giờ in
`0.470 m · 3.81 r` kèm note nói bán kính dùng để quy đổi.

### T9 — nén row latency

Câu cảnh báo 4 dòng rút còn một dòng + `?`. Nội dung đầy đủ vào hint,
không mất. Ràng buộc cũ giữ: cảnh báo nằm trong row p99, không thành
banner phủ cả bảng.

### T10 — tên candidate trong bảng detector

Tra tên từ `run.report.candidates`, giữ hash mono bên cạnh — hash là thứ
đường dẫn trace và bug report khoá vào. Candidate có trong packet mà
không có trong report thì in hash trần: bịa nhãn tệ hơn nhãn khó đọc.

### T11 — `TradeoffInsights`

`lib/tradeoffs.ts`, bốn quy tắc: `tradeoff` · `sweep` · `unmeasured` ·
`atLimit`. Mỗi insight trả về **danh sách metric key nó đọc**, render
thành tên metric, nên mọi khẳng định tra ngược được lên bảng.

Run này ra `sweep`: "`astar+dwa` dẫn 5 trên 5 chỉ số có hướng,
`rrtstar+dwa` không dẫn ở chỉ số nào." Vẫn in — im lặng thì người đọc
không phân biệt được bảng một chiều với việc mình đọc sót.

Test khoá cái sai nguy hiểm hơn: **không bao giờ gọi sweep là tradeoff**.
Bảo người đọc cân một trade-off không tồn tại thì họ sẽ đi tìm nửa còn
lại.

### T12 — bars chuẩn hoá

Fill là **độ tốt**, không phải độ lớn: hàng `lower` thì số nhỏ hơn vẽ
bar dài hơn. Vẽ độ lớn thô sẽ đặt latency tệ nhất full width cạnh success
rate tốt nhất full width, và mắt quét dọc đọc cả hai thành thắng.

Thang: ngưỡng deployment khi có khai, giá trị lớn hơn của cặp khi không.
Nói rõ trong chú thích. Hàng không có hướng không vẽ.

Một bug tôi tự tạo và test bắt: một candidate vẫn vẽ bar — mỗi bar là
candidate so với chính nó. Đã chặn ở `candidates.length < 2`.

### T13 — panel điểm số

Nhãn chữ trước ký hiệu: `Thành công u_R 1.00`. Bar bị chặn vẽ viền đứt
rỗng thay vì xám.

**Không dùng gạch chéo** như plan viết: `repeating-linear-gradient` sẽ
là gradient thứ ba trong stylesheet mà test `tokens.test.ts` chỉ cho
phép đúng hai (`.progress-active` và `.skeleton`, cả hai đang animate
thứ gì đó). Viền đứt nói cùng ý — "không nằm trên cùng thang đo" chứ
không phải "thấp trên thang đo" — mà không phá luật đó.

### T14 — export lên header

Chỗ này **đảo ngược một quyết định cũ có lý do ghi lại**, nên nói rõ.

Test `decision-prose.test.tsx` khoá "export sau phần điểm", lý do: đừng
mời người đọc gửi run đi trước khi họ đọc kết luận. Đúng — hồi đó.

Sau lượt 3, kết luận là panel **đầu tiên**, ngay dưới header. "Sau phần
điểm" và "trên header" từ chỗ cách nhau sáu màn hình nay cách nhau một
cái liếc. Chỗ cũ có cái giá mà chỗ mới không có: nút không có tiêu đề
section nào, trôi giữa hai panel, người vào để export phải cuộn qua toàn
bộ lập luận mới thấy.

Test viết lại kèm nguyên đoạn lý do này, không xoá lịch sử tranh luận.

### T15 — chung scale chart

`latencyPlot` thêm tham số `tFloorS`; `duration` (max của cặp, đã có sẵn
ở `TracePanel`) luồn xuống qua `CandidateEpisode` → `TraceViewer` →
`LatencyChart`. Episode ngắn hơn giờ kết thúc giữa khung — đó là sự thật.

Nhãn trục y `54` đè `50`: `msMax` là budget + 8% headroom trên mọi run
không spike, nên hai nhãn cách nhau vài pixel. Bỏ nhãn khung khi nó rơi
trong `TICK_GAP` của nhãn budget — budget là đường có nghĩa, đỉnh khung
chỉ là chỗ nét vẽ dừng.

---

## Phần **không** làm, và vì sao

Nói thẳng vì cả hai đều nằm trong plan.

### Breakdown `weight × score = contribution` trên panel điểm *(T13, ý thứ ba)*

**Không làm được trong phạm vi web-only.** Trọng số objective không có
trên `DecisionRun`. Chúng có ở hai chỗ khác:

- `PacketWaterfall.bars[].weight` — nhưng đó là phân rã **ΔU của cặp**,
  và chỉ tồn tại khi có waterfall, tức khi có phép so. Run bị chặn không có.
- `run.manifest.preference_profile` phía backend — lấy được nhưng phải
  nối dây API, mà plan ghi rõ "không sửa backend".

`EvidencePanel.WaterfallBlock` **đã** render `objective | weight | delta
| contribution | ci` cho run có waterfall, nên phần này không trống hoàn
toàn. Việc đã làm: sửa caption cột weight của bảng so sánh cho trỏ đúng
chỗ đó, thay vì câu "xem cùng phần điểm bên dưới" (sai chỗ).

Muốn có breakdown per-candidate cho mọi run thì cần một việc backend
riêng — đề xuất tách plan.

### Bỏ ô "Đã đi được 0.0 %" ở `t = 0` *(T15, ý cuối)*

**Cố ý không làm.** Ở `t = 0` thì **mọi** ô tích luỹ đều đọc số 0 của
nó: exposure `0.0 s`, replan `0`, path efficiency `0.000`. Bỏ riêng ô
progress là tuỳ tiện; bỏ hết bốn ô thì lưới 7 ô reflow ngay khung hình
đầu tiên của mỗi lần phát — giật hình mỗi lần bấm Chạy, tệ hơn hẳn một
ô đọc `0.0 %` trong một khoảnh khắc.

---

## Kiểm chứng

Typecheck `tsc --noEmit`: sạch sau mỗi lượt.

Test web: **70 file, 1621 test, xanh hết.** Thêm mới trong đợt này:

| File | Nội dung |
|---|---|
| `lib/__tests__/decision-advice.test.ts` | 7 test — năm nhánh + hai bẫy |
| `lib/__tests__/tradeoffs.test.ts` | 8 test — bốn quy tắc + không-gọi-sweep-là-tradeoff |
| `components/__tests__/decision-summary.test.tsx` | 9 test — render summary + advice |
| `components/__tests__/tradeoff-insights.test.tsx` | 8 test — insight, bars, panel điểm |
| `components/__tests__/comparison-grid.test.tsx` | +9 test cột Winner |
| `app/__tests__/evidence-panel.test.tsx` | +5 test localize + tên candidate |

Test sửa vì tiền đề đổi, mỗi cái ghi lại lý do ngay trong test:
`trace-viewer` (thứ tự replay — sửa hai lần, lần hai sau khi An báo mất
canvas; test ghi cả hai lần sai theo hai hướng ngược nhau),
`evidence-panel` (thứ tự panel),
`decisions-page` (`Outcome` biến mất, no-card copy chuyển file),
`decision-prose` (vị trí export), `running-comparison` (chữ ký
`latencyPlot`, số key tile), `tokens` (không đổi — CSS mới viết đúng
scale ngay từ đầu sau lần đầu bị bắt).

Full suite chạy cuối cùng theo yêu cầu của An.

**Chưa merge, chưa push.** Bảy commit đứng trên `tongduyan_4`.

Ghi chú vặt: `git gc` chạy nền báo
`fatal: bad object refs/remotes/origin/tongduyan_3` sau mỗi commit. Ref
remote cũ hỏng, không ảnh hưởng commit nào. Dọn bằng
`git update-ref -d refs/remotes/origin/tongduyan_3` khi tiện.
