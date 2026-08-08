# Điều tra — Vì sao bật replanning trên `bidirectional_corridor` vẫn va chạm

> **Ngày:** 2026-08-08
> **Loại:** quan sát/điều tra — **không đổi một dòng code sản phẩm**.
> **Nhánh:** `integrate-tongduyan`, sau khi Đợt A và Đợt B đã xong.
> **Xuất phát:** dev báo — bật replanning (`max_replans=2`) trên
> `bidirectional_corridor`, nhìn visualization 2D/2.5D thì robot **vẫn va
> chạm**, đường đi **không khác gì** khi tắt, và benchmark cũng không
> thấy chênh lệch giữa có replan và không replan. Câu hỏi kèm theo: "hay
> do đề tài quá khó không thể thực hiện được?"
>
> **Kết luận ngắn: quan sát của dev đúng ở cả ba điểm. Đề tài không quá
> khó — replanning hoạt động đúng thiết kế, nhưng nó là công cụ sai cho
> đúng map đó.** Ba nguyên nhân độc lập, đo được từng cái.

---

## 1. Cách đo

Chạy trực tiếp `run_stack()` trên thư viện scenario, `astar+dwa`, 5 seed
(1–5), so `NO_REPLANNING` với `ReplanningConfig(enabled=True,
max_replans=2)`. Không qua API, không qua UI — để loại trừ mọi khả năng
lỗi nằm ở tầng hiển thị.

## 2. Nguyên nhân 1 — replanning **chưa từng chạy** trên map đó

```text
bidirectional_corridor, astar+dwa, 5 seed
  off    {collision: 5}  replans=[0,0,0,0,0]  t=[21.0, 20.9, 5.9, 5.8, 20.4]
  on(2)  {collision: 5}  replans=[0,0,0,0,0]  t=[21.0, 20.9, 5.9, 5.8, 20.4]
```

Hai dòng **giống hệt nhau từng con số**, kể cả thời gian. `replan_count`
bằng 0 ở cả 5 seed khi đã bật.

Lý do nằm ở một dòng:

```python
# services/simulator/planbench_simulator/nav_stack.py:165
_REPLANNABLE = (EpisodeStatus.STUCK, EpisodeStatus.NO_PROGRESS)
```

Episode ở `bidirectional_corridor` kết thúc bằng `COLLISION`, mà
`COLLISION` **không** nằm trong danh sách đó. `engine.resume_after_replan()`
cũng từ chối `COLLISION` với lý do được ghi rõ trong docstring: *"a
collision is a verdict on the episode, and letting a new path undo it
would let replanning buy results it did not earn."*

Đây là chủ ý và **đã quyết định giữ nguyên**. Nới trigger sang
`COLLISION` sẽ làm `bidirectional_corridor` có số khác giữa on/off,
nhưng phá định nghĩa `success_rate`/`collision_rate`: một run đâm 3 lần
rồi tới đích thì tính là gì? Đó là mua kết quả bằng cách đổi định nghĩa
thành công.

Hệ quả phải nói thẳng: **replanning vô dụng ở mọi scenario mà robot
*đâm* thay vì *kẹt*.** `crossing_obstacle` cũng vậy.

Và đây cũng là lời giải cho "không thấy đường đi khác": không có replan
nào xảy ra để mà đổi đường. (Nếu có xảy ra thì vẫn còn giới hạn #163 —
đường vẽ trên màn hình là đường của lần plan **đầu** — nhưng ở đây chưa
tới lượt nó.)

## 3. Nguyên nhân 2 — hành lang đơn không có route thay thế

Kể cả nếu trigger có nổ, global replanning vẫn không giải được map này.
`bidirectional_corridor` là **một** hành lang 2 m, chỉ tồn tại **một**
route tôpô từ start tới goal. Global planner lập lại đường bao nhiêu lần
cũng trả về đúng đường đó.

Đối chiếu: map test của Đợt 4.1 là phòng có **hai** cửa — replan tìm ra
cửa còn lại. Có route thay thế thì replanning mới có việc để làm.

Né xe đi ngược chiều trong hành lang đơn là **maneuver cục bộ** (nép sang
một bên rồi đi tiếp), tức việc của local planner, không phải của
replanning.

## 4. Nguyên nhân 3 — DWA không bao giờ đánh lái để né

Đây là phát hiện nặng nhất và chưa được ghi ở đâu. Trace từng bước điều
khiển của một episode (seed 1):

```text
     t  rob_x  rob_y  onc_x  onc_y    gap     v      w
  0.00   1.00   4.00   4.68   4.00   3.03  0.10   0.00
  3.00   1.99   4.00   3.12   4.00   0.47  0.00   0.00
  8.00   3.85   4.00   6.12   4.00   1.62  0.61   0.00
 12.00   6.21   4.00   8.52   4.00   1.65  0.58   0.00
 19.00  10.73   4.00  12.72   4.00   1.34  0.68   0.00
 20.00  11.35   4.00  12.68   4.00   0.68  0.36   0.00
final: collision with dynamic obstacle at (11.476, 3.999) after 20.95s
```

`w` (vận tốc góc) **bằng 0 ở mọi bước**. Tọa độ `y` của robot đứng nguyên
ở 4.00 — đúng tim hành lang — cho tới lúc va chạm. Robot chỉ tăng/giảm
tốc (thậm chí dừng hẳn ở t = 3.0), **chưa từng lệch sang bên một lần
nào**.

### 4.1. Loại trừ giả thuyết "hành lang quá chật"

Giữ nguyên mọi thứ, chỉ nới bề rộng hành lang:

```text
width=2.0m  off/on  {collision: 5}  replans=[0,0,0,0,0]
width=2.5m  off/on  {collision: 5}  replans=[0,0,0,0,0]
width=3.0m  off/on  {collision: 5}  replans=[0,0,0,0,0]
width=4.0m  off/on  {collision: 5}  replans=[0,0,0,0,0]
```

**4 m — thừa chỗ để né — vẫn va chạm 5/5.** Không phải vấn đề hình học.

(Để đầy đủ: ngay ở 2 m thì việc tránh nhau vẫn khả thi về hình học —
robot r = 0.3, xe kia r = 0.35, cần lệch tâm 0.65 m, hành lang cho phép
lệch tối đa 0.70 m. Sát nhưng không phải bất khả.)

### 4.2. Nguyên nhân trong code

**(a) Rollout dùng điểm LiDAR đóng băng.**
`DWAPlanner._rollout_batch` tính clearance của mọi ứng viên `(v, ω)` dựa
trên tập điểm LiDAR **tại vị trí vừa đo được**, và giữ nguyên tập đó
suốt horizon:

```python
diff = points[:, :, None, :] - obstacles[None, None, :, :]
clearances = np.sqrt(...).min(axis=(1, 2))
```

`obstacles` là ảnh chụp một thời điểm. Xe đối diện chạy 0.6 m/s, horizon
1.5 s → **0.9 m** dịch chuyển hoàn toàn không được mô hình hóa.
Controller tính ra "an toàn" cho một tình huống không còn tồn tại vào
lúc nó tới nơi. Đây là giới hạn kinh điển của DWA thuần, không phải lỗi
cài đặt.

**(b) Trọng số kéo về đường lấn át clearance.**

| Thành phần | Trọng số |
|---|---:|
| `goal` | 2.0 |
| `path` | 1.4 |
| `heading` | 1.0 |
| **tổng kéo về đường** | **4.4** |
| `clearance` | 1.2 |

`clearance` còn bị bão hòa: `usable = min(max(clearance − robot.radius,
0), clearance_cap)` với `clearance_cap = 0.6`. Nghĩa là vượt 0.9 m
clearance thì né thêm **không được thưởng gì**.

Lệch sang bên phải trả giá `path` + `goal` **ngay lập tức**, trong khi
lợi ích clearance chỉ xuất hiện ở cuối horizon và bị chặn trần. Nên ứng
viên ω = 0 thắng ở mọi bước.

Ghi chú kỹ thuật: hai ứng viên ±ω đối xứng có chi phí **bằng nhau tuyệt
đối** trên map này (hành lang đối xứng, vật cản đúng trên tim, đường toàn
cục đúng trên tim). Nên kể cả khi né có lợi, còn một câu hỏi thứ hai là
chọn bên nào — DWA hiện không có luật phá thế đối xứng.

## 5. Nguyên nhân 3 **không** phải bug cần vá gấp

Cần nói rõ để tránh đọc sai: nền tảng vừa **đo được một giới hạn thật của
DWA**. Đó đúng là việc một benchmark sinh ra để làm, và nó là kết quả có
giá trị — PathBench và Alyassi et al. đều không báo cáo thứ này.

Điều bắt buộc là **đọc đúng**: con số va chạm trên các scenario có vật
cản động là **giới hạn của baseline**, không phải đặc tính của scenario;
và nó **không** được dùng làm bằng chứng rằng một planner khác tốt hơn,
cho tới khi cả hai chạy dưới cùng ngân sách tinh chỉnh (P01).

## 6. Bằng chứng replanning vẫn hoạt động

Toàn thư viện scenario, cùng phép đo:

| Scenario | off | on(2) | replans |
|---|---|---|---|
| `bidirectional_corridor` | collision 5/5 | collision 5/5 | 0 |
| `crossing_obstacle` | success 2 / collision 3 | success 2 / collision 3 | 0 |
| **`sudden_stop`** | **stuck 5/5**, t = 12.9 | **success 5/5**, t = 23.3 | **1** |
| `doorway` | success 5/5 | success 5/5 | 0 |
| `intersection` | success 5/5 | success 5/5 | 0 |

`sudden_stop`: **stuck 5/5 → success 5/5**, mỗi run replan đúng 1 lần,
thời gian tăng từ 12.9 s lên 23.3 s (đi đường vòng + khoảng chờ hết cửa
sổ stuck). Đây là bằng chứng tính năng chạy đúng.

`doorway` và `intersection` vốn đã success — không có gì để replan.

## 7. Trả lời trực tiếp ba quan sát của dev

1. **"Bật replan vẫn collision"** — đúng. Replan chưa từng chạy vì
   `COLLISION` không phải trạng thái replannable.
2. **"Không thấy đường di chuyển khác đi"** — đúng, và đây là hệ quả
   trực tiếp của (1), không phải lỗi visualization. (Giới hạn #163 về
   đường vẽ là đường plan đầu vẫn còn, nhưng ở map này chưa tới lượt nó.)
3. **"Benchmark không thấy rõ khác biệt giữa có replan và no-replan"** —
   **báo cáo đang nói đúng sự thật.** 4/5 scenario thật sự không khác.
   Muốn thấy khác biệt thì chạy `sudden_stop`.

**"Đề tài quá khó không?"** — Không. Replanning làm đúng thứ nó được
thiết kế để làm (mục 6). Cái thiếu là một baseline biết né vật cản động,
và đó là một stack mới chứ không phải một bản vá.

## 8. Quyết định đã chốt

- **Không sửa code.** Ghi giới hạn: KNOWN_LIMITATIONS **#164** (COLLISION
  không replannable) và **#165** (DWA coi vật cản động là tĩnh).
- **Không nới trigger sang `COLLISION`.** Giữ nguyên định nghĩa thành
  công.
- **Scenario để demo/kiểm chứng replanning là `sudden_stop`**, không phải
  `bidirectional_corridor`.

## 9. Đề xuất cho sau này (chưa làm, chưa approve)

**`dwa_predictive` — một stack MỚI, không phải bản vá của DWA.** Ước
lượng vận tốc vật cản từ hai scan LiDAR liên tiếp, rồi dịch điểm theo
thời gian trong rollout:

```text
p_k = p_0 + v_ước_lượng × (k × horizon_dt)
```

Hai ràng buộc bắt buộc:

1. **Không đọc `dynamic_obstacles_now()`.** Vận tốc phải ước lượng từ
   cảm biến, nếu không thì lớp quan sát bị nâng và ta lặp lại đúng lỗ
   hổng S1 mà Đợt A vừa dọn.
2. **Đăng ký như stack riêng với ngân sách riêng.** Luật P01 cấm nâng cấp
   kiến trúc của một planner giữa chừng vì nó chạy kém — đó chính là lỗ
   hổng S2 mà đề bài phê phán ở Alyassi et al. (họ thay CNN+MLP bằng RNN
   khi RL chạy kém, rồi vẫn xếp chung bảng với baseline không được tinh
   chỉnh gì). Tune tay `weight_path`/`clearance_cap` riêng cho DWA cũng
   vướng đúng luật đó.

Nếu làm, đây là một đóng góp có giá trị: nó biến bảng kết quả thành một
so sánh **reactive vs predictive local planner** dưới cùng lớp quan sát
và cùng ngân sách — đúng loại bằng chứng mà mục 0.5 của đề bài nói hiện
chưa văn liệu nào cung cấp được.
