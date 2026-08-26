# Báo cáo thi hành — Cải thiện hiệu quả AI Analyst (plan bản 6)

**Plan:** `plans/2026-08-26/de-xuat-cai-thien-hieu-qua-ai-analyst.md` bản 6
(An duyệt 2026-08-26).
**Nền:** bản 8 + bản 9 đã ship — report
`reports/2026-08-26/tongduyan_ai-analyst-ban-8.md`.
**Nhánh:** `tongduyan_ai-analyst-ban-8`, worktree `../P-011-analyst`.
**Quy ước:** một file cho cả plan; mỗi phase một mục, viết ngay sau khi commit
phase đó. Không chạy full suite cho tới khi xong plan — chỉ suite chạm tới.

| Phase | Trạng thái | Commit |
|---|---|---|
| W0 nền đánh giá + preregistration | **xong** | `8299a61` |
| W1.0 ToolHost thật vào InProcessHost | **xong** | `73be097` |
| W1.1 handler measurements | **xong** | `35c73b7` |
| W1.2 handler timeline | **xong** | `81030a4` |
| W1.3 timeline vào packet runtime | **xong** | `23aba5c` |
| W1.4 reader traits | **xong** | `e0de7f8` |
| W1.5 retrieval opt-in | **xong** | `dbedbaf` |
| W1.6 cơ chế duyệt traits | **xong** (chờ người duyệt) | `3375b13` |
| W1.7 feature flags | **xong** | `bd8f752` |
| W1.8 snapshot bộ ba | **xong** | `6df43a4` |
| B1 baseline real-host | **chặn** — cần ngân sách model | |
| E1–E3 input ablation | **chặn** — sau B1 | |
| W2 hybrid candidate generator | **xong** | `077319d` |
| W3 tool routing | **xong** | `66f327f` |
| W4 discriminated union + repair | **xong** | `30ecd57` |
| E4–E7 | chưa | |
| W5 | chưa | |
| E8–E10, freeze, confirmatory | chưa | |

---

## W0 — Nền đánh giá trước khi tối ưu

### Đã làm gì

**1. Nhãn tách khỏi fixture, sống phía scorer** (W0.1, W0.7)

- `services/analyst_service/planbench_analyst/eval_spec.py` (mới):
  `CaseLabels` (expected mechanism / subject / `acceptable_refs` any-of /
  `acceptable_tools` / `expect_abstention` / **`expected_check_required`** /
  wording ceiling / rationale), `RefPredicate` (`subject` | `ref_prefix` |
  `scope_prefix`, khớp qua fact index của `PacketView`), `EvalSpec` với
  `.checksum` hash **canonical content** (đổi một nhãn là đổi checksum, không
  cần đụng version), `.strata` chốt từ `expected_check_required`,
  `refs_satisfy`, `assert_no_label_in`, `load_eval_spec` — **từ chối**
  `partition != development`.
- `fixtures/golden/labels/visible.json` (mới): 3 nhãn cho 3 fixture; checksum
  `cd06d54a…c029cc`. Strata: check_required = (inflation-001, rrt-001),
  no_check = (dwa-001).

**2. Fixture đủ dữ liệu cho họ cần checker** (W0.3)

`scripts/build_golden_fixtures.py` viết lại: chạy **cả hai stack** qua
`EpisodeTraceRecorder` thật (`evidence_class="reference"`), đọc parquet lại
để lấy `clearance_m` / `planner_latency_ms`; tính `inflation_margin` từ
`_hard_radius − radius`, `required_passage_width = 2·(radius+margin)`, đo
route bằng `measure_route(..., sample_spacing_m = resolution/2)`. Packet giờ
mang `RobotFacts` + `route.narrowest_passage_m`. Ba fixture cài lại:

| Fixture | Observation | Ghi chú |
|---|---|---|
| inflation-001 | 2× `narrow_gap_refusal` | narrowest 0.25 m < required 0.66 m — quyết định tường minh, `gap_vs_footprint` có cái để đo |
| rrt-001 | `stuck_cluster` | corridor 0.55 m > required 0.50 m, RRT* từ chối ở budget |
| dwa-001 | `detour`, `near_miss_cluster`, `stuck_cluster` | `latency_spike` phụ thuộc wall-clock, có lúc có lúc không |

**3. Preregistration chốt trước B1** (W0.8)

`preregistration.py` (mới): dataclass frozen, checksum
`17354118…510a` **pin trong test**. Hard constraints (structural = 0,
budget/protocol = 1, menu_recall = 1); primary = case-level mechanism
correctness, McNemar exact ghép cặp, δ = 0.10, α = 0.05; 6 secondary theo
thứ tự hierarchical; `min_cases_for_pass_k = 12`; `repeats = 3`; trọng số
router `U = 1.0·q − 0.02·cost_k − 0.005·lat_s`; họ staged 3/6. Chi tiết:
`notes/2026-08-26/tongduyan_preregistration-va-phan-vung-du-lieu.md`.

**4. Harness: tin cậy có CI, cache là lỗi** (W0.5, W0.6)

`harness.py`: `wilson_interval` (không sập về 0 chiều rộng ở 0/n, n/n);
`quality_pass_hat_k(runs, min_cases)` trả `(rate|None, (held, cases), ci)` —
dưới ngưỡng **không** trả số; `HarnessReport.cache_hits` +
`measured_independently`; `compare_with_floor(..., cache=)` **raise** nếu có
cache hit.

**5. Nhãn và answer key không vào container** (W0.1 "labels phía scorer")

- `docker/Dockerfile.analyst`: không `COPY fixtures/`; thêm `RUN rm
  …/golden_fixtures.py` — `VISIBLE_SUITE` là code mang expected findings.
- `planbench_explanation/__init__.py`: bỏ import eager `VISIBLE_SUITE`, thay
  bằng `__getattr__` lazy — package không vỡ khi file bị gỡ, và mọi chỗ
  `from planbench_explanation import VISIBLE_SUITE` vẫn chạy (12 case).

**6. Rubric chấm tay packet thật** (W0.2)

`notes/2026-08-26/tongduyan_rubric-cham-tay-packet-that.md` — r0.1.0, 5 tiêu
chí rời rạc, mù cấu hình (xáo + mã S1..), anchor ghi trước khi đọc đầu ra,
`plausible_other` báo riêng, < 12 packet thì counts.

### Test

`tests/test_analyst_eval_spec.py` (mới, 19 test): nhãn load và phủ fixture;
stratum từ nhãn; citation khác-mà-đúng vẫn tính; nhãn rỗng không claim;
checksum đổi theo content không theo version; distractor knobs trong
checksum; **từ chối partition confirmatory**; view mọi fixture không mang
nhãn; Dockerfile không COPY fixtures, có `RUN rm golden_fixtures.py`;
`VISIBLE_SUITE` lazy; preregistration pin checksum; primary endpoint một số
một phép thử; `pass^k` dưới 12 case là counts; Wilson không sập biên.

Chạy: `test_analyst_eval_spec + test_analyst_harness +
test_analyst_service_wiring + test_explanation_e5 + test_explanation_e6` —
**197 passed**. Ruff sạch trên file mới/sửa.

### Nợ ghi lại

- `rrt-001`: packet không phơi bày tường minh việc `rrtstar` từ chối (chỉ
  thấy qua candidate metrics). Nhãn hiện dùng `fact:candidate:rrtstar+dwa`
  prefix; nếu W1.1 (`get_candidate_measurements`) đổi cách đặt ref thì nhãn
  đổi theo — và checksum eval spec đổi, đúng ý.
- `dwa-001`: `latency_spike` nondeterministic (latency đo wall-clock). Không
  đưa vào nhãn; nếu sau này có fixture cần nó thì detector phải nhận latency
  từ trace thay vì đo lúc build.
- 9/12 case trong `VISIBLE_SUITE` vẫn chưa có fixture — 3/6 họ, ghi trong
  `families_staged`.
- Chưa có holdout ⟹ **exploratory** cho mọi E-phase cho tới khi
  `OFFICIAL_GOLDEN_READY`.

### Ngoài phạm vi W0, để lại

- W1.0 bắt đầu ngay sau commit này: `MockToolHost` trong
  `round_host.InProcessHost` thay bằng `ToolHost` thật, evidence dựng từ
  `PacketArtifact` của fixture, giữ bất biến `RoundSource`
  (`evidence_identity_checksum` không đổi); đổi tên
  `round_host.EvidenceSource` → `RoundEvidence` để hết đụng tên với protocol
  `host.EvidenceSource`.

---

## W1.0 — `ToolHost` thật vào `InProcessHost`

### Đã làm gì

**1. Lane dev chạy host thật của platform.**

`round_host.InProcessHost` bọc `MockToolHost` (admission thật, execution
stub, mọi mechanism check trả `checker_not_implemented`). Đo trên đó chỉ đo
**analyst có xin verify hay không**, không đo xin thì có được gì — hai số
đang bị đọc thành một. Nay bọc `planbench_explanation.host.ToolHost`, có 4
checker thật phía sau; admission vẫn là `ToolSession` của host (một cách trả
lời "tool này được chạy không", không phải hai).

`replay_planner` là tham số, không import: `SimulatorReplayPlanner` nằm ở
`services/simulator`, mà `round_host` được COPY vào image analyst — import
thẳng là kéo cả simulator vào một image không thể cài nó.

Đổi tên `round_host.EvidenceSource` → `RoundEvidence` (đụng tên với protocol
`host.EvidenceSource`).

**2. Fact query không bị mất khi đổi host.**

`MockToolHost._serve` là chỗ duy nhất đọc packet cho 5 fact/navigation tool;
`ToolHost` trả `tool_unavailable` cho tất cả. Đổi host mà không chuyển phần
đọc thì một vòng vừa verify được mechanism vừa báo "known unknowns của chính
packet không có sẵn". Tách ra
`packages/explanation/planbench_explanation/packet_facts.py::serve_from_packet`,
**cả hai host cùng gọi**; khác nhau ở chữ ký: stub đóng dấu ref toàn số 0 và
`mock://`, host thật lưu qua sink và ký bằng build
(`platform_implementation_ref()` = hash nội dung code checker).

**3. Nguồn bằng chứng thật cho fixture.**

`ReportEvidence.from_packet(packet, sidecar_directory/-ies)`: route trong
`task.route` đăng ký cho mọi candidate dưới một region id
(`host.ROUTE_REGION_ID = "route"`), nên `gap_vs_footprint` có hình học để so
— đúng hình học analyst được xem. Fixture không có scoring report nên
`latency_vs_expanded_nodes` trả `not_checkable` (W1.1 sẽ đưa candidate
measurements vào packet, không phải bịa dòng ở đây).

**4. Sidecar theo từng candidate, và fixture giờ có sidecar.**

`ReportEvidence` nhận thêm `sidecar_directories: Mapping[candidate_id, Path]`.
Hai candidate của một world chạy **cùng điều kiện** nên chung
`episode_context_id` (id là hash của điều kiện) — một thư mục phẳng thì file
thứ hai đè tên file thứ nhất.

`build_golden_fixtures.py` giờ (a) dùng `episode_context_id` **thật** của
platform thay cho `"<case>:<candidate>"` tự chế — chuỗi cũ còn chứa `:`, không
đặt được tên file trên Windows; (b) bật `planning_recorder` khi `run_stack`,
ghi sidecar + snapshots vào
`fixtures/golden/visible/<case>/sidecar/<candidate>/`, đọc lại và validate
ngay lúc build.

**5. Seam công nhận bằng chứng sidecar.**

`TYPICAL_AVAILABLE_EVIDENCE` chưa bao giờ có `planning_inputs`,
`planner_parameters`, `planner_implementation_version`, `seed_set` ⟹
`rrt_convergence` và `replay_global_plan` **bị từ chối ngay ở admission trên
mọi run**, có sidecar hay không. Menu chào một check không ai với tới được,
và analyst đọc đó là "platform không có câu trả lời". Thêm
`round_host.SIDECAR_EVIDENCE`, cộng vào available set khi `sidecar_present`.

### Ba lỗi platform lộ ra khi chạy đường thật

1. **`ReportEvidence` mất hai method.** `replay_evidence` và
   `convergence_evidence` (host.py cũ, ~695–762) bị thụt vào **trong thân
   `_positive`** — code chết từ commit E6b `a87a9af`, không thuộc class nào.
   Chưa ai thấy vì `_replay`/`_convergence` return sớm khi `replay_planner is
   None`, và không test nào dựng `ToolHost` với planner thật. Đưa lại vào
   class.
2. **Hai từ vựng cho một refusal.** Checker raise `insufficient_seeds`, card
   khai `seed_set_too_small` ⟹ `session.record` ném `ProtocolRejection:
   unknown_failure_code` và **giết cả vòng**. Card là contract trên dây, nên
   đổi mã trong checker cho khớp card.
3. **Còn nhiều mã chưa khai.** `replay_did_not_reproduce`,
   `replay_inputs_mismatched`, `replay_harness_incomplete`,
   `seed_counted_twice`, `budget_parameter_not_recorded`, và các mã
   `ReplayUnavailable` đều **không** nằm trong `failure_modes` của hai card
   replay. `ToolHost._declared` giờ hạ mã lạ xuống `host_internal_error` (mã
   host hợp lệ) thay vì để cả analysis chết vì một chữ. Sửa gốc = card khai
   đủ + bump `TOOL_CATALOG_VERSION` — **đổi contract trên dây, để cùng đợt W3**.

### Test

`tests/test_analyst_real_host.py` (mới, 12 test):

- **Đường chính:** proposal → `gap_vs_footprint` thật → `supported`
  (0.25 m so với 0.66 m cần) → `promote()` ra claim. Đây là DoD smoke của W1.0.
- Result ký bằng build thật, artifact không phải `mock://`.
- Region packet không mang ⟹ `region_not_resolved`, không đo bừa.
- Fact query (`get_known_unknowns`) vẫn trả lời trên host thật.
- Request và host cùng một packet; packet khác ⟹ `EvidenceMismatch` lúc dựng.
- Có sidecar ⟹ `rrt_convergence` **được nhận** và checker từ chối bằng lý do
  của chính nó (`seed_set_too_small`: 1 episode = 1 seed); không sidecar ⟹
  không được chào.
- Mỗi candidate đọc sidecar của mình; candidate không có thư mục ⟹ không có
  bằng chứng.
- **Replay dựng lại đúng câu trả lời**: `check_replay_global_plan` trên sidecar
  rrt-001 cho `supported`, `attempts_replayed == attempts_recorded`.
- Mã refusal card không khai ⟹ `host_internal_error`, vòng còn sống.

Chạy: 13 suite chạm tới (analyst real_host/runner/eval_spec/harness/bundle/
wiring/knowledge/identity + explanation e5/e6/e6b/contracts/promotion) —
**363 passed**. Thêm `test_explanation_gate` + `test_analyst_budget_artifact`
xanh.

**`tests/test_host_parity_golden.py` fail 5 test — có sẵn, không do W1.0.**
Đã `git stash` toàn bộ thay đổi và chạy lại: vẫn fail y hệt. Lệch chữ số cuối
của float (`…915` vs `…916`) giữa máy này và máy sinh fixture; không đụng gì
tới simulator/planning trong phase này.

### Nợ ghi lại

- `rrt_convergence` chưa verify được family của nó: cần ≥8 seed, fixture mới
  có 1 episode ⟹ 1 seed. Cần một planted run nhiều seed cho
  `rrt_sample_starvation`.
- Sidecar ghi `execution_environment_ref` = build lúc plant (`git:8299a61…`).
  Replay từ build khác sẽ `replay_did_not_reproduce` — đúng thiết kế, nhưng
  nghĩa là fixture phải rebuild khi muốn dùng replay ở build mới.
- `get_map_region_features` vẫn `tool_unavailable`: card đòi `samples_taken`,
  `RouteFeatures` không giữ số này. Thêm field là đổi schema packet.
- Card replay khai thiếu failure mode (điểm 3 ở trên) — W3.

---

## W1.1 — Handler `get_candidate_measurements`

### Đã làm gì

**Card đòi bằng chứng nó không đọc ⟹ không ai gọi được.**
`get_candidate_measurements` khai `required_evidence=("episode_decision_utility",)`
— viết trước khi M1 có block measurements. Mọi planted world là `GATE_ONLY`,
không xếp hạng ai, nên `evidence_for` gỡ token đó ⟹ tool bị từ chối ngay ở
admission trên **mọi** packet có measurements mà không có ranking. Block nằm
trong packet, card nằm trên menu, giữa chúng không có đường.

- `catalog.py`: `required_evidence=("candidate_measurements",)`; token mới vào
  `TYPICAL_AVAILABLE_EVIDENCE`; `TOOL_CATALOG_VERSION` 3.2.0 → **3.3.0** (đổi
  luật admission = đổi wire contract; bundle freeze ở 3.2.0 đã được chấm trên
  một menu mà tool này không gọi được).
- `round_host.evidence_for`: gỡ `candidate_measurements` khi
  `packet.measurements` rỗng — suy từ packet như mọi token khác.
- `packet_facts.serve_from_packet(card, packet, arguments)`: thêm tham số
  arguments và kiểu trả về thứ ba **`FactRefusal(code)`**. `None` = "platform
  không phục vụ tool này"; refusal = "hiểu câu hỏi, packet không trả lời được",
  và code phải là code **card tự khai** (session từ chối code lạ — E6b).
  - `candidate_not_in_packet`: lỗi của analyst, hỏi lại id khác có thể được.
  - `measurements_not_recorded`: lỗi của run, hỏi lại vô nghĩa.
- `n_episodes` lấy từ denominator nhỏ nhất trong các MeasuredValue, không bịa.
  Không trả `EvidenceReference` — card không khai kind nào, session sẽ từ chối.
- `scripts/build_golden_fixtures.py`: mỗi candidate có measurements thật đọc
  ngược từ trace trên đĩa (success_rate, collisions, path_length,
  latency p99/median, min_clearance), denominator = 1 và nói rõ.
  `decision_utility` vắng — không ai xếp hạng, số 0 sẽ đọc thành "được chấm 0".

### Test

`tests/test_analyst_measurements.py` (16 test): contract; hai refusal phân
biệt; thiếu argument không đoán; host thật ký bằng build, stub ký `mock://`,
cùng một câu trả lời; packet không measurements ⟹ từ chối ở admission.

Chạy: 10 suite chạm tới — **282 passed**.

**Commit:** `35c73b7`

---

## W1.2 — Handler `get_episode_timeline`

### Đã làm gì

Cùng một hình lỗi như W1.1: card đòi `("trace", "reference_line")` — thứ M2
**dựng ra** các điểm timeline **từ đó**, không phải thứ nó đọc. Run không có
sidecar thì seam gỡ `trace` ⟹ packet đang mang block vẫn bị trả lời
"unavailable".

- `catalog.py`: `required_evidence=("episode_timeline",)`; thêm argument
  **`candidate_id` (không bắt buộc)**; failure modes thêm
  `clock_not_recognised`, `candidate_required_for_episode`;
  `TOOL_CATALOG_VERSION` → **3.4.0**; `schemas/tools/*` sinh lại.
- `packet_facts._timeline`: clock là argument, sai clock thì **từ chối** chứ
  không tự chọn (hai clock là hai câu hỏi khác nhau). `episode_context_id` là
  hash của **điều kiện** nên hai candidate của một so sánh dùng chung — nếu cả
  hai đều có timeline mà không nói candidate nào thì từ chối, câu trả lời không
  nói của ai là câu trả lời về không ai.
- `packet_builder.timeline_from_trace(...)` tách ra từ `timelines_from_traces`
  để fixture builder (không có ΔU để chọn exemplar) đi cùng một phép tính.
- Fixture: timeline thật cho cả hai candidate, role gán theo dữ liệu
  (clearance thấp nhất → `safety_critical`, còn lại → `typical`); `Deployment`
  lấy từ world, `clearance_warning_m` mượn ngưỡng near-miss của detector và nói
  rõ vì sao (planted world không có task profile; `clearance_preference` là
  trọng số cost, không phải mét).

### Hai lỗi thật do chạy trên fixture thật mà ra

Fact index của analyst **từ chối ref trùng**, và trùng thì đổ cả view chứ không
chỉ một citation:

1. `packet_view` đặt ref timeline không có candidate ⟹ hai candidate cùng
   episode sinh hai fact cùng ref. Ref nay là
   `episode:<id>/<candidate>/<clock>/<mark>`.
2. Trace một hàng (planner từ chối ngay tại start pose) đẩy cả ba mark
   `at_time` về t=0 ⟹ ba bản sao của một khoảnh khắc. `timeline_from_trace` khử
   trùng theo `(clock, mark)`.

### Test

`tests/test_analyst_timeline.py` (16 test) + suite chạm tới — **391 passed**.

**Commit:** `81030a4`

---

## W1.3 — Timeline từ runtime/API vào packet, đo byte

### Đã làm gì

`build_scoring_packet` dựng timeline **chỉ khi** có `deployment`, mà
`_explanation_packet` trong `selection.py` chưa bao giờ truyền — nên guard
clause trả về sớm kèm một omission không ai đọc, và **mọi packet production
mang `timelines: []`** trong khi fixture mang đầy. Ablation đầu vào này lẽ ra
đo fixture với chính nó.

- `packet_builder.DeploymentThresholds`: bốn số **profile** khai (radius,
  control period, clearance warning, vmax). Số thứ năm — reference length —
  **không** ở đây: nó là chiều dài đường của **từng episode**, một số dùng
  chung cho cả run sẽ đọc robot đi được nửa bản đồ thành đã xong.
- `packet_builder.project_progress(trace)`: sinh `progress_m` bằng chính phép
  chiếu detector đang dùng, trả kèm chiều dài đường. Trace đã có `progress_m`
  thì trả nguyên — ai đó phía trên đã đo theo một đường mà hàm này không thấy.
- `timeline_from_trace` tự chiếu khi thiếu cột và ghi đè `reference_length_m`
  bằng đường của chính episode đó.
- `selection.py`: dựng `DeploymentThresholds` từ profile và truyền vào
  `build_scoring_packet(deployment_thresholds=...)`.
- `build_golden_fixtures.py` bỏ bản sao `_with_progress` của nó.

### Chi phí đo được (không ước lượng)

| Fixture | Packet đầy đủ | Bỏ timelines | Block timeline | ~token | Tỷ trọng |
|---|---|---|---|---|---|
| inflation-001 | 4 924 B | 3 158 B | 1 766 B | ~441 | 35.9% |
| rrt-001 | 5 099 B | 2 770 B | 2 329 B | ~582 | 45.7% |
| dwa-001 | 5 694 B | 3 306 B | 2 388 B | ~597 | 41.9% |
| **tổng** | 15 717 B | 9 234 B | **6 483 B** | ~1 620 | 41.2% |

Đây là con số E2 sẽ cân: gain của timeline phải bù ~1.6k token/3 packet. Test
chốt trần 4 kB cho hai episode để một hồi quy "mang cả trace" là test đỏ chứ
không phải hoá đơn prompt.

### Test

`tests/test_explanation_timeline_runtime.py` (9 test) + suite chạm tới
(297 passed) + `test_explanation_report_wiring` và `test_vertical_slice`
(23 passed, 2m46s).

**Commit:** `23aba5c`

---

## W1.4 - Reader `AlgorithmTraitRow -> TraitSource`

M3 dựng bảng `algorithm_traits` (migration 0012) và `traits_store` dựng hình
dạng; **không có gì nối hai cái**. Mọi reader vẫn lấy `SHIPPED_TRAITS` - hằng
số mà migration seed *từ đó* - nên một nature viết cho thuật toán import được
ghi vào bảng rồi không ai đọc. Bảng mà một nửa platform ghi còn nửa kia không
thấy tệ hơn không có bảng: nhìn ngoài tưởng tính năng đã có.

`apps/api/planbench_api/db/traits_repositories.py` (mới) -
`SqlTraitRepository.load()/get()/save()/seed()`:

- Trả về đúng `TraitSource` mà **cả hai lane** (advisory rules và analyst) đang
  nhận. Hai loader với hai bộ lọc là hai bảng, và bất đồng sẽ hiện ra đúng chỗ
  không ai nhìn - phần giải thích.
- Sắp theo `algorithm_id` chứ không theo thứ tự DB trả: W1.8 hash catalog này,
  và content hash mà thứ tự đầu vào đổi theo tâm trạng DB là checksum đổi vì lý
  do không ai gọi tên được.
- Row không parse được thì **từ chối cả load**, không bỏ qua. Bỏ qua sẽ đọc
  xuống dưới thành "không ai mô tả thuật toán này", câu dễ nghe hơn sự thật.
- `seed()` không đè row đã có - review là thứ duy nhất trong bảng do người làm
  bằng tay.

**Test:** `tests/api/test_trait_repository.py` (13) + `test_sql_repositories`
- 110 passed. **Commit:** `e0de7f8`

---

## W1.5 - Knowledge retrieval vào runner, opt-in

A5 dựng retriever, resolver và trait offers; runner **không gọi cái nào**. Hai
đầu vào tồn tại mà chưa vòng nào chạy với chúng.

- `run_round(..., features=..., traits=...)`: cả hai **mặc định tắt**. Đây là
  nửa quyết định ý nghĩa của phép đo - mặc định bật sẽ nhét thứ E1 định thêm
  vào chính baseline nó được đo lại.
- Transcript ghi `knowledge:<resolved>/<offered>`: "không có gì khớp" khác
  "khớp năm cái mà không cái nào resolve", chỉ một trong hai là lỗi retrieval.
- Offer được **index thành fact citable** trong packet view (`kb:<id>@<v>`),
  vì guard rule 1 drop ref view không resolve được - entry cho model xem mà
  không cho cite thì với model nó là kho bị cấm dùng.
- `review_status` nằm trong label chứ không dùng làm bộ lọc: được promotion hay
  không là câu trả lời của promotion matrix, không phải của retrieval.

**Test:** `tests/test_analyst_retrieval_round.py` (13) + suite analyst - 179
passed. **Commit:** `dbedbaf`

---

## W1.6 - Duyệt traits: anchor độc lập, khoá trước golden

**Đây là phase cần người duyệt - xem mục "Cần An quyết" cuối báo cáo.**

`packages/benchmark/planbench_benchmark/traits_review.py` (mới):

- `approve(entry, reviewed_by, at)` - từ chối nếu không có người ký, không có
  gì để duyệt, hoặc **anchor không độc lập**. Anchor lặp lại chính claim, viện
  "ai cũng biết", hoặc không trỏ ra ngoài row đều bị từ chối: row approved được
  quyền backing một claim đã promote, và folklore trong bảng đọc y hệt số đo.
- `lock_for_golden(source, promoting=True)` - còn row chưa duyệt thì **không
  chạy**. Duyệt một nature sau khi thấy nó giúp được case nào là chọn oracle từ
  kết quả, và không checksum nào phân biệt được việc đó với duyệt tử tế.
- `scripts/review_algorithm_traits.py` - `list` / `seed` / `approve <id> --by`.
  Cố tình **không có `--all`**: review làm được cho sáu row bằng một cờ là
  review sẽ được làm bằng một cờ.

**Luật bắt ngay row đầu tiên:** anchor của `dwa` trong `TRAITS` là
"velocity-sampling controller; horizon and weights are its whole world" - mô tả
thuật toán, không trỏ đi đâu, nên row đó **không bao giờ duyệt được**. Đã sửa
thành `planbench_planning.dwa: the rollout scoring loop, ...`.

**Test:** `tests/test_analyst_traits_review.py` (19) + outcome/traits suites -
82 passed. **Commit:** `3375b13`

---

## W1.7 - Feature flag từng đầu vào, vào `runtime_config_checksum`

`services/analyst_service/planbench_analyst/features.py` (mới) -
`RoundFeatures(measurements, timelines, knowledge, traits, filter_tool_menu,
auto_route_checker)`:

- Vào `runtime_config_checksum`. Bundle chấm với block timeline trong prompt
  rồi replay không có nó **không còn dùng chung một identity** - trước đây lần
  đọc thứ hai sẽ hiện ra như model variance.
- Bốn cờ đầu vào **độc lập**: E3 cần 2x2 đủ, cặp chỉ đổi cùng nhau là một arm
  đội hai tên. Test kiểm 16 tổ hợp cho 16 checksum khác nhau.
- Mặc định = **hành vi trước W1.7** (measurements/timelines bật, retrieval
  tắt), không phải "baseline nên là gì". Mặc định đổi hành vi sẽ chạy lại mọi
  phép đo cũ dưới một arm mới mà không ai yêu cầu; baseline phải **khai** arm
  vector của nó.
- Runner **từ chối** khi được đưa TraitSource mà vector không khai traits -
  nếu không, checksum nói arm tắt trong khi prompt mang natures.
- `filter_tool_menu` / `auto_route_checker` (của W3) **từ chối `True`** thay vì
  im lặng không làm gì: một arm báo là đã chạy mà chưa chạy là lỗi duy nhất
  không thứ gì phía sau phát hiện được. Vẫn nằm trong checksum khi tắt, để
  preregistration viết trước không phải viết lại sau.

**Test:** `tests/test_analyst_features.py` (13) + suite analyst - 191 passed.
**Commit:** `bd8f752`

---

## W1.8 - Snapshot traits tái dựng được (bộ ba)

Hash một mình pin **giá trị**, không pin **tài liệu**. Bảng có trạng thái
*hiện tại*: operator sửa một row, pointer dịch, revision mà bundle được chấm
biến mất - còn lại một bundle nêu một hash không ai dựng nổi tài liệu khớp.
Nhìn thì "đã pin", thực tế không replay được: đúng thứ frozen bundle sinh ra
để chặn, đi vào qua đúng cái field không ai kiểm.

`services/analyst_service/planbench_analyst/traits_snapshot.py` (mới) +
`AnalystBundle` thêm 3 field:

| Field | Nghĩa |
|---|---|
| `traits_revision_id` | revision nào - nhãn để operator nói chuyện |
| `traits_snapshot_checksum` | hash **nội dung**, mọi reader tự tính lại |
| `traits_snapshot_ref` | tài liệu ở đâu - **content-addressed**, checksum nằm trong tên file |

- Có một thì phải có cả ba (bundle validator), và cả ba nằm trong `identity` +
  `runtime_config_checksum`. Mỗi cái riêng lẻ có thể đúng trong khi cặp sai:
  ref trỏ revision khác, checksum khớp tài liệu bundle không nêu, id bị dùng
  lại.
- Hash **toàn bộ catalog**, không phải phần một packet dùng - subset theo
  packet sẽ cho một hệ hai checksum trên hai case.
- Canonical trước khi hash (sort `(algorithm_id, kind)`, text qua NFKC bằng
  chính `sanitize.canonical`, hash bằng chính `artifact_checksum`) - không đẻ
  công thức hash thứ hai.
- `read_snapshot` tính lại checksum từ bytes và **từ chối** file sửa tại chỗ;
  `verify_snapshot` kiểm cả ba; `delete_snapshot` từ chối khi còn bundle cite.

**Test:** `tests/test_analyst_traits_snapshot.py` (20) + bundle/gate/identity -
127 passed. **Commit:** `6df43a4`

---

## W2 - Candidate generator hybrid

`services/analyst_service/planbench_analyst/candidates.py` (mới). Nền tảng đề
xuất **không gian cơ chế**, model chọn trong đó. Bắt model tự nghĩ ra không
gian thì nó bám vào chữ trong packet, guard drop kết quả — và phép đo khi đó đo
guard chứ không đo model.

Bốn luật, mỗi luật là một cách làm sai đã tránh:

- **Candidate không mang `supporting_refs`.** Refs là việc của model, guard chấm
  việc chọn đó. Shortlist kèm sẵn citation sẽ chấm cách đọc của generator trong
  khi trông như chấm model.
- **`verification_options` là biến riêng** (cờ riêng): shortlist là prior về
  *cơ chế*, options là gợi ý *cách kiểm chứng*. E4a/E4b đo tách; gộp thì gain ở
  một bên báo thành gain ở cả hai.
- **Ba nguồn, gộp, không nhân đôi**, dedupe `(mechanism_id, subject)`. Một cơ
  chế đến từ hai nguồn là **một** candidate với hai lý do; liệt kê hai lần sẽ
  đọc thành hai cơ chế đồng ý với nhau.
  - Traits hành xử khác: nature nói thuật toán *như thế nào*, không nói run này
    xảy ra gì — nên nó **nâng** cơ chế mà run đã gợi ý và **không tự sinh** cơ
    chế mới. Một nature sinh được candidate từ hư không chính là folklore của
    model đi vào bằng cửa của platform.
- **`unknown` luôn có mặt** và luôn cuối danh sách. Shortlist không có đường
  từ chối là ép chọn, và ép chọn là thứ làm analyst sai một cách tự tin.

**Distractor** ở cùng module, **eval-only, fail-closed**: `partition` khác
`development` thì `CandidateRefusal`. Distractor bốc từ các proposition
**assertable** platform biết, không bốc từ nhãn scorer; bỏ gold phải **truyền
tường minh** gold là gì (harness đoán = tự chấm phán đoán của mình).
`generator_recall_at_k` chấm trên **output của generator**, trước mọi can thiệp
harness — `RoundOutcome.shortlist` giữ đúng bản đó.

Prompt thêm block `CANDIDATES` (chỉ khi cờ bật), `PROMPT_VERSION` → `a3.0.0`.
Hai cờ mới: `candidate_shortlist`, `verification_options`, đều **mặc định tắt**.

**Test:** `tests/test_analyst_candidates.py` (25) + suite analyst — 234 passed.
**Commit:** `077319d`

---

## W3 - Tool routing theo capability

`services/analyst_service/planbench_analyst/routing.py` (mới). Hai thay đổi,
**độc lập**, vì trả lời hai câu hỏi khác nhau:

| Cờ | Loại | Ý nghĩa |
|---|---|---|
| `filter_tool_menu` | **presentation** | Ẩn card mà run này không phục vụ được. Request đó dù sao cũng chết ở admission; nhưng refusal đọc với model như platform hỏng, và nó dành lượt sau đi vòng qua bức tường không tồn tại. |
| `auto_route_checker` | **semantic** | Code chọn checker sau declare + admission. Đây là thứ duy nhất trong lớp này **đổi nghĩa một metric**: `checker_selection` thôi là "model chọn đúng check chưa" và thành "code chọn đúng chưa". |

- **`menu_recall`** đo **trước** khi tin bất kỳ arm nào có filter. Filter cắt
  mất tool mà case cần thì mọi số phía sau là số về filter — và hỏng kiểu này
  vô hình về sau: vòng chạy đơn giản là không bao giờ hỏi.
- **Fact query / evidence navigation không bị lọc theo cơ chế**: chúng chính là
  cách analyst *tìm ra* cơ chế, lọc theo cơ chế chưa chọn là vòng tròn.
  `unknown` giữ nguyên menu evidence-capable.
- **W3.2 — card khai nguồn của từng argument** (`ArgumentSource`: packet
  candidate / episode / region / pair, hoặc `analyst`). Router chỉ điền argument
  có nguồn **packet**; argument thuộc về model (budget multiplier, độ rộng cửa
  sổ) để nguyên — điền mặc định là platform tự chọn thí nghiệm rồi tự chấm.
  Schema wire không đổi (đã regenerate, không drift) nên **không bump catalog**.
- **Bốn failure type** giữ bốn số: `tool_not_in_menu`,
  `missing_required_evidence`, `missing_required_argument`,
  `repeat_after_verdict` — bốn cách sửa khác nhau; gộp thành một số thì không
  chỉ được vào đâu.
- Transcript ghi `menu:<shown>/<all>`, `routed:<tool>:code_route`,
  `route_declined:<reason>` để report tách được **code-route** và
  **model-chọn**.

**Test:** `tests/test_analyst_routing.py` (21) + suite chạm tới — 362 passed.
**Commit:** `66f327f`

---

## W4 - Discriminated union và repair có giới hạn

Trước đây một hình dạng mang hai thứ khác nhau: statement mà bằng chứng đã có
sẵn trong packet, và statement viết **trước** khi check chạy. Hai cái đọc giống
hệt nhau, dù cái thứ hai chỉ được phép tồn tại vì host buộc evidence vào
hypothesis đã declare trước.

- **`decision: "no_check" | "check"`** vào schema, đặt **trước** `statement` để
  model chốt nhánh rồi mới viết — viết trước rồi dán nhãn sau là kết luận đi
  tìm hạng mục. `PROMPT_VERSION` → `a4.0.0`.
- Union **ép trong parser**, không ép trong schema: strict mode buộc khai mọi
  property của mọi nhánh, nên union thật sẽ phải nới `additionalProperties`
  hoặc nhân đôi cả object. Parser từ chối **có tên** (`no_check` mà kèm check;
  `check` mà không nêu tool) — và có tên chính là điều kiện để repair được.
- **Repair đúng một lần**, tính là **một model call** (không phải retry theo
  nghĩa A7): vòng lặp repair tới khi parse được là vòng lặp trả tiền để được
  đồng ý.
- **Guard rule 8 — `draft_claims_a_verdict`**: draft nói kết quả của check chưa
  chạy bị chặn. Từ ngữ y hệt verdict thật, nên sau đó không thứ gì phân biệt
  được.
- **Audit link**: transcript ghi `draft:<id>`, `final:<id>`,
  `supersedes:<cũ>:<mới>`. Không sửa `HypothesisProposal` (sẽ phải bump
  `EXPLANATION_SCHEMA_VERSION` và dựng lại toàn bộ fixture) — viết lại dưới cùng
  ID vốn đã bất khả thi theo protocol, phần còn thiếu chỉ là dòng audit.
- **W4.6 — chi phí theo lớp chốt trước**: `cost_by_class(results, spec)` dùng
  `expected_check_required` từ file nhãn; `branch_matrix` báo nhánh model chọn
  **chỉ như chẩn đoán**. Báo chi phí theo nhánh model chọn là post-treatment:
  nhánh là kết quả, và so subset chọn sau khi nhìn output là so hai quần thể
  khác nhau rồi gọi hiệu số đó là chi phí.

**Test:** `tests/test_analyst_union.py` (14) + suite chạm tới — 262 passed.
**Commit:** `30ecd57`

---

## Cần An quyết (hai chỗ chặn)

Toàn bộ phần **code** của plan tới W4 đã xong. Phần còn lại — B1, E1–E10, W5,
freeze, confirmatory — là **đo**, và đo cần hai thứ chỉ An mở được:

### 1. Duyệt traits (W1.6)

Cơ chế đã có, người duyệt thì chưa. Trạng thái hiện tại: **6/6 row là `draft`**
(anchor của cả sáu đều checkable sau khi sửa row `dwa`).

```bash
python scripts/review_algorithm_traits.py list
python scripts/review_algorithm_traits.py approve dwa --by "An Tong"
```

Chưa duyệt thì traits vẫn **được cite** để mở rộng không gian giả thuyết, nhưng
**không backing được claim đã promote**, và một golden run có promoting trên
nature sẽ bị `lock_for_golden` chặn.

### 2. Ngân sách model cho B1 và E1–E10

B1 là baseline real-host: chạy model thật trên 3 fixture, 3 repeat, **bypass
cache** (harness từ chối báo cáo nếu `cache_hits > 0`). E1–E10 nhân số đó lên
theo số arm — arm vector hiện có 8 cờ, riêng E3 đã là 2×2.

Cần An chốt:

- Model nào (`o4-mini` như lần A7? local Ollama? cả hai để so?).
- Trần chi phí cho đợt B1 + E1–E3, và có chạy tiếp E4–E10 hay dừng lại xem số.

Nhắc lại một điều đã ghi trong preregistration: chưa có holdout (3/6 họ,
`OFFICIAL_GOLDEN_READY=False`) nên **mọi kết quả E là exploratory**, không đủ
cho quyết định deployment. Nếu muốn kết luận deployment thì phải dựng nốt 3 họ
còn lại trước — đó cũng là một quyết định của An.
