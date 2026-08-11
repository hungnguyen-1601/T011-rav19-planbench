# ⚠ Tấm card này đã bị thay thế — đừng đọc nó như một kết quả

**Chạy:** 2026-08-10 15:44 · `warehouse_a_v1` · 30 episode ghép cặp ·
`astar+dwa` (`ac187ee7a77e`) vs `rrtstar+dwa` (`2baaad3628e1`)
**Tính dưới:** `contracts_version 5.0.0`, anchor `v1.2`
**Kết luận nó in ra:** `CLEAR_RECOMMENDATION` cho `astar+dwa`, ΔU = +0,0256,
CI95 = [+0,0052, +0,0453]

**Giữ lại, không xoá** — vật chứng của bốn lỗi mà dự án học được từ chính nó.

> **Lưu ý riêng của tấm này:** nó **không phải một lần đo mới**. Mọi con số ở đây trùng khít tới
> chữ số float cuối với run `2026-08-10/057733f06738` (ΔU = 0.02555142290484136, cùng CI, cùng
> per-episode) vì nó **chấm lại trên đúng bộ trace đó** sau khi Pareto và sensitivity được thêm
> vào. Hai thư mục, một tập dữ liệu. Đếm nó thành hai lần chạy độc lập là nhân đôi bằng chứng
> từ hư không.

---

## Bốn thứ trong tấm card này không còn đúng

### 1. Cận trên va chạm 10,0% đứng trên **một** mẫu

Card in `"0 va chạm quan sát trong 30 lần chạy; cận trên 95%: 10,0%"`, với
`n_distinct_episodes` **không tồn tại** trong schema thời đó.

Quy tắc số 3 giả định 30 lần chạy **độc lập**. `astar+dwa` tất định, và xe nâng của
`warehouse_a_v1` (`seed_time_offset = 6 s` trên chu kỳ 24 s) không bao giờ cắt qua tuyến — đo
được ở Phase 5.1: gần nhất qua 100 seed là **2,53 m** so với khoảng chạm 0,66 m, **0/100 seed**
vào trong 2 m. Nên đó là **một** episode phát lại 30 lần.

Bằng chứng trực tiếp: lần chạy 100 episode sau đó cho `decision_utility` giống hệt tới 16 chữ số
— `0.8205179005094823`.

Sửa ở `contracts 6.0.0`: G2 tính trên **số episode phân biệt**; bảng cổng in cả hai con số.

### 2. ΔU trung vị in cạnh CI của trung bình

Card in `delta_u_vs_second` (trung vị) ngay cạnh `ci95` (khoảng của **trung bình**, HĐ-11.2). Hai
thống kê khác nhau đứng cạnh nhau đọc như một con số và thanh sai số của nó. Ở bộ 30 episode
trung vị tình cờ nằm trong khoảng nên không ai thấy; ở bộ 100 episode nó **nằm ngoài**
(+0,0131 so với [+0,0028, +0,0111]).

Sửa ở `contracts 6.0.0`: thêm `delta_u_mean` để khoảng tin cậy có chủ sở hữu nhìn thấy được.

### 3. Ngưỡng G4 là 100 ms, không phải 50 ms

`threshold_ms: 100.0` đến từ `robot.control_period: 0.1` — nhượng bộ 10 Hz khai trong profile vì
"DWA Python không tính nổi một bước trong 50 ms". Ngưỡng cổng bị nới gấp đôi vì candidate không
qua nổi nó.

Sửa ở `contracts 6.1.0`: hai profile về 20 Hz. Lý do nhượng bộ đã hết đúng từ trước — p99 đo được
là 10,81 ms và 16,10 ms.

Kèm theo, `p99 = 59,30 ms` của `rrtstar+dwa` trên card này là hiện vật của máy không ghim nhân:
cùng candidate ghim 2 nhân cho **16,10 ms**, chênh 3,7 lần.

### 4. `benchmark_host` khai sai

`cores_allocated: 1, threads: 1` là số **hardcode trong script**, không đo. Run thật giữ toàn bộ
20 nhân. Sửa ở `contracts 6.1.0` bằng `hostinfo.py`.

---

## Ngoài ra

Candidate id `ac187ee7a77e` và `2baaad3628e1` **không còn tồn tại** — DWA nay chạy 20 Hz nên
`candidate_id` đã đổi.

## Đọc thêm

- `docs/antongduy/reports/2026-08-11/tongduyan_phase-5-1-mot-tam-card-noi-doi.md` — lỗi ①②
- `docs/antongduy/reports/2026-08-11/tongduyan_f0-dua-ve-quy-dao-va-f1-mvp-do-mot-stack.md` — ③④
- `contracts/CONTRACTS.md` §18, mục `6.0.0` và `6.1.0`
