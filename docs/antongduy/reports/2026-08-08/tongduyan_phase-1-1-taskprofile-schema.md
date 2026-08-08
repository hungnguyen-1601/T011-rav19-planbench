# Báo cáo — Phase 1.1: TaskProfile schema (CONTRACTS HĐ-2)

> **Ngày:** 2026-08-08
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **1.1**
> (plan tổng: `ke-hoach-chuyen-huong-planner-selector.md`, đợt 0.2)
> **Nhánh:** `integrate-tongduyan`
> **Phạm vi:** chỉ 1.1. Không đụng 1.2 (Candidate), 1.3 (EpisodeContext), 1.4 (contract move).

---

## 1. Đã làm gì

### 1.1. File mới `packages/schemas/planbench_schemas/task_profile.py`

Schema đúng HĐ-2, tất cả Pydantic `frozen=True, allow_inf_nan=False` theo house style:

| Class | Vai |
|---|---|
| `EnvironmentRef` | đường dẫn `.pgm` + `.yaml` định dạng `map_server`; chỉ giữ path, không đọc disk — validate profile không cần file tồn tại |
| `Mission` | start/goal (`Pose2D`) + `probability`; nhận cả dạng `[x, y, theta]` như YAML trong contract lẫn dạng mapping |
| `TaskRobotSpec` | kế thừa `RobotConfig` + `type` + `control_period` (T_cycle); property `t_cycle_ms` cho G4 |
| `TaskConstraints` | ngưỡng G1–G3 + tolerance + timeout; property `n_min_evaluation_episodes = ceil(3/p_max)` (HĐ-7.1) |
| `HardwareSpec` | `target_device`, `available_ram_mb` — nguồn ngưỡng G4/G5 |
| `TaskProfile` | gộp tất cả; `claim_level` chỉ là mức *mong muốn*, mức thật do `effective_claim_level()` tính |

### 1.2. Quyết định thiết kế quan trọng nhất: KHÔNG thêm field vào `RobotConfig`

Plan tổng viết "thêm `robot.control_period` vào `RobotConfig` nếu thiếu". Khi
làm thật thì phát hiện đây là bẫy: `Scenario` chứa `RobotConfig`, và
`_scenario_checksum()` hash `scenario.model_dump()` — thêm bất kỳ field nào
vào `RobotConfig` là **đổi checksum của mọi scenario đang tồn tại**, kéo theo
mọi `BenchmarkReport` cũ tự khai "không so được" và cache difficulty (P03)
thành stale. Đúng cái bẫy mà báo cáo đợt 4.1 (replanning) đã ghi lại khi
cân nhắc thêm field vào `Scenario`.

Giải pháp: `TaskRobotSpec(RobotConfig)` — subclass mang `control_period`,
`RobotConfig` gốc không đổi một byte. Có test khóa chặt điều này:
`TestScenarioChecksumUntouched::test_robot_config_has_no_new_fields` liệt kê
đúng 5 field hiện có của `RobotConfig`; ai thêm field sẽ vỡ test và buộc phải
đọc lý do.

### 1.3. Hai quy tắc contract được cưỡng chế bằng code

- **`effective_claim_level()`** (HĐ-2.2): 1 mission ⇒ `mission`; nhiều ⇒
  `deployment`; robust cần thêm cờ `neighborhood_evaluated`. `claim_level`
  khai trong YAML chỉ đóng vai **trần** — được khai thấp hơn dữ liệu, không
  bao giờ cao hơn. Đây chính là "vi phạm trông như thế nào" của HĐ-2: card in
  `ROBUST` khi chỉ có 1 mission giờ không thể xảy ra từ schema.
- **`n_min_evaluation_episodes`** (HĐ-7.1): suy từ `collision_probability_max`
  bằng quy tắc số 3. Có guard làm tròn trước khi `ceil` vì
  `3/0.01 = 299.999…94` trong float — không có guard thì yêu cầu bị đội thêm
  1 episode do nhiễu nhị phân. Test parametrize 5 mức rủi ro (0.01→300,
  0.005→600, 0.003→1000, 0.1→30, 1.0→3).

### 1.4. Chi tiết nhỏ có chủ đích

- `available_observations` được **canonical hóa** (strip, dedup, sort, cấm
  rỗng) ngay trong validator — G6 là phép so tập con, hai cách viết cùng một
  tập phải bằng nhau.
- `no_path_rate_max` default `0.02` đúng G1 của HĐ-7, override được.
- Tổng probability so với 1.0 bằng tolerance `1e-6` — `0.40+0.35+0.25` không
  bằng đúng 1.0 trong float, ví dụ ngay trong contract sẽ fail nếu so cứng.

### 1.5. Export

`planbench_schemas/__init__.py` thêm 7 tên mới vào import + `__all__` (giữ
thứ tự alphabet).

## 2. Test

- File mới `tests/test_task_profile.py` — **27 test**: parse ví dụ contract,
  hai dạng pose, frozen, canonical observations, tổng probability (cả case
  nhiễu float), mission id trùng, missions rỗng, 4 case claim level, 5 case
  N_min, `t_cycle_ms`, bounds của từng sub-schema, và 2 test khóa
  `RobotConfig` bất biến.
- `pytest tests/test_task_profile.py` → **27 passed**.
- Chạy kèm hàng xóm (`test_scenario_protocol.py`, `test_map_io.py`) → 77 passed.
- `ruff check` + `ruff format` sạch.
- Full suite đang chạy nền lúc viết báo cáo — kết quả cập nhật bên dưới.

## 3. Dọn dẹp plan cũ trong lượt này

**Không có gì để dọn trong lát cắt này.** 1.1 chỉ thêm file mới + sửa
`__init__`; không file nào nó chạm thuộc diện "plan cũ không dùng". Các điểm
dọn đã nhìn thấy trước và sẽ dọn đúng lúc chạm vào (theo nguyên tắc làm đến
đâu dọn đến đấy):

| Sẽ dọn khi làm | Cái gì |
|---|---|
| 2.3 `definitions.py` | ghi chú deprecation cho `smoothness` (tên cũ) ngay tại `episode_metrics.py`; xung đột tên `path_efficiency` xử lý bằng docstring hai phía |
| 5.1 evaluation distribution | `generalization.py` (P05 held-out) đóng băng — gỡ khỏi đường import của tầng decision, không xóa |
| 6.x API | leaderboard giữ chạy nhưng gỡ vai "màn hình chính" trong navigation |

## 4. Mở khóa gì tiếp theo

Theo bảng tra backlog: 1.1 mở khóa **1.3 EpisodeContext** (cần mission id),
**3.1 anchors** (`${constraints.*}`/`${robot.*}` giờ có chỗ để resolve),
**3.2 gates** (mọi ngưỡng đọc từ đây). 1.2 (Candidate + hash) không phụ
thuộc 1.1, làm song song được.
