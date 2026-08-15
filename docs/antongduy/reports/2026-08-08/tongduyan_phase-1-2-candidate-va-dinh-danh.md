# Báo cáo — Phase 1.2: Candidate và định danh (CONTRACTS HĐ-1)

> **Ngày:** 2026-08-08
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **1.2**
> **Nhánh:** `integrate-tongduyan`
> **Tiền đề:** Phase 1.1 (TaskProfile) xong cùng ngày — xem
> `tongduyan_phase-1-1-taskprofile-schema.md`.
> **Phạm vi:** chỉ 1.2. Không đụng 1.3 (EpisodeContext), 1.4 (move contract).

---

## 1. Đã làm gì

### 1.1. Package mới `packages/decision/planbench_decision/`

Tầng decision theo CONTRACTS §16 (map vào layout hiện tại theo plan tổng mục 2).
Đăng ký vào `pyproject.toml` `pythonpath` và `ruff.toml` `known-first-party`
— thiếu dòng ruff thì CI báo 3 lỗi import-sort mà local không thấy, đúng cái
bẫy `ruff.toml` đã ghi chú sẵn.

`candidate.py` — `Candidate` + hai component + validate scope:

| Thành phần | Vai |
|---|---|
| `StackComponent` | một tầng modular: `name` + `version` |
| `PolicyComponent` | tầng duy nhất của monolithic: `name` + `checkpoint` + `version` |
| `Candidate` | `type: modular\|monolithic`, params, `observation_requirements`; `candidate_id` là computed field |
| `load_candidate()` | parse + đối chiếu id khai sẵn |
| `validate_experiment_scope()` | cưỡng chế HĐ-1.4, raise chứ không cảnh báo |

### 1.2. Ba quyết định thiết kế đáng ghi

**(a) Định danh là hash, `id` khai trong YAML bị loại bỏ — nhưng vẫn được đối chiếu.**

Contract viết `id: null # sinh tự động`. Bản code đầu tiên để `id` thành field
thật rồi cross-check trong `model_validator`. Bỏ cách đó vì nó phá round-trip:
`candidate_id` là `computed_field` nên có mặt trong `model_dump()`, và với
`extra="forbid"` thì `model_validate(model_dump())` **fail** — đúng cái round
trip mà candidate lưu trong DB và trong manifest phụ thuộc.

Cách chốt: validator `mode="before"` **bỏ** cả `id` lẫn `candidate_id` khỏi
input; việc đối chiếu id người viết chuyển sang `load_candidate()` ở biên.
Giữ được cả hai tính chất: dump/reload nguyên vẹn, và một hash cũ dán vào YAML
sau khi sửa config thì **không load được** thay vì âm thầm dán nhãn sai lên
configuration mới.

**(b) `extra="forbid"` trên Candidate.** `global_plannr` viết sai chính tả mà
được bỏ qua sẽ parse thành candidate thiếu tầng, rồi báo lỗi trỏ vào chỗ khác.

**(c) Params block không thuộc tầng nào ⇒ từ chối.** `params.dwa` trên stack
chạy `mppi` không bao giờ được đọc, **nhưng vẫn đổi `candidate_id`**: hai
candidate hành xử giống hệt nhau lại được chấm điểm, so sánh và báo cáo như hai
đối thủ. Silent no-op ở đây tệ hơn là không cho chạy.

### 1.3. `validate_experiment_scope` — vi phạm HĐ-1.4 không thể lọt

So sánh **cả component lẫn params của tầng bị giữ cố định**: hai candidate cùng
chạy `dwa` không phải là "giữ controller cố định" nếu một bên đã tinh chỉnh
lại. Ba luật:

- `global_planner_selection` ⇒ tầng local (tên + version + params) giống hệt ở mọi candidate;
- `local_controller_selection` ⇒ gương lại cho tầng global;
- `full_stack_selection` ⇒ không ràng buộc.

Thêm hai luật áp cho **mọi** scope: candidate trùng `candidate_id` xuất hiện hai
lần ⇒ raise (một configuration không thể là đối thủ của chính nó); tập rỗng ⇒
raise. Monolithic **không được** vào run scope theo tầng — nó không có tầng nào
để giữ cố định, nên không câu nào về "global planner" phủ được nó.

### 1.4. Vocabulary quan sát dùng chung — sửa lại 1.1

`packages/schemas/planbench_schemas/observations.py` (file mới):
`ObservationToken` = `lidar_2d` | `human_state_estimates`, `KNOWN_OBSERVATIONS`,
`canonical_observations()`.

**Vì sao phải siết:** G6 là phép so tập con **theo mặt chữ**. Candidate khai
`lidar2d` gặp deployment khai `lidar_2d` sẽ bị loại ở G6 vì một lỗi chính tả,
và Decision Card báo "không tương thích phần cứng" — một câu trả lời **sai
nhưng trông đúng**. Nên vocabulary đóng, cả hai phía validate cùng một hàm,
token lạ fail lúc parse chứ không fail lúc gate.

Đây là **sửa lại 1.1**: `available_observations` hôm nay còn nhận chuỗi tự do
(và test cũ dùng `"camera"`). Đã đổi sang vocabulary chung, cập nhật 2 test của
1.1 và thêm 1 test mới cho token lạ.

**`full_static_map` cố tình KHÔNG là một requirement.** Deployment cung cấp bản
đồ trong `TaskProfile.environment`, nên mọi deployment đều có nó. Đưa nó thành
requirement thì mọi candidate modular đều fail G6 trên profile mà tác giả không
nghĩ đến việc khai lại điều hiển nhiên — ngược hẳn mục đích của cổng. Lý do này
ghi trong docstring cả hai file vì nó là loại quyết định 3 tháng sau không ai
đoán lại được.

### 1.5. Bridge registry ↔ candidate

`packages/benchmark/planbench_benchmark/candidates.py` (file mới) — chỗ **duy
nhất** hai hệ định danh gặp nhau:

- `observation_requirements_for(info)` suy requirement từ khai báo P02 sẵn có
  (hợp của hai tầng) — P02 đổi vai thành nguồn của G6 đúng như plan.
- `candidate_from_stack(stack_id, params=...)` → Candidate, có validate params
  qua registry.
- `stack_id_for()` / `build_planners(candidate, episode_seed=...)` → chiều
  ngược lại, để runner (1.3, P4) dựng planner thật.

**Mọi stack trong registry map thành `modular`, kể cả `astar+ppo`** — stack đó
là A\* lập đường + PPO đi theo (`requires_global_path=True`), tức đúng hình
dạng modular. Monolithic là policy end-to-end không có global planner; registry
chưa có cái nào, và chạy được nó cần adapter `MonolithicPolicy` của HĐ-4.
`build_planners` trên monolithic raise kèm đúng câu đó thay vì trả về thứ gì
đó nửa vời.

### 1.6. Bug thật lộ ra khi viết test

Test đầu dùng tên param của contract (`sim_time`) — repo này gọi là
`horizon_seconds`. Kết quả: `candidate_from_stack("astar+dwa", params={"sim_time": 2.5})`
**không** lỗi, và sinh ra candidate có `candidate_id` **giống hệt** bản mặc
định (Pydantic bỏ qua key lạ theo mặc định).

Bản thân định danh không sai — hai candidate đó *thật sự* hành xử giống nhau.
Cái sai là người viết tin rằng mình đang đánh giá một controller đã tinh chỉnh,
rồi đọc một kết quả thật như câu trả lời cho câu hỏi không ai hỏi. Thêm
`UnknownParameterError`: param không nằm trong `config_schema.properties` của
stack ⇒ từ chối lúc đăng ký candidate. Đây là lỗi chỉ lộ ra khi viết test, đúng
loại HĐ-15.2 nói.

Cũng vì lý do trên, `candidate_from_stack` **vật chất hóa toàn bộ default** vào
`params` (`validated.model_dump()`), không giữ default ngầm: nếu default đổi ở
commit sau, candidate cũ và mới phải có id khác nhau.

## 2. Test

- `tests/test_candidate.py` — **37 test**: hai hình dạng hợp lệ + 6 kiểu trộn
  bị từ chối, canonical requirements, 7 test định danh (thứ tự khóa, thứ tự
  token, đổi param, đổi version, đổi requirements, đổi type, `stack_label`
  không phải identity), round-trip dump/reload, 4 test `load_candidate`,
  13 test scope.
- `tests/test_candidate_bridge.py` — **17 test**: mapping requirement,
  `astar+ppo` là modular, param lạ bị từ chối, default vật chất hóa, reference
  stack bị từ chối, build planner hai tầng, monolithic không có registry stack,
  và cặp `astar+dwa` vs `rrtstar+dwa` là `global_planner_selection` hợp lệ
  (chính là cặp cho lát cắt dọc P4).
- 3 file mới + sửa: `pytest tests/test_candidate.py tests/test_candidate_bridge.py tests/test_task_profile.py` → **82 passed**.
- `ruff check packages` + format: sạch.
- Full suite: xem mục 5.

## 3. Dọn dẹp trong lượt này

Theo nguyên tắc làm đến đâu dọn đến đấy, những gì **thuộc lát cắt này**:

| Việc | Loại |
|---|---|
| `available_observations` chuỗi tự do ⇒ vocabulary đóng | sửa lại 1.1 (không phải plan cũ) |
| `benchmarkable=False` (D12) được **cưỡng chế ở biên mới**: `NotBenchmarkableError` chặn `*+pure_pursuit` thành candidate | mang luật cũ sang thế giới mới thay vì để một bool không ai kiểm |
| `requires_global_path=False` ⇒ cũng bị chặn khỏi đường modular | cùng lý do |

**Chưa xóa dòng nào.** Hai entry `*+pure_pursuit` giữ nguyên trong registry:
`tests/test_nav_stack.py` và `test_path_follower.py` còn dùng
`PurePursuitLocalPlanner` trực tiếp, và nó vẫn là pipeline reference hợp lệ —
cái cần chặn là *tư cách candidate*, và điều đó đã chặn ở biên. Các điểm dọn
còn treo (deprecated `smoothness` ở 2.3, đóng băng `generalization.py` ở 5.1,
hạ vai leaderboard ở 6.x) chưa tới lượt vì lát cắt này không chạm vào chúng.

## 4. Mở khóa gì tiếp theo

1.2 mở khóa **1.3 EpisodeContext** (`episode_context_id` cần `candidate_id` để
sinh danh sách chạy), **2.1 trace metadata** (`candidate_id` là một cột
metadata bắt buộc của HĐ-5), và **mọi phép so** ở phase 3. `build_planners()`
làm P4 (lát cắt dọc) chỉ còn thiếu context + trace.

## 5. Kết quả full suite

`pytest tests/ -q` → **1529 passed, 6 skipped** (11 phút 32). Baseline sau
Phase 1.1 là 1474 passed — thêm 55 test (37 + 17 mới, cộng 1 test mới ở
`test_task_profile.py` cho token quan sát lạ), **không vỡ test nào**.

Việc siết vocabulary quan sát ở 1.4 không lan ra ngoài `test_task_profile.py`:
`available_observations` là schema mới của Phase 1.1, chưa có nơi nào khác
trong repo dùng tới nó.
