# ⚠ Đây là "tấm card nói dối" — giữ lại đúng vì nó nói dối

**Chạy:** 2026-08-11 02:20 · `warehouse_a_v1` · **100 episode** ghép cặp, xen kẽ, ghim 2 nhân ·
`astar+dwa` (`ac187ee7a77e`) vs `rrtstar+dwa` (`2baaad3628e1`)
**Tính dưới:** `contracts_version 5.0.0`, anchor `v1.2`
**Kết luận nó in ra:** `CLEAR_RECOMMENDATION` cho `astar+dwa`, ΔU = +0,0131,
CI95 = [+0,0028, +0,0111]

**Giữ lại, không xoá — và tấm này là quan trọng nhất trong ba tấm.** Sáu tiêu chí nghiệm thu
HĐ-15.1 đều xanh khi nó ra đời. **Không có gì trên nó trông sai.** Đó chính là điều nó chứng
minh, và là lý do dự án bây giờ có `n_distinct_episodes`, có `validate_control_rate`, và có một
điều khoản nói rằng một ghi chú "nhớ làm ở phase sau" không phải một biện pháp bảo vệ.

---

## Lỗi chính: cận trên 3,0% tính từ **một** mẫu duy nhất

Card in, cho `astar+dwa`:

```
G2: 0 va chạm quan sát trong 100 lần chạy; cận trên 95%: 3,0%
```

Đo lại: cả **100** episode của A\* giống hệt nhau tới chữ số float cuối.

```
astar+dwa      utility per-episode:   1 giá trị khác nhau /100
rrtstar+dwa    utility per-episode: 100 giá trị khác nhau /100
```

RRT\* biến thiên vì nó là planner ngẫu nhiên. A\* tất định, và môi trường không cho nó gì để phản
ứng khác đi. **Số mẫu hiệu dụng là 1**; quy tắc số 3 cho `3/1`, tức run này không chặn được gì.

Nguyên nhân, truy bằng ba giả thuyết loại từng cái: seed **có** tới được vật cản, xe nâng **có**
đổi pha theo seed, robot **có** đi xuyên hành lang của nó. Cái sai là **biên độ** —
`seed_time_offset = 6 s` trên chu kỳ **24 s** chỉ quét một phần tư pha, robot cắt qua lane đó
trong cửa sổ ~2 giây, và **0/100 seed** đưa hai bên vào trong 2 m (gần nhất **2,53 m**, chạm nhau
ở 0,66 m).

Dấu hiệu đầu tiên là `decision_utility` **giống hệt tới 16 chữ số** giữa run 30 và run 100
episode: `0.8205179005094823`. Với 70 episode mới, trung bình theo tập phải xê dịch ít nhất ở
chữ số thứ tư.

**Sửa ở `contracts 6.0.0`, ba tầng:** G2 đếm episode phân biệt · obstacle `periodic` phải dịch
trọn chu kỳ · và bảng cổng in cả `n_runs` lẫn `n_distinct_episodes`.

## Lỗi phụ: trung vị in cạnh khoảng tin cậy của trung bình

```
ΔU median +0,013123,  CI95 [+0,002783, +0,011141]
```

Trung vị **nằm ngoài** khoảng. Không phải lỗi tính: `delta_u_vs_second` là **trung vị** (HĐ-11.3),
`ci95` là khoảng của **trung bình** (+0,007134, HĐ-11.2). Ở run 30 episode trung vị tình cờ nằm
trong khoảng nên không ai thấy.

Sửa ở `contracts 6.0.0`: thêm `delta_u_mean`.

## Hai thứ nữa, phát hiện muộn hơn ở `contracts 6.1.0`

- **`threshold_ms: 100.0`** — ngưỡng G4 đến từ `control_period: 0.1`, một nhượng bộ 10 Hz khai vì
  "DWA Python không tính nổi một bước trong 50 ms". Ngay trên tấm card này có bằng chứng nhượng
  bộ đó đã lỗi thời: p99 gộp đo được là **10,81 ms** và **16,10 ms**, thừa dưới 50 ms. Cả hai
  profile nay về 20 Hz.
- **`benchmark_host: cores_allocated 1, threads 1`** — số hardcode trong script. Run này **thật
  sự** được ghim 2 nhân (đó là lý do p99 của RRT\* xuống 16,10 ms từ 59,30 ms), nhưng manifest
  không ghi được điều đó vì không có trường nào cho nó và không ai đo. `hostinfo.py` sửa.

---

## Điều tấm card này làm đúng, và đáng giữ vì nó

Bốn thứ được sửa **trước** lần chạy này đều là sửa thật, và cả bốn đều làm kết luận **yếu đi**
hoặc thận trọng hơn, không cái nào làm đẹp kết quả:

- `simulate()` chuyển sang xen kẽ context-outer (HĐ-3.2) — tải máy thành nhiễu chung, triệt tiêu
  trong hiệu số ghép cặp. Bằng chứng: một phần năm cuối run chậm hơn hẳn nhưng đập vào cả hai
  candidate gần bằng nhau (tỷ lệ 1,06 so với 1,078 toàn run).
- `--episodes` thôi ghi đè số suy từ rủi ro khai báo.
- Ghim nhân, lần đầu.

## Ngoài ra

Candidate id `ac187ee7a77e` và `2baaad3628e1` **không còn tồn tại** — DWA nay chạy 20 Hz nên
`candidate_id` đã đổi. Bộ trace của run này (`artifacts/traces/2baaad3628e1`,
`artifacts/traces/ac187ee7a77e`, gitignored, 9,5 MB) được **giữ nguyên làm bằng chứng cho chính
phát hiện này**, không phải làm số liệu nghiệm thu.

## Đọc thêm

- `docs/antongduy/reports/2026-08-11/tongduyan_phase-5-1-mot-tam-card-noi-doi.md` — toàn bộ lượt truy nguyên
- `docs/antongduy/reports/2026-08-11/tongduyan_f0-dua-ve-quy-dao-va-f1-mvp-do-mot-stack.md` — hai lỗi 6.1.0
- `contracts/CONTRACTS.md` §18, mục `6.0.0` và `6.1.0`
