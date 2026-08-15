# Quyết định của dev trước khi mở Phase 5 — chưa thực thi dòng code nào

> **Ngày:** 2026-08-10 · **Người quyết:** An · **Ghi lại bởi:** Claude
> **Bối cảnh:** Phase 1–4 của `backlog-uu-tien-planner-selector.md` đã đóng
> (lát cắt dọc 6/6 tiêu chí HĐ-15.1 xanh, contract `3.0.0`, suite
> `1854 passed / 6 skipped`). Sáu câu hỏi treo được nêu ở cuối
> `reports/2026-08-10/tongduyan_phase-4-lat-cat-doc.md` và trong phiên rà soát
> hôm nay. Dev đã trả lời cả sáu.
> **Trạng thái:** đã chốt, **cố ý chưa thực thi** — dev chưa có thời gian giám sát.
> Lượt làm tiếp theo lấy file này làm đầu vào, không hỏi lại.

---

## Bảng chốt nhanh

| # | Câu hỏi | Quyết định | Trạng thái |
|---|---|---|---|
| 1 | Thang anchor `min_clearance` (`U_S ≡ 0`) | Sửa sang thang **mặt robot** theo đề xuất | ⏳ chờ làm |
| 2 | Khe `.gitignore` cho card + manifest | **Xác nhận giữ** | ✅ không cần làm gì |
| 3 | Contract thiếu chữ ký Dev A / Dev C | **Bypass** — An duyệt là đủ | ⏳ chờ ghi vào §0 |
| 4 | Cache lưới inflate trước Phase 5.1 | **Làm**, nhưng **hold** vì >10 phút | ⏸ hold |
| 5 | Manifest HĐ-13 lưu context đầy đủ | Sửa contract ở **Phase 6.1**, cùng migration | ⏳ Phase 6.1 |
| 6 | Anchor tiền cho `business_adjusted` | **Thêm** | ⏳ chờ làm |

---

## 1. Anchor `min_clearance` — sửa sang thang mặt robot

**Vấn đề (mục 5.2 báo cáo Phase 4):** `clearance_m` của HĐ-5 và collision layer của
simulator trả khoảng cách từ **mặt** robot (đã trừ bán kính). Anchor hiện tại viết
theo thang **tâm** robot. Hai thang lệch nhau đúng một bán kính, nên trên kho tham
chiếu mọi episode nằm dưới `bad` ⇒ `u = 0` ⇒ `U_S = 0` cho mọi candidate ⇒ objective
an toàn (`w_S = 0,10`) là hằng số, không phân biệt được gì.

Số liệu thật: `min_clearance` trung vị 0,041 m (A\*) và 0,070 m (RRT\*); anchor hiện
tại `bad = radius × 1,05 = 0,273`, `good = radius × 2,0 = 0,520`. Con số 4 cm là
**đúng** — robot rộng 0,52 m trong khe kệ 0,68 m thì mỗi bên còn 0,08 m.

**Quyết định:** giữ metric (mặt robot là nghĩa của "clearance" trong trace), sửa anchor.

```yaml
# contracts/metric_anchors.yaml
min_clearance: {good: "${robot.radius}", bad: 0.0}
```

Với thang này, khe hẹp nhất của kho chấm ≈ 0,31 thay vì 0,00 — phân biệt được.

**Việc kèm theo, không được quên:**

- Bump `metric_anchors.version` `v1.0` → `v1.1`. Manifest đã ghi
  `anchor_config_version` nên card cũ vẫn tự khai nó tính dưới anchor nào.
- Bump contract: đổi thang chấm điểm của một metric là nội dung HĐ-8.2.
  Đây **không** phải đổi ngữ nghĩa cổng (khác 3.0.0 của G4) nhưng có đổi điểm số
  của mọi candidate ⇒ đề xuất **MINOR** `3.0.0` → `3.1.0`, để dev bác nếu thấy phải MAJOR.
- **Không cần mô phỏng lại.** HĐ-5 đặt trace làm nguồn duy nhất, nên tính lại card từ
  bộ trace ở `artifacts/runs/2026-08-10/057733f06738/` mất vài giây.
- Kỳ vọng: `decision_utility = 0.812618` sẽ **đổi**, và khuyến nghị có thể lật —
  RRT\* có clearance trung vị cao hơn (0,070 so với 0,041). Nếu lật thì đó là kết quả
  đúng, không phải regression; báo cáo phải nói rõ.

## 2. Khe `.gitignore` — xác nhận giữ

D15 ignore cả `artifacts/`. Phase 4 mở khe cho đúng hai file JSON vài kB
(`decision_card.json`, `manifest.json`) của mỗi run, vì HĐ-15.1 biến lát cắt thành hồ
sơ nghiệm thu và HĐ-13 biến manifest thành thứ người khác dựng lại card từ đó.
Trace Parquet vẫn bị ignore.

**Dev xác nhận giữ.** Không còn là quyết định treo.

## 3. Chữ ký contract — bypass

Mục 0 CONTRACTS đòi ≥2 approve; bản hiện tại `3.0.0` vẫn chỉ có chữ ký ứng với `2.0.0`.

**Quyết định:** bypass. Tạm thời **An duyệt là đủ**, không đợi Dev A / Dev C.

Việc phải làm: sửa §0 ghi thẳng quy trình duyệt hiện hành thay vì để điều khoản
≥2-approve nằm đó bị vi phạm âm thầm. Một hợp đồng có điều khoản không ai theo thì
mọi điều khoản khác cũng mất trọng lượng — nên ghi ngoại lệ tường minh, kèm ngày và
lý do (nhóm chưa vận hành đủ người ở giai đoạn này).

## 4. Cache lưới inflate — làm, nhưng HOLD

**Vì sao cần:** Phase 5.1 chạy `N_min = 300` ở mức rủi ro 1%. Ở 20 s/episode × 2
candidate ≈ 3,3 giờ mỗi lượt, và Pareto/sensitivity còn quét lại.

**Chẩn đoán code:** `OccupancyGrid.inflate` (`services/simulator/planbench_simulator/grid.py:98-135`)
là vòng lặp Python thuần — mỗi ô OCCUPIED nhân với ~350 offset trong disk bán kính
0,54 m ở độ phân giải 5 cm. Gọi từ `nav_stack.py:98`, **mỗi episode và mỗi lần replan**.

Hai việc tách bạch, không phải một:

| | Nội dung | Ước lượng | Ghi chú |
|---|---|---|---|
| (a) **Vector hoá `inflate`** | `scipy.ndimage.binary_dilation` với disk footprint; giữ nguyên luật *UNKNOWN không bị phủ thì vẫn UNKNOWN* | ~40 phút + test | Ăn **cả replan** — replan có `extra_obstacles` nên cache không cứu được |
| (b) **Cache `_planning_grid`** | Key = (map hash, static obstacles, `inflation_radius`) | ~30 phút | Chỉ ăn plan đầu mỗi episode |
| | Chạy lại `pytest tests/ -q` | 10,5 phút | |

Tổng ~1,5 giờ ⇒ vượt ngưỡng 10 phút dev đặt ⇒ **hold**.

**Khuyến nghị khi mở lại:** làm **(a) trước**, đo lại, rồi mới quyết có cần (b) không.
(a) rẻ hơn về rủi ro (không đụng vòng đời object, không có lớp bug cache-stale) và cứu
được nhiều đường gọi hơn. `scipy` đã có sẵn trong deps.

## 5. Manifest HĐ-13 — để Phase 6.1

**Vấn đề (mục 4 báo cáo Phase 2.3):** metadata HĐ-5 lưu **hash** của context chứ không
lưu `mission_id`, và hash không đảo ngược được. Nên một lần *tính lại metric từ thư mục
trace* — đúng thứ HĐ-5 hứa — chỉ làm được nếu manifest lưu **bản ghi context đầy đủ**,
không phải chỉ danh sách id như HĐ-13 đang viết.

**Quyết định:** sửa contract ở **Phase 6.1**, cùng lượt với migration bảng
`task_profiles` / `candidates` / `decision_cards`. Không sửa ngay.

Rủi ro chấp nhận: từ giờ tới Phase 6.1, mọi manifest ghi ra đều **không** tái lập được
metric một cách độc lập nếu mất object `EpisodeContext` trong bộ nhớ. Với lát cắt hiện
tại thì không sao vì script chạy một mạch; nó chỉ cắn khi có run chạy qua worker.

## 6. Anchor tiền — thêm

**Vấn đề (mục 5 báo cáo Phase 3.3):** `business_adjusted` hiện **validate đủ nhưng từ
chối tính**, vì chi phí kỹ thuật quy tiền có đơn vị **tiền/nhiệm vụ** mà
`metric_anchors.yaml` không có anchor cho thang đó (`tuning_wall_clock_h` tính bằng giờ).

**Quyết định:** thêm anchor tiền, bật đường tính thật.

Vì sao đáng làm dù backlog xếp ngoài phạm vi: demo **hai chân trời lật khuyến nghị**
(50.000 nhiệm vụ so với 200 nhiệm vụ pilot) là luận điểm mạnh nhất của đề tài — mục N3
gọi nó là *"thứ phân biệt một dự án kỹ thuật với một dự án sản phẩm"*. Không có anchor
tiền thì chỉ chạy được fallback ghi ở plan 3.2.

**Chưa chốt, phải quyết lúc làm:**

- Tên và đơn vị anchor (`cost_per_mission_vnd`? `cost_per_mission_usd`? có nên là
  không-đơn-vị và để preference profile mang tỉ giá?).
- `good` / `bad` lấy từ đâu cho đúng tinh thần "ngoại sinh". Đây là chỗ dễ bịa số
  nhất trong cả hệ — nếu anchor tiền do ta chọn thì nó phải nằm trong preference
  profile (Declared) chứ không nằm trong file anchor (mốc vật lý), nếu không là vi
  phạm chính luật N2 đã đặt ra.
- Card ở chế độ này in nhãn *"Đã hiệu chỉnh theo giả định kinh doanh do người dùng
  khai"* — phải có test chuỗi, và phải chắc `travel_time_accounting` không bật cả hai
  đường (validator một-trong-hai đã có ở Phase 3.3).

Ước lượng ~1,5–2 giờ.

---

## Thứ tự đề xuất cho lượt làm tiếp theo

```
#1 anchor clearance (blocker Phase 5) ── #3 §0 bypass (rẻ, dọn nợ hợp đồng)
        │
        └── #4 (a) vector hoá inflate ── đo lại ── quyết (b)
                    │
                    └── Phase 5.1 evaluation distribution N=300
                                │
                                └── #6 anchor tiền (song song được, không chặn 5.1)
```

`#1` là blocker thật sự duy nhất: `U_S` còn là hằng số 0 thì Pareto (5.2) và
sensitivity (5.3) đều chạy trên một objective chết, và mọi kết luận lấn át sẽ bỏ qua
chiều an toàn.
