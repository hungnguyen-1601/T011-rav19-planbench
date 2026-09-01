# Báo cáo — Đợt 3.1: F09 Biểu đồ và xuất báo cáo

> **Ngày:** 2026-08-07
> **Plan nguồn:** `docs/antongduy/plans/2026-08-05/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`, mục **3.1**
> **Nhánh:** `integrate-tongduyan`
> **Tiền đề:** Đợt 0–2 đã xong (RRT\*, Docker, P02, P04, P05, P03, Scenario Editor).
> **Phạm vi:** chỉ 3.1. Mục 3.2 (F05 — sửa metrics engine) **chưa** làm.

---

## 1. Vấn đề đang giải

Bốn đợt trước sinh ra một đống số có giá trị: lớp quan sát (P02), trung
vị + IQR + CI95 + p-value + effect size (P04), tập dev/holdout và chênh
lệch tổng quát hóa (P05), độ khó đo được (P03).

Toàn bộ số đó **nằm sau một màn đăng nhập, trong các bảng**. Hai hệ quả:

1. Người review không mở được kết quả nếu không có tài khoản — nghĩa là
   không có cách nào gửi một kết quả benchmark cho người bên ngoài kiểm
   tra. Một nền tảng benchmark mà kết quả không rời khỏi được nó thì
   phần "có thể kiểm chứng" chỉ là lời hứa.
2. Một tỉ lệ thành công trung bình không nói được thuật toán **hỏng ở
   đâu**. `78%` có thể là "qua hết scenario dễ, chết sạch scenario khó"
   hoặc "giảm đều" — hai thuật toán khác hẳn nhau, cùng một con số.

3.1 giải đúng hai chuyện đó: ba biểu đồ, và một endpoint xuất Markdown.

---

## 2. Quyết định đã chốt trước khi code

Plan để mở mục "Điểm cần quyết định khi approve" số 2: `recharts` hay
SVG thủ công. **Đã hỏi và user chọn `recharts`** (bản 3.10.1, tương
thích React 19). Đây là dependency runtime đầu tiên của `apps/web` ngoài
Next/React — chi phí thật, ghi ở KNOWN_LIMITATIONS #145: bundle
first-load của `/leaderboard` và `/benchmarks/[id]` đi từ ~140 kB lên
~262 kB.

Đổi lại: không phải tự viết trục, chú giải, tooltip và error bar.

---

## 3. Ba ranh giới của biểu đồ

Đây là phần đáng bàn của đợt này. Biểu đồ là chỗ người đọc **ngừng đặt
câu hỏi sớm nhất** — mắt chấp nhận một đường cong trước khi đầu kịp hỏi
nó được vẽ từ cái gì. Nên ba luật dưới đây được đặt vào **tầng dữ liệu**
(`apps/web/src/lib/charts.ts`), là hàm thuần có test, chứ không nằm rải
trong JSX.

### 3.1. Giá trị thiếu không bao giờ được vẽ thành 0

Một stack chưa bao giờ về đích thì không có trung vị thời gian di
chuyển. Vẽ nó thành một cột cao 0 sẽ đọc thành "nó nhanh nhất" — đúng
ngược lại sự thật. Nên stack đó **không có cột**, và tên nó được liệt kê
dưới biểu đồ.

Tương tự: scenario chưa hiệu chuẩn không có toạ độ x, nên vắng mặt khỏi
đường cong; stack thiếu một phía dev/holdout không có cặp cột.

Ba builder đều trả về danh sách "cái gì đã bị loại" (`missing`,
`uncalibrated`, `incomplete`) — panel **không được phép** vẽ mà không
biết cái gì không có trên hình.

### 3.2. Không có thang đo thì không vẽ, chứ không thay bằng thứ trông giống

Trục x của đường cong độ khó là số đo P03. Nếu chưa ai chạy
`calibrate_difficulty.py` thì UI hiện thông báo "chưa có hiệu chuẩn",
**không** lấy `CURRICULUM_ORDER` ra làm trục.

`CURRICULUM_ORDER` là thứ tự người viết xếp ra. Dùng nó làm trục sẽ cho
ra một biểu đồ **trông như đã đo** mà không đo gì — và toàn bộ lý do P03
tồn tại là để phát hiện thứ tự viết tay đó có đúng không.

### 3.3. Hai râu error bar là hai đại lượng khác nhau, và phải nói rõ

Cột là trung vị. Râu rộng là IQR (các lần chạy dao động bao nhiêu). Râu
hẹp là CI95 bootstrap cho chính trung vị (số seed này ghim trung vị chặt
tới đâu).

Vẽ mỗi CI95 sẽ mời người đọc nhầm một ước lượng hẹp của một đại lượng
dao động dữ dội thành "thuật toán ổn định" — đúng cái sai mà P04 sinh ra
để chặn. Panel ghi rõ râu nào là gì.

---

## 4. Đã làm gì

### 4.1. Backend — `GET /benchmarks/{id}/report.md`

Mới: `apps/api/planbench_api/report_markdown.py`.

Trả `text/markdown; charset=utf-8` +
`Content-Disposition: attachment; filename="benchmark-<slug>-<id>.md"`.
Benchmark chưa chạy trả **409** kèm câu chỉ việc cần làm, không phải một
tài liệu toàn ô trống — ô trống đọc như kết quả.

Bố cục tài liệu đặt **nguồn gốc trước kết quả**: id, thời điểm,
`git_sha`, checksum điều kiện/map/scenario, danh sách seed,
`protocol_version`, split, độ khó + `calibration_version`. Một con số
mất điều kiện đi kèm thì không còn là bằng chứng.

Sau đó: điều kiện chạy → stack + lớp quan sát → tỉ lệ kết cục → phân
phối → kiểm định ghép cặp → chênh lệch tổng quát hóa → bảng từng run →
**giới hạn đã biết**.

Ba chi tiết đáng nói:

**Ký tự đặc biệt không được phá bảng.** Tên benchmark là dữ liệu người
dùng. Một dấu `|` trong tên sẽ tách hàng thành thêm một cột và dịch mọi
ô sang trái — một bảng hỏng mà vẫn *trông như* bảng, tệ hơn một bảng
hỏng rõ ràng. `_cell()` escape `|` và `\`, gộp xuống dòng thành khoảng
trắng. Có test đếm số cột của **mọi** hàng trong **mọi** bảng của tài
liệu.

**Cảnh báo nằm cạnh con số nó áp vào.** Số cặp seed in cùng hàng với
p-value; mục "Known limitations" là bản tóm tắt, không phải chỗ duy nhất
một giới hạn xuất hiện.

**Chênh lệch tổng quát hóa được ghi rõ là số của người khác.** Một
benchmark chạy một scenario nên tự nó không có gì để trừ. Route tính
summary giữa các benchmark **đã accepted** rồi truyền vào, và tài liệu
nói thẳng đó không phải kết quả của lần chạy này.

### 4.2. Frontend — ba biểu đồ

| Biểu đồ | Ở đâu | Đọc gì |
|---|---|---|
| Đường cong độ khó | `/leaderboard` | `/leaderboard` + `/difficulty-calibration`, join theo tên scenario |
| Trung vị + IQR + CI95 | `/benchmarks/[id]` | `report.aggregates` |
| Chênh lệch dev/holdout | `/leaderboard` | `/generalization` |

Mỗi biểu đồ một component (`DifficultyCurveChart`, `MetricIntervalChart`,
`GeneralizationGapChart`), tooltip riêng để hiện **scenario nào** đứng
sau một điểm — người nhìn thấy chỗ trũng muốn biết scenario nào trũng,
không phải toạ độ.

Chênh lệch dev/holdout vẽ **một biểu đồ cho mỗi metric**: success rate,
travel time và path efficiency không cùng đơn vị, gộp một trục sẽ để một
số giây nằm cạnh một phân số và ngụ ý so được với nhau bằng chiều cao.

Bảng cũ ở panel generalization **được giữ nguyên**, không bị biểu đồ
thay thế: bảng là chỗ một kết quả holdout thiếu hiện lên **thành ô
thiếu**, còn biểu đồ chỉ có thể bỏ qua cột đó.

### 4.3. Tải file khi endpoint có xác thực

Không dùng `<a href>`. Token nằm ở header, đưa vào URL sẽ để lại vết
trong history và log của mọi proxy trên đường đi.

`apps/web/src/lib/reports.ts`: `fetch` với header `Authorization` →
`Blob` → object URL → thẻ `a` tổng hợp → revoke. Revoke ở **tick sau**
chứ không ngay lập tức: vài trình duyệt chưa kịp đọc URL lúc `click()`
trả về và sẽ lưu ra file rỗng.

Tên file lấy từ `Content-Disposition` của server (server là bên biết tên
benchmark và đã làm nó an toàn), có fallback theo id nếu proxy cắt
header, và luôn lọc `/` `\` khỏi tên server gửi về.

---

## 5. Test

**Backend — `tests/api/test_api_report_export.py`, 20 test:**

- giao nhận: content-type, `Content-Disposition`, tên file, 401 khi
  không đăng nhập, 200 với người không sở hữu (đọc mở, làm mới khóa),
  404 benchmark lạ, **409 benchmark chưa chạy** + đúng thông điệp;
- nguồn gốc: id, ba checksum, `git_sha`, seed, `protocol_version`,
  split, độ khó, lớp quan sát;
- số liệu: bảng trung vị/IQR/CI95, đủ hàng run, p-value không bao giờ
  xuất hiện thiếu số cặp seed, một thuật toán thì nói rõ không chạy
  kiểm định;
- cảnh báo: benchmark ít seed, benchmark chưa accepted, chênh lệch
  "không tính được" chứ không phải 0;
- giá trị thiếu: blank hết trường phân phối → ra `—`, **không** ra
  `0.000`; stack không còn trong registry → báo "không rõ lớp quan sát";
- toàn vẹn Markdown: `|` trong tên bị escape và **mọi bảng giữ đúng số
  cột**; xuống dòng bị gộp; tên file không chứa `/`, `..`, `"`.

**Frontend — `src/lib/__tests__/charts.test.ts`, 19 test:** join theo
scenario, sắp theo trục, loại scenario chưa hiệu chuẩn và **gọi tên**
chúng, trung bình theo report chứ không gộp theo episode, cờ `stale`,
không có calibration thì không vẽ gì, bounds → offset hai phía, không vẽ
cột 0 cho stack không có trung vị, râu không bao giờ chỉ ngược, dấu của
gap đọc theo `higher_is_better`, tên file tải về.

**Frontend — `src/app/__tests__/charts-and-export.test.tsx`, 17 test:**
nối dây ở mức source (panel có mount, cảnh báo ít seed có trên panel
biểu đồ, bảng generalization không bị thay thế, download không đưa token
vào URL, có `createObjectURL` + `revokeObjectURL`), và **mọi khóa dịch
`charts.*` được dùng đều có trong cả `en.json` lẫn `vi.json`**.

**Tổng:** backend `1363 passed, 4 skipped` (chạy toàn bộ `pytest`).
Frontend `435 passed` + 36 test mới.

> **Hai test frontend đang đỏ và không phải do đợt này.** Đã kiểm bằng
> cách stash toàn bộ thay đổi rồi chạy lại: cả hai đỏ y hệt trên cây
> sạch.
> 1. `assistant-page.test.tsx` — `readFileSync` trên
>    `src/app/models/page.tsx`, file **không tồn tại** trên nhánh này.
> 2. `dashboard-page.test.tsx` — so `"/system/page.tsx"` với đường dẫn
>    ghép bằng `path.join`, ra `"\system\page.tsx"` trên Windows.
>
> Cả hai nằm ngoài phạm vi 3.1 nên không sửa kèm; ghi lại ở đây để
> không ai mất công điều tra lại.

---

## 6. Kiểm chứng end-to-end

Chạy API thật (in-memory), import 3 scenario thư viện — `open_space` và
`doorway` (dev), `intersection` (holdout) — mỗi cái một benchmark
`astar+dwa` + `rrtstar+dwa` × 5 seed, accept cả ba, rồi:

**1. Xuất report thật:**

```text
content-type: text/markdown; charset=utf-8
disposition: attachment; filename="benchmark-e2e-intersection-23564f605759.md"
159 dòng, 7826 byte
```

Trích phần nguồn gốc — độ khó và calibration nối đúng:

```text
| Scenario difficulty (P03) | 0.033 (CI95 0.006–0.167, band easy) |
| Difficulty calibration version | 1.0.0 |
| Difficulty baseline | `astar+dwa` |
```

Và phần giới hạn tự sinh đúng theo dữ liệu:

```text
- Only 5 seed(s). Below 30 the intervals are wide and a significant
  p-value is a reason to look further, not a result.
- This is a held-out scenario. Every look at held-out results erodes
  what makes them held out; this run is part of that record.
```

**2. Chạy chính hàm dựng biểu đồ trên payload API thật** (lưu
`/leaderboard`, `/generalization`, `/difficulty-calibration` ra file rồi
nạp vào `buildDifficultyCurve` / `buildGapSeries` — không dùng fixture):

```text
calibration 1.0.0, baseline astar+dwa, uncalibrated [], stale []
astar+dwa    doorway 0.000/100%  open_space 0.000/100%  intersection 0.033/100%
rrtstar+dwa  doorway 0.000/100%  open_space 0.000/100%  intersection 0.033/100%
gap success_rate: cả hai stack dev 1.0 / holdout 1.0 / gap 0.0
gap median_travel_time: astar dev 9.95 / holdout 13.40 / gap −3.45
```

**3. SSR không vỡ:** `next start`, `GET /leaderboard` → 200,
`GET /benchmarks/{id}` → 200, log server sạch. (Đây là kiểm chứng
render duy nhất có được: môi trường test là Node không jsdom nên
`recharts` không dựng SVG để assert — xem giới hạn #144.)

**Một phát hiện từ chính lần kiểm chứng này:** đường cong gần như
**phẳng**. Ba scenario nằm ở 0.000, 0.000 và 0.033, cả hai stack đều
100%. Đây không phải lỗi biểu đồ — đây đúng là kết luận P03 đã ghi
(thang độ khó rỗng ở khoảng giữa) hiện lên thành hình lần đầu. Biểu đồ
làm đúng việc của nó: nó cho thấy bộ scenario hiện tại **không phân biệt
được** hai stack.

---

## 7. Chỗ làm khác plan, và vì sao

**Plan viết biểu đồ 2 vẽ cho 5 metric** (travel time, path efficiency,
smoothness, clearance, latency). Làm 3.

Clearance và latency được tổng hợp thành worst/mean chứ **không** có
trung vị + IQR + CI95 — không có gì để vẽ râu. Bịa một khoảng cho chúng
là đúng thứ mà cả panel này sinh ra để tránh. Hai metric đó vẫn nằm
trong bảng và trong report. Percentile latency là việc của F05 (mục
3.2), và khi có thì thêm vào đây là chuyện nhỏ.

**Bộ lọc scenario không áp cho biểu đồ.** Lọc còn một scenario thì
"đường cong" chỉ còn một điểm. Đường cong và chênh lệch dev/holdout luôn
dựng từ dữ liệu không lọc, giống cách panel generalization đã làm từ
P05. Hệ quả: bảng và biểu đồ trên cùng một trang có thể đang nói về hai
tập dữ liệu khác nhau — ghi ở #139.

---

## 8. Definition of Done (plan mục 3.1)

- [x] Người dùng tải được Markdown report.
- [x] UI hiển thị difficulty curve.
- [x] UI hiển thị median, IQR và CI.
- [x] UI hiển thị generalization gap.
- [x] Report có metadata tái lập (git SHA, checksum, seed, protocol
      version, calibration version).
- [x] Report không kết luận mạnh khi thiếu dữ liệu.

Danh sách test của plan cũng đủ: benchmark chưa hoàn thành trả lỗi rõ
ràng (409), content type đúng, có `Content-Disposition`, filename hợp
lệ, warning khi thiếu seed, có observation class, có protocol version,
có calibration version, field `null` không phá render, ký tự đặc biệt
không phá Markdown.

---

## 9. Giới hạn đã ghi vào `KNOWN_LIMITATIONS.md` (mục 136–145)

1. Đường cong chỉ vẽ được scenario đã hiệu chuẩn — và cache hiện tại
   rỗng ở khoảng giữa nên đường cong gần như chỉ có hai cụm ở hai đầu.
2. Một điểm có thể là trung bình nhiều report; nhìn hình không phân biệt
   được điểm từ 1 lần chạy với điểm từ 5 lần chạy.
3. Bật trộn nhóm quan sát thì biểu đồ trộn theo, và cảnh báo chỉ ở bảng.
4. Bộ lọc scenario không áp cho biểu đồ.
5. Clearance và latency không có biểu đồ phân phối.
6. Report Markdown không nhúng biểu đồ; chưa có PDF.
7. `git_sha` trong report là commit của tiến trình API **đang chạy**,
   không phải commit lúc benchmark chạy.
8. Độ khó và chênh lệch tổng quát hóa trong report đọc theo trạng thái
   **hiện tại**, khác với `scenario_split` và lớp quan sát (đã snapshot).
9. Không có test render biểu đồ (Node, không jsdom).
10. `recharts` là dependency runtime đầu tiên ngoài Next/React; bundle
    trang phân tích ~140 kB → ~262 kB.

Mục **#125** cũng được sửa lại cho đúng: độ khó nay đã có đường cong và
có mặt trong report, nhưng **thứ hạng** vẫn chưa tính đến độ khó.

---

## 10. File đã đổi

**Mới:**
- `apps/api/planbench_api/report_markdown.py`
- `apps/web/src/lib/charts.ts`, `apps/web/src/lib/reports.ts`
- `apps/web/src/components/DifficultyCurveChart.tsx`
- `apps/web/src/components/MetricIntervalChart.tsx`
- `apps/web/src/components/GeneralizationGapChart.tsx`
- `tests/api/test_api_report_export.py`
- `apps/web/src/lib/__tests__/charts.test.ts`
- `apps/web/src/app/__tests__/charts-and-export.test.tsx`

**Sửa:**
- `apps/api/planbench_api/routers/benchmarks.py` (route `report.md`)
- `apps/web/src/app/leaderboard/page.tsx` (2 panel biểu đồ)
- `apps/web/src/app/benchmarks/[id]/page.tsx` (panel phân phối + export)
- `apps/web/src/app/globals.css` (`.chart-tooltip`)
- `apps/web/src/lib/i18n/locales/en.json`, `vi.json` (21 khóa)
- `apps/web/package.json`, `package-lock.json` (`recharts@3.10.1`)
- `docs/API_CONTRACT.md`, `docs/KNOWN_LIMITATIONS.md`

---

## 11. Bước tiếp theo

**Mục 3.2 — F05: sửa metrics engine.** Thêm `smoothness_squared` bên
cạnh smoothness cũ, latency p50/p95/p99, stop-and-go count, near-miss
count, time-to-first-collision — không xóa field cũ, không đổi nghĩa
field cũ.

Ba việc nhỏ nên làm cùng lúc đó:

1. **Percentile latency có phân phối** thì thêm được vào biểu đồ mục
   4.2 mà không phải sửa gì ngoài `INTERVAL_METRICS`.
2. **Chụp `git_sha` vào `report` lúc chạy** để bỏ được giới hạn #142 —
   là đổi schema nên phải đi cùng một đợt có đổi schema sẵn.
3. **Viết vài scenario lấp khoảng độ khó 0.2–0.8** rồi hiệu chuẩn lại.
   Lần kiểm chứng ở mục 6 cho thấy đây đang là giới hạn lớn nhất của cả
   bộ benchmark: biểu đồ vẽ đúng, nhưng không có gì để vẽ.

Sau 3.2 là mốc nghiệm thu chung Đợt 0–3 của plan: chạy lại
`docker compose build/up` (image web nay có thêm `recharts`) và kiểm
end-to-end trong container.
