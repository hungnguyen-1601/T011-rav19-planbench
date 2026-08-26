# Kế hoạch — `dwa_predictive`: bộ điều khiển dự đoán chuyển động vật cản

**Trạng thái:** đã duyệt · **P0–P5 xong** (P5 đóng bằng **kết quả âm**,
xem sửa plan ở test 7.2) · **P6, P7 chưa làm** · **phiên lập kế hoạch riêng**, không gộp
vào hai plan cùng ngày (`mot-su-that-va-cham-va-recovery.md`,
`vung-cam-va-kha-nang-phuc-hoi.md`) — khác phiên, khác phạm vi, và plan
này **giả định hai plan kia đã xong** (phase 1/1b/2/3 đã hiện thực).

**Nền đã đọc:** toàn bộ `reports/` và `plans/` từ 08-08, cộng
`nav_stack.py`, `dwa/planner.py`, `registry.py`, `candidates.py`,
`feasibility.py`, `dynamic.py`, `selection.py`.

---

## 0. Câu hỏi thật sự đang được hỏi

Yêu cầu ban đầu: *"thuật toán dùng để dự đoán chuyển động vật cản thay
vì đứng yên khi gặp vật cản"*. Cần tách hai thứ trong câu đó, vì chúng
là hai lỗi khác nhau và chỉ một cái là do thiếu dự đoán:

| triệu chứng | nguyên nhân | plan nào xử lý |
|---|---|---|
| Robot **kẹt và không thoát ra được** | lưới nhị phân, vành cấm quá rộng, không có recovery | **đã xong** — phase 1/2/3 ngày 14-08 |
| Robot **phanh cứng rồi bò theo sau** một vật cản đang đi ngang | DWA coi mọi điểm LiDAR là **đứng yên vĩnh viễn** | **plan này** |

Chỗ chính xác trong code, và nó chỉ có một dòng:

```python
# dwa/planner.py:318 — _rollout_batch
diff = points[:, :, None, :] - obstacles[None, None, :, :]
```

`points` có trục thời gian (`K` bước rollout). `obstacles` **không có**.
Bộ điều khiển đang lăn quỹ đạo của chính nó qua 1.5 giây tương lai,
nhưng đối chiếu với **một ảnh chụp thế giới tại t=0**, giữ nguyên suốt
horizon. Hệ quả có hai chiều, và chiều thứ hai ít người nghĩ tới:

- **Quá thận trọng** với vật cản đang **rời đi**: một người đã đi khỏi
  cửa vẫn còn đứng đó trong đầu bộ điều khiển suốt horizon, nên khe hở
  bị chấm là hẹp và `clearance` đắt. Robot dừng chờ một chỗ **đã trống**.
- **Quá liều** với vật cản đang **lại gần**: một xe đẩy đi tới ở 1 m/s
  được lăn như thể nó đứng yên, nên quỹ đạo cắt ngang mặt nó được chấm
  là **an toàn**. Đây là chiều nguy hiểm, và mục 5 nói nó không chỉ là
  chuyện chấm điểm — nó chạm vào một **bảo đảm cứng**.

Mục tiêu của plan này **không phải** "làm robot đi nhanh hơn". Là: *bộ
điều khiển lăn thế giới về phía trước cùng lúc với chính nó, và điều đó
được đo bằng một phép so có kiểm soát chứ không bằng cảm nhận khi xem
replay.*

---

## 1. Prior art, và tại sao lấy đúng biến thể này

Ba họ, đã có tên trong tài liệu chứ không phải tôi đặt:

| họ | ý tưởng | vì sao chọn / không chọn |
|---|---|---|
| **DWA + không-thời gian** (Missura & Bennewitz 2019, *Predictive Collision Avoidance for the Dynamic Window Approach*; nhánh DW4DO) | Lăn **cả** quỹ đạo robot **và** quỹ đạo vật cản theo thời gian; kiểm va chạm trong `(x, y, t)` thay vì `(x, y)` | **Chọn.** Sửa đúng dòng code sai ở trên, giữ nguyên cấu trúc DWA (cửa sổ động, lấy mẫu tất định, chấm cost có trọng số). Delta so với `dwa` hiện tại là **cục bộ và đọc được**, nên phép so `dwa` vs `dwa_predictive` cô lập đúng một ý tưởng |
| **Velocity Obstacles / RVO / ORCA** | Làm việc trong không gian vận tốc: tập vận tốc dẫn tới va chạm là một hình nón | Không chọn ở MVP. RVO giả định **đối phương cũng tránh mình** — vật cản trong `dynamic.py` là hàm thuần của `(spec, time, seed)`, **không phản ứng gì**. Dùng RVO ở đây là đo một giả định sai. Còn VO không tương hỗ thì gần như trùng với không-thời gian, chỉ khác biểu diễn |
| **Học (PPO/CADRL)** | Chính sách end-to-end học tránh người | Đã có chỗ trong nền tảng (`astar+ppo`, HĐ-1.2 monolithic), là **hướng khác**, không phải biến thể của DWA. Không thuộc plan này |

**Chốt:** `dwa_predictive` = DWA không-thời gian với mô hình **vận tốc
hằng**, vận tốc **ước lượng từ chính LiDAR**.

---

## 2. Ràng buộc nghiệt ngã nhất, và nó không phải kỹ thuật

`dwa` khai `local_observation_class="lidar_only"`
(`registry.py:245`). Nếu `dwa_predictive` đọc vận tốc vật cản từ
`engine.dynamic_obstacles_now()`, nó thành `lidar+human_states`, và
theo `observation.py` + `candidates.py:_REQUIREMENTS`:

- deployment phải sở hữu `human_state_estimates` (cổng **G6**);
- bảng xếp hạng **mặc định từ chối** xếp chung hai lớp quan sát khác
  nhau — đúng cái khoảng trống S1 (Alyassi et al.) mà nền tảng này sinh
  ra để phơi bày.

Nói thẳng: **một `dwa_predictive` đọc ground truth sẽ thắng `dwa`, và
chiến thắng đó vô nghĩa.** Nó đang so "biết trước tương lai" với "nhìn
bằng cảm biến", không phải so hai bộ điều khiển.

Nên thiết kế bắt buộc:

> Ước lượng vận tốc vật cản phải sinh ra **bên trong bộ điều khiển, từ
> các lần quét LiDAR liên tiếp**. Sai số ước lượng **là một phần của
> thuật toán**, không phải thứ được miễn.

`Observation` đã có đủ để làm điều đó, và đây là điều tôi đã kiểm:
`Observation.time` tồn tại (`episode.py:69`), `pose` và `lidar_ranges`
cũng vậy — tức bộ điều khiển có mọi thứ cần để so hai khung quét cách
nhau một chu kỳ điều khiển đã biết. Không cần nới hợp đồng quan sát nào.

### 2b. Oracle — dụng cụ chẩn đoán, đã chốt làm (P4), không vào registry

Vẫn nên có `dwa_oracle_predictive` đọc thẳng ground truth, **không phải**
để xếp hạng mà để trả lời: *"nếu tri giác hoàn hảo thì dự đoán đáng giá
bao nhiêu?"*. Nó khai `lidar+human_states`, và khoảng cách giữa nó và
`dwa_predictive` chính là **giá của việc phải tự ước lượng**.

Nếu làm: **không đăng ký vào registry** — không phải vì kỷ luật mà vì
không đăng ký nổi: factory của registry có chữ ký `config -> LocalPlanner`,
không có engine nào để đóng nguồn ground truth vào. Oracle sống trong
một script chẩn đoán, được dựng trực tiếp với một provider, chạy qua
`run_stack`. Nó không bao giờ là candidate, không bao giờ lên
`/candidates`, và không ai phải nhớ đừng khuyến nghị nó — nó **không có
đường** để được khuyến nghị. (Chi tiết provider ở P4.)

**Oracle chỉ được biết *hiện tại*, không được biết *tương lai*.** Nó
nhận `(vị trí, vận tốc)` thật **tại thời điểm này** và ngoại suy bằng
**đúng mô hình vận tốc hằng** mà `dwa_predictive` dùng. Cho nó đọc
`position_at(obstacle, t + k·dt, seed)` thì nó không còn là "tri giác
hoàn hảo" — nó là **biết trước tương lai**, và khi đó khoảng cách giữa
hai ứng viên trộn lẫn *sai số ước lượng* với *sai số mô hình*, tức
không đo được cái nào.

Với ràng buộc này, oracle đo **đúng một thứ**: giá của việc phải tự ước
lượng. Trên `sudden_stop` nó sai **cùng kiểu** với `dwa_predictive` —
cả hai ngoại suy vận tốc hằng xuyên qua cú dừng cho tới khi *quan sát*
được cú dừng, oracle hồi sau một `Δt`, tracker hồi sau cửa sổ của nó —
và đó là dấu hiệu oracle được dựng đúng (test 7.9a phát biểu chính xác
ba pha của chuyện này).

---

## 2c. Một tiền đề chưa thoả: **robot và vật cản đang ở hai hệ toạ độ**

Đây là thứ phải chốt **trước** khi viết dòng tracking đầu tiên, và nó là
một defect **đang tồn tại của `dwa`**, không phải của plan này. Đã kiểm
trên code:

| | pose nào | nguồn |
|---|---|---|
| Rollout robot | `state.pose` — **pose thật** | `engine.get_state()` → `self._robot` (`engine.py:261`) |
| Điểm LiDAR | `observation.pose` — **pose robot tin là** | `engine.get_observation()` → `_believed_pose()` (`engine.py:280`) |

`_rollout_batch` (`planner.py:304`) dựng quỹ đạo từ `state.pose`;
`_obstacle_points` (`planner.py:435`) dựng đám mây từ `observation.pose`.
Hai đại lượng bị **trừ cho nhau** ở dòng `diff` — trong khi chúng lệch
nhau đúng bằng sai số định vị. `_nearest_obstacle_distance`
(`planner.py:399`) cũng trộn đúng hai thứ đó, nghĩa là **bảo đảm phanh
của phase 1b đang được đo vắt qua hai hệ toạ độ**.

Hôm nay điều này chỉ làm khoảng hở lệch một hằng số. **Với tracking nhiều
khung thì nó thành vận tốc**: `pose_error` là tổng các sin, nó *dao động*
theo bước, nên tường đứng yên sẽ có vận tốc dao động. Sàn nhiễu ở [2]
chặn được **biên độ**, không chặn được việc hai hệ toạ độ khác nhau —
đúng như phản biện đã nêu.

**Hợp đồng đúng, và nó chính là thứ `SafetyEnvelope` sinh ra để làm:**

```
Bộ điều khiển HÀNH ĐỘNG trong  believed frame  (nó không có pose thật)
Test  PHÁN XỬ    trong          true frame      (thế giới thì có)
position_uncertainty_m là số hạng BẮC CẦU giữa hai cái
```

Robot thật không có `get_state()`. Một bộ điều khiển đọc pose thật là
một bộ điều khiển không tồn tại được ngoài đời — và nền tảng này đã trả
giá một lần cho đúng loại đặc quyền đó (HĐ-4.1, `_replan` đọc
observation chứ không đọc ground truth). Nên: **mọi thứ `compute()` làm
đều chạy trên `observation.pose`**, và test phase 1b giữ nguyên việc
phán xử bằng pose thật (đúng như plan 14-08 §7.3 đã đòi).

**Giá phải trả, nói trước:** sửa việc này **đổi quỹ đạo của `dwa`** trên
mọi deployment khai nhiễu định vị ⇒ mọi số đo cũ phải đo lại ⇒
`task_profile_id` mới. Nó là **một pha riêng**, không nhét vào plan này.

**Cho tới khi pha đó xong**, phép so đầu tiên chạy với
`localization_drift_m = 0` và `localization_jump_probability = 0`, và
báo cáo **ghi thẳng** rằng kết quả **không nói gì** về độ bền trước
nhiễu định vị. Lưu ý kèm theo: form deployment hiện bật sẵn cả bảy
luồng nhiễu, nên deployment "không nhiễu định vị" **không phải** cấu
hình mà team đang chạy hằng ngày — đây là một cấu hình đo, và phải được
gọi đúng tên như vậy.

---

## 3. Kiến trúc — ba khối, và chỉ khối thứ ba là DWA

```
LiDAR scan (t)  ──▶  [1] phân cụm  ──▶  [2] ghép cặp + ước lượng vận tốc
                                              │
                                              ▼
                                    [3] rollout không-thời gian  ──▶  (v, ω)
```

### [1] Phân cụm — từ điểm rời rạc thành vật thể

Hiện `_obstacle_points` (`dwa/planner.py:435`) trả về một đám mây điểm
**không danh tính**. Không có danh tính thì không ghép cặp được giữa hai
khung, và không ghép cặp được thì không có vận tốc.

- Gom theo tia liền kề, cắt cụm khi bước nhảy khoảng cách vượt ngưỡng
  (adaptive breakpoint). Duyệt theo thứ tự tia cố định ⇒ **tất định**,
  đúng yêu cầu `LocalPlanner`.
- Ngưỡng cắt cụm suy từ **hình học cảm biến**, không từ thế giới: ở tầm
  `r` với độ phân giải góc `Δθ = angle_span / num_rays`, hai điểm liền
  kề trên cùng một mặt phẳng cách nhau `≈ r · Δθ`. Ngưỡng là bội số của
  đại lượng đó cộng biên `lidar_range_sigma_m`. Cả hai đều nằm trong
  `LidarConfig` và `SensorNoise` — thứ bộ điều khiển **được phép biết**
  vì đó là đặc tả cảm biến của chính nó.
- Mỗi cụm: tâm + bề rộng + số điểm.

**Cụm nào *không* được theo dõi — và tiêu chí không phải kích thước
thật.**

Bản đầu của plan này định suy ngưỡng từ `DynamicObstacle.radius` lớn
nhất deployment khai. **Sai, và sai đúng kiểu mục 2 vừa cấm.** Danh sách
vật cản động là ground truth của scenario; một bộ điều khiển
`lidar_only` đọc nó là đang biết trước *trong phòng này có những vật thể
to cỡ nào* — rò rỉ nhẹ, nhưng cùng họ với rò rỉ mà cả nền tảng này sinh
ra để phơi bày. Và nó lộ ra ngay khi ai đó chạy `dwa_predictive` trên
một map lạ: ngưỡng đến từ một tri thức không có ở đó.

Tiêu chí đúng cũng không phải kích thước, mà là **tính bị chặn và tính
bền**, cả hai đọc được từ chính lần quét:

| dấu hiệu | ý nghĩa | quyết định |
|---|---|---|
| Cụm **chạm mép quét** (giáp tia đầu/cuối của một khoảng liên tục, hoặc kéo dài qua vùng ngoài `max_range`) | không biết nó dừng ở đâu ⇒ không có tâm để theo dõi | tĩnh |
| Cụm **thẳng và dài** (dư bình phương của khớp đường thẳng nhỏ trên bề rộng lớn) | tường, kệ hàng | tĩnh |
| Cụm **bị chặn hai đầu**, bề rộng nhỏ, cong | vật thể rời | theo dõi |

Ngưỡng của ba dấu hiệu này là **tham số của candidate**, khai rõ trong
`DWAPredictiveConfig`. Đó là chỗ đúng cho chúng: chúng thuộc lớp 3, chỉ
ảnh hưởng **chi phí mềm** (mục 4), nên một ứng viên chỉnh chúng không
đụng được vào miền cứng. Nói thẳng là ứng viên này **có nhiều núm vặn
hơn `dwa`** — và đó là một sự thật về thuật toán phải được ghi trên
`/candidates` chứ không giấu đi: một bộ theo dõi là một mô hình, và mô
hình thì có tham số.

### [2] Ghép cặp + vận tốc — chỗ dễ sai nhất, và tôi liệt kê trước

- **Ghép cặp:** tâm gần nhất giữa hai khung, trong bán kính cổng
  `association_speed_limit · Δt + biên nhiễu`.

  **`association_speed_limit` không phải `v_obstacle_max`, cố ý.** Bản
  trước dùng chung một trường và đó là một bug phụ thuộc: cổng ghép cặp
  cần con số này **kể cả khi P0 âm tính và P1 bị bỏ**. Nhưng lý do tách
  sâu hơn chuyện phụ thuộc — hai con số **hỏng theo hai kiểu khác
  nhau**:

  | | chủ | sai thì chuyện gì xảy ra | lớp |
  |---|---|---|---|
  | `v_obstacle_max` | deployment | bảo đảm phanh thủng ⇒ **va chạm** | 2, cứng |
  | `association_speed_limit` | candidate | ghép cặp hỏng ⇒ tracker **thoái lui về `dwa`** | 3, mềm |

  Một tham số mà sai chỉ làm ước lượng kém đi thì thuộc candidate; một
  tham số mà sai làm robot đâm thì thuộc deployment. Hai chế độ hỏng
  khác nhau không được là một trường.

  Và default của `association_speed_limit` **không được suy từ tốc độ
  vật cản thật của scenario** — cùng lối rò rỉ ground truth vừa gỡ ở
  ngưỡng cụm. Nó là một knob của candidate, khai thẳng trong
  `DWAPredictiveConfig`, hiện trên `/candidates` như mọi tham số khác.
- **Vận tốc:** sai phân trên một cửa sổ vài khung (bình phương tối thiểu
  ngắn), không phải hai khung liền — hai khung liền thì nhiễu tầm quét
  ăn thẳng vào đạo hàm.
- **Sàn nhiễu — bắt buộc, và phải *suy ra*.** Robot tin sai vị trí của
  chính nó thì **tường sẽ có vận tốc**. `SafetyEnvelope.for_noise` đã
  cho biên sai số vị trí; `lidar_range_sigma_m` cho nhiễu tầm. Sàn:

  ```
  v_floor ≈ (2 · position_uncertainty_m + k · lidar_range_sigma_m) / window_seconds
  ```

  Dưới sàn ⇒ **vận tốc bằng 0**, coi là tĩnh. Suy ra từ thứ deployment
  đã khai, giống hệt cách `SafetyEnvelope` và `N_min` được suy — **không
  thêm một núm vặn nào**. Đây là điểm tôi cho là quan trọng nhất của cả
  plan: **không có sàn này, `dwa_predictive` sẽ tệ hơn `dwa` trên mọi
  cảnh tĩnh**, và nó sẽ tệ *đúng lúc* deployment khai nhiễu định vị —
  tức đúng lúc dự án này muốn đo.

- **Ba nguồn vận tốc ma đã biết trước, ghi ra để lần đo sau khỏi ngơ
  ngác:** (a) tâm cụm trượt khi vật thể **lộ dần ra** sau góc khuất —
  vật đứng yên "chạy" tới nửa bề rộng của nó; (b) `lidar_dropout_probability`
  làm cụm vỡ đôi rồi liền lại; (c) hai vật đi ngang nhau ⇒ ghép cặp
  chéo, hai vận tốc đảo chiều.

  Không cái nào giải được triệt để ở mức tri giác 2D này. Cách xử lý
  trung thực: **để chúng xảy ra, chặn chúng ở tầng an toàn (mục 4), và
  đo chúng** — số cụm được theo dõi, số lần ghép cặp hỏng, sai số vận
  tốc so ground truth (chỉ để **chẩn đoán**, không vào bất cứ metric nào
  được xếp hạng).

**Vòng đời một track — phải khai rõ, vì mặc định ngầm ở đây đều nguy
hiểm.** Bản trước bỏ trống mục này; đó là thiếu sót, vì mọi trường hợp
dưới đây **chắc chắn xảy ra** trong mọi episode có traffic:

| tình huống | quy tắc | vì sao |
|---|---|---|
| **Khởi động** (chưa đủ khung để ước lượng) | vận tốc = **0**, hành xử **y hệt `dwa`** | Đoán vận tốc từ một khung là bịa. Vài chu kỳ đầu chưa có thông tin thì đừng vờ là có |
| **Track mới xuất hiện** | vận tốc = 0 cho tới khi đủ cửa sổ | như trên |
| **Mất dấu** (không ghép được ở khung này) | **giữ track, ngoại suy, giảm tin cậy**; hết `track_timeout` thì xoá | Che khuất một phần là chuyện thường; xoá ngay thì mỗi lần khuất là một lần khởi động lại và vận tốc về 0 đúng lúc cần nhất |
| **Vật thể bị che rồi hiện lại** | thành track **mới** | Ghép lại qua khoảng khuất dài là bài toán khác (re-identification), không thuộc MVP |
| **Ghép cặp mơ hồ** (hai ứng viên trong cổng) | **bỏ cả hai**, vận tốc = 0 | Ghép sai sinh vận tốc đảo chiều — tệ hơn không ghép |

Nguyên tắc chung của cả bảng, và nó là cùng một câu: **mọi chế độ hỏng
đều thoái lui về `dwa`**. Bộ theo dõi hỏng ⇒ ứng viên trở thành bộ điều
khiển gốc, không phải một bộ điều khiển gốc mang vận tốc rác.

### [3] Rollout không-thời gian — và nó gần như **miễn phí**

```python
# hiện tại: (N,K,2) - (1,1,M,2)
diff = points[:, :, None, :] - obstacles[None, None, :, :]
# dự đoán:  (N,K,2) - (1,K,M,2)   với obstacles_at[k] = p + v·(k·dt)
```

Điều tôi đã kiểm và nó quan trọng cho cổng **G4**: phép broadcast hiện
tại **đã** tạo tensor `(N, K, M, 2)`. Cho vật cản một trục thời gian
`(K, M, 2)` broadcast vào **đúng cùng hình dạng đó** — chi phí của phép
tính nặng nhất **không đổi**. Phần thêm là phân cụm + ghép cặp, `O(M)`
mỗi bước điều khiển với `M = num_rays = 72`, tức nhỏ hơn nhiều so với
`N·K·M` (800 × 20 × 72 ở `dwa_default`).

**Dự đoán trước khi đo, ghi ở đây để bản báo cáo sau biết cái nào có
trước:** p99 của `dwa_predictive` cao hơn `dwa` **dưới 20%** ở cùng mật
độ lấy mẫu. Nếu ra khác, đó là câu trả lời và ứng viên vẫn được đăng ký
nói đúng như thế — đúng tinh thần đã áp cho `dwa_balanced`.

---

## 4. Ranh giới cứng/mềm — chỗ plan này dễ phá hợp đồng L1–L4 nhất

Đây là mục cần dev đọc kỹ nhất. Phase 1 vừa dựng xong một **miền khả thi
cứng dùng chung**, và dự đoán có thể phá nó bằng cửa sau.

Hiện tại phép từ chối cứng là:

```python
keep_out = hard_clearance(robot, self._envelope)   # planner.py:189
if clearances[index] <= keep_out: continue         # planner.py:194
```

**Cám dỗ:** cho `clearances` thành khoảng hở **dự đoán**, giữ nguyên
phép từ chối. Đừng.

Vì sao: khi đó một ứng viên khai `prediction_horizon` dài hơn sẽ có
**miền khả thi hẹp hơn** — một tham số của candidate lại thu hẹp miền
cứng. Đúng nguyên văn cái **L2** cấm, và đúng cái defect
`safety_margin` vừa bị tách đôi để sửa (mục 1.4 plan 14-08).

**Cách sửa đã có tiền lệ trong chính dự án này — tách đôi, không chọn
một bên:**

| | thuộc về | đo trên cái gì |
|---|---|---|
| **Từ chối cứng** | lớp 2, deployment sở hữu | khoảng hở tới **các điểm đo được tại thời điểm hiện tại** — **y như hôm nay, không đổi một dòng** |
| **Chi phí mềm** | lớp 3, candidate sở hữu | khoảng hở **dự đoán** dọc horizon; time-to-collision; phạt cắt mặt vật cản đang tới |

Đọc ra: **dự đoán mua tốc độ và sự mượt, không mua an toàn.** An toàn
vẫn do bảo đảm phanh + miền cứng của phase 1/1b lo. `dwa_predictive`
không được phép **đi vào chỗ** mà `dwa` bị cấm; nó chỉ được phép **đi
qua sớm hơn** chỗ mà cả hai đều được đi.

### 4b. "Miền cứng" gồm **hai** ràng buộc, không một — và bản trước đã lẫn

Phản biện của dev đúng, và chỗ lẫn nằm ở đây. Bộ điều khiển có **hai**
thứ cứng, không phải một:

| | ràng buộc | ở đâu |
|---|---|---|
| **(a)** | Từ chối theo **tập**: `clearances[i] <= keep_out` | `planner.py:194` |
| **(b)** | Chặn theo **vận tốc**: `v_max = min(v_max, stopping_limit)` | `planner.py:277` |

Mục 4 ở trên nói "miền khả thi cứng không đổi" và tôi **đang nói về
(a)**. Nhưng mục 5 bản trước lại đề xuất cho `dwa_predictive` **nới (b)**
ở chỗ nó chứng minh được vật cản đang rời xa. Đó vẫn là **một tham số
candidate nới một ràng buộc cứng**, chỉ là nới ràng buộc thứ hai. Và nó
làm test 7.4 (*"hai controller từ chối đúng cùng tập (v, ω)"*) **không
thể đúng**, vì `stopping_limit` cắt thẳng vào `v_max` tức đổi luôn tập
được lấy mẫu.

**Chốt: MVP không nới (b).** Cả hai ràng buộc cứng giữ nguyên, giống hệt
nhau ở hai ứng viên. Dự đoán chỉ vào cost.

**Và có một lập luận độc lập mạnh hơn cả lập luận hợp đồng**, đủ để
đóng cửa hướng kia kể cả khi ai đó tìm được cách khai `prediction_horizon`
ở tầng deployment:

> **Ước lượng dùng để *nới* an toàn thì lỗi ước lượng thành va chạm.
> Ước lượng dùng trong *cost* thì lỗi ước lượng chỉ thành đi kém tối
> ưu.**
>
> Chính plan này, ở mục [2], đã liệt kê **ba nguồn vận tốc ma** không
> giải được triệt để ở mức tri giác 2D. Cho một đại lượng có ba chế độ
> hỏng đã biết cái quyền hạ ngưỡng an toàn là chọn đúng chiều sai.

Nếu sau này thật sự muốn nới (b) bằng ước lượng, nó là **một pha riêng**
với những thứ MVP không có: cận tin cậy trên vận tốc chứ không phải giá
trị điểm, hành vi khi mất dấu, và một hợp đồng an toàn mở rộng có test
riêng. Ghi lại ở đây để lần sau không phải nghĩ lại từ đầu, **không**
làm ở MVP.

Hệ quả kèm theo, và nó tốt: **L1 và L4 không phải sửa gì.** Validator
của L4 đo đường của global trên miền liên tục tại thời điểm lập kế
hoạch; dự đoán không đụng vào miền đó.

**Một hệ quả phải chấp nhận và ghi ra:** với ràng buộc này,
`dwa_predictive` **có thể vẫn va chạm** trong ca vật cản lao tới nhanh,
đúng bằng mức `dwa` va chạm. Nó không được thiết kế để cứu ca đó — mục 5
mới là chỗ ca đó thuộc về.

---

## 5. Phát hiện phụ khi đọc code: bảo đảm phanh **chưa tính vật cản đang lại gần**

Chưa đo. Đây là **phân tích từ đọc code**, và mục 7 có test tái hiện để
xác nhận hoặc bác bỏ trước khi ai đó tin nó.

Phase 1b vừa đưa admissibility về đúng công thức gốc:

```python
to_obstacle = self._nearest_obstacle_distance(obstacles, state)   # planner.py:274
headroom   = max(0.0, min(to_goal, to_obstacle))
stopping_limit = self._speed_that_stops_within(headroom, robot)
```

`_nearest_obstacle_distance` (`planner.py:399`) đo tới **các điểm của
lần quét hiện tại**, tức **coi vật cản đứng yên**. Bảo đảm phát biểu
được là: *"robot dừng kịp trước chỗ vật cản **đang** đứng"*.

Với vật cản đang lại gần ở tốc độ `u`, khe hở co lại theo `(v + u)`
trong khi robot chỉ dự trù `v`. Số cụ thể trên robot mặc định
(`v=0.8`, `a=0.5`): quãng phanh 0.64 m, thời gian phanh 1.6 s. Vật cản
đi tới ở 1.0 m/s **đi thêm 1.6 m** trong khoảng đó. Bảo đảm cần khe hở
≈ 2.24 m nhưng chỉ đòi 0.64 m.

**Vì sao điều này quan trọng hơn nó thoạt nghe.** Nó nằm ở **lớp 2** —
đúng chỗ phase 1b vừa dựng lên để an toàn thôi phụ thuộc trọng số của
candidate. Nếu đúng, thì bảo đảm đó **vẫn đang thủng**, chỉ là thủng theo
trục thời gian thay vì trục trọng số.

**Và nó không được sửa bằng `dwa_predictive`.** Nếu chỉ ứng viên dự đoán
mới an toàn trước vật cản đang tới, phép so **đo an toàn** chứ không đo
dự đoán — đúng lập luận đã dùng để đẩy recovery lên deployment. Sửa phải
áp cho **cả hai**, và bằng thứ **không cần ước lượng**:

> Chặn tốc độ theo khe hở tương lai xấu nhất, với giả định vật cản có
> thể lại gần ở tối đa `v_obstacle_max` — **khai trên deployment**,
> giống nhau cho mọi ứng viên, ghi vào manifest. Đúng cách đã xử lý λ,
> `sensor_noise` và `replanning`.

**Và dừng đúng ở đó.** Bản trước của plan này đi thêm một bước — cho
`dwa_predictive` *nới* biên xấu nhất ở chỗ nó chứng minh được vật cản
đang rời xa. Mục 4b vừa bác bỏ bước đó: nó là ước lượng nới an toàn, và
nó phá test 7.4. Nên mục 5 là **một pha an toàn thuần tuý, áp cho cả
hai ứng viên như nhau**, và `dwa_predictive` **không hưởng lợi gì** từ
nó. Nếu về sau muốn biến biên xấu-nhất thành biên có điều kiện, đó là
pha nêu ở cuối 4b.

### 5b. `v_obstacle_max` phải **được simulator kiểm chứng**, không chỉ được khai

Một con số khai trên deployment mà không ai kiểm thì không phải bảo đảm
— nó là một dòng chữ. Profile khai 1.0 m/s trong khi một
`WaypointMotion` chạy 1.5 m/s thì bảo đảm phanh sai **đúng bằng chỗ nó
được tin tưởng nhất**.

Tin tốt, đã kiểm trên `dynamic.py`: **cả bốn luật chuyển động đều có cận
trên tốc độ đóng dạng**, nên validator là **toàn phần**, không có nhánh
"không chứng minh được":

| motion | cận trên tốc độ |
|---|---|
| `WaypointMotion` | `speed` |
| `RandomWalkMotion` | `speed` |
| `SuddenStopMotion` | `speed` |
| `PeriodicMotion` | `π · \|end − start\| / period` (đạo hàm của `0.5·(1−cos)`) |

Validator chạy lúc **nạp deployment**, từ chối ngay, đúng hình dạng
"fail at startup" của HĐ-1.4 — một profile sai phát hiện sau 300 episode
là 300 episode trả lời một câu hỏi khác. Nhánh từ chối vẫn phải viết cho
luật chuyển động **tương lai** nào không chứng minh được cận trên: khi
đó deployment bị từ chối, hoặc chạy được nhưng **không được phép mang
tuyên bố an toàn đó**.

**Đề xuất thứ tự:** làm mục 5 **trước** mục 3. Cùng lập luận "công bằng
trước năng lực" mà plan 14-08 đã dùng để xếp (2) trước (3). Nếu đo xong
thấy lỗ hổng **không** tái hiện được, bỏ mục 5, ghi lại kết quả âm, và
đi thẳng vào mục 3.

---

## 6. Nối vào nền tảng — chỗ nào phải sửa, chỗ nào tự chạy

| chỗ | việc | ghi chú |
|---|---|---|
| `packages/planning/planbench_planning/dwa_predictive/` | module mới | **Không kế thừa `DWAPlanner`**. Kế thừa thì hai ứng viên dùng chung code và một sửa lỗi ở lớp cha lặng lẽ đổi cả hai — trong khi `StackComponent.version` là *một phần của candidate id*. Tách phần dùng chung ra hàm thuần, hai lớp gọi vào |
| `registry.py` | `astar+dwa_predictive`, `rrtstar+dwa_predictive` | `local_observation_class="lidar_only"`, `benchmarkable=True`. Mô tả phải nói **vận tốc là ước lượng, mô hình là vận tốc hằng** — lên thẳng `/candidates`, đúng tiền lệ `_RRT_STAR_DESCRIPTION` |
| `candidates.py` → `CONTROLLER_CONFIGS` | thêm khoá `"dwa_predictive"` với `coarse/balanced/default` | Cùng mật độ lấy mẫu với `dwa` để trục latency so được. Docstring đã nói "Adding a controller is adding a key here" — kiểm lại xem có đúng thế thật không |
| **`LOCAL_CONTROLLER_CONFIGS` — một lỗ hổng đang có** | tên config **phẳng toàn cục**, và **không chỗ nào kiểm** tên config có thuộc đúng controller của stack không | `astar+dwa_predictive:dwa_coarse` sẽ **chạy**, vì mọi tham số của `dwa_coarse` cũng hợp lệ với `dwa_predictive`, và báo cáo sẽ ghi `local_controller_config: dwa_coarse` trên một ứng viên **không phải dwa**. `CONTROLLER_OF_CONFIG` đã tồn tại, chưa ai dùng để chặn. **Thêm một phép kiểm ở `build_candidates`** trước khi có ứng viên thứ hai làm chuyện này thành hiện thực |
| **`StackComponent.version` — lỗ hổng thứ hai đang có** | code dùng chung phải đi vào **cả hai** candidate id | `candidate_from_stack` nhận `local_version: str = "v1"` (`candidates.py:132`) và **không caller nào truyền vào** — `selection.py:172` và `decision_service.py:313` đều để mặc định. Tức **mọi candidate đều là `v1` vĩnh viễn**, và docstring của `StackComponent` đang hứa ngược lại: *"cùng một DWA sau khi sửa lỗi là một candidate khác"*. Hôm nay là nợ; ngày `dwa` và `dwa_predictive` dùng chung một lõi thì **một sửa lỗi ở lõi lặng lẽ đổi cả hai ứng viên mà artifact không ghi lại gì**. Sửa: `local_version` lấy từ checksum của **module điều khiển + module lõi dùng chung** |
| UI | **không phải sửa** (kết luận vòng 3; vòng 2 từng nói cần nhãn riêng) | Lý do đổi: oracle **thôi đăng ký registry** — factory không có engine để đóng provider vào, nên nó dựng trực tiếp trong script chẩn đoán (P4). Không có trong registry thì không lên `/candidates`, và `CandidatePicker.tsx:44` vốn đã lọc `benchmarkable` cho phần còn lại. Hai stack `dwa_predictive` thường tự hiện qua registry như mọi stack khác |
| `TaskProfile` | chỉ sửa **nếu** làm mục 5 (`v_obstacle_max`) | Nếu bỏ mục 5 thì **không đụng gì** |
| `docs/KNOWN_LIMITATIONS.md` | mục mới | Vận tốc hằng; ba nguồn vận tốc ma; không tương hỗ |

### Điều tốt nhất của plan này về mặt hợp đồng

**Không cần `task_profile_id` mới.** Recovery, λ và inflation đổi *episode
là cái gì* nên bắt buộc sinh deployment mới (mục 5 plan 14-08). Dự đoán
là chuyện của **candidate**: thế giới không đổi, `episode_context_id`
không đổi, nên `dwa` và `dwa_predictive` **dùng chung y hệt tập context**
và ghép cặp bootstrap chạy thẳng. `candidate_id` tự khác vì params khác.

**Trừ khi làm mục 5** — `v_obstacle_max` là ràng buộc deployment và
**đổi cả hai ứng viên**, nên khi đó **phải** có profile mới. Đó là lý do
thứ hai để tách mục 5 thành pha riêng và làm trước.

### Scope của phép so

```
--candidates astar+dwa:dwa_balanced,astar+dwa_predictive:dwa_predictive_balanced \
--scope local_controller_selection
```

`validate_experiment_scope` sẽ đòi **tầng global giống hệt** — đúng cái
ta muốn. `--scope` đã có sẵn ở `scripts/compare.py:91`.

---

## 7. Test bắt buộc

1. **Vận tốc hằng ⇒ dự đoán đúng.** Vật cản `waypoint` chạy thẳng, không
   nhiễu: vận tốc ước lượng hội tụ về vận tốc thật trong sai số nêu rõ.
   Không đạt thì mọi thứ phía sau vô nghĩa.

2. **Thế giới tĩnh ⇒ dự đoán *không đổi gì*.** Trên cảnh không có vật
   cản động, `dwa_predictive` phải cho quỹ đạo **giống `dwa`** trong sai
   số số học. Đây là test quan trọng nhất của cả bộ: nó ghim rằng phần
   thêm chỉ kích hoạt khi có chuyển động thật. Chạy **có bật nhiễu định
   vị** — đó là lúc sàn nhiễu ở mục [2] bị thử thật.

   > ### ⛔ SỬA PLAN 15-08 — tiêu chí này **KHÔNG ĐẠT ĐƯỢC** với thiết kế MVP
   >
   > *(An chốt 15-08. Sửa có chủ ý, không phải bỏ qua.)*
   >
   > Đo được ở P5, trên ba cảnh **hoàn toàn tĩnh** và tắt **mọi** luồng
   > nhiễu — nên không một con số nào dưới đây là nhiễu cảm biến:
   >
   > | cảnh | vận tốc ma trung vị | lớn nhất |
   > |---|---|---|
   > | `doorway` | 0.28 m/s | **1.01** |
   > | `static_obstacles` | 0.41 m/s | **1.27** |
   > | `narrow_corridor` | 0.04 m/s | 0.35 |
   >
   > Traffic thật của thư viện chạy 0.6–0.8 m/s. **Vận tốc ma cùng bậc độ
   > lớn với tín hiệu thật**, nên "quỹ đạo giống `dwa`" là bất khả.
   >
   > **Nguyên nhân là hình học, không phải ngưỡng.** Một centroid tracker
   > 2D không phân biệt được cột tĩnh 0.75 m với người đi bộ bằng hình
   > dạng; và tâm cụm dịch khi **góc nhìn** của robot đổi, không chỉ khi
   > vật đổi. Với LiDAR 72 tia (5.00°/tia), một vật 0.35 m ở 4 m rộng
   > **2 tia** — không đủ điểm để nói nó là gì.
   >
   > **Sàn nhiễu của plan (mục [2]) cũng thiếu một số hạng:**
   > `(2·position_uncertainty + k·σ_range)/window` **bằng đúng 0** trên
   > deployment không nhiễu. Đã thêm số hạng lượng tử hoá quét
   > `reach·Δθ/window` — tồn tại với cảm biến hoàn hảo. Nó giúp
   > `narrow_corridor` (95 → 31 track có vận tốc) và **không đóng được**
   > hai cảnh kia.
   >
   > **Tiêu chí thay thế, yếu hơn và được nói rõ là yếu hơn:** provider
   > rỗng ⇒ lệnh **giống hệt từng byte** với `dwa`. Nó ghim công tắc
   > (mọi chế độ hỏng của tracker thoái lui về `dwa`) nhưng **không** ghim
   > điều 7.2 thật sự hỏi — *tracker có phân biệt nổi vật tĩnh không*.
   > Câu trả lời đo được: **không**.
   >
   > **P5 đóng lại bằng kết quả âm.** Plan đã nói trước rằng một kết quả
   > âm là một kết quả; đây là một cái. Thứ **vẫn** đứng vững: ràng buộc
   > cứng không bị chạm, nên ma chỉ vào **chi phí**. Nhưng xem cảnh báo ở
   > cuối mục 4 — điều đó **không** đồng nghĩa "không thể làm va chạm tệ
   > hơn".

3. **`sudden_stop` — ca đối kháng, và nó đã có sẵn trong thư viện.**
   `SuddenStopMotion` là **phản ví dụ hoàn hảo** của vận tốc hằng: vật
   cản chạy đều rồi **đứng phắt**. Dự đoán sẽ nói nó còn đi tiếp và robot
   sẽ lách vào chỗ nó **không hề tới**.

   Phát biểu test theo **cái không được xảy ra**, không theo "phải tốt
   hơn": `dwa_predictive` **không được va chạm nhiều hơn** `dwa` trên
   `sudden_stop` ở cùng tập seed. Chậm hơn thì được — đó là kết quả và sẽ
   được báo cáo đúng như thế.

4. **Hai ràng buộc cứng, kiểm **cả hai**.** Với cùng
   `(state, observation)`:
   - (a) tập `(v, ω)` **bị từ chối** của `dwa_predictive` **bằng đúng**
     của `dwa`;
   - (b) `v_max` sau khi áp `stopping_limit` **bằng đúng** ở hai ứng
     viên.

   Bản trước chỉ phát biểu (a), và đó chính là chỗ mâu thuẫn ở 4b lọt
   qua. Test này là hàng rào của quyết định 4b: nó đỏ ngay ngày ai đó
   cho `clearances` thành khoảng hở dự đoán, **và** ngày ai đó cho ước
   lượng nới giới hạn phanh.

4b. **Mọi chế độ hỏng của tracker thoái lui về `dwa`.** Ép tracker vào
   từng ô của bảng vòng đời ở [2] — chưa đủ khung, mất dấu, ghép cặp mơ
   hồ — và đòi lệnh phát ra **bằng đúng** lệnh của `dwa` ở bước đó.

5. **L4 vẫn xanh trên cả hai stack** (`astar+dwa_predictive` và
   `rrtstar+dwa_predictive`). Không sửa validator, chỉ mở rộng tập chạy.

6. **Tất định.** Cùng seed ⇒ cùng byte. Bộ theo dõi mang **trạng thái
   giữa các bước** — thứ `DWAPlanner` gần như không có (chỉ `_previous`)
   — nên `reset()` phải xoá sạch. Test: chạy hai episode liên tiếp trên
   một instance, kết quả phải bằng chạy hai instance riêng.

7. **Repro cho mục 5** (nếu làm): `crossing_obstacle` với vật cản tốc độ
   cao, `weight_clearance=0`, horizon ngắn — đúng công thức đã lộ ra lỗ
   hổng phanh lần trước. Phát biểu theo **tính chất ở mọi bước**, không
   theo tình huống, đúng như test phase 1b.

8. **Validator `v_obstacle_max`** (nếu làm mục 5): deployment khai
   0.5 m/s với một `PeriodicMotion` đi 1.2 m/s **phải bị từ chối lúc
   nạp**, không phải lúc chạy. Một ca cho mỗi loại trong bốn luật.

9. **Oracle không biết trước tương lai** — hai nửa, hai pha, vì nửa sau
   cần tracker mà tracker tới P5 mới có:
   - **7.9a (P4):** trên `sudden_stop`, ba pha — ranh giới là *quan
     sát*, không phải *sự kiện*:

     | pha | provider phải trả | oracle phải làm |
     |---|---|---|
     | `t < stop_time` | vận tốc trước-dừng, **khác 0** | ngoại suy vận tốc hằng **xuyên qua** `stop_time` khi horizon vượt nó — vị trí dự đoán sau `stop_time` vẫn di chuyển |
     | `stop_time ≤ t < stop_time+Δt` | vận tốc **tắt dần** (sai phân ăn một phần cửa sổ) | theo con số đó |
     | `t ≥ stop_time+Δt` | **0** | ngừng ngoại suy chuyển động |

     Pha đầu chứng minh không đọc tương lai; pha cuối chứng minh biết
     hiện tại. Bản vòng 4 đòi provider trả vận tốc trước-dừng **sau**
     `stop_time` — mâu thuẫn với chính công thức sai phân về quá khứ
     (vật đứng yên đủ một `Δt` thì sai phân bằng 0 theo định nghĩa), và
     nhầm ranh: quan-sát-thấy-đã-dừng là tri thức hiện tại hợp lệ, thứ
     bị cấm là biết *trước lúc dừng* rằng nó sắp dừng. Pha giữa phải có
     mặt trong test, không assert nó là flaky ngay tại biên.
   - **7.9b (P5):** so oracle với tracker trên cùng bộ cảnh của cổng
     P4. Khoảng cách giữa hai đường là *giá của tri giác*; nó đọc được
     vì cả hai trả cùng `ObstacleTrack`.

---

## 8. Đo cái gì để nói "tốt hơn" — và không thêm metric nào

`EpisodeMetricSet` đã có đủ; thêm metric là đổi Metrics Engine và cổng,
một pha riêng, và không cần cho câu hỏi này:

| chỉ số đã có | vai | dự đoán làm gì với nó |
|---|---|---|
| **`success` / success rate** | **cổng, đọc trước hết** | Không được giảm. Xem lập luận dưới |
| `failure_reason` (timeout, stuck, collision) | cổng | Không được dịch từ "chậm" sang "không tới nơi" |
| `collision_count`, `near_miss_rate` | cổng | **không được tệ đi.** Ràng buộc, không phải mục tiêu |
| `stop_and_go_count` | **mục tiêu chính** | "Đứng yên khi gặp vật cản" chính là cái này |
| `travel_time_s`, `time_efficiency` | mục tiêu | bớt chờ vô ích ⇒ nhanh hơn |
| `min_clearance` | đọc kèm | có thể **giảm** — lách sát hơn qua chỗ vừa trống. Đọc cùng `near_miss_rate`, không đọc một mình |
| `p99_latency_ms` (G4) | cổng | hàng rào chi phí của khối theo dõi |

**Vì sao ba dòng đầu phải đứng trước, và bản trước thiếu chúng:** giảm
`stop_and_go_count` mà **không tới đích** không phải cải thiện. Một
robot lao thẳng qua traffic có `stop_and_go_count` bằng 0 và
success rate bằng 0. Đọc bảng theo thứ tự **cổng trước, mục tiêu sau**;
mục tiêu chỉ có nghĩa khi mọi cổng đã xanh.

**Và `stop_and_go_count` phải so trên tập episode *cả hai cùng thành
công*.** Trung bình trên toàn bộ trộn lẫn hai thứ khác nhau: một ứng
viên bỏ cuộc sớm có ít lần dừng vì nó **đi ít hơn**, không vì nó mượt
hơn. Nền tảng đã có đúng từ vựng cho việc này — `pairing` ghép theo
`episode_context_id` và metric engine đã có tiền lệ
`median_travel_time_successful`.

**Một cảnh báo về chính phép điều kiện đó**, để đừng đổi một thiên lệch
lấy một thiên lệch khác: điều kiện trên "cả hai cùng thành công" là
chọn mẫu, và nếu hai ứng viên có success rate lệch nhau thì tập giao
**không** đại diện. Nên phát biểu kết quả bằng **hai câu tách rời**:
*"success rate là X vs Y"* (cổng G1, toàn bộ tập) và *"trên các context
cả hai cùng tới đích, stop-and-go là A vs B"*. Gộp hai câu thành một số
là chỗ một tấm card bắt đầu nói dối.

Cảnh nào để đo: `crossing_obstacle`, `bidirectional_corridor`,
`intersection`, `dynamic_warehouse` — bốn cảnh có traffic thật.
`sudden_stop` giữ vai **ca đối kháng** như mục 7.3, không phải cảnh để
khoe số.

**Nói trước một khả năng, để lúc nó xảy ra không ai bất ngờ:** rất có
thể `dwa_predictive` **thua** trên vài cảnh, nhất là khi nhiễu định vị
cao (vận tốc ma) hoặc `random_walk` (vận tốc hằng sai theo định nghĩa).
Đó **là** kết quả — nền tảng này sinh ra để cho ra loại câu trả lời đó,
và một tấm Decision Card nói *"đừng dùng predictive ở deployment này"*
là một tấm card **thành công**.

---

## 9. Ước lượng

**Thứ tự đã đổi so với bản trước:** `[3]` rollout không-thời gian và
oracle làm **trước** tracker. Đề xuất của dev, và nó đúng — oracle cho
một `dwa_predictive` chạy được với **sai số ước lượng bằng 0**, nên khi
tracker vào sau, mọi hồi quy đều cô lập được về đúng một khối. Làm
ngược lại thì lần đầu chạy là hai khối mới cùng lúc và không ai biết
khối nào sai.

| pha | ngày |
|---|---|
| (0) đo lỗ hổng phanh vs vật cản lại gần — xác nhận hay bác bỏ | 0.5 |
| (5) `v_obstacle_max` lớp 2 + validator 5b, áp **cả hai** controller *(chỉ nếu (0) dương tính)* | 1.5–2 |
| [3] rollout không-thời gian + cost mới | 1 |
| oracle (`dwa_oracle_predictive`) + test 7.9 | 0.5 |
| [1]+[2] phân cụm + ghép cặp + vận tốc có sàn nhiễu + vòng đời track | 2.5 |
| registry + configs + kiểm `CONTROLLER_OF_CONFIG` + version/checksum + KNOWN_LIMITATIONS | 1 |
| test (mục 7) | 1.5 |
| chạy phép so + Decision Card + report | 1 |
| **tổng** | **8 ngày** nếu (0) âm tính · **9.5–10** nếu dương tính |

Tăng so với bản trước (6.5–8) là do vòng đời track, validator 5b, hai
lỗ hổng ở mục 6, và oracle chuyển từ "nếu còn thời gian" thành một pha
có chỗ đứng. **Không** gồm pha hệ toạ độ ở 2c — pha đó riêng, và phép so
đầu tiên chạy không nhiễu định vị.

Nếu chỉ có một ngày: làm **(0)**. Nó hoặc phơi ra một lỗ hổng an toàn ở
lớp 2 — quan trọng hơn toàn bộ phần còn lại — hoặc đóng lại một nghi ngờ
với chi phí nửa ngày.

---

## 10. Quyết định của dev — chốt 14-08

| # | câu hỏi | quyết định |
|---|---|---|
| 1 | Va chạm **dự đoán** là từ chối cứng hay chi phí mềm? | **Mềm.** Miền khả thi cứng không đổi một dòng; dự đoán chỉ vào cost. Test 7.4 là hàng rào của quyết định này |
| 2 | Vận tốc lấy từ đâu? | **Ước lượng từ LiDAR**, giữ `lidar_only`. Sai số ước lượng là một phần của thuật toán |
| 3 | Làm mục 5 (`v_obstacle_max`) trước không? | **Đo trước (0.5 ngày), rồi quyết.** Dương tính ⇒ mục 5 làm trước [1][2][3], vì nó đổi **cả hai** ứng viên và bắt buộc sinh `task_profile_id` mới. Âm tính ⇒ bỏ, **ghi lại kết quả âm** vào report, đi thẳng vào thuật toán |
| 4 | Có làm `dwa_oracle_predictive` không? | **Có** — *diagnostic-only, không đăng ký registry* (cập nhật vòng 3; bản chốt đầu ghi `benchmarkable=False` như pure_pursuit, đã bị thay: oracle không đăng ký nổi và không cần). Khoảng cách giữa nó và `dwa_predictive` **là** giá của việc phải tự ước lượng |
| 5 | Mô hình dự đoán? | **Vận tốc hằng** ở MVP. Không dùng RVO — vật cản trong `dynamic.py` là hàm thuần của `(spec, time, seed)`, không phản ứng gì |

**Hệ quả của (1) phải nói rõ, vì nó là thứ dễ bị đọc nhầm sau này:**
với quyết định này, `dwa_predictive` **không an toàn hơn** `dwa`. Nó
được đo bằng `stop_and_go_count` và `travel_time_s`, với
`collision_count` và `near_miss_rate` là **ràng buộc không được tệ đi**,
không phải mục tiêu. Ai đọc card sau này mà kỳ vọng "dự đoán ⇒ ít va
chạm hơn" là đang đọc sai thứ đã được đo.

**Hệ quả của (3):** ước lượng ở mục 9 tách làm hai nhánh —
**6.5 ngày** nếu (0) âm tính, **8 ngày** nếu dương tính. Không có nhánh
nào bỏ qua (0).

### Sửa sau phản biện của dev — vòng 2, 14-08

Bảy điểm, tất cả đã vào thân plan:

| # | phản biện | xử lý |
|---|---|---|
| 1 | "Chỉ mềm" mâu thuẫn với việc nới `v_obstacle_max` | **Nhận.** Mục **4b** mới: có **hai** ràng buộc cứng, bản trước chỉ nói một. MVP không nới cả hai. Test 7.4 tách làm (a) và (b) |
| 2 | Rollout ở pose thật, LiDAR ở pose tin — hai hệ toạ độ | **Nhận, đã kiểm** (`engine.py:261` vs `:280`). Mục **2c** mới. Là defect **đang có của `dwa`**, tách pha riêng; phép so đầu chạy không nhiễu định vị và ghi rõ giới hạn |
| 3 | Ngưỡng cụm suy từ `DynamicObstacle.radius` là rò rỉ ground truth | **Nhận.** Mục [1] viết lại: ngưỡng từ hình học LiDAR; phân loại theo **tính bị chặn + tính bền**, không theo kích thước; ngưỡng thành tham số candidate khai rõ |
| 4 | `v_obstacle_max` phải được kiểm chứng | **Nhận.** Mục **5b** mới. Tin tốt: cả bốn luật chuyển động có cận trên đóng dạng ⇒ validator toàn phần |
| 5 | Oracle chỉ được biết hiện tại | **Nhận.** Vào mục 2b, kèm test 7.9: oracle phải **sai giống** predictive trên `sudden_stop` |
| 6 | Oracle dựng trước tracker | **Nhận.** Đổi thứ tự ở mục 9 — cô lập được hồi quy về đúng một khối |
| 7 | Thiếu vòng đời track; thiếu success/timeout/stuck; version code dùng chung; nhãn UI | **Nhận cả bốn.** Bảng vòng đời ở [2]; mục 8 xếp lại theo **cổng trước, mục tiêu sau** + cảnh báo thiên lệch khi điều kiện trên "cả hai cùng thành công"; hai lỗ hổng `StackComponent.version` và nhãn UI vào bảng mục 6 |

Một chỗ **thu hẹp** lại so với phản biện: UI đã lọc `benchmarkable` ở
`CandidatePicker.tsx:44`, nên oracle **không** lọt vào ô chọn ứng viên.
Việc phải làm nhỏ hơn — `/candidates` vẫn liệt kê nó dưới nhãn
`reference`, và nhãn đó cần tách khỏi nghĩa "adapter tạm" của
pure_pursuit.

**Hệ quả của (4)** *(cập nhật vòng 3)*: oracle là **dụng cụ đo**, không
phải candidate — và từ vòng 3, điều đó được bảo đảm bằng **cấu trúc**
thay vì bằng cờ: nó không đăng ký registry (không đăng ký nổi — factory
không có engine để đóng provider vào), sống trong một script chẩn đoán,
chạy qua `run_stack` trực tiếp. Không có đường nào từ nó tới Decision
Card hay UI để phải chặn.

### Sửa sau phản biện của dev — vòng 3, 14-08

| # | phản biện | xử lý |
|---|---|---|
| 1 | Cổng ghép cặp của P5 dùng `v_obstacle_max`, nhưng P1 optional ⇒ trường có thể không tồn tại | **Nhận — bug phụ thuộc thật.** Tách hai trường ở mục [2]: `v_obstacle_max` (deployment, lớp 2 — sai thì va chạm) và `association_speed_limit` (candidate, lớp 3 — sai thì tracker thoái lui về `dwa`). Hai chế độ hỏng khác nhau, hai chủ khác nhau. Default của trường mới không suy từ tốc độ vật cản thật — cùng luật chống rò rỉ như ngưỡng cụm |
| 2 | "Tracker không thể tốt hơn oracle" không đúng trên mọi motion law | **Nhận.** Đúng cho *chất lượng ước lượng*, sai cho *kết quả điều khiển* trên cảnh sai mô hình — trễ của tracker trên `sudden_stop` vô tình gần sự thật hơn ngoại suy tự tin. Cổng P4 viết lại: chỉ đo trên cảnh **gần-hằng trong prediction horizon**; `sudden_stop`/`random_walk` đo giới hạn mô hình, không tham gia cổng. Kèm việc mới: kiểm luật chuyển động từng cảnh (`PeriodicMotion` là sin, không phải hằng), dựng cảnh cắt ngang vận-tốc-hằng riêng nếu cần |
| 3 | Chưa định nghĩa đường cấp ground truth cho oracle | **Nhận.** P4 viết lại: `GroundTruthObstacleProvider` tiêm qua constructor từ script chẩn đoán; ba đường cấm (engine vào `compute()`, ground truth vào `Observation`, provider trong factory) ghi thành bảng kèm lý do. Vận tốc bằng **sai phân một phía về quá khứ** — "quanh t" của bản trước là đọc tương lai; `t<Δt` cho vận tốc 0, trùng chủ đích với luật warm-up của tracker |

Hệ quả dây chuyền của (3), làm plan **gọn đi**: oracle không đăng ký
nổi registry (factory không có engine) ⇒ không bao giờ lên `/candidates`
⇒ **việc nhãn UI ở P6 biến mất**. Vòng 2 nói "cần nhãn riêng" — vòng 3
giải quyết bằng cách xoá luôn chỗ đứng của nhãn.

### Sửa sau phản biện của dev — vòng 4, 14-08

| # | phản biện | xử lý |
|---|---|---|
| 1 | P0 vẫn kiểm công thức tĩnh `v²/(2a) + v·T` — không đo được lỗ hổng vật-cản-lại-gần, có thể **âm tính sai** và bỏ oan P1 | **Nhận — nguy hiểm nhất vòng này.** Biểu thức tĩnh là đúng cái `stopping_limit` hiện tại đã cưỡng chế, nên nó xanh gần như mọi bước. P0 viết lại: ghi **cả hai** `static_required_gap` và `moving_required_gap = (v+u)·T + v²/(2a) + u·v/a`; bằng chứng = **trạng thái kẹp** `static ≤ gap < moving`. Kèm đối xứng: `moving_required_gap` chính là bất biến P1 cưỡng chế — một thước đo hai lần, trước và sau |
| 2 | `v_obstacle_max = 0.0` mặc định mâu thuẫn validator — profile cũ có vật cản động bị từ chối, hết backward-compatible | **Nhận — hai câu của tôi tự đá nhau.** Đổi sang `float \| None = None`: `None` = legacy, không tuyên bố an toàn, manifest ghi rõ; số dương = khai và kiểm chứng; `0.0` = chỉ hợp lệ khi không có vật cản động, sai thì từ chối. Tiền lệ: `robustness_margin: float \| None`, null có nghĩa định nghĩa sẵn |
| 3 | Provider "đóng engine vào closure" không khớp `run_stack` — nó tự tạo engine bên trong | **Nhận — thiết kế cũ không hiện thực nổi** (`nav_stack.py:875`). Sửa: provider thuần đóng `(scenario, seed)`, nhận `time`, tái tạo qua `position_at` — chính hàm engine dùng (`engine.py:578`), nên trùng ground truth từng bit. `time` từ `Observation.time`, kênh đã có sẵn. Provider trả `ObstacleTrack(center, radius, velocity, confidence)` chung cấu trúc với tracker để khoảng cách oracle–tracker không lẫn sai khác hình học; oracle `confidence=1.0` |
| 4 | Bốn chỉnh tài liệu: tiêu đề 2b cũ; bảng quyết định #4 còn ghi `benchmarkable=False`; test 7.9 chưa chạy được ở P4; cổng P4 chưa khai "cải thiện đo được" là gì; migration id chưa chốt | **Nhận cả bốn.** 2b đổi tiêu đề; #4 ghi *diagnostic-only*; 7.9 tách 7.9a (P4 — provider tiếp tục ngoại suy sau `stop_time`) và 7.9b (P5 — so oracle với tracker); cổng P4 có bảng tiêu chí khai trước (≥20 seed/cảnh, so cặp cùng context, CI 95% bootstrap của Δ median loại 0, metric cổng không xấu đi); migration id ghi thành **câu hỏi mở duy nhất**, không chặn P0–P5, chốt trước P6, ba phương án + khuyến nghị (a) |

### Sửa sau phản biện của dev — vòng 5, 14-08

| # | phản biện | xử lý |
|---|---|---|
| 1 | 7.9a bản vòng 4 đòi provider trả vận tốc trước-dừng **sau** `stop_time` — mâu thuẫn với chính công thức sai phân về quá khứ (vật đứng yên đủ `Δt` ⇒ sai phân = 0 theo định nghĩa) | **Nhận — hai câu cùng một vòng tự đá nhau.** 7.9a viết lại thành **ba pha** quanh `stop_time`; ranh của "không đọc tương lai" là *quan sát*, không phải *sự kiện*: trước dừng phải ngoại suy xuyên qua, sau khi quan sát thấy dừng phải trả 0. Pha chuyển tiếp (`Δt`, vận tốc tắt dần) khai tường minh để test không flaky tại biên. Độ trễ `Δt` đối xứng chủ đích với cửa sổ tracker — hiệu hai độ trễ là một phần thứ 7.9b đo. Câu "sai y hệt" ở 2b tinh chỉnh thành "sai cùng kiểu, hồi sau độ trễ của mình" |
| 2 | `max()` trên deployment không có vật cản động ném `ValueError` | **Nhận.** `max(..., default=0.0)`; `0.0` khớp luôn ngữ nghĩa "không gì chuyển động ⇒ khai 0.0 hợp lệ" |
| 3 | P7 dùng `dwa_pred_balanced` trong khi P6 chưa khai tên; cần chuẩn hoá | **Nhận.** Chốt `dwa_predictive_{coarse,balanced,default}` theo đúng quy ước controller+mức; sửa cả hai command block (mục 6 và P7). Vô hại hôm nay nhưng thành bug thật ở P6 việc 3, khi phép kiểm `CONTROLLER_OF_CONFIG` đối chiếu tên với controller |

---

## 11. Kế hoạch xây dựng

### 11.0. Đồ thị phụ thuộc, và hai cổng quyết định

```
P0  đo lỗ hổng phanh ────┬── âm tính ──────────────────────┐
   (cổng quyết định 1)   │                                 │
                         └── dương tính ── P1 v_obstacle_max ┤
                                            (profile mới)   │
                                                            ▼
                                                  P2 tách lõi dùng chung
                                                            │
                                                            ▼
                                                  P3 rollout không-thời gian
                                                            │
                                                            ▼
                                                  P4 oracle  ← cổng quyết định 2
                                                            │   (dự đoán có đáng không?)
                                                            ▼
                                                  P5 tracker
                                                            │
                                                            ▼
                                                  P6 nối nền tảng
                                                            │
                                                            ▼
                                                  P7 chạy phép so + card
```

Ngoài phạm vi plan này, chặn phần nào: **pha hệ toạ độ (mục 2c)**. Cho
tới khi xong, mọi phép so ở P7 chạy với `localization_drift_m = 0` và
`localization_jump_probability = 0`.

**Hai cổng quyết định, và cả hai đều có nhánh "dừng lại":**

| cổng | ở đâu | câu hỏi | nhánh dừng |
|---|---|---|---|
| 1 | sau **P0** | Lỗ hổng phanh vs vật cản lại gần có thật không? | Âm tính ⇒ **bỏ P1**, ghi kết quả âm vào report, sang thẳng P2 |
| 2 | sau **P4** | Với tri giác *hoàn hảo*, mô hình vận tốc hằng có cải thiện đo được **trên cảnh gần-hằng** không? | Không ⇒ **dừng cả plan**. Cổng chỉ chạy cảnh trong miền giả định của mô hình; `sudden_stop`/`random_walk` đo giới hạn, không tham gia cổng (chi tiết ở P4) |

Cổng 2 là lý do thứ hai để oracle đứng trước tracker, ngoài lý do cô lập
hồi quy: nó là **chỗ rẻ nhất để hủy dự án này**.

---

### P0 — Đo lỗ hổng phanh với vật cản đang lại gần · **0.5 ngày**

**Mục tiêu:** xác nhận hay bác bỏ phân tích ở mục 5. Không sửa gì.

**File:** `tests/test_admissible_stopping.py` (mới, hoặc nối vào file
test phase 1b nếu đã có).

**Việc:**
1. Dựng cảnh: vật cản `WaypointMotion` lao thẳng vào robot, tốc độ quét
   `{0.3, 0.6, 1.0, 1.5}` m/s. Robot mặc định (`v_max=0.8`, `a=0.5`).
2. Cấu hình **đối kháng**, đúng công thức đã lộ lỗ hổng lần trước:
   `weight_clearance=0`, `horizon_seconds=0.5`. Tắt hết nhiễu.
3. Ở **mọi bước**, ghi lại: `v`, tốc độ khép `u` của vật cản (thành
   phần vận tốc hướng về robot, ground truth — đây là test chứ không
   phải controller), khoảng hở thật tới bề mặt, và **cả hai** biểu thức:

   ```
   static_required_gap = v·T + v²/(2a)
   moving_required_gap = (v+u)·T + v²/(2a) + u·v/a
   ```

   Số hạng `u·v/a`: trong thời gian robot phanh `t_stop = v/a`, vật cản
   đi thêm `u·t_stop`. Số hạng `(v+u)·T`: trong chu kỳ phản ứng cả hai
   cùng khép. Bản trước chỉ ghi biểu thức tĩnh — và biểu thức tĩnh là
   **đúng cái `stopping_limit` hiện tại đã cưỡng chế**, nên nó sẽ xanh
   ở gần như mọi bước và P0 có thể **báo âm tính sai**, bỏ P1 trong khi
   lỗ hổng có thật.

4. Đếm số bước ở **trạng thái kẹp**:
   `static_required_gap ≤ gap < moving_required_gap` — an toàn nếu vật
   đứng yên, không an toàn vì nó đang tiến lại. Kèm kết cục episode.

**Xong khi:** có một bảng `tốc-độ-vật-cản × (kết cục, số bước ở trạng
thái kẹp, gap nhỏ nhất)`, đúng dạng bảng ở mục 1.5 của plan 14-08.
**Dương tính** = tồn tại bước ở trạng thái kẹp (lỗ hổng có thật kể cả
khi cảnh này chưa kịp va chạm); va chạm thật là bằng chứng mạnh hơn
nhưng không phải điều kiện cần.

**Đối xứng chủ đích với P1:** `moving_required_gap` chính là bất biến
P1 sẽ cưỡng chế. P0 đo số bước vi phạm nó; P1 xong thì đúng phép đo đó
phải về **0**. Một thước, hai lần đo, trước và sau.

**Chỗ dễ sai:** đo khoảng hở tới **bề mặt** (tâm trừ bán kính vật cản
trừ bán kính robot), không phải tâm-tới-tâm. Sai chỗ này thì bảng nói
ngược.

**Đầu ra:** một mục trong report, kể cả khi âm tính. Kết quả âm tốn nửa
ngày và đóng lại một nghi ngờ — nó **là** kết quả.

---

### P1 — `v_obstacle_max` ở lớp 2 · **1.5–2 ngày** · *chỉ khi P0 dương tính*

**Mục tiêu:** bảo đảm phanh đứng vững trước vật cản đang lại gần, **cho
cả hai controller như nhau**. `dwa_predictive` không hưởng lợi gì.

**File:**

| file | việc |
|---|---|
| `packages/schemas/planbench_schemas/task_profile.py` | thêm `v_obstacle_max: float \| None = None`. **`None`, không phải `0.0`** — bản trước nói "mặc định 0.0 giữ profile cũ" và điều đó **mâu thuẫn với chính validator của pha này**: profile cũ có vật cản 1.0 m/s + mặc định 0.0 ⇒ bị từ chối lúc nạp, tức không hề backward-compatible. Ba nghĩa: `None` = chưa khai, hành vi legacy, **không mang tuyên bố an toàn** (manifest ghi rõ); số dương = khai và bị kiểm chứng; `0.0` = hợp lệ **chỉ khi** không có vật cản động. Đúng tiền lệ `robustness_margin: float \| None` — null có nghĩa được định nghĩa là "chưa đo" |
| `packages/schemas/planbench_schemas/dynamic.py` | `max_speed(motion) -> float` cho bốn luật, theo bảng 5b |
| `packages/schemas/planbench_schemas/feasibility.py` | `stopping_distance` nhận thêm tốc độ khép của vật cản; hoặc thêm `closing_headroom(...)` riêng — **không** thêm tham số nào của candidate vào chữ ký |
| `packages/planning/planbench_planning/dwa/planner.py` | `_dynamic_window` dùng biên xấu nhất mới |
| `apps/api/…` nơi nạp `TaskProfile` | gọi validator, từ chối lúc nạp |
| `contracts/CONTRACTS.md` + `contracts/schemas/manifest.schema.json` | bump; `v_obstacle_max` vào manifest (`additionalProperties: false` đã bắt hụt một lần ở A3) |

**Việc:**
1. `max_speed` cho bốn luật + nhánh `NotImplementedError` tường minh cho
   luật tương lai.
2. Validator lúc nạp deployment, **chỉ chạy khi `v_obstacle_max` không
   phải `None`**:
   `max((max_speed(o.motion) for o in dynamic_obstacles), default=0.0)
   <= v_obstacle_max`. `default=0.0` không phải trang trí: thiếu nó,
   deployment **không có** vật cản động ném `ValueError` ngay tại
   validator — và `0.0` khớp luôn ngữ nghĩa đã chốt: không gì chuyển
   động thì khai `v_obstacle_max = 0.0` hợp lệ.
   Từ chối bằng câu văn cho **người đang chọn**,
   không phải cho stack trace — đúng lối
   `PPOStackConfig._require_a_model` đã viết. `None` không bị từ chối —
   nó bị **ghi nhận**: profile chạy được nhưng manifest nói rõ bảo đảm
   phanh-trước-vật-động không tồn tại ở đây.
3. Sửa `_dynamic_window`: với `v_obstacle_max = u` đã khai, biên trở
   thành `(v+u)·T + v²/(2a) + u·v/a ≤ headroom` — đúng biểu thức
   `moving_required_gap` của P0. `None` ⇒ `u = 0` ⇒ đúng công thức hôm
   nay, từng bit. Giải đóng dạng theo `v` (vẫn bậc hai), đừng lặp điểm
   cố định.
4. **`task_profile_id` mới** cho mọi deployment muốn đo dưới ràng buộc
   này. Không sửa tại chỗ; `same_deployment` đã chặn sẵn.

**Test:** P0 chạy lại phải **xanh** ở mọi tốc độ vật cản. Cộng test
validator (mục 7.8): một ca cho mỗi luật trong bốn luật.

**Chỗ dễ sai:** `v_obstacle_max = None` phải cho hành vi
**byte-identical** với hôm nay — cả ở validator (không từ chối gì) lẫn
ở `_dynamic_window` (`u = 0`). Có một test riêng cho điều đó, cùng lối
`NO_REPLANNING` và `NO_RECOVERY` đã làm. Và một test cho nghĩa thứ ba:
`0.0` với một profile **có** vật cản động phải bị từ chối — "không có
gì chuyển động" là một tuyên bố, và tuyên bố sai thì từ chối.

---

### P2 — Tách lõi dùng chung, **không đổi hành vi** · **0.5 ngày**

**Mục tiêu:** `dwa` và `dwa_predictive` chia sẻ code mà không chia sẻ
danh tính. Pha này **không thêm tính năng nào**.

**File:** `packages/planning/planbench_planning/common/dwa_core.py`
(mới) · `packages/planning/planbench_planning/dwa/planner.py`.

**Việc:**
1. Rút ra **hàm thuần**, không phải lớp cha: `_linspace`,
   `_final_heading`, `_distance_to_polyline`, phần dựng cửa sổ động,
   phần rollout, phần dựng đám mây điểm từ scan.
2. `DWAPlanner` gọi vào chúng. **Không** đổi một dòng logic nào.
3. **Cấm kế thừa.** `dwa_predictive` sẽ **không** kế thừa `DWAPlanner` —
   `StackComponent.version` là một phần của candidate id, và một lớp cha
   chung làm một sửa lỗi lặng lẽ đổi cả hai ứng viên.

**Test — quan trọng nhất của pha:** **golden trajectory**. Chạy một tập
episode cố định *trước* refactor, lưu quỹ đạo, và đòi *sau* refactor ra
**đúng cùng byte**. Một refactor "chắc là không đổi gì" ở đúng chỗ này
là cách êm ái nhất để làm hỏng mọi số đo đã có.

**Xong khi:** golden test xanh, `ruff` sạch, **một commit riêng**. Đừng
trộn pha này với P3 — trộn vào thì lúc số đo lệch không ai biết do
refactor hay do tính năng mới.

---

### P3 — Rollout không-thời gian + cost mới · **1 ngày**

**Mục tiêu:** bộ điều khiển lăn thế giới về phía trước cùng lúc với
chính nó. Chưa có tracker — vận tốc **được tiêm vào** từ bên ngoài.

**File:** `packages/planning/planbench_planning/dwa_predictive/planner.py`
(mới) · `common/dwa_core.py`.

**Việc:**
1. `DWAPredictiveConfig`: kế thừa mọi trường của `DWAConfig`, thêm
   `prediction_horizon_seconds`, `weight_time_to_collision`,
   `association_speed_limit` (candidate sở hữu — xem [2]), và ba ngưỡng
   phân loại cụm của mục [1]. **Không** thêm trường nào chạm vào miền
   cứng.
2. Giao diện nội bộ nhận `tuple[ObstacleTrack, ...]` — track động có
   `(center, radius, velocity, confidence)`, phần còn lại của scan giữ
   nguyên là điểm tĩnh. Ở pha này tracks đến từ tham số, chưa từ
   tracker — đó là thứ cho phép P4 cắm oracle vào mà không cần tracker,
   và vì oracle với tracker trả **cùng cấu trúc**, khoảng cách P5 đo
   được là thuần sai số ước lượng, không lẫn sai khác hình học.
3. Đổi phép broadcast: `(N,K,2) − (1,K,M,2)` thay cho `(1,1,M,2)`.
   Kiểm hình dạng tensor bằng test, đừng tin mắt.
4. Cost mới: khoảng hở **dự đoán** dọc horizon; time-to-collision; phạt
   cắt mặt vật cản đang tới.
5. **Từ chối cứng giữ nguyên** — chạy trên điểm đo tại thời điểm hiện
   tại, y hệt `dwa`. Đây là chỗ dev đã chốt ở 4b.

**Test:** 7.4 (a) **và** (b) — hai ràng buộc cứng giống hệt `dwa`;
7.2 (thế giới tĩnh ⇒ quỹ đạo giống `dwa`); test hình dạng tensor; test
tất định.

**Chỗ dễ sai:** trục thời gian của vật cản phải khớp **`horizon_dt` của
rollout**, không phải `control_period`. Lệch một bước thì dự đoán trễ
một nhịp và không ai nhìn ra từ số liệu.

---

### P4 — Oracle · **0.5 ngày** · **cổng quyết định 2**

**Mục tiêu:** đo trần của ý tưởng, với sai số ước lượng bằng 0.

**File:** `packages/planning/planbench_planning/dwa_predictive/oracle.py`
· `scripts/` (script chẩn đoán). **Không đụng `registry.py`** — xem
đường cấp dữ liệu bên dưới.

**Đường cấp ground truth — provider tiêm vào, không phải registry.**
Bản trước nói "đóng engine vào closure" và điều đó **không hiện thực
nổi**: `run_stack` tự tạo `SimulationEngine` bên trong
(`nav_stack.py:875`), script không bao giờ cầm được engine đó. Nhưng
cũng **không cần** — luật chuyển động là hàm thuần, và chính engine đọc
vật cản qua `position_at(obstacle, time, scenario.random_seed)`
(`engine.py:578`). Provider đóng `(scenario, seed)` — hai thứ script
**có** — và tái tạo chính xác thứ engine thấy:

```
scripts/diagnose_oracle.py
    │  đóng (scenario, scenario.random_seed) vào một closure
    ▼
GroundTruthObstacleProvider: (time: float) -> tuple[ObstacleTrack, ...]
    │  vị trí:   position_at(obstacle, t, seed)
    │  vận tốc: (position_at(t) − position_at(t−Δt)) / Δt
    │  tiêm qua constructor
    ▼
DWAOraclePredictive(provider, config)  ──▶  run_stack(...)
    │  trong compute(): provider(observation.time)
```

`time` đến từ `Observation.time` — trường đã có sẵn trong hợp đồng quan
sát, không phải đặc quyền. Thứ oracle được ưu ái là **nội dung** provider
trả, không phải kênh nào mới.

**Provider trả `ObstacleTrack(center, radius, velocity, confidence)` —
đúng cấu trúc tracker của P5 sẽ trả**, không phải `(vị trí, vận tốc)`
trần. Lý do: nếu oracle ăn tâm-vật-cản còn tracker ăn điểm-bề-mặt-LiDAR
thì khoảng cách oracle–tracker ở P5 trộn lẫn *sai số ước lượng* với
*sai khác hình học*, và con số đáng giá nhất của plan (giá của tri
giác) thành không đọc được. Oracle đặt `confidence = 1.0`.

Ba đường **cấm**, và lý do từng đường:

| đường | vì sao cấm |
|---|---|
| Cho `LocalPlanner.compute()` nhận engine | mọi controller từ đó trở đi *có thể* đọc ground truth; hàng rào P02 thành lời dặn |
| Nhét ground truth vào `Observation` | `Observation` là hợp đồng "robot thấy gì" — một trường ground truth trong đó là rò rỉ được chuẩn hoá |
| Provider resolve được từ registry/factory | `dwa_predictive` thường có thể gọi cùng provider; và thực tế **không đăng ký nổi** — factory có chữ ký `config -> LocalPlanner`, không có engine để đóng vào. Cái không-đăng-ký-nổi này là tính năng: oracle không có đường thành candidate |

**Việc:**
1. `ObstacleTrack` (schema nhỏ, dùng chung với tracker P5). Provider
   như sơ đồ trên; vận tốc bằng **sai phân một phía về quá khứ** —
   **không** phải "quanh t" như bản trước, `position_at(t + ε)` là đọc
   tương lai, đúng thứ mục 2b cấm. Với `t < Δt`: vận tốc **0** — trùng
   quy tắc warm-up của tracker, và sự trùng đó là chủ đích: oracle và
   tracker phải cùng luật ở chỗ chưa có thông tin.
2. Cắm vào giao diện `predict` của P3. Ngoại suy bằng **đúng mô hình vận
   tốc hằng** — không được dùng luật chuyển động thật.
3. Script chẩn đoán dựng `DWAOraclePredictive` trực tiếp, chạy qua
   `run_stack`, ghi kết quả ra bảng. Không Decision Card, không registry,
   không UI.

**Test:** 7.9a — ba pha quanh `stop_time`, kiểm thẳng trên vận tốc
provider trả rồi trên hành vi oracle; phát biểu đầy đủ ở mục 7. Ranh
giới của "không đọc tương lai" là *quan sát*: trước khi dừng, dự đoán
phải xuyên qua `stop_time` như thể vật còn đi (đó là bằng chứng); sau
khi đã quan sát thấy dừng (`t ≥ stop_time + Δt`), provider phải trả 0
và oracle phải thôi ngoại suy — biết-hiện-tại là hợp lệ, một tracker
hoàn hảo cũng kết luận thế. Độ trễ `Δt` này đối xứng chủ đích với cửa
sổ ước lượng của tracker, và hiệu hai độ trễ là một phần "giá của tri
giác" 7.9b sẽ đo. (Phép so oracle-vs-tracker là 7.9b, thuộc P5 — tracker
tới đó mới tồn tại.)

**Cổng — phát biểu lại, vì bản trước đo nhầm thứ.** Câu "tracker không
thể tốt hơn oracle" chỉ đúng về **chất lượng ước lượng trạng thái hiện
tại**. Về kết quả điều khiển thì không: trên `sudden_stop`, oracle biết
chính xác vận tốc ngay trước khi vật cản dừng và ngoại suy nó đầy tự
tin; một tracker có trễ vô tình gần sự thật hơn. Trên cảnh **sai mô
hình**, thua oracle không nói lên điều gì.

Nên cổng đo đúng câu hỏi của nó — *mô hình vận tốc hằng, trong miền giả
định của chính nó, có đáng tiền không*:

> Chạy oracle vs `dwa` trên các cảnh mà chuyển động **gần-hằng trong
> một prediction horizon** (1–1.5 s). Nếu không cải thiện đo được **ở
> đó** theo tiêu chí khai sẵn dưới đây, dừng plan. `sudden_stop` và
> `random_walk` **không tham gia cổng** — chúng đo giới hạn mô hình,
> không đo giá trị mô hình.

**"Cải thiện đo được" khai trước khi chạy, không phải sau khi nhìn số**
— cùng kỷ luật với dự đoán 11.6 ms đã ghi trước ở `dwa_balanced`:

| tiêu chí | ngưỡng |
|---|---|
| Tập | ≥ 20 seed mỗi cảnh, **cùng context** cho `dwa` và oracle, so theo cặp |
| Đạt | ít nhất một trong: CI 95% bootstrap-theo-cặp của Δ`travel_time_s` (median) nằm hẳn dưới 0; hoặc của Δ`stop_and_go_count` nằm hẳn dưới 0 |
| Không được | mọi metric cổng của mục 8 (success, collision, near-miss) xấu đi có ý nghĩa |
| Ghi | con số dự đoán trước khi chạy vào report, kết quả bên cạnh, cái nào có trước nói rõ |

Việc kèm theo, vì thư viện cảnh không tự khai điều này: **kiểm luật
chuyển động của từng cảnh trước khi chọn cảnh cổng.** `WaypointMotion`
là hằng thật; `PeriodicMotion` là hình sin — chỉ gần-hằng khi `period`
dài so với horizon. Nếu cảnh cắt ngang của thư viện hoá ra là sin chu
kỳ ngắn, cổng cần một cảnh cắt ngang vận-tốc-hằng dựng riêng (một
`WaypointMotion` đi ngang hành lang — vài dòng scenario, không phải một
pha).

---

### P5 — Tracker · **2.5 ngày**

**Mục tiêu:** thay oracle bằng ước lượng từ chính LiDAR, giữ
`lidar_only`.

**File:** `packages/planning/planbench_planning/dwa_predictive/tracking.py`
(mới).

**Việc, theo đúng thứ tự:**

| # | việc | xong khi |
|---|---|---|
| 1 | **Phân cụm** theo tia liền kề, ngưỡng `≈ r·Δθ + k·σ_range` | cụm ổn định giữa hai khung trên cảnh tĩnh |
| 2 | **Phân loại** bị chặn/thẳng-dài/chạm-mép-quét (bảng mục [1]) | tường không bao giờ được theo dõi |
| 3 | **Ghép cặp** tâm gần nhất trong cổng `association_speed_limit·Δt + biên` (candidate sở hữu, **không** phải `v_obstacle_max` — xem [2]) | test 7.1 xanh trên vật cản chạy thẳng |
| 4 | **Ước lượng vận tốc** bình phương tối thiểu trên cửa sổ vài khung | sai số hội tụ theo ngưỡng nêu rõ |
| 5 | **Sàn nhiễu** suy từ `position_uncertainty_m` và `lidar_range_sigma_m` | test 7.2 xanh **có bật nhiễu định vị** |
| 6 | **Vòng đời track** — cả năm dòng của bảng ở mục [2] | test 7.4b: mọi chế độ hỏng thoái lui về `dwa` |
| 7 | **Bộ đếm chẩn đoán**: số track, số lần ghép hỏng, sai số vs ground truth | ghi ra event/log, **không** vào metric xếp hạng |

**Test:** 7.1, 7.2, 7.3 (`sudden_stop` — ca đối kháng), 7.4b, 7.6 (tất
định qua `reset()`, vì đây là khối đầu tiên trong `dwa_predictive` mang
trạng thái giữa các bước), và **7.9b** — phép so oracle-vs-tracker,
chính là "đối chiếu bắt buộc cuối pha" bên dưới, giờ chạy được vì cả
hai đã tồn tại và trả cùng `ObstacleTrack`.

**Chỗ dễ sai — cả ba đã liệt kê ở mục [2] và cả ba sẽ xảy ra:** tâm cụm
trượt khi vật thể lộ dần sau góc khuất; `lidar_dropout_probability` làm
cụm vỡ đôi; hai vật đi ngang nhau gây ghép chéo. Không chặn được triệt
để — đo chúng bằng bộ đếm ở việc 7.

**Đối chiếu bắt buộc cuối pha:** chạy lại **đúng** bộ cảnh của P4, so
với oracle. Khoảng cách giữa hai đường **là** giá của việc phải tự ước
lượng, và nó là một trong những con số đáng giá nhất plan này sinh ra.

---

### P6 — Nối vào nền tảng, và trả hai món nợ · **1 ngày**

**Mục tiêu:** ứng viên đi được hết đường từ registry tới Decision Card.

| # | việc | file |
|---|---|---|
| 1 | Đăng ký `astar+dwa_predictive`, `rrtstar+dwa_predictive` — mô tả **nói rõ** vận tốc là ước lượng và mô hình là vận tốc hằng, đúng tiền lệ `_RRT_STAR_DESCRIPTION` | `registry.py` |
| 2 | `CONTROLLER_CONFIGS["dwa_predictive"]` — ba tên chốt cứng: **`dwa_predictive_coarse` / `dwa_predictive_balanced` / `dwa_predictive_default`**, cùng mật độ lấy mẫu với ba mức của `dwa` để trục latency so được. Tên theo đúng quy ước đang có (controller + mức, phẳng toàn cục, tự mang controller của nó) — không viết tắt `pred`: tên này sẽ bị việc 3 đối chiếu với controller và sẽ nằm nguyên văn trong mọi report | `candidates.py` |
| 3 | **Nợ 1:** chặn tên config lệch controller. `CONTROLLER_OF_CONFIG` đã tồn tại, chưa ai dùng — kiểm ở `build_candidates`, ném `SystemExit`/`ValueError` với câu văn cho người | `candidates.py`, `selection.py` |
| 4 | **Nợ 2:** `local_version` từ checksum của module điều khiển **+ lõi dùng chung** `dwa_core.py`, thay cho `"v1"` cứng. Không có nó thì một sửa lỗi ở lõi âm thầm đổi cả hai ứng viên | `candidates.py:132`, `selection.py:172`, `decision_service.py:313` |
| 5 | ~~Nhãn UI riêng cho oracle~~ — **hết cần từ vòng 3**: oracle không đăng ký registry (P4), nên không bao giờ xuất hiện trên `/candidates`. Việc UI của plan này về **0** | — |
| 6 | `KNOWN_LIMITATIONS.md`: vận tốc hằng; ba nguồn vận tốc ma; không tương hỗ; **và** giới hạn hệ toạ độ ở mục 2c | `docs/KNOWN_LIMITATIONS.md` |

**Test:** thêm hai stack mới vào **hàng rào L4** (test 7.5) — chạy cả
`astar+dwa_predictive` và `rrtstar+dwa_predictive`. Không sửa validator,
chỉ mở rộng tập chạy.

**Chỗ dễ sai — và là câu hỏi mở duy nhất còn treo của plan:** việc 4
đổi **mọi** `candidate_id` đang có. Nó là hành vi đúng — chúng lẽ ra đã
phải khác nhau — nhưng mọi run đã lưu sẽ không khớp id nữa. Trạng thái:
**chưa chốt, không chặn P0–P5** (không pha nào trước P6 đụng
`candidate_id`), nhưng **phải chốt trước khi bắt đầu P6**. Ba phương án
để dev chọn lúc đó: (a) chấp nhận đứt gãy, run cũ giữ id cũ như dữ liệu
lịch sử; (b) chỉ áp checksum cho controller **mới**, `dwa` cũ giữ
`"v1"` — không sạch nhưng không đứt; (c) một bảng ánh xạ id-cũ → id-mới
trong storage. Khuyến nghị của tôi: **(a)** — nền tảng đã có tiền lệ
"không sửa tại chỗ, tạo mới" (`same_deployment`), và (b) để lại đúng
lỗ hổng đang định vá cho một nửa registry.

---

### P7 — Chạy phép so, dựng card, viết report · **1 ngày**

**Việc:**
1. Deployment cho phép so: `localization_drift_m = 0`,
   `localization_jump_probability = 0` (giới hạn ở mục 2c), các luồng
   nhiễu khác giữ nguyên. **`task_profile_id` mới**, ghi rõ vì sao.
2. Chạy:
   ```
   scripts/compare.py \
     --candidates astar+dwa:dwa_balanced,astar+dwa_predictive:dwa_predictive_balanced \
     --scope local_controller_selection
   ```
3. Bốn cảnh có traffic (`crossing_obstacle`, `bidirectional_corridor`,
   `intersection`, `dynamic_warehouse`) cộng `sudden_stop` làm **ca đối
   kháng**, không phải cảnh khoe số.
4. Đọc bảng mục 8 theo thứ tự **cổng trước, mục tiêu sau**. Phát biểu
   kết quả bằng **hai câu tách rời** — success rate trên toàn tập,
   stop-and-go trên tập giao "cả hai cùng tới đích".
5. Report ở `docs/antongduy/reports/<ngày>/tongduyan_*.md`, phủ hết mọi
   pha đã chạy, gồm **cả kết quả âm** ở P0 và P4 nếu có.

**Điều phải viết vào report kể cả khi nó khó chịu:** nếu
`dwa_predictive` **thua** — rất có thể ở `sudden_stop`, và có thể ở cảnh
`random_walk` — thì đó là kết quả. Một tấm Decision Card nói *"đừng dùng
predictive ở deployment này"* là một tấm card **thành công**.

---

### 11.8. Ranh giới commit

Mỗi pha là **một commit**, trừ P5 tách làm hai (`1–4` phân cụm+vận tốc,
`5–7` sàn nhiễu+vòng đời+chẩn đoán). P2 **bắt buộc** đứng riêng — một
refactor không đổi hành vi trộn chung với tính năng mới là cách chắc
chắn nhất để không truy được lỗi về đâu.

Report viết sau mỗi pha có kết quả đo được (P0, P4, P5-đối-chiếu, P7),
không đợi hết plan.
