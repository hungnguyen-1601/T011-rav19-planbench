# Verify: Export Excel + Share report qua Email

Ngày: 2026-08-22 · Nhánh `tongduyan_4` · Không chạy code, chỉ đọc.

Phạm vi đọc: `apps/api/planbench_api/decision_xlsx.py`,
`decision_export.py`, `routers/decisions.py`,
`apps/web/src/lib/reports.ts`, `apps/web/src/app/decisions/[id]/page.tsx`,
`tests/api/test_decision_xlsx.py`, `packages/decision/planbench_decision/objectives.py`.

---

## Kết luận ngắn

| Chức năng | Trạng thái |
|---|---|
| Export Excel | **Đạt ~65%**. Workbook thật, có test, nhưng sai tên file, thiếu sheet Summary/Detailed Comparison đúng hình, không có number format và conditional formatting, thiếu success state. |
| Share report qua Email | **0%. Không tồn tại.** Không nút, không modal, không endpoint, không provider. |

Grep toàn repo `share|email|mailto|smtp|sendgrid|mailgun` trong
`apps/`: không hit nào là chức năng — toàn văn trong docstring và
`account_service` (email đăng nhập). Backend không có bất kỳ đường gửi
mail nào.

---

## 1. Export Excel — chi tiết từng yêu cầu

### 1.1 Nút — ĐẠT (lệch nhãn nhẹ)

`ExportReport` tại [page.tsx:1281](../../../../../apps/web/src/app/decisions/[id]/page.tsx#L1281),
render tại [page.tsx:157](../../../../../apps/web/src/app/decisions/[id]/page.tsx#L157) —
ngay sau `ConclusionPanel`, tức sát kết quả cuối. Không giấu trong menu
ba chấm. Đúng nguyên tắc UX.

Nhãn hiện tại: `decisions.export.excel = "Excel (.xlsx)"` cạnh
`decisions.export.markdown = "Export Markdown"`. Hai nhãn không song
song về ngữ pháp; yêu cầu ghi rõ "Export Excel"/"Xuất Excel".

**Sửa:** đổi giá trị i18n thành `Export Excel` (en) / `Xuất Excel` (vi).

### 1.2 Tên file — KHÔNG ĐẠT

Hiện: `decision-<run_id>.xlsx`
([decision_xlsx.py:63](../../../../../apps/api/planbench_api/decision_xlsx.py#L63)),
gắn vào `Content-Disposition` tại
[routers/decisions.py:954](../../../../../apps/api/planbench_api/routers/decisions.py#L954).

Yêu cầu: `<project>_<comparison>_<YYYY-MM-DD_HH-mm>.xlsx`.

Thiếu cả ba thành phần. Dữ liệu để dựng tên đều đã có sẵn trong `run`:
`run.task_profile_id` (project), cặp candidate `stack_label` từ
`report["candidates"]` (comparison), `identity.created_at`/`run.created_at`
(timestamp). Không phải thu thập thêm gì.

Có test đang khoá hành vi cũ:
`test_the_filename_names_the_run` — phải sửa test cùng lúc.

### 1.3 Cấu trúc workbook — KHÔNG ĐẠT

Sheet hiện có: `Provenance`, `Sample`, `Gates`, `Outcome by candidate`,
`Decision Card`, `Episodes`, `Human record`.

Không có sheet tên `Summary`, không có sheet tên `Detailed Comparison`.

**Summary — nội dung có đủ nhưng bị chẻ đôi.** Ánh xạ:

| Yêu cầu | Đang nằm ở |
|---|---|
| Thời điểm chạy | `Provenance` → "Run" |
| Dataset/version | `Provenance` → Deployment, Contracts version, Code version, Anchor config |
| Thuật toán/phiên bản | `Outcome by candidate` → Candidate, Config (không có ở Provenance) |
| Overall score | `Decision Card` → "Decision utility" |
| Winner | `Decision Card` → "Recommended" |
| Confidence | `Decision Card` → "ΔU 95% interval", "Effect size" |
| Final recommendation | `Decision Card` → "Recommended" + caveat "Scope" |

Người đọc phải mở 3 sheet để ráp được câu trả lời. Cần một sheet
`Summary` đứng đầu gom lại.

**Detailed Comparison — sai hình bảng, đây là gap lớn nhất.**
`OUTCOME_COLUMNS`
([decision_export.py:353](../../../../../apps/api/planbench_api/decision_export.py#L353))
là bảng **một dòng một candidate**, 18 cột metric nằm ngang.

Yêu cầu là bảng **một dòng một metric**:
`metric | unit | Algorithm A | Algorithm B | delta | winner | weight | note`.

So với hiện trạng:

- `metric`, `Algorithm A`, `Algorithm B` — suy ra được bằng cách xoay bảng hiện có.
- `unit` — **không tồn tại**. Đơn vị đang bị nhét vào chuỗi giá trị (`"7.35 ms"`), không tách cột.
- `delta` — **không tồn tại** ở cấp metric. Chỉ có ΔU tổng ở Decision Card.
- `winner` — **không tồn tại** ở cấp metric. Chỉ có winner tổng.
- `weight` — **không tồn tại dạng cột**. ~~Phải nối dây backend trước.~~
  **Đính chính 2026-08-22:** lấy được ngay, không cần nối dây —
  `run.manifest["preference_profile"]` đã có sẵn, tra ra bộ số qua
  `PREFERENCE_PROFILES`. Nhưng chỉ 3/10 metric thực sự có trọng số.
  Xem [tongduyan_chon-metrics-cho-detailed-comparison.md](tongduyan_chon-metrics-cho-detailed-comparison.md) §3.
- `note` — **không tồn tại** dạng cột. Caveat hiện là dòng rời cuối sheet.

### 1.4 Formatting — ĐẠT MỘT NỬA

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| Header | Đạt | `Font(bold=True)` mọi header |
| Column width | Đạt | `column_dimensions[...].width` mọi sheet |
| Freeze header | Đạt | `freeze_panes = "A2"` ở Gates + `write_table` |
| Metadata rõ ràng | Đạt | Sheet `Provenance` + caveat gắn theo sheet |
| **Number format** | **Không đạt** | Mọi giá trị ghi dạng **string**, cố ý — docstring module nói rõ: *"Values are written as the strings the Markdown export shows, not as raw floats. It costs sorting and summing"*. Excel không sort/sum/chart được. |
| **Conditional formatting** | **Không đạt** | Không có `PatternFill`, `ColorScaleRule`, `CellIsRule` nào trong file. |

Lưu ý quan trọng: number format và conditional formatting **là cùng một
gap**. Conditional formatting của openpyxl chấm trên giá trị số; ô đang
là string thì rule không bắt. Phải sửa cái trước mới làm được cái sau.

Đây là **xung đột thiết kế có chủ ý**, không phải quên. Module chọn
string để `.md` và `.xlsx` không bao giờ in hai con số khác nhau cho
cùng một giá trị, và test `test_every_gate_number_appears_in_both` +
`test_neither_invents_a_number_the_other_lacks` đang khoá đúng ràng
buộc đó. Cách gỡ đúng: ghi **float thật vào ô** + đặt `cell.number_format`
sao cho chuỗi hiển thị khớp y hệt chuỗi Markdown. Giữ được cả hai. Nếu
làm khác, hai test kia sẽ đỏ và đó là tín hiệu đúng, không phải test sai.

### 1.5 Trạng thái UI — THIẾU SUCCESS

| State | Trạng thái |
|---|---|
| exporting | Đạt — `busy === "xlsx"` đổi nhãn thành `decisions.export.busy` |
| error | Đạt — `<span className="error-text">{failed}</span>` |
| **success** | **Không đạt** — không hiện filename, không có nút tải lại |

`downloadReport` **đã return filename**
([reports.ts:66](../../../../../apps/web/src/lib/reports.ts#L66)) nhưng
`ExportReport` vứt giá trị đó đi tại
[page.tsx:1293](../../../../../apps/web/src/app/decisions/[id]/page.tsx#L1293).

Đã có tiền lệ trong repo: `charts.exportSaved = "Saved {filename}"`.
Dùng lại đúng pattern đó. Nút "tải lại" gần như miễn phí — nút Export
vẫn bấm lại được, chỉ cần đổi nhãn khi đã có filename.

### 1.6 Test hiện có

`tests/api/test_decision_xlsx.py` — 18 test, phủ khá tốt: hai export
đồng nhất, null nói "not measured", run không có card vẫn export được,
sheet name hợp lệ Excel, freeze panes, route HTTP, report thiếu field
không crash. Không có test nào cho number format, conditional
formatting, hay tên file theo định dạng yêu cầu — vì các thứ đó chưa
tồn tại.

---

## 2. Share report qua Email — KHÔNG TỒN TẠI

Không có gì để verify. Toàn bộ mục 2 của yêu cầu chưa được bắt đầu:
không nút "Share report", không modal/drawer, không trường To/CC/
Subject/Message, không lựa chọn đính kèm, không validation, không state
nào.

Điểm đáng khen duy nhất trong tình huống này: **không có false success
nào cả**, vì không có gì giả vờ gửi.

---

## A. User flow

### A1. Export Excel

```
Trang Decision detail, cuộn tới cuối
  → thấy ConclusionPanel (kết quả cuối)
  → ngay dưới: [Export Excel] [Export Markdown] [Share report]
  → click [Export Excel]
     → nút đổi thành "Exporting…", disabled, spinner
     → API dựng workbook, trả Content-Disposition
     → trình duyệt lưu file
     → nút trở lại "Export Excel"
     → bên cạnh hiện: "✓ Saved warehouse_a_v2_astar-vs-rrtstar_2026-08-22_14-30.xlsx"
        kèm link nhỏ [Tải lại]
  → lỗi: nút trở lại bình thường, hiện "✗ <message>" + [Thử lại]
```

Một bước. Không wizard.

### A2. Share report

```
Cùng hàng nút → click [Share report]
  → modal mở đè lên trang (không điều hướng)
  → form đã prefill:
       To:      (rỗng, focus ở đây)
       CC:      (ẩn, có link "+ CC")
       Subject: "Decision report — warehouse_a_v2 — astar+dwa recommended"
       Message: 4 dòng tóm tắt, sửa được
       Đính kèm: [x] Excel report (≈ 48 KB)
                 [ ] Link tới report  ← disabled + tooltip nếu chưa có share link
  → click [Open email client]  (MVP mode — xem D5)
     → mở mailto: với To/CC/Subject/Body đã điền
     → modal chuyển sang trạng thái "Đã mở email client"
        + nhắc: "File Excel phải đính kèm thủ công — [Tải file]"
  → hoặc click [Hủy] → modal đóng, form giữ nguyên nếu mở lại trong cùng phiên
```

Hai bước: mở modal, gửi.

---

## B. Wireframe / component specification

### B1. Hàng nút — sửa `ExportReport` hiện có

```
┌─ ConclusionPanel ────────────────────────────────────────────┐
│  Recommended: astar+dwa   ΔU +0.081 [0.032, 0.129]           │
└──────────────────────────────────────────────────────────────┘

  [ Export Excel ]  [ Export Markdown ]  [ ⇗ Share report ]
  ✓ Saved warehouse_a_v2_astar-vs-rrtstar_2026-08-22_14-30.xlsx  · Tải lại
```

- `.decision-export` đã là flex/wrap/gap 8px — giữ nguyên, thêm nút thứ ba.
- Export Excel = primary, Markdown = secondary, Share = secondary có icon.
- Dòng success nằm dưới, không đẩy nút.

### B2. Modal Share

```
┌──────────────────────────────────────────── ✕ ─┐
│  Share report                                   │
│  warehouse_a_v2 · astar+dwa vs rrtstar+dwa      │
│ ─────────────────────────────────────────────── │
│  To *                                           │
│  ┌───────────────────────────────────────────┐  │
│  │ an@vinai.io ⊗   binh@vinai.io ⊗   |       │  │  ← chip input
│  └───────────────────────────────────────────┘  │
│  + CC                                           │
│                                                 │
│  Subject                                        │
│  ┌───────────────────────────────────────────┐  │
│  │ Decision report — warehouse_a_v2 — …      │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  Message                                        │
│  ┌───────────────────────────────────────────┐  │
│  │ Selection run 8f3a completed 2026-08-22.  │  │
│  │ Recommended: astar+dwa (utility 0.78).    │  │  ← 5 dòng, resize dọc
│  │ ΔU +0.081, CI95 [0.032, 0.129].           │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  Đính kèm                                       │
│  [x] Excel report          warehouse_…xlsx 48 KB│
│  [ ] Link tới report       — chưa bật chia sẻ   │  ← disabled + tooltip
│                                                 │
│ ─────────────────────────────────────────────── │
│  ⓘ Chưa nối email provider. Nút dưới mở email   │
│    client của bạn; file phải đính kèm tay.      │
│                                                 │
│              [ Hủy ]   [ Open email client ]    │
└─────────────────────────────────────────────────┘
```

Component mới:

| Component | Vai trò |
|---|---|
| `ShareReportButton` | Nút + quản lý `open` state |
| `ShareReportDialog` | Modal, focus trap, Esc đóng, click nền đóng |
| `EmailChipInput` | To/CC — nhập, validate, chip, xoá; Enter/comma/space tách chip |
| `AttachmentRow` | Checkbox + tên file + dung lượng; disabled có lý do |
| `ShareModeNotice` | Banner nói rõ MVP mode — bắt buộc, xem D5 |

Style: light theme, semi-compact, Inter/Be Vietnam Pro — bám đúng token
đang có trong `globals.css`, không tự chế màu/spacing mới. Modal width
560px, radius và shadow lấy từ token popover có sẵn.

---

## C. Data schema

### C1. Sheet `Summary` (mới, đứng đầu workbook)

Dạng key–value hai cột, gom từ `provenance_rows` + `card_rows` +
`decision_evidence_rows`:

| Row label | Nguồn |
|---|---|
| Run at | `identity.created_at` ?? `run.created_at` |
| Project / deployment | `run.task_profile_id` |
| Experiment scope | `identity.experiment_scope` |
| Dataset version | `identity.anchor_config_version` |
| Contracts version | `run.contracts_version` |
| Code version | `identity.git_sha` |
| Algorithm A | `candidates[0].stack_label` + `local_controller_config` |
| Algorithm B | `candidates[1].stack_label` + `local_controller_config` |
| Episodes compared | `evidence.n_episodes` |
| **Winner** | `card.recommended.stack` |
| **Overall score** | `card.decision_utility` (float, `number_format="0.000"`) |
| **Confidence (ΔU 95%)** | `evidence.ci95` → hai ô số `ci_low`, `ci_high` |
| ΔU mean | `evidence.delta_u_mean` |
| Effect size | `evidence.effect_size` |
| Decision mode | `card.decision_mode` |
| Pareto label | `card.pareto_label` |
| **Final recommendation** | câu ghép: recommended + scope (`scope_of`) |
| Preference profile | `settings.preference_profile` ← **cần nối dây mới** |

### C2. Sheet `Detailed Comparison` (mới)

Bản chốt sau khi khảo sát metric thật của hệ thống. Lý do từng lựa chọn
ở [tongduyan_chon-metrics-cho-detailed-comparison.md](tongduyan_chon-metrics-cho-detailed-comparison.md).

Một dòng một metric, 10 cột:

```
Metric | Unit | <stack A> | <stack B> | Delta | Delta unit | Winner | Limit | Weight | Note
```

| Cột | Kiểu ô | Nguồn |
|---|---|---|
| `Metric` | text | `decisions.compare.<key>` — nhãn đã có sẵn vi + en |
| `Unit` | text | `Format.unit`: `%`, `ms`, `s`, `m`, `MB`, rỗng cho count |
| `<stack A>` / `<stack B>` | **number** + `number_format` | giá trị thô; **header là `stack_label` thật**, không phải chữ "Algorithm A" |
| `Delta` | **number** | B − A trên thang hiển thị, không tự đảo dấu theo hướng tốt |
| `Delta unit` | text | `Format.deltaUnit ?? unit` — cột riêng vì hiệu của hai tỉ lệ là **pp** |
| `Winner` | text | `A` / `B` / `tie` / `no direction` / `not measured` |
| `Limit` | number/rỗng | ngưỡng deployment khai: G3 `threshold`, G1 `threshold`, G4 `threshold_ms`, G5 `available_ram_mb`, G2 = 0 |
| `Weight` | number/rỗng | **chỉ 3/10 dòng có**; ô rỗng bắt buộc kèm lý do ở `Note` |
| `Note` | text | `decisions.compare.why.<key>` — 10 câu đã viết sẵn vi + en |

Mười dòng, đúng bằng `comparisonRows()`:

| # | Metric | Unit | Hướng | Limit | Weight |
|---|---|---|---|---|---|
| 1 | Success rate | % | cao | G3 `threshold` | `w_r` |
| 2 | Collisions observed | count | thấp | 0 | — gate G2 |
| 3 | Collision probability, 95% upper bound | % | thấp | — | — cỡ mẫu |
| 4 | Episodes with no route found | % | thấp | G1 `threshold` | — gate G1 |
| 5 | Worst clearance in the whole run | m | cao | — | — U_S dùng mean |
| 6 | Median episode duration | s | thấp | — | — |
| 7 | Planner latency, pooled p99 | ms | thấp | G4 `threshold_ms` | `w_c × β1` |
| 8 | Memory estimate on the target board | MB | thấp | G5 `available_ram_mb` | `w_c × β2` |
| 9 | Distinct episodes | count | cao | — | — nền bằng chứng |
| 10 | Replans across the run | count | **không** | — | — |

Bằng đúng lưới trên UI là **cố ý**: người xem màn hình và người mở file
phải đang đọc cùng một bài so sánh về cùng một run.

Loại khỏi bảng, có lý do: `peak_search_nodes`/`peak_tree_nodes` (HĐ-6
tách hai cột vì chúng đếm hai thứ khác nhau), mean của
`episode_decision_utility` (là đường chấm điểm thứ hai), G6 (quyết trước
episode 1, không sinh số).

Giá trị chưa đo: ô để **rỗng thật** nhưng cột `Winner` ghi
`not measured` và `Note` nói rõ. Khác cách hiện tại (nhét chữ
"not measured" vào ô giá trị) — vì cột giá trị giờ là số. Bất biến "null
không bao giờ đọc thành 0" được giữ bằng cột chữ, không bằng chuỗi trong
ô số.

### C2b. Sheet `Objective Breakdown` (mới)

```
Objective | Weight | <stack A> | <stack B> | Delta | Contribution A | Contribution B
```

| Dòng | Weight |
|---|---|
| U_R — Reliability | `w_r` |
| U_S — Safety | `w_s` |
| U_E — Efficiency | `w_e` |
| U_C — Cost | `w_c` |
| ├ β1 latency · β2 memory · β3 CPU time · β4 engineering cost | `w_c × βᵢ` |
| **Decision utility** | **1.00** |

`Contribution = Weight × U`. Cộng dọc phải ra đúng `decision_utility`.
β3 và β4 có trọng số thật nhưng **đầu vào không có trong report** — hai ô
giá trị để rỗng, note `"input not recorded in report"`.

Lấy trọng số:

```python
profile_label = (run.manifest or {}).get("preference_profile")
```

| Trường hợp | Xử lý |
|---|---|
| Khớp `PREFERENCE_PROFILES` | Tra ra `w_r/w_s/w_e/w_c` + `beta` |
| Có hậu tố `(perturbed)` | `weights_override` không lưu ở đâu. Weight rỗng + note. **Không đoán.** |
| `manifest is None` | Run không có card — bỏ luôn sheet này, giữ `Detailed Comparison` |

Bắt buộc đọc từ manifest của **chính run đó**, không lấy mặc định
`"kho_ban_dem"`: một card tính dưới `benh_vien_gio_cao_diem` (w_s = 0.50)
mà in trọng số `kho_ban_dem` (w_s = 0.10) thì mọi contribution đều sai,
và sai một cách không nhìn ra được vì tổng vẫn ra số hợp lý.

### C3. Payload email

```jsonc
// POST /api/v1/decisions/{run_id}/share   (giai đoạn có backend)
{
  "to":       ["an@vinai.io", "binh@vinai.io"],   // >= 1, RFC 5322
  "cc":       [],                                  // optional
  "subject":  "Decision report — warehouse_a_v2 — astar+dwa recommended",
  "message":  "…",                                 // plain text, <= 5000 ký tự
  "attach_excel": true,
  "include_link": false,
  "locale":   "vi"                                 // để server dựng nội dung mặc định
}
```

```jsonc
// 202 Accepted
{
  "share_id": "shr_01J…",
  "mode": "sent",                 // "sent" | "queued" | "client_handoff"
  "recipients": 2,
  "attachment": { "filename": "warehouse_a_v2_…xlsx", "bytes": 49152 },
  "link": null
}
```

```jsonc
// 4xx/5xx — dùng đúng error envelope hiện có của API
{ "error": { "code": "SHARE_PROVIDER_UNAVAILABLE", "message": "…", "retryable": true } }
```

**Giai đoạn MVP không có backend**: không gọi endpoint nào. Client dựng
`mailto:` từ chính payload trên và `mode` luôn là `"client_handoff"`.
Không POST, không toast "Đã gửi".

---

## D. Error / empty / loading / success states

### D1. Export Excel

| State | Hiển thị |
|---|---|
| idle | `[Export Excel]` bật |
| loading | `[Exporting…]` disabled + spinner; nút Markdown và Share cũng disabled |
| success | `✓ Saved <filename>` + link `Tải lại`; nút trở về idle |
| error | `✗ <message API trả>` + `[Thử lại]`; 401 đã `clearSession()` sẵn trong `downloadReport` |
| empty | Run không có card **vẫn export được** — đã đúng, giữ. Sheet Summary ghi rõ "No Decision Card" + lý do. |

### D2. Modal Share — validation

| Điều kiện | Xử lý |
|---|---|
| To rỗng | nút gửi disabled, helper text `"Cần ít nhất một người nhận"` |
| Email sai định dạng | chip đỏ, tooltip `"Địa chỉ không hợp lệ"`, không cho gửi |
| Trùng địa chỉ To/CC | tự bỏ trùng, không báo lỗi |
| Subject rỗng | cho phép, prefill lại giá trị mặc định khi blur |
| Message > 5000 ký tự | đếm ký tự đỏ, chặn gửi |
| Không chọn đính kèm nào | cảnh báo vàng `"Email sẽ không kèm file hay link"`, **vẫn cho gửi** |

### D3. Modal Share — loading

Nút gửi → spinner + `"Đang gửi…"`, mọi trường disabled, modal **không**
đóng được (chặn Esc và click nền) để tránh gửi đôi.

### D4. Modal Share — success / error

- Success (có backend): modal chuyển sang panel xác nhận —
  `"✓ Đã gửi tới 2 người"` + danh sách địa chỉ + `[Đóng]`. Tự đóng sau 4 s.
- Error: giữ nguyên form, không xoá gì người dùng đã gõ, banner đỏ
  `"✗ <message>"` + `[Thử lại]`. Retry gọi lại đúng payload cũ.

### D5. MVP mode — điều khoản bắt buộc

Chưa có email provider. Cấm tuyệt đối hiển thị `"Đã gửi"`.

Hai lựa chọn hợp lệ, chọn **một** và nói rõ trên UI:

1. **Open email client** (khuyến nghị) — nút ghi đúng chữ
   `Open email client`, banner giải thích, sau khi mở thì trạng thái là
   `"Đã mở email client — file cần đính kèm thủ công"` kèm nút tải file.
   Trung thực, không cần backend, dùng được thật.
2. **Demo send** — nút ghi `Demo send`, banner ghi
   `"Chế độ demo: không có email nào được gửi"`, kết quả hiện đúng
   payload sẽ gửi. Chỉ dùng khi trình bày.

Không được dùng chữ "Send"/"Gửi" trơn cho tới khi provider nối thật.

---

## E. Acceptance criteria cho QA

### E1. Export Excel

| # | Tiêu chí | Cách kiểm |
|---|---|---|
| E1.1 | Nút ghi "Export Excel" (en) / "Xuất Excel" (vi) | Đổi ngôn ngữ, đọc nhãn |
| E1.2 | Nút nằm trong vùng nhìn thấy ngay dưới kết quả cuối, không trong menu ẩn | Xem trang |
| E1.3 | Tên file khớp `<project>_<comparison>_<YYYY-MM-DD_HH-mm>.xlsx` | Tải, đọc tên; kiểm cả `Content-Disposition` |
| E1.4 | Timestamp trong tên file khớp thời điểm chạy run, không phải thời điểm bấm nút | So với "Run at" trong sheet Summary |
| E1.5 | Workbook mở được bằng Excel và LibreOffice, không cảnh báo repair | Mở thủ công cả hai |
| E1.6 | Có sheet `Summary` và sheet `Detailed Comparison` | Đọc tab |
| E1.7 | Summary có đủ 7 mục: run at, dataset/version, algorithm/version, overall score, winner, confidence, final recommendation | Đối chiếu bảng C1 |
| E1.8 | Detailed Comparison có đủ 10 cột theo đúng thứ tự | Đọc header |
| E1.8a | Có đúng 10 dòng, cùng thứ tự với lưới trên UI | Mở cạnh nhau, so từng dòng |
| E1.8b | Header cột A/B là `stack_label` thật, không phải "Algorithm A/B" | Đọc header |
| E1.8c | Dòng Replans có `Winner = no direction`, không ai được tô màu | Xem dòng 10 |
| E1.8d | Chênh lệch dưới `1e-3 × scale` hiện `tie`, không hiện winner | Tìm run có hai giá trị gần nhau |
| E1.8e | Metric chỉ một bên đo được: `Winner = not measured`, **ô kia không bị tô đỏ** | Tìm run thiếu số |
| E1.8f | Cột `Limit` khớp ngưỡng khai ở G1/G3/G4/G5 | So với task profile |
| E1.8g | Cột `Delta unit` là `pp` ở 3 dòng phần trăm, không phải `%` | Đọc dòng 1, 3, 4 |
| E1.8h | Chỉ 3 dòng có `Weight`; 7 dòng còn lại rỗng **và có lý do ở `Note`** | Đọc cột weight |
| E1.8i | `Weight` khớp `preference_profile` của **chính run đó** | Export hai run khác profile, so |
| E1.8j | Run sweep (`(perturbed)`): weight rỗng + note, **không đoán số** | Export một run sweep |
| E1.8k | **`SUM` cột Contribution = `decision_utility` trên Summary**, khớp 6 chữ số thập phân | Gõ `=SUM()` trong Excel |
| E1.8l | Run không có card: không có sheet `Objective Breakdown`, `Detailed Comparison` vẫn đầy đủ | Chọn run bị chặn gate |
| E1.8m | `Note` hiển thị đúng ngôn ngữ đang chọn | Export ở chế độ vi và en |
| E1.9 | Ô số là **số thật**, không phải text | Click ô, xem `=ISNUMBER()` trả TRUE; thử `SUM` một cột |
| E1.10 | Số hiển thị khớp y hệt giá trị trong bản `.md` cùng run | Xuất cả hai, so từng con số |
| E1.11 | Header đậm, freeze ở dòng 1, mọi sheet | Cuộn xuống, header còn dính |
| E1.12 | Conditional formatting tô được ô tốt/xấu trên cột delta | Nhìn màu; sửa một ô số, màu đổi theo |
| E1.13 | Giá trị chưa đo: ô rỗng + cột note ghi "not measured", **không** hiện 0 | Tìm metric chưa đo |
| E1.14 | Sort cột `delta` trong Excel cho thứ tự số đúng | Sort thử |
| E1.15 | Trong lúc export, nút disabled, không bấm đôi ra hai file | Bấm liên tiếp |
| E1.16 | Export xong hiện filename và cho tải lại | Xem dòng success |
| E1.17 | API lỗi 500 → hiện message lỗi + nút thử lại, không tải file rỗng | Chặn mạng, thử |
| E1.18 | Token hết hạn (401) → về màn đăng nhập, không tải file HTML lỗi | Xoá token, thử |
| E1.19 | Run không có Decision Card vẫn export được, Summary ghi rõ lý do | Chọn run bị chặn gate |
| E1.20 | Tên sheet không chứa `[ ] : * ? / \` và ≤ 31 ký tự | Đã có test, giữ |

### E2. Share report

| # | Tiêu chí | Cách kiểm |
|---|---|---|
| E2.1 | Nút "Share report" nằm cùng hàng với nút Export | Xem trang |
| E2.2 | Click mở modal, **URL không đổi**, trang không cuộn về đầu | Xem thanh địa chỉ |
| E2.3 | Esc và click nền đóng modal (trừ lúc đang gửi) | Thử cả hai |
| E2.4 | Focus vào ô To khi mở; Tab đi đúng thứ tự; focus không thoát khỏi modal | Chỉ dùng bàn phím |
| E2.5 | Subject và Message có prefill và **sửa được** | Gõ đè |
| E2.6 | CC ẩn mặc định, hiện khi bấm "+ CC" | Thử |
| E2.7 | Email sai định dạng bị chặn, chip đỏ, không gửi được | Nhập `abc@`, `a b@c.d` |
| E2.8 | To rỗng → nút gửi disabled | Xoá hết chip |
| E2.9 | Hiện đúng tên file và dung lượng đính kèm | So với file tải thật |
| E2.10 | Nếu chọn "link report" thì phải nói rõ ai xem được | Đọc dòng quyền truy cập |
| E2.11 | Nếu chưa có share link, checkbox link disabled + có lý do, **không phải bấm được rồi lỗi** | Xem tooltip |
| E2.12 | **Không có nút nào ghi "Send"/"Gửi" trơn khi chưa nối provider** | Đọc nhãn |
| E2.13 | MVP: bấm nút mở đúng email client với To/CC/Subject/Body đã điền | Bấm, xem cửa sổ mail |
| E2.14 | MVP: sau khi mở client, **không** hiện "Đã gửi"; có nhắc đính kèm tay + nút tải file | Đọc trạng thái |
| E2.15 | Đang gửi: mọi trường disabled, không đóng được modal, không gửi đôi | Bấm liên tiếp |
| E2.16 | Lỗi: form giữ nguyên nội dung đã gõ, có nút thử lại, retry dùng đúng payload cũ | Chặn mạng, thử lại |
| E2.17 | Success (khi có backend): hiện số người nhận và danh sách địa chỉ | Gửi thật |
| E2.18 | Modal đọc được bằng screen reader: có `role="dialog"`, `aria-modal`, `aria-labelledby` | Kiểm DOM |
| E2.19 | Light theme, Inter/Be Vietnam Pro, spacing khớp token app, không lệch style | So với modal khác trong app |

---

## Thứ tự làm đề xuất

1. **Filename** — rẻ nhất, sai rõ nhất, sửa 1 hàm + 1 test.
2. **Success state của Export** — filename đã có sẵn ở return value, chỉ cần dùng.
3. **Sheet `Summary`** — ráp từ ba hàm `*_rows` đã có, không cần dữ liệu mới.
4. **Số thật + number format** — phải làm trước bước 5; sẽ đụng hai test đồng-nhất, đó là điểm cần cẩn thận nhất trong cả gói.
5. **Conditional formatting** — chỉ khả thi sau bước 4.
6. **Sheet `Detailed Comparison`** — bảng metric (unit, direction, deltaUnit, note) **đã có sẵn** trong `candidateMetrics.ts` và `decisions.compare.*`; việc chính là khai một lần dùng cho cả hai phía thay vì chép sang Python.
7. **Sheet `Objective Breakdown`** — chỗ duy nhất `weight` có nghĩa đầy đủ. Không bị chặn bởi backend.
8. **Share modal** — làm mới hoàn toàn, chạy ở MVP mode "Open email client".

*(Bước 7 trước đây ghi là "nối weights vào report" — đã đính chính, xem §1.3.)*
