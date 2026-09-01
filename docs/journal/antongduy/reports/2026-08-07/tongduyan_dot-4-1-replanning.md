# Báo cáo — Đợt 4.1: Replanning khi bị vật cản động chặn

> **Ngày:** 2026-08-07
> **Plan nguồn:** `docs/antongduy/plans/2026-08-05/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`, mục **4.1**
> (thiết kế chi tiết tham chiếu thêm `plans/2026-08-03/scenario-editor-va-replanning-cong-bang.md`, Plan B).
> **Nhánh:** `integrate-tongduyan`
> **Tiền đề:** Đợt 0–3 đã nghiệm thu; 4.3 (F08 replay) đã làm riêng theo yêu cầu user.
> **Phạm vi:** chỉ 4.1. **Không** đụng 4.2 (map loader ROS `map_server`).

---

## 1. Vấn đề đang giải

Hôm nay robot bị một vật cản động đứng chắn đường là thua ngay: engine
kết luận `STUCK` và episode kết thúc. Đường toàn cục được lập đúng một
lần, ở đầu episode, trên grid chỉ có vật cản **tĩnh**. Không có cơ chế
nào để robot xin một đường khác.

Điều này làm sai lệch benchmark theo một hướng khó thấy: mọi thuật toán
đều bị phạt như nhau, nhưng cái bị đo là "local planner có luồn qua được
khe không", chứ không phải "cả stack có xử lý được tình huống bị chặn
không" — mà tình huống thứ hai mới là thứ Nav2 làm trong thực tế.

## 2. Ba quyết định thiết kế khó nhất

### 2.1. Cấu hình replanning nằm ở `BenchmarkSpec`, KHÔNG ở `Scenario`

Plan 08-03 (bản cũ) đề xuất thêm `replanning_enabled`/`max_replans` vào
`Scenario`, lý do: nó tự động đi vào `_scenario_checksum()` nên không
phải viết thêm code để bảo đảm công bằng. Plan 08-05 (bản được approve)
đã treo lại quyết định này: *"Không tự động thêm vào `Scenario` nếu điều
đó làm thay đổi dữ liệu cũ mà chưa có migration."*

Kiểm tra thực tế: `_scenario_checksum()` hash `scenario.model_dump()`
trừ `random_seed` và `description`. Thêm bất kỳ field nào vào `Scenario`
sẽ **đổi checksum của mọi scenario đang tồn tại**, kéo theo:

- `conditions_checksum` của mọi `BenchmarkReport` đã lưu đổi theo → mọi
  report cũ tự khai là "không so được với nhau";
- toàn bộ cache hiệu chuẩn độ khó (P03) thành `stale`, vì
  `ScenarioCalibration` so `scenario_checksum` để phát hiện scenario đã
  bị sửa.

Đây đúng là hai rủi ro "Cao" trong bảng rủi ro của plan ("Benchmark cũ
đổi checksum", "Metadata split và Scenario bị lệch"). Nên chọn cách
khác: `ReplanningConfig` là schema riêng
(`packages/schemas/planbench_schemas/replanning.py`), gắn vào
`BenchmarkSpec`, cùng đúng lý do P05 không nhét `split` vào `Scenario` và
P03 không nhét `difficulty` vào `Scenario` — **replanning là luật của
giao thức đánh giá áp lên scenario, không phải đặc tính vật lý của
scenario**.

Điều kiện công bằng của plan vẫn được giữ, chỉ bằng cơ chế khác:
`BenchmarkSpec` có **đúng một** `replanning` cho cả sweep, `runner.py`
đọc từ spec chứ không bao giờ đọc từ `AlgorithmSpec.config`, nên không
có đường nào để cấp cho stack này 3 lượt và stack kia 0 lượt.

### 2.2. Checksum chỉ đổi khi replanning **bật**

`FairnessRecord.build()` chỉ nối chuỗi replanning vào payload hash khi
config khác mặc định. Hệ quả:

| Tình huống | conditions_checksum |
|---|---|
| Benchmark cũ (không có field) | **không đổi một bit** |
| Chạy mới, replanning tắt | giống hệt benchmark cũ |
| Replanning bật, `max_replans=2` | khác |
| Đổi sang `max_replans=3` | khác nữa |
| Cùng luật, khác thuật toán | **giống nhau** |

Cách "luôn hash" đơn giản hơn về code nhưng sẽ thông báo với người dùng
rằng toàn bộ kết quả cũ vừa mất giá trị so sánh, trong khi điều kiện
chạy của chúng không hề đổi. Có test riêng ghim tính chất này.

### 2.3. Ô lưới chứa robot bị ép về FREE khi replan — và vì sao nó an toàn

Đây là chi tiết mà nếu bỏ qua thì tính năng **chạy không lỗi nhưng không
bao giờ hoạt động**. Lần chạy thử đầu tiên cho kết quả:

```text
off  stuck  t=13.9  replans=0
on   stuck  t=13.9  replans=0     ← bật mà không replan lần nào
```

Nguyên nhân: robot bị chặn thì đứng rất gần vật cản — gần hơn bán kính
inflate (`robot.radius + √2 × resolution`). Ô chứa tâm robot vì thế bị
đánh dấu occupied trên grid quy hoạch, global planner nhận start nằm
trong vật cản và trả `no path`. Replan thất bại đúng vào lúc cần nhất.

Cách xử lý: sau khi inflate, ép **đúng một ô** — ô chứa tâm robot — về
`FREE`. Khẳng định được, không phải cho tiện: engine kết thúc episode
ngay khoảnh khắc robot chồng lên vật cản, nên robot còn đang chạy tức là
chứng minh được nó không nằm trong vật cản nào; ô đó bị occupied là do
biên an toàn quy hoạch, không phải do hình học. Các ô lân cận giữ nguyên
inflation, nên đường trả về vẫn phải thoát ra qua khoảng trống thật.

Sau khi sửa:

```text
off  stuck    t=13.9  replans=0
on   success  t=32.7  replans=1
```

## 3. Cái đã làm

### 3.1. `ReplanningConfig` — schema mới

```python
class ReplanningConfig(BaseModel):   # frozen
    enabled: bool = False
    max_replans: int = Field(default=0, ge=0)
```

Validator từ chối `enabled=True, max_replans=0`: bật mà không làm gì là
trạng thái tệ nhất — report sẽ ghi "replanning: enabled" trong khi không
robot nào từng replan.

**Trigger không cấu hình được**, chủ ý. Engine kết luận `STUCK` hoặc
`NO_PROGRESS` là điều kiện kích hoạt; mở trigger thành tham số sẽ mở lại
đúng cánh cửa mà config này đóng — một stack replan ở ngưỡng nhạy hơn
stack khác. Nếu sau này muốn tune, nó phải vào chung vòng ngân sách P01
(Đợt 5A).

### 3.2. `SimulationEngine`: hai method mới

- `dynamic_obstacles_now()` — vị trí ground-truth của vật cản động tại
  thời điểm hiện tại. Public hoá vì replan cần: planner chỉ nhận map
  tĩnh sẽ lập lại **đúng đường vừa bị chặn**, do không input nào của nó
  thay đổi. Đây là ground truth nhưng chỉ stack đọc, giữa hai bước điều
  khiển — `get_observation()` không đổi một dòng, nên khai báo cân bằng
  thông tin P02 vẫn đúng nguyên.
- `resume_after_replan(note)` — hồi sinh episode đã `FINISHED` với
  `STUCK`/`NO_PROGRESS`. Từ chối `COLLISION` và `TIMEOUT`: đường mới
  không được phép xoá một va chạm đã xảy ra.

  Hai việc phải làm, không phải một. Đổi state về `RUNNING` là nửa hiển
  nhiên; nửa còn lại là **reseed cửa sổ trượt** `_window` — mọi mẫu
  trong đó vẫn mô tả một robot đứng yên, nên nếu không reseed thì bước
  kế tiếp kết luận `STUCK` lại ngay và replan chỉ mua được đúng 1 bước
  mô phỏng. Có test riêng cho việc này.

  Event `stuck` bị **thay** bằng event `replan` (giữ nguyên thời điểm và
  lý do trong message). Để lại event `stuck` sẽ nhét một kết luận chấm
  dứt vào hồ sơ của một episode không chấm dứt ở đó.

### 3.3. `nav_stack.run_stack()` — nơi cắm logic

Đúng điều kiện công bằng #1 của plan: cắm ở chỗ **mọi** stack đi qua,
không cắm vào `dwa/planner.py` hay bất kỳ file thuật toán nào. Sau mỗi
`engine.step()`, nếu engine vừa kết thúc với `STUCK`/`NO_PROGRESS`, còn
ngân sách, và replanning bật:

1. lấy vật cản động hiện tại, rasterize vào grid quy hoạch tạm rồi
   inflate;
2. mở ô chứa robot (mục 2.3);
3. `global_planner.plan(grid_mới, vị_trí_hiện_tại, goal)`;
4. thành công → `local_planner.reset(đường_mới, robot)`,
   `engine.resume_after_replan(...)`, `held_action = None` (lệnh đang
   giữ được tính cho đường vừa hỏng, phải tính lại ngay);
5. thất bại hoặc hết lượt → giữ nguyên `STUCK`/`NO_PROGRESS` như cũ.

Mặc định tắt; run tắt cho **trajectory giống hệt** run trước khi có tính
năng (có test).

### 3.4. Metrics

- `EpisodeMetrics.replan_count: int | None` — đếm trực tiếp lúc chạy
  theo pattern accumulator (`latencies`/`failures`), không suy từ
  trajectory: một lần replan không để lại dấu vết nào trong trajectory
  để suy ngược.
- `global_planning_time` và `expanded_nodes` thành **tổng cộng dồn** qua
  mọi lần plan. Khi tắt chỉ có 1 plan → giá trị giống hệt hành vi cũ,
  không regression.
- `planned_path_length`/`path_efficiency` theo **đường của lần replan
  cuối** — đường robot thật sự đang đi lúc kết episode.

### 3.5. Báo cáo và hiệu chuẩn

- Report Markdown: bảng Conditions luôn ghi luật replanning; bảng Runs
  thêm cột **Replans** **chỉ khi** replanning bật (tắt thì cột đó là một
  dãy số 0 nhắc lại điều bảng Conditions đã nói).
- `scripts/calibrate_difficulty.py --max-replans N`: baseline replan
  được thì scenario dễ đi, tức là **một thang đo khác**. Script bắt buộc
  phải kèm `--calibration-version` riêng, không cho dùng version mặc
  định của thang không-replanning, và `BaselineSpec.replanning_enabled`
  ghi lại đúng luật đã chạy (trước đây hard-code `False`).

## 4. File thay đổi

| File | Thay đổi |
|---|---|
| `packages/schemas/planbench_schemas/replanning.py` | **mới** — `ReplanningConfig`, `NO_REPLANNING` |
| `packages/schemas/planbench_schemas/__init__.py` | export |
| `services/simulator/planbench_simulator/engine.py` | `dynamic_obstacles_now()`, `resume_after_replan()` |
| `services/simulator/planbench_simulator/nav_stack.py` | `_planning_grid()`, `_replan()`, `_with_free_start_cell()`, vòng replan trong `run_stack()` |
| `packages/metrics/planbench_metrics/episode_metrics.py` | `replan_count` + đổi nghĩa (có ghi chú) 3 field khi có replan |
| `packages/benchmark/planbench_benchmark/spec.py` | `BenchmarkSpec.replanning`, `FairnessRecord.replanning_enabled/max_replans`, hash có điều kiện |
| `packages/benchmark/planbench_benchmark/runner.py` | truyền luật từ spec xuống từng run |
| `apps/api/planbench_api/{services,routers/benchmarks}.py` | `POST /benchmarks` nhận `replanning` |
| `apps/api/planbench_api/report_markdown.py` | dòng Conditions + cột Replans |
| `apps/web/src/lib/{types,benchmarkTypes}.ts` | `replan_count`, `replanning`, 2 field fairness |
| `scripts/calibrate_difficulty.py` | `--max-replans`, ép version riêng |
| `tests/test_replanning.py` | **mới** — 25 test |
| `docs/{API_CONTRACT,IMPLEMENTATION_STATUS,KNOWN_LIMITATIONS}.md` | contract + giới hạn #152–#157 |

## 5. Test — `tests/test_replanning.py`

Đối chiếu danh sách "Test bắt buộc" của plan 4.1:

| Plan yêu cầu | Test |
|---|---|
| Replanning off → robot STUCK | `test_blocked_route_ends_stuck_without_replanning` |
| Replanning on → robot có thể SUCCESS | `test_same_scenario_reaches_the_goal_with_replanning` |
| Stuck window được reset | `test_resume_does_not_immediately_re_derive_stuck` |
| Cùng config khác thuật toán → checksum giống | `test_two_algorithms_under_one_rule_share_a_checksum`, `test_the_rule_lives_on_the_spec_not_on_an_algorithm` |
| Đổi replanning config → checksum khác | `test_changing_the_rule_changes_the_checksum` |
| DWA reset an toàn | `test_dwa_forgets_the_old_path_and_the_old_command` |
| PPO reset an toàn | `test_ppo_forgets_the_old_path` (skip khi không có SB3) |
| RRT\* replanning hợp lệ | `test_rrtstar_replans_onto_a_valid_path` |

Thêm ngoài danh sách:

- **Ngân sách là trần cứng.** `CountingPlanner` luôn trả về một đường vô
  dụng (robot đứng nguyên chỗ) nên chỉ có ngân sách mới kết thúc được
  episode: với `max_replans` = 1/2/3, số lần gọi `plan()` phải đúng bằng
  `budget + 1` và `replan_count == budget`. Test premise chứng minh
  trường hợp hồi phục được; test này chứng minh trường hợp không hồi
  phục vẫn dừng.
- **Tắt = y hệt trước đây**: cùng status, **cùng trajectory**.
- **Checksum cũ không đổi**: `build(...)` không truyền replanning và
  truyền `NO_REPLANNING` cho cùng một checksum.
- **Spec cũ vẫn deserialize** (`model_validate` payload không có field).
- Engine từ chối resume khi episode chưa kết thúc, và khi kết thúc bằng
  `COLLISION`.
- `enabled=True, max_replans=0` và `max_replans=-1` bị từ chối.
- Event `replan` có mặt, event `stuck` không còn.
- Chi phí lập đường cộng dồn (`expanded_nodes` của run có replan > run
  không replan).

Bản đồ dùng cho test premise: phòng chia đôi bằng tường có **hai** cửa;
đường ngắn đi qua cửa dưới, một xe đẩy (`sudden_stop`, bán kính 1.8 m)
lăn vào và đỗ hẳn ở cửa dưới tại t = 5 s, trong khi robot cần ~8 s để
tới nơi — nên nó luôn gặp xe **đã đỗ**, không phụ thuộc may rủi về thời
điểm. Cửa trên vẫn thông; chỉ planner biết xe đang ở đâu mới tìm ra.

## 6. Kiểm chứng

### 6.1. Backend

```text
tests/test_replanning.py                      24 passed, 1 skipped (PPO optional)
tests/test_nav_stack.py + test_engine.py
  + test_metrics.py + test_benchmark_engine.py
  + test_difficulty.py + test_scenario_protocol.py
  + test_observation_class.py                190 passed
tests/api                                    441 passed, 1 skipped
ruff format + ruff check                     sạch
```

Full suite: xem mục 6.4.

### 6.2. Frontend

```text
npm run typecheck    sạch
npm run build        Compiled successfully
npm test             443 passed / 1 failed + 1 suite fail — CẢ HAI PRE-EXISTING
```

Hai failure y hệt đã ghi ở report Đợt 3.2, không liên quan đợt này
(không file nào trong diff chạm tới chúng):

1. `assistant-page.test.tsx` — đọc `src/app/models/page.tsx`, file không
   tồn tại trên nhánh (artifact của merge `integrate-tongduyan`).
2. `dashboard-page.test.tsx` — so path cứng `"/system/page.tsx"` với
   path Windows `"\system\page.tsx"`. Bug separator của test.

### 6.3. Script hiệu chuẩn

```text
$ python scripts/calibrate_difficulty.py --max-replans 2 --scenarios open_space --dry-run
error: --max-replans changes what difficulty means, so it needs its own
       --calibration-version (the default belongs to the no-replanning scale)

$ python scripts/calibrate_difficulty.py --max-replans 2 \
      --calibration-version 2.0.0-replan --scenarios open_space,doorway --dry-run
baseline astar+dwa  seeds 3  scenarios 2  git 462d2cd4628d
  open_space   difficulty=0.000 success=1.000 (6.2s)
  doorway      difficulty=0.000 success=1.000 (6.1s)
```

Cache thật **chưa** được ghi lại với replanning — thang đo hiện hành vẫn
là thang không-replanning (KNOWN_LIMITATIONS #157).

### 6.4. Full suite

```text
python -m pytest tests/ -q --ignore=tests/api    971 passed, 4 skipped in 180s
python -m pytest tests/api -q                    441 passed, 1 skipped in 724s
                                       tổng:    1412 passed, 5 skipped
```

Baseline sau Đợt 3.2 là `1388 passed, 4 skipped`. Chênh đúng **+24**, là
số test mới của `test_replanning.py`; skip 4 → 5 là test PPO mới (torch
optional, không cài trong môi trường này). **Không có fail mới.**

## 7. Definition of Done của plan 4.1 — đối chiếu

Plan 4.1 không có checklist DoD riêng; đối chiếu theo mục "Điều kiện
công bằng" và "Test bắt buộc":

- [x] Replanning đặt trong stack chung (`run_stack`), không đặt riêng trong DWA.
- [x] Cùng luật trigger cho mọi thuật toán (trigger không cấu hình được).
- [x] Cấu hình replanning nằm trong benchmark conditions (`FairnessRecord` + checksum).
- [x] Cùng scenario + cùng replanning config → cùng checksum.
- [x] Không tune replanning riêng cho một thuật toán (luật ở spec, không ở `AlgorithmSpec.config`).
- [x] Replan lấy vị trí obstacle động hiện tại, rasterize vào grid tạm (không replan ngây thơ).
- [x] Stuck window được reset, không chỉ đổi state.
- [x] Toàn bộ test bắt buộc pass.
- [x] Khi replanning bật, calibration phải tạo version mới; không ghi đè cache cũ.
- [x] Không thêm field vào `Scenario`, không đổi checksum benchmark cũ.

## 8. Rủi ro còn lại

| Rủi ro | Ghi chú |
|---|---|
| Trigger chỉ chạy sau khi đã STUCK — robot mất trọn `stuck_time_window` (5 s) mỗi lần bị chặn | Chủ ý; trigger sớm là một tham số và phải vào vòng tune P01. KNOWN_LIMITATIONS #152 |
| Ép ô robot về FREE là một biên an toàn bị nới | Chỉ 1 ô, và chỉ khi engine đã chứng minh robot không va chạm. #153 |
| `replan_count` chưa lên aggregate/leaderboard | Cùng lý do hoãn như #146 — đổi overall score cần review riêng. #154 |
| `path_efficiency` của run có replan không so trực tiếp được với run không replan | Cấu hình nằm trong checksum nên trong cùng một so sánh mọi stack cùng luật. #155 |
| Chưa có UI bật replanning | Chỉ bật được qua API/script. #156 |
| Cache difficulty hiện tại đo với replanning tắt | Bật là thang khác, bắt buộc version mới. #157 |
