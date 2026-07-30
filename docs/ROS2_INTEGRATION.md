# ROS2 / Nav2 Integration (M7)

Không dùng Gazebo. Simulator 2D tự dựng đóng vai trò robot + sensor +
môi trường; Nav2 đóng vòng điều khiển qua `/cmd_vel` đúng như với phần
cứng thật.

## Package

| Package | Loại | Vai trò |
|---|---|---|
| `planbench_msgs` | ament_cmake | `EpisodeStatus`, `BenchmarkEvent`; service `LoadScenario`, `ResetSimulator`, `StartEpisode`, `StopEpisode`, `GetEpisodeResult` |
| `planbench_ros_bridge` | ament_python | Chuyển đổi **thuần** domain ↔ ROS msg (không rclpy spin) → test được không cần ROS graph |
| `planbench_simulator_node` | ament_python | Node bọc `SimulationEngine` |
| `planbench_nav2_bringup` | ament_cmake | `nav2_params.yaml` + launch file |
| `planbench_benchmark_runner` | ament_python | Chạy scenario × seed qua NavigateToPose, thu kết quả |

**Vì sao tên là `planbench_simulator_node` chứ không phải
`planbench_simulator`** như spec liệt kê: `planbench_simulator` đã là tên
package Python của core library. Hai module cùng tên sẽ che nhau và node
sẽ import nhầm mà không báo lỗi.

## Giao diện topic

Simulator **publish**:

| Topic | Kiểu | Ghi chú |
|---|---|---|
| `/map` | `nav_msgs/OccupancyGrid` | latched (TRANSIENT_LOCAL); giá trị cell đã theo chuẩn ROS nên copy thẳng |
| `/scan` | `sensor_msgs/LaserScan` | frame `base_scan`; góc khớp chính xác `planbench_simulator.lidar.scan` |
| `/odom` | `nav_msgs/Odometry` | twist theo hệ body |
| `/tf` | `map→odom` (identity), `odom→base_link` | |
| `/tf_static` | `base_link→base_scan` | |
| `/clock` | `rosgraph_msgs/Clock` | nguồn thời gian mô phỏng |
| `/episode_status`, `/benchmark_event` | custom | trạng thái và sự kiện |

Simulator **subscribe**: `/cmd_vel` (`geometry_msgs/Twist`).

## Quyết định thiết kế

**Không dùng AMCL.** Simulator biết ground truth nên `map→odom` phát
identity. Thêm AMCL chỉ đưa sai số định vị vào một benchmark đang đo
planning và control.

**Episode arming.** Sau khi load, vật lý **đứng yên** ở start pose cho
đến khi gọi `~/start_episode`. Nếu chạy ngay từ lúc boot, stuck detector
sẽ kết thúc episode sau 5 giây — trước cả khi Nav2 kịp dựng costmap.
Trong lúc armed, `/scan`, `/tf`, `/clock` vẫn chạy (Nav2 cần chúng để
khởi động), chỉ robot là bất động.

**Hai đồng hồ.** `/clock` dùng `_sim_time` luôn tăng; `engine.time` (thời
gian episode) chỉ tăng sau khi start. Nhờ vậy timestamp sensor luôn tươi
mà thời gian episode vẫn bắt đầu từ 0.

**Watchdog `/cmd_vel`.** Quá `cmd_vel_timeout` (mặc định 1 s) không nhận
lệnh → robot dừng. Giữ lệnh cũ khi controller chết sẽ khiến robot chạy
mất kiểm soát, ngược hẳn mục đích của watchdog.

**Simulator là trọng tài.** Runner ghi cả `nav2_status` lẫn kết quả của
simulator. Nav2 báo SUCCEEDED chỉ có nghĩa "goal checker của tôi thoả
mãn", không đồng nghĩa với phán quyết collision/timeout/stuck của
benchmark. Ghi cả hai để bất đồng lộ ra thay vì bị che.

**Cùng robot, cùng scenario.** `nav2_params.yaml` khai báo đúng giới hạn
của `STANDARD_ROBOT` (radius 0.3, v 1.0, ω 2.0, a 1.0, α 3.0) và
`xy_goal_tolerance` = 0.30 khớp `goal_tolerance` của scenario. Đây là
điều kiện để so Nav2 với A*+DWA và A*+PPO.

## Chạy

```bash
export PLANBENCH_ROOT=$PWD
source /opt/ros/jazzy/setup.bash
source $PLANBENCH_ROOT/ros2_ws/install/setup.bash
# Core packages nằm trong repo (chưa cài); pydantic lấy từ .venv vì
# system Python không có và không cài global.
export PYTHONPATH="$PLANBENCH_ROOT/.venv/lib/python3.12/site-packages:\
$PLANBENCH_ROOT/packages/schemas:$PLANBENCH_ROOT/packages/planning:\
$PLANBENCH_ROOT/packages/metrics:$PLANBENCH_ROOT/packages/benchmark:\
$PLANBENCH_ROOT/services/simulator:$PYTHONPATH"
export ROS_LOCALHOST_ONLY=1

# Terminal 1
ros2 run planbench_simulator_node simulator_node --ros-args -p scenario:=open_space -p seed:=1
# Terminal 2
ros2 launch planbench_nav2_bringup planbench_nav2.launch.py
# Terminal 3
ros2 run planbench_benchmark_runner runner_node --ros-args \
  -p scenarios:="['open_space','static_obstacles','doorway']" -p seeds:="[1,2]"
```

Build: `cd ros2_ws && colcon build` (cần môi trường ROS, **không** dùng
`.venv` cho node ROS).

## Xử lý lỗi ROS

Runner đặt tên cho từng chế độ hỏng thay vì treo: `ros_service_timeout`,
`scenario_load_failed`, `action_server_unavailable`, `episode_start_failed`,
`goal_send_timeout`, `goal_rejected`, `runner_timeout`. Nav2 abort/cancel
được ghi vào cột `nav2_status`.

## Lỗi đã gặp khi tích hợp

1. **Episode chết vì stuck trước khi Nav2 kết nối** → thêm arming +
   `StartEpisode`/`StopEpisode`.
2. **Status cũ còn lưu trong runner** → vòng lặp thoát ngay, báo
   "running" với 0 s. Xoá cache trước mỗi episode.
3. **Episode thứ hai trở đi luôn hỏng**: reset dịch chuyển robot về start
   nhưng Nav2 vẫn tin robot ở chỗ cũ → abort hoặc "succeeded" tức thì.
   Sửa: đợi TF ổn định (`settle_seconds`, mặc định 3 s) rồi gọi
   `clear_entirely_{global,local}_costmap`. Trước 3/6, sau **6/6**.
