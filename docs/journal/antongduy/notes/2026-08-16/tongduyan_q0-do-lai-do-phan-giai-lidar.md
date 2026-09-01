# Q0 — đo lại độ phân giải LiDAR, và plan mất tiền đề

**Loại:** quan sát/đánh giá. Không đổi một dòng code sản phẩm nào.
**Ngày:** 2026-08-16
**Thuộc:** pha Q0 của plan `plans/2026-08-16/sua-tri-giac-dwa-predictive.md`
**Dữ liệu:** `artifacts/q0_resolution/sweep.json` (160 episode, 27.6 phút),
`artifacts/q0_resolution/phantom.json` (32 episode, 5.6 phút)
**Script:** `scripts/diagnose_resolution.py`

---

## 0. Q0 tồn tại để làm gì, và nó đã làm đúng việc đó

Plan 16-08 được dựng trên một bảng đo **một seed**, trung vị lấy trên
2–17 frame. Q0 là pha chạy lại ở N ≥ 20 trước khi sửa bất cứ thứ gì, và
plan đã ghi sẵn rủi ro của nó:

> Q0 có thể huỷ toàn bộ phần còn lại. Đó là mục đích của nó.

Nó đã huỷ. Hai phát hiện dưới đây, cái thứ nhất bác bỏ bảng cũ, cái thứ
hai bác bỏ hướng đi của cả plan.

---

## 1. Thiết lập

| | |
|---|---|
| Deployment | `warehouse_crossing_v1`, AMR cắt ngang 0.8 m/s hằng số |
| Candidate | `astar+dwa_predictive : dwa_predictive_balanced` |
| Seed | **calibration A = 1000..1019** (N = 20); dải 0..119 đã cháy |
| Nhánh | có traffic, và **cùng deployment rút hết traffic** |
| Không đo | latency — chạy song song 10 worker, p99 ở đây vô nghĩa (thuộc Q5) |

Nhánh tĩnh là bắt buộc chứ không phải phụ: chỉ đo cảnh có traffic thì
**mọi** thay đổi làm tracker nhạy hơn đều trông như cải thiện. Trên cảnh
tĩnh, theo định nghĩa, mọi vận tốc báo ra đều là ảo.

---

## 2. Bảng chính — N = 20

### Cảnh có traffic

```
 rays   deg  enc/eps  in_range  rays/f  clustered  passed  vel_out   err_med    n
   72  5.00    17/20      2394    1.77      24.4%    2.0%     0.9%     0.429   22
  144  2.50    17/20      2403    3.55      33.1%    4.6%     3.5%     0.935   84
  271  1.33    17/20      2368    6.49      41.6%    5.2%     4.1%     0.813   97
  360  1.00    17/20      2393    8.66      45.5%    5.6%     4.5%     0.864  107
```

### Cảnh tĩnh — mọi vận tốc đều là ảo

```
 rays   phantom_rate   phantom_p90   tracks/f   per-track
   72         14.17%         1.868       4.32       3.54%
  144         78.56%         1.515      11.02      14.53%
  271         97.52%         1.820      19.39      21.98%
  360         99.19%         2.023      25.72      22.88%
```

`phantom_rate` = tỉ lệ frame có **ít nhất một** vật chuyển động giả —
đây là thứ thật sự đi vào hàm cost. `per-track` = tỉ lệ track riêng lẻ
mang vận tốc giả.

---

## 3. Phát hiện 1 — bảng một-seed của plan **bị bác bỏ**

Bảng §1.4 của plan nói: đỉnh ở 144 tia, **thoái lui** ở 271 và 360.

Ở N = 20 **không có thoái lui nào**. `vel_out` tăng đơn điệu:

| | một seed | N = 20 |
|---|---|---|
| 72 | 1.4% | 0.9% |
| 144 | **11.8%** | 3.5% |
| 271 | 9.0% | 4.1% |
| 360 | 8.7% | 4.5% |
| `err_med` @144 | **0.164** | **0.935** |

Con số `0.164 m/s` từng là bằng chứng mạnh nhất cho "144 tia là điểm
ngọt" — ở N = 20 nó là **0.935 m/s**, tức sai số cỡ chính tốc độ cần đo.
Nó là ăn may với n nhỏ.

**Phải xoá khỏi plan:** toàn bộ mệnh đề không-đơn-điệu, và cả cơ chế
"tường vỡ vụn ⇒ `ambiguous_drops` bùng nổ ⇒ track thật bị hi sinh" mà
tôi dựng ra để giải thích nó. Cơ chế đó có thật (số `ambiguous_drops`
2 → 894 là số đo được), nhưng nó **không** gây ra thoái lui ở đầu ra —
vì không có thoái lui.

---

## 4. Phát hiện 2 — cái giá thật của độ phân giải

Đi từ 72 lên 360 tia:

```
phát hiện thật:  0.9%  ->  4.5%     ( x5 )
ảo giác:        14.2%  -> 99.2%     ( x7 )
```

Ở 360 tia, trong một nhà kho **không có gì chuyển động**, tracker báo có
vật đang di chuyển ở **99.19% số frame**. p90 tốc độ ảo 2.02 m/s — gấp
2.5 lần traffic thật.

**Objective, khai trước khi bảng tồn tại**, áp vào:

```
ràng buộc cứng: phantom_rate <= baseline 72 tia (14.17%)
  144 tia  78.56%  TRƯỢT
  271 tia  97.52%  TRƯỢT
  360 tia  99.19%  TRƯỢT
=> cấu hình hợp lệ duy nhất: 72 tia — chính cái đang chạy
```

---

## 5. Cơ chế — sàn vận tốc mô hình sai đại lượng

Câu hỏi tôi tự đặt trước khi có số: mức tăng ảo là do **nhiều track hơn**
hay **mỗi track tệ hơn**? Đo riêng để trả lời, và đáp án là **cả hai**:

```
tracks/frame:   4.32  -> 25.72     ( x6.0 )
per-track ảo:  3.54%  -> 22.88%    ( x6.5 )
```

Hai thừa số nhân nhau ra 14% → 99%.

Vế thứ hai mới là vế quan trọng, vì nó nói **giảm số track rác là không
đủ**. Bằng chứng nằm ở một cột trông có vẻ tầm thường:

```
phantom_p90:  1.868   1.515   1.820   2.023      <- gần như PHẲNG
```

Biên độ vận tốc ảo **không đổi** theo độ phân giải. Trong khi đó sàn
chặn nó co lại tuyến tính:

```
velocity_floor = (2·σ_pose + margin·σ_range + reach·Δθ) / window
                                              ^^^^^^^^^
tại 4 m:  72 tia -> 0.584 m/s        360 tia -> 0.186 m/s
```

Số hạng `reach·Δθ` — thứ tôi thêm vào ở P5 để mô hình hoá lượng tử hoá
tia — đang gánh gần như toàn bộ việc chặn ảo ở 72 tia. Nó giả định
**biên độ ảo tỉ lệ với khoảng cách tia**. Phép đo nói biên độ ảo
**không phụ thuộc khoảng cách tia**.

Nghĩa là sàn đúng ở 72 tia vì **trùng hợp về độ lớn**, không phải vì mô
hình đúng. Nguồn ảo trội thực sự là centroid trượt dọc bề mặt khi robot
di chuyển — phụ thuộc chuyển động của robot, không phụ thuộc Δθ.

---

## 6. Hệ quả cho plan

Tiền đề trung tâm của plan 16-08 là:

> tăng độ phân giải là đòn bẩy chính; Q1 làm cảm biến khai được, Q2 làm
> ngưỡng co giãn theo cảm biến để việc tăng tia thôi phản tác dụng.

Tiền đề này **không đứng vững**. Q1 + Q2 như đang viết sẽ mở đường cho
một cấu hình mà tracker ảo giác gần như mọi frame.

Và Q2b (test tường theo tính liên tục) — pha tôi đặt nhiều kỳ vọng nhất
— chỉ tấn công thừa số `tracks/frame`. Kể cả nếu nó hoàn hảo, đưa
25.72 track/frame về 4.32, thì `per-track` vẫn 22.88% thay vì 3.54%, và
phantom_rate ở 360 tia vẫn cao hơn baseline nhiều lần.

**Thứ tự đúng đảo lại:** sàn vận tốc phải được thiết kế lại **trước**,
dựa trên một mô hình biên độ ảo khớp với phép đo (phẳng theo Δθ, phụ
thuộc chuyển động robot). Mọi việc về độ phân giải chỉ có nghĩa sau đó.

Đề xuất cụ thể để dev chốt: xem mục "Đề xuất sửa plan" trong phần cập
nhật của `plans/2026-08-16/sua-tri-giac-dwa-predictive.md`.

---

## 7. Ba thứ về phương pháp, lộ ra khi dựng harness

**(a) Bản đo đầu tiên là bản đo hư, và nó im lặng.**
`DWAPredictivePlanner.reset()` dựng `LidarTracker` **mới** (có chủ đích),
còn `run_stack` gọi `reset` sau khi caller kịp bọc instance. Wrapper bị
vứt trước scan đầu tiên ⇒ episode chạy **thành công**, mọi counter bằng
0, bảng đọc ra "tracker không thấy gì" thay vì "không ai đang đo".
Script giờ bọc ở mức class, khôi phục trong `finally`, và **ném lỗi khi
`frames == 0`**.

**(b) "N seed" không phải cỡ mẫu.** Chỉ **17/20 seed** có cuộc gặp; có
seed vào tầm 83 frame mà 0 tia chạm (che khuất hoàn toàn). Bảng in cột
`enc/eps` để người đọc không suy cỡ mẫu từ chữ "20 seed".

**(c) Ghim BLAS về 1 luồng là đòn bẩy tốc độ, không phải chi tiết.**
10 worker ở cấu hình mặc định chạy chậm gần bằng 1 worker — các luồng
numpy giành đúng số core mà script muốn dùng cho episode. Ghim xong:
160 episode trong 27.6 phút. Ghi trong script kèm số đo, vì nó là điều
kiện để phép đo này khả thi.

Ngoài ra script hỗ trợ `--resume`: mỗi episode ghi ra JSONL ngay khi
xong, và **dòng mang checksum code controller** — resume sau khi sửa
tracker sẽ **từ chối** dòng cũ thay vì trộn hai phiên bản vào một bảng.

---

## 8. Cái note này **không** kết luận

- Không nói mô hình vận tốc hằng vô dụng — P4 (oracle) đã bác điều đó.
- Không nói `dwa_predictive` nên bị rút. Đó là quyết định sau cổng Q4,
  và Q4 chưa chạy.
- Không đo latency hay bộ nhớ. Thuộc Q5.
- Không nói gì về độ bền trước nhiễu định vị — L17 vẫn treo, và mọi số
  ở đây chạy với `localization_drift_m = 0`.
