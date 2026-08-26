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
| W0 nền đánh giá + preregistration | **xong** | xem git log — dòng `Lay the evaluation foundation…` |
| W1.0 ToolHost thật vào InProcessHost | đang làm | |
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
