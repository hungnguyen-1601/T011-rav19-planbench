# Đã làm: Export Excel + Share report qua Email

Ngày: 2026-08-22 · Nhánh `tongduyan_4` · 9 commit từ `2609d8b` tới `5343ea1`.

Thực hiện theo [plans/2026-08-22/export-excel-va-share-email.md](../../plans/2026-08-22/export-excel-va-share-email.md).
Toàn bộ 11 phase đã xong.

---

## 1. Cần An xem trước: hai commit lẫn WIP của An

**Đây là lỗi của tôi, báo trước mọi thứ khác.** Lúc bắt đầu phiên, working
tree đã có sẵn phần việc chưa commit của An — bản refactor `ComparisonGrid`
sang table cell, kèm CSS, test và `candidateMetrics`. Tôi dùng
`git add -A <thư mục>` quá rộng và hai commit của tôi đã cuốn phần đó vào:

| Commit | Phần của An bị cuốn vào |
|---|---|
| `046a7db` (P2) | `globals.css` (refactor table-cell), `decisions-page.test.tsx`, hai file locale |
| `8ca24e9` (P9) | `ComparisonGrid.tsx`, `comparison-grid.test.tsx`, `candidateMetrics.ts`, `candidate-metrics.test.ts` |

**Không mất gì** — toàn bộ nội dung đã nằm trong lịch sử, và cả hai commit
đều xanh. Vấn đề là commit message mô tả việc khác với một nửa nội dung
của nó.

Chưa push, nên sửa được. Nếu An muốn tách ra thành commit riêng mang tên
An, tôi làm — cần rewrite hai commit đó. Nếu An thấy không đáng, để
nguyên cũng không hỏng gì.

---

## 2. Export Excel

### Tên file

`decision-<run_id>.xlsx` → `<project>_<comparison>_<YYYY-MM-DD_HH-mm>.xlsx`.
Ví dụ `warehouse_a_v2_astar-dwa-vs-rrtstar-dwa_2026-08-21_14-30.xlsx`.

- Trên 2 candidate thì đếm (`4-candidates`) chứ không liệt kê — tên nhồi
  bốn stack là tên không ai đọc hết.
- Timestamp là **thời điểm chạy run**, không phải lúc bấm nút: hai lần
  export cùng một run phải ra cùng một tên.
- `created_at` hỏng thì **bỏ hẳn đoạn timestamp**, không thay bằng `now()`.
  Một cái tên nói sai giờ tệ hơn một cái tên thiếu giờ, vì chỉ cái đầu
  được tin.
- Cắt thân ở 120 ký tự cho vừa giới hạn đường dẫn Windows.

### Workbook: 9 sheet

`Summary` · `Provenance` · `Sample` · `Gates` · **`Detailed Comparison`** ·
**`Objective Breakdown`** · `Decision Card` · `Episodes` · `Human record`

**`Summary` đứng đầu** — trước đây câu trả lời cho "run này ra cái gì" nằm
rải ở ba tab. Có đủ 7 mục yêu cầu, cộng `preference_profile` khi run ghi
lại. Run không có card vẫn có Summary, nói thẳng "không xếp hạng ai" kèm
lý do.

**`Detailed Comparison` thay `Outcome by candidate`** (An đã chốt bỏ). 10
cột:

```
Metric | Unit | <stack A> | <stack B> | Delta | Delta unit | Winner | Limit | Weight | Note
```

Mười dòng đúng bằng `comparisonRows()` trên UI. Chạy được với N candidate:
từ 3 candidate trở lên không sinh cột Delta (`B − A` vô nghĩa qua ba), và
Winner là một *tập* tên stack.

**`Objective Breakdown`** — 4 trục + 4 dòng con β + dòng tổng, có cột
`Contribution = Weight × U`. Cộng dọc ra đúng `decision_utility` của card.

### Số thật, không phải chuỗi

Ba sheet mới lưu **float** kèm `number_format`, nên sort / sum / vẽ biểu
đồ được. Sheet cũ giữ nguyên chuỗi.

Lý do tách: `as_number` dùng `%.3g` — ba chữ số **có nghĩa** — và Excel
không có khái niệm đó, nên không có format string nào tái tạo được. Ba
sheet mới dùng bộ số thập phân cố định của `candidateMetrics.ts` thay vì
`.3g`. Hệ quả: hai nhóm sheet có thể in khác số chữ số cho cùng một giá
trị, và sheet mới mang số thô nên bấm vào ô là thấy đủ — có một dòng
caveat `Precision` nói điều đó.

Tỉ lệ lưu **thô** (0.9667) dưới format `0.0%` — Excel tự nhân 100. Delta
của hai tỉ lệ lưu đã nhân sẵn, đơn vị `pp`, vì `2.0%` cho khoảng cách
giữa 70.0% và 72.0% là nói khoảng cách đó là tỉ lệ của một tỉ lệ.

Ô chưa đo để **rỗng thật** — không phải 0, không phải chữ "not measured".
Chữ trong cột số lấy mất khả năng sort của cả cột.

### Conditional formatting

Tô từ winner mà module đã tính (`PatternFill` tĩnh), **không** dùng
`CellIsRule` theo ngưỡng: một quy tắc thứ hai chạy trong Excel có thể lệch
khỏi cột `Winner` ngay bên cạnh, thành hai phán quyết trên một dòng.

Không tô: ô rỗng · dòng tie · dòng `no direction` · dòng chỉ một bên đo
được. **"Không dẫn đầu" khác "thua"** — một candidate không ghi được giá
trị thì không thua, vì không có cuộc so nào.

Cột `Limit` **có** dùng `CellIsRule`: ngưỡng đó do deployment khai, là sự
thật về giá trị chứ không phải về cuộc so sánh.

### Cột Weight — 3/10 dòng

Success rate → `w_r` · p99 → `w_c × β1` · Memory → `w_c × β2`. Bảy dòng
còn lại trống **và mỗi dòng nói rõ lý do trong Note**. Va chạm bằng 0
theo hợp đồng (HĐ-6 loại va chạm khỏi U_S để không đem đổi lấy tốc độ);
worst clearance không phải `w_s` vì U_S dùng **mean**.

Trọng số đọc từ `run.manifest["preference_profile"]` của **chính run đó**.
Bốn trường hợp, mỗi cái một câu khác nhau: khớp bảng · `(perturbed)` (sweep
HĐ-11.5 không lưu bộ thay thế → để rỗng, **không đoán**) · tên profile bảng
không còn · bảng trọng số không nạp được trong bản dựng này.

### Trạng thái UI

Success state: hiện filename thật (đọc từ `Content-Disposition`), nút đổi
nhãn thành "Download again". Nhãn nút đổi `Excel (.xlsx)` → `Export Excel`
/ `Xuất Excel`. Lượt mới xoá cả dòng lỗi lẫn dòng saved.

---

## 3. Song ngữ

An chốt làm cả hai định dạng. Mọi chuỗi vào một bảng `decision_text.py`,
`?locale=en|vi` trên cả `report.md` và `report.xlsx`, frontend truyền
ngôn ngữ đang chọn trong app (không phải `Accept-Language` của trình
duyệt — hai cái lệch nhau đủ thường).

Ba bất biến, khoá bằng test:

1. **Golden snapshot** `tests/golden/decision_report_{en,unranked_en}.md` —
   sinh **trước** khi động vào gì. Trước đó repo không có golden nào cho
   Markdown.
2. Gọi không locale bằng **đúng byte** gọi `locale="en"`.
3. Mọi key phải đủ cả hai ngôn ngữ, **không fallback**. Thiếu là raise.
   Một bản "tiếng Việt" lẫn nửa tiếng Anh thì người đọc không phân biệt
   được đâu là lựa chọn, đâu là lỗ hổng.

`?locale=fr` trả 422, không lặng lẽ đưa tiếng Anh. Tên file không đổi
theo ngôn ngữ.

Tên sheet tiếng Việt có test riêng cho giới hạn 31 ký tự của Excel.

---

## 4. Share report

Modal cạnh nút export, dùng lại pattern `.modal-backdrop` của
`SendForReview` (`role="dialog"`, `aria-modal`, Escape + click nền).

**Không giả vờ đã gửi.** Nút ghi `Open email client` / `Mở ứng dụng email`,
banner nói thẳng chưa nối provider, xác nhận ghi "ứng dụng email đã mở"
chứ không phải "đã gửi". Có test quét source cấm mọi chữ khẳng định đã
gửi — test này đã bắt được một biến tôi lỡ đặt tên `sent`, đúng như nó
được viết ra để làm.

- **Dung lượng là số đo, không phải lời khai.** Modal fetch luôn workbook
  khi mở, nên size hiện là size thật; blob đó cũng dùng lại cho nút tải
  file, không fetch hai lần. `mailto:` không mang được file nên phải nói
  rõ và đưa nút tải ngay đó.
- Chip input tách ở Enter/phẩy/space/blur, dán cả danh sách tách một lần.
- Regex email cố tình lỏng (`\S+@\S+\.\S+`): form từ chối một địa chỉ
  thật tệ hơn form để lọt lỗi chính tả mà người gửi sẽ thấy bounce.
- Chip sai tô đỏ **riêng chip**, không tô cả field — một địa chỉ sai
  trong năm cái đúng là một thứ cần sửa, tô cả field thì giấu mất cái nào.
- Checkbox link disabled kèm lý do trong tooltip, không bấm được rồi mới
  lỗi.
- Body dài quá `mailto` (1800 ký tự) thì cắt **có cảnh báo** + nút sao
  chép toàn văn.
- Prefill subject/message, sửa được hết. Run không card có câu riêng —
  "recommended: not measured" đọc như template hỏng.

---

## 5. Test

| Suite | Kết quả |
|---|---|
| Web (`vitest`, toàn bộ) | **1566 / 1566 xanh**, 66 file |
| Python (`pytest tests/`, toàn bộ) | **3855 xanh, 9 skip, 1 đỏ** |

Test đỏ: `tests/test_execution_conditions.py::TestNothingTheSimulatorReadsIsUnhashed::test_run_stack_has_not_grown_a_condition`
— `planning_recorder` xuất hiện trong tập điều kiện của run stack.

**Không liên quan tới việc này.** `planning_recorder` chỉ nằm trong
`packages/benchmark/episode.py`, `services/simulator/nav_stack.py` và ba
file test; `git diff 2609d8b..HEAD` trên `tests/test_execution_conditions.py`,
`services/simulator/` và `packages/benchmark/` **rỗng hoàn toàn**. Đây là
lỗi có sẵn từ trước.

Test mới thêm: 39 (`test_decision_comparison.py`) + 20
(`test_decision_text.py`) + 2 golden + ~20 trong `test_decision_xlsx.py` +
24 (`share-report-dialog.test.tsx`) + 6 trong `decisions-page.test.tsx`.

Đáng giá nhất vẫn là hai cái đã nêu trong plan:

- `SUM(Contribution) == decision_utility` — bắt cùng lúc bốn thứ: số phải
  là số thật, trọng số đúng profile, ánh xạ objective đúng, và không có
  đường chấm điểm thứ hai lẻn vào.
- Test parity đọc thẳng `candidateMetrics.ts` bằng regex, khoá key /
  thứ tự / direction / unit / deltaUnit / `TIE_TOLERANCE`. Trôi là đỏ ngay.

**Có sửa test cũ, không sửa để cho qua:**

- 3 file web đọc source Python dạng text — chuỗi chuyển sang
  `decision_text.py`, claim không đổi, chỉ đổi chỗ đọc.
- `test_the_outcome_table_carries_what_the_page_compares_on` → đổi tên và
  nhắm vào `Detailed Comparison`.
- Test đếm call site của `recommendedCandidateLabel` cứng ở 2 → nới thành
  "≥ 2 và không có derivation inline nào", vì ý nó là "một lookup dùng
  chung", không phải con số.
- `test_neither_invents_a_number_the_other_lacks` giới hạn vào các sheet
  còn mirror Markdown, kèm lý do. **Hai test đồng-nhất `.md`↔`.xlsx` cốt
  lõi không phải sửa dòng nào** — đúng như plan dự đoán.

Golden snapshot có regenerate **một lần**, ở P6, vì tôi sửa fixture cho
`decision_utility` bằng đúng tổng có trọng số của chính nó (trước đó là
số bịa, khiến không viết được assertion cộng dọc). Diff chỉ chạm các con
số utility, không chạm cấu trúc nào — renderer không đổi.

---

## 6. Đổi so với plan

| Plan | Thực tế | Lý do |
|---|---|---|
| P4 Summary trước P5 hạ tầng số | Đảo lại | Summary tiêu thụ tầng số; làm ngược thì viết chuỗi rồi sửa lại thành số |
| Bảng text nằm trong `decision_export.py` | Module riêng `decision_text.py` | ~140 entry, nhiều đoạn ba câu; để chung thì phần logic chìm nghỉm |
| Q2: `HEAD` endpoint để đo dung lượng | Fetch luôn workbook | Không cần endpoint mới, size là số đo thật, và blob dùng lại cho nút tải |
| Markdown cũng bỏ `Outcome by candidate` | Markdown **giữ** | Tài liệu đọc từ trên xuống; bảng xoay dọc đẩy tên stack lên header không ai cuộn lại. Bỏ cũng sẽ phá golden. |
| Eligibility về `Objective Breakdown` | Đúng vậy, dạng dòng chữ | yes/no là phán quyết; số 1/0 trong cột utility sẽ bị cộng vào |

---

## 7. Còn nợ

`path_efficiency`, `time_efficiency`, `near_miss_rate`,
`cpu_time_per_mission_s`, `tuning_wall_clock_h` là **đầu vào trực tiếp**
của U_S, U_E, U_C nhưng `selection.py` không viết vào report ở cấp nào.

Hệ quả nhìn thấy được ngay trên sheet `Objective Breakdown` vừa dựng: hai
dòng β cuối có trọng số thật, ô giá trị rỗng, note ghi
`"input not recorded in the report"`. U_S và U_E cũng vậy — có điểm mà
không có số đo nào giải thích điểm đó từ đâu.

Lỗ hổng ở `selection.py`, không ở export. Sửa ở đó thì sheet tự đầy đủ.

Việc khác chưa làm: hợp nhất thật bảng metric (hiện dựa vào test parity),
và nối email provider.

---

## 8. Không làm

Không push. Không restart server. Test đỏ có sẵn ở
`test_execution_conditions.py` để nguyên — ngoài phạm vi.
