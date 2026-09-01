# Kế hoạch chuyển hướng: PlanBench → Planner Selector

> **Ngày lập:** 2026-08-08 · **Người lập:** An (cùng Claude)
> **Nguồn:** `docs/antongduy/de-tai-moi-planner-selector.md` + `docs/antongduy/CONTRACTS_1.md` (contracts v1.0.0)
> **Trạng thái:** chờ team approve.
> **Quyết định đã chốt với An trước khi viết:**
> ① **Retrofit** trên repo hiện tại, không build lại (phân tích ở mục 1).
> ② **Giữ bố cục repo hiện tại** (`packages/ services/ apps/`), sửa CONTRACTS §16 thành bảng map logical→physical (PATCH).
> ③ **Trace theo Parquet** đúng HĐ-5, thêm `pyarrow`.
> ④ Quỹ thời gian **~4 tuần** → tới MVP demo đầu-cuối + một phần sensitivity.
> ⑤ **Không có bo mạch đích** → sim-only, `realtime_gate.status` luôn `screened_on_host`, Target Verifier ra khỏi scope.

---

## 1. Vì sao retrofit, không build lại

### 1.1. Đề tài mới tự thiết kế như phần mở rộng

- §8 đề tài mới: *"Bốn interface giữ nguyên không sửa một dòng. Thêm bốn tầng, tất cả nằm **sau** Metrics Engine"* — tầng mới chỉ ăn output của tầng đo, không đụng sim core.
- §0: *"Không có gì trong tài liệu cũ bị vứt đi — gần một nửa đổi vai trò."*
- RBAC + Approval (F10/F11) giữ nguyên vai chốt an toàn; Trajectory Viewer giữ nguyên xuống vai "xem bằng chứng".

### 1.2. Bảng tái dùng — tài sản hiện có khớp hợp đồng mới

| Hợp đồng mới | Hiện trạng repo | Tái dùng |
|---|---|---|
| HĐ-4 interfaces | `common/base.py`, `common/local_base.py`, sim core (`engine`, `kinematics`, `lidar`, `collision`, `grid`, `nav_stack`, `episode_runner`) | ~100% |
| HĐ-1 candidate | A\*, RRT\*, DWA, PPO; khái niệm stack = global+local đã đúng (D13); PPO là mẫu `monolithic` | ~80% — thiếu `candidate_id` hash |
| HĐ-3 ghép cặp | `runner.py` đã chạy cùng seed list cho mọi algorithm, seed điều khiển cả vật cản động lẫn planner ngẫu nhiên | ~70% — thiếu `episode_context_id` chính thức |
| HĐ-6 metrics | `episode_metrics.py`: clearance, near_miss, p50/95/99 latency, smoothness², stop_and_go, replan_count | ~70% — thiếu `L_ref`, `time_efficiency`, `peak_rss_mb`, `cpu_time` |
| HĐ-11 thống kê | `statistics.py`: `bootstrap_ci`, `wilcoxon_compare`, `cliffs_delta` (SciPy, có input guard) | ~50% — thiếu paired bootstrap trên ΔU |
| G6 quan sát | P02 `observation_class` (đợt 1.1 cũ) | đổi vai trực tiếp thành `observation_requirements` |
| `instance_difficulty` | P03 difficulty calibration (đợt 2.2 cũ) | đổi vai trực tiếp |
| HĐ-14 RBAC/Approval | F10/F11 chạy thật, chống tự duyệt, audit log append-only | ~100% |
| Hạ tầng | Docker compose đã chạy thật, SQLite/Postgres + Alembic, OAuth, Next.js + recharts, ~1.190 test xanh | ~100% |

### 1.3. Chi phí hai phương án

- **Build lại:** đốt 3–4 tuần chỉ để về lại vạch hiện tại (~24k LOC Python + ~31k LOC TS + 1.190 test + RBAC/DB/UI/Docker) trong quỹ 4 tuần → không còn thời gian cho chính tầng decision, là toàn bộ tính mới của đề tài. **Loại.**
- **Retrofit:** tầng decision là pure Python mỏng đứng sau Metrics Engine; lát cắt dọc ~1,5 tuần; MVP Decision Card ~3 tuần; tuần 4 làm UI + sensitivity + demo.
- Ma sát thật của retrofit, đều bounded: (a) bố cục repo ≠ §16 → đã chốt sửa contract; (b) trace JSON → Parquet, ~2–3 ngày; (c) map `AlgorithmSpec/BenchmarkSpec` → `Candidate/TaskProfile`, additive; (d) map loader PGM/YAML chưa có — phải làm dù build lại hay không.

### 1.4. Số phận các phần vừa làm xong (đợt 0–4 + A–B của plan cũ)

| Phần cũ | Số phận theo đề mới |
|---|---|
| RRT\* (0.1) | Giữ nguyên — candidate thứ 3 |
| P02 observation_class (1.1) | Đổi vai → nguồn của G6, gần như miễn phí |
| P04 statistics (1.2) | Giữ làm nền; bổ sung paired bootstrap ΔU |
| P05 held-out + generalization (2.1) | **Đóng băng, không xóa** — đề mới thay vai bằng Task Neighborhood (pha 2). Không port, không quảng bá trên UI mới |
| P03 difficulty (2.2) | Thu hẹp → `instance_difficulty` (cảnh báo + chọn số episode) |
| Scenario Editor (2.3) | Giữ — công cụ tạo map/mission cho TaskProfile |
| F09 charts + export (3.1) | Giữ recharts; Decision Card cần waterfall + Pareto mới |
| F05 metrics fix (3.2) | Giữ — nền của HĐ-6 |
| Replanning (4.1, A, B) | Giữ nguyên — thuộc tính của candidate stack, đi vào params hash |
| Model Registry, Chat, OAuth | Đóng băng, không đụng |
| Leaderboard | Giữ chạy, không còn là màn hình chính; màn hình chính mới là Decision Card |

**Lưu ý xung đột ngữ nghĩa phải xử lý tường minh:** `path_efficiency` hiện tại = planned/actual (đo độ bám đường). HĐ-6 định nghĩa `path_efficiency = L_ref/path_length` (đo độ tối ưu so với Dijkstra). Hai metric khác nhau cùng tên. Quyết định: tầng decision **chỉ** đọc `metrics/definitions.py` mới (đúng contract); metric cũ giữ nguyên cho UI cũ, docstring ghi rõ khác biệt. Không đổi tên field cũ để không vỡ report đã lưu.

---

## 2. Bố cục vật lý (đã chốt giữ layout hiện tại)

Bảng map logical (CONTRACTS §16) → physical, sẽ ghi thẳng vào CONTRACTS khi sửa:

| CONTRACTS §16 | Vị trí thật |
|---|---|
| `contracts/` | `contracts/` (mới, ở gốc repo): `CONTRACTS.md` (move từ `docs/antongduy/CONTRACTS_1.md`), `schemas/*.json`, `metric_anchors.yaml` |
| `sim/` | `services/simulator/planbench_simulator/` |
| `planners/` | `packages/planning/planbench_planning/` (+ `ml/planbench_rl` cho policy) |
| `metrics/` | `packages/metrics/planbench_metrics/` — thêm `definitions.py` |
| `decision/` | `packages/decision/planbench_decision/` (**package mới**) |
| `runner/` | `packages/benchmark/planbench_benchmark/` — thêm `contexts.py` |
| `api/` | `apps/api/planbench_api/` |
| `web/` | `apps/web/` |
| `runs/` | `artifacts/runs/` (trace parquet · manifest.json · decision_card.json) |

---

## 3. Roadmap 4 tuần

### Đợt 0 — Hợp đồng + nền móng schema (tuần 1, ~3 ngày)

Bốn thứ đề bài bắt phải có trong schema từ đầu: `hardware_spec`, `deployment_horizon`, `candidate_id`, `metric_anchors.yaml` có version.

**0.1. Chốt hợp đồng (0,5 ngày)**
- Tạo `contracts/`, move `CONTRACTS_1.md` → `contracts/CONTRACTS.md`.
- Sửa §16: bảng map ở mục 2 trên; bump `contracts_version` 1.0.0 → 1.0.1 (PATCH — chỉ map vị trí, không đổi ngữ nghĩa).
- Ghi bảo lưu sim-only: Target Verifier ngoài scope, mọi Decision Card in `screened_on_host`.
- Team ký mục 16.

**0.2. TaskProfile schema — HĐ-2 (1 ngày)**
- `packages/schemas/planbench_schemas/task_profile.py`: `TaskProfile`, `Mission`, `Constraints`, `HardwareSpec` đúng schema HĐ-2. Pydantic frozen, validator: `probability` tổng = 1; `claim_level` là computed property theo quy tắc 2.2 (hệ tính, không tin user).
- `robot.control_period` — kiểm tra `RobotConfig` hiện có; thiếu thì thêm field có default (MINOR không phá dữ liệu cũ).
- Test: claim_level tự hạ; từ chối profile thiếu hardware.

**0.3. Candidate + định danh — HĐ-1 (1 ngày)**
- `packages/decision/planbench_decision/candidate.py`: `Candidate` (`type: modular|monolithic`), loader từ chối `monolithic` có `global_planner`; `candidate_id = sha256_short(canonical_json(...))[:12]` đúng 1.3.
- Map từ registry hiện có: `astar+dwa` + config → Candidate; PPO checkpoint → `monolithic`.
- `experiment_scope` validation: `global_planner_selection` mà params local khác nhau → **fail lúc khởi động** (đúng "vi phạm trông như thế nào" HĐ-1.4).
- Test: hash ổn định qua thứ tự khóa; hai config khác nhau → hai id.

**0.4. Map loader `map_server` PGM/YAML (1 ngày)**
- `packages/schemas/planbench_schemas/map_io.py` mở rộng (file đã tồn tại — kiểm tra rồi thêm): đọc `.pgm` + `.yaml` (`resolution`, `origin`, `negate`, `occupied_thresh`) → `OccupancyGrid` hiện có. Thêm `PyYAML` (ghim version).
- Test: round-trip map mẫu; ngưỡng occupied đúng.

### Đợt 1 — Lát cắt dọc HĐ-15 (tuần 1–2, mốc cứng: **hết tuần 2**)

Mục tiêu nguyên văn: *1 bản đồ · 1 cặp start/goal · 1 robot · 2 candidate · 30–100 episode ghép cặp → trace → metrics → gates → 4 objective → decision_utility → CI của ΔU → Decision Card JSON.* Chưa cần web UI, Pareto, sensitivity, neighborhood.

**1.1. EpisodeContext — HĐ-3 (1 ngày)**
- `packages/benchmark/planbench_benchmark/contexts.py`: `EpisodeContext`, `episode_context_id` đúng 3.1; generator sinh danh sách context **trước**, vòng ngoài context – vòng trong candidate; field `sample_set: evaluation|neighborhood`.
- Tái dùng seeding hiện có của `run_single` (seed → scenario + planner). Assert mọi candidate cùng tập context — Decision Engine từ chối ΔU nếu lệch.

**1.2. TraceRecorder Parquet — HĐ-5 (2 ngày)**
- Thêm `pyarrow` (ghim version, cả `docker/requirements-api.txt`).
- `packages/benchmark/planbench_benchmark/trace.py`: recorder ghi đúng cột HĐ-5 (`t, x, y, theta, v, omega, clearance_m, planner_latency_ms, event`) + metadata (`episode_context_id`, `candidate_id`, `task_profile_id`, `sample_set`, `global_plan_length_m`, `global_plan_time_ms`, `peak_rss_mb`, `cpu_time_s`).
- `clearance_m` tính **trong lúc ghi** từng bước bằng `clearance_to_obstacles` sẵn có (hiện đang tính hậu kỳ trong metrics — chuyển vào bước ghi để trace tự đủ).
- `peak_rss_mb`: `psutil` (đã có trong deps? kiểm tra; thiếu thì thêm). `cpu_time_s`: `time.process_time`.
- Ghi vào `artifacts/runs/<run_id>/traces/<context_id>_<candidate_id>.parquet`.

**1.3. `metrics/definitions.py` — HĐ-6 (2 ngày)**
- Nơi **duy nhất** định nghĩa metric cho tầng decision; input duy nhất = trace Parquet + task_profile.
- Mới: `L_ref` (Dijkstra trên grid của chính context — tái dùng A\* core với heuristic 0 hoặc viết Dijkstra riêng ~50 dòng), `path_efficiency = L_ref/path_length` (ghi chú xung đột tên ở mục 1.4), `T_ideal = L_ref/v_max`, `time_efficiency`, `p99_latency_ms`, `success` theo `goal_tolerance_*` của TaskProfile.
- Test then chốt (tiêu chí HĐ-15 số 5): `L_ref ≤ path_length_m` ở **mọi** episode thành công.

**1.4. `packages/decision/` — gates, anchors, objectives, utility, stats (3 ngày)**
- `gates.py`: G1–G6, ngưỡng đọc từ TaskProfile, **không hardcode**. G2: `N_min = ceil(3/collision_probability_max)`; output kèm chuỗi bắt buộc *"0 va chạm quan sát trong {N} lần chạy; cận trên 95% dưới phân phối kịch bản đã mô phỏng: {3/N:.1%}"*. G4: `realtime_gate.status = screened_on_host` cố định (sim-only). CI test cấm chuỗi "an toàn"/"TCO" trong output (HĐ-7.1, danh sách cấm #10).
- `anchors.py`: load `contracts/metric_anchors.yaml`, resolve tham chiếu `${constraints.*}`/`${robot.*}`/`${hardware.*}`; validator **từ chối số cứng** ở `bad` của metric có cổng (luật 8.3.2); công thức `u()` duy nhất 8.1.
- `objectives.py`: U_R/U_S/U_E/U_C đúng 9.1, tính **theo từng episode** (HĐ-11.1); `measured_only` → β4=0 renormalize.
- `utility.py`: `decision_utility` (đúng tên biến), 4 preference profile 9.2; `travel_time_accounting` validator một-trong-hai (MVP chỉ làm `efficiency`; `monetized_cost` để pha sau nhưng validator chặn từ giờ).
- `stats.py`: paired bootstrap trên ΔU đúng 11.2 (resample theo context, 1000 lần, seed cố định — tái dùng pattern `BOOTSTRAP_SEED` có sẵn trong runner); nhãn `CLEAR_RECOMMENDATION`/`NEAR_EQUIVALENT`; tie-break đúng thứ tự 11.3.
- `decision_card.py` + `manifest.py`: JSON đúng HĐ-12/HĐ-13 (git_sha, docker digest khi có, anchor version, tập context id). `declared_assumptions: null` ở technical mode.

**1.5. CLI lát cắt dọc + nghiệm thu (1 ngày)**
- `scripts/vertical_slice.py`: 1 map (nạp bằng loader 0.4), 1 mission, 2 candidate (`astar+dwa` config A vs `rrtstar+dwa` config A — cùng local để minh hoạ `global_planner_selection`), 50 episode ghép cặp → in Decision Card JSON + manifest.
- **Nghiệm thu đúng 5 tiêu chí HĐ-15.1:** (1) assert cùng tập context; (2) chạy lại cùng manifest → cùng `decision_utility` tới 6 chữ số; (3) bảng gate đủ 6 cổng kèm số lần chạy; (4) ΔU + CI không NaN; (5) `L_ref ≤ path_length_m` mọi episode thành công.
- Sau mốc này **không quay lại sửa phương pháp luận** trừ khi lát cắt phát hiện giả định sai (HĐ-15.2).

### Đợt 2 — Decision Engine đầy đủ + API (tuần 3)

**2.1. Evaluation distribution + N_min thật (1 ngày)**
- Generator bộ `evaluation`: mission × hiện thực vật cản × seed, độc lập (HĐ-3.3); chạy `N ≥ N_min` (mặc định 300 với 1%) cho các candidate qua sàng — episode 2D nhanh, không cần racing (N9 đúng là pha 2).
- `instance_difficulty` từ P03 cache → chọn số episode + cảnh báo trên card.

**2.2. Pareto — HĐ-10 (1,5 ngày)**
- `pareto.py`: non-inferiority trên `LCB₉₅(ΔU_j)` ghép cặp, `ε = 0.02`; ba nhãn `PARETO_FRONTIER`/`LIKELY_DOMINATED`/`UNCERTAIN_DOMINANCE`; **gắn nhãn, không xóa**; test bắt buộc: không dữ liệu → không kết luận (bài kiểm tra HĐ-10.2).
- `alternative` trên Decision Card chỉ lấy từ `PARETO_FRONTIER`.

**2.3. API (2 ngày)**
- Router mới `apps/api/planbench_api/routers/decisions.py` (+ task_profiles, candidates):
  - `POST /task-profiles`, `GET /task-profiles/{id}` — CRUD tối thiểu, lưu qua repository pattern sẵn có.
  - `POST /candidates` — đăng ký candidate, trả `candidate_id`; khai `tuning_trials_used`/`tuning_wall_clock_h` kèm bằng chứng log (N7 mức MVP).
  - `POST /decisions` — chạy selection qua worker sẵn có (background job như benchmark hiện tại); `GET /decisions/{id}` → Decision Card + gate report.
  - Nối Approval hiện có (HĐ-14): card `APPROVED` mới cho `GET /decisions/{id}/approved_config.yaml`. Tái dùng chống-tự-duyệt.
- Alembic migration: bảng `task_profiles`, `candidates`, `decision_cards` (URI + checksum theo D15 — file lớn nằm ở `artifacts/runs/`).

**2.4. Sensitivity mức MVP (1,5 ngày)** — *(kéo từ tuần 5 roadmap gốc lên vì là "tính năng quan trọng nhất" N1; anchor sensitivity ±10% rẻ nên làm cùng)*
- `sensitivity.py`: `weight_stability_margin` (quét trọng số quanh profile, tìm biên lật); `anchor_stability` (xê dịch anchor ±10%, khuyến nghị đổi? — chạy lại pipeline utility trên metric đã có, không chạy lại sim nên nhanh).
- Ngưỡng cảnh báo đúng HĐ-11.5.

### Đợt 3 — UI Decision Card + demo (tuần 4)

**3.1. Trang `/decisions` (3 ngày)**
- Decision Card làm màn hình chính: tên candidate lớn + nhãn CLEAR/NEAR-EQUIVALENT + scope (`MISSION_LEVEL`, `experiment_scope`, `decision_mode`, `screened_on_host` label) + phương án thay thế + khối evidence (ΔU, CI, n_episodes, effect size, weight margin, anchor stability).
- Bảng cổng: ai bị loại ở cổng nào, kèm số lần chạy — dữ liệu demo đắt giá (K4 nhanh nhất vẫn bị loại).
- Waterfall phân rã `decision_utility` (recharts đã có) + thanh trượt trọng số re-rank client-side (API trả per-episode objectives nên client tính lại U tức thời).
- Form tạo TaskProfile (tái dùng Scenario Editor cho map/mission) + form đăng ký candidate.
- Approval trên card → xuất `approved_config.yaml`.

**3.2. Nghiệm thu + demo + báo cáo (2 ngày)**
- Dựng ví dụ 4 candidate K1–K4 đúng §6.2 đề tài (A\*+DWA default, A\*+DWA tuned, RRT\*+DWA, PPO) trên map warehouse; demo hai chân trời 50.000 vs 200 nhiệm vụ lật khuyến nghị *(cần `business_adjusted` tối thiểu cho engineering cost khấu hao — nếu không kịp, demo bằng `technical` + `tuning_wall_clock_h` anchor, vẫn lật được)*.
- Rà toàn bộ chuỗi UI/báo cáo bằng bảng ngôn ngữ 9.2 (có test chuỗi cấm).
- Manifest nghiệm thu HĐ-13: người khác dựng lại cùng Decision Card từ manifest.
- Cập nhật README + báo cáo cuối.

### Ngoài scope 4 tuần (pha 2, đúng thứ tự cắt của đề)

Mission distribution L2 (schema đã sẵn, chỉ thiếu MissionSampler) → Adaptive Scheduler/racing (N9 — chưa cần, episode 2D rẻ) → Task Neighborhood K=20 (N5) → Target Verifier (không có board) → `monetized_cost` đầy đủ + What-if Panel → `trials_to_90`.

---

## 4. Phụ thuộc và rủi ro

```
0.1 contract ──┬─ 0.2 TaskProfile ──┬─ 1.1 contexts ── 1.2 trace ── 1.3 definitions ── 1.4 decision ── 1.5 slice
               ├─ 0.3 Candidate ────┘                                                      │
               └─ 0.4 map loader ──────────────────────────────────────────────────────────┤
                                                        2.1 eval-dist ── 2.2 pareto ── 2.3 API ── 2.4 sensitivity ── 3.x UI/demo
```

| Rủi ro | Giảm thiểu |
|---|---|
| Lát cắt dọc trượt mốc tuần 2 | Đợt 0 giữ tối giản; 1.4 có thể chạy trước bằng trace giả lập trong test song song với 1.2 |
| Trace Parquet đổi hành vi episode_runner làm vỡ test cũ | Recorder là lớp bọc thêm, không sửa engine; test cũ giữ nguyên đường JSON hiện có |
| Xung đột tên `path_efficiency` gây nhầm khi review | Ghi chú trong cả hai module + báo cáo; decision layer chỉ import từ `definitions.py` |
| Nhánh team khác merge conflict | Toàn bộ code mới nằm ở package/route mới; điểm chạm duy nhất: `RobotConfig.control_period`, requirements |
| Demo lật khuyến nghị theo horizon không kịp business mode | Fallback ghi rõ ở 3.2 |

## 5. Định nghĩa "xong" mỗi PR (theo HĐ-15.3)

Test cho logic mới · không metric ngoài `definitions.py` · không hardcode ngưỡng thuộc TaskProfile · đụng hợp đồng thì bump `contracts_version` cùng PR · chuỗi cấm ("an toàn", "TCO") có test CI.
