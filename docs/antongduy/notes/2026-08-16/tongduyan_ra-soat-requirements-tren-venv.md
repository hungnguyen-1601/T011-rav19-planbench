# Rà soát `requirements.txt` — đủ hay chưa, kiểm trên đúng `.venv`

**Ngày:** 2026-08-16 · **Loại:** quan sát/đánh giá · **Nhánh:** `tongduyan_plannerselector`
**Câu hỏi:** người mới clone repo về, cài đúng `requirements.txt`, có chạy được dự án không?

---

## 0. Kết luận

**Đủ.** Không import bên thứ ba nào trong repo bị bỏ sót. Full backend
suite chạy trên `.venv` sạch: **2815 passed, 8 skipped, 0 failed**
(42 phút 17 giây, exit 0).

Đây là lần kiểm chạy trên **đúng môi trường README chỉ định**, không phải
conda base — chính là lỗi mà note `2026-08-12/tongduyan_hai-moi-truong-va-hai-dependency-chua-khai.md`
ghi lại.

---

## 1. Cách kiểm

Không đọc file rồi gật. Bốn phép độc lập:

| # | Phép kiểm | Kết quả |
|---|---|---|
| 1 | Quét **AST** mọi `.py` trong repo, trừ stdlib và module cục bộ, đối chiếu với `requirements.txt` | Không thiếu gói nào |
| 2 | `pip install --dry-run -r requirements.txt` trên `.venv` | exit 0, không cài thêm gì |
| 3 | So từng dòng ghim `==` với `pip list` | **20/20 khớp phiên bản**, không lệch cái nào |
| 4 | `pytest --collect-only` rồi chạy full suite | 2819 collected, **2815 passed / 8 skipped / 0 failed** |

Phép 1 quan trọng nhất vì nó bắt được thứ ba phép kia không bắt: một gói
được import nhưng tình cờ có sẵn trong môi trường. Đúng cách `psutil`
sống sót từ 04-08 tới 12-08.

---

## 2. Ba nhóm import **không** nằm trong `requirements.txt`

Cả ba đều đúng chủ ý, ghi ra để lần sau không ai "sửa".

**(a) ROS2** — `rclpy`, `nav2_msgs`, `tf2_ros`, `geometry_msgs`,
`sensor_msgs`, `nav_msgs`, `rosgraph_msgs`, `builtin_interfaces`,
`rcl_interfaces`, `action_msgs`, `planbench_msgs`, `ament_index_python`,
`launch`, `launch_ros`. Chỉ trong `ros2_ws/`, build bằng colcon chứ không
pip. Không thuộc phạm vi file này.

**(b) LangGraph scaffold** — `langgraph`, `langchain_core`,
`langchain_openai`. Chỉ trong `src/`, là template T-011 đi kèm repo;
PlanBench không dùng. Hai chỗ đụng vào đều xử lý sạch:

- `tests/test_agents/test_graph.py:16-17` và `tests/test_api/test_routes.py:15-16`
  — `pytest.importorskip` ở mức module.
- `tests/test_api/conftest.py` — import **trong thân fixture**, vì một
  conftest import lỗi biến thành collection error chứ không phải skip sạch.

**(c) `dotenv`** — `scripts/submit_log.py:24-29` bọc `try/except ImportError`.
Ngoài ra python-dotenv vẫn vào máy gián tiếp qua `uvicorn[standard]` và
`pydantic-settings`.

---

## 3. Tám test skip — không cái nào là lỗi

Tất cả đều là `importorskip` trên gói **optional**, đúng thiết kế
`requirements-optional.txt`:

| Skip | Gói thiếu |
|---|---|
| `tests/test_agents/test_graph.py` · `tests/test_api/test_routes.py` | `langgraph`, `pytest_asyncio` (scaffold T-011) |
| `tests/test_rl.py` | `gymnasium` |
| `tests/test_tuning.py` | `optuna` |
| `tests/api/test_api_models.py:647` | `planbench_rl.observation` |

Đã kiểm trực tiếp: `optuna`, `mlflow`, `torch`, `gymnasium`,
`stable_baselines3`, `openai`, `anthropic`, `psycopg` **đều chưa cài** —
và hệ thống vẫn chạy đủ. Suy giảm có tiếng, đúng như file optional hứa.

---

## 4. Hai điểm đáng biết, không phải lỗi

**`.venv` chạy Python 3.13.12 (Anaconda)**, trong khi header
`requirements.txt` hướng dẫn `python3.12 -m venv`. Hợp lệ —
`requires-python = ">=3.12"` — nhưng nếu muốn CI và máy dev khớp nhau thì
đây là chỗ lệch duy nhất còn lại.

**`docker/requirements-api.txt` cố ý lệch** với `requirements.txt` ở ba
chỗ: thiếu `psutil` (image Linux có `os.sched_setaffinity`, nhánh psutil
không với tới được), thiếu `torch`/`sb3`/`gymnasium` (training là workload
riêng, kéo torch vào image API là thêm vài GB cho code API không chạy),
thiếu pytest/ruff. Cả ba đều có comment giải thích ngay trong file.

---

## 5. Phía web

`apps/web` cài đủ, `package-lock.json` có, `npm ls --depth=0` sạch: 10 gói
top-level (next 15.5.22, react 19.2.8, recharts, yaml, vitest, typescript,
ba gói `@types`). Node v22.17.1, npm 11.18.0.

---

## 6. Còn để ngỏ

Đúng một mục, **chuyển nguyên từ note 12-08 mục 7 sang**, vì nó vẫn chưa
được nối vào đâu:

> `.venv` không có gì kiểm nó còn khớp `requirements.txt`. Lệnh
> `pip install --dry-run -r requirements.txt` làm được việc đó trong một
> giây; chưa nối vào `dev_stack.sh`, chưa nối vào pre-commit, chưa nối vào
> chỗ nào.

Hôm nay tôi chạy nó bằng tay và nó sạch. Lần sau vẫn phải nhớ chạy bằng tay.
