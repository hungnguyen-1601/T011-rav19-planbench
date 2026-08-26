# Plan: hoàn thiện Export Excel + Share report qua Email

Ngày lập: 2026-08-22 · Nhánh `tongduyan_4` · An đã duyệt hướng, chốt hai
điểm mở (§5). Chưa code.

Căn cứ:
[notes/2026-08-22/tongduyan_verify-export-excel-share-email.md](../../notes/2026-08-22/tongduyan_verify-export-excel-share-email.md)
· [notes/2026-08-22/tongduyan_chon-metrics-cho-detailed-comparison.md](../../notes/2026-08-22/tongduyan_chon-metrics-cho-detailed-comparison.md)

---

## 0. Mục tiêu và ranh giới

**Làm:** đưa Export Excel từ 65% lên đủ yêu cầu, xuất được song ngữ, và
dựng Share report ở chế độ MVP trung thực.

**Không làm trong plan này:**

- Nối email provider thật (SMTP/SendGrid/SES). Chưa có hạ tầng, và quyết
  định đó là của An.
- Bổ sung `path_efficiency` / `time_efficiency` / `near_miss_rate` /
  `cpu_time_per_mission_s` / `tuning_wall_clock_h` vào report. Lỗ hổng
  của `selection.py`, phạm vi riêng — xem §7.

**Ràng buộc cứng về Markdown.** An đã chốt làm song ngữ, nên bản `.md`
**sẽ** có thêm một dạng output mới. Ràng buộc không mất đi, nó đổi hình:

> `render_decision_markdown(run, locale="en")` phải ra **đúng từng byte**
> như output hôm nay, ở mọi thời điểm của plan này. Tiếng Việt là output
> *thêm vào*, không phải output *thay thế*.

Ai đã lưu một bản `.md` trong ticket vẫn diff sạch với bản export lại.
Chi tiết cách khoá ở QĐ-4.

---

## 1. Bốn quyết định kiến trúc

Đọc trước — bốn điểm này chi phối mọi phase phía sau.

### QĐ-1. Số thật chỉ ở ba sheet mới, sheet cũ giữ nguyên chuỗi

Vấn đề: `as_number` dùng `%.3g` — **3 chữ số có nghĩa**, số chữ số thập
phân thay đổi theo độ lớn. Excel `number_format` không có khái niệm chữ
số có nghĩa, nên không dịch 1:1 được. Ép dịch là tự chuốc lỗi làm tròn.

Giải: **không đụng cách sheet cũ ghi giá trị.** Ba sheet mới (`Summary`,
`Detailed Comparison`, `Objective Breakdown`) ghi số thật với
`number_format` **cố định số thập phân**, lấy đúng bộ mà
`candidateMetrics.ts` đã dùng:

| Đại lượng | Python (để kiểm chứng) | Excel `number_format` | Ghi chú |
|---|---|---|---|
| Tỉ lệ | `f"{v*100:.1f}"` | `0.0%` | **Lưu giá trị thô 0.942**; Excel tự nhân 100 |
| Latency | `f"{v:.2f}"` | `0.00" ms"` | |
| Thời lượng | `f"{v:.1f}"` | `0.0" s"` | |
| Khoảng cách | `f"{v:.3f}"` | `0.000" m"` | |
| Bộ nhớ | `f"{v:.1f}"` | `0.0" MB"` | |
| Đếm | `f"{v:.0f}"` | `0` | |
| Utility / U | `f"{v:.4f}"` | `0.0000` | 4 chữ số để P7 cộng khớp |

Hệ quả phải nói rõ với người đọc: sheet cũ và sheet mới **có thể in khác
số chữ số** cho cùng một giá trị (`123.456` ms ra `123` ở `.3g` và
`123.46` ở `0.00`). Không phải bất đồng — sheet mới mang **số thô**, click
vào ô là thấy đủ. Một dòng caveat trên `Detailed Comparison` nói điều đó.

Đổi lại: hai test đồng-nhất `.md`↔`.xlsx` hiện có **không phải sửa**, vì
chúng soi sheet cũ. Trục cũ giữ nguyên bất biến; trục mới có test
đồng-nhất riêng với lưới UI.

### QĐ-2. Bảng metric khai một lần trong Python, UI đọc lại sau

`direction`, `unit`, `deltaUnit`, `TIE_TOLERANCE`, quy tắc `leaders()`
hiện sống trong [candidateMetrics.ts](../../../../apps/web/src/lib/candidateMetrics.ts).
Chép sang Python là bản định nghĩa thứ hai, sẽ trôi ở lần sửa đầu tiên.

Giải, **hai bước tách rời**:

- **Trong plan này:** khai bảng metric trong `decision_export.py`
  (`COMPARISON_METRICS`), và thêm **test parity** đọc thẳng
  `candidateMetrics.ts` bằng regex, khẳng định hai bên cùng danh sách
  key, cùng thứ tự, cùng `direction`, `unit`, `deltaUnit`, cùng tie
  tolerance. Trôi thì đỏ ngay.
- **Sau, ngoài plan này:** cho report mang bảng đó ra, UI đọc từ report,
  xoá bản TS. Chỉ làm khi An muốn.

Test parity mua 90% giá trị của việc hợp nhất với 10% rủi ro. Tiền lệ có
sẵn: [decisions-page.test.tsx:106](../../../../apps/web/src/app/__tests__/decisions-page.test.tsx#L106)
đã đọc source bằng chuỗi để khoá một bất biến.

### QĐ-3. `Detailed Comparison` thay thế `Outcome by candidate`

**An đã chốt: bỏ hẳn.** Nội dung sheet cũ là tập con thật sự:

- 10 cột metric → `Detailed Comparison` (xoay dọc, thêm unit, delta,
  winner, limit, weight, note)
- `Utility /100`, `U_R`, `U_S`, `U_E`, `U_C` → `Objective Breakdown`
- `Eligible to recommend` → cột trên `Objective Breakdown`, giữ nguyên
  caveat hiện có

**Phải hỗ trợ N candidate, không chỉ 2.** `comparisonRows()` đã đúng như
vậy và export phải theo:

| Số candidate | `Delta` + `Delta unit` | `Winner` |
|---|---|---|
| 2 | có | `A` / `B` / `tie` / `no direction` / `not measured` |
| ≥ 3 | **không sinh cột** | tên các stack dẫn đầu, phân tách bằng phẩy (`leaders()` trả về một **tập**) |
| < 2 ghi được giá trị | — | `not measured` |

### QĐ-4. Song ngữ: `en` là bản neo, `vi` là bản thêm

Mọi chuỗi người đọc thấy — nhãn hàng, tên sheet, tiêu đề mục Markdown,
caveat, note của metric — chuyển vào **một** bảng text khoá theo
`(key, locale)`. `locale` chảy qua tham số, không qua biến toàn cục và
không qua trạng thái module.

Bất biến khoá bằng test, không bằng lời hứa:

1. **Golden snapshot cho `en`.** Chưa có file golden nào cho Markdown
   (`tests/golden/` chỉ có `dwa_trajectories.json` và `host_parity.json`).
   Sinh một cái **trước khi động vào gì**, ở phase P0, từ code hiện tại.
   Từ đó mọi phase phải giữ nó xanh.
2. `render_decision_markdown(run)` — không truyền locale — phải bằng
   **đúng từng byte** `render_decision_markdown(run, locale="en")`.
   Mặc định không được đổi.
3. Mọi key trong bảng text phải có đủ cả `en` và `vi`. Test quét, thiếu
   một cái là đỏ. Không fallback lặng lẽ sang tiếng Anh — một bản "tiếng
   Việt" lẫn nửa tiếng Anh tệ hơn một bản tiếng Anh nhất quán.

Tên file **không** đổi theo locale: nó dựng từ `task_profile_id` và
`stack_label`, đều là ASCII, và một run phải có một tên.

Tên sheet tiếng Việt có dấu — Excel chấp nhận, nhưng `_sheet_name()` vẫn
phải chạy: giới hạn 31 ký tự tính theo ký tự, và tiếng Việt dài hơn tiếng
Anh. `"So sánh chi tiết"` vừa, nhưng phải có test cho mọi tên ở cả hai
ngôn ngữ.

---

## 2. Phase — Export Excel

### P0 · Golden snapshot cho Markdown hiện tại

**File:** `tests/golden/decision_report_en.md` (mới),
`tests/api/test_decision_markdown.py`

Sinh từ code **chưa sửa gì**, dùng fixture run có card đầy đủ. Thêm test
so sánh byte. Đây là lưới an toàn cho toàn bộ plan — làm đầu tiên, không
gộp với phase nào.

Nếu An muốn chắc hơn: sinh hai snapshot, một cho run có card và một cho
run không card (`no_card_reason` chạy nhánh khác).

---

### P1 · Tên file

**File:** `apps/api/planbench_api/decision_xlsx.py`,
`tests/api/test_decision_xlsx.py`, `routers/decisions.py`

```python
def decision_workbook_filename(run: Any) -> str:
    """<project>_<comparison>_<YYYY-MM-DD_HH-mm>.xlsx"""
```

- `project` ← `run.task_profile_id`
- `comparison` ← các `stack_label` nối bằng `-vs-`, theo thứ tự trong
  report; **> 2 candidate** → `<n>-candidates`; **0 candidate** →
  `no-candidates`
- timestamp ← `identity.created_at` ?? `run.created_at`, parse ISO, in
  `%Y-%m-%d_%H-%M`. **Thời điểm chạy run, không phải lúc bấm nút** — hai
  lần export cùng một run phải ra cùng một tên.
- Qua `_slug()`: giữ `[A-Za-z0-9._-]`, còn lại thành `-`, gộp `-` liên
  tiếp. `astar+dwa` → `astar-dwa`.
- Cắt thân ở 120 ký tự, tránh giới hạn đường dẫn Windows.
- `created_at` hỏng hoặc thiếu → **bỏ hẳn đoạn timestamp**, không thay
  bằng `now()`: một cái tên nói sai thời điểm tệ hơn một cái tên thiếu.

Đổi chữ ký từ `(run_id: str)` sang `(run: Any)`; sửa call site ở
[routers/decisions.py:955](../../../../apps/api/planbench_api/routers/decisions.py#L955).

**Test:** đổi `test_the_filename_names_the_run` thành
`test_the_filename_names_project_comparison_and_when`; thêm ca 3
candidate, 0 candidate, `created_at` hỏng, `stack_label` có ký tự lạ, và
gọi hai lần ra cùng tên.

**Rủi ro:** thấp. Frontend lấy tên từ `Content-Disposition`
([reports.ts:53](../../../../apps/web/src/lib/reports.ts#L53)); fallback chỉ
dùng khi header vắng.

---

### P2 · Success state của Export

**File:** `apps/web/src/app/decisions/[id]/page.tsx` (`ExportReport`),
`lib/i18n/locales/{en,vi}.json`, `app/globals.css`

`downloadReport` **đã trả filename** và `ExportReport` đang vứt đi
([page.tsx:1293](../../../../apps/web/src/app/decisions/[id]/page.tsx#L1293)).

```tsx
const [saved, setSaved] = useState<{ format: "md" | "xlsx"; filename: string } | null>(null);
```

- Thành công → hiện `t("decisions.export.saved", { filename })`, dùng lại
  đúng câu chữ của `charts.exportSaved` đã có.
- "Tải lại" = bấm lại chính nút đó. Không thêm nút thứ tư.
- Lượt mới → `setSaved(null)` cùng `setFailed(null)`.
- Nhãn: `decisions.export.excel` → `Export Excel` / `Xuất Excel`.

Khoá mới: `decisions.export.saved`, `decisions.export.retry`.
CSS: `.decision-export__saved` cạnh `.decision-export`
([globals.css:4138](../../../../apps/web/src/app/globals.css#L4138)), **dùng
token spacing/màu có sẵn** — commit `77a90fe` vừa đưa shell lên thang
spacing, đừng thêm giá trị lẻ.

**Test:** thành công hiện filename · lỗi hiện lỗi và **không** hiện
filename · lượt mới xoá dòng cũ.

---

### P3 · Tầng text song ngữ

**File:** `decision_export.py`, `decision_markdown.py`, `decision_xlsx.py`

Làm **trước** các sheet mới, để P5/P6/P7 sinh ra đã song ngữ sẵn thay vì
viết tiếng Anh rồi retrofit.

- Một bảng `_TEXT: dict[str, dict[Locale, str]]`, `Locale = Literal["en", "vi"]`.
- `locale: Locale = "en"` thành tham số của `render_decision_markdown`,
  `render_decision_xlsx`, và các hàm `*_rows` sinh nhãn.
- Chuyển hết chuỗi hiện có vào bảng, **bản `en` chép nguyên văn**, không
  sửa một dấu phẩy. Rồi viết bản `vi`.
- Tiền lệ tiếng Việt trong API đã có:
  [gates.py:100](../../../../packages/decision/planbench_decision/gates.py#L100)
  và `early_stop.py` đều mang chuỗi tiếng Việt.

Khối lượng dịch thật: ~30 nhãn hàng, 7 tên sheet, ~10 caveat dài, các
tiêu đề mục Markdown. Caveat là phần tốn công nhất và **không được rút
gọn khi dịch** — chúng là điều kiện đọc số, không phải trang trí.

**Test:** golden `en` từ P0 vẫn xanh · gọi không locale bằng đúng byte
gọi `locale="en"` · mọi key đủ cả hai ngôn ngữ · tên sheet ở cả hai
ngôn ngữ đều hợp lệ Excel (≤ 31 ký tự, không ký tự cấm).

---

### P4 · Sheet `Summary`

**File:** `decision_export.py` (thêm `summary_rows`), `decision_xlsx.py`

`summary_rows(run, report, locale)` gom từ `provenance_rows` +
`card_rows` + `decision_evidence_rows`. **Không tự đọc lại report** — nếu
không sẽ là đường thứ hai tới cùng dữ liệu.

Sheet đứng **đầu** workbook. Nội dung theo bảng C1 trong notes. Ba ô số
theo QĐ-1: `decision_utility` (`0.0000`), `ci_low`, `ci_high`.

Run không có card: sheet vẫn tồn tại, phần recommendation thay bằng
`No Decision Card` + `no_card_reason()` — cùng cách `Decision Card` đang
làm.

**Test:** `Summary` là sheet đầu · đủ 7 mục · run không card vẫn có
`Summary` và nói rõ lý do · `decision_utility` là **số**, không phải chuỗi.

---

### P5 · Hạ tầng số + `number_format`

**File:** `decision_export.py`, `decision_xlsx.py`

Phase rủi ro nhất. **Commit riêng, không trộn.**

```python
@dataclass(frozen=True)
class Quantity:
    """Một đại lượng: giá trị thô, cách Excel in, cách kiểm chứng."""
    value: float | None
    excel_format: str          # '0.00" ms"'
    def text(self) -> str: ... # bản chữ, để test đối chiếu
```

Bảng format là **một** hằng số, dùng chung cho ba sheet mới. Helper:

```python
def write_number(target, row, column, q: Quantity) -> None:
    """Ô rỗng thật khi None — không phải chữ, không phải 0."""
```

Bất biến bắt buộc: **`value is None` thì ô để trống**, và người gọi nói
"chưa đo" ở một ô chữ khác. Không bao giờ ghi `0`; không ghi chuỗi
`"not measured"` vào ô số — cột đó phải sort và sum được.

**Test:** với mọi `Quantity`, `q.text()` khớp cách `candidateMetrics.ts`
in đại lượng cùng loại (bảng đối chiếu cứng trong test) · `None` sinh ô
`value is None` · mọi `excel_format` được openpyxl chấp nhận.

**Rủi ro và cách chặn:** hai test đồng-nhất `.md`↔`.xlsx` **không được
đỏ**. Chúng soi sheet cũ mà phase này không chạm. Đỏ nghĩa là đã lỡ đụng
— dừng, đừng sửa test cho qua. Golden `en` cũng phải xanh.

---

### P6 · Sheet `Detailed Comparison`, bỏ `Outcome by candidate`

**File:** `decision_export.py`, `decision_xlsx.py`, `tests/api/test_decision_xlsx.py`

```python
COMPARISON_METRICS: tuple[MetricSpec, ...]
# key · unit · delta_unit · direction · đường đọc giá trị
# · đường đọc limit · khoá note trong _TEXT
```

Mười dòng theo §4.2 của notes. Giá trị đọc **từ gate payload** ở đâu gate
đã sinh ra nó (G1 `no_path_rate`, G2 `observed` + `upper_bound_95`, G5
`memory_estimate_mb`) — không tính lại. Đúng kỷ luật mà
[candidateMetrics.ts](../../../../apps/web/src/lib/candidateMetrics.ts) đã ghi
trong docstring của nó.

`comparison_rows(report, locale)` trả mỗi metric một dòng: giá trị từng
candidate + delta + winner + limit + weight + note.

Quy tắc winner sao nguyên: `TIE_TOLERANCE = 1e-3` **nhân scale của
dòng** · `direction: "none"` không có winner · dưới hai giá trị thì không
so · mọi bên bằng nhau thì không ai thắng. **"Không dẫn đầu" khác
"thua"** — quyết định P8 tô ô nào.

Xoá `OUTCOME_COLUMNS` / `outcome_rows` và sheet `Outcome by candidate`.
Đổi `test_the_outcome_table_carries_what_the_page_compares_on` thành
`test_the_comparison_sheet_carries_what_the_page_compares_on`. Giữ caveat
`Eligible to recommend`, chuyển sang `Objective Breakdown`.

Note lấy **ý** từ `decisions.compare.why.*`, viết vào `_TEXT` cả `en` và
`vi`. Không import runtime từ locale JSON của web.

**Test parity với TS (QĐ-2):** đọc `candidateMetrics.ts`, trích danh sách
key trong `comparisonRows()`, khẳng định trùng `COMPARISON_METRICS` về
key, thứ tự, direction, unit, deltaUnit, và giá trị `TIE_TOLERANCE`.

**Test khác:** đúng 10 dòng đúng thứ tự · header là `stack_label` thật ·
Replans `no direction` · tie · chỉ một bên đo được · `Limit` khớp gate ·
`Delta unit` là `pp` ở ba dòng phần trăm · 3 candidate thì không có cột
delta và winner là tập · run không card vẫn đầy đủ sheet này.

---

### P7 · Sheet `Objective Breakdown`

**File:** `decision_export.py`, `decision_xlsx.py`

```
Objective | Weight | <stack A> | <stack B> | … | Delta | Contribution A | …
```

Dòng: U_R, U_S, U_E, U_C, bốn dòng con β của U_C, dòng tổng
**Decision utility**. `Contribution = Weight × U`, `number_format 0.0000`.

```python
label = (getattr(run, "manifest", None) or {}).get("preference_profile")
```

| Trường hợp | Xử lý |
|---|---|
| Khớp `PREFERENCE_PROFILES` | tra ra `w_r/w_s/w_e/w_c` + `beta` |
| Hậu tố `(perturbed)` | weight rỗng + note "weights perturbed for the HĐ-11.5 sweep and not recorded". **Không đoán.** |
| `manifest` là `None` | run không card — **bỏ hẳn sheet này** |
| Tên lạ (profile bị xoá sau này) | weight rỗng + note nêu tên đó. Không nổ. |

Import `PREFERENCE_PROFILES` từ `planbench_decision` **trong hàm**, theo
đúng cách `render_decision_xlsx` đang import `openpyxl`.

β3 (CPU time) và β4 (engineering cost): **trọng số có, đầu vào không có
trong report.** Hiện đúng trọng số, hai ô giá trị rỗng, note
"input not recorded in report". Nói đúng cả hai vế.

Fake `Run` ở [test_decision_xlsx.py:27](../../../../tests/api/test_decision_xlsx.py#L27)
**chưa có `manifest`** — thêm vào, và đọc bằng `getattr` để một run cũ
dựng trước khi cột này tồn tại không làm nổ export.

**Test:** `SUM(Contribution) == decision_utility` khớp 6 chữ số thập phân
· trọng số khớp `preference_profile` của chính run đó · hai run khác
profile ra hai bộ trọng số khác nhau · run perturbed để rỗng và không
đoán · run không card thì không có sheet · β3/β4 có trọng số nhưng ô giá
trị rỗng.

Test đầu là test đáng giá nhất cả gói: bắt cùng lúc bốn thứ — số phải là
số thật, trọng số đúng profile, ánh xạ objective đúng, và không có đường
chấm điểm thứ hai lẻn vào.

---

### P8 · Conditional formatting

**File:** `decision_xlsx.py`

Phụ thuộc P5 (rule chấm trên số, ô chuỗi không bắt) và P6/P7 (tô lên
chính hai sheet đó).

- Ô của candidate **dẫn đầu** → nền xanh nhạt
- Ô của candidate **trail** → nền đỏ nhạt
- **Không tô:** ô rỗng · dòng `tie` · dòng `no direction` · dòng chỉ một
  bên đo được

Cách làm: **không** dùng `CellIsRule` theo ngưỡng cho winner. Winner đã
tính sẵn ở Python bằng `leaders()`; dùng `PatternFill` tĩnh đúng những ô
đó. Ngưỡng động sẽ tô theo một quy tắc thứ hai, tự do lệch khỏi cột
`Winner` ngay bên cạnh — hai phán quyết mâu thuẫn trên một dòng.

Cột `Limit`: **dùng** `CellIsRule` tô cam nhạt ô **vượt limit**. Đây là
ngưỡng deployment khai, không phải quy tắc tự chế, nên động là đúng.

Màu lấy từ token của `globals.css`, không tự chọn hex. Thêm `▲`/`▼` ở
cột `Winner` để in đen trắng vẫn phân biệt được.

**Test:** dòng Replans không fill · dòng tie không fill · ô rỗng không
fill · ô trail có fill · số vượt limit có fill cảnh báo.

---

### P9 · Tham số `?locale=` trên route + nối frontend

**File:** `routers/decisions.py`, `apps/web/src/lib/reports.ts`,
`page.tsx`

- Thêm `locale: Literal["en","vi"] = "en"` làm query param cho **cả hai**
  route `report.md` và `report.xlsx`. Mặc định `en` — client cũ không
  đổi hành vi.
- Giá trị lạ → 422 của FastAPI, không tự lùi về `en` lặng lẽ.
- `downloadDecisionReport` / `downloadDecisionWorkbook` nhận thêm locale;
  `ExportReport` truyền locale đang chọn từ `useTranslation`.
- Tên file **không** đổi theo locale (QĐ-4).

**Test:** `?locale=vi` trả nội dung tiếng Việt · không truyền locale trả
đúng byte như `?locale=en` · `?locale=fr` trả 422 · frontend gửi đúng
locale đang chọn.

---

## 3. Phase — Share report

### P10 · Modal Share, chế độ "Open email client"

**File mới:** `apps/web/src/components/ShareReportDialog.tsx`,
`components/__tests__/share-report-dialog.test.tsx`
**Sửa:** `page.tsx` (`ExportReport`), `globals.css`, hai file locale

**Dùng lại pattern modal đã có**, không phát minh mới. Mẫu:
[SendForReview.tsx](../../../../apps/web/src/components/SendForReview.tsx) —
`.modal-backdrop` + `.modal`, `role="dialog"`, `aria-modal="true"`,
`aria-labelledby`, Escape và click nền cùng đóng, `.field`, `.error-box`,
`.primary`.

Cấu trúc theo wireframe §B2 của notes. Điểm cần chốt khi code:

- **Chip input cho To/CC.** Tách chip ở Enter, dấu phẩy, dấu cách, và khi
  blur. Dán chuỗi nhiều địa chỉ thì tách hết một lần.
- **Validation:** regex `\S+@\S+\.\S+`, không cố theo RFC 5322 đầy đủ.
  Chip sai → đỏ + `aria-invalid`, chặn gửi. Trùng giữa To và CC thì tự
  bỏ, không báo lỗi.
- **Prefill:** subject
  `"Decision report — {deployment} — {recommended} recommended"`, message
  bốn dòng: run id, thời điểm, recommended + utility, ΔU + CI. Run không
  card thì message nói run không sinh khuyến nghị và gate table là kết
  quả. **Sửa được hết.**
- **Đính kèm:** checkbox Excel hiện tên file (dùng chung hàm P1) và dung
  lượng — lấy qua `HEAD /decisions/{id}/report.xlsx` (§5 Q2).
- **Link report:** checkbox **disabled**, tooltip nói chưa bật chia sẻ.
  Không bấm được rồi mới lỗi.
- **Không nút nào ghi "Send"/"Gửi" trơn.** Nút chính:
  `Open email client` / `Mở ứng dụng email`. Banner `ShareModeNotice` cố
  định phía trên nút, nói rõ chưa nối provider và file phải đính kèm tay.
- Bấm nút → dựng `mailto:` với To/CC/Subject/Body đã encode, gọi
  `window.location.href`. Modal chuyển sang panel "Đã mở ứng dụng email"
  + nút `Tải file Excel` (gọi `downloadDecisionWorkbook`) + nút Đóng.
- **`mailto:` giới hạn ~2000 ký tự** ở một số client. Body vượt ngưỡng
  thì cắt, thêm dòng nói đã cắt, kèm nút `Sao chép toàn bộ nội dung`.
  Cắt lặng lẽ là mất chữ mà không ai biết.

**Test:** mở modal không đổi URL · Escape và click nền đóng · focus vào
To khi mở · email sai bị chặn · To rỗng thì nút disabled · hiện tên file
và dung lượng · checkbox link disabled kèm lý do · bấm nút dựng đúng
`mailto:` · body dài bị cắt có cảnh báo · panel sau khi mở client có nút
tải file · **không có chuỗi "sent"/"đã gửi" nào trong component**.

Test cuối viết dạng quét source như
[decisions-page.test.tsx:106](../../../../apps/web/src/app/__tests__/decisions-page.test.tsx#L106).
Ràng buộc trung thực phải khoá bằng test, không bằng lời hứa.

---

## 4. Thứ tự, commit, kiểm giữa các bước

| # | Phase | Phụ thuộc | Commit riêng |
|---|---|---|---|
| 1 | **P0 golden snapshot** | — | có, làm đầu tiên |
| 2 | P1 tên file | P0 | có |
| 3 | P2 success state | — | có |
| 4 | P3 tầng text song ngữ | P0 | có |
| 5 | P4 sheet Summary | P3 | có |
| 6 | **P5 hạ tầng số** | P4 | **bắt buộc riêng** |
| 7 | P6 Detailed Comparison | P5 | có |
| 8 | P7 Objective Breakdown | P5 | có |
| 9 | P8 conditional formatting | P6, P7 | có |
| 10 | P9 route `?locale=` + frontend | P3, P6, P7 | có |
| 11 | P10 Share modal | P1 | có |

P2 và P10 là frontend, độc lập với chuỗi backend — chạy song song được.
P10 cần P1 xong để lấy đúng tên file hiển thị trên modal.

P8 xuống sau P6/P7 vì nó tô lên chính hai sheet đó. P9 xuống gần cuối vì
nó cần toàn bộ chuỗi đã vào `_TEXT`.

**Sau mỗi phase backend:** `pytest tests/api/test_decision_xlsx.py
tests/api/test_decision_markdown.py`. Golden `en` phải xanh. Không chạy
full suite — theo lệ đã chốt.

**Sau mỗi phase frontend:** chỉ chạy đúng file test vừa đụng.

Commit theo `TongDuyAn - <một dòng tiếng Anh>`. **Không tự commit** — làm
xong dừng và báo cáo, An tự commit. Không tự restart server.

---

## 5. Điểm mở

| # | Câu hỏi | Trạng thái |
|---|---|---|
| Q1 | Bỏ hẳn `Outcome by candidate`? | ✅ **Chốt: bỏ hẳn.** Vào QĐ-3 và P6. |
| Q4 | Có làm locale cho export? | ✅ **Chốt: làm, cả hai định dạng.** Vào QĐ-4, P0, P3, P9. |
| Q2 | Dung lượng file đính kèm ở modal lấy sao? | Khuyến nghị: thêm `HEAD /decisions/{id}/report.xlsx` trả `Content-Length`. Rẻ và đúng. Cách khác — tải sẵn cả file chỉ để đo — là tải hai lần. |
| Q3 | MVP: `Open email client` hay `Demo send`? | Khuyến nghị `Open email client`, đã viết vào P10. Dùng được thật, không giả vờ gì. |
| Q5 | Thiết kế sẵn hợp đồng `POST /share`? | Khuyến nghị: chỉ viết schema vào notes (đã có §C3), **không** dựng endpoint. Endpoint chưa gọi được mà đã tồn tại sẽ có người gọi. |

---

## 6. Rủi ro

| Rủi ro | Chặn bằng |
|---|---|
| Markdown `en` đổi output ngoài ý muốn | Golden snapshot P0, xanh sau mỗi phase |
| Bản `vi` thiếu key, lặng lẽ rơi về `en` | Test quét đủ cặp `en`+`vi`, không có fallback |
| Tên sheet tiếng Việt vượt 31 ký tự | Test tên sheet ở **cả hai** ngôn ngữ |
| Hai test đồng-nhất `.md`↔`.xlsx` đỏ ở P5 | Là **tín hiệu đúng** — đã lỡ đụng sheet cũ. Dừng, không sửa test cho qua. |
| Bảng metric Python trôi khỏi TS | Test parity QĐ-2 |
| Trọng số in ra không phải của run đó | Test "hai run khác profile ra hai bộ trọng số khác nhau" |
| Ô chưa đo bị tô đỏ như "thua" | Test riêng ở P8; quy tắc "không dẫn đầu ≠ thua" |
| Modal Share sinh false success | Test quét source cấm chuỗi "sent"/"đã gửi" |
| Tên file quá dài trên Windows | Cắt thân 120 ký tự ở P1 |
| Run cũ không có `manifest` làm nổ export | `getattr(run, "manifest", None)`, có test |
| Caveat bị rút gọn khi dịch sang tiếng Việt | Review riêng phần caveat ở P3 — chúng là điều kiện đọc số, không phải trang trí |

---

## 7. Việc còn nợ, ghi lại để không mất

`path_efficiency`, `time_efficiency`, `near_miss_rate`,
`cpu_time_per_mission_s`, `tuning_wall_clock_h` là **đầu vào trực tiếp**
của U_S, U_E, U_C nhưng `selection.py` không viết chúng vào report ở bất
kỳ cấp nào.

Hệ quả sau khi plan này xong: `Objective Breakdown` sẽ hiện `U_E = 0.62`
với **không một số đo nào giải thích 0.62 từ đâu ra**. Hai trong bốn trục
quyết định không truy ngược được.

Lỗ hổng ở `selection.py`, không ở export, và lớn hơn mọi thứ trong plan
này. Sửa ở đó thì `Objective Breakdown` tự đầy đủ mà không phải đụng lại.
