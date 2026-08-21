# Plan — AI Analyst subsystem (AI1–AI5): agent sinh giả thuyết "vì sao thuật toán thắng"

**Ngày:** 2026-08-19 · **Trạng thái:** bản 7, chờ An approve
**Bản 7 — sau vòng rà thứ sáu của An (5 điểm):** dry run tách type
`DryGateRun` không chứa `GateDecision` (không còn đường rửa điểm qua
`analyst_visible`); effective budget vào verification chain
(`GateDecision.effective_budget_checksum`, `verify_gate_decision` +
`analyst_visible` đối chiếu budget production); bundle **embed
`requested_budget: AnalysisBudget`** thay vì chỉ checksum; token budget có
semantics cụ thể (cumulative, estimate-trước/charge-sau, overshoot ⇒
budget_exceeded); `provider_turn` chốt là JSON mapping — structural equality,
không phải byte-identical.
**Bản 6 — sau vòng rà thứ năm của An (4 điểm + 3 điểm nên sửa):** `RoundSource`
dựng cặp analysis+host từ cùng evidence source (available_evidence không còn
rỗng mặc định, admission và host không thể bất đồng); gate fail-closed theo
suite status (`preregistered`) + mọi packet `recorded`, cờ đổi tên `dry_run` +
artifact mang `is_dry_run`; model gateway round-trip nguyên vẹn `provider_turn`
opaque; `AnalysisBudget` contract — requested budget vào bundle identity,
effective = min(requested, platform cap), calibration/gate/production cùng
effective; stderr + transcript hidden gate thành restricted artifact; flatten
config đổi sang canonical JSON Pointer chống collision; source-tree hash định
nghĩa bằng manifest byte-level.
**Bản 5:** RoundHostProtocol declare/call, model gateway + sandbox, JSONL ABI,
flatten config, cache dev, revise-redeclare, luật pass 3 lượt, PacketArtifact
loader. **Bản 4:** host sở hữu session, hai lane, generation config
capability-aware, freeze clean-tree + model preflight. **Bản 3:** seam duy nhất,
frozen-bundle calibration, fixture manifest, abstention semantics. **Bản 2:**
bundle đủ field, 6 metric × 6 họ, critic advisory, cấm số.
**Thiết kế nguồn:** `plans/2026-08-18/tang-giai-thich-vi-sao.md` (bản 7) §3/§6/§7 ·
`notes/2026-08-18/tongduyan_giai-phap-giai-thich-vi-sao-thuat-toan-thang.md` (v2)
**Đối chiếu hiện trạng:** `notes/2026-08-19/tongduyan_ra-soat-e5-e6a-cho-plan-analyst.md`

---

## 0. Contract baseline

Plan viết against một **clean commit** — mọi diff so với baseline phải rà lại
các phase liên quan:

| Thứ | Giá trị |
|---|---|
| Baseline commit | `05e67de` (E4.1 = `81e93b0`; E6b = `a87a9af`) |
| `TOOL_CATALOG_VERSION` | `3.0.0` |
| `VISIBLE_SUITE_VERSION` | `calibration-0.1.0` (12 case, 6 họ × 2, 7/12 abstain) |
| `SIDECAR_SCHEMA_VERSION` | `0.2.0` (RLE) |
| Gate seam | `gate.py`: `Analyst = Callable[[AnalysisRequest], AnalysisResponse]`; **không truyền `available_evidence`** (mặc định rỗng, protocol.py:188) và **chỉ kiểm visibility, chưa kiểm suite.status** (gate.py:169) — cả hai đổi ở §A4/RFC |
| Session ownership | cả hai host tự tạo `self.session = ToolSession(analysis)` (integration.py:169, host.py:521) |
| `generation_parameters` schema | `dict[str, float\|int\|str\|bool]` — scalar phẳng (bundle.py:121) ⇒ flatten JSON Pointer (§A2) |
| ProviderTurn | provider layer giữ raw assistant turn để replay (provider.py:84 — Gemini `thought_signature`, Anthropic thinking blocks) ⇒ gateway phải round-trip (§A4.4) |
| Họ stageable | 3/6; 3 họ `CANNOT_STAGE_YET` (comment E4.1 stale — sửa nhân tiện) |
| `OFFICIAL_GOLDEN_READY` | `False` |
| KB v1 | 5 entry đều `draft` |
| `packet_ref` canonical root | `fixtures/golden/visible/<case_id>/packet.json` |

## 1. Context

Platform sở hữu dữ liệu/contract/gate (E0–E6); đây là plan AI subsystem
(AI1–AI4 + đường tới AI5): agent đọc CasePacket, sinh `HypothesisProposal`, gọi
tool qua catalog đóng, nộp AnalystBundle cho gate. AI5 tách plan riêng sau gate
pass (§A8).

**Quyết định đã chốt với An:** 2 agent riêng chung model backend · tái dùng
provider M8 · code ở `services/analyst_service/planbench_analyst/` · không
fine-tune · một seam orchestration duy nhất · gate/official calibration chạy
đúng container image được chấm, model call qua platform gateway, container
không cầm credential.

**Nguyên tắc bất biến (plan bản 7):** analyst không đọc Parquet thô, không tự
đóng dấu, tool menu đóng, **LLM không bao giờ là nguồn của một con số** (§A3).
Hidden packet không rời trust boundary platform trừ đường vendor API đã khai
(plan nền :253); container bị chấm không có đường exfiltrate — kể cả qua
stderr/log (§A4.4).

## 2. Tái dùng (không viết mới)

| Có sẵn | Ở đâu | Dùng cho |
|---|---|---|
| `LLMProvider`/`LLMRequest`/`LLMMessage.provider_turn`/`MockProvider`/`build_provider` | `planbench_agent/provider.py`, `factory.py` | mọi lời gọi model + replay turn |
| `AnalysisRequest`/`AnalysisResponse`/`ToolRequest`/`ToolResult`/`ToolSession` | `planbench_explanation/protocol.py` | wire protocol |
| `AnalystBundle`/`MetricTargets`/`GateDecision`/`analyst_visible`/`verify_gate_decision` | `bundle.py` | đóng gói + gate + flag |
| `run_gate` | `gate.py` | gate + dry gate (sau RFC §A4.5) |
| `KnowledgeQuery`/`KnowledgeResult`/`MechanismReferenceCandidate`/`resolve_candidates` | `knowledge_contract.py` | AI2 |
| `TOOL_CATALOG` (16 card) + `ToolIO.check_arguments` | `catalog.py`, `tools.py` | menu đóng + validate arg |
| `ToolHost` + 4 mechanism checker | `host.py`, `checkers.py`, `replay.py` | thi hành thật |
| `MockToolHost` + `reference_analyst` + `TYPICAL_AVAILABLE_EVIDENCE` | `integration.py` | offline + floor + evidence set mẫu |
| `VISIBLE_SUITE` + `score_case`/`score_suite`/`CALIBRATION_TARGETS` | `golden_fixtures.py`, `golden.py` | calibration + scoring |
| `HypothesisProposal`/`EvidenceRef`, `CasePacket`/`build_case_packet`, `check_phrases`, `require_assertable`, `canonical_subjects`, `artifact_checksum` | `ledger.py`, `case_packet.py`, `levels.py`, `propositions.py`, `subjects.py`, `versioning.py` | output, input, validator canonical |

## 3. Các phase

### A0 — Skeleton + hạ tầng container (0.5–1 ngày)

- `services/analyst_service/planbench_analyst/` + wire path (`pyproject.toml`,
  `scripts/dev_stack.sh`, `ruff.toml`; guard test pythonpath).
- Sửa `docker/Dockerfile.api` PYTHONPATH thiếu `packages/decision`,
  `packages/explanation`, `packages/plugin_sdk`, `ml` — cộng
  `services/analyst_service`, `services/agent_service`.
- Test: import surface + pythonpath guard.

### A1 — Packet view + fact index (0.5 ngày)

- `packet_view.py`: validate header versions; fact index
  `{ref, value, unit, subject/candidate, scope}` + identifier hợp lệ (`B7`…);
  serialize deterministic.
- Test: cùng packet ⇒ cùng chuỗi; header lệch ⇒ từ chối; identifier tách khỏi
  quantity.

### A2 — Hypothesis engine, AI1 lõi (1.5–2.5 ngày)

- `analyst.py`: `AnalysisRequest` → LLM call → structured output → map vào
  `HypothesisProposal`/`AnalysisResponse`.
- **`hypothesis_id` hệ sinh** từ content hash canonical; trùng nội dung ⇒
  dedupe; digest collision thật ⇒ refuse round.
- **Generation config capability-aware**: `effective_generation_config()` +
  `validate_generation_config()` (unsupported ⇒ refuse trước call). Precedence
  merge xác định: provider constructor defaults < model config < per-request
  config — merge xong mới flatten.
- **Flatten = canonical JSON Pointer, chống collision** (vòng 5 điểm 6): dotted
  key va chạm được (`{"thinking.type": "x"}` vs `{"thinking": {"type": "x"}}`).
  Dùng JSON Pointer (`/thinking/type`, `/output/effort`,
  `/sampling/temperature`), escape `~0`/`~1` theo RFC 6901, sort key trước
  checksum, **từ chối duplicate path sau flatten**. Checksum trên canonical
  JSON. Test: hai cấu hình khác nhau không thể cho cùng flattened
  representation. (Widen schema bundle thành recursive JSON = RFC dự phòng.)
- **Cache — hai chế độ key** (bundle chưa tồn tại trước A7):

  ```
  A2–A6 dev:  runtime_config_checksum = hash(prompt ‖ effective-config ‖
              retrieval-config ‖ catalog-version ‖ source_manifest_hash)
  A7 frozen:  bundle.identity_checksum
  ```

  **`source_manifest_hash` định nghĩa byte-level** (vòng 5 điểm 7), không phải
  "git tree" mơ hồ: glob cố định —

  ```
  services/analyst_service/**
  services/agent_service/planbench_agent/**
  packages/explanation/planbench_explanation/**
  schemas/tools/**
  docker/Dockerfile.analyst
  pyproject.toml, uv.lock, requirements*.txt
  ```

  sort relative path, hash (path ‖ file-content checksum) — **không dùng
  mtime**; dev tree bẩn vẫn hash đúng bytes đang chạy. Memoize per-call như
  bản 5; transcript + response checksum mọi call live.
- Offline = `MockProvider(script=[...])`; `DeterministicAnalystResponder`
  optional.
- `prompts.py` hằng số — nguồn `prompt_checksum`.
- Test: parse; trường lạ; dedupe/collision; unsupported config refuse;
  precedence; JSON Pointer collision; manifest hash bỏ mtime; hai chế độ cache.

### A3 — Self-guard + critic advisory (1–2 ngày)

- `guard.py` — gọi validator canonical, 5 luật pre-submit:
  1. mọi ref `supports`/`contradicts` tồn tại trong fact index;
  2. cấm numeric quantity trong statement (thập phân, `%`, sci-notation, số
     viết chữ lexicon en/vi); identifier khớp fact index được phép; số hiển thị
     do renderer lấy từ fact record. Test 5 ca;
  3. `proposition_type` ∉ `packet.blocked_claim_types`;
  4. requested_check theo lớp tool: `mechanism_check` ⇒ proposition ∈ card;
     `fact_query`/`evidence_navigation` ⇒ supported rỗng hợp lệ;
     `research_proposal` ⇒ spec-only;
  5. verb-guard `check_phrases(statement, "associated")`.
- Blocked proposal: loại khỏi final, giữ audit artifact kèm code; hết proposal
  ⇒ round abstention có reason; còn ⇒ không abstain.
- Critic = advisory: rerank + cờ, không xóa; log đủ ba; ablation A6.
- Test: từng luật; blocked-all/một-phần; critic không mất proposal.

### A4 — Seam + hai lane + JSONL ABI + gateway, AI3 (3–4.5 ngày)

#### A4.1. Seam + RoundSource — analysis và host bind từ cùng evidence source (vòng 5 điểm 1)

```python
class RoundHostProtocol(Protocol):
    def declare(self, response: AnalysisResponse) -> None: ...
    def call(self, request: ToolRequest) -> ToolResult: ...

class AnalystRunner(Protocol):
    def run(self, analysis: AnalysisRequest,
            host: RoundHostProtocol) -> AnalysisResponse: ...

class PreparedRound:
    analysis: AnalysisRequest      # available_evidence SUY TỪ evidence source
    host: RoundHostProtocol        # dựng từ CÙNG evidence source
    requested_budget_checksum: str # từ bundle.requested_budget
    effective_budget_checksum: str # min(requested, platform cap)
    evidence_identity_checksum: str  # gate artifact chứng minh round dựng từ gì

RoundSource = Callable[[PacketArtifact, AnalystBundle], PreparedRound]
```

- `HostSource(AnalysisRequest)` của bản 5 **bị loại**: `available_evidence` là
  field frozen của `AnalysisRequest` (mặc định rỗng — protocol.py:188), host
  dựng sau request là quá muộn, `admit()` chết ở `missing_required_evidence`
  (protocol.py:560) dù host có evidence thật. `RoundSource` dựng evidence
  source trước → suy `available_evidence` → dựng `AnalysisRequest` → dựng host
  từ cùng source → trả cặp đã bind. **Admission và evidence host không thể bất
  đồng.**
- In-process adapter: `declare()` → `host.session.declare(...)`; container
  proxy: `declare()` → frame. Hai lane cùng seam; runner không biết session.

#### A4.2. Vòng runner + revise-redeclare

```
engine → guard → host.declare(batch 1)
→ [tool_request → tool_result]*
→ revise (≤2 vòng): nội dung đổi ⇒ content hash mới ⇒ ID MỚI
    → host.declare(batch mới)    # TRƯỚC request tiếp theo
→ final AnalysisResponse
```

Proposal đã declare là immutable (`hypothesis_redefined` — protocol.py:427);
batch mới declare trước request mới; proposal bị thay giữ audit artifact với
`supersedes`; refuted loại khỏi final nhưng không xóa lịch sử.

#### A4.3. JSONL ABI

- `stdio_protocol.py` + spec doc. Frame set: `hello` · `analysis_request` ·
  `declare_proposals` · `declaration_ack` · `model_request`/`model_response` ·
  `tool_request`/`tool_result` · `final_response` · `error` · `done`.
- Envelope: `protocol_version` (= `ANALYST_RUNNER_PROTOCOL_VERSION`, vào bundle
  identity qua `runner_protocol_version`) · `analysis_run_id` · `bundle_id` ·
  `sequence` · `message_type` · `correlation_id` · payload theo schema ·
  **giới hạn kích thước THEO TỪNG LOẠI frame** — `model_response` trần riêng
  cao hơn vì mang `provider_turn` (hệ quả điểm 3), các frame khác trần chặt.
- Từ chối: frame sai phase · duplicate/out-of-order `sequence` · stdout chứa
  dòng không phải JSON ⇒ error + kill · EOF sớm ⇒ chấm như analyst raised ·
  response sau timeout ⇒ bỏ. `declare_proposals` ⇒ platform validate →
  `session.declare(...)` → `declaration_ack` → mới được `tool_request`.

#### A4.4. Model gateway + budget + restricted artifacts

- **Gateway**: container không credential, không outbound network. `model_request`
  → platform validate bundle/model/config/budget → provider bằng credential
  platform, config từ bundle khóa → `model_response`.
- **Round-trip `provider_turn` nguyên vẹn — JSON mapping, không phải bytes**
  (vòng 5 điểm 3 + vòng 6 điểm 5): type thật là
  `ProviderTurn(format: str, payload: Mapping[str, Any])` (provider.py:84 —
  Gemini `thought_signature`, Anthropic thinking blocks). Contract: payload bắt
  buộc JSON-compatible mapping; container **không inspect/modify**; round-trip
  giữ **deep structural equality + thứ tự array**; checksum trên canonical
  JSON, **không yêu cầu byte-identical serialization**; unknown format vẫn
  chuyển tiếp nguyên `format` + `payload`. Vendor cần binary payload ⇒ RFC mới
  với base64, không thiết kế trước. Test round-trip 3 ca: Anthropic thinking
  block · Gemini thought signature · unknown format (structural equality).
- **`AnalysisBudget` — source of truth, embed trong bundle** (vòng 5 điểm 4 +
  vòng 6 điểm 3/4, RFC platform):

  ```python
  class AnalysisBudget(BaseModel):
      max_tool_requests: int
      max_model_calls: int        # cumulative toàn round
      max_input_tokens: int       # cumulative, theo usage provider báo
      max_output_tokens: int      # cumulative, theo usage provider báo
      max_wall_time_ms: int       # monotonic deadline toàn round (provider + tool)
      max_frame_bytes: dict[str, int]   # theo loại frame

  class AnalystBundle:            # RFC: embed OBJECT, không chỉ checksum
      requested_budget: AnalysisBudget  # checksum suy từ object, vào identity
  ```

  Bundle chỉ mang checksum thì không dựng lại được limits để chạy — embed
  object, bundle tự mô tả đầy đủ, ít moving part. **Effective =
  min(requested, platform cap)**; gate/calibration report ghi cả requested lẫn
  effective. Luật: **effective của official calibration = effective của gate =
  effective của production; lệch ⇒ calibration vô hiệu, chạy lại** — platform
  siết cap thì recalibrate, không re-freeze bundle. Giá trị budget mặc
  định/preregistered nằm trong config artifact platform, **không để executor
  tự chọn**.
- **Token semantics khi thi hành** (vòng 6 điểm 4): per-call
  `LLMRequest.max_tokens = min(requested_per_call, output_tokens_remaining)`.
  Trước call: estimate input — vượt phần còn lại ⇒ refuse trước dispatch. Sau
  call: charge usage thật từ provider response. Estimate thấp hơn usage thật
  làm vượt budget ⇒ giữ response trong restricted audit, đánh round
  `budget_exceeded`, không cho call tiếp. Không retry provider call ngoài
  retry policy đã khóa trong effective config.
- **Restricted artifacts** (vòng 5 điểm 5 — network bị khóa nhưng stderr vẫn in
  được cả packet): stderr của hidden gate **chỉ platform truy cập**; không đưa
  raw stderr vào `GateDecision`/report gửi submitter; stderr có byte cap —
  vượt ⇒ truncate hoặc kill; error công khai chỉ gồm **mã lỗi đóng + case token
  vô danh** (không lộ case_id hidden); raw JSONL transcript, prompt, model
  response của hidden run cũng là restricted artifact — submitter chỉ nhận
  metric + mã lỗi.
- Sandbox: FS read-only, chỉ mount artifact cần thiết; CPU/memory/process/time
  limits; stdout chỉ protocol, log đi stderr.
- Dev in-process lane gọi provider trực tiếp; official calibration + gate bắt
  buộc lane container + gateway.

#### A4.5. Đọc ToolResult + RFC platform

- Non-completed ⇒ không đọc verdict; tôn trọng `unsupported_inferences`;
  `refuted` ⇒ rút proposal; `not_checkable` ⇒ InvestigationRecord giữ ở
  `not_checkable`, không checker-based promotion. 12 mã rejection theo mã.
- **RFC platform (gom một chỗ):** `gate.py` — nhận `RoundSource`, drive lane
  container, **fail-closed suite rule** (vòng 5 điểm 2):

  ```
  if not dry_run:
      require suite.visibility == "hidden"
      require suite.status == "preregistered"       # gate.py:169 hiện chỉ kiểm visibility
      require mọi PacketArtifact.fixture_kind == "recorded"
  ```

  cờ `allow_visible_suite` đổi tên `dry_run`. **Dry run tách type — không tạo
  `GateDecision`** (vòng 6 điểm 1): `analyst_visible()` chỉ nhận
  `GateDecision` (bundle.py:374), một dry run chứa decision bình thường là
  đường rửa điểm — caller lấy riêng decision và bật feature:

  ```python
  class DryGateRun:
      is_dry_run: Literal[True]
      score: SuiteScore            # KHÔNG có GateDecision

  class GateRun:
      is_dry_run: Literal[False]
      decision: GateDecision
  ```

  Dry run chỉ tạo score/report — không object nào đi qua được
  `verify_gate_decision()`.
  **Effective budget vào verification chain** (vòng 6 điểm 2):
  `GateDecision.effective_budget_checksum`; `GateRun` mang cả
  `requested_budget_checksum` + `effective_budget_checksum`;
  `verify_gate_decision(decision, targets=…, effective_budget=production_budget)`;
  `analyst_visible()` trả **false** nếu effective budget production khác budget
  đã được gate.
  `bundle.py` — thêm `runner_protocol_version` + **embed `requested_budget`**
  (§A4.4). `AnalysisBudget` + `PacketArtifact` loader vào
  `planbench_explanation`.
- Test: declare-trước-admit; revise-redeclare; RoundSource bind (evidence khớp
  admit); budget từng trục (tool/model/token/time/frame); sequence lệch; frame
  sai phase; non-JSON stdout; EOF sớm; timeout-kill; provider_turn round-trip 3
  ca; container không thấy credential; suite calibration + hidden ⇒ gate refuse
  khi không dry_run; stderr vượt cap.

### A5 — Knowledge provider, AI2 (0.5–1 ngày)

- `KnowledgeQuery` → `KnowledgeResult` (`MechanismReferenceCandidate` only),
  resolve qua `resolve_candidates()`, xử lý `RejectedReference`.
- KB toàn draft ⇒ AI2 chỉ mở rộng hypothesis search + trả reference candidate;
  `retrieval_score` không là confidence/evidence.
- v1 lexical match; vector DB chờ số đo A6.
- Test: không tự trả `review_status`/`source_refs`; entry lạ/lệch ⇒ rejected.

### A6 — Dev calibration + fixture source (1.5–2.5 ngày)

- Fixture root khớp suite: `fixtures/golden/visible/<case_id>/{packet.json,
  provenance.json}`.
- **`PacketArtifact` + loader platform validate** (không tin caller): recompute
  `packet_checksum` từ canonical CasePacket ⇒ lệch reject; load provenance
  canonical; recompute `provenance_checksum` ⇒ lệch reject; provenance phải trỏ
  đúng packet checksum + `packet_ref`; **`fixture_kind` do loader suy từ
  provenance đã validate**; hidden/preregistered gate chỉ nhận `recorded`.
- `harness.py`: `score_case`/`score_suite`, 6 họ, 6 metric
  `CALIBRATION_TARGETS`.
- Định nghĩa so sánh (ngưỡng đề xuất): thắng floor = structural 0 ∧ ≥
  `reference_analyst` cả 6 metric ∧ vượt hẳn ≥1 trong {precision, recall@3}.
  Critic bật = precision/abstention +≥0,05 ∧ recall@3 giảm <0,05 ∧ structural 0.
- Cache dev: `runtime_config_checksum`; nondeterminism run bypass cache;
  cache hit ≠ repetition — harness assert.
- Kết quả A6 không phải điểm nộp.

### A6.5 — Data readiness golden chính thức (platform, ngoài critical path)

3/6 họ stageable; 3 họ `CANNOT_STAGE_YET`. Platform: planted runs với sidecar →
packet fixture `recorded` → mở 3 họ còn lại → flip `OFFICIAL_GOLDEN_READY` →
preregister (suite status — điều kiện gate fail-closed §A4.5). A6 chuyển sang
packet thật khi xong.

### A7 — Freeze bundle + container + official calibration (1.5–2 ngày)

**Thứ tự: code xong → build container → freeze bundle → calibration chính
bundle đó → đổi gì rebuild + calibration lại → nộp.**

- Freeze đòi clean tree (`git status --porcelain` rỗng; bẩn ⇒ refuse);
  `agent_code_digest = git:<SHA>`.
- Model identity preflight; mọi response calibration cùng identity, lệch ⇒ hủy.
- `Dockerfile.analyst`; `container_digest` = digest image.
- `bundle_builder.py`: đủ field + `runner_protocol_version` +
  `requested_budget` (embed object, checksum vào identity) +
  `generation_parameters` (JSON Pointer flatten).
- **Official calibration = 3 lượt lane container + gateway, effective budget =
  budget của gate**, luật pass bảo thủ: structural 0 cả 3 · không
  protocol/runtime error · identity khớp preflight cả 3 · statistical metric
  lấy **minimum** so targets · **không retry**. Bypass cache (nondeterminism
  smoke test); report gắn `bundle_identity_checksum` + requested/effective
  budget.
- **Dry gate**: `run_gate(..., dry_run=True)` qua lane container — trả
  `DryGateRun` (score/report, không `GateDecision`).
- Test: tree bẩn refuse; thiếu field refuse; identity ổn định; calibration từ
  chối bundle chưa freeze; identity drift ⇒ hủy; lượt fail không retry;
  effective budget lệch gate ⇒ calibration vô hiệu.

### A8 — AI5 productization: TÁCH PLAN RIÊNG

Sau hidden gate pass. Scope tối thiểu: async route + job states + idempotency ·
flag theo `GateDecision` verified · timeout/cost budget (cùng `AnalysisBudget`
effective với gate) + degrade · artifact retention + transcript ·
authorization · fallback panel deterministic E4 · controlled rollout. Plan này
dừng ở bundle qua official calibration + dry gate.

## 4. Ngoài phạm vi

Fine-tune · vector DB (chờ A6) · hidden gate run (platform) · planted runs +
`OFFICIAL_GOLDEN_READY` (A6.5, platform) · AI5 (plan riêng) · AI paper-import.

## 5. Files chính

```
services/analyst_service/planbench_analyst/
  __init__.py  packet_view.py  prompts.py  analyst.py
  guard.py  runner.py  round_host.py  stdio_protocol.py  stdio_lane.py
  model_gateway.py  knowledge_provider.py  harness.py  bundle_builder.py
docker/Dockerfile.analyst
fixtures/golden/visible/<case_id>/{packet.json,provenance.json}
tests/test_analyst_packet_view.py  test_analyst_engine.py
tests/test_analyst_guard.py        test_analyst_runner.py
tests/test_analyst_stdio.py        test_analyst_gateway.py
tests/test_analyst_knowledge.py    test_analyst_harness.py
tests/test_analyst_bundle.py       test_analyst_fixtures.py
```

**RFC platform (gom một chỗ, diff có test):** `gate.py` (`RoundSource` +
fail-closed suite rule + `DryGateRun`/`GateRun` tách type + lane container) ·
`bundle.py` (`runner_protocol_version`, embed `requested_budget`,
`GateDecision.effective_budget_checksum`, `verify_gate_decision` +
`analyst_visible` đối chiếu effective budget) · `AnalysisBudget` +
`PacketArtifact` + loader (`planbench_explanation`) ·
`planbench_agent/provider.py` + 2 adapter (effective/validate generation
config). Ngoài ra: `pyproject.toml` · `scripts/dev_stack.sh` · `ruff.toml` ·
`docker/Dockerfile.api` (A0).

## 6. Kiểm chứng

**Mỗi phase:** `pytest tests/test_analyst_*.py` (MockProvider) + `ruff check`.

**Milestone — trước freeze bundle (cuối A7); lặp lại trước AI5 rollout:**

1. Full suite (ngoại lệ có chủ đích của luật "không full suite").
2. Explanation/gate regression.
3. Container smoke trên exact image digest, lane stdio + gateway.
4. Import-path test (+ trong container).
5. Dry gate visible suite (`dry_run=True`, artifact `is_dry_run`).
6. Failure-path: timeout-kill · frame sai phase · non-JSON stdout · EOF sớm ·
   malformed response · budget exhausted từng trục · host refusal (12 mã) ·
   provider unavailable · model identity drift · container không đọc được
   credential · provider_turn round-trip 3 ca (structural equality) · stderr
   vượt cap · suite chưa preregistered ⇒ gate refuse · dry run không sinh được
   object qua `verify_gate_decision` · `analyst_visible` false khi effective
   budget production lệch gate · token overshoot ⇒ `budget_exceeded`, response
   vào restricted audit, không call tiếp.

## 7. Ước lượng & thứ tự

A0 → A1 → A2 → A3 → A4 → A5 → A6 → A7 tuần tự: **~10.5–16 ngày** (A4 lên
3–4.5 vì RoundSource + budget + restricted artifacts). A6.5 song song platform.
AI5 = plan riêng.

## 8. Rủi ro

| Rủi ro | Giảm nhẹ |
|---|---|
| `available_evidence` rỗng ⇒ mọi tool chết `missing_required_evidence` | `RoundSource` dựng analysis + host từ cùng evidence source, trả cặp đã bind |
| Suite calibration chạy như gate thật | fail-closed: hidden + preregistered + mọi packet recorded; dry run tách type |
| Dry run tạo `GateDecision` bật được feature | `DryGateRun` không chứa decision — không object nào qua `verify_gate_decision` |
| Mất `provider_turn` ⇒ revise call bị vendor từ chối | round-trip JSON mapping, structural equality + thứ tự array; test 3 ca kể cả unknown format |
| Budget không source of truth ⇒ ba môi trường ba hệ | `AnalysisBudget` embed trong bundle (identity); effective = min(requested, cap) vào `GateDecision` + `verify_gate_decision` + `analyst_visible`; lệch ⇒ calibration vô hiệu / flag off |
| Token estimate thấp hơn usage thật | charge usage provider báo; overshoot ⇒ `budget_exceeded` + restricted audit + dừng call |
| Hidden lộ qua stderr/log/transcript | restricted artifacts: stderr platform-only + byte cap; error công khai = mã đóng + token vô danh; transcript/prompt/response hidden = restricted |
| Flatten collision ⇒ hai config cùng checksum | canonical JSON Pointer + escape RFC 6901 + reject duplicate path + test |
| source-tree hash mơ hồ | manifest byte-level glob cố định, sort path, hash content, không mtime |
| Container không declare được / exfiltrate | frame declare/ack; không credential, không network, FS read-only |
| "Best of N" lẻn vào calibration | minimum 3 lượt, structural 0 cả 3, không retry |
| Model overclaim / bịa số | schema tước quyền + cấm numeric quantity + validator canonical + promotion authority |
| Coupling agent_service | chỉ import provider layer; digest repo-level; tách shared package khi cần |
