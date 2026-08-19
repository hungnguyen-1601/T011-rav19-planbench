# Plan — AI Analyst subsystem (AI1–AI5): agent sinh giả thuyết "vì sao thuật toán thắng"

**Ngày:** 2026-08-19 · **Trạng thái:** bản 2, chờ An approve
**Bản 2 — sau vòng rà của An (9 điểm) + E5/E6a đã land:** bỏ toàn bộ shim (contract
E5 đã có thật), bundle đủ field bắt buộc + container digest, state machine round
tường minh (declare trước admit), bỏ tuyên bố deterministic quá mạnh (cache theo
identity_checksum + đo nondeterminism bằng repeated runs), calibration đủ 6 metric ×
6 họ qua scorer platform, critic hạ xuống advisory + ablation, cấm số trong
hypothesis_statement, AI2 khai rõ giới hạn KB draft, thêm AI5 productization +
Docker thành task. Đối chiếu hiện trạng: `notes/2026-08-19/tongduyan_ra-soat-e5-e6a-cho-plan-analyst.md`.
**Thiết kế nguồn:** `plans/2026-08-18/tang-giai-thich-vi-sao.md` (bản 7) §3/§6/§7 ·
`notes/2026-08-18/tongduyan_giai-phap-giai-thich-vi-sao-thuat-toan-thang.md` (v2) §6–§7
**Tiền đề:** E0–E5, E6a xong; E6b đang commit. Contract import thẳng từ
`planbench_explanation` — không shim gì nữa.

---

## 1. Context

Tầng giải thích đã chốt ranh giới: platform sở hữu dữ liệu/contract/gate (E0–E6),
AI subsystem là plan riêng (AI1–AI5). Đây là plan của AI subsystem đó — agent đọc
CasePacket, sinh `HypothesisProposal`, gọi tool qua catalog đóng, nộp AnalystBundle
cho gate, và (AI5) trở thành tính năng dùng được sau khi qua gate.

**Quyết định đã chốt với An:**

- **2 agent riêng, chung model backend** — không nhét analyst vào AI paper-import
  của đồng nghiệp. Giao nhau duy nhất qua dữ liệu platform (plugin → trace →
  CasePacket), không qua code.
- **Tái dùng trực tiếp** tầng LLM provider của M8
  (`services/agent_service/planbench_agent/`: `LLMProvider`,
  `LLMRequest.output_schema`, `AnthropicProvider`, `MockProvider`,
  `DeterministicResponder`, `factory.build_provider`).
- Code mới ở **`services/analyst_service/planbench_analyst/`** — thứ bị gate chấm
  nằm trọn một chỗ, `agent_code_digest` của bundle trỏ vào repo SHA.
- **Không fine-tune** — ràng buộc chất lượng nằm ở contract + prompt + guard.
- Plan này đi tới **sản phẩm** (AI5), không dừng ở bundle prototype; AI5 có
  prerequisite rõ (E4.1 + gate pass) nên nằm cuối, không chặn các phase trước.

**Nguyên tắc bất biến (plan bản 7):** analyst không đọc Parquet thô, không tự đóng
dấu, tool menu đóng, **LLM không bao giờ là nguồn của một con số** hay kết luận
nhân quả — hệ quả trực tiếp: `hypothesis_statement` cấm chứa số (§A3).

## 2. Tái dùng (không viết mới)

| Có sẵn | Ở đâu | Dùng cho |
|---|---|---|
| `LLMProvider`/`LLMRequest`/`MockProvider`/`build_provider` | `planbench_agent/provider.py`, `factory.py` | mọi lời gọi model |
| `AnalysisRequest`/`AnalysisResponse`/`ToolRequest`/`ToolResult`/`ToolSession` | `planbench_explanation/protocol.py` | toàn bộ wire protocol — import, không định nghĩa lại |
| `AnalystBundle`/`MetricTargets`/`GateDecision`/`analyst_visible` | `bundle.py` | đóng gói + gate + flag |
| `KnowledgeQuery`/`KnowledgeResult`/`MechanismReferenceCandidate`/`resolve_candidates` | `knowledge_contract.py` | AI2 đúng contract |
| `TOOL_CATALOG` (16 card, 4 lớp) + `ToolIO.check_arguments` | `catalog.py`, `tools.py` | menu đóng + validate arg phía client |
| `ToolHost` + 4 mechanism checker | `host.py`, `checkers.py`, `replay.py` | thi hành thật (E6a/E6b) |
| `MockToolHost` + `reference_analyst` + `run_round`/`open_round` | `integration.py` | tích hợp offline + **floor baseline** |
| `VISIBLE_SUITE` (6 họ × 2, 7/12 abstain) + `score_case`/`score_suite`/`MetricTargets` | `golden_fixtures.py`, `golden.py` | calibration + scoring — không tự viết metric |
| `HypothesisProposal`/`EvidenceRef`, `CasePacket`/`build_case_packet`, `check_phrases`, `require_assertable`, `canonical_subjects`, `artifact_checksum` | `ledger.py`, `case_packet.py`, `levels.py`, `propositions.py`, `subjects.py`, `versioning.py` | output schema, input, validator canonical |

## 3. Các phase

### A0 — Skeleton + hạ tầng chạy được trong container (0.5–1 ngày)

- Tạo `services/analyst_service/planbench_analyst/` (`__init__.py` boundary
  docstring theo phong cách `planbench_agent`). **Không còn contracts_shim** —
  E5 đã land.
- Wire path: `pyproject.toml` pythonpath, `scripts/dev_stack.sh` PY_PATH,
  `ruff.toml known-first-party` (guard test `tests/test_dev_stack_pythonpath.py`).
- **Docker là task, không phải ghi chú** (điểm 9): sửa `docker/Dockerfile.api`
  PYTHONPATH đang thiếu `packages/decision`, `packages/explanation`,
  `packages/plugin_sdk`, `ml` — cộng thêm `services/analyst_service`. Platform
  không chạy được bundle nếu container không import được dependency.
- Test: import surface + pythonpath guard.

### A1 — Packet view + fact index (0.5 ngày)

- `packet_view.py`: validate `CasePacket` header versions khớp bản đang chạy,
  dựng **fact index** — mỗi fact một record `{ref, value, unit, subject/candidate,
  scope}` (không chỉ ref trần: guard A3 cần đối chiếu số-đúng-chỗ, điểm 7) — và
  serialize packet thành text deterministic cho prompt (ordering cố định).
- Test: cùng packet ⇒ cùng chuỗi; header lệch version ⇒ từ chối; index đủ
  value/unit/subject.

### A2 — Hypothesis engine, AI1 lõi (1–2 ngày)

- `analyst.py`: một agent. Nhận `AnalysisRequest` (packet + catalog +
  `max_tool_requests` + `analyst_bundle_id`) → LLM call → structured output qua
  `LLMRequest.output_schema` = proposals + abstentions, map vào
  `HypothesisProposal`/`AnalysisResponse`.
- **`hypothesis_id` do hệ sinh, không do model đặt** (điểm 3): hash nội dung
  canonical của proposal (proposition_type + subject + supports + requested_checks,
  loại field volatile), đụng nhau ⇒ suffix. `declare()` platform refuse
  `hypothesis_redefined` — id ổn định là điều kiện sống.
- **Reproducibility best-effort, không tuyên bố deterministic** (điểm 4):
  temperature 0 chỉ giảm variance, API model vẫn nondeterministic (plan nền :253).
  Mọi response live lưu transcript + response checksum vào artifact. Cache =
  memoize per-call: call đầu key `(bundle.identity_checksum, prompt/request
  checksum, packet checksum)`; call sau cộng transcript-so-far checksum. Không
  dùng `bundle_id` trong key — nó chỉ là nhãn (report E5 :112).
- `prompts.py` hằng số — `prompt_checksum` của bundle tính từ đây.
- Chạy không cần key nhờ `MockProvider`/`DeterministicResponder`.
- Test scripted: parse đúng; trường lạ ⇒ parse error; id sinh ổn định qua hai lần
  chạy cùng nội dung.

### A3 — Self-guard + critic advisory (1–2 ngày)

- `guard.py` — **gọi validator canonical của platform, không viết lại logic**
  (điểm 7): `check_phrases`, `require_assertable`, `canonical_subjects`,
  `ToolIO.check_arguments` cho từng requested_check. Guard chỉ thêm phần platform
  không expose trước-khi-nộp:
  1. mọi ref trong `supports`/`contradicts` tồn tại trong fact index;
  2. **cấm số trong `hypothesis_statement`** — regex chặn numeric literal; mọi
     lượng hóa đi qua EvidenceRef trỏ record fact index có value/unit/subject;
     câu hiển thị (nếu cần số) render từ fact table, không từ model;
  3. `proposition_type` ∉ `packet.blocked_claim_types` — vi phạm ⇒ abstention có
     `missing_evidence`;
  4. requested_check: tool tồn tại trong catalog + proposition ∈
     `supported_proposition_types` của card (checker-selection là metric gate);
  5. verb-guard `check_phrases(statement, "associated")`.
- **Critic pass = advisory, không phải gate thứ hai** (điểm 6): cùng model ⇒ lỗi
  tương quan, có thể âm thầm giết hypothesis đúng. Luật: critic chỉ **rerank +
  gắn cờ**, không xóa; lưu đủ ba (proposal gốc, critique, quyết định cuối) vào
  artifact; authority duy nhất = guard deterministic + promotion platform.
  **Ablation ở A6**: single-pass vs generator+critic trên VISIBLE_SUITE — critic
  không cải thiện precision/abstention có ý nghĩa thì không bật mặc định.
- Test: từng luật một fixture vi phạm; statement chứa số ⇒ chặn; critic không
  bao giờ làm mất proposal khỏi artifact.

### A4 — Vòng đời analysis round, AI3 (1–2 ngày)

- `round_runner.py` — **state machine tường minh** (điểm 3), khớp
  `protocol.py`/`integration.run_round`:

  ```
  AnalysisRequest
    → engine sinh AnalysisResponse (proposals + abstentions)
    → guard A3
    → session.declare(proposals)            # batch-atomic, trước mọi request
    → [ToolRequest → ToolHost.call() → ToolResult]*   # sequence tăng dần,
    →                                        # analysis_run_id + analyst_bundle_id
    →                                        # xuyên suốt, budget = max_tool_requests
    → revise: 1 LLM call đọc results → AnalysisResponse sửa đổi
    → (tối đa 2 vòng revise) → final AnalysisResponse
  ```

- Đọc `ToolResult` đúng nghĩa: `execution_status != completed` ⇒ không đọc
  verdict; tôn trọng `unsupported_inferences`; `refuted` ⇒ rút proposal;
  `not_checkable` ⇒ hypothesis đứng ở associated. Rejection từ `ToolSession.admit`
  (12 mã) xử lý theo mã, không nuốt.
- Offline chạy trên `integration.MockToolHost` (admit qua ToolSession thật);
  online cùng code chạy trên `ToolHost` thật — chỉ đổi host object.
- Test: declare-trước-admit (request trước declare bị refuse); budget cạn ⇒ dừng
  sạch; sequence lệch ⇒ reject; refuted/not_checkable đúng hành vi.

### A5 — Knowledge provider, AI2 (0.5–1 ngày)

- `knowledge_provider.py`: nhận `KnowledgeQuery` (features only), trả
  `KnowledgeResult` chứa `MechanismReferenceCandidate` — **đúng type
  `knowledge_contract.py`, không interface rút gọn** (điểm 8); resolve qua
  `resolve_candidates()` canonical, xử lý `RejectedReference` outcomes.
- **Vai trò hiện tại khai rõ**: KB v1 toàn draft ⇒ `may_support_a_claim=False`
  mọi entry — AI2 chỉ (a) mở rộng hypothesis search space, (b) trả reference
  candidate đúng contract. `retrieval_score` không bao giờ là confidence hay
  evidence. Khi An approve KB thì giá trị promote tự mở, code không đổi.
- v1 lexical match (`knowledge.match` + tokenizer `planbench_agent/rag.py` nếu
  cần scoring); không vector DB trước khi harness A6 chỉ ra recall kém.
- Test: provider không tự trả `review_status`/`source_refs`; entry lạ/lệch
  version ⇒ rejected outcome đúng loại.

### A6 — Calibration harness (1–2 ngày)

- `harness.py` chấm bằng **scorer platform** — `score_case`/`score_suite`/
  `ScoreBoard` — trên `VISIBLE_SUITE` (**đủ 6 họ**: inflation_gap_closure ·
  dwa_local_minimum · rrt_sample_starvation · expansion_latency ·
  negative_control · insufficient_evidence). **Đủ 6 metric của
  `CALIBRATION_TARGETS`** (điểm 5): structural_violations = 0 · precision ≥ 0,90 ·
  recall@3 ≥ 0,70 · abstention ≥ 0,90 (định nghĩa scorer trên ca phải-abstain,
  không phải tỷ lệ abstain thô) · component_attribution ≥ 0,85 ·
  checker_selection ≥ 0,90.
- Packet cho từng planted case: `packet_ref` của VISIBLE_SUITE chưa resolve được
  (chờ A6.5) ⇒ trước mắt dựng packet tổng hợp bằng `build_case_packet` khớp
  từng case; khi packet fixture thật có thì trỏ sang, harness không đổi.
- **Baseline bắt buộc**: `reference_analyst` (model-free) là floor — LLM analyst
  không thắng floor thì không có lý do ship. **Ablation critic** (A3) chạy ở đây.
- **Live evaluation là bắt buộc, không phải smoke tùy chọn** (điểm 4): mock chỉ
  chứng minh orchestration. Chạy model thật trên VISIBLE_SUITE **≥ 2 lần lặp** để
  đo nondeterminism (variance từng metric vào report — đúng yêu cầu "đo bằng
  repeated runs" plan nền :253). Cần `ANTHROPIC_API_KEY`; CI vẫn MockProvider.
- Report JSON vào `artifacts/analyst/<date>/` kèm transcript + checksums.

### A6.5 — Data readiness cho calibration chính thức (phối hợp platform, ngoài critical path)

Điểm 5 của An: golden chính thức chưa sẵn — writer có nhưng chưa có planted runs
chạy cùng recorder; `OFFICIAL_GOLDEN_READY = False`; 4/6 họ `CANNOT_STAGE_YET`
(`scripts/plant_golden_runs.py`). Phase này **thuộc platform**, liệt kê để plan
không giả vờ nó xong: chạy planted runs với sidecar → packet fixtures thật cho
VISIBLE_SUITE → mở dần 4 họ còn lại → flip `OFFICIAL_GOLDEN_READY` → preregister.
Analyst chỉ tiêu thụ; A6 chuyển từ packet tổng hợp sang packet thật khi phase này
xong.

### A7 — AnalystBundle + container (0.5–1 ngày)

- `bundle.py` phía analyst: lắp `AnalystBundle` **đủ field contract** (điểm 2):
  `bundle_id` · `agent_code_digest` = `git:<repo SHA>` — **repo-level, cover cả
  dependency bắc cầu** `planbench_agent`/`planbench_explanation` (tách shared
  package chỉ khi cần digest mịn hơn — không phải bây giờ) · `container_digest`
  (sha256 image) · `model_id` + `model_revision` (lấy từ response API) ·
  `prompt_checksum` · `rag_index_version` + `retrieval_config_checksum` (AI2 v1
  lexical: version = KB version + tokenizer config checksum) ·
  `tool_catalog_version` · `generation_parameters` · `created_at`.
- **Dockerfile.analyst**: image chạy được round offline (MockToolHost) trong
  container — vì platform chạy bundle trong môi trường platform kiểm soát,
  image không chạy được = bundle không nộp được. Digest của image này là
  `container_digest`.
- Test: bundle thiếu field ⇒ contract refuse (đã có phía platform, thêm test
  phía builder); `identity_checksum` ổn định khi chỉ đổi `bundle_id`/`created_at`.

### A8 — AI5 productization (2–3 ngày; prerequisite: E4.1 + gate pass)

Điểm 9 — chốt phương án "đi tới sản phẩm":

- **Async endpoint** "Phân tích nguyên nhân": nhận run → dựng packet (E4.1) →
  round → lưu artifact; không bao giờ render lời model — UI chỉ đọc claim ledger
  sau promotion (luật plan bản 7 §4.6).
- **Feature flag theo `GateDecision` đã verify**: `analyst_visible()` +
  `verify_gate_decision()` là nguồn duy nhất; nối lên web (Python đã có, web
  chưa — E5 report §9).
- **Timeout + cost budget** mỗi round (token + số LLM call), quá ⇒ degrade.
- **Observability**: log structured mỗi round (bundle id, packet checksum,
  request/rejection codes, token, latency), artifact transcript đầy đủ.
- **Fallback**: LLM chết/quá budget ⇒ panel deterministic (template + claim
  ledger) — đường này đã tồn tại từ E4, chỉ cần không chặn nó.
- **Controlled rollout**: flag bật theo deployment, version mới = bundle mới =
  gate mới (hidden rotation — platform).

## 4. Ngoài phạm vi

Fine-tune model · vector DB (chờ số đo A6) · hidden gate run (platform chạy, AI
nộp bundle) · planted runs + packet fixtures + `OFFICIAL_GOLDEN_READY` (A6.5,
platform) · AI paper-import của đồng nghiệp.

## 5. Files chính

```
services/analyst_service/planbench_analyst/
  __init__.py  packet_view.py  prompts.py  analyst.py
  guard.py  round_runner.py  knowledge_provider.py
  harness.py  bundle.py
docker/Dockerfile.analyst
tests/test_analyst_packet_view.py  test_analyst_engine.py
tests/test_analyst_guard.py        test_analyst_round.py
tests/test_analyst_knowledge.py    test_analyst_harness.py
tests/test_analyst_bundle.py
```

Sửa nhỏ: `pyproject.toml` (pythonpath), `scripts/dev_stack.sh`, `ruff.toml`
(known-first-party), `docker/Dockerfile.api` (PYTHONPATH thiếu 4 đường — sửa ở A0).

## 6. Kiểm chứng

- Mỗi phase: `pytest tests/test_analyst_*.py` (MockProvider) + `ruff check`.
  Không chạy full suite.
- A6: harness trên VISIBLE_SUITE — offline (mock + reference_analyst floor) và
  **live ≥ 2 lần lặp** đo variance; report JSON + transcript artifact.
- A7: build image, chạy round offline trong container, digest ghi vào bundle.
- Sau mỗi phase: report vào `docs/antongduy/reports/<ngày>/tongduyan_*.md`.
  Không tự commit.

## 7. Ước lượng & thứ tự

A0 → A1 → A2 → A3 → A4 → A5 → A6 → A7 tuần tự, ~6–9 ngày.
A6.5 song song phía platform. A8 chờ E4.1 + gate pass.

## 8. Rủi ro

| Rủi ro | Giảm nhẹ |
|---|---|
| Model overclaim / bịa số | schema tước quyền + cấm số trong statement + guard gọi validator canonical + promotion platform là authority cuối |
| Critic giết hypothesis đúng (lỗi tương quan) | advisory-only, log đủ ba, ablation A6 trước khi bật |
| Tuyên bố reproducible quá mức | không tuyên bố deterministic; transcript + checksum mọi response; repeated runs đo variance |
| Calibration lệch gate thật | dùng scorer + targets platform nguyên bản, không tự viết metric |
| Packet tổng hợp A6 lệch packet thật | A6.5 thay bằng packet fixture thật khi có; harness không đổi interface |
| Bundle không chạy trong môi trường platform | Dockerfile.analyst + test round trong container (A7); Dockerfile.api PYTHONPATH sửa ở A0 |
| KB draft bị đọc thành evidence | AI2 khai rõ vai trò; score không phải confidence; test provider không tự trả review_status |
| Coupling vào agent_service | chỉ import provider layer; digest repo-level cover bắc cầu; tách shared package chỉ khi cần digest mịn |
