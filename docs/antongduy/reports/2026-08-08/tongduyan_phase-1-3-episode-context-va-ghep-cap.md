# Báo cáo — Phase 1.3: EpisodeContext và luật ghép cặp (CONTRACTS HĐ-3)

> **Ngày:** 2026-08-08
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **1.3**
> **Nhánh:** `integrate-tongduyan`
> **Tiền đề:** Phase 1.1 (TaskProfile) và 1.2 (Candidate) xong cùng ngày.
> **Phạm vi:** chỉ 1.3. Không đụng 1.4 (move contract), 2.x (trace, map loader).

---

## 1. Đã làm gì

| File | Nội dung |
|---|---|
| `planbench_schemas/identity.py` (mới) | `canonical_json()`, `sha256_short()` — hai primitive dùng chung cho cả hai định danh của contract |
| `planbench_schemas/episode_context.py` (mới) | `EpisodeContext`, `SampleSet`, `NOMINAL_VARIANT`, `episode_context_id` |
| `planbench_benchmark/contexts.py` (mới) | `evaluation_seed_count()`, `build_evaluation_contexts()`, `iter_run_plan()`, `episode_total()` |
| `planbench_decision/pairing.py` (mới) | `require_shared_contexts()`, `require_sample_set()`, `context_ids()` |
| `tests/task_profile_fakes.py` (mới) | fixture dùng chung, tách ra từ `test_task_profile.py` |

### 1.1. Vì sao `EpisodeContext` nằm ở `schemas`, không ở `benchmark`

CONTRACTS §16 xếp `contexts.py` vào `runner/`. Nhưng ba nơi cần `EpisodeContext`:
runner (sinh danh sách), trace (metadata HĐ-5), và decision (ghép cặp ΔU). Đặt
nó trong `benchmark` thì `planbench_decision` phải import `planbench_benchmark`
— chiều ngược, vì bridge 1.2 đã cho `benchmark → decision`. Vòng import.

Chốt: **schema** ở `planbench_schemas` (đúng pattern `Scenario`/`RobotConfig`),
**generator + run plan** ở `planbench_benchmark/contexts.py` (đúng vai
`runner/` của §16), **luật từ chối** ở `planbench_decision/pairing.py` (contract
viết rõ đây là hành vi của Decision Engine).

### 1.2. `sample_set` KHÔNG nằm trong hash — và hệ quả phải xử lý

HĐ-3.1 chốt payload được hash đúng 4 trường: `task_profile_id`, `mission_id`,
`environment_variant`, `seed`. `sample_set` không có trong đó, nên nó **không
được** đưa vào hash: một id tính theo payload khác sẽ không khớp với id do một
implementation khác của cùng contract tính ra. Có test khẳng định hash đúng bằng
`sha256_short(canonical_json({4 trường}))`.

Nhưng bỏ `sample_set` ra khỏi hash mở một lỗ: một context `neighborhood` để
`environment_variant = "nominal"` sẽ hash **giống hệt** context `evaluation`
cùng mission cùng seed. Khi đó lệnh cấm gộp hai bộ mẫu (HĐ-11.4) không còn kiểm
được — nhìn vào id không biết dòng đó thuộc bộ nào.

Chốt bằng một invariant hai chiều trong validator:

```
sample_set == "evaluation"    ⟺  environment_variant == "nominal"
```

`evaluation` trên một variant ⇒ raise; `neighborhood` trên `nominal` ⇒ raise.
Vừa khớp HĐ-3.3 (evaluation lấy mẫu độc lập trên môi trường gốc; neighborhood
luôn là nhiễu quanh gốc), vừa làm hai bộ mẫu không thể trùng id.

### 1.3. Số episode suy từ rủi ro, không do người chọn

`evaluation_seed_count(profile) = ceil(N_min / số_mission)`, với `N_min` là
`ceil(3 / collision_probability_max)` từ 1.1. Seed dùng chung cho mọi mission,
nên mỗi seed sinh một episode cho **mỗi** mission — tổng episode = seed ×
mission ≥ N_min. Làm tròn **lên**: thiếu một episode so với `N_min` là trượt G2,
tức mất cả lần chạy.

Ví dụ: rủi ro 1% + 1 mission ⇒ 300 seed. Rủi ro 1% + 3 mission ⇒ 100 seed,
300 episode. Rủi ro 2% + 2 mission ⇒ 75 seed, 150 episode.

`build_evaluation_contexts` **cân bằng** giữa các mission, cố tình **không**
trọng số theo `Mission.probability` — quy mission distribution thành ngân sách
episode là việc của Mission Sampler (§1.2, pha 2). Làm ẩu ở đây thì một số
"trung bình cho vận hành kho A" lại được trích từ một mẫu cân bằng. Có test
khẳng định mission `probability=0.40` và `0.25` nhận **cùng** số episode.

### 1.4. Thứ tự vòng lặp: vì sao nó thật sự quan trọng

HĐ-3.2 bắt vòng ngoài là context, vòng trong là candidate. `iter_run_plan()`
làm đúng thế. Điều đáng ghi lại là **lý do**, vì kết quả hai cách giống nhau
(mọi episode seed từ context của nó):

| Ngắt sweep giữa đường | Candidate-outer | Context-outer |
|---|---|---|
| Dữ liệu thu được | candidate đầu 300 episode, candidate cuối 0 | mọi candidate cùng 140 context |
| So sánh được không | không, bỏ hết | được, chỉ nhỏ hơn |

Nên thứ tự này biến vi phạm mà HĐ-3.2 gọi tên — "hai candidate có số lượng
episode khác nhau trong cùng một run" — thành **không thể xảy ra về cấu trúc**,
thay vì một thứ phải nhớ đi kiểm. Có test cắt plan ở biên context rồi khẳng định
số episode mỗi candidate vẫn bằng nhau.

`iter_run_plan` cũng từ chối context trùng id: cùng một điều kiện chạy hai lần
sẽ bị đếm thành hai mẫu độc lập.

### 1.5. Nguồn ngẫu nhiên — kiểm chứng, không giả định

HĐ-3.2 đòi mọi thứ ngẫu nhiên (vị trí/quỹ đạo vật cản động, nhiễu cảm biến,
nhiễu odometry) suy từ seed của context, **không** từ RNG toàn cục. Đã grep toàn
bộ `services/simulator`, `packages/planning`, `packages/schemas`:

- `import random` / `np.random.<hàm>` không seed: **0 kết quả**;
- chỉ hai chỗ ngẫu nhiên, cả hai đều seed tường minh:
  `dynamic.position_at(obstacle, time, seed)` và
  `RRTStarPlanner` (`default_rng(SeedSequence([config.seed, episode_seed]))`).

Kết luận ghi vào docstring: yêu cầu này **đã đạt sẵn theo thiết kế**, không phải
việc phải làm. Nhiễu LiDAR/odometry hiện chưa tồn tại (KNOWN_LIMITATIONS #7);
khi thêm thì phải lấy seed từ context — docstring nói rõ ràng buộc đó.

## 2. Test

- `tests/test_episode_context.py` (mới) — **35 test**: 6 test định danh (ổn
  định, từng trường hash đổi id, `sample_set` không được hash, round-trip,
  frozen, seed âm), 4 test invariant hai chiều, 3 test số seed suy từ rủi ro,
  7 test generator (cân bằng mission, probability không trọng số, tái lập,
  `first_seed`), 4 test run plan (thứ tự vòng lặp, mọi cặp xuất hiện đúng 1
  lần, context trùng, input rỗng), 8 test `require_shared_contexts`, 3 test
  `require_sample_set`.
- `pytest` 4 file của Phase 1 → **117 passed**.
- `ruff check packages tests/` → sạch; đã format.
- Full suite: xem mục 4.

## 3. Dọn dẹp trong lượt này

| Việc | Loại |
|---|---|
| Gộp `_canonical_json` + `_sha256_short` (private trong `candidate.py`) thành `planbench_schemas/identity.py` dùng chung | **dedup thật**: hai định danh frozen của contract phải hash giống nhau từng byte; hai bản copy sẽ trôi khỏi nhau |
| Tách `make_profile`/`three_missions` từ `test_task_profile.py` sang `tests/task_profile_fakes.py`, thêm `constraints()` | phase 3.x (anchors, gates) đều cần fixture này; theo precedent `tests/agent_fakes.py`. Gỡ luôn 2 khối constraint dài lặp trong test |
| Sửa import chéo giữa test về convention repo (import trần, không `from tests.`) | nhất quán với `tests/api/*` |

`identity.py` có docstring nói rõ nó **không** thay
`planbench_benchmark.spec._canonical` (hash `repr`-based của fairness checksum
cũ): cái đó phải hash y như cũ mãi mãi, nếu không mọi `BenchmarkReport` đã lưu
tự khai là không so được với nhau. Hai hàm cùng mục đích nhưng khác hợp đồng —
để lẫn là mất dữ liệu cũ.

## 4. Một lỗ hổng của contract phát hiện được (chưa tự sửa)

`TaskProfile` theo HĐ-2 **không có vật cản động**. Nhưng HĐ-3.3 định nghĩa bộ
`evaluation` là "mission × **lần hiện thực vật cản** × seed". Tức nguồn của vật
cản động chưa được contract chỉ ra: nó không nằm trong task profile, và cũng
không phải thuộc tính của candidate.

Không tự quyết vì đây là nội dung hợp đồng, không phải chi tiết hiện thực. Hai
hướng để bàn ở 1.4 khi ký contract:

1. thêm một khối `dynamic_obstacles` (hoặc tham chiếu tới một environment model)
   vào `TaskProfile.environment` — deployment khai luôn mật độ/kiểu chuyển động;
2. giữ `Scenario` hiện có làm environment model, `TaskProfile.environment` trỏ
   tới một scenario id — tái dùng toàn bộ `SCENARIO_LIBRARY` và Scenario Editor
   đã có.

Hướng 2 rẻ hơn nhiều và tái dùng được tài sản sẵn có, nhưng cần một câu trong
contract. **Chưa chặn 1.3** vì context chỉ là định danh; nó chặn 2.x
(materialize Scenario từ context để chạy thật).

## 5. Kết quả full suite

*(cập nhật khi lệnh chạy nền xong)*

## 6. Mở khóa gì tiếp theo

Xong 1.3 là **Phase 1 hết phần code** — còn 1.4 (move contract + ký, gồm cả
quyết định ở mục 4 trên). Mở khóa **2.1 TraceRecorder** (`episode_context_id` +
`candidate_id` là metadata bắt buộc của HĐ-5) và **3.4 paired bootstrap**
(`require_shared_contexts` trả về tập id đã sắp xếp, đúng thứ tự resample cần
cho bootstrap tái lập được).
