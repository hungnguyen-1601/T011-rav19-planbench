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
| W1.0 ToolHost thật vào InProcessHost | **xong** | `d25914a` |
| W1.1–W1.8 | chưa | |
| B1 baseline real-host | chưa | |
| E1–E3 input ablation | chưa | |
| W2 hybrid candidate generator | chưa | |
| W3 tool routing | chưa | |
| W4 discriminated union + repair | chưa | |
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
