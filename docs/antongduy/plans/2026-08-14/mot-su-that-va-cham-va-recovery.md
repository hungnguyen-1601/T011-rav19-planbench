# Kế hoạch — một sự thật va chạm, inflation theo bậc, và recovery

**Trạng thái:** **đã duyệt 14-08** (bốn quyết định ở mục 8) · **pha riêng**, không nhét vào kế hoạch
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

### 1.1. Hợp đồng khả thi giữa hai tầng *(dev chốt 14-08)*

Bốn luật, và chúng **không** nói "hai vùng cấm bằng nhau" — chúng nói một
**quan hệ có hướng**:

| | luật |
|---|---|
| L1 | Global **không được** trả về đường mà local **chắc chắn** không lái được |
| L2 | Local **được phép** thận trọng hơn global |
| L3 | Vùng global coi là **va chạm thật** thì local **cũng phải** coi là va chạm |
| L4 | Một đường có clearance **thấp hơn keep-out của DWA** phải bị đánh dấu **"không lái được"** trong test tích hợp |

**L1 chính là luật mà B1 vi phạm**, và **L4 chính là hàng rào lẽ ra đã bắt
được nó**: B1 nới lớp đệm cục bộ quanh robot, RRT* khai thác chỗ nới đó và
trả về đường cách xe đẩy 0.13 m — dưới keep-out 0.31 m của DWA. Global trả
một con đường local **bị cấm đi**. Không test nào bắt, vì chưa có L4.

### 1.2. Hệ quả suy ra từ L1 + L2 — **cần dev xác nhận lại**

Hai luật này **kéo nhau** nếu sự thận trọng của local là một **từ chối
cứng**:

- L1 đòi: mọi đường global trả về phải lái được ⇒ `keepout_global ≥
  keepout_local`.
- L2 cho phép: `keepout_local ≥ keepout_global`.

Cả hai chỉ cùng đúng khi `keepout_local = keepout_global`, tức quay về
đúng ràng buộc thừa đã loại ở đầu mục 1.

**Lối ra duy nhất — và nó chính là hướng đi của mục 2:** phần thận trọng
**vượt trên** biên va chạm chung phải là **mềm** (chi phí), không phải
**cứng** (từ chối). Chỉ **va chạm** mới cứng.

Hiện DWA đang làm ngược:

```python
keep_out = robot.radius + config.safety_margin
if clearances[index] <= keep_out:     # <- TỪ CHỐI CỨNG ở 0.31 m
    continue
```

Suy ra thay đổi: ngưỡng **từ chối cứng** của DWA hạ xuống **`robot.radius`
(va chạm)**, còn `safety_margin` thành một số hạng **chi phí dốc**. Robot
vẫn tránh xa như cũ trong đại đa số tình huống, nhưng khi lựa chọn duy
nhất là đi sát thì nó **đi được** thay vì đứng im.

Đây là **hệ quả tôi suy ra**, không phải điều dev nói. Nó **đổi hành vi
mọi ứng viên**, nên cần xác nhận trước khi code.

**Test:** test tham số hoá quét mọi tầng, khẳng định không tầng nào tự
khai lại bán kính/footprint; test tính chất — cùng tư thế cho cùng phán
quyết va chạm ở mọi tầng (dung sai đúng bằng lượng tử hoá ô, **nêu rõ**);
và **hàng rào L4**, xem mục 7.

**Ước lượng:** 1 ngày, +0.5 nếu làm cả thay đổi ngưỡng DWA ở 1.2.

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
  pha.

  *(dev chốt 14-08)* **Chấp nhận triển khai với objective mới mà chưa xác
  minh các điều kiện bảo đảm tiệm cận tối ưu còn giữ được.** Ghi lại
  thành một hạn chế đã biết, không phải một thứ bị bỏ quên: rewire trên
  một chi phí không phải metric làm mất chứng minh tiệm cận tối ưu của
  RRT*, nên từ đây **"RRT\*" trong dự án này là một biến thể cost-aware**,
  và mọi so sánh phải đọc nó như thế. Ghi vào `docs/KNOWN_LIMITATIONS.md`
  và vào mô tả stack trong registry, để nó lên tới màn hình `/candidates`
  chứ không nằm trong một comment.
- **DWA**: *(dev chốt)* **được phép đọc riêng** khoảng hở liên tục của
  nó — không bắt dùng chung trường chi phí. Nhưng phải **không mâu thuẫn
  về tính khả thi**: bốn luật L1–L4 ở mục 1.1 là hợp đồng, và mục 1.2 là
  thứ phải sửa để L1 và L2 cùng đúng được.

  Đọc riêng là lựa chọn tốt ở đây vì bộ điều khiển phản ứng với **thứ cảm
  biến thấy ngay lúc đó**, còn trường chi phí là ảnh chụp lúc lập kế
  hoạch. Ép chung sẽ làm local chậm một nhịp so với thế giới.

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

### Recovery thuộc về ai — **đã chốt: theo scope**

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

**Dev chốt 14-08: theo scope.** Không luật phẳng.

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
3. **Hàng rào L4 — cái quan trọng nhất trong danh sách này.** Một test
   tích hợp lấy **mọi** đường mà global trả về (kế hoạch đầu **và** mọi
   lần replan), đo khoảng hở tối thiểu tới vật cản, và **đánh dấu
   "không lái được"** nếu nó thấp hơn ngưỡng từ chối cứng của DWA.

   Chạy cho **cả** `astar+dwa` **và** `rrtstar+dwa`, vì đây đúng là chỗ
   B1 hỏng và chỉ lộ ra ở họ planner lấy mẫu: A* đi vòng 0.59 m và qua
   được, RRT* cắt sát 0.13 m và không. Một hàng rào chỉ chạy A* sẽ xanh
   trong khi hệ đang hỏng.
4. **Recovery đổi trạng thái, không đổi kết quả**: sau R1–R3 episode phải
   ở một trạng thái **khác** (vị trí, hướng, hoặc thời gian) — một recovery
   không đổi gì là một recovery vô nghĩa và phải đỏ.
5. **R4 có trần**: số lần clear costmap phải hữu hạn và **ghi lại**. Test
   khẳng định không có đường nào clear vô hạn.
6. **Tái hiện với đủ 7 luồng nhiễu của form** — ca gốc chỉ lộ ra ở đó.

---

## 8. Quyết định của dev — chốt 14-08

| # | câu hỏi | quyết định |
|---|---|---|
| 1 | Recovery theo scope hay phẳng? | **Theo scope** (mục 3) |
| 2 | DWA đọc chung trường chi phí? | **Đọc riêng được**, nhưng phải thoả hợp đồng khả thi L1–L4 (mục 1.1) |
| 3 | RRT* mất tiệm cận tối ưu? | **Chấp nhận**, ghi thành hạn chế đã biết và đưa lên UI |
| 4 | Footprint đa giác? | **Không ở MVP** — giữ hình tròn, nâng cấp sau |

### Về (4): giữ hình tròn, nhưng **đừng khoá cứng vào hình tròn**

Quyết định là đúng cho MVP — footprint đa giác kéo theo kiểm va chạm đa
giác ở **mọi** tầng, và đó là một pha riêng nữa.

Nhưng mục 1 nói *"lưới là biểu diễn **dẫn xuất** từ footprint"*. Nếu viết
nguyên tắc đó dưới dạng **một hàm nhận footprint** ngay từ đầu — dù MVP
chỉ có một hiện thực hình tròn — thì lần nâng cấp sau là **thêm một hiện
thực**, không phải đi khái quát hoá lại bốn tầng.

Chi phí thêm bây giờ gần bằng không; chi phí khái quát hoá lần hai là
đúng công việc mục 1 đang làm, làm lại lần nữa.

### Còn treo — hệ quả suy ra ở mục 1.2

L1 và L2 chỉ cùng đúng được nếu phần thận trọng vượt trên biên va chạm là
**mềm**. Suy ra: ngưỡng từ chối cứng của DWA hạ xuống `robot.radius`,
`safety_margin` thành chi phí. **Đây là suy luận của tôi, không phải điều
dev nói**, và nó đổi hành vi mọi ứng viên — cần xác nhận trước khi code.

---

## 9. Tổng ước lượng

| pha | ngày |
|---|---|
| (1) một sự thật va chạm + hợp đồng L1–L4 | 1–1.5 |
| (2) inflation theo bậc + xoá B1 | 2–3 |
| (3) recovery R1–R4 | 2.5 |
| hợp đồng + manifest + UI + test | 1.5 |
| **tổng** | **7–8 ngày** |

Không phải một buổi. Nếu chỉ có một ngày: làm **(1)** — nó là bất biến,
nó rẻ, và nó không xoá bỏ được bởi bất cứ quyết định nào ở (2) hay (3).
