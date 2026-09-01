# Phase 3 — recovery: robot được làm gì khi lập kế hoạch hết tác dụng

**Ngày:** 2026-08-14
**Plan:** `docs/antongduy/plans/2026-08-14/mot-su-that-va-cham-va-recovery.md`, phase 3
**Trạng thái:** xong, full suite xanh

---

## 1. Recovery thuộc về ai — theo scope, đúng như plan chốt

Ngoài đời recovery *là* một phần của stack, và stack có recovery tốt hơn
*là* stack tốt hơn. Nhưng nếu một ứng viên được lùi còn ứng viên kia
không, phép so đo **recovery** chứ không đo tầng mà run tuyên bố đang so.
Đúng lập luận HĐ-4.1 về đặc quyền thông tin khi replan.

Nên: khai trên **deployment** (`TaskProfile.recovery`), áp trên đường mọi
ứng viên đều đi qua. Chuyển sang candidate cần một scope mới
(`recovery_selection`) — **chưa dựng**, vì dựng nó trước khi có ai muốn
so recovery là làm cái thứ hai trước cái thứ nhất.

Mặc định **tắt**, như `replanning`, và cùng lý do: nó đổi chỗ robot dừng
lại, tức đổi mọi metric phía sau, và mọi run đã lưu đều đo khi chưa có
nó. Bật nó là tạo deployment mới chứ không phải sửa deployment cũ.

---

## 2. Bốn bậc thang, và bậc cuối khác loại

| | Hành vi | Đổi cái gì | Trả bằng gì |
|---|---|---|---|
| R1 | chờ tại chỗ | thời gian — vật cản động đi qua | thời gian mô phỏng |
| R2 | lùi | vị trí robot | thời gian **và** quãng đường |
| R3 | xoay | hướng robot | thời gian |
| R4 | quên thứ đã cảm nhận | **niềm tin, không phải thế giới** | thời gian, và một hạn mức riêng |

**R1–R3 đổi trạng thái thế giới; R4 xoá bằng chứng.** Đó là lý do nó
đứng cuối và bị chặn. Một stack được clear costmap thoải mái là stack tự
cho phép mình quên vật cản nó vừa nhìn thấy, và ở đây điều đó dẫn thẳng
tới va chạm mà **không cổng nào bắt được**: Metrics Engine đọc trace, và
một vật cản bị quên không để lại dòng nào nói rằng nó đã bị quên. Số lần
được đếm và ghi vào event chính vì thế.

Trong codebase này không có costmap bền vững — lưới replan được dựng lại
từ LiDAR mỗi lần. Nên "clear costmap" dịch trung thực thành: **replan
trên bản đồ tĩnh, vứt toàn bộ LiDAR return**.

**Recovery bị tính tiền bằng cách được mô phỏng, không bằng cách bị
trừ.** R1 đốt thời gian mô phỏng tính vào timeout; R2/R3 đốt thời gian
**và** quãng đường, nên chúng tự rơi vào `travel_time_s` và
`path_length_m`. Không có số hạng phạt nào, và không nên có — đúng lập
luận đã cho `max_replans` nghỉ và giữ `replan_count` làm bằng chứng.

---

## 3. Rất ít nút bấm, vì hầu hết suy ra được

`RecoveryConfig` chỉ có **hai** con số ngoài `enabled`, và cả hai đều là
lựa chọn thật:

- `max_escalation` — được leo tới bậc nào. Cách để nói "chờ và lùi và
  xoay, nhưng đừng bao giờ quên" mà không cần một cờ cho mỗi hành vi.
- `max_forgets` — hạn mức riêng cho bậc cuối, vì nó tiêu thứ khác thời
  gian. Mặc định 1: lần thứ hai là quên hai lần.

Còn lại **suy ra tại chỗ dùng**:

- chờ = **một `stuck_time_window`**. Chờ ngắn hơn cửa sổ của chính bộ
  phát hiện thì không chứng minh được gì — trạng thái đứng yên sẽ được
  suy lại từ những mẫu chưa bao giờ ngừng mô tả một robot đứng yên.
- lùi = **một `hard_clearance`**. Đủ để thôi dính sát thứ đang chặn; xa
  hơn là phá đi quãng đường episode đã trả tiền.
- xoay = **quay về waypoint kế tiếp của đường hiện tại**. Suy từ plan,
  không phải một góc ai đó chọn.

Hỏi tác giả deployment một "khoảng cách lùi" là bắt họ trả lời lại câu
mà hình học của chính con robot đã trả lời.

---

## 4. Ba thứ tôi làm sai, và cả ba do **đo** mới lộ ra

### 4.1 Trigger sai — recovery chạy **0 lần** trong đúng cảnh nó sinh ra để xử lý

Bản đầu leo thang khi replan **bị từ chối**. Đo trên phòng hai cửa: cả
**43/43** replan đều **thành công**, robot vẫn timeout, và recovery chạy
**0 lần**.

Một plan trả về mà không đổi được gì là **trường hợp phổ biến**, không
phải hiếm. Nên tín hiệu phải là *lập kế hoạch có đang giúp không*, chứ
không phải *lập kế hoạch có trả lời không*.

Trigger mới: **tiến bộ giữa hai lần đứng yên liên tiếp**, đo bằng chính
`stuck_min_displacement` của deployment — cùng ngưỡng bộ phát hiện dùng
để kết luận robot đã dừng, áp lên khoảng cách tới goal thay vì lên mặt
đất.

### 4.2 Recovery lái mù — biến 2 timeout thành 2 **va chạm**

| Cấu hình | Trước khi có kiểm tra | Sau |
|---|---|---|
| λ=0, recovery on | **collision** t=63s | timeout, 7 recovery |
| λ=2, recovery on | **collision** t=44s | timeout, 7 recovery |

Lùi là **hướng duy nhất controller không bao giờ kiểm** — nó nhìn nơi nó
đang đi tới. Một recovery lái mù là **tầng thứ tư có câu trả lời riêng**
cho "robot có được ở đây không", đúng cái defect mà phase 1 và 2 dựng ra
để xoá.

Sửa: mỗi bước bị từ chối nếu tư thế nó tạo ra lọt vào trong
`hard_clearance` của bất cứ thứ gì robot **nhìn thấy được** (LiDAR
return, không phải ground truth — cùng lý do HĐ-4.1 bắt `_replan` đọc
observation).

Và **một bước nhìn trước cần một bước biên**: engine ramp vận tốc theo
`max_linear_acceleration` nên tư thế suy từ vận tốc *lệnh* không phải tư
thế bước sau tạo ra; còn LiDAR return là các điểm lấy mẫu vài độ một
chứ không phải điểm gần nhất của bức tường. Thiếu biên đó, cú lùi **qua
được** kiểm tra rồi va chạm **đúng một bước sau**.

### 4.3 "Lùi" không phải là "tránh xa vật cản"

Robot vi sai chỉ đi được dọc hướng của nó. Nên "lùi" = "đi ngược hướng
đang quay mặt", và hai thứ đó **khác nhau đúng lúc robot kẹt trong tư
thế quay lưng vào thứ đang chặn**. Đo được: robot đứng cạnh tường, mũi
hướng dọc hành lang, cú lùi lái thẳng vào tường, va chạm ngay bước sau.

Sửa: bậc R2 bị **bỏ qua** nếu phía sau không rộng hơn phía trước. Một
recovery không giúp được gì thì nên tốn 0 và nhường chỗ cho bậc tiếp.

### 4.4 (bonus) Event nói dối

`back_up` báo `"backed up 0.30 m"` bất kể đi được bao xa — một cú lùi bị
chặn sau 5 mm vẫn ghi 0.30 m. Giờ báo **quãng đường thật sự đi được**:
`"backed up 0.27 m of 0.30 m"`. Một event stream nói quá những gì robot
làm còn tệ hơn không có event stream, vì nó chính là thứ người ta đọc khi
thấy quỹ đạo trông sai.

---

## 5. Thang chạy thật, trên `sudden_stop`/phòng hai cửa

```
t= 37.85 recovery 1 (wait):    waited 5.0s in place
t= 42.85 recovery 2 (back_up): no more room behind than ahead; did not reverse
t= 48.00 recovery 3 (turn):    turned -7° towards the path
t= 69.90 recovery 4 (wait):    waited 5.0s in place        <- thang đã reset
t= 76.10 recovery 5 (back_up): backed up 0.27 m of 0.30 m
t= 79.95 recovery 6 (turn):    turned -1° towards the path
t= 84.90 recovery 7 (forget):  replanned on the static map, discarding what the LiDAR saw (1/1)
```

Đọc ra: cả bốn bậc đều chạy, R2 tự từ chối khi vô ích, thang **reset**
sau khi robot tiến được (nên chuỗi là `wait, back_up, turn, wait, ...`
chứ không phải một dãy leo thẳng), và `forget` dừng đúng ở 1/1.

**Nói thẳng: recovery không cứu được cảnh này.** Episode vẫn timeout.
Cái phase này bảo đảm là recovery **bị chặn, an toàn, bị tính tiền, và
được ghi lại**, và **không bao giờ biến một timeout thành va chạm** — chứ
không phải nó giải được mọi bế tắc.

---

## 6. Test

`tests/test_recovery.py` — 19 test:

1. **Tắt cho tới khi deployment xin** — mặc định không làm gì; episode
   không bật recovery **giống hệt** episode tắt tường minh (khác đi
   nghĩa là mọi số đo trước phase này đã lặng lẽ dịch chỗ).
2. **Thang được leo và được reset** — thứ tự đóng băng; **không bậc nào
   bị nhảy cóc** (phát biểu theo thứ tự *lần xuất hiện đầu*, vì thang
   reset giữa chừng là hành vi đúng — bản test đầu tôi viết theo prefix
   và nó fail chính cái reset đó); `max_escalation=3` chặn được `forget`.
3. **Bậc xoá bằng chứng bị chặn** — tối đa `max_forgets`; `max_forgets=0`
   ("đừng nữa") và `max_escalation=3` ("đừng bao giờ") là hai câu khác
   nhau; mọi lần dùng đều ghi hạn mức vào event.
4. **Recovery tuân miền khả thi cứng** — không bao giờ biến timeout
   thành collision; cú lùi bị từ chối khi lùi không phải lối ra; event
   báo đúng quãng đường thật.
5. **Bị tính tiền bằng mô phỏng** — chờ tiêu đúng một `stuck_time_window`;
   recovery và replan **tách bạch trong record** ("planner tìm được
   đường khác" và "robot lùi rồi thử lại" là hai sự thật khác nhau).
6. **Nút bấm suy ra được ở đâu thì suy ra** — config chỉ mang đúng hai
   lựa chọn thật; manifest nói rõ cả khi tắt.
7. **R3 được biện minh bằng thứ nó thật sự làm** — xem mục 7.

---

## 7. Một chỗ plan nói sai, và tôi không hiện thực theo lời đó

Plan biện minh R3 là *"xoay tại chỗ → quét lại LiDAR ở góc khác"*.

**Với LiDAR mặc định của dự án này, điều đó sai.** `LidarConfig.angle_span`
mặc định là **2π** — robot đã nhìn thấy phía sau lưng nó rồi, xoay không
lộ ra return nào mới. Nó chỉ đúng với deployment nào khai span hẹp hơn.

R3 vẫn đáng có, nhưng vì lý do khác và lý do đó có thật: controller với
`allow_reverse=False` quay mặt vào tường thì **không có lệnh nào khả
nhận cả**, và bất kỳ hướng nào nó lái được cũng hơn hướng nó đang có.
Nên R3 xoay **về phía waypoint kế tiếp**, và cả code lẫn test đều ghi rõ
điều nó **không** khẳng định.

---

## 8. Kiểm chứng (chưa full suite — chờ lệnh)

| Việc | Kết quả |
|---|---|
| `tests/test_recovery.py` | 19 passed |
| `tests/test_replanning.py` | 35 passed, 1 skipped |
| `test_nav_stack` / `test_task_profile` / `test_form_covers_the_contract` | passed |
| `ruff check .` | sạch |
| Full backend suite | **2568 passed, 7 skipped** |
| Web suite (`vitest run`) | 670 passed / 32 files |
| `tsc --noEmit` | sạch |

Hai sửa dọc đường. Web suite bắt được một sót của **phase 2**:
`cautionRamp` trong `lib/keepOut.ts` vẫn dùng **cả** đường chéo ô, trong
khi `_caution_ramp` đã đổi thành **nửa** đường chéo — vành phụ trên UI
rộng gấp rưỡi phần ramp thật. Đã sửa và ghim lại bằng test đọc thẳng
`nav_stack.py`.

Sửa thứ hai: `engine.resume_after_replan` nhận thêm `event_type`
để recovery không bị ghi thành replan; thông điệp lỗi đổi từ
`"cannot resume after replan"` sang `"cannot resume (replan)"`, và hai
test trong `test_replanning.py` khớp chuỗi đó đã được cập nhật.

---

## 9. Còn lại

Plan `mot-su-that-va-cham-va-recovery.md` đã xong **cả ba phase**.
