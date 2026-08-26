# Cấu trúc plugin hợp lệ cho Algorithm Host

**Ngày:** 2026-08-18

Plugin là một gói gồm **manifest + code thuật toán/adapter + test**. Plugin không
được lưu vào database; code nằm trong thư mục plugin hoặc Python package. Database
chỉ lưu Candidate — một cấu hình cụ thể được tạo từ plugin.

## 1. Cấu trúc tối thiểu

```text
my_planner/
├── __init__.py
├── planner.py
└── .planbench-plugin/
    └── plugin.json
```

- `plugin.json`: khai plugin là loại gì, cần dữ liệu nào và phải import class nào.
- `planner.py`: code thực sự chạy thuật toán hoặc adapter gọi thư viện có sẵn.
- `__init__.py`: export class được ghi trong `entry_point`.
- `tests/` và `algorithm_spec.yaml` nên có, nhưng không bắt buộc để discovery đọc
  được plugin.

## 2. Ví dụ `plugin.json`

```json
{
  "plugin_api": "1.1.0",
  "id": "org.example.theta-star",
  "version": "0.1.0",
  "role": "global",
  "runtime": {
    "supported_lanes": ["python_in_process"],
    "production_lane": "python_in_process",
    "profiles": {
      "python_in_process": {
        "protocol": "planbench-inproc/v1",
        "codec": "python-object/v1",
        "deadline_policy": "control-period",
        "entry_point": "my_planner:ThetaStarPlanner"
      }
    }
  },
  "requirements": {
    "all_of": ["planbench://channel/planning-grid@1"]
  },
  "supports": {
    "action_types": ["global-path@1"],
    "robot_dynamics": ["differential-drive@1"],
    "execution_models": ["synchronous-step@1"]
  },
  "config_schema": {
    "type": "object",
    "properties": {
      "heuristic_weight": {
        "type": "number",
        "minimum": 1.0,
        "default": 1.0
      }
    }
  }
}
```

Ý nghĩa các phần:

| Trường | Ý nghĩa |
|---|---|
| `plugin_api` | Phiên bản giao thức plugin mà host hỗ trợ. |
| `id`, `version` | Định danh và phiên bản plugin. |
| `role` | `global`, `local` hoặc `monolithic`. |
| `runtime` | Cách chạy plugin và class cần import. |
| `requirements` | Các channel/capability plugin bắt buộc phải được cấp. |
| `supports` | Output, robot dynamics và execution model tương thích. |
| `config_schema` | Các tham số người dùng được phép cấu hình. |

`entry_point: "my_planner:ThetaStarPlanner"` nghĩa là import class
`ThetaStarPlanner` từ package `my_planner`.

## 3. Ví dụ code thuật toán

```python
from planbench_plugin_sdk import GlobalPlanResponse


class ThetaStarPlanner:
    def __init__(self, heuristic_weight: float = 1.0):
        self.heuristic_weight = heuristic_weight

    @property
    def name(self) -> str:
        return "theta_star"

    def plan(self, request):
        grid = next(
            channel.payload
            for channel in request.channels
            if channel.capability == "planbench://channel/planning-grid@1"
        )
        path = theta_star(grid, request.start, request.goal, self.heuristic_weight)
        if path is None:
            return GlobalPlanResponse(success=False, failure_reason="no path")
        return GlobalPlanResponse(success=True, path=tuple(path))
```

`theta_star(...)` là implementation thật của thuật toán. Nếu đã có thư viện chính
thức, class trên có thể chỉ là adapter gọi thư viện đó.

## 4. Ba loại plugin

- `global`: nhận start/goal và trả global path qua `plan()`.
- `local`: nhận trạng thái từng tick và trả vận tốc qua `reset()` + `step()`.
- `monolithic`: cũng dùng `reset()` + `step()`, nhưng không cần global path.

## 5. Khi đưa plugin vào hệ thống

```text
Đặt bundle vào thư mục plugin hoặc cài Python package
→ host đọc plugin.json
→ kiểm manifest, dependency và compatibility
→ khi được phép mới import code
→ tạo Candidate trên UI/API
→ Candidate được lưu DB và dùng để chạy benchmark
```

- Manifest sai schema: plugin bị `quarantined`.
- Thiếu dependency/provider: vẫn `registered`, nhưng chưa `runnable`.
- Thiếu config bắt buộc: plugin vẫn tồn tại, nhưng không tạo được Candidate.
- Đủ điều kiện: host import `entry_point` và chạy plugin.

Ví dụ thật trong repo:

- `examples/plugins/corridor_planner`: global plugin in-process.
- `examples/plugins/social_nav`: local plugin dùng provider graph.
- `examples/plugins/remote_wanderer`: local plugin chạy subprocess.

## 6. Phạm vi hiện tại

Algorithm Host đã discovery và chạy được plugin chuẩn bị sẵn. UI upload plugin và
Paper-to-Plugin bằng AI/LLM chưa thuộc MVP hiện tại; đây là phần mở rộng sau khi
host và trace safety hoàn tất.
