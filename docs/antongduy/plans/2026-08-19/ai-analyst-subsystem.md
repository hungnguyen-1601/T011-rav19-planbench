# Plan — AI Analyst subsystem (AI1–AI4): agent sinh giả thuyết "vì sao thuật toán thắng"

**Ngày:** 2026-08-19 · **Trạng thái:** chờ An approve
**Thiết kế nguồn:** `plans/2026-08-18/tang-giai-thich-vi-sao.md` (bản 7) §3/§6/§7 ·
`notes/2026-08-18/tongduyan_giai-phap-giai-thich-vi-sao-thuat-toan-thang.md` (v2) §6–§7
**Tiền đề:** E0–E4 xong; **E5 đang làm song song — plan này coi như E5 đã có**, code
against spec qua một shim tập trung, E5 hoàn tất thì reconcile (phase A7).

---

## 1. Context

Tầng giải thích đã chốt ranh giới: platform sở hữu dữ liệu/contract/gate (E0–E6),
AI subsystem là plan riêng (AI1–AI5). Đây là plan của AI subsystem đó — agent đọc
CasePacket, sinh `HypothesisProposal`, gọi tool qua catalog đóng, nộp AnalystBundle
cho gate. Platform đã có đủ để nhận nó: `CasePacket` + builder, `HypothesisProposal`
(schema tước quyền — không có trường status/confidence/impact), `ToolCard`/`ToolCatalog`,
promotion matrix, KB v1 + `resolve()`, render template.

**Quyết định đã chốt với An (2026-08-19):**

- **2 agent riêng, chung model backend** — không nhét analyst vào AI paper-import
  của đồng nghiệp. Chung: model provider, harness code, hạ tầng. Riêng: prompt,
  tool catalog, output schema, bundle, gate. Hai con giao nhau duy nhất qua dữ liệu
  platform (plugin → trace → CasePacket), không qua code.
- E5 đang làm ⇒ shim + reconcile sau, không chờ.
- **Tái dùng trực tiếp** tầng LLM provider của M8:
  `services/agent_service/planbench_agent/` (`LLMProvider`, `LLMRequest.output_schema`,
  `AnthropicProvider` mặc định `claude-opus-5`, `MockProvider`, `DeterministicResponder`,
  `factory.build_provider`).
- Code mới đặt ở **`services/analyst_service/planbench_analyst/`** — thứ bị gate chấm
  nằm trọn một chỗ, AnalystBundle digest trỏ vào đây.
- **Không fine-tune** — golden 72–120 packet quá nhỏ để train; mọi ràng buộc chất
  lượng nằm ở contract + prompt + guard, không nằm ở weights.

**Nguyên tắc bất biến (từ plan bản 7):** analyst không bao giờ đọc Parquet thô,
không tự đóng dấu, tool menu đóng, mọi con số phải có trong packet; LLM không bao
giờ là nguồn của một con số hay kết luận nhân quả.

## 2. Tái dùng (không viết mới)

| Có sẵn | Ở đâu | Dùng cho |
|---|---|---|
| `LLMProvider`/`LLMRequest`/`MockProvider`/`build_provider` | `services/agent_service/planbench_agent/provider.py`, `factory.py` | mọi lời gọi model |
| `HypothesisProposal`, `RequestedCheck`, `EvidenceRef` | `packages/explanation/planbench_explanation/ledger.py` | output schema của analyst — import thẳng, không định nghĩa lại |
| `CasePacket`, `build_case_packet`, `.blocked_claim_types` | `case_packet.py` | input duy nhất |
| `ToolCard`/`ToolCatalog`/`PropositionPolicy` | `tools.py` | kiểm tool-selection phía client |
| `check_phrases`, `PhrasePolicy` | `levels.py` | verb-guard trên hypothesis_statement |
| `canonical_propositions`, `require_assertable`, `canonical_subjects` | `propositions.py`, `subjects.py` | validate output |
| `knowledge.match`/`resolve`, `KNOWLEDGE_BASE` | `knowledge.py` | AI2 v1 (KB 5 entry — chưa cần vector DB) |
| `artifact_checksum` | `versioning.py` | cache key, bundle digest |

## 3. Các phase

### A0 — Skeleton + E5 shim (0.5–1 ngày)

- Tạo `services/analyst_service/planbench_analyst/` (`__init__.py` có boundary
  docstring theo phong cách `planbench_agent`).
- `contracts_shim.py` — **một file duy nhất** chứa mọi type E5 chưa tồn tại, mirror
  đúng plan bản 7: `ToolRequest`/`ToolResult` (§3.2, đủ correlation fields:
  `analysis_run_id`, `case_packet_checksum`, `tool_catalog_version`,
  `analyst_bundle_id`, `sequence`), `AnalysisRequest`, `AnalystBundle` (§6),
  `KnowledgeQuery`/`KnowledgeResult`/`MechanismReferenceCandidate` (§3.4).
  Pydantic `frozen=True, extra="forbid"` như convention explanation. Mỗi class đánh
  dấu `E5-SHIM` — reconcile = diff một file.
- Wire path: thêm vào `pyproject.toml [tool.pytest.ini_options] pythonpath`,
  `scripts/dev_stack.sh` PY_PATH, `ruff.toml known-first-party` (guard test
  `tests/test_dev_stack_pythonpath.py` sẽ bắt nếu thiếu). Ghi chú:
  `docker/Dockerfile.api` PYTHONPATH đang thiếu cả `packages/explanation` — chưa
  sửa trong plan này, chỉ ghi nhận.
- Test: `tests/test_analyst_contracts.py` — schema rejection (ToolResult không cho
  analyst tự tạo trường verdict tự do, bundle thiếu digest bị từ chối…).

### A1 — Packet view + fact index (0.5 ngày)

- `packet_view.py`: nhận `CasePacket`, validate header versions khớp bản đang chạy,
  dựng **fact index** (mọi ref citable: observation, waterfall objective, map
  feature, exemplar, kb citation, mọi số kèm đơn vị) và serialize packet thành text
  deterministic cho prompt (ordering cố định — cùng packet cùng prompt).
- Test: cùng packet ⇒ cùng chuỗi; số trong index khớp packet; packet header lệch
  version ⇒ từ chối.

### A2 — Hypothesis engine, AI1 lõi (1–2 ngày)

- `analyst.py`: một agent, không multi-agent — packet nhỏ, menu tool đóng,
  multi-agent thừa. Vòng: packet view → LLM call (system prompt encode thang 4 mức,
  8 subject, 4 ranh giới cứng, danh sách proposition assertable) → structured output
  qua `LLMRequest.output_schema` = danh sách `HypothesisProposal` + abstentions.
- Deterministic: temperature 0 qua generation params trong bundle; cache theo
  `(artifact_checksum(packet), bundle_id)`; chạy được không cần API key nhờ
  `MockProvider`/`DeterministicResponder` (đúng pattern factory M8: thiếu key ⇒
  mock, chọn tường minh mà không dùng được ⇒ raise).
- Prompt đặt trong `prompts.py` như hằng số (checksum được — `prompt_checksum`
  của bundle tính từ đây).
- Test với `MockProvider` scripted: parse đúng, proposal có trường lạ ⇒ parse error,
  model trả text tự do ⇒ retry/refuse.

### A3 — Self-guard + critic pass (1–2 ngày)

- `guard.py`, chạy sau engine, trước khi nộp — mirror check của platform để rớt ở
  đây thay vì rớt gate:
  1. mọi ref trong `supports`/`contradicts` tồn tại trong fact index;
  2. mọi số xuất hiện trong `hypothesis_statement` khớp một số trong packet;
  3. `proposition_type` không nằm trong `packet.blocked_claim_types`
     (known_unknowns) — vi phạm ⇒ chuyển thành abstention có `missing_evidence`;
  4. `requested_checks` tồn tại trong catalog + `proposition_type` ∈
     `supported_proposition_types` của card (metric gate checker-selection ≥ 0,90);
  5. verb-guard: `check_phrases(statement, "associated")` — hypothesis chưa được
     verify thì không được dùng động từ mức cao hơn.
- Critic pass: lời gọi LLM thứ hai, prompt "bác bỏ hypothesis này chỉ bằng packet";
  bị bác ⇒ rớt hoặc hạ thành abstention. Precision + abstention là hai target gate
  ưu tiên (≥ 0,90) — pass này ăn thẳng vào đó.
- Test: từng luật guard một fixture vi phạm.

### A4 — Tool loop client, AI3 (1–2 ngày)

- `tool_client.py`: dựng `ToolRequest` (shim) đủ correlation fields + `sequence`
  tăng dần; budget cứng (mặc định: ≤ 3 vòng, ≤ 8 request/vòng phân tích); đọc
  `ToolResult` — tôn trọng `unsupported_inferences` (không suy mạnh hơn),
  `execution_status != completed` ⇒ không đọc verdict.
- `testing/mock_host.py`: mock tool host trả canned `ToolResult` theo fixture
  (đánh dấu E5-SHIM — host thật là E6 platform). Đây là stub tích hợp để analyst
  phát triển không chờ E6, đúng §8 plan bản 7 ("nhóm AI bắt đầu song song trên
  mock E5").
- Vòng đầy đủ: proposals → guard → requests → mock results → revise (1 lời gọi LLM
  đọc results) → final proposals + abstentions.
- Test: budget bị vượt ⇒ dừng sạch; result `refuted` ⇒ proposal bị rút;
  `not_checkable` ⇒ hypothesis đứng ở associated.

### A5 — Knowledge provider, AI2 v1 (0.5–1 ngày)

- `knowledge_provider.py`: nhận `KnowledgeQuery`, trả `KnowledgeResult` chứa
  **chỉ** `MechanismReferenceCandidate` (entry_id + entry_version +
  retrieval_score). KB hiện 5 entry curated ⇒ v1 dùng lexical match (tái dùng
  `knowledge.match` + tokenizer của `planbench_agent/rag.py` nếu cần scoring);
  **không vector DB** — đo bằng harness A6 trước, chỉ nâng cấp nếu recall kém.
- Resolve luôn qua `knowledge.resolve()` (canonical) — test khẳng định provider
  không bao giờ tự trả `review_status`/`source_refs`.

### A6 — Calibration harness + AnalystBundle, AI4 (1–2 ngày)

- `harness.py`: chạy analyst trên bộ **dev fixtures** — packet tổng hợp dựng bằng
  `build_case_packet` với nguyên nhân cài chủ đích, bắt đầu 3 họ × 4–6 biến thể
  (inflation đóng khe · DWA local minimum · negative control), mỗi họ có ca
  positive / negative / phải-abstain. **Ghi rõ: đây KHÔNG phải golden chính thức**
  — golden chính thức chờ E4.5 sidecar writer (luật plan bản 7).
- Metric đúng định nghĩa gate §6: precision, recall@3, abstention rate,
  checker-selection accuracy; report JSON vào `artifacts/analyst/<date>/`.
- `bundle.py`: lắp `AnalystBundle` — `model_id`, `prompt_checksum` (từ
  `prompts.py`), `generation_parameters`, `tool_catalog_version`, `kb_version`,
  `agent_code_digest` (git SHA). Mọi `ToolRequest` mang `analyst_bundle_id`.
- Smoke test live tùy chọn với `ANTHROPIC_API_KEY` (convention env của M8 có sẵn);
  CI/test mặc định chạy MockProvider.

### A7 — E5 reconciliation (khi An hoàn tất E5 — checklist ghi sẵn, chưa thi hành)

- Diff `contracts_shim.py` với schemas E5 thật → xóa shim, import từ
  `planbench_explanation`; swap `mock_host` sang tool host E6; chạy lại toàn bộ
  schema-rejection tests hai phía; bump `tool_catalog_version` trong bundle.

## 4. Ngoài phạm vi

Fine-tune model · vector DB · UI/endpoint/feature flag (E5/E6 platform) · hidden
gate run (platform chạy, AI chỉ nộp bundle) · AI paper-import của đồng nghiệp.

## 5. Files chính

```
services/analyst_service/planbench_analyst/
  __init__.py  contracts_shim.py  packet_view.py  prompts.py
  analyst.py   guard.py  tool_client.py  knowledge_provider.py
  harness.py   bundle.py  testing/mock_host.py
tests/test_analyst_contracts.py  test_analyst_engine.py
tests/test_analyst_guard.py      test_analyst_tool_loop.py
tests/test_analyst_knowledge.py  test_analyst_harness.py
```

Sửa nhỏ: `pyproject.toml` (pythonpath), `scripts/dev_stack.sh`, `ruff.toml`
(known-first-party).

## 6. Kiểm chứng

- Mỗi phase: `pytest tests/test_analyst_*.py` (MockProvider, không cần key) +
  `ruff check`. Không chạy full suite.
- A6 end-to-end: `python -m planbench_analyst.harness` trên dev fixtures → report
  metric in ra + JSON artifact; một lần smoke live nếu An cấp key.
- Sau mỗi phase: report vào `docs/antongduy/reports/<ngày>/tongduyan_*.md`.
  Không tự commit.

## 7. Ước lượng & thứ tự

A0 → A1 → A2 → A3 → A4 → A5 → A6 tuần tự, ~6–9 ngày. A7 chờ E5.

## 8. Rủi ro

| Rủi ro | Giảm nhẹ |
|---|---|
| Shim lệch E5 thật lúc reconcile | shim một file, mirror nguyên văn §3.2/§3.4/§6; A7 diff + schema-rejection tests hai phía |
| Model overclaim / bịa số | guard 5 luật + critic pass + schema tước quyền (platform đã chặn tầng cuối) |
| Mock host quá dễ ⇒ điểm ảo | canned results lấy từ fixture có đáp án cài chủ đích, có ca refuted/not_checkable |
| Dev fixtures bị coi là golden | đánh dấu rõ trong harness + report; golden chính thức chờ E4.5 |
| Coupling vào agent_service | chỉ import provider layer (vendor-neutral); nếu sau này cần, tách packages/llm_provider — đã cân nhắc, An chọn import trực tiếp |
