# Phase 2 — vành cấm thành cái giá, không còn là bức tường

**Ngày:** 2026-08-14
**Plan:** `docs/antongduy/plans/2026-08-14/mot-su-that-va-cham-va-recovery.md`, phase 2
**Trạng thái:** xong, chưa commit (chờ lệnh)

---

## 1. Vấn đề

Lưới nhị phân trả lời câu *"robot có được đứng ở đây không"* bằng một con
số **nửa về thế giới, nửa về file bản đồ**. Trên `sudden_stop` đang ship,
vành của planner là 0.61 m, trong đó 0.35 m là `√2 × resolution` — hình
học của ô lưới. Robot đứng ở chỗ chính test va chạm của nó nói là hợp lệ
mà vẫn nằm sâu 0.30 m trong vành ấy, và 55 lần replan trong 120 s đều trả
"no path exists" từ một ô có **0 trong 8** hàng xóm còn trống.

---

## 2. Thay đổi cốt lõi

Ba đại lượng ở chỗ trước đây chỉ có một:

```
_feasible_clearance(scenario) = hard_clearance(robot, envelope)
_hard_radius(map, scenario)   = _feasible_clearance + √2/2 × resolution   # lưới cấm
_caution_ramp(map, scenario)  = √2/2 × resolution + _feasible_clearance   # tính tiền
```

Hệ số chi phí giảm **tuyến tính** từ `1 + λ` sát biên xuống `1` ở cuối
ramp. Tuyến tính chứ không mũ như Nav2: decay mũ mang theo một hằng số
tốc độ ai đó phải chọn, còn đường dốc thẳng được cố định bởi đúng hai đầu
mút, cả hai đều là đại lượng deployment đã khai.

### Lượng tử hoá là **hai phía**, và hai nửa đi hai chỗ khác nhau

Đây là chỗ tôi phải sửa lại giữa chừng, sau khi đo.

Ô OCCUPIED nghĩa là "vật cản chạm ô này", **không nói chạm ở đâu trong
ô**. Nên khoảng cách tâm–tâm chỉ chặn khoảng cách thật trong phạm vi một
đường chéo ô, và chặn ở **cả hai** phía: nửa của vật cản, nửa của robot.

- **Nửa phía vật cản** phải nằm trong lệnh cấm (`_hard_radius`). Đây là
  **số học, không phải thận trọng**: bỏ nó ra thì lưới thành xấp xỉ
  **lạc quan** của miền cứng — điều duy nhất nó không được phép là thế.
  Bản đầu tôi bỏ hẳn cả đường chéo ra khỏi lệnh cấm, và đo được ngay:
  trên phòng hai cửa ở ô 0.5 m với robot 0.3 m, inflate 0.30 m **không
  đánh dấu thêm một ô nào** (tâm hai ô kề nhau cách 0.5 m). A* trả về
  đường cạo sát tường, controller không lái được, **40/43 lần replan
  không tìm ra gì** — đúng lỗi cũ, vào bằng cửa khác.
- **Nửa phía robot** nằm trong ramp, chỉ tính tiền. Đường đi là vật thể
  liên tục và được kiểm như thế: hàng rào L4 đo mọi đường global theo
  **mét**, trên cả hai stack.

Hệ quả cần nói thẳng: **không có bán kính inflation nào** khiến
"controller nói tư thế này hợp lệ" kéo theo "lưới của planner đồng ý".
Nhị phân buộc phải chọn một phía; gradient thì không.

### λ — `clearance_preference`, khai trên deployment

Con số **duy nhất người phải chọn**, không suy ra được. Khai trên
**deployment**, chung cho mọi ứng viên, vào manifest (HĐ-13).

**λ được nướng thẳng vào lưới** trước khi bất kỳ planner nào nhận bản đồ.
Không planner nào cần λ riêng, nên **không candidate nào mua được đường
ngắn hơn bằng cách bớt quan tâm** — cùng kiểu cưỡng chế bằng cấu trúc
như safety envelope ở phase 1.

**Mặc định 4.0 là đo được, không phải chọn bừa**, và phải đo vì tác dụng
**không đơn điệu**:

| λ | phòng hai cửa | sudden_stop A* | sudden_stop RRT* |
|---|---|---|---|
| 2.0 | timeout, 42 replan | success | success |
| **4.0** | **success, 1 replan** | **success** | **success** |
| 6.0 | success, 1 replan | success | **timeout** |
| 10.0 | success, 1 replan | success | **timeout** |

Dưới ngưỡng, planner vẫn cạo sát cửa bị chặn mà controller không lái qua
được. **Trên** ngưỡng, planner lấy mẫu đi lang thang: gradient đủ mạnh
làm gần như mọi cạnh đều đắt, cây RRT* thôi hội tụ. Nên 4.0 là **giá trị
chạy được, không phải tối ưu**, và chưa hiệu chuẩn theo dữ liệu thật.

## 3. Hai planner giờ mới thật sự đọc trường chi phí

Plan đã ghi rõ đây là **điều kiện chưa thoả**: A* dùng `step_cost = 1/√2`
và RRT* rewire theo `euclidean_distance` — thuần khoảng cách cả hai. Một
trường chi phí không ai đọc là một trường chi phí không làm gì.

**A\*** — `step_cost = khoảng_cách × hệ_số(ô đi tới)`. Hệ số thuộc về ô
**được bước vào**: bước kết thúc ở đó, tính theo ô xuất phát sẽ cho một
đường gom được ưu đãi của chỗ trống trên đường chui vào chỗ hẹp.

Tính khả nhận của heuristic **vẫn còn** — thứ phải kiểm trước khi động
vào cost của A*: hệ số ≥ 1 nên mỗi bước tốn ít nhất bằng khoảng cách của
nó, Euclid vẫn không bao giờ ước lượng vượt. Nếu cho phép hệ số < 1 thì
đã phải chia heuristic cho hệ số nhỏ nhất — và đó là lý do lưới **từ
chối** giữ một hệ số dưới 1.

**RRT\*** — chi phí cạnh là **tích phân trường dọc cạnh**. Phần khó nhất
của pha, và cách giữ cho nó không chậm là dùng khoảng cách đường thẳng
làm **chặn dưới**:

- chọn cha: duyệt ứng viên theo chặn dưới tăng dần, dừng ngay khi chặn
  dưới kế tiếp không thể thắng cạnh thật tốt nhất đã tìm được;
- rewire: nút mà khoảng cách thẳng đã không giúp nổi thì cạnh thật cũng
  không, nên phép kiểm rẻ vẫn cắt tỉa và phép đắt chỉ chạy trên số sống
  sót;
- nối goal: khoảng cách trước, va chạm sau, tích phân sau cùng.

Trên lưới nhị phân, chặn dưới **chính là** chi phí, nên ứng viên đầu tiên
nhìn thấy được là ứng viên thắng — đúng một phép kiểm va chạm như trước.

---

## 4. Cái bẫy suýt làm cả pha thành vô nghĩa

`simplify_path` cắt góc theo tầm nhìn. A* bỏ công tìm đường vòng qua dải
đắt, rồi bộ cắt góc kéo thẳng lại **xuyên đúng dải đó** và trả về một
đường ôm sát vật. Sự thận trọng của tìm kiếm bị xoá ở khâu hậu xử lý,
im lặng, ở **mọi** lần lập kế hoạch.

Đã sửa: một shortcut chỉ được nhận nếu nó **không đắt hơn** đoạn nó thay
thế (`segment_cost`, tích phân cùng bước lấy mẫu mà phép kiểm tầm nhìn
vẫn dùng). Trên lưới không phân bậc mọi hệ số bằng 1, nên chi phí = độ
dài, đường thẳng qua hai điểm không bao giờ dài hơn đường đi qua chúng,
phép kiểm luôn đạt — hành vi **y hệt** như trước.

---

## 5. Bong bóng B1 đã xoá

`_with_room_to_leave` bị xoá, `tests/test_b1_room_to_leave.py` cũng vậy.
Thay bằng `_with_standing_room`, và nó **nới đúng phần thận trọng của
lưới, không nới miền cứng**: ô nào bị chặn trên lưới `_hard_radius` mà
**tự do** trên lưới `_feasible_clearance` thì được mở, trong bán kính một
`_caution_ramp` quanh robot. Ô nằm trong miền cứng thật **không bao giờ**
được mở, nên đường ra vẫn thoả L1 — và L4 đo lại bằng mét.

Riêng **ô robot đang đứng thì mở vô điều kiện**. Đây là chỗ thứ hai tôi
phải sửa sau khi đo: ô rộng 0.5 m, robot giữ khoảng cách 0.3 m với tường
sẽ đặt LiDAR return gần nhất vào **chính ô chứa tâm nó**, nên luật có
điều kiện từ chối đúng lúc cần nới nhất — đo được **"start is inside an
obstacle" 43/44 lần replan**. Nhưng robot **đang ở đó**, và engine kết
thúc episode ngay khi robot chồng lên vật cản, nên sự hiện diện của nó
chính là bằng chứng.

**Vì sao đây không phải B1 quay lại.** B1 mở mọi thứ mà *inflation* đã
đánh dấu, tức trả lại **không gian trống thật**, và không gian trống có
giá trị khác nhau với từng họ planner (đo trên `sudden_stop`: A* lấy hành
lang rộng 0.59 m bằng 3 waypoint; RRT* cắt đúng khe đó còn 0.13 m bằng 10
waypoint, có khúc quay 170° và 187° mà robot chỉ-tiến-không-lùi không lái
nổi).

Hai điểm khác: nới **dừng ở miền cứng** chứ không dừng ở vật cản thô, nên
không bao giờ trả lại thứ bất hợp lệ; và mọi ô được mở **giữ nguyên hệ số
chi phí cực đại**, nên cắt qua khe đó là **đắt** với bất kỳ ai làm thế —
đó chính là câu trả lời của gradient cho thiên vị của B1, và là lý do lần
này được phép là một vùng chứ không phải một ô.

## 6. Số đo

Bảng λ ở mục 2 là số đo chính. Ngoài ra, phần **hàng rào bắt được lỗi**
đáng ghi lại vì cả hai lần đều là test/số đo bắt chứ không phải suy luận:

| Lần | Triệu chứng đo được | Nguyên nhân |
|---|---|---|
| 1 | 40/43 replan không tìm ra đường, phòng hai cửa ô 0.5 m | bỏ **cả** đường chéo ô ra khỏi lệnh cấm → lưới lạc quan, inflate 0.30 m không đánh dấu thêm ô nào |
| 2 | `"start is inside an obstacle"` 43/44 lần | luật "không mở ô có LiDAR return" từ chối chính ô robot đang đứng |

Và một lần nữa ở mức mặc định: `Scenario.clearance_preference` ban đầu
tôi để 0.0 với lý do "giữ hành vi cũ cho scenario dựng trước khi có
trường này". Sai: hành vi cũ đi kèm inflation nhị phân rộng hơn miền cứng
cả một đường chéo ô. Sau khi lệnh cấm co lại, λ=0 **không tái lập hành vi
cũ mà cũng không tốt** — nó cấp cho planner giấy phép cạo sát vật mà
không ai tính tiền, rồi controller không lái nổi thứ trả về. Full suite
bắt đúng chỗ đó: 4 test replanning đỏ.

## 7. UI — vành cấm giờ phải là **hai** vành

Test web bắt được: vành cũ vẽ một đĩa duy nhất và gọi nó là vùng cấm. Sau
phase 2 điều đó thành lời nói dối theo **chiều ngược lại** — nó vẽ đất mà
robot được phép đứng như thể là tường.

Giờ vẽ hai:

- **vành cấm** (`robot.radius + safety envelope`) — nét đứt `[4,4]`, alpha
  như cũ;
- **dải tính tiền** (thêm `√2 × resolution` + taper) — nét chấm `[2,3]`,
  alpha **nhạt hơn hẳn**, vẽ **dưới** vành cấm.

Thứ tự nhạt-dần và kiểu nét khác nhau chính là tín hiệu: người đọc phải
phân biệt được ngay cái nào robot được vào. Trộn hai thứ vào một đĩa
**đúng là** thứ đã làm con robot kẹt trở nên khó hiểu — nó đứng trong
vùng mà bức tranh gọi là cấm còn test va chạm của chính nó gọi là ổn.

Cả hai chế độ 2D và 2.5D vẽ giống nhau, từ cùng một hàm.

Form deployment có thêm ô `clearance_preference` (λ) — test
`test_form_covers_the_contract.py` bắt ngay khi thiếu, đúng như nó được
viết ra để làm.

---

## 8. Test

`tests/test_graded_inflation.py` — 24 test + 1 skip:

1. **Chỉ miền cứng là cấm** — `_feasible_clearance` không mang số hạng
   nào của lưới; `_hard_radius` mang **đúng nửa** đường chéo và không hơn;
   số ô bị chặn thật sự giảm; và **mọi** ô đi được đều nằm ngoài
   `hard_clearance` của vật cản thật (kiểm bằng distance transform trên
   toàn lưới, không lấy mẫu).
2. **Gradient là lời khuyên, không phải giấy phép** — không hệ số nào
   dưới 1; giảm đơn điệu khi rời tường và về đúng 1.0 giữa sảnh; λ=0 khôi
   phục **chính xác** khoảng cách thuần; schema candidate không hề có λ.
3. **Cả hai planner thật sự đọc** — λ cao thì đường đi xa vật hơn (chạy
   cho cả A* và RRT*); `cost` báo về khác `path_length` khi đường buộc
   phải men tường, và **bằng nhau** giữa sảnh trống; trên lưới không phân
   bậc, `cost == path_length` tới `1e-9`.
4. **Cắt góc không xoá được gradient** — shortcut đắt hơn bị từ chối,
   shortcut rẻ hơn vẫn được nhận, và trên lưới không phân bậc hành vi y
   hệt trước.
5. **Bong bóng đã xoá, robot vẫn ra được** — chạy cả hai stack với đủ 7
   luồng nhiễu của form; `_with_room_to_leave` không còn trong source;
   `_with_standing_room` chạm đúng một ô và không bao giờ nới ô có
   return.
6. **Kết luận sống sót qua độ phân giải** — 0.125 / 0.25 / 0.5 m. Miền
   cứng là mét vật lý nên **không đổi**; cả ramp **và** bán kính cấm của
   lưới **phải co lại** khi ô nhỏ đi, vì lưới mịn hơn thì bớt mơ hồ hơn.

Hai test đầu tôi viết sai **tiền đề** chứ không phải code sai, và đã sửa
tiền đề: một test đo dốc chi phí dọc một cột cắt qua chỗ vẫn còn đắt, và
một test đòi `cost > path_length` trên đường đi **giữa sảnh trống** — ở
đó hai số **phải** bằng nhau, và bản đầu tiên của test đó không đo gì cả.

---

## 9. Hạn chế đã ghi vào `docs/KNOWN_LIMITATIONS.md`

1. **Bảo đảm tiệm cận tối ưu của RRT\* chưa được xác minh.** Phiếm hàm
   chi phí mới hằng-từng-ô, tức gián đoạn ở mọi cạnh ô. Dev đã chốt chấp
   nhận. Từ nay **"RRT\*" trong dự án này là biến thể cost-aware**, và
   điều đó được ghi cả trong mô tả stack trên `/candidates` chứ không nằm
   trong comment.
2. **λ là số do người chọn**, chưa hiệu chuẩn theo dữ liệu. Đổi λ **đổi
   mọi đường đi**, nên đổi nó là tạo deployment mới.
3. **Tích phân chi phí là xấp xỉ lấy mẫu** (1/4 ô), không phải đi chính
   xác chuỗi ô (Amanatides–Woo).
4. **Vẫn nới một ô** quanh robot, vì lượng tử hoá hai phía là không tránh
   được.

---

## 10. Kiểm chứng

| Việc | Kết quả |
|---|---|
| `test_graded_inflation.py` + `test_hard_feasible_set.py` | 51 passed, 1 skipped |
| `test_replanning.py` + API replanning | 40 passed, 1 skipped |
| `test_grid` / `test_astar` / `test_rrtstar` / `test_path_utils` | 94 passed |
| `test_form_covers_the_contract.py` | passed |
| Web suite (`vitest run`) | 670 passed / 32 files |
| `tsc --noEmit` | sạch |
| `ruff check .` | sạch |
| Full backend suite | **2549 passed, 7 skipped** |

---

## 11. Còn lại

**Phase 3** — recovery behaviours R1–R4. Chưa bắt đầu.

Chưa commit. Chờ lệnh.
