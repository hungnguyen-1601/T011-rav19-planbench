# Báo cáo — Đợt 2.1: P05 Tập held-out và chênh lệch tổng quát hóa

> **Ngày:** 2026-08-06
> **Plan nguồn:** `docs/antongduy/plans/2026-08-05/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`, mục **2.1**
> **Nhánh:** `tongduyan`
> **Tiền đề:** Đợt 1 (P02 + P04) đã xong cùng ngày — xem
> `tongduyan_dot-1-1-p02-can-bang-thong-tin.md` và
> `tongduyan_dot-1-2-p04-quy-trinh-thong-ke.md`.
> **Phạm vi:** chỉ 2.1. Mục 2.2 (P03 hiệu chuẩn độ khó) và 2.3 (Scenario
> Editor) **chưa** làm trong đợt này.

---

## 1. Vấn đề đang giải

Trước đợt này, cả 10 scenario đều được dùng như nhau. Không có gì phân
biệt "scenario mà thuật toán được phát triển trên đó" với "scenario giữ
riêng để kiểm tra". Hệ quả: mọi con số trong hệ thống đều là số **trên
tập đã tinh chỉnh**, và không có cách nào trả lời câu hỏi mà một
benchmark phải trả lời được — thuật toán này tốt, hay chỉ là đã được
chỉnh cho đúng mấy scenario này?

P05 thêm đúng một thứ: **một tuyên bố có thể kiểm chứng về việc scenario
nào được giữ riêng**, kèm cách đo chênh lệch giữa hai nhóm, và một sổ
ghi mỗi lần tập held-out bị mở ra xem.

---

## 2. Quyết định lớn: split **không** nằm trong `Scenario`

Đúng như plan chốt, và đây là điểm mà mọi thứ còn lại phụ thuộc vào.

`conditions_checksum` băm scenario. Nếu `split` là một field của
`Scenario` thì phân loại lại `intersection` từ dev sang holdout sẽ đổi
checksum của **mọi benchmark từng chạy trên nó** — hai report được tạo
dưới cùng một điều kiện vật lý sẽ ngừng so sánh được với nhau chỉ vì có
người sửa một tài liệu chính sách. Một quyết định về quy trình đánh giá
không được phép làm mất hiệu lực dữ liệu đã đo.

Nên split nằm ở file riêng:
`packages/benchmark/planbench_benchmark/scenario_protocol.json`, có
version, validate nghiêm ngặt lúc load (`extra="forbid"`: gõ sai
`splits` thay vì `split` là lỗi, không phải một scenario âm thầm thành
`unassigned`).

Ba quy tắc kèm theo:

1. **Report chụp lại (snapshot) split lúc chạy**, không tra lại lúc đọc.
   Phân loại lại scenario tháng sau mô tả benchmark tương lai, không mô
   tả benchmark quá khứ.
2. **Chưa phân loại là `unassigned`, không phải `dev`.** Mặc định vào
   dev là cách tập held-out lặng lẽ phình ra mỗi lần có người thêm
   scenario mới.
3. **Không có endpoint ghi.** Chuyển split phải sửa file + review +
   deploy. Không ai được đổi phân loại sau khi đã nhìn thấy kết quả.

---

## 3. Tập holdout đã chốt

| Scenario | Split | Lý do giữ riêng (ghi trong file) |
|---|---|---|
| `bidirectional_corridor` | holdout | Xe đi ngược chiều trong hành lang hẹp: đòi hỏi **nhường đường**, hành vi không scenario dev nào thưởng |
| `intersection` | holdout | Giao cắt vuông góc tại ngã tư, bố cục không giống scenario dev nào |
| `dynamic_warehouse` | holdout | Nhiều vật cản **khác mô hình chuyển động** cùng lúc, gồm cả random walk |
| 7 scenario còn lại | dev | |

Lý do là bắt buộc, và có test ép điều đó: `test_held_out_scenarios_state_why`.
Một tập held-out không nêu lý do thì trên thực tế chỉ là "mấy cái khó
nhất" — mà đó lại đúng là điều plan cấm.

Giới hạn thành thật: cả ba cũng nằm cuối thang độ khó. Xem mục 7.

---

## 4. Đã làm gì

### 4.1. `scenario_protocol.py` + `scenario_protocol.json` (mới)

`ScenarioSplit = Literal["dev", "holdout", "unassigned"]`,
`scenario_protocol_metadata(name)` luôn trả lời được (scenario lạ →
`unassigned` chứ không raise, vì người gọi thường là một benchmark sắp
chạy scenario vừa được tạo), `scenarios_in_split()`, `protocol_version()`.
File load một lần, cache, và hỏng thì **ném lỗi** — một protocol parse
dở sẽ hạ cấp scenario holdout xuống unassigned mà không ai biết.

### 4.2. `BenchmarkReport` — 3 trường mới, không xóa trường nào

```
protocol_version: str | None      # None trên report trước P05
scenario_split: "dev"|"holdout"|"unassigned"   # mặc định unassigned
generalization_gap: dict[str, float] | None    # luôn None hiện nay
```

`generalization_gap` luôn `None` vì **một benchmark chạy đúng một
scenario**, nên toàn bộ report thuộc trọn một split và không có gì để
trừ. Trường có mặt để benchmark nhiều scenario sau này không phải phá
schema; chênh lệch thật được tính giữa các report.

### 4.3. `generalization.py` (mới) — chênh lệch **giữa** các report

Gom report theo thuật toán, chia hai phía theo split **đã ghi lúc
chạy**, rồi trừ. Bốn quyết định thiết kế đáng ghi lại:

- **Scenario có trọng số bằng nhau.** Trung bình trong từng scenario
  trước, rồi mới trung bình qua các scenario — chạy `doorway` 10 lần
  không được làm phía dev chủ yếu là `doorway`.
- **`unassigned` bị loại và đếm**, không gộp vào dev. Số bị loại được
  báo, vì nó thường là lời giải thích cho một bảng trống.
- **Thiếu một phía thì `gap = None`.** Không phải 0, không phải "không
  có chênh lệch".
- **`GAP_METRICS` khai báo `higher_is_better`.** Chênh lệch luôn là
  `dev − holdout`; dấu `+` là tốt hay xấu do metric quyết định, và UI
  đọc cờ đó chứ không tự đoán.

Ba metric: success rate, trung vị thời gian di chuyển, trung vị hiệu
quả đường đi. Dùng trung vị chứ không dùng trung bình (P04) — một
episode chôn chân sẽ dịch chênh lệch nhiều hơn mọi khác biệt hành vi
thật.

### 4.4. Nhật ký dùng holdout

`HoldoutUse` ghi mỗi benchmark từng chạy scenario holdout: id, tên,
scenario, số seed, thời điểm kết thúc. Tầng API cấp id và thời gian
(package benchmark không biết gì về benchmark đã lưu). Chạy holdout
cũng được log ở `services.run`.

Tập held-out mất giá trị **vì bị xem nhiều lần**, và sự bào mòn đó vô
hình trừ khi có ai ghi lại. Hệ thống không chặn — một tập held-out sinh
ra để được dùng — nhưng làm cho câu "chúng tôi chỉ kiểm một lần" trở
thành một câu **kiểm chứng được**.

### 4.5. API

| Endpoint | Nội dung |
|---|---|
| `GET /scenario-protocol` | Phân loại của scenario; `?scenario_name=` tra một cái |
| `GET /generalization` | Chênh lệch theo từng stack + nhật ký holdout |
| `GET /scenario-library` | mỗi entry thêm `split`, `protocol_version`, `split_notes` |

`accepted_only` mặc định `true`, giống leaderboard: một tuyên bố về
tổng quát hóa dựng từ run chưa review thì cũng là tuyên bố chưa ai
kiểm. Lọc theo `algorithm` **không** lọc nhật ký holdout — lần chạy đó
đã xảy ra, bất kể người đọc đang xem stack nào.

### 4.6. Frontend

- `SplitBadge` dùng chung: holdout tô kiểu cảnh báo (không phải nhãn
  trung tính — nó là một **quy tắc về việc được làm gì** với con số bên
  cạnh), `unassigned` ghi rõ chữ, không bao giờ để ô trống.
- **Trang library**: cột nhóm đánh giá, tooltip là lý do giữ riêng.
- **Trang tạo benchmark**: chọn scenario holdout thì hiện cảnh báo
  **trước khi tạo** — chi phí của việc xem tập held-out phải trả ngay
  lúc nhìn thấy kết quả. Không disable nút.
- **Trang chi tiết benchmark**: split đã snapshot + protocol version,
  đặt cạnh conditions checksum vì cùng loại sự thật ("kết quả này được
  so với cái gì"); banner riêng cho holdout và cho unassigned.
- **Trang leaderboard**: bảng chênh lệch dev/holdout, thiếu một phía in
  "chưa tính được" chứ không in 0, kèm cảnh báo từng stack và số lần đã
  dùng holdout. Biểu đồ thuộc F09 (Đợt 3); cái phải có trước là một
  chỗ mà **một phía thiếu hiện ra đúng như thiếu**.

---

## 5. Test

**`tests/test_scenario_protocol.py` — 34 test.** Hai test quan trọng
nhất nằm đầu file:

- `test_reclassifying_a_scenario_changes_no_checksum` — chuyển `doorway`
  dev → holdout qua một file protocol tạm, rồi khẳng định
  `_scenario_checksum` **và** `conditions_checksum` không đổi. Đây là
  tính chất mà cả thiết kế tồn tại để bảo đảm.
- `test_reclassification_applies_to_new_runs_only` — report cũ giữ
  nguyên split nó được tạo dưới đó.

Còn lại: file protocol (đủ 10 scenario, dev/holdout không giao, holdout
phải có lý do), validate (sai chính tả split, key lạ, thiếu version,
version rỗng — tất cả phải **lỗi**, không được rơi xuống unassigned),
snapshot (scenario tự tạo chạy ra `unassigned`; report thiếu trường mới
vẫn deserialize), và chênh lệch (trọng số scenario bằng nhau, lặp cùng
scenario được trung bình trước, metric thiếu một phía bị bỏ và ghi rõ,
coverage lệch bị cảnh báo, protocol lệch version bị cảnh báo).

**`tests/api/test_api_generalization.py` — 13 test**, chạy benchmark
thật qua API: report mang split, scenario tự tạo ra `unassigned`, run
chưa accept bị loại mặc định, `unassigned` bị loại và đếm, lọc theo
thuật toán vẫn giữ nhật ký holdout.

**`apps/web/src/app/__tests__/scenario-split.test.tsx` — 32 test**:
cảnh báo holdout hiện trước khi tạo và **không** disable nút, unassigned
được gắn nhãn, gap một phía in placeholder, UI đọc `higher_is_better`
từ backend, i18n đủ hai ngôn ngữ và bản tiếng Việt không phải bản tiếng
Anh.

**Kết quả chạy:**

```
pytest (toàn bộ)                        1265 passed, 4 skipped (8:14)
  tests/test_scenario_protocol.py       34 passed
  tests/api/test_api_generalization.py  13 passed
ruff check .                            All checks passed
ruff format --check                     219 files already formatted
npm run typecheck (apps/web)            sạch
npm test (apps/web)                     314 passed / 1 fail có sẵn
```

Baseline sau Đợt 1.2 là 1218 passed; +47 test backend, +32 test frontend.

Hai fail frontend **có sẵn từ trước và không liên quan** (đã nêu ở hai
báo cáo trước): `dashboard-page.test.tsx` so đường dẫn kiểu POSIX trên
Windows, `assistant-page.test.tsx` đọc `src/app/models/page.tsx` chưa
tồn tại.

---

## 6. Kiểm chứng end-to-end

Chạy thật `astar+dwa` và `rrtstar+dwa`, 3 seed, trên 2 scenario dev
(`doorway`, `crossing_obstacle`) và 1 scenario holdout (`intersection`):

```
doorway            split=dev      protocol=1.0.0  gap_field=None
   astar+dwa       success=1.000  median_travel=9.50
   rrtstar+dwa     success=1.000  median_travel=9.85
crossing_obstacle  split=dev      protocol=1.0.0  gap_field=None
   astar+dwa       success=0.333  median_travel=12.65
   rrtstar+dwa     success=1.000  median_travel=13.60
intersection       split=holdout  protocol=1.0.0  gap_field=None
   astar+dwa       success=1.000  median_travel=13.40
   rrtstar+dwa     success=1.000  median_travel=14.10
```

Chênh lệch (`dev − holdout`):

```
astar+dwa    dev     success=0.667  median_travel=11.075
             holdout success=1.000  median_travel=13.400
             gap     success=-0.333 median_travel=-2.325
             warn: uneven coverage (2 dev vs 1 holdout)
             warn: too few seeds — gap kế thừa giới hạn đó

rrtstar+dwa  dev     success=1.000  median_travel=11.725
             holdout success=1.000  median_travel=14.100
             gap     success= 0.000 median_travel=-2.375

holdout usage: p05-intersection / intersection / 3 seed
gap reproducible on re-run: True
```

Ba điều đáng đọc kỹ ở đây:

1. **Chênh lệch success rate của `astar+dwa` là âm** — nó làm **tốt
   hơn** trên scenario holdout. Đây là bằng chứng ngược lại điều người
   ta hay giả định (holdout = khó hơn): `crossing_obstacle` (dev) có
   người đi bộ cắt ngang và `astar+dwa` hỏng ở 2/3 seed, trong khi
   `intersection` thì nó qua được cả 3. Đúng như thiết kế mong muốn:
   chênh lệch đo **khác biệt về loại tình huống**, không phải một thứ
   tự độ khó — và dấu của nó không được giả định trước.
2. **Coverage lệch bị nêu ra**, không bị làm ngơ: 2 scenario dev so với
   1 scenario holdout là hai trung bình trên hai lượng bằng chứng khác
   nhau.
3. **Tái lập được**: chạy lại cùng seed cho **cùng** chênh lệch.

`generalization_gap` trên từng report đúng là `None` ở cả ba — mỗi
benchmark thuộc trọn một split, không có gì để trừ.

---

## 7. Definition of Done (plan mục 2.1)

- [x] Không thêm `split` vào `Scenario`.
- [x] Không đổi checksum benchmark cũ (có test đổi split thật rồi so
      checksum).
- [x] Có protocol metadata versioned.
- [x] Có trạng thái `unassigned`, và scenario mới mặc định vào đó.
- [x] UI có cảnh báo holdout — trước khi tạo, và trên trang kết quả.
- [x] Report lưu snapshot split + protocol version.
- [x] Có test backward compatibility (report thiếu trường mới vẫn đọc
      được, ra `unassigned`).
- [x] Scenario Editor không sửa trực tiếp split — không có endpoint ghi
      nào cho split; đổi phân loại phải qua file + review + deploy.

---

## 8. Giới hạn đã ghi vào `KNOWN_LIMITATIONS.md` (mục 112–118)

1. **Tập holdout do người chọn, chưa hiệu chuẩn.** Có lý do viết ra,
   nhưng cả ba cũng nằm cuối thang độ khó — **chưa loại trừ được** khả
   năng chênh lệch phản ánh độ khó thay vì khả năng tổng quát hóa. Chỉ
   P03 tách được hai nguyên nhân này. (Số liệu mục 6 là một chỉ dấu
   ngược thú vị, không phải bằng chứng.)
2. **Chênh lệch là hiệu của hai trung bình, không phải kiểm định** —
   không p-value, không khoảng tin cậy cho chính chênh lệch.
3. **Scenario trọng số bằng nhau**, nên scenario chạy 1 seed có cùng
   tiếng nói với scenario chạy 30 seed.
4. **`generalization_gap` trên report luôn `null`.**
5. **MVP không chặn chạy holdout nhiều lần** — chỉ đếm được, không ngăn
   được.
6. **Không có đường chuyển split trong app** — scenario tạo trong ứng
   dụng đứng ở `unassigned` tới lần release sau.
7. **Chỉ 3 metric được so giữa hai split**; clearance, độ mượt, latency
   chưa có.

---

## 9. File đã đổi

**Mới:**
- `packages/benchmark/planbench_benchmark/scenario_protocol.py`
- `packages/benchmark/planbench_benchmark/scenario_protocol.json`
- `packages/benchmark/planbench_benchmark/generalization.py`
- `apps/api/planbench_api/generalization.py`
- `apps/web/src/components/SplitBadge.tsx`
- `tests/test_scenario_protocol.py`
- `tests/api/test_api_generalization.py`
- `apps/web/src/app/__tests__/scenario-split.test.tsx`

**Sửa:**
- `packages/benchmark/planbench_benchmark/spec.py`, `runner.py`, `__init__.py`
- `apps/api/planbench_api/routers/library.py`, `services.py`
- `apps/web/src/lib/platformTypes.ts`, `benchmarkTypes.ts`
- `apps/web/src/app/library/page.tsx`, `benchmarks/page.tsx`,
  `benchmarks/[id]/page.tsx`, `leaderboard/page.tsx`
- `apps/web/src/lib/i18n/locales/en.json`, `vi.json`
- `docs/API_CONTRACT.md`, `docs/KNOWN_LIMITATIONS.md`

---

## 10. Bước tiếp theo

Còn lại của Đợt 2: **2.2 — P03 hiệu chuẩn độ khó thực nghiệm** (cũng là
thứ duy nhất trả lời được giới hạn số 1 ở trên), rồi **2.3 — Scenario
Editor**.
