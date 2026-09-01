# Báo cáo — Phase 3.3: Objectives + Decision Utility (HĐ-9)

> **Ngày:** 2026-08-10
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **3.3**
> **Nhánh:** `plannerselector_p2`
> **Điều kiện vào:** 3.3 phụ thuộc 3.1 (anchors) ✓
> **Contract:** `2.0.1` → **`2.1.0`** (MINOR, xem mục 3)

---

## 1. Đã làm

| File | Vai |
|---|---|
| `packages/decision/planbench_decision/objectives.py` (mới) | U_R/U_S/U_E/U_C, `decision_utility`, 4 preference profile, `DecisionSettings` |
| `packages/decision/planbench_decision/candidate.py` | thêm `TuningDeclaration` + trường `tuning` (HĐ-1.6 mới) |
| `contracts/CONTRACTS.md` | HĐ-1.6 mới; HĐ-9.1 làm rõ hai mức tổng hợp; §18 |
| `packages/schemas/planbench_schemas/contracts.py` | `CONTRACTS_VERSION = "2.1.0"` |
| `tests/test_objectives.py` (mới) | 35 test |

Hai hàm vào:

```python
episode_objectives(metric, anchors, candidate, settings)  -> ObjectiveBreakdown  # level="episode"
set_objectives(metrics, anchors, candidate, settings)     -> ObjectiveBreakdown  # level="set"
```

## 2. Phát hiện lớn nhất của phase: hai mức tổng hợp **không bằng nhau** ở U_R

Bản 2.0.x nói hai điều không thể cùng đúng:

- HĐ-9.1 chú thích `U_R = u(success)` — *"theo episode: 0 hoặc 1"*;
- HĐ-12 (và ví dụ §6.2 của tài liệu mẹ) in `U_R = 0,34` cho candidate đạt `success_rate = 96,7%`.

Vì `u()` là affine **có clip**, trung bình theo episode của `u(success)` bằng đúng
`success_rate` = **0,967**, còn mức tập cho `u(0,967) = ` **0,34** với ngưỡng 0,95.
Chênh nhau gần ba lần, và cả hai đều là con số của contract.

Không thể chọn một bỏ một:

- **Mức episode là bắt buộc** — HĐ-11.1 nói thẳng `decision_utility` phải tính được
  theo từng episode, nếu không thì không có ΔU ghép cặp. Đó là toàn bộ Phase 3.4.
- **Mức tập là bắt buộc** — 0,34 mới là con số mang ý nghĩa "dôi bao nhiêu so với
  ngưỡng khách hàng khai". In 0,967 lên card thì cột U_R chỉ còn là success_rate viết
  lại, và ràng buộc `success_rate_min` biến mất khỏi điểm số.

Nên hiện thực **cả hai, đặt tên khác nhau, và `level` đi kèm mọi kết quả**. Một điểm
đáng chú ý: hai mức **trùng nhau ở mọi metric không chạm biên clip** — có test khẳng
định U_S mức tập bằng đúng trung bình U_S theo episode tới chữ số cuối. Nghĩa là chênh
lệch không phải hai công thức khác nhau, mà đúng một hiệu ứng clip ở đúng một chỗ.

Hệ quả phải nói rõ trên card (đã ghi vào contract): **`decision_utility` in trên card
không phải trung bình của `decision_utility` theo episode.**

## 3. Contract 2.0.1 → 2.1.0 (MINOR)

**① HĐ-1.6 mới — schema cho khai báo chi phí kỹ thuật.** HĐ-6 từ đầu đã yêu cầu
`tuning_wall_clock_h`, `tuning_trials_used`, `n_tunable_params` "khai lúc đăng ký
candidate, có bằng chứng log", nhưng không có chỗ nào trong schema nhận chúng. Không
có nó thì **β4 = 0,30 của U_C** không tính được (đồng hạng nặng nhất trong U_C) và
tie-break bậc 3 của HĐ-11.3 cũng không hiện thực được ở Phase 3.4.

```yaml
tuning:
  tuning_trials_used: 30
  tuning_wall_clock_h: 24.0
  n_tunable_params: 12
  evidence_log: artifacts/tuning/k2_optuna.log   # bắt buộc
```

Mặc định `null` ⇒ MINOR. **Không vào `candidate_id`** (cùng lý do `resource_profile`:
số giờ bỏ ra để tìm bộ tham số không làm robot chạy khác — bộ tham số tìm được thì có,
và nó đã nằm trong hash qua `params`). Có test khóa điều này.

`evidence_log` bắt buộc vì đây là **con số tự khai duy nhất đi thẳng vào điểm**.

**② HĐ-9.1 làm rõ** — mục 2 ở trên, kèm bảng hai mức và một dòng "vi phạm trông như
thế nào".

## 4. Ba luật được hiện thực bằng cấu trúc, không bằng lời dặn

### 4.1. Thiếu khai báo thì **từ chối**, không thay bằng 0

Coi "chưa khai" là "không tốn công" thì candidate lười khai luôn thắng ở O4 — đúng
chiều khuyến khích sai. `_engineering_cost_hours` ném `ObjectiveError` kèm hai lối ra
hợp lệ: khai đi, hoặc chấm dưới profile `measured_only` (β4 = 0, không định giá thứ
nền tảng không đo được).

`measured_only` **chuẩn hóa lại** ba β còn lại về tổng 1. Để nguyên tổng 0,70 thì U_C
của profile đó âm thầm bị bóp so với mọi profile khác, dù trọng số `w_C` không đổi.

### 4.2. `travel_time_accounting` — chống tính hai lần bằng validator

`monetized_cost` chỉ hợp lệ ở `business_adjusted`, và khi bật thì `time_efficiency`
**rời khỏi** O3 (U_E còn mình `path_efficiency`, không phải nhân 0,5 rồi để trống nửa
kia — làm vậy sẽ chặn trần U_E ở 0,5 cho mọi candidate). Bốn tổ hợp bất hợp lệ bị chặn
ngay lúc dựng `DecisionSettings`, không phải sau 200 episode.

### 4.3. `collision_count` không bao giờ vào U_S

HĐ-6 giao va chạm cho G2 và chỉ G2. Có test: hai episode giống hệt, một cái
`collision_count = 3`, U_S bằng nhau. Nếu va chạm vừa loại ở cổng vừa trừ điểm thì nó
ngầm trở thành thứ đánh đổi được với tốc độ — đúng cái mà việc có cổng loại bỏ.

## 5. `business_adjusted`: validate đủ, **từ chối tính**

Backlog cố ý để `monetized_cost`/What-if ngoài phạm vi. Nhưng lý do từ chối không phải
"chưa làm" mà cụ thể hơn: chi phí kỹ thuật quy tiền có đơn vị **tiền/nhiệm vụ**, và
`metric_anchors.yaml` không có anchor cho thang đó (`tuning_wall_clock_h` tính bằng
giờ). Dùng tạm thang giờ cho một con số tiền là lỗi đơn vị đội lốt con số.

Từ chối thay vì xấp xỉ, vì card ở chế độ này in nhãn *"Đã hiệu chỉnh theo giả định
kinh doanh do người dùng khai"* — câu đó không được đứng trên một con số tính dưới
thang không ai khai. Thông báo lỗi nói đúng thứ còn thiếu.

## 6. Nghiệm thu bằng số của contract

- `u(success_rate = 29/30 = 0,9667)` với ngưỡng 0,95 ⇒ **0,3333**; trung bình theo
  episode ⇒ **0,9667**. Cả hai đều có test, cạnh nhau.
- Đổi profile khách hàng sang `success_rate_min = 0,96` ⇒ cùng dữ liệu ra **0,1667**.
  Ngưỡng đi theo deployment, không nằm trong code.
- U_C với latency ở mốc `good`, memory 19 MB, CPU 0,5 s và 24 giờ tinh chỉnh khai báo
  ⇒ `0,70 + 0,30 × 0,4 = ` **0,82**, khớp β mặc định.
- **Test lật thứ hạng theo profile:** candidate "cẩn thận" (giữ khoảng cách, chậm) và
  candidate "nhanh" (rẻ, đi sát kệ) — `kho_ban_dem` (w_S = 0,10, w_C = 0,35) chọn cái
  nhanh, `benh_vien_gio_cao_diem` (w_S = 0,50, w_C = 0,15) chọn cái cẩn thận. Cùng
  metric, cùng anchor, hai câu trả lời trái ngược. Đây là luận điểm của đề tài viết
  thành một assertion.

## 7. Chưa làm — cố ý

- **`business_adjusted` tính thật** (mục 5) — cần thêm anchor cho chi phí quy tiền.
- **Pareto (HĐ-10), bootstrap ΔU (HĐ-11)** — Phase 3.4, module này chỉ cung cấp
  `decision_utility` theo từng episode để làm đầu vào.
- **Sensitivity trọng số/anchor (HĐ-11.5)** — Phase 5.3; `ResolvedAnchors.scaled` đã
  có sẵn từ 3.1.
- **Tie-break HĐ-11.3** — Phase 3.4, nhưng dữ liệu nó cần (`n_tunable_params`) giờ đã
  có chỗ đứng nhờ HĐ-1.6.

## 8. Test

`tests/test_objectives.py`: **35 test** — 4 preference profile của contract (7) ·
validator của `DecisionSettings` (6) · hai mức tổng hợp và chỗ chúng lệch/trùng (5) ·
công thức từng objective (5) · bắt buộc khai chi phí kỹ thuật (4) · decision_utility,
đổi tên `score`, card block, anchor theo deployment (8).

Full suite: `pytest tests/ -q` → **1774 passed, 6 skipped** (9 phút 28). Baseline sau
Phase 3.2 là 1739 — thêm đúng 35 test, **không vỡ test nào**, gồm cả 4 test
`test_contract_version` sau khi bump 2.1.0. Ruff sạch. Đã kiểm tay vòng import cả hai
thứ tự (`metrics` trước, `decision` trước) đều sạch.

## 9. Trạng thái Phase 3

| Mục | Trạng thái | Phụ thuộc |
|---|---|---|
| 3.1 Anchors + `u()` | ✅ | 1.1 ✓ |
| 3.2 Gates G1–G6 | ✅ | 1.1 ✓, 2.3 ✓ |
| 3.3 Objectives + Decision Utility | ✅ | 3.1 ✓ |
| 3.4 Paired bootstrap ΔU + nhãn | chưa — **làm được ngay** | 3.3 ✓, 1.3 ✓ |
| 3.5 Decision Card + Manifest | chưa | cần 3.2 ✓, 3.3 ✓, 3.4 |
