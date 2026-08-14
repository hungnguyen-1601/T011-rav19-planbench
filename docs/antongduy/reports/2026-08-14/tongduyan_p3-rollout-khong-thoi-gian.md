# P3 — rollout không-thời gian: bộ điều khiển lăn thế giới cùng với chính nó

**Ngày:** 2026-08-14
**Plan:** `docs/antongduy/plans/2026-08-14/du-doan-chuyen-dong-vat-can.md`, P3
**Trạng thái:** xong · **chưa chạy full suite, chưa đăng ký registry — chờ lệnh**

---

## 1. Một trục bị thiếu

`DWAPlanner` lăn quỹ đạo của **chính nó** qua horizon rồi đối chiếu với
**một ảnh chụp thế giới tại t=0**, giữ nguyên suốt cả rollout:

```python
diff = points[:, :, None, :] - obstacles[None, None, :, :]
#      (N, K, 2)                (1,  1,  M, 2)   <- không có trục thời gian
```

Hệ quả chạy theo **hai** chiều, và chiều thứ hai mới là chiều ít ai nghĩ
tới:

- **Quá thận trọng** với vật cản đang **rời đi**: người đã bước khỏi cửa
  vẫn còn đứng đó trong đầu rollout, nên khe hở bị chấm là hẹp và robot
  chờ một chỗ **đã trống**.
- **Quá liều** với vật cản đang **tới**: xe đẩy khép ở 1 m/s được chấm
  như đang đỗ, nên quỹ đạo cắt ngang mặt nó được chấm là an toàn.

`dwa_predictive` cho vật cản một trục thời gian của riêng chúng:

```python
diff = points[:, :, None, :] - predicted[None, :, :, :]
#      (N, K, 2)                (1,  K,  M, 2)   <- cùng K
```

---

## 2. Đã thêm gì

| file | nội dung |
|---|---|
| `dwa_predictive/tracks.py` | `ObstacleTrack(center, radius, velocity, confidence)` + `position_at()` |
| `dwa_predictive/planner.py` | `DWAPredictiveConfig`, `DWAPredictivePlanner`, `TrackProvider` |
| `dwa_predictive/__init__.py` | export |
| `common/dwa_core.py` | `rollout_times()` — đồng hồ dùng chung |
| `tests/test_dwa_predictive.py` | 25 test |

**Chưa đăng ký registry** — đó là P6. Ở P3 ứng viên chưa có đường nào tới
`/candidates`, và điều đó đúng: nó chưa có tracker, chỉ chạy được khi ai
đó tiêm track vào.

### 2.1. Một cấu trúc, ba nguồn

`ObstacleTrack` là thứ P4 (oracle ground truth) và P5 (tracker LiDAR) sẽ
**cùng** trả về. Nếu ba nguồn trả ba hình dạng khác nhau thì con số đáng
giá nhất của plan — *giá của việc phải tự ước lượng* — sẽ trộn **sai số
ước lượng** với **sai khác hình học**, và không đọc được nửa nào.

Nên oracle **không** đưa tâm vật cản trong khi tracker đưa centroid cụm.
Cả hai đưa `ObstacleTrack`, và khoảng cách giữa chúng là sai số ước lượng
thuần.

`confidence` có mặt từ P3 dù chưa ai hạ nó: một cấu trúc mọc thêm trường
sau sẽ mọc ở **ba** nguồn cùng lúc.

### 2.2. Track đến từ đâu

`compute()` đọc từ một **provider được tiêm**, không tự dẫn xuất:

```
P3: test tiêm vào       -> đo "lăn thế giới có chạy không"
P4: ground truth        -> đo "dự đoán đáng giá bao nhiêu" với sai số = 0
P5: tracker LiDAR       -> đo "tự ước lượng tốn bao nhiêu"
```

**Không** provider ⇒ không track ⇒ mọi số hạng dự đoán **bằng đúng 0** ⇒
lệnh **giống hệt `dwa`**. Đây là công tắc mọi thứ phía sau dựa vào, và
nó được khẳng định chứ không phải hy vọng.

---

## 3. Cái gì **không** được đổi, và vì sao

Dự đoán mua **tốc độ và sự mượt**, không mua **an toàn**. Cả hai ràng
buộc cứng giữ nguyên như `dwa`:

| ràng buộc | đo trên cái gì |
|---|---|
| Từ chối theo **tập** (`clearances <= keep_out`) | điểm LiDAR **tại thời điểm này** — không đổi một dòng |
| Chặn theo **vận tốc** (`stopping_limit`) | y hệt, đọc cùng `v_obstacle_max` đã khai |

Nếu cho khoảng hở **dự đoán** vào phép từ chối thì
`prediction_horizon_seconds` — một tham số **candidate** — sẽ thu hẹp
miền khả thi cứng mà global planner đã lập kế hoạch dựa vào. Đúng nguyên
văn cái **L2** cấm.

Và có một lập luận độc lập mạnh hơn cả lập luận hợp đồng:

> **Ước lượng dùng để *nới* an toàn thì lỗi ước lượng thành va chạm.
> Ước lượng dùng trong *cost* thì lỗi ước lượng chỉ thành đi kém tối ưu.**

Vận tốc ở đây là ước lượng có **ba chế độ hỏng đã biết** (mục [2] của
plan, hiện thực ở P5). Cho một đại lượng như thế quyền hạ ngưỡng an toàn
là chọn đúng chiều sai.

---

## 4. Hai số hạng chi phí, không phải ba

Plan liệt kê ba: khoảng hở dự đoán, time-to-collision, **và** phạt cắt
mặt vật cản đang tới. Tôi hiện thực **hai**, và gộp cái thứ ba vào TTC:

> Một quỹ đạo cắt ngang mặt thứ đang tới **chính là** một quỹ đạo có
> time-to-collision ngắn. Một trọng số thứ ba không có chế độ hỏng riêng
> là một núm để vặn, không phải một thứ để đo.

| số hạng | trọng số | vì sao |
|---|---|---|
| `predicted_clearance` | **dùng chung `weight_clearance`** | cùng một nguyện vọng, đo trên tương lai — đúng cách `comfort` đã dùng chung. Trọng số riêng sẽ cho phép một ứng viên quan tâm khoảng hở **dự đoán** hơn khoảng hở **thật**, và đó không phải sở thích của ai cả |
| `time_to_collision` | `weight_time_to_collision` **(mới)** | đại lượng thật sự mới: *bao lâu nữa thì gặp nhau*, không suy ra được từ khoảng cách |

**Tham số của tracker chưa có mặt.** Plan liệt kê
`association_speed_limit` và ba ngưỡng phân loại cụm trong
`DWAPredictiveConfig` ở P3. Tôi hoãn sang **P5**, cùng lúc với tracker
đọc chúng: một trường config **không ai đọc** là một núm hiện lên
`/candidates` khai rằng nó đổi được gì đó, và không.

---

## 5. Cái bẫy plan đã gọi tên trước: đồng hồ lệch một bước

`rollout_batch` dựng vị trí bằng `cumsum`, nên **cột `k` là tư thế sau
`k+1` bước**, không phải sau `k` bước. Cột 0 đã ở `horizon_dt` giây trong
tương lai; mảng đó **không bao giờ** chứa tư thế xuất phát.

Vậy vật cản phải được đẩy đi `(k+1)·horizon_dt`, không phải
`k·horizon_dt`. Dùng nhầm cho ra một bộ điều khiển **trễ đúng một nhịp**,
và — đây mới là phần nguy hiểm — **không metric tổng hợp nào lộ ra điều
đó**, vì một dự đoán cũ vẫn là một dự đoán.

Nên đồng hồ nằm trong **một** hàm dùng chung, `dwa_core.rollout_times()`,
thay vì hai chỗ tự viết `arange(steps) * dt` và một chỗ đúng.

Độ lớn của sai lệch, đo được: với track khép ở `u`, mất `u·dt` quãng
tiếp cận — **0.1 m** ở cấu hình chuẩn. Đủ nhỏ để trông như làm tròn trong
mọi con số tổng hợp.

---

## 6. Kiểm bằng mutation, vì "xanh" đã hai lần không đủ

Bốn lần trong plan này một phép đo **xanh** mà đo ít hơn điều nó khai
(tốc độ lúc chạm P0, nội suy P1, `crossing_obstacle` và `allow_reverse`
P2). Nên P3 không dừng ở "test pass" — hai khẳng định đắt nhất bị **cố ý
phá** để xem test có đỏ không.

### 6.1. Đồng hồ — bắt được ngay

Đổi `(arange(steps)+1)*dt` thành `arange(steps)*dt`:

```
3 failed, 20 passed
```

Ba test cùng lớp `TestTheTimeAxisLinesUpWithTheRollout` đỏ. Đạt.

### 6.2. Ranh giới L2 — **lọt**, và đó là phát hiện của mục này

Đổi phép từ chối thành `min(clearances[i], predicted_clearances[i]) <= keep_out`
— tức đúng vi phạm L2 mà cả module viết ra để chặn:

```
43 passed        <- KHÔNG test nào đỏ
```

Vì sao lọt, và nó là một bài học chung:

- lớp `TestTheHardConstraintsAreUntouched` đọc `_dynamic_window`, mà phép
  từ chối **không nằm trong** `_dynamic_window` — nó nằm trong vòng lặp
  của `compute()`;
- lớp `TestWithoutTracksItIsExactlyDWA` chạy episode **không có track**,
  nên `predicted_clearances` là `+inf` và `min(inf, x) == x` — đột biến
  **vô hình**.

**Một test mang tên một ràng buộc thì phải chạm vào ràng buộc đó.**

Đã thêm `test_a_predicted_collision_does_not_refuse_a_measured_clear_command`:
scan **rỗng** (mọi tia cùng tầm ⇒ không return nào) nên mọi ứng viên được
**đo** là thoáng, trong khi một track ngồi gần và khép nhanh nên mọi ứng
viên bị **dự đoán** là vi phạm. Dự đoán được phép làm chúng **đắt**;
không được phép làm chúng **bị từ chối**.

Chạy lại đột biến với test mới:

```
E  + all 288 candidate velocities collide (288 rejected); commanding stop
1 failed, 24 passed
```

Kèm một test chiều ngược lại: track khai vật cản **đang rời đi** không
được **cứu** một lệnh mà phép đo đang từ chối.

---

## 7. Test

`tests/test_dwa_predictive.py` — **25 passed**, tổ chức theo **ba cách
pha này hỏng được**:

| lớp | khẳng định |
|---|---|
| `TestTheTimeAxisLinesUpWithTheRollout` | cột 0 đã đi trước một bước; khoảng cách dự đoán khớp **dạng đóng** tính tay; sai lệch của đồng hồ cũ đúng bằng `u·dt` và hiện thực nằm ở phía đúng |
| `TestTheTensorHasTheShapeTheDocstringClaims` | `(N,)` cho cả hai đầu ra; min lấy trên **cả hai** trục (horizon và track) |
| `TestWithoutTracksItIsExactlyDWA` | lệnh **giống hệt** `dwa` trên 3 cảnh tĩnh; hai số hạng mới **bằng đúng 0**, không phải "nhỏ" — `1e-17` sẽ phá tie-break ở cảnh khác; tập khoá cost = `dwa` **cộng đúng hai** |
| `TestTheHardConstraintsAreUntouched` | cửa sổ lấy mẫu **bằng đúng tập** của `dwa` ở 4 trạng thái; `_speed_that_stops_within` bằng nhau ở mọi `v_obstacle_max`; **phép từ chối** không đọc dự đoán (6.2); track không nới cửa sổ |
| `TestPredictionActuallyChangesTheScore` | một công tắc không bao giờ bật sẽ pass mọi test trên: track **tới** phải đắt hơn track **đi**; TTC hữu hạn chỉ khi có thứ đang tới; `prediction_horizon_seconds` thật sự giới hạn tầm nhìn |
| `TestItIsDeterministic` | hai episode trên một instance = hai instance riêng |

---

## 8. Kiểm chứng

| Việc | Kết quả |
|---|---|
| `tests/test_dwa_predictive.py` | **25 passed** |
| `test_dwa_core_refactor.py` (golden P2) | **20 passed** — `dwa` không dịch một byte |
| `test_dwa.py` · `test_hard_feasible_set.py` · `test_admissible_stopping.py` · `test_nav_stack.py` | gộp chung: **159 passed** (5m15s) |
| Mutation: đồng hồ lệch bước | **bắt được** (3 đỏ) |
| Mutation: dự đoán vào phép từ chối cứng | **lọt lúc đầu** ⇒ đã thêm test ⇒ **bắt được** |
| `ruff check .` | sạch |
| Full backend suite | **chưa chạy — chờ lệnh** |

---

## 9. Còn lại

Tiếp theo là **P4 — oracle**, và nó là **cổng quyết định 2**: với tri
giác *hoàn hảo*, mô hình vận tốc hằng có cải thiện đo được **trên cảnh
gần-hằng** không? Không ⇒ **dừng cả plan**. Đó là chỗ rẻ nhất để huỷ.

P3 để lại ba việc, tất cả đã có chỗ:

- **Tham số tracker** (`association_speed_limit`, ba ngưỡng cụm) → P5,
  cùng lúc với thứ đọc chúng.
- **Đăng ký registry + `CONTROLLER_CONFIGS`** → P6. Hôm nay
  `dwa_predictive` chưa có đường tới `/candidates`, và chưa nên có.
- **`local_version` vẫn cứng `"v1"`** → P6 việc 4. Từ pha này trở đi món
  nợ đã **thành hiện thực**: hai controller dùng chung `dwa_core.py`, nên
  một bản sửa ở lõi đổi **cả hai** ứng viên mà artifact không ghi lại gì.
