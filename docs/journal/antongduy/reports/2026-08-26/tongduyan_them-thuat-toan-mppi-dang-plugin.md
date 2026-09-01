# Thêm thuật toán MPPI dưới dạng plugin import được

**Ngày:** 2026-08-26
**Việc:** dựng một thuật toán thứ tư cho hệ thống (sau `a*`, `rrt*`,
`dwa`, và bundle ngoài `vfh_plus`), đóng gói dạng plugin để import qua
**Models → Import algorithm** và chạy được ngay với các thuật toán hiện
có.

**Ràng buộc thiết kế do An đặt:** lần này chỉ được nhìn **schema import**
và **các ví dụ thuật toán được import**, không được nhìn scenario
library. Lần trước bundle `vfh_plus` bị hỏng nguyên tắc vì đã xem
scenario rồi mới quyết định hằng số.

---

## 1. Đã giao gì

Thư mục mới `mppi_import/` ở gốc repo, cùng bố cục với
`vfh_plus_iterated/`:

| File | Vai |
|---|---|
| `mppi.zip` | file để upload qua form import |
| `mppi_controller/planner.py` | thuật toán, 1 file, chỉ dùng `math` + `random` |
| `mppi_controller/__init__.py` | để entry point `mppi_controller:MPPIController` giải được |
| `mppi_controller/.planbench-plugin/plugin.json` | manifest |
| `DESCRIPTION.txt` | dán vào ô Description của form |
| `README.md` | thuật toán là gì, mỗi quyết định lấy từ dòng hợp đồng nào, đã chạy gì |
| `MAPPING.md` | từng hàm đối chiếu với từng bước của MPPI, và 7 chỗ đi lệch |

Bundle: `plugin_id = org.vinai.mppi`, `version = 0.1.0`, `role = local`,
lane `subprocess`, yêu cầu đúng một capability `lidar_2d`,
`requires_global_path: true`.

## 2. Chọn thuật toán gì, và vì sao — suy ra từ hợp đồng, không từ scenario

Ba câu hỏi "global hay local", "đọc kênh nào", "họ thuật toán nào" đều bị
hợp đồng import chốt sẵn, không phải do sở thích:

**Bắt buộc là local (hoặc monolithic).**
`apps/api/planbench_api/plugin_registry.py:55` đặt
`SUPPORTED_ROLES = {"local", "monolithic"}` và `REQUIRED_LANE =
"subprocess"`, kèm lý do: `SubprocessPlugin` chỉ có `reset`/`step`, không
có `plan()`. Nên **hiện tại không thể import một global planner** dù muốn.
Câu này trả lời luôn phần "global planner hoặc local controller tùy bạn
suggest" trong yêu cầu — hệ thống chỉ nhận được một trong hai.

**Chỉ xin `lidar_2d`.** `plugin_runtime.SYNTHESISABLE` là tập capability
mà khâu kiểm tra sau import dựng được ngoài episode; xin thứ khác thì
bundle dừng ở trạng thái `structural` (*chưa được kiểm*), không lên
`loaded`. Trong tập đó `human_state_estimates` chỉ có provider oracle nên
mọi run sẽ thành oracle-class, bị chặn khỏi đường chấm điểm production.
`lidar_2d` một mình ánh xạ sang observation class `lidar_only` — đúng lớp
mà DWA và VFH+ đang được định giá, nên ghép cặp so sánh được mà không phải
tranh luận G6.

**Chọn họ sampling optimal-control (MPPI).**
`LocalResetRequest.episode_seed` được thêm ở `plugin_api` 1.2.0 kèm ghi
chú rằng HĐ-4 cho phép một thuật toán lấy mẫu là tất định *khi biết
seed*. Tức hợp đồng đã mở sẵn chỗ cho một họ thuật toán mà roster hiện
chưa có ai: `dwa` tất định, `pure_pursuit` tất định, `ppo` là policy học.
Lấp đúng cái lỗ hợp đồng đã chừa ra là lựa chọn suy từ hợp đồng.

Và nó khác thật với những cái đang có, khác theo trục mà một selector
dùng được:

| | ứng viên là gì | có mô hình động lực học | nhớ gì giữa các tick |
|---|---|---|---|
| DWA | tốt nhất trong một thực đơn cặp `(v, ω)` **hằng** | có | không |
| VFH+ | một **hướng** chọn từ histogram | không | histogram + hướng trước |
| pure_pursuit | một cung hình học tới carrot | không | không |
| **MPPI** | một **chuỗi lệnh biến thiên theo thời gian**, lấy trung bình có trọng số cả lô | có | toàn bộ chuỗi nominal |

## 3. Thuật toán chạy thế nào

Mỗi tick:

1. Giữ chuỗi nominal `U = (u_0 … u_{T−1})` từ tick trước (warm start).
2. Nhiễu `U` thành `K` chuỗi ứng viên.
3. Mô phỏng từng chuỗi tiến về trước bằng động học differential-drive,
   **kẹp theo giới hạn gia tốc khai báo của robot ngay trong lúc roll
   out**.
4. Chấm điểm: khoảng cách tới carrot trên global path, độ hở với vật cản,
   tốc độ chưa dùng, độ lớn góc quay, cộng chi phí cuối chân trời.
5. Gộp: `w_k ∝ exp(−(S_k − S_min)/λ)`, `U ← U + Σ_k w_k ε_k`.
6. Phát `u_0`, dịch chuỗi một bước, sang tick sau.

Điểm khác DWA: DWA chọn **cái tốt nhất** trong một thực đơn cặp hằng số;
MPPI lấy **trung bình có trọng số** của cả lô các chuỗi biến thiên, và
khởi động từ đáp án tick trước — nên lệnh liên tục theo thời gian thay vì
nhảy giữa các ô trong lưới mẫu.

**Bảy chỗ đi lệch khỏi cách đọc thẳng của phương pháp**, đủ chi tiết trong
`MAPPING.md`. Ba chỗ đáng nhắc ở đây:

- **Va chạm được kiểm bằng một bảng "tầm tự do theo phương vị"**
  (`_free_range_map`) dựng một lần mỗi tick, tra O(1). So từng điểm roll
  out với từng tia là `samples × horizon × rays` phép tính khoảng cách,
  không lọt nổi deadline mà lane thi hành bằng cách **giết worker**.
  Bảng này khác histogram của VFH+: mỗi ô giữ một **khoảng cách**, không
  phải một bit chặn/thoáng — nên một quỹ đạo quay đầu trước khi tới tường
  không bị phạt vì đã từng chĩa vào tường.
- **Nhiễu được rút sẵn một lần ở `reset` vào một "sổ"**, đánh chỉ số theo
  `(tick, sample, step)`. Hướng dẫn tác giả cấm dùng generator mà trạng
  thái phụ thuộc số lần bị gọi; làm thế này tuân đúng chữ, và tiện thể
  bỏ sạch lời gọi RNG khỏi vòng lặp nóng.
- **Nhiễu được ghi công cho update là nhiễu *sau* khi kẹp**, không phải
  nhiễu đã rút. Update của MPPI chỉ nhất quán nếu `ε_k` là thứ roll out
  thực sự chạy; ghi công giá trị đã rút sẽ đẩy `U` về phía lệnh robot
  không đạt được và làm nó bão hoà vĩnh viễn ở giới hạn của chính nó.

## 4. Một lỗ hổng hợp đồng phát hiện được khi làm

**`episode_seed` không bao giờ tới được plugin trong lane subprocess.**

`subprocess_lane._encode_reset` gửi `plugin_api`, `global_path`, `robot`,
`declared` — không có `episode_seed`. Mà bundle import **luôn** chạy lane
subprocess (`plugin_registry.REQUIRED_LANE`). Kết quả: **không plugin
import nào seed được**, và lời khuyên §5 trong `docs/plugin_author_guide.md`
hiện không thi hành được cho đúng nhóm đối tượng nó viết cho. Đây đúng
dạng vấn đề mà ghi chú 1.2.0 nói field này sinh ra để sửa.

Bundle đọc bằng `getattr(request, "episode_seed", 0)` nên không chết, và
`README.md` §3 ghi rõ cái giá: mọi episode dùng chung một sổ nhiễu, nên
controller tái lập được **giữa các episode** chứ không chỉ trong một
episode — mạnh hơn HĐ-4 đòi. Đổi lại nó **không đóng góp phương sai do
seed**, tức paired bootstrap qua seed đang đo phương sai của scenario chứ
không của controller; và không hỏi được nó nhạy thế nào với chính việc lấy
mẫu của nó.

**Chưa sửa host.** Sửa `_encode_reset` là đụng vào platform, ngoài phạm vi
"dựng một plugin import được". Nếu An muốn, thêm một dòng vào dict đó là
đủ, và file plugin không cần đổi gì.

## 5. Đã kiểm những gì

Chạy thật, qua lane subprocess thật:

| Kiểm | Kết quả |
|---|---|
| `inspect_bundle` (cửa import) trên `mppi.zip` | `ok=True`, `package_dir=mppi_controller`, không problem |
| `resolve_compatibility` (preflight) | `registered_and_runnable`, `runnable=True` |
| `check_local_plugin` qua `SubprocessRuntime` | **conformance: no findings** — đủ method của role, hai worker mới trả lời giống hệt nhau, đọc đúng các kênh đã khai, không ghi vào request |
| `observation_class_for(('lidar_2d',))` | `lidar_only` — cùng lớp với DWA/VFH+ |
| `config_model_for` | 17 field của bundle + `control_period` do host thêm, không field nào bị từ chối |
| Thời gian mỗi tick (mặc định, 200 tick) | **1.22 ms/tick** round-trip, 0 safe stop, so với control period 50 ms |
| Lái vòng kín trong một thế giới đồ chơi **tự viết** | tới đích sau 220 tick, 10.26 m, độ hở nhỏ nhất 0.15 m, không va chạm; giống hệt nhau với seed 1/2/3 (đúng tính chất ở mục 4) |

**Không chạy scenario nào của library, và không sửa gì theo số đo.** Thế
giới đồ chơi (phòng 12×8, hai đĩa vật cản, path 5 waypoint, lidar 72 tia
ray-cast) viết ra chỉ để trả lời "vật thể này có lái được không", không
phải "nó tốt không". Con số đầu tiên trung thực về controller này là sweep
đầu tiên có người chạy.

**Chưa tinh chỉnh tham số.** Mọi mặc định là giá trị hợp lý đầu tiên.
`dwa_balanced` thì **đã** được tinh chỉnh — nên một so sánh ở mặc định là
so một controller đã tune với một controller chưa tune, và báo cáo phải
nói ra điều đó hoặc phải tune trước.

## 6. Cách import

1. **Models → Import algorithm** (cần quyền admin).
2. Upload `mppi_import/mppi.zip`.
3. Dán nội dung `mppi_import/DESCRIPTION.txt` vào ô Description.
4. Chọn robot profile của deployment cần đo.

Sau khi import, hệ thống tự giải nén và chạy conformance ngay (không phải
bấm lần hai). Kỳ vọng trạng thái `loaded`.

Muốn import lại sau khi sửa code: registry khoá theo
`(plugin_id, plugin_version)` nên phải **tăng `version` trong
`plugin.json`**, zip lại, import lại. Candidate identity đi theo checksum
của archive, nên bundle mới là candidate mới và kết quả cũ vẫn trỏ đúng
code đã sinh ra nó.

## 7. Chưa làm / để ngỏ

- **Chưa sửa `_encode_reset` để mang `episode_seed`** — xem mục 4.
- **Chưa chạy trên scenario library**, cố ý, theo ràng buộc thiết kế.
- **Chưa commit** — theo quy ước, An tự commit.
