# P0 — bảo đảm phanh trước vật cản đang lại gần

**Ngày:** 2026-08-14
**Plan:** `docs/antongduy/plans/2026-08-14/du-doan-chuyen-dong-vat-can.md`, P0
**Trạng thái:** xong · **cổng quyết định 1: DƯƠNG TÍNH ⇒ làm P1**
**Chưa commit, chưa chạy full suite — chờ lệnh.**

---

## 1. P0 hỏi gì

Phase 1b đã biến admissible stopping thành ràng buộc thật: giới hạn tốc
độ đọc khoảng cách tới **vật cản gần nhất** thay vì tới đích, và
`tests/test_hard_feasible_set.py` chứng minh nó đứng vững trên
`sudden_stop` kể cả khi tắt hết số hạng mềm.

Nhưng bảo đảm đó phát biểu trên **lần quét hiện tại**, tức nó nói đúng
một câu: *robot dừng kịp trước chỗ vật cản **đang** đứng*. P0 hỏi câu
tiếp theo — khi vật cản **đang lao tới**, khe hở co theo `(v + u)` trong
khi robot chỉ dự trù `v`.

Hai biểu thức, đo ở **mọi bước**:

```
static_required_gap = v·T + v²/(2a)                  <- cái controller đang cưỡng chế
moving_required_gap = (v+u)·T + v²/(2a) + u·v/a      <- cái thế giới đòi hỏi
```

`u·v/a` là quãng vật cản đi trong `t_stop = v/a` giây robot phanh;
`(v+u)·T` là quãng **cả hai** cùng khép trong một chu kỳ phản ứng. Với
`u = 0` biểu thức thứ hai **trùng khít** biểu thức thứ nhất — nó là phần
mở rộng chặt, không phải luật khác.

**Bằng chứng là trạng thái kẹp, không phải va chạm.** Một bước có
`static ≤ gap < moving` là một bước controller chấm là an toàn mà thế
giới thì không — đó chính là khuyết tật. Đợi va chạm sẽ làm kết quả phụ
thuộc vào việc cảnh này có đủ chỗ lách hay không, trong khi P0 hỏi về
**bảo đảm**, không hỏi về một cái sảnh.

Đây cũng là chỗ bản đầu của plan có thể **âm tính sai**: nó chỉ ghi biểu
thức tĩnh, mà biểu thức tĩnh đúng bằng thứ `stopping_limit` đang cưỡng
chế, nên nó xanh ở gần như mọi bước.

---

## 2. Dụng cụ đo

`tests/test_admissible_stopping.py` (mới, 28 test). Không sửa một dòng
code sản phẩm nào — P0 là phép đo.

**Cảnh:** sảnh trống `open_space`, robot đi từ `(1.5, 4.5)` tới
`(9.5, 4.5)`, một xe đẩy `WaypointMotion` (bán kính 0.4 m, `loop=False`)
lao thẳng ngược chiều xuống đúng làn đó từ `x = 11.5`. Head-on và **trong
chỗ trống có chủ đích**: một hành lang sẽ trộn lẫn *"không dừng kịp"* với
*"không còn chỗ né"*, mà câu hỏi ở đây chỉ là giới hạn tốc độ có đúng
không.

**Robot:** đúng xe của `open_hall_v2` / `warehouse_a_v2` —
`radius=0.26`, `v_max=0.8`, `a=0.5`. **Tắt toàn bộ bảy luồng nhiễu**: P0
hỏi số học của giới hạn tốc độ có đủ không, nhiễu sẽ đặt lời giải thích
thứ hai lên mọi con số.

**Đo trên pose thật và tâm vật cản thật**, khoảng hở **bề mặt tới bề
mặt** (tâm-tới-tâm trừ 0.4 trừ 0.26). Đo trên pose tin-là sẽ là tự chấm
bài mình — đúng lỗi đọc mà phase 1b đã phải sửa một lần. `u` là thành
phần vận tốc **hướng về robot**, lấy từ ground truth qua `position_at`:
hợp lệ ở đây và **chỉ ở đây**, vì đây là test phán xử controller chứ
không phải controller cảm nhận thế giới.

`T` là **control period của chính controller** (0.05 s ở `dwa_balanced`),
không phải `simulation_dt` — vì đó là thời gian phản ứng mà bảo đảm được
phát biểu bằng.

---

## 3. Bảng kết quả

`astar+dwa`, `dwa_balanced`, tắt hết nhiễu:

| tốc độ xe đẩy | **trọng số đối kháng** | | | **trọng số đang ship** | | |
|---|---|---|---|---|---|---|
| (m/s) | kết cục | bước kẹp | gap nhỏ nhất | kết cục | bước kẹp | gap nhỏ nhất |
| 0.001 (đứng yên) | success | 0 | 1.624 | success | 0 | 1.624 |
| 0.10 | success | 0 | 0.584 | success | 0 | 0.567 |
| 0.15 | success | 21 | **0.005** | **collision** | 1 | −0.001 |
| 0.20 | **collision** | 6 | −0.026 | **collision** | 24 | −0.007 |
| 0.30 | **collision** | 11 | −0.026 | **collision** | 25 | −0.017 |
| 0.60 | **collision** | 17 | −0.051 | **collision** | 19 | −0.020 |
| 1.00 | **collision** | 19 | −0.064 | **collision** | 20 | −0.037 |
| 1.50 | **collision** | 21 | −0.015 | **collision** | 22 | −0.104 |

"Trọng số đối kháng" = `weight_clearance=0`, `horizon_seconds=0.5` —
đúng công thức đã lộ lỗ hổng phase 1b lần trước. "Đang ship" = giá trị
mặc định của `dwa_balanced`, không đổi gì.

---

## 4. Đọc bảng — ba điều, và điều thứ ba mới là điều nặng nhất

### 4.1. Dương tính, và rộng hơn plan giả định

Plan đoán lỗ hổng mở ra quanh **1.0 m/s** của một người đi bộ. Nó mở ra
giữa **0.10 và 0.20 m/s** — chậm hơn người đi dạo, và **thấp hơn mọi
`v_obstacle_max` mà một tác giả deployment sẽ nghĩ tới việc khai**. Một
lỗ hổng chỉ hở trước xe nâng 1.5 m/s là ca hiếm; lỗ hổng này thì không.

Hàng 0.15 m/s đáng đọc riêng: trọng số đối kháng **thoát**, nhưng thoát
với khe hở nhỏ nhất **5 mm** và **21 bước kẹp**. Đó không phải an toàn,
đó là may.

### 4.2. Dụng cụ đã được hiệu chuẩn

Xe đẩy đứng yên (0.001 m/s, đi 60 mm suốt cả episode, **cùng luật chuyển
động** với các hàng còn lại chứ không phải static obstacle): **0 vi phạm
cả hai biên**, success, và vẫn tiến tới cách robot dưới 2 m — tức số 0 là
vì robot xử lý được, không phải vì đo nhầm vật cản. Hàng 0.10 m/s cũng
sạch, khe hở gần nhất 0.584 m.

Nghĩa là mọi vi phạm ở các hàng dưới **đến từ chuyển động khép lại**, chứ
không phải từ số học của phép đo hay từ một hồi quy của phase 1b.

### 4.3. **Trọng số đang ship không cứu được — nó còn tệ hơn**

Đây là điều tôi không lường trước và nó đổi mức độ nghiêm trọng của phát
hiện. Cấu hình đang ship **va chạm ở mọi tốc độ trong bảng**, và ở
0.15 m/s nó **va chạm đúng chỗ cấu hình đối kháng còn lách qua được**.

Trước phase 1b, an toàn trên `sudden_stop` tựa vào `weight_clearance`
tình cờ đủ lớn. Ở đây nó **không tựa vào gì cả**. Nên lỗ hổng này không
phải tạo tác của hai núm vặn đối kháng — nó là hành vi của deployment
đang chạy hằng ngày.

---

## 5. Cơ chế, và nó **minh oan cho code**

Trải từng bước ở `u = 1.0 m/s`:

```
 t      gap      v      u   static  moving   trạng thái
4.25   2.310   0.800  1.000  0.680   2.330   kẹp
 ...    ...     ...    ...    ...     ...    kẹp  (21 bước liên tiếp)
5.15   0.690   0.800  1.000  0.680   2.330   kẹp
5.20   0.601   0.775  1.000  0.639   2.239   VỠ BIÊN TĨNH  <- bắt đầu phanh
5.25   0.514   0.750  1.000  0.600   2.150   VỠ BIÊN TĨNH
 ...                                          giảm 0.025 m/s mỗi bước = a·T, kịch trần
5.40                                          "all 24 candidate velocities collide; commanding stop"
5.60  -0.064                                  COLLISION
```

**Không có gì trục trặc ở t=5.20.** Robot xả tốc độ đúng
`max_linear_acceleration` ngay từ bước đầu tiên tiêu chuẩn của chính nó
bị vi phạm — test khẳng định điều đó ở mọi bước sau đó, sai số 1e-6. Nó
muộn vì **tiêu chuẩn được đo với một chiếc xe đẩy chỉ đứng yên bên trong
mô hình thế giới của controller**.

21 bước trước đó, robot chạy 0.800 m/s với `static = 0.680` và
`gap ≥ 0.690`: **hợp lệ theo đúng bảo đảm phase 1b, ở từng bước một.**
Cần 2.330 m, có 2.310 m rồi 0.690 m. Tới lúc buộc phải phản ứng thì
không còn lệnh khả nhận nào — cửa sổ động ở `v ≈ 0.675` chỉ với tới được
`v ∈ [0.65, 0.70]`, và mọi `ω` trong đó đều va chạm.

**Lỗ hổng nằm ở lớp 2** — đúng chỗ phase 1b vừa dựng lên để an toàn thôi
phụ thuộc trọng số của candidate. Bảo đảm đó **vẫn đang thủng**, chỉ là
thủng theo trục **thời gian** thay vì trục **trọng số**.

---

## 6. Test đã viết

`tests/test_admissible_stopping.py` — **28 passed**, 15.6 s.

| nhóm | khẳng định gì |
|---|---|
| `TestTheTwoExpressionsAreOneExpression` | `moving` **mở rộng** `static`, không thay thế: `u = 0` ⇒ hai biểu thức bằng nhau (lời hứa backward-compatible của P1 được kiểm **ở đây**, không phải được giả định ở đó); và biểu thức tĩnh đúng là thứ `_speed_that_stops_within` giải |
| `TestTheProbeIsCalibrated` | xe đẩy đứng yên ⇒ 0 vi phạm cả hai biên; và nó **vẫn được nhìn thấy** (gap < 2 m), nên số 0 không phải do đo nhầm vật |
| `TestTheGuaranteeDoesNotCoverAnApproachingObstacle` | **phát hiện P0**: trạng thái kẹp tồn tại ở mọi tốc độ trong `{0.2, 0.3, 0.6, 1.0, 1.5}`; episode kết thúc bằng va chạm; **trọng số đang ship cũng vậy**; cơ chế phanh-kịch-trần-mà-vẫn-muộn; và lỗ hổng mở dưới tốc độ đi bộ |

**Ba điều về cách viết, cả ba là bẫy đã sập trong repo này:**

1. **Test này khẳng định một khuyết tật, có chủ đích.** Docstring của lớp
   ghi thẳng: *P1 lật ngược mọi khẳng định ở đây* — cùng dụng cụ, đọc lần
   thứ hai, và phép đo phải về **0** ở mọi tốc độ. Kèm câu cảnh báo:
   nếu chúng xanh mà **chưa** có P1 thì thứ bị dịch là dụng cụ, không
   phải controller.
2. **Hàng 0.15 m/s không vào assertion**, chỉ nằm trong docstring. Nó là
   hàng biên, và một khẳng định ngưỡng đặt đúng ở biên là một lần tung
   đồng xu.
3. **Công thức nằm ở một helper duy nhất** (`required_gaps`), vì P1 sẽ
   cưỡng chế đúng biểu thức đó. Một thước, hai lần đo.

---

## 7. Kết luận và việc tiếp theo

**Cổng quyết định 1: DƯƠNG TÍNH.** Theo plan (mục 11.0), nhánh này ⇒
**làm P1** — `v_obstacle_max` ở lớp 2, validator 5b, áp cho **cả hai**
controller như nhau.

Ba hệ quả phải nói rõ, vì chúng đổi thứ tự việc:

- **P1 không còn là "nếu"** — 1.5–2 ngày, và nó đứng trước P2/P3/[1][2].
- **Bắt buộc `task_profile_id` mới** cho mọi deployment muốn đo dưới ràng
  buộc này. `v_obstacle_max` là ràng buộc deployment và **đổi cả hai ứng
  viên**, nên nó đổi *episode là cái gì*.
- **`dwa_predictive` không hưởng lợi gì từ P1**, và đó là chủ đích: nếu
  chỉ ứng viên dự đoán mới an toàn trước vật cản đang tới thì phép so đo
  **an toàn** chứ không đo **dự đoán** — đúng lập luận đã dùng để đẩy
  recovery lên deployment.

Một điều P0 **không** trả lời, ghi ra để không ai đọc quá: cảnh này chạy
**không nhiễu**. Nó nói lỗ hổng có thật trong số học của giới hạn tốc độ;
nó **không** nói gì về độ bền của biên mới trước nhiễu định vị — đó là
pha hệ toạ độ ở mục 2c của plan, vẫn đứng ngoài phạm vi.

**Đối xứng với P1, nhắc lại để lần sau khỏi nghĩ lại:** `moving_required_gap`
chính là bất biến P1 cưỡng chế. P0 đếm số bước vi phạm nó
(6 / 11 / 17 / 19 / 21 ở bốn tốc độ + 0.2); P1 xong thì **đúng phép đo đó
phải về 0**, và mọi hàng `collision` phải thôi là `collision`.

---

## 8. Kiểm chứng

| Việc | Kết quả |
|---|---|
| `tests/test_admissible_stopping.py` | **28 passed** (15.6 s) |
| `tests/test_hard_feasible_set.py` (phase 1b, hàng xóm) | 25 passed (65 s) |
| `ruff check` trên file mới | sạch |
| `ruff format --check` trên file mới | sạch |
| Full backend suite | **chưa chạy — chờ lệnh** |
| Code sản phẩm đổi | **không một dòng** |
