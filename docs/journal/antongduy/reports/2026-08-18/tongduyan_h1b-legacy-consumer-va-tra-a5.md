# H1b — legacy consumer đầu tiên của SDK, và món nợ A5 trả xong

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §8 H1b
**Trạng thái:** xong, 47 test mới xanh, lát cắt liền kề 134 passed, **full
suite CHƯA chạy** (theo lệnh An), **chưa commit**.

---

## 1. Đã tạo

### (a) `packages/benchmark/planbench_benchmark/policies.py` — **trả A5**

Registry policy khoá theo `PolicyComponent.name`, mảnh cuối cùng của con
đường monolithic (adapter + `run_policy` đã có từ 6.6.0, note 13-08):

- `PolicyEntry` (name, description, `reference` flag D12,
  `requires_checkpoint`, builder) + `register_policy` — trùng tên fail
  loud, cùng lý lẽ `ManifestIndex`.
- **Luật checkpoint hai nhánh:** policy không trọng số phải khai
  `checkpoint="builtin"` — giá trị khác bị từ chối vì checkpoint nằm
  trong `candidate_id`, nhận bừa sẽ đúc nhiều id cho một cấu hình không
  thể khác nhau. Policy có trọng số đòi `resolve_checkpoint` callable —
  layering y như `_build_ppo`: tầng này chỉ biết file, model_registry
  của API là người phân giải.
- Đăng ký `greedy_reference_policy` (reference D12, không trọng số) để
  con đường declare → build → `run_policy` là thật chứ không phải hứa.

### (b) `packages/benchmark/planbench_benchmark/legacy_plugins.py`

`synthetic_manifests()` — **dẫn xuất từ registry mỗi lần gọi, không lưu
tay** (bài học fingerprint áp cho metadata): stack withdrawn hoặc
reference tự động không có manifest. Một manifest **mỗi component**
(astar, rrtstar — global; dwa, ppo — local; greedy_reference_policy —
monolithic), vì contract §5.5 là ba role, còn *pairing* vẫn thuộc quyền
registry.

`LegacyPluginLoader`: parse mọi synthetic manifest qua đúng SDK parser
(H1a), rồi **delegate hết** về factory cũ — `build_global_planner`,
`build_local_planner`, `candidate_from_stack`, `build_policy`. Không
re-derive identity, không loop mới.

### (c) Cập nhật lời từ chối `stack_id_for`

Message cũ nói policy registry "does not exist yet" — giờ thành nói dối.
Đổi thành redirect sang `build_policy`; test tương ứng trong
`test_candidate_bridge.py` đổi match `MonolithicPolicy` → `build_policy`.
Đây chính là hàng rào 13-08 "sẽ đỏ đúng ngày loader được thêm" — nó đã
đỏ đúng ngày, sửa có chủ đích.

## 2. DoD H1b đối chiếu — mỗi dòng một test

| DoD | Test ghim |
|---|---|
| Synthetic manifest A*, RRT*, DWA resolve về đúng factory | `build_global("astar"/"rrtstar")`, `build_local("dwa", dwa_balanced)` trả đúng planner name; mọi manifest parse qua SDK parser |
| PPO đi đúng lazy checkpoint/model-registry path | thiếu model → "no PPO model was chosen"; build controller khi thiếu RL deps → "dependencies are not installed" (skipif khi máy có sb3) |
| Monolithic loader, chạy qua `run_policy` — **A5** | `Candidate(type="monolithic")` build ra `GreedyReferencePolicy`, chạy episode doorway qua loop chung: `run.algorithm == "greedy_reference_policy"` (tên một lớp, không "none+"), `plan.success` với path rỗng, 0s planning — đúng ba tính chất HĐ-1.2 |
| Candidate ID không đổi | đường manifest == đường trực tiếp; và == **bytes từ H0 fixture đã commit** (`3b18dfbfa9e7` cho astar+dwa) — chỉ git làm chứng được "không đổi qua commit" |
| Unknown config fail như cũ | `sim_time` → `UnknownParameterError`; `horizon_seconds=-1` → `AlgorithmConfigError` |
| Chưa cần AlgorithmHost per-tick | không file host nào; loader chỉ resolve và delegate |

Ghim thêm:

- **Exact set** component: `["astar", "dwa", "greedy_reference_policy",
  "ppo", "rrtstar"]` — thêm component mà không quyết định là test đỏ
  (guard style đã bắt lỗi hai lần ở phiên P6).
- `dwa_predictive` và `pure_pursuit` **không** có manifest — registry từ
  chối thì manifest không được chào.
- Hai component hợp lệ không suy ra một stack: `rrtstar+ppo` bị relay
  đúng lời từ chối registry.
- Luật checkpoint: unknown policy liệt kê known; checkpoint bịa cho
  policy không trọng số bị từ chối; policy có trọng số không resolver bị
  từ chối, có resolver thì builder nhận **đúng path đã phân giải** (test
  double, có cleanup khỏi registry toàn cục để không rò sang loader
  khác trong session).

## 3. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/test_legacy_plugins.py` (mới, 21 test) | passed |
| Lát cắt: legacy_plugins + candidate_bridge + plugin_sdk + candidate_identity + benchmark_engine | **134 passed, 1 skipped**, 29s |
| `ruff check` + `format` các file chạm | sạch |
| Full backend suite | **CHƯA CHẠY — theo lệnh An** |

## 4. Cho gate sau H1b

- `H1_ideal` = 2.5–3 ngày (prereg đã commit).
- `H1_actual` ≈ **1 ngày kỹ thuật** (H1a + H1b cùng ngày 18-08).
- `schedule_factor` ≈ 0.33–0.4 ⇒ `projected_remaining` ≈ 3.3–5.2 ngày
  trên ideal(H2..H8) 10–13 — **dưới trần 3 tuần rất xa**.
- Điều kiện 2 của gate: An đã khai "host là deliverable chiến lược: Có".
- Điều kiện 3: `robustness_margin` **trên critical path** (An xác nhận
  trong prereg) — đây là điều kiện duy nhất không tự thoả. Gate là quyết
  định của An, không phải của report này.

## 5. Còn treo

1. Full suite trước khi commit — chờ lệnh.
2. PPO runtime golden (nợ từ H0, cần máy có RL extras).
3. Gate: An điền mục 5 của prereg (`H1_actual`, verdict) rồi quyết
   H2–H8 hay dừng-sạch.
