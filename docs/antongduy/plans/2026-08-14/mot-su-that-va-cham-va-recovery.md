# Kế hoạch — một sự thật va chạm, inflation theo bậc, và recovery

**Trạng thái:** chờ dev duyệt · **pha riêng**, không nhét vào kế hoạch
14-08 (`vung-cam-va-kha-nang-phuc-hoi.md`) — đó là phiên lập kế hoạch
khác, phạm vi khác, và pha này **thay thế một phần việc pha kia vừa làm**

**Nền:**
`docs/antongduy/notes/2026-08-13/tongduyan_hai-vung-cam-mot-con-robot.md`
· `docs/antongduy/reports/2026-08-14/tongduyan_b1-bong-bong-thoat.md`

---

## 0. Vì sao có pha này

Chuỗi nhân quả đã đo được, không phải suy đoán:

1. Hai tầng giữ **hai vùng cấm khác nhau** quanh cùng một vật cản —
   0.31 m (bộ điều khiển, hình học liên tục) và 0.61 m (bộ lập kế hoạch,
   ô lưới). Toàn bộ chênh lệch là số hạng lượng tử hoá lưới.
2. Robot đỗ ở nơi **chính nó cho là hợp lệ**, nằm sâu trong vành cấm của
   planner. Lưới **nhị phân** ⇒ A* không bước nổi một ô ⇒ `"no path"`,
   55 lần giống hệt nhau.
3. **B1** giải phóng một bong bóng quanh robot. Sửa được triệu chứng.
4. Nhưng B1 **không trung lập giữa hai họ planner**: RRT* tối ưu độ dài
   và đặt node ở bất kỳ đâu nên khai thác bong bóng triệt để, trả về
   đường cách xe đẩy **0.13 m** — *dưới* ngưỡng 0.31 m mà DWA bị cấm đi.
   A* đi từng ô nên vô tình đi vòng rộng (0.59 m) và qua được.

**B1 là một cái vá cho tính nhị phân của lưới.** Pha này gỡ nguyên nhân,
và **xoá B1**.

Và một quan sát riêng, cũng đo được:

> Replan mà không có recovery chỉ là **hỏi lại đúng câu hỏi cũ**. Kẹt →
> replan → cùng một lưới → cùng một câu trả lời. Bản sửa "thử lại tới hết
> timeout" khiến nó không chết ngay, nhưng vẫn là 10 lần hỏi giống nhau.

---

## 1. Bất biến: **một** sự thật va chạm

**Không phải "hai vùng cấm bằng nhau".** Đó là ràng buộc thừa — nó bắt bộ
điều khiển thận trọng như bộ lập kế hoạch, trong khi hai tầng có lý do
chính đáng để khác nhau.

Bất biến đúng, hẹp hơn và mạnh hơn:

> Chỉ được có **một** câu trả lời cho câu hỏi *"tư thế này có va chạm
> không"*, và **một** định nghĩa footprint. Lưới là một **biểu diễn dẫn
> xuất** từ footprint, không bao giờ là một định nghĩa thứ hai.

Cụ thể:

- `RobotConfig.radius` (sau này có thể là footprint đa giác) là **nguồn
  duy nhất**. Engine, DWA, `_planning_grid`, và phần vẽ UI đều trích dẫn
  nó qua **một hàm**, không ai gõ lại.
- Inflation **được phép khác nhau** giữa global và local — vì inflation
  là **sở thích** (*"không nên đi gần"*), không phải **biên** (*"không
  thể ở đây"*). Lẫn hai thứ này chính là lỗi khái niệm của B3 trong kế
  hoạch trước.
- `_inflation_radius` đã là một bước đúng hướng (làm ở B4). Mở rộng
  nguyên tắc đó cho footprint và cho phép kiểm va chạm.

**Test:** một test tham số hoá quét mọi tầng, khẳng định không tầng nào
tự khai lại bán kính/footprint; và một test tính chất — với **cùng một
tư thế**, engine, DWA và lưới phải cho **cùng một phán quyết va chạm**
(cho phép sai khác đúng bằng lượng tử hoá ô, và **nêu rõ** dung sai đó).

**Ước lượng:** 1 ngày.

---

## 2. Inflation theo bậc, và điều kiện để nó có nghĩa

Thay lưới nhị phân bằng **trường chi phí**: gần vật cản thì đắt, xa thì
rẻ, chỉ vùng **thực sự va chạm** mới là cấm tuyệt đối.

Cái này **hoà tan con bug gốc**: robot nằm sâu trong vùng nới vẫn có
đường ra, chỉ là đắt. Không cần bong bóng.

Và nó **xoá luôn vấn đề công bằng** của B1: gradient không thiên vị họ
planner nào, vì cả hai đều **trả cùng một giá** cho việc đi sát.

### ⚠ Điều kiện, đã kiểm tra và hiện **chưa thoả**

```
A*    step cost = 1.0 / √2            -> thuần khoảng cách
RRT*  rewire theo euclidean_distance  -> thuần khoảng cách
```

**Không planner nào hiện đọc trường chi phí.** Nên đây **không phải** việc
sửa lớp lưới — nó là **sửa hàm mục tiêu của cả hai planner**:

- **A\***: `step_cost` thành `khoảng_cách × (1 + λ · cost(ô))`. Thay đổi
  nhỏ về mã, nhưng đổi đường đi ⇒ đổi mọi số đo.
- **RRT\***: chi phí cạnh và điều kiện rewire phải tích phân trường chi
  phí dọc cạnh, không chỉ lấy độ dài. Đây là phần **khó nhất** của cả
  pha: rewire dựa trên một chi phí không phải metric làm mất tính chất
  tiệm cận tối ưu của RRT*, và cần nói rõ ta chấp nhận điều đó.
- **DWA**: đã có `weight_clearance` đọc khoảng hở liên tục. Cân nhắc cho
  nó đọc **cùng trường chi phí** để ba tầng nói cùng một ngôn ngữ — hoặc
  cố ý không, và **ghi lý do**.

**λ (hệ số quy đổi chi phí ↔ khoảng cách) là một con số do người chọn.**
Không tránh được. Nên: khai trên **deployment**, giống nhau cho mọi ứng
viên, ghi vào manifest — đúng cách đã xử lý `sensor_noise` và
`replanning`.

**Xoá B1** ngay khi (2) chạy. Giữ cả hai là giữ một cái vá đã hết lý do
tồn tại, và cái vá đó có thiên vị đã biết.

**Ước lượng:** 2–3 ngày (RRT* chiếm phần lớn).

---

## 3. Recovery behaviours

Bốn hành vi, theo thứ tự leo thang. Ba cái đầu đổi **trạng thái thế
giới**, cái cuối đổi **niềm tin**:

| | hành vi | đổi cái gì | dùng khi |
|---|---|---|---|
| R1 | **Chờ** tại chỗ | thời gian trôi, vật cản động đi qua | vật chặn đang di chuyển |
| R2 | **Lùi** một đoạn an toàn | robot rời khỏi chỗ kẹt | đứng quá sát để xoay xở |
| R3 | **Xoay tại chỗ** | hướng, và **quét lại LiDAR ở góc khác** | tầm nhìn bị che |
| R4 | **Clear costmap** | niềm tin, không phải thế giới | nghi perception sai |

**R4 phải là cuối cùng, và phải có giới hạn.** Nó không đổi thế giới — nó
**xoá bằng chứng**. Một hệ clear costmap thoải mái là một hệ tự cho phép
mình quên vật cản nó vừa nhìn thấy. Trong bối cảnh dự án này, đó là một
đường thẳng dẫn tới va chạm mà không cổng nào bắt được.

**Recovery phải bị tính tiền**, đúng như replan: R1 tiêu thời gian mô
phỏng (timeout), R2/R3 tiêu thời gian **và** quãng đường (`travel_time_s`,
`path_length_m`). Không cần số hạng phạt riêng — cùng lập luận đã dùng
cho `replan_count`.

### Câu hỏi thiết kế khó nhất — và **không nên chốt cứng**

Recovery là **điều kiện hiện trường** hay **năng lực ứng viên**?

Cả hai đều có lý. Ngoài đời recovery *là* một phần của stack, và stack có
recovery tốt hơn *là* stack tốt hơn. Nhưng nếu một ứng viên được lùi còn
ứng viên kia không, phép so đo **recovery** chứ không đo planner.

**Nền tảng đã có sẵn từ vựng để không phải chọn cứng: `experiment_scope`.**

- `global_planner_selection` / `local_controller_selection` → recovery
  **dùng chung**, khai trên deployment, áp trên đường mọi ứng viên đều đi
  qua. Đúng lập luận HĐ-4.1.
- Muốn so recovery với nhau → **một scope mới** (`recovery_selection`),
  và khi đó recovery chuyển sang candidate.

Chọn theo scope, không chọn một luật phẳng. Đây là điểm tôi đề nghị dev
duyệt riêng.

**Ước lượng:** 2 ngày (R1–R3), +0.5 ngày R4 kèm giới hạn.

---

## 4. Thứ tự, và lý do

```
(1) một sự thật va chạm     ← bất biến; rẻ; mọi thứ sau dựa vào nó
(2) inflation theo bậc      ← rồi XOÁ B1
(3) recovery behaviours
```

**Vì sao (2) trước (3): công bằng trước năng lực.** Recovery dựng trên
một bộ khung **đã biết là thiên vị** giữa hai họ planner thì đáng giá kém
hơn recovery dựng trên bộ khung đã công bằng. Mọi số đo thu được ở bước
(3) trên nền chưa sửa sẽ phải đo lại.

Cám dỗ làm ngược — (3) trước vì nó cho hiệu quả nhìn thấy nhanh nhất, và
R1/R2 hoạt động được ngay cả trên lưới nhị phân. Tôi vẫn khuyên không,
đúng lý do trên.

---

## 5. Hệ quả hợp đồng

Cả (2) và (3) **đổi *episode là cái gì***: thời gian, quãng đường, khoảng
hở, phơi nhiễm va chạm đều khác. Theo đúng luật đã áp cho `sensor_noise`
và `replanning`:

- `episode_context_id` **không** băm chúng ⇒ hai lượt chạy cùng seed, một
  bên có recovery một bên không, **dùng chung mọi context id** mà là hai
  thí nghiệm.
- ⇒ **`task_profile_id` mới** cho bất cứ deployment nào muốn đo dưới
  chúng. Không sửa tại chỗ. `same_deployment` đã chặn sẵn.
- ⇒ **manifest phải ghi** cả cấu hình inflation (λ, profile chi phí) lẫn
  tập recovery và ngưỡng kích hoạt.
- ⇒ bump hợp đồng, cập nhật `manifest.schema.json`
  (`additionalProperties: false` đã bắt hụt một lần ở A3).

---

## 6. Thứ **không** bê từ Nav2

Cây hành vi mặc định của Nav2 đầy hằng số đã tinh chỉnh: thứ tự recovery,
số lần thử, timeout, bán kính clear. **Mỗi hằng số là một con số do người
chọn** — đúng loại núm vặn vừa gỡ khi bỏ `max_replans`, và đúng loại tạo
tác khiến một ứng viên lẽ ra thoát được bị chấm là hỏng.

Lấy **cấu trúc**; hằng số thì **khai trên deployment**, **giống nhau cho
mọi ứng viên**, và **ghi vào manifest**.

---

## 7. Test bắt buộc

1. **Một sự thật**: test tham số hoá — không tầng nào tự khai lại
   footprint; cùng tư thế cho cùng phán quyết va chạm ở mọi tầng.
2. **Bất biến theo độ phân giải**: cùng cảnh ở 0.05 / 0.125 / 0.25 m phải
   cho cùng *kết luận* (không nhất thiết cùng đường). Con bug gốc sinh ra
   từ một đại lượng của lưới, nên hàng rào phải bắt đúng chuyện đó.
3. **Không thiên vị họ planner**: `sudden_stop` với **cả** `astar+dwa`
   **và** `rrtstar+dwa` — cả hai phải trả về đường **lái được**, tức
   khoảng hở tối thiểu ≥ keep-out của bộ điều khiển. Đây là hàng rào cho
   đúng thứ B1 làm hỏng.
4. **Recovery đổi trạng thái, không đổi kết quả**: sau R1–R3 episode phải
   ở một trạng thái **khác** (vị trí, hướng, hoặc thời gian) — một recovery
   không đổi gì là một recovery vô nghĩa và phải đỏ.
5. **R4 có trần**: số lần clear costmap phải hữu hạn và **ghi lại**. Test
   khẳng định không có đường nào clear vô hạn.
6. **Tái hiện với đủ 7 luồng nhiễu của form** — ca gốc chỉ lộ ra ở đó.

---

## 8. Câu hỏi cần dev quyết trước khi code

1. **Recovery theo scope hay phẳng?** (mục 3). Tôi đề nghị theo scope.
2. **DWA có đọc chung trường chi phí không**, hay giữ khoảng hở liên tục
   riêng? Đọc chung thì ba tầng cùng ngôn ngữ; giữ riêng thì bộ điều
   khiển vẫn phản ứng đúng với thứ cảm biến thấy ngay lúc đó. Tôi nghiêng
   **giữ riêng, và ghi rõ lý do** — nhưng đây là quyết định của dev.
3. **Chấp nhận RRT\* mất tiệm cận tối ưu** khi rewire trên chi phí không
   phải metric?
4. **Footprint đa giác** làm luôn ở pha này hay để sau? Nav2 hỗ trợ đổi
   footprint khi robot mang hàng; nếu định làm thì (1) nên khái quát ngay
   từ đầu thay vì khái quát lần hai.

---

## 9. Tổng ước lượng

| pha | ngày |
|---|---|
| (1) một sự thật va chạm | 1 |
| (2) inflation theo bậc + xoá B1 | 2–3 |
| (3) recovery R1–R4 | 2.5 |
| hợp đồng + manifest + UI + test | 1.5 |
| **tổng** | **7–8 ngày** |

Không phải một buổi. Nếu chỉ có một ngày: làm **(1)** — nó là bất biến,
nó rẻ, và nó không xoá bỏ được bởi bất cứ quyết định nào ở (2) hay (3).
