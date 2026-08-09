# Báo cáo — Phase 3.1: Anchors + `u()` (HĐ-8)

> **Ngày:** 2026-08-09
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **3.1**
> **Nhánh:** `plannerselector_p2`
> **Điều kiện vào:** 3.1 phụ thuộc 1.1 (TaskProfile) — đã xong từ Phase 1.
> **Contract:** `2.0.0` → **`2.0.1`** (PATCH, xem mục 4).

---

## 1. Đã làm

| File | Vai |
|---|---|
| `contracts/metric_anchors.yaml` (mới) | File anchor v1.0, đúng nội dung HĐ-8.2 |
| `packages/decision/planbench_decision/anchors.py` (mới) | Loader, resolver `${...}`, công thức `u()`, sweep ±10% |
| `tests/test_anchors.py` (mới) | 32 test |

## 2. Ba quyết định thiết kế

### 2.1. Anchor ngoại sinh — và vì sao `u` có nghĩa vật lý

Chuẩn hóa theo tập candidate (min-max) làm điểm của một candidate phụ thuộc vào
việc **ai khác được ghi danh**: thêm một planner 200 ms thì hai đối thủ 10 ms và
20 ms nhảy từ 1,00/0,00 lên 1,00/0,95 — cùng code, khác người thắng (§17 cấm 3).
Anchor ở đây lấy từ vật lý bài toán và từ giới hạn deployment khai, nên `u = 0,7`
ở clearance nghĩa là "cách tường 1,7 lần bán kính robot", không phải "nhì trong
lô này".

### 2.2. Luật 2 (metric có cổng) được **kiểm**, không chỉ được viết

`bad` của `success_rate`, `p99_latency_ms`, `memory_estimate_mb` bắt buộc là tham
chiếu `${...}`. Ghi cứng `success_rate.bad = 0,90` trong khi khách khai
`success_rate_min = 0,95` thì candidate đạt 0,96 được chấm vì vượt một cái mốc
**không ai đặt**, và file anchor trôi khỏi ràng buộc deployment mà không có triệu
chứng nào. Loader từ chối thẳng.

Có test khẳng định **chính file đang ship** tuân luật, không chỉ khẳng định loader
biết từ chối — hai điều khác nhau.

### 2.3. `${...}` được **parse**, không `eval`

Ngữ pháp: một đường dẫn field, tối đa một phép nhân hoặc chia. File anchor là thứ
người dùng upload; cho qua `eval` thì một file YAML thành thực thi mã tùy ý. Test
liệt kê thẳng các chuỗi bị từ chối, gồm `${__import__('os').system(...)}`.

Tham chiếu chỉ đi vào TaskProfile (không ra ngoài), phải trỏ tới **một con số** —
trỏ vào cả khối `constraints` bị từ chối chứ không stringify.

## 3. Nghiệm thu bằng chính số của contract

`u(success_rate = 0,967)` với `success_rate_min = 0,95` ⇒ **0,34**, đúng `U_R` của
K1 trong ví dụ chạy tay §6.2 của tài liệu đề tài. Có test khóa con số này: anchor
trôi thì ví dụ trong tài liệu và hệ thống không còn nói cùng một thứ.

Bảng resolve trên profile tham chiếu:

| Metric | good | bad | Nguồn của `bad` |
|---|---:|---:|---|
| `success_rate` | 1,00 | 0,95 | `${constraints.success_rate_min}` |
| `p99_latency_ms` | 10 | 50 | `${robot.control_period * 1000}` |
| `min_clearance` | 0,52 | 0,273 | `${robot.radius * 1.05}` |
| `memory_estimate_mb` | 819,25 | 3277 | `${hardware.available_ram_mb}` |
| `path_efficiency` | 1,00 | 0,65 | vật lý bài toán (không có cổng ⇒ được phép là số) |

Đổi profile thì mốc đổi theo: khách khai `success_rate_min = 0,99` ⇒ `bad = 0,99`,
và 0,995 được chấm 0,5. Cùng một file anchor.

## 4. Contract 2.0.0 → 2.0.1 (PATCH)

HĐ-8.2 và HĐ-9.1 gọi metric clearance là **`min_clearance_m`**, trong khi HĐ-6 —
bảng định nghĩa metric — gọi là **`min_clearance`**. Anchor tra **theo đúng tên
metric**, nên hai tên là: một anchor không bao giờ khớp, và một metric âm thầm
không có thang (rồi `u()` ném lỗi "no anchor for" ở Phase 3.3, xa chỗ gây lỗi).

Sửa hai chỗ đầu theo HĐ-6 (PATCH = làm rõ câu chữ), bump `2.0.1`, thêm dòng §18,
`CONTRACTS_VERSION` khớp. 4 test version xanh.

## 5. Việc thêm ngoài mô tả backlog (nhỏ, có lý do)

- **`ResolvedAnchors.scaled(factor)`** — sweep ±10% mà HĐ-8.3 luật 3 bắt mọi lần
  ra quyết định phải chạy. Hai đầu `good`/`bad` **cùng dịch**: câu hỏi là "thang
  có được chọn đúng không", không phải "một đầu của thang". Version string ghi
  luôn mức dịch (`v1.0±+10%`) để một card sinh dưới anchor nhiễu không bao giờ bị
  nhầm với card sinh dưới anchor khai báo. Phase 5.3 chỉ việc gọi.
- **`ANCHORABLE_METRICS`** — anchor cho tên lạ bị từ chối. Một typo
  (`path_efficency`) sẽ nằm trong file mãi mãi, không chấm gì, trong khi metric nó
  định neo thì không có thang.
- **`u()` từ chối `good == bad`** và đo không hữu hạn: cả hai cho ra một thang
  vô nghĩa hoặc NaN lan vào utility.

## 5b. Test

`tests/test_anchors.py`: **32 test** — công thức hai chiều + clip · file đang ship
(đường dẫn, version, resolve, tái lập số §6.2, đổi theo deployment) · luật 2 cho cả
3 metric có cổng · resolver (nhân, chia, field lạ, trỏ vào block, biểu thức tùy ý,
field private) · validate file (tên metric lạ, thiếu version, thiếu file, sai shape,
thang sụp) · sweep ±10% · metric chưa có anchor.

Full suite: `pytest tests/ -q` → **1699 passed, 6 skipped** (8 phút 39). Baseline
sau Phase 2.3 là 1667 — thêm đúng 32 test, **không vỡ test nào**. Ruff sạch.

## 6. Chưa làm — cố ý

- **Objective R/S/E/C** (HĐ-9) là Phase 3.3, không phải ở đây. Module này chỉ trả
  `u` cho từng metric.
- **Chạy sweep ±10% thật** và ghi `anchor_stability` lên card: Phase 5.3.
- **`anchor_config_version` vào manifest**: Phase 3.5 (manifest), đã có sẵn
  `AnchorSet.version` để lấy.

## 7. Trạng thái Phase 3

| Mục | Trạng thái | Phụ thuộc |
|---|---|---|
| 3.1 Anchors + `u()` | ✅ | 1.1 ✓ |
| 3.2 Gates G1–G6 | chưa — **làm được ngay**, độc lập 3.1 | 1.1 ✓, 2.3 ✓ |
| 3.3 Objectives + Decision Utility | chưa | cần 3.1 ✓ |
| 3.4 Paired bootstrap ΔU | chưa | cần 3.3, 1.3 ✓ |
| 3.5 Decision Card + Manifest | chưa | cần 3.2–3.4 |
