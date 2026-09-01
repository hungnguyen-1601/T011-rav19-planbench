# Báo cáo — Phase 3.2: Feasibility Gates G1–G6 (HĐ-7)

> **Ngày:** 2026-08-10
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **3.2**
> **Nhánh:** `plannerselector_p2`
> **Điều kiện vào:** 3.2 phụ thuộc 1.1 (TaskProfile) ✓ và 2.3 (`definitions.py`) ✓; độc lập 3.1 nên làm song song được — đúng như backlog dự trù.
> **Contract:** giữ nguyên **`2.0.1`** — xem mục 5.

---

## 1. Đã làm

| File | Vai |
|---|---|
| `packages/decision/planbench_decision/gates.py` (mới) | 6 cổng + `GateReport` + `to_card()` + bộ chặn từ ngữ |
| `packages/decision/planbench_decision/__init__.py` | export lớp công khai của gates |
| `tests/test_gates.py` (mới) | 40 test |

Hàm vào duy nhất:

```python
evaluate_gates(candidate, profile, metrics, contexts) -> GateReport
```

`metrics` là `EpisodeMetricSet` của Phase 2.3 — cổng không tự tính metric nào, đúng luật "không thêm metric ngoài `definitions.py`" (HĐ-15.3).

## 2. Bốn quyết định thiết kế

### 2.1. Không một con số ngưỡng nào nằm trong module này

G1 đọc `no_path_rate_max`, G3 đọc `success_rate_min`, G4 đọc `robot.control_period`,
G5 đọc `hardware.available_ram_mb`, G6 đọc `available_observations`, và `N_min` của
G2 suy từ `collision_probability_max`. Test `test_g3_bar_moves_with_the_deployment`
chạy **cùng một bộ episode** qua hai profile khai `0,95` và `0,99`, ra hai phán quyết
khác nhau — nếu có một hằng số trong code thì test này không thể xanh. Ba test tương
tự cho G4, G5, G2.

Cách hỏng nếu không có luật này: một khách hàng thứ hai bị chấm theo mức chịu đựng
của khách hàng đầu tiên, và không có triệu chứng nào ngoài một con số trông hợp lý.

### 2.2. Sáu cổng **luôn** chạy hết, không short-circuit

HĐ-15.1 tiêu chí 3 bắt in đủ 6 cổng kèm số lần chạy. "Bị loại ở G2" mà không biết G4
có trượt không là một chẩn đoán không hành động được: đội sửa sẽ tối ưu va chạm rồi
phát hiện candidate vẫn trượt latency ở vòng sau. `blocking_gates` trả về **danh sách**
theo thứ tự contract, không phải cổng đầu tiên.

### 2.3. G2: 0 va chạm **không** đủ để pass

Zero va chạm trong 10 lần chạy tương thích với tỉ lệ va chạm thật 26%. Nếu chỉ xét
"observed == 0" thì **kích thước lô chạy quyết định được phép tuyên bố gì** — đúng
chiều đảo ngược mà HĐ-7.1 cấm. Nên G2 đòi cả `N ≥ N_min = ceil(3/p_max)`.

Câu bắt buộc được sinh nguyên văn và có test khóa mặt chữ:

```
0 va chạm quan sát trong 30 lần chạy; cận trên 95% dưới phân phối kịch bản đã mô phỏng: 10.0%
```

Với N = 300 (p_max = 0,01) ra đúng `1.0%` — con số in trong card mẫu HĐ-12.

**Khi đã có va chạm thì `upper_bound_95 = None`.** Quy tắc số ba chỉ áp cho dữ liệu
không có sự kiện; nêu một cận trên ở đó là phép tính đội lốt bằng chứng.

`evaluate_gates` cũng gọi `require_sample_set(contexts, "evaluation")`: gộp
`neighborhood` vào làm N phồng lên mà không thêm mẫu độc lập, khiến `3/N` đẹp hơn
bằng chứng cho phép (§17 cấm 7).

### 2.4. §17 cấm 10 là code, không phải lời dặn

`assert_no_banned_language()` duyệt toàn bộ card (chuỗi, dict, list) tìm `an toàn` và
`TCO`, và `to_card()` **tự gọi** nó trước khi trả về — không trông vào việc mọi caller
tương lai còn nhớ luật. `an toàn` khớp cả `không an toàn` (cùng một overclaim, ngược
chiều); `TCO` khớp theo word boundary nên không bắt nhầm từ chỉ chứa ba chữ cái đó.
Có test CI cho cả hai chiều: card thật sạch, và bộ chặn thật sự bắt được 5 biến thể.

## 3. Hai chỗ chọn "xấu nhất" thay vì "trung bình"

G4 lấy **max** p99 qua các episode, G5 lấy **max** `memory_estimate_mb`. Cả hai ngưỡng
là **trần**, không phải mục tiêu: một episode vượt budget là một vi phạm, mà trung bình
trên 29 episode ngoan sẽ nuốt mất nó. Riêng G4 còn một lý do nữa — trung bình của các
phân vị không còn là phân vị của cái gì cả.

## 4. Bảo lưu sim-only được hiện thực, không chỉ được ghi

- `RealtimeGateStatus` là `Literal["screened_on_host"]` — **một giá trị**. Không có
  đường nào trong code sinh ra `verified_on_target` (§17 cấm 12).
- Mọi `G4Result` mang nguyên văn `"G4 mới qua vòng sàng lọc — chưa xác nhận trên bo
  mạch đích"`.
- `MemoryGateStatus` chỉ có `estimated_from_structure` | `declared_by_author`.
- Candidate khai `resource_profile.source = "measured_on_target"` bị **từ chối bằng
  exception**, kèm chỉ dẫn: gỡ bảo lưu và bump MINOR trước khi dùng.

G5 không bao giờ chạm `peak_rss_mb` để ra phán quyết; trường này đi kèm card dưới tên
`peak_rss_mb_diagnostic` — đặt tên như vậy để không ai nhầm nó với số của cổng (§17
cấm 13). Có test bơm `peak_rss_mb = 4000` (vượt xa budget 3277) và khẳng định G5 vẫn
pass với estimate 19 MB.

## 5. Vì sao contract **không** đổi ở phase này

HĐ-7 mô tả đủ cả 6 cổng, nguồn ngưỡng, hai pha của G4/G5, chuỗi báo cáo bắt buộc và
bảo lưu sim-only. Không phát sinh giả định thiếu nào khi hiện thực, nên `2.0.1` giữ
nguyên — khác Phase 3.1, nơi việc code lộ ra hai tên gọi khác nhau của một metric.

Một chỗ contract để ngỏ và tôi chọn thay: **phán quyết cổng trên một tập episode cần
một phép tổng hợp**, HĐ-6 định nghĩa `p99_latency_ms` và `memory_estimate_mb` theo
từng episode. Chọn max (mục 3). Đây là quyết định hiện thực, không mở rộng ngữ nghĩa
cổng, nên không phải sửa hợp đồng.

## 6. Từ chối vs. đánh trượt — hai việc khác nhau

`GateInputError` được ném (không biến thành "fail") khi: không có episode nào; trộn
metric của candidate khác; một context lặp lại; contexts và metrics không mô tả cùng
một lượt chạy; episode chạy dưới task profile khác với profile đang áp ngưỡng; thiếu
`memory_estimate_mb`.

Lý do: "candidate này bị loại" và "chúng ta không biết nó có nên bị loại không" là hai
phát biểu khác nhau. Một Decision Card lẫn hai thứ đó sẽ loại một candidate vì lỗi sổ
sách.

## 7. Card

`GateReport.to_card()` trả **đúng hình dạng HĐ-12**: G1/G3/G6 là chuỗi `"pass"`/
`"fail"`, G2/G4/G5 là block. Bằng chứng đầy đủ (rate quan sát, ngưỡng, missing token)
nằm trên object `GateReport` — card là bản tóm tắt phải so bằng mắt được với contract,
còn bảng cổng trên UI (7.1) đọc object.

## 8. Test

`tests/test_gates.py`: **40 test** — ngưỡng đến từ profile (4 test, mỗi cái đổi profile
và kiểm phán quyết lật) · G1 (3) · G2 (5: N_min, câu bắt buộc nguyên văn, con số 1.0%
của contract, không cận trên khi có va chạm, từ chối neighborhood) · G4 (2) · G5 (5) ·
G6 (3) · report/card (4) · ngôn ngữ cấm (6) · input không đủ để phán quyết (5).

Full suite: `pytest tests/ -q` → **1739 passed, 6 skipped** (8 phút 34). Baseline sau
Phase 3.1 là 1699 — thêm đúng 40 test, **không vỡ test nào**. Ruff sạch. Mypy: chỉ
còn lỗi `import-not-found` sẵn có của workspace (mypy chưa được nối `pythonpath` của
các package), không có lỗi kiểu mới.

## 9. Một ghi chú kỹ thuật: vòng import

`planbench_metrics.definitions` import `planbench_decision.candidate` (để lấy
`ResourceProfile`). Nếu `gates.py` import ngược lại lúc runtime thì thứ tự "metrics
trước" sẽ đóng vòng và vỡ. Nên `EpisodeMetricSet` chỉ được import trong
`if TYPE_CHECKING` — cổng chỉ đọc thuộc tính, không cần lớp lúc chạy. Đã kiểm tay cả
hai thứ tự import đều sạch.

## 10. Trạng thái Phase 3

| Mục | Trạng thái | Phụ thuộc |
|---|---|---|
| 3.1 Anchors + `u()` | ✅ | 1.1 ✓ |
| 3.2 Gates G1–G6 | ✅ | 1.1 ✓, 2.3 ✓ |
| 3.3 Objectives + Decision Utility | chưa — **làm được ngay** | cần 3.1 ✓ |
| 3.4 Paired bootstrap ΔU | chưa | cần 3.3, 1.3 ✓ |
| 3.5 Decision Card + Manifest | chưa | cần 3.2 ✓, 3.3, 3.4 |
