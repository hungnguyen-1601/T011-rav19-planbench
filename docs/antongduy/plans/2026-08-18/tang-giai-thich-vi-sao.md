# Plan — Tầng giải thích "vì sao" (Explanation Layer) — bản 7

**Ngày:** 2026-08-18 · **Trạng thái:** chờ An approve · tên branch replay An cung cấp lúc thi hành
**Bản 7 (vòng 6) — siết các chỗ contract còn tin lời tự khai:** promotion matrix chỉ đọc
`proposition_policy` typed, văn xuôi không vào code path; tách `execution_status` /
`proposition_verdict` + khóa một enum provenance duy nhất; RAG chỉ trả reference
candidate, platform resolve từ canonical KB; hidden gate chạy trên **AnalystBundle bất
biến** trong môi trường platform kiểm soát.
**Thiết kế nguồn:** `notes/2026-08-18/tongduyan_giai-phap-giai-thich-vi-sao-thuat-toan-thang.md` (v2)
**Bản 6 — đổi định hướng AI (vòng 5):** plan này **không xây AI** (không model, prompt,
RAG, tool routing, agent loop) — nó **sở hữu dữ liệu, contract và gate** để một AI
subsystem bên ngoài đọc tình huống và bị chấm. Ba quyết định chốt cùng An:
① tool host + mechanism-check tools do **platform** hiện thực (checker là trusted base
của promotion gate — nhóm bị chấm không hiện thực thứ đóng dấu cho mình);
② **platform giữ hidden subset và tự chạy gate run** qua AnalysisRequest interface;
③ KB matcher deterministic **giữ trong plan** — panel không-AI giữ được mức "Suy luận
phù hợp". (Lịch sử bản 2–5: xem git.)

---

## 1. Mục tiêu

Decision Card trả lời *ai thắng*; tầng này trả lời *vì sao*, hiển thị theo **4 mức bằng
chứng** (`observed → associated → mechanism_verified → intervention_supported`) +
qualifier; "Chưa đủ bằng chứng" = không có claim. Tầng deterministic tự đứng được;
AI subsystem (plan riêng của nhóm AI) chỉ làm giàu thêm qua giao thức ở §3.

## 2. Ranh giới trách nhiệm

**Plan này SỞ HỮU (đặc tả + hiện thực):**
- Case packet và toàn bộ dữ liệu đầu vào (detectors, map features, contrast, waterfall,
  exemplars, sidecar `PlanningInputEvidence`).
- Schema `AnalysisRequest` / `HypothesisProposal` / `InvestigationRecord` / `Claim`.
- Tool catalog contract: `ToolCard` / `ToolRequest` / `ToolResult` — input/output schema,
  ý nghĩa chính xác của kết quả, provenance, checksum, version, failure modes, **trần
  bằng chứng của từng tool**.
- **Tool host + mechanism-check implementations** (①): `gap_vs_footprint`,
  `replay_global_plan`, `latency_vs_expanded_nodes`, `rrt_convergence` — đặc tả ở E5,
  hiện thực ở E6 (lịch phối hợp H4/H6). Fact-query và evidence-navigation tools cũng
  platform — chúng là API đọc dữ liệu plan này sở hữu.
- Research/evaluation lane policy; claim ledger + deterministic promotion gate.
- KB v1 curated + **matcher deterministic** (③) — không LLM.
- Golden: planted-case schema, packet fixtures, đáp án preregistered, **hidden subset +
  gate harness do platform giữ và chạy** (②).
- UI fallback không cần AI + feature flag cho external analyst.

**Plan này CHỈ ĐẶC TẢ, không hiện thực:** mechanism knowledge provider / RAG endpoint
(contract §3.4) · research experiment executor (chỉ specification).

**NGOÀI PHẠM VI hoàn toàn** (thuộc plan AI1–AI5 của nhóm AI): chọn model · system
prompt · agent planning · thuật toán chọn tool · RAG chunking/embedding/reranking ·
vector DB · model memory · retry/reflection loop · fine-tuning · chạy và tối ưu
evaluation để đạt gate · vận hành API model.

## 3. AI Enablement Contract — giao thức tích hợp (không phải thiết kế Agent)

```
Platform tạo CasePacket
        ↓
External Analyst sinh HypothesisProposal
        ↓
External Analyst yêu cầu tool bằng ToolRequest
        ↓
Tool host (platform) xác thực request và thực thi
        ↓
ToolResult có provenance quay lại hệ thống
        ↓
Deterministic promotion tạo InvestigationRecord/Claim
        ↓
UI render Claim — không bao giờ render trực tiếp lời model
```

### 3.1. ToolCard — mỗi tool trong catalog

```yaml
tool_id: gap_vs_footprint
tool_version: 1.0.0
title: Check geometric passage feasibility
purpose:                                 # VĂN XUÔI — tài liệu cho người và nhóm AI,
  verifies:                              # KHÔNG tham gia code path
    - "Required clearance exceeds measured passage width."
  does_not_verify:
    - "This mechanism caused the complete utility difference."
    - "The global planner actually attempted this passage."
proposition_policy:                      # TYPED — thứ duy nhất promotion matrix đọc
  supported_proposition_types: [geometric_infeasibility]
  forbidden_inference_types: [complete_utility_attribution]
  maximum_claim_level: mechanism_verified
execution: {mode: deterministic, side_effects: none, lane: diagnostic,
            estimated_cost: low, timeout_ms: 1000, idempotent: true}
preconditions:
  required_evidence: [map_checksum, region_geometry, robot_footprint,
                      inflation_parameters, inflation_implementation_version]
input_schema_ref:  schemas/tools/gap_vs_footprint.request.json
output_schema_ref: schemas/tools/gap_vs_footprint.result.json
evidence_policy:
  allowed_input_provenance: [recorded, verified_reconstruction]
failure_modes:
  - {code: region_not_resolved}
  - {code: missing_footprint}
  - {code: implementation_version_unknown}
  - {code: ambiguous_passage_geometry}
```

Promotion matrix đọc **`proposition_policy` + `evidence_policy`** — hai khối typed enum.
`verifies`/`does_not_verify` là chuỗi tự do phục vụ người đọc; chuỗi tự do quyết định
logic máy là mở cửa cho drift và game. Hai lớp phải nhất quán — có test đối chiếu
mỗi dòng prose có dòng typed tương ứng.

### 3.2. ToolRequest / ToolResult

```yaml
ToolRequest:
  request_id: req-017
  analysis_run_id: run-…       # nối request/result vào đúng vòng phân tích
  case_packet_checksum: …      # đúng packet
  tool_catalog_version: …      # đúng catalog
  analyst_bundle_id: …         # đúng phiên bản analyst (§6)
  sequence: 3                  # thứ tự trong vòng
  tool_id: gap_vs_footprint
  tool_version: 1.0.0
  hypothesis_id: hyp-004
  arguments: {candidate_id: …, episode_context_id: …, region_id: aisle_B7}
  evidence_refs: [map:…, candidate:…]

ToolResult:                    # CHỈ tool host được tạo/ký — model không tự tạo được
  request_id: req-017
  tool_id: gap_vs_footprint
  tool_version: 1.0.0
  execution_status: completed        # completed | rejected | failed | not_checkable
  proposition_verdict: supported     # supported | refuted | inconclusive
  input_provenance: recorded         # enum khóa: recorded | verified_reconstruction
                                     #            | reconstructed | missing
  measurements: {passage_width_m: 0.68, required_clearance_m: 0.74, margin_m: -0.06}
  supported_propositions:
    - {proposition_id: geometric_infeasibility_at_B7, result: supported}
  unsupported_inferences: [complete_utility_attribution]   # cùng enum forbidden_inference_types
  evidence_artifact_ref: …
  evidence_checksum: …
  implementation_ref: …        # git SHA / docker digest của checker
```

Ba luật đi kèm: **(a)** `execution_status` nói tool chạy thế nào, `proposition_verdict`
nói mệnh đề đứng hay đổ — không bao giờ dùng chung một chữ `pass` cho cả hai;
**(b)** `proposition_verdict` mức top-level chỉ hợp lệ cho tool khai đúng **một**
proposition; tool đa-proposition bỏ top-level, verdict nằm trong từng entry;
**(c)** enum provenance khóa một bộ duy nhất toàn hệ (`recorded` /
`verified_reconstruction` / `reconstructed` / `missing`) — `not_checkable` là
`execution_status`, không phải provenance; mọi cách viết cũ
(`recorded_or_verified_reconstruction`) quy về bộ này.

### 3.3. Bốn lớp tool trong catalog

| Lớp | Ví dụ | Trần bằng chứng |
|---|---|---|
| **Fact-query** | `get_objective_decomposition`, `get_episode_observations`, `get_candidate_contrast`, `get_map_region_features`, `get_known_unknowns` | thường `observed` |
| **Evidence-navigation** | `find_exemplar_episodes`, `get_replay_window`, `get_trajectory_segment`, `get_event_neighborhood` | không promote claim — chỉ trả evidence references |
| **Mechanism-check** | `gap_vs_footprint` (trần `mechanism_verified`), `replay_global_plan`, `latency_vs_expanded_nodes` (trần `associated` — deterministic ≠ causal), `rrt_convergence` | theo card từng tool |
| **Research-proposal** | `build_component_swap_spec`, `build_parameter_intervention_spec`, `build_task_perturbation_spec` | chỉ sinh specification: `execution_authorized: false`, `required_lane: research` — không tool nào tự chạy experiment |

### 3.4. Knowledge/RAG contract — chỉ định nghĩa đầu ra, không thiết kế retrieval

RAG thuộc nhóm AI ⇒ **platform không tin trường tự khai nào từ nó** — `review_status:
approved` tự khai chính là ca provider khai `provenance="oracle"` mà H3 đã chặn bằng
allowlist. RAG chỉ trả **khóa tham chiếu**:

```yaml
KnowledgeQuery:
  task_features: […]  candidate_components: […]  observations: […]
  excluded_mechanisms: […]
KnowledgeResult:
  entries: [MechanismReferenceCandidate…]
  kb_version: …  retrieval_version: …
MechanismReferenceCandidate:            # RAG trả — chỉ khóa + điểm retrieval
  knowledge_base_id: navigation-mechanisms
  entry_id: inflation_gap_closure
  entry_version: 2
  retrieved_for: {hypothesis_id: hyp-004}
  retrieval_score: 0.83
```

```
RAG reference candidate
    ↓
Platform canonical KB lookup (KB của E3 — nguồn duy nhất)
    ↓
review_status / source_refs / applicability_conditions CHÍNH THỨC
```

Luật resolve: entry không tồn tại ⇒ reject · `entry_version` không khớp ⇒ reject ·
entry chưa `approved` ⇒ không dùng để promote claim · RAG không bao giờ tự cung cấp
nội dung authoritative. Không nói embedding/chunk/rerank nào — retrieval là việc của
nhóm AI; nguồn chân lý là canonical KB.

## 4. Ràng buộc (giữ từ bản 5, còn hiệu lực nguyên)

1. Không chạm 3 khóa cứng contract + không chạm schema Manifest gốc; tham chiếu một
   chiều từ explanation artifact (source_manifest_ref/checksum + 5 version).
2. Claim ledger 100% deterministic-gated; tước quyền bằng schema (proposal không có
   trường status/confidence/impact); `impact_ref` tách `observed_contribution` /
   `attributable_effect_estimate`, template khóa cách nói.
3. Provenance replay: run cũ kẹt `reconstructed`/trần `associated`; output-plan so bytes
   chỉ là refuter; `plans=[]` ⇒ `not_checkable`; kiểm git SHA/docker digest trước replay.
4. Research: mọi tool chỉ sinh spec; execution chờ runner enforce policy end-to-end.
5. `known_unknowns` cấu trúc, orchestrator cưỡng chế `blocks_claim_types`.
6. Panel degrade an toàn; **UI không bao giờ render trực tiếp lời model**.

## 5. Các đợt (platform)

| Đợt | Nội dung | Ước lượng |
|---|---|---|
| **E0** | Explanation contracts: ledger schemas (Proposal/Record/Claim/EvidenceRef/CheckerResult), promotion matrix (claim type × tool × verdict × provenance, đọc từ ToolCard), `PlanningInputEvidence` spec + validator, `impact_ref` hai loại, artifact versioning | 1–2 ngày |
| **E1** | Waterfall paired ΔU + CI marginal (copy khóa test) + drill-down hai mức utility | 1–2 ngày |
| **E2** | Audit/merge branch replay + progress-sync (`projection_quality` + fallback) + exemplar preregistered + regression | 2–4 ngày sau audit |
| **E3** | Detectors → Observation · map features (khe hẹp nhất + mật độ vật cản; **topology và số ngã rẽ hoãn sang E3.5**) · contrast graph 4 đầu ra · **KB v1 + matcher deterministic** (`source_strength`/`review_status`, không tham gia promotion) | 4–5 ngày |
| **E3.5** | Map topology + số ngã rẽ (Voronoi/skeleton). Tách ra vì cần một phép phân tích hình học riêng, và một nhãn topology đoán ra đặt cạnh số đo thật là điều tệ hơn không có nhãn. Cũng là thứ detector "chọn nhánh khác tại ngã rẽ" (§4.2 note) đang chờ. | 1–2 ngày, sau E4 |
| **E4** | CasePacket builder + claim ledger nối liền + render template (khóa cách nói theo mức và impact_kind) + ma trận UI 5 kết cục run **(đã cắm vào trang + i18n)** | 2–3 ngày |
| **E4.1** | Endpoint packet/ledger. Vướng một quyết định thật: dựng packet cần đọc trace mọi episode để chạy detector ⇒ **dựng lúc chấm** (đọc rẻ, phải bump report) hay **dựng theo yêu cầu + cache** (report không đổi, request đầu nặng). Chờ An chốt. | 1 ngày sau khi chốt |
| **E4.5** | Minimal sidecar writer `PlanningInputEvidence` — mọi attempt kể cả `no_path`; neo `AlgorithmHost`; seam chưa ổn ⇒ hoãn sau H4/H6 + luật "không golden chính thức trước khi writer sẵn sàng" | 1–2 ngày |
| **E5** ✅ | **AI enablement** (xong 19-08): AnalysisRequest/ToolRequest/ToolResult + ToolSession · catalog 16 card đủ 4 lớp · AnalystBundle + GateDecision + feature flag · knowledge contract §3.4 · research specification schema · golden format + 12 case visible (calibration, **không** preregistered — chặn bằng `OFFICIAL_GOLDEN_READY=False`) · mock tool host + reference analyst · 72 test | 3–5 ngày |
| **E6** | **Tool host + mechanism-check implementations** (platform, ①) + **gate harness**: platform giữ hidden subset, chạy **AnalystBundle bất biến** (§6) trên hidden packets trong môi trường platform kiểm soát, tự chấm, quyết định bật flag (②). Lịch phối hợp H4/H6 | 4–6 ngày |

E5 **không** deliver: LLM client, prompt, RAG, tool routing, AI evaluation run, model backend.
E5 cũng **không** deliver checker thật (E6) và **không** dựng được packet fixture cho golden
— cần sidecar E4.5; `PlantedCase.packet_ref` hiện là đường dẫn chưa resolve.

Chi tiết kỹ thuật từng đợt E0–E4.5 giữ nguyên như bản 5 (waterfall mean-only + marginal
CI; exemplar recipe; contrast graph; sidecar validator; ma trận UI CLEAR /
NEAR_EQUIVALENT / no_survivors / gate_only / interrupted).

## 6. Golden evaluation — acceptance contract cho AI subsystem

> Bộ golden và metric là acceptance contract; triển khai, chạy calibration và tối ưu
> agent để đạt gate là trách nhiệm của owner AI subsystem. **Gate run trên hidden do
> platform thực hiện** — nhóm AI không cầm hidden, và **nộp bundle, không nộp report**.

**AnalystBundle — đơn vị được chấm là một bundle bất biến, không phải một endpoint sống.**
Endpoint do nhóm AI vận hành có thể log hidden packets, đổi prompt giữa gate run, deploy
code mới trong lúc chấm, hoặc nhận diện gate để trả hành vi riêng — report từ đó không
tái lập được:

```yaml
AnalystBundle:
  bundle_id: …
  agent_code_digest: …          container_digest: …
  model_id: …                   model_revision: …
  prompt_checksum: …            rag_index_version: …
  retrieval_config_checksum: …  tool_catalog_version: …
  generation_parameters: …      created_at: …
```

Platform chạy bundle trong môi trường platform kiểm soát. Model là API ngoài:
platform giữ credential, platform gửi request, prompt/config lấy từ bundle đã khóa,
nhóm AI không được thay endpoint logic trong gate, toàn bộ response lưu checksum.
`analyst_bundle_id` xuất hiện trong mọi ToolRequest (§3.2) — mọi vòng phân tích truy
được về đúng bundle. **Rủi ro tồn dư phải khai, không giả vờ bundle giải quyết hết:**
với API model, hidden packet vẫn rời platform tới vendor; và bundle không khóa được
nondeterminism của API — đo bằng repeated runs, giảm nhẹ bằng hidden rotation theo
version (đã có §6 trình tự khóa).

- Platform cung cấp, **tách theo đợt** (sửa 19-08 — bản trước gộp hết vào E5 trong khi
  packet fixture phụ thuộc writer chưa có, tự mâu thuẫn với bảng §5):
  - **E5**: planted-case schema · expected hypothesis IDs · expected abstention cases ·
    expected checker requests · forbidden claims · metric definitions + scorer ·
    **visible calibration skeleton** (12 case, `status="calibration"`).
  - **E4.5**: packet fixtures thật, có provenance chính thức — mọi họ dựa trên replay
    cần sidecar ghi planning input đúng lúc xảy ra.
  - **E6**: hidden suite · gate harness chạy AnalystBundle · preregistration thật.
  Cưỡng chế bằng `OFFICIAL_GOLDEN_READY` trong `golden.py`: `status="preregistered"`
  bị từ chối cho tới khi writer sẵn sàng.
- Bộ **chính thức** (E4.5 + E6): **6 họ × 12–20 biến thể (72–120 packet)** — inflation đóng khe · DWA local
  minimum · RRT\* thiếu sample · expansion gây latency · negative control ·
  confounded/insufficient-evidence. Mỗi họ có positive / negative / ca phải abstain /
  biến thể gần ranh giới. Báo macro-average theo họ + micro-average.
- Target calibration (chưa đóng băng; precision + abstention ưu tiên hơn recall):
  invariant cấu trúc = 0 tuyệt đối (ledger contamination, unsupported rendered
  assertion, blocked claim leakage); statistical: precision ≥ 0,90 · recall@3 ≥ 0,70 ·
  abstention ≥ 0,90 · component-attribution ≥ 0,85 · checker-selection ≥ 0,90.
- Trình tự khóa: metric + protocol → nhóm AI chạy visible calibration → thương lượng
  threshold → **platform duyệt + preregister** → khóa prompt/model/KB/catalog →
  platform mở hidden đúng một lần. Version mới ⇒ hidden subset mới.

## 7. Plan phía nhóm AI (tham chiếu, ngoài plan này)

AI1 analyst implementation · AI2 RAG/knowledge provider (trả reference candidate theo
§3.4, không trả nội dung authoritative) · AI3 tool **integration** (gọi tool host
platform — không hiện thực checker) · AI4 chạy calibration + **nộp AnalystBundle** cho
gate run · AI5 controlled rollout sau flag.

## 8. Thứ tự và phụ thuộc

```
E0 ──> E1 ──┐
E0 ──> E2 ──┼──> E4 ──> E4.5 ──> E5 ──> E6 (phối hợp H4/H6)
E0 ──> E3 ──┘                     └──> nhóm AI bắt đầu AI1/AI2 song song trên mock E5
```

E0–E4 chỉ đọc artifact; E4.5 writer phía runner; E6 thực thi planner ở chế độ chẩn đoán.
Nhóm AI khởi động ngay khi E5 xong — không chờ E6 (mock/stub đủ để tích hợp).

## 9. Quyết định — chốt / còn treo

**Đã chốt (vòng 4 + 5):** sidecar E4.5 + luật golden chờ writer · threshold =
calibration target, platform preregister · LLM offline/async, nút "Phân tích nguyên
nhân", interface trung lập, version mới không ghi đè · golden 6 họ × 12–20 ·
checker + tool host = platform (E6) · hidden gate platform chạy · KB matcher giữ E3.

**Đã chốt thêm (19-08):** khoản treo "tên branch replay" đóng — đối tượng audit là
UI hai canvas merge ở `d3ba3b6`, xem `notes/2026-08-19/tongduyan_audit-ui-hai-canvas-cho-e2.md`
· progress-sync đi đường fallback trước, API sau · ΔU theo episode ghi vào report
lúc chấm (`episode_decision_utility`) · **topology + số ngã rẽ tách thành E3.5**,
không nằm trong định nghĩa "E3 xong".

**Đã chốt thêm (19-08, sau E5):** đơn vị được chấm là AnalystBundle bất biến, feature flag
suy ra từ GateDecision chứ không phải cờ ai bật cũng được · golden chưa được preregister
cho tới khi có writer E4.5, cưỡng chế bằng hằng số nền tảng · mock host trả
`not_checkable` cho mọi mechanism-check cho tới E6.

**Còn treo:** thứ tự E1–E3 (một người ⇒
đề xuất E1 → E3 → E2) · lịch E6 khớp H4/H6 · E4.1 cách dựng packet (chờ An) ·
duyệt KB v1 để entry được phép đỡ claim.

## 10. Rủi ro chính

| Rủi ro | Giảm nhẹ |
|---|---|
| Nhóm AI đọc ToolResult mạnh hơn nghĩa thật | `proposition_policy` typed + `unsupported_inferences`; prose không vào code path, có test đối chiếu prose↔typed |
| Model tự tạo ToolResult / tự đóng dấu | chỉ tool host ký; proposal không có trường số/status; ledger deterministic |
| Hidden gate mất hiệu lực | platform giữ hidden + chạy AnalystBundle bất biến trong môi trường platform; version mới ⇒ hidden mới |
| Endpoint analyst đổi hành vi giữa gate run | bundle digest toàn phần (code/container/model/prompt/RAG index); platform giữ API credential; response checksummed |
| RAG tự khai review_status/nội dung | chỉ nhận MechanismReferenceCandidate; resolve từ canonical KB; entry lạ/lệch version ⇒ reject |
| Hidden lộ tới vendor API model | rủi ro tồn dư khai rõ; hidden rotation theo version; không tái dùng hidden đã mở |
| Checker do bên bị chấm hiện thực | đã loại — checker platform-owned (E6) |
| Contract E5 đóng băng sớm, nhóm AI cần đổi | tool_version + schema version; thay đổi qua RFC hai bên, không sửa tại chỗ |
| Writer E4.5 đụng H-series | neo AlgorithmHost, phối hợp H4/H6; golden chờ writer |
| Sidecar bỏ sót attempt thất bại | outcome path/no_path/error + validator "mọi attempt có dòng" |
| `observed_contribution` render thành nhân quả | impact_kind + template khóa, có test |
| UI lộ lời model | luật "chỉ render Claim" + test render |
