# P6 — nối `dwa_predictive` vào nền tảng, và trả hai món nợ

**Ngày:** 2026-08-15
**Plan:** `docs/antongduy/plans/2026-08-14/du-doan-chuyen-dong-vat-can.md`, P6
**Trạng thái:** xong cả sáu việc · **chưa chạy full suite — chờ lệnh**
**Commit:** `22d6068`

---

## 1. Việc của pha này

Đưa ứng viên đi được hết đường từ registry tới Decision Card. Và trả hai
món nợ mà plan đã ghi từ mục 6: cả hai **vô hại khi chỉ có một
controller**, và cả hai **thôi vô hại ngay khi có hai**.

Bối cảnh phải nói trước: **P5 đóng bằng kết quả âm** — tracker không
giành lại được lợi ích của oracle ở cấu hình 72 tia. P6 vẫn đăng ký ứng
viên, và đó là đúng: plan nói rõ một tấm Decision Card ghi *"đừng dùng
predictive ở deployment này"* là một tấm card **thành công**. Nhưng nó
chỉ thành công nếu ứng viên **đi được hết đường** để tấm card đó tồn tại.

---

## 2. Đăng ký (việc 1, 2)

Hai stack mới trong `registry.py`: `astar+dwa_predictive`,
`rrtstar+dwa_predictive`. Cả hai `benchmarkable=True`.

**Vẫn `lidar_only`, và đó là điểm mấu chốt.** Lấy vận tốc từ engine sẽ
biến nó thành `lidar+human_states`, và bảng xếp hạng **mặc định từ chối**
xếp chung hai lớp quan sát khác nhau — đúng như vậy: một ứng viên được
cho biết mọi thứ ở đâu sẽ thắng vì một lý do **không liên quan gì đến dự
đoán**. Có test khẳng định điều này cho cả hai stack.

**Mô tả lên thẳng `/candidates`, nên nó phải nói ra hai thứ mà người đọc
sẽ mặc định bỏ qua:**

> Vận tốc vật cản **được ước lượng** từ LiDAR của chính robot — không
> được cho — nên sai số của estimator là một phần của ứng viên. **Mô hình
> là vận tốc hằng**, sai ngay khi có gì đó rẽ hoặc dừng. Vật cản không
> được giả định né robot. Dự đoán chỉ vào chi phí: miền cứng và giới hạn
> phanh **giống hệt** `dwa`.
>
> Đo 15-08 trên `intersection`: với tri giác **hoàn hảo** thì ý tưởng
> đáng giá (11/11 cặp bất đồng nghiêng về nó, p = 0.0005), nhưng tracker
> LiDAR **không giành lại được gì** — xem L16.

Test khẳng định chuỗi `"estimated"` và `"constant velocity"` có mặt trong
mô tả. Một mô tả đúng hôm nay mà lặng lẽ bị rút gọn sau này thì lại thành
một ứng viên trông tự tin hơn nó có quyền.

**Ba config, cùng mật độ lấy mẫu với `dwa`:**
`dwa_predictive_{coarse,balanced,default}`. Cùng
`velocity_samples`/`omega_samples`/`control_period` với ba mức của `dwa`,
để **trục latency G4 so được**. Một stack dự đoán mà cũng lấy mẫu thưa
hơn sẽ trộn hai thay đổi vào một số đọc; giữ nguyên mật độ thì phần đắt
thêm **chính là** tracker cộng phép broadcast không-thời gian.

Tên đầy đủ `dwa_predictive_*`, không viết tắt `pred`: việc 3 đối chiếu
tên config với controller, và các chuỗi này nằm **nguyên văn** trong mọi
report đã lưu.

---

## 3. Nợ 1 — tên config mượn của controller khác (việc 3)

**Lỗ hổng sống cho tới hôm nay.** Tên config nằm trong **một namespace
phẳng** và không chỗ nào kiểm cặp `(stack, config)`. `dwa_coarse` chỉ khai
mật độ lấy mẫu, và **mọi khoá của nó cũng là trường hợp lệ của
`DWAPredictiveConfig`** — nên:

```
astar+dwa_predictive : dwa_coarse
```

**chạy được**, và report lưu lại ghi `local_controller_config: dwa_coarse`
bên cạnh một ứng viên **không phải** `dwa`. Episode không sai gì; **bản
ghi** thì sai.

`CONTROLLER_OF_CONFIG` đã được dẫn xuất và export từ trước, **chưa ai
đọc**. Giờ nó có người đọc: `validate_config_names()`, gọi **đầu tiên**
trong `build_candidates` — trước khi dựng ứng viên, vì một cặp lệch dựng
lên hoàn toàn bình thường và chỉ lộ ra trong chính cái report nó sắp dán
nhãn sai.

Kiểm chứng:

```
OK       astar+dwa            : dwa_balanced
OK       astar+dwa_predictive : dwa_predictive_balanced
REFUSED  astar+dwa_predictive : dwa_coarse
REFUSED  astar+dwa            : dwa_predictive_default
REFUSED  astar+dwa            : nope            (tên không tồn tại)
```

Thông điệp viết cho **người đang chọn**, nêu luôn tên đúng nên dùng.

**Một test giữ cho phép kiểm này khỏi thành code chết:**
`test_the_borrowed_pair_really_would_have_run` dựng thẳng
`astar+dwa_predictive` với `dwa_coarse` và khẳng định nó **build được**.
Nếu ngày nào đó `dwa_coarse` thôi hợp lệ với config dự đoán, cặp kia sẽ
hỏng vì lý do khác và `validate_config_names` sẽ chỉ còn là trang trí —
test này bắt đúng lúc đó.

---

## 4. Nợ 2 — `local_version` luôn là `"v1"` (việc 4)

`candidate_from_stack` nhận `local_version: str = "v1"` và **không caller
nào từng truyền vào** — `selection.py`, `decision_service.py`,
`measure.py` đều để mặc định. Nên **mọi candidate nền tảng từng sinh ra
đều là `v1` vĩnh viễn**, trong khi docstring của `StackComponent` hứa
ngược lại: *"cùng một DWA sau khi sửa lỗi là một candidate khác"*.

Id nói hai lượt chạy là **cùng một ứng viên** trong khi code bên dưới đã
đổi.

**Vì sao món nợ này *nặng thêm* chứ không chỉ *cũ đi*:** từ P2 hai
controller **dùng chung** `dwa_core.py`. Một bản sửa ở đó đổi hành vi của
**cả hai** — và cả hai id sẽ đứng yên.

**Đã sửa:** `local_version` mặc định thành checksum của **source
controller cộng lõi dùng chung**:

```
dwa             67faa4f26e01   (planner + dwa_core)
dwa_predictive  4f842cacffa3   (planner + tracking + tracks + dwa_core)
pure_pursuit    v1             (fallback: không benchmarkable)
ppo             v1             (fallback: đã mang checksum checkpoint)
```

Băm **văn bản source** chứ không phải một số người tự khai: một con số do
người bảo trì là một con số người ta quên, và cái hỏng thì **im lặng**.
Docstring và comment cũng vào checksum — chúng không đổi được hành vi,
nhưng một checksum cố bỏ qua chúng sẽ phải parse Python để quyết định cái
gì quan trọng, và **nhạy quá** là chiều sai an toàn cho một định danh.

### Quyết định của An: **(a) chấp nhận đứt gãy**

Plan để ngỏ ba phương án và đòi chốt **trước** khi bắt đầu P6. An chọn
(a): checksum cho **mọi** controller.

**Hệ quả, nói thẳng: mọi `candidate_id` đang tồn tại đều đổi.** Run đã lưu
giữ id cũ như dữ liệu lịch sử và **không khớp** id mà cùng stack sinh ra
bây giờ.

Lý do (a) đúng hơn (b) *"chỉ áp cho controller mới"*: (b) để lại đúng lỗ
hổng đang vá cho **một nửa** registry — và tệ hơn, với hai controller
dùng chung `dwa_core`, một sửa lỗi ở lõi sẽ đổi id của `dwa_predictive`
mà **không** đổi id của `dwa`, tức hai ứng viên chạy cùng một bản sửa mà
hồ sơ ghi khác nhau. Nền tảng cũng đã có tiền lệ *"không sửa tại chỗ, tạo
mới"* (`same_deployment`).

`local_version` vẫn còn là tham số tường minh — một caller dựng lại
candidate **lịch sử** phải nói được nó chạy code nào, và chính những id
đã lưu là lý do tham số đó sống.

---

## 5. Việc 5 và 6

**Việc 5 — nhãn UI cho oracle: về 0**, đúng như plan vòng 3 dự đoán.
Oracle **không đăng ký nổi** registry (factory có chữ ký
`config -> LocalPlanner`, không có scenario để đóng provider vào), nên nó
không bao giờ lên `/candidates`. Có test khẳng định registry không biết
nó.

**Việc 6 — `KNOWN_LIMITATIONS.md`, thêm L13–L17:**

| | nội dung |
|---|---|
| **L13** | Mô hình **vận tốc hằng** — sai ngay khi có gì rẽ/dừng. `PeriodicMotion` sai số ngoại suy trung vị **0.949 m** sau 1.5 s |
| **L14** | **Bốn** nguồn vận tốc ma. Ba cái plan liệt kê, cộng một cái plan không lường: **lượng tử hoá quét**, tồn tại **với cảm biến hoàn hảo**. Đo được 0.28–0.41 m/s trung vị, đỉnh 1.27 |
| **L15** | Vật cản **không** né robot — không RVO/ORCA, vì `dynamic.py` là hàm thuần không phản ứng |
| **L16** | **11 cơ hội, tracker lấy 0** ở 72 tia. Nút thắt là **tần suất phát hiện** (1.6%), không phải độ chính xác (sai số 15% khi có báo) |
| **L17** | **Chưa đo dưới nhiễu định vị** — pha hệ toạ độ còn treo, nên P7 phải chạy `localization_drift_m = 0` |

L16 kèm một câu cho người đọc Decision Card sau này, vì nó dễ bị đọc
nhầm nhất:

> Card nói `dwa_predictive` ngang `dwa` là card **đúng**. Nó **không**
> nói mô hình dự đoán vô dụng — oracle đã bác điều đó với `p = 0.0005`.
> Nó nói **cảm biến này không đủ để ước lượng cái mô hình cần**.

---

## 6. Hàng rào L4 mở rộng, và một chỗ chính test tự mắc lỗi vừa cấm

`STACKS` trong `tests/test_hard_feasible_set.py` từ hai lên **bốn** —
thêm cả hai stack dự đoán. Đây là ca sẽ bắt được một số hạng dự đoán rò
vào **miền cứng** ở đúng mức hợp đồng phát biểu: một ứng viên có sự thận
trọng thêm nằm ở **phép từ chối** thay vì ở **chi phí** sẽ bắt đầu loại
những đường mà global planner có quyền trả về.

**Và helper của chính test đó đang mắc đúng lỗi việc 3 vừa cấm.** `_run`
hardcode `LOCAL_CONTROLLER_CONFIGS["dwa_balanced"]` cho **mọi** stack —
tức ghép config `dwa` với stack dự đoán. Nó chạy được (mọi khoá đều hợp
lệ), nên test sẽ xanh trong khi mô hình hoá đúng cái defect. Đã sửa:
helper suy config từ controller của chính stack.

**29 test L4 xanh trên cả bốn stack.**

---

## 7. Test

`tests/test_candidate_identity.py` — **26 passed, 1 skipped**:

| lớp | khẳng định |
|---|---|
| `TestTheNewStacksAreReachable` | đăng ký + `benchmarkable`; **vẫn `lidar_only`**; mô tả có `"estimated"` và `"constant velocity"`; ba config cùng mật độ với `dwa` |
| `TestAConfigurationMayNotBeBorrowed` | cặp đúng được nhận; ba cặp mượn bị từ chối; thông điệp nêu tên đúng; tên không tồn tại bị từ chối; **cặp mượn thật sự chạy được** (giữ phép kiểm khỏi thành code chết); mọi config đều có chủ |
| `TestACandidateIdTracksItsCode` | version thôi là literal; hai controller hai version; **lõi dùng chung được băm vào cả hai**; ổn định giữa các lần gọi; **params vẫn tách candidate**; version tường minh vẫn thắng; controller không có source thì fallback; **mọi stack benchmarkable dựng được candidate** |

Ca skip là `astar+ppo` — cần checkpoint, đã có bộ test riêng.

---

## 8. Kiểm chứng

| Việc | Kết quả |
|---|---|
| `tests/test_candidate_identity.py` | **26 passed, 1 skipped** |
| `tests/test_hard_feasible_set.py` (L4, bốn stack) | **29 passed** |
| `test_candidate.py` · `test_candidate_bridge.py` · `test_gates.py` | 115 passed |
| `test_measure.py` · `test_compare.py` · `test_fairness.py` · `test_decision_card.py` | 121 passed |
| `ruff check .` | sạch |
| **Full backend suite** | **CHƯA CHẠY** |

---

## 9. Còn lại — và hai thứ phải chốt trước P7

**P7 là pha duy nhất còn lại.** Nhưng hai thứ nên chốt trước:

1. **§8 của plan chĩa nhầm trục.** P4 mục 7 đo được: dự đoán mua **an
   toàn**, không mua **tốc độ**. Trong khi §8 xếp `stop_and_go_count` và
   `travel_time_s` làm **mục tiêu**, còn collision chỉ là ràng buộc. Chạy
   P7 với bộ metric đó sẽ đo đúng cái trục mà dự đoán chứng minh được là
   không làm gì.
2. **L17 buộc P7 chạy `localization_drift_m = 0`.** Pha hệ toạ độ (mục 2c
   của plan) chưa làm, nên kết quả P7 **không nói gì** về độ bền trước
   nhiễu định vị, và report phải ghi đúng như vậy.

Và một việc vận hành, giờ là việc gấp nhất:

> **Full backend suite chưa chạy trong cả phiên này**, trong khi P6 vừa
> **đổi mọi `candidate_id`** — thay đổi có bán kính ảnh hưởng rộng nhất
> từ đầu plan. Nên chạy trước khi P7 sinh ra bất kỳ artifact nào.

Việc treo từ các pha trước, không đổi: tái bắt sau gap > 0.5 s; 72 tia có
đủ không; **L8** (`kinematics.py` bậc không).
