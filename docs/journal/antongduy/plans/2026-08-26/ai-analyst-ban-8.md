# Plan — AI Analyst (lớp AI cố vấn "vì sao A thắng B"), bản 8

**Ngày:** 2026-08-26 · **Trạng thái:** **An đã duyệt, đang thi hành**
**Nhánh thi hành:** `tongduyan_ai-analyst-ban-8`, tách từ `main` tại `738ee1f`
**Kế thừa:** `plans/2026-08-19/ai-analyst-subsystem.md` (bản 7) — bản 8 **không
thay thế** bản 7, nó là bản 7 cộng bốn khoảng hụt và trừ những chỗ An đã chốt.
Chỗ nào bản 8 im lặng thì bản 7 vẫn là luật.
**Không đi:** `plans/2026-08-24/ai-analyst-duong-ngan.md` — An chọn đường đầy đủ.
**Verify nền:** `notes/2026-08-26/tongduyan_verify-plan-ai-analyst.md`
**Skill đối chiếu:** `agent-harness-layers` · `guardrail-design` ·
`guardrail-redteam` · `eval-harness` · `agent-tool-design-eval` ·
`agent-workflow-graph` · `rag-retrieval` · `bites`

---

## 0. Bốn quyết định của An (2026-08-26)

| # | Câu hỏi | Chốt | Hệ quả trong plan |
|---|---|---|---|
| 1 | Lớp nào | **Lane 2 — Analyst "vì sao"** | Lane 1 (`advisor.py`) không đổi; chỉ dùng chung `provider.py` |
| 2 | Đường nào | **Đường đầy đủ, plan 19-08** | container + gateway + JSONL ABI **trong phạm vi** (A4, A7) |
| 3 | Golden | **3/6 họ, khai rõ 3/6** | A6.5 vào phạm vi; `OFFICIAL_GOLDEN_READY` giữ `False` |
| 4 | KB v1 | **Chưa ký** | Trần claim là `associated`; đường KB ⟶ `mechanism_verified` đóng |

## 1. Nguyên tắc bất biến — không phase nào được đổi

Kế thừa nguyên văn bản 7 §1, nhắc lại vì đây là lý do cả tầng tồn tại:

1. Analyst **không đọc Parquet thô**; nó chỉ thấy `CasePacket` và kết quả tool.
2. Analyst **không tự đóng dấu**: `HypothesisProposal` không có field số, không
   `status`, không `confidence` (`extra="forbid"` biến chính sách thành lỗi parse).
3. **Menu tool đóng** — 16 card, không sinh check tự do.
4. **LLM không bao giờ là nguồn của một con số.** Số hiển thị do renderer lấy từ
   fact record.
5. **Promotion matrix tất định** giữ nguyên quyền đóng dấu; analyst đề xuất.
6. `analyst_visible` mặc định off, vẫn đòi `GateDecision` đã verify.

## 2. Delta so với bản 7

### 2.1. Bốn khoảng hụt phải đóng

| # | Đóng ở phase | Nội dung |
|---|---|---|
| K1 | **A-1** | `reference_analyst` che biến ⇒ sàn crash 11/13 packet thật; nhánh không crash làm cổng blocked-claim vô hiệu trong im lặng |
| K2 | **A3 + A4.4** | Chuỗi do bên thứ ba viết (manifest plugin import) đi thẳng vào prompt analyst qua `CasePacket.candidates` |
| K3 | **A6** | Sáu metric chưa có taxonomy lỗi đứng sau; thiếu trục reliability (`pass^k`) và trục chi phí |
| K4 | **A3** | Citation resolve ≠ citation ủng hộ claim ⇒ guard cần luật 6 |

### 2.2. Sáu điểm nhỏ

1. **No-progress guard** trong vòng revise — checker tất định, gọi lại cùng
   argument cho đúng verdict cũ; so payload trước khi tiêu một lượt (A4.2).
2. **Timeout per-call**, không chỉ `max_wall_time_ms` cho cả round (A2).
3. **Eval routing riêng cho 16 card**, taxonomy mượn 22 `RejectionCode` (A6).
4. **AI2 giữ lexical**, BM25 là mốc; ngưỡng "không biết" đặt trên điểm gốc (A5).
5. **Guard luật 7**: proposal không gắn được ref nào ⇒ **xoá**, không nộp (A3).
6. **Ablation critic = leave-one-out, 3–5 lượt mỗi cấu hình**, không 1 (A6).

## 3. Các phase

Thứ tự thi hành. Mỗi phase: commit một dòng tiếng Anh, và một mục trong
`reports/2026-08-26/tongduyan_ai-analyst-ban-8.md` (một file chung cho cả plan).

### A-1 — Vá sàn trước khi dựng gì lên trên (0,5 ngày)

Không phase nào sau đây có nghĩa nếu sàn so sánh không chạy.

1. `reference_analyst`: đổi tên biến vòng lặp; **kèm test dựng packet ≥2 loại
   detection đã map** và đòi cả hai đi qua đúng cổng blocked-claim. 12 fixture
   golden hiện tại không chạm tới nhánh này nên chỉ sửa dòng là không đủ.
2. `run_gate` kiểm `suite.status == "preregistered"` khi không dry-run —
   fail-closed theo bản 7 §A4.5. Rẻ, và `bites` đã có chỗ chứng minh nó cắn.
3. Chạy lại bộ răng `bites` 24-08, đòi `GATE_SUITE_MISMATCH_IGNORED` và
   `ADVISOR_ADDITION_CAP_OFF` chuyển sang **CẮN**.

**DoD:** `reference_analyst` chạy sạch 13/13 packet thật; abstain đúng trên packet
0 observation; test blocked-claim mới đỏ khi revert bản vá; bites ≥14/14.

### A0 — Skeleton + hạ tầng (0,5–1 ngày)

- `services/analyst_service/planbench_analyst/` + wire `pyproject.toml`,
  `scripts/dev_stack.sh`, `ruff.toml`.
- `docker/Dockerfile.api` PYTHONPATH thiếu `packages/decision`,
  `packages/explanation`, `packages/plugin_sdk`, `ml` — cộng cả hai service.
- Test: import surface + pythonpath guard.

**DoD:** import được từ test và từ container; ruff sạch.

### A1 — Packet view + fact index (0,5 ngày)

- `packet_view.py`: validate header version; fact index
  `{ref, value, unit, subject, scope}`; serialize tất định.
- **Mới (bản 8):** index phụ tra theo `subject` — vật liệu cho guard luật 6.

**DoD:** cùng packet ⇒ cùng chuỗi; header lệch ⇒ từ chối; identifier (`B7`) tách
khỏi quantity; tra `subject` trả đúng tập ref.

### A2 — Hypothesis engine, AI1 lõi (1,5–2,5 ngày)

Giữ nguyên bản 7 §A2: `hypothesis_id` từ content hash, generation config
capability-aware, flatten JSON Pointer chống collision, `source_manifest_hash`
byte-level, hai chế độ cache, `prompts.py` là nguồn `prompt_checksum`.

**Mới (bản 8):**

- **Timeout cho từng provider call**, tách khỏi deadline cả round; tắt retry
  tầng provider để chỉ còn một tầng retry mình kiểm soát.
- **Đếm chi phí ngay từ A2**: token vào/ra và số tool-call ghi vào artifact mỗi
  round, không đợi tới lúc vượt budget mới biết.

**DoD:** parse; trường lạ; dedupe/collision; unsupported config refuse;
precedence merge; JSON Pointer collision; manifest hash bỏ mtime; hai chế độ
cache; call treo ⇒ round hỏng có mã, không treo cả process.

### A3 — Guard + critic + biên dữ liệu vào (1,5–2,5 ngày)

Năm luật của bản 7 §A3 giữ nguyên. Thêm hai luật và một lane:

- **Luật 6 — ref phải ủng hộ claim.** Mọi `supports`/`contradicts` phải trỏ vào
  ref mà fact index xác nhận **cùng subject** với `proposed_subject` (và scope
  không mâu thuẫn). Luật 1 hỏi *ref có tồn tại*; luật 6 hỏi *ref có nói về cái
  đang nói*. Đây là nửa còn lại của ca A15.
- **Luật 7 — xoá rẻ hơn giữ.** Proposal không gắn được ref nào ⇒ loại khỏi
  final, giữ audit artifact. Không nộp một proposal trần rồi để `missing_evidence`
  rỗng gánh.
- **Lane sanitize (K2).** Mọi chuỗi trong packet có nguồn từ bên thứ ba —
  `candidate_id`, `global_planner`, `local_controller`, `local_controller_config`
  — đi qua một bước cách ly **trước khi vào prompt**: chuẩn hoá NFKC, cắt trần độ
  dài, bọc trong khối dữ liệu có nhãn, và **thay bằng nhãn nội bộ** (`C1`, `C2`)
  trong phần hội thoại; ánh xạ nhãn ⟶ chuỗi gốc do renderer giữ. Kèm detector
  đếm (không chặn im lặng): chuỗi mang chỉ thị, mang marker mở không có marker
  đóng, hoặc vượt trần ⇒ ghi `injection_suspected` vào audit artifact.
  **Chuẩn hoá của detector và của bên cách ly phải là cùng một hàm** — theo
  `guardrail-design`, khe hở giữa hai cách chuẩn hoá là nguồn bypass phổ biến
  nhất.
- Critic vẫn **advisory**: rerank + cờ, không xoá; log đủ ba (trước, sau, cờ).

**DoD:** mỗi luật một test; blocked-all ⇒ round abstention có lý do; blocked một
phần ⇒ không abstain; critic không làm mất proposal; packet mang chuỗi chỉ thị ⇒
nhãn thay thế đúng, `injection_suspected` được đếm, và không proposal nào mang
claim type mà packet đã chặn.

### A4 — Seam + hai lane + JSONL ABI + gateway, AI3 (3–4,5 ngày)

Giữ **nguyên văn** bản 7 §A4.1–A4.5: `RoundHostProtocol` / `AnalystRunner` /
`PreparedRound` / `RoundSource`; vòng declare → tool → revise-redeclare; frame
set và envelope; gateway không cho container cầm credential; `AnalysisBudget`
embed trong bundle, effective = min(requested, cap); restricted artifact cho
stderr/transcript hidden; RFC platform cho `gate.py` và `bundle.py`, `DryGateRun`
tách type.

**Mới (bản 8):**

- **Luật nội dung trên gateway (K2, chiều ra).** Gateway là cổng egress duy
  nhất; nó từ chối payload mang bí mật platform và ghi lại kích thước + checksum
  từng frame. Dùng **cùng hàm chuẩn hoá** với detector ở A3.
- **No-progress guard.** Trước khi tiêu một lượt revise: nếu batch proposal mới
  cho ra cùng tập `(tool_id, arguments)` như lượt trước thì dừng vòng, đánh
  `no_progress`, không gọi lại checker. Checker tất định — gọi lại là đốt budget
  để nhận đúng verdict cũ.
- **Mọi nhánh kết thúc đi qua một điểm `finalize` duy nhất** trước khi trả
  `AnalysisResponse`, để audit trail có đúng một sự kiện đóng mỗi round bất kể
  đi đường nào.

**DoD:** như bản 7 §A4 kèm ba test mới — no-progress dừng đúng lượt; gateway từ
chối payload mang bí mật; mọi đường thoát đều sinh đúng một sự kiện `finalize`.

### A5 — Knowledge provider, AI2 (0,5–1 ngày)

Giữ bản 7 §A5. Ghi rõ thêm:

- KB **5/5 draft, An chưa ký** ⇒ `may_support_a_claim` false toàn bộ; AI2 chỉ mở
  rộng không gian giả thuyết và trả `MechanismReferenceCandidate`.
- **Trần claim của cả hệ ở mốc này là `associated`** qua đường KB; đường checker
  vẫn lên `mechanism_verified` được.
- v1 **lexical**, không vector DB: 5 entry thì BM25 là mốc và cũng là trần.
  Ngưỡng "không biết" đặt trên **điểm gốc**, không trên điểm hợp nhất.

**DoD:** AI2 không tự trả `review_status`/`source_refs`; entry lạ ⇒ rejected;
`retrieval_score` không xuất hiện ở bất kỳ đường nào dẫn tới confidence.

### A6 — Dev calibration + harness (2–3 ngày)

Giữ bản 7 §A6 (fixture root, `PacketArtifact` + loader validate, `harness.py`,
định nghĩa thắng sàn, cache dev). **Mới, theo `eval-harness`:**

1. **Error analysis trước metric.** Chạy analyst trên 13 packet thật, đọc trace,
   open coding từng round (chỉ ghi lỗi đầu tiên), gom theo root cause, đếm tần
   suất. Bảng tần suất đó vào report **trước** khi đọc sáu con số preregister.
2. **`pass^3`**: mỗi case chạy 3 lượt, báo cáo cả `pass@1` lẫn `pass^3`. Một
   analyst đúng 90%/lượt chỉ còn 0,73 ở `pass^3` — con số phải sống chung ở
   production.
3. **Chi phí là một trục báo cáo**: token và tool-call trung vị mỗi case, theo
   từng loại round.
4. **So với sàn bằng paired test** trên cùng packet (McNemar), không so hai
   trung bình rời nhau. Dưới ~6 discordant case thì kết luận là "chưa đủ dữ
   liệu".
5. **Eval routing riêng cho tool**: mỗi case ghi `failure_type` theo taxonomy
   `wrong_tool` · `wrong_arg_value` · `unnecessary_tool` · `missing_info`, đối
   chiếu với `RejectionCode` host trả về.
6. **Ablation critic là leave-one-out**, mỗi cấu hình 3–5 lượt.

**DoD:** bảng tần suất lỗi có trước bảng metric; `pass@1` và `pass^3` cùng xuất
hiện; mọi macro in kèm "3/6 họ"; báo cáo nêu rõ **A6 không đo precision trên 13
packet thật** — precision chỉ ra từ golden có đáp án.

### A6.5 — Ba họ golden (1–1,5 ngày)

- `plant_golden_runs.py` cho `inflation-001`, `rrt-001`, `dwa-001`, **chạy có
  sidecar** (`PlanningInputRecorder` attached — packet dựng từ run trước writer
  mang planning input tái dựng, và ngưỡng thoả thuận trên đó là ngưỡng nướng
  sẵn lỗi tái dựng vào).
- Dựng `fixtures/golden/visible/<case_id>/{packet.json, provenance.json}` từ
  chính run vừa trồng; `fixture_kind` do loader suy từ provenance đã validate.
- `OFFICIAL_GOLDEN_READY` **giữ `False`**. Ba họ `CANNOT_STAGE_YET` ở lại đúng
  chỗ, có tên, có lý do.

**DoD:** `score_suite` chạy được trên 3 họ; mỗi con số macro in kèm "3/6 họ";
loader từ chối packet checksum lệch.

### A7 — Freeze bundle + container + official calibration (1,5–2 ngày)

Giữ **nguyên văn** bản 7 §A7: clean-tree mới freeze, `agent_code_digest`, model
identity preflight, `Dockerfile.analyst`, `container_digest`, bundle builder đủ
field, calibration 3 lượt lane container + gateway, lấy minimum, **không retry**,
bypass cache, dry gate trả `DryGateRun`.

**DoD:** như bản 7 §A7.

### A8 — AI5 productization

**Ngoài phạm vi bản 8**, plan riêng sau khi qua gate.

## 4. Files chính

```
services/analyst_service/planbench_analyst/
  __init__.py  packet_view.py  prompts.py  analyst.py  guard.py
  sanitize.py                       <- mới, bản 8 (K2)
  runner.py  round_host.py  stdio_protocol.py  stdio_lane.py
  model_gateway.py  knowledge_provider.py  harness.py  bundle_builder.py
docker/Dockerfile.analyst
fixtures/golden/visible/<case_id>/{packet.json,provenance.json}
tests/test_analyst_*.py
```

**RFC platform** (diff có test): `gate.py` · `bundle.py` · `AnalysisBudget` +
`PacketArtifact` + loader trong `planbench_explanation` ·
`planbench_agent/provider.py` + 2 adapter · `integration.py` (A-1) ·
`pyproject.toml` · `ruff.toml` · `docker/Dockerfile.api`.

## 5. Kiểm chứng

**Mỗi phase:** chỉ chạy test của phần vừa sửa (`pytest tests/test_analyst_*.py`
hoặc file liên quan) + `ruff check`. **Không chạy full suite** cho tới khi xong
toàn bộ plan — đó là lệnh của An cho lần này.

**Trước freeze bundle (cuối A7):** full suite (ngoại lệ có chủ đích), explanation
/gate regression, container smoke trên đúng image digest, import-path test, dry
gate visible suite, và toàn bộ failure-path của bản 7 §6.

**Bộ răng:** chạy lại `bites` sau A-1 và sau A3 (luật 6, luật 7, lane sanitize
đều phải chứng minh được là có răng, không phải cổng trang trí).

## 6. Rủi ro

Kế thừa bảng bản 7 §8, thêm bốn dòng:

| Rủi ro | Giảm nhẹ |
|---|---|
| Lane sanitize thay nhãn làm hỏng khả năng trích dẫn của model | nhãn ổn định trong cả round; renderer giữ ánh xạ; test round-trip nhãn ⟶ chuỗi gốc |
| Detector injection và bên cách ly chuẩn hoá khác nhau ⇒ bypass | đúng một hàm chuẩn hoá, dùng chung, có test đối xứng |
| No-progress guard dừng sớm một vòng revise đáng lẽ có ích | chỉ so **tập `(tool_id, arguments)`**, không so văn bản; đổi argument là có tiến triển |
| `pass^3` làm chậm A6 gấp ba | chỉ áp cho case golden có đáp án, không áp cho 13 packet thật |

## 7. Ước lượng

A-1 (0,5) → A0 (0,5–1) → A1 (0,5) → A2 (1,5–2,5) → A3 (1,5–2,5) →
A4 (3–4,5) → A5 (0,5–1) → A6 (2–3) → A6.5 (1–1,5) → A7 (1,5–2)
= **12,5–18,5 ngày**, so với 10,5–16 của bản 7. Chênh lệch là A-1, K2 và phần
mở rộng đo đạc của A6.
