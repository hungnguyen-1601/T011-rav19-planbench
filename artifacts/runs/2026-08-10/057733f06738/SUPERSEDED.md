# ⚠ Tấm card này đã bị thay thế — đừng đọc nó như một kết quả

**Chạy:** 2026-08-10 15:11 · `warehouse_a_v1` · 30 episode ghép cặp ·
`astar+dwa` (`ac187ee7a77e`) vs `rrtstar+dwa` (`2baaad3628e1`)
**Tính dưới:** `contracts_version 4.2.0`, anchor `v1.2`
**Kết luận nó in ra:** `CLEAR_RECOMMENDATION` cho `astar+dwa`, ΔU = +0,0256,
CI95 = [+0,0052, +0,0453]

**Giữ lại, không xoá.** Đây là vật chứng của bốn lỗi mà dự án đã học được từ chính nó, và mỗi
lỗi sau đó đã thành một điều khoản hợp đồng hoặc một phép kiểm. Xoá đi là xoá bằng chứng cho
những điều khoản đó.

---

## Bốn thứ trong tấm card này không còn đúng

### 1. Cận trên va chạm 10,0% đứng trên **một** mẫu

Card in `"0 va chạm quan sát trong 30 lần chạy; cận trên 95%: 10,0%"`, với
`n_distinct_episodes` **không tồn tại** trong schema thời đó.

Quy tắc số 3 giả định 30 lần chạy **độc lập**. `astar+dwa` là planner tất định, và xe nâng của
`warehouse_a_v1` (`seed_time_offset = 6 s` trên chu kỳ 24 s) không bao giờ cắt qua tuyến đường —
đo được ở Phase 5.1: khoảng cách gần nhất qua 100 seed là **2,53 m**, trong khi chạm nhau ở
0,66 m, và **0/100 seed** vào trong 2 m.

Nên 30 episode đó là **một** episode phát lại 30 lần. Bằng chứng trực tiếp: lần chạy 100 episode
sau đó cho `decision_utility` **giống hệt tới 16 chữ số** — `0.8205179005094823` — điều chỉ xảy
ra khi cả hai bộ chứa cùng một episode duy nhất.

Sửa ở `contracts 6.0.0`: G2 tính cận trên trên **số episode phân biệt**, và bảng cổng in cả
`n_runs` lẫn `n_distinct_episodes`.

### 2. Ngưỡng G4 là 100 ms, không phải 50 ms

Card in `threshold_ms: 100.0`. Ngưỡng đó đến từ `robot.control_period: 0.1` — một nhượng bộ 10 Hz
khai trong profile với lý do "DWA Python không tính nổi một bước điều khiển trong 50 ms". Tức
**ngưỡng cổng thời gian thực bị nới gấp đôi vì candidate không qua nổi nó**.

Sửa ở `contracts 6.1.0`: cả hai profile về 20 Hz. Lý do nhượng bộ đã hết đúng từ trước mà không
ai để ý — sau khi 3.0.0 đổi G4 sang p99 gộp và Phase 5.1 ghim nhân, p99 đo được là 10,81 ms và
16,10 ms, thừa dưới 50 ms.

### 3. `p99 = 59,30 ms` của `rrtstar+dwa` là hiện vật của phép đo, không phải tính chất candidate

Cùng candidate đó, đo lại khi ghim 2 nhân, cho **16,10 ms** — chênh **3,7 lần**. Card này đo trên
máy không ghim, nên con số 59,3 ms nói về tải của máy chứ không nói về RRT\*.

### 4. `benchmark_host` khai sai

Manifest ghi `cores_allocated: 1, threads: 1`. Con số đó **hardcode trong script**, không đo. Run
thật giữ toàn bộ 20 nhân. Sửa ở `contracts 6.1.0`: `hostinfo.py` đo affinity thật và cảnh báo khi
run không được ghim.

---

## Ngoài ra

Candidate id `ac187ee7a77e` và `2baaad3628e1` **không còn tồn tại**: DWA nay chạy ở 20 Hz nên
`candidate_id` đã đổi. Bộ trace của run này (`artifacts/traces/`, gitignored) được giữ làm bằng
chứng, không phải làm số liệu.

## Đọc thêm

- `docs/antongduy/reports/2026-08-11/tongduyan_phase-5-1-mot-tam-card-noi-doi.md` — lỗi ①
- `docs/antongduy/reports/2026-08-11/tongduyan_f0-dua-ve-quy-dao-va-f1-mvp-do-mot-stack.md` — ②③④
- `contracts/CONTRACTS.md` §18, mục `6.0.0` và `6.1.0`
