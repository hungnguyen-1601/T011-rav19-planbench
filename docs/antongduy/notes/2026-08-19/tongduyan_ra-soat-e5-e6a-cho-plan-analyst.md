# Rà soát E5/E6a — đã đủ nền để gỡ blocker của plan AI Analyst chưa?

**Ngày:** 2026-08-19 · **Loại:** đánh giá hiện trạng (không đổi code)
**Đối chiếu với:** `plans/2026-08-19/ai-analyst-subsystem.md` (viết lúc E5 chưa có,
phải shim toàn bộ contract E5)

---

## 1. Kết luận

**Đủ.** Mọi type plan analyst phải shim đều đã tồn tại thật trong
`packages/explanation/planbench_explanation/`, đúng hoặc vượt spec plan bản 7.
Plan analyst cần một bản sửa: **xóa phase A0-shim, xóa mock host tự chế, xóa
phase A7 reconciliation** — thay bằng import trực tiếp. Blocker còn lại đều nằm
phía platform (gate harness, golden chính thức, E4.1 endpoint), không chặn
đường phát triển analyst.

## 2. Đối chiếu từng thứ đã shim

| Plan analyst shim | Hiện trạng | Ở đâu |
|---|---|---|
| `ToolRequest`/`ToolResult` + correlation fields | **CÓ, đủ cả 6 field** (`analysis_run_id`, `case_packet_checksum`, `tool_catalog_version`, `analyst_bundle_id`, `sequence`, `evidence_refs`) | `protocol.py` |
| `AnalysisRequest` | **CÓ** (+ `AnalysisResponse` với `abstained`/`abstention_reason` first-class) | `protocol.py` |
| `AnalystBundle` | **CÓ, superset** (thêm `model_revision`; `identity_checksum` loại `bundle_id`/`created_at`) | `bundle.py` |
| `KnowledgeQuery`/`KnowledgeResult`/`MechanismReferenceCandidate` | **CÓ**, kèm `resolve_candidates()` canonical đúng luật §3.4 | `knowledge_contract.py` |
| `ToolCatalog` thật | **CÓ — 16 card đủ 4 lớp**, version 3.0.0 (working tree), typed IO từng card + JSON Schema sinh ra ở `schemas/tools/` (32 file) | `catalog.py`, `tools.py` |
| Mock tool host | **CÓ, tốt hơn bản định tự chế**: `MockToolHost` admit qua `ToolSession` THẬT (cùng rejection codes), kèm `reference_analyst` deterministic làm floor | `integration.py` |
| Metric gate + targets | **CÓ**: `MetricTargets` đúng ngưỡng §6 (precision 0.90, recall@3 0.70, abstention 0.90, component-attribution 0.85, checker-selection 0.90), `GateDecision`, `verify_gate_decision` | `bundle.py` |
| Golden format + visible suite | **CÓ format + 12 case visible** (`VISIBLE_SUITE`, 6 họ × 2 biến thể, 7/12 phải abstain) | `golden.py`, `golden_fixtures.py` |
| Feature flag | **CÓ tầng Python** (`analyst_visible`/`why_not_visible`); web chưa đụng | `bundle.py` |

Ngoài shim, E6a/E6b còn cho thêm thứ plan analyst chưa dám giả định:

- **Tool host thật đã chạy**: `ToolHost` (`host.py`) + đủ **4 mechanism checker**
  (`gap_vs_footprint`, `latency_vs_expanded_nodes` ở `checkers.py`;
  `replay_global_plan`, `rrt_convergence` ở `replay.py` — working tree,
  `AWAITING_SIDECAR` đã rỗng).
- **Sidecar E4.5 đã nối vào pipeline** (uncommitted E6b): recorder được construct
  thật trong `packages/benchmark/episode.py` (`record_planning_inputs=True` mặc
  định), `trace.py` có `planning_inputs_path()`, `SimulatorReplayPlanner` dựng lại
  grid không re-inflate.

## 3. Tác động lên plan analyst — sửa gì

1. **A0**: bỏ `contracts_shim.py` hoàn toàn. Package analyst chỉ còn skeleton +
   wire pythonpath. Import mọi contract từ `planbench_explanation`.
2. **A4**: bỏ `testing/mock_host.py` — dùng `integration.MockToolHost` của
   platform. Vòng lặp analyst code thẳng lên `ToolSession`/`ToolHost` interface
   thật; budget dùng `max_tool_requests` của `AnalysisRequest` (mặc định 64) thay
   vì tự đặt.
3. **A2 thêm baseline**: `reference_analyst` (model-free) của platform là floor —
   harness A6 phải báo cáo LLM analyst so với floor này; không thắng floor thì
   không có lý do ship.
4. **A6**: calibration nhắm `VISIBLE_SUITE` (12 case, đáp án + abstention có sẵn)
   thay vì tự chế dev fixtures — **nhưng** packet fixture chưa tồn tại
   (`packet_ref` chưa resolve được, xem §4). Trước mắt vẫn cần dựng packet tổng
   hợp bằng `build_case_packet` cho từng planted case; khi E4.1 + planted runs
   xong thì trỏ sang packet thật.
5. **A7**: xóa. Không còn gì để reconcile.
6. **Scoring**: dùng thẳng `score_case`/`score_suite`/`ScoreBoard` của `golden.py`
   thay vì tự viết metric.

Ước lượng giảm: ~6–9 ngày → **~4–6 ngày** (bỏ shim + mock + reconcile, thêm ít
công nối MockToolHost/VISIBLE_SUITE).

## 4. Blocker còn lại — đều phía platform, không chặn analyst dev

| Thiếu | Chặn gì | Ghi chú |
|---|---|---|
| Gate harness / hidden suite runner | gate run cuối (AI chỉ nộp bundle) | chỉ có schema; hidden suite off-repo by design; cần bundle thật từ phía AI trước |
| `OFFICIAL_GOLDEN_READY = False`, packet fixture chưa có | calibration trên packet thật | chờ E4.1 (endpoint dựng packet) + 4/6 họ chưa stage được (`CANNOT_STAGE_YET` trong `scripts/plant_golden_runs.py`) |
| HTTP endpoint analysis round | tích hợp online | chờ E4.1 |
| Web surfacing của `analyst_visible` | UI | E5 report §9 đã khai |
| KB v1 chưa approve | không claim nào dựa KB promote được | chờ An sign-off — 5 entry đều draft |
| `rrt_convergence` cần *tập* seed | checker này trên run thật | sidecar ghi 1 seed/attempt — E6b report §5 ghi "chờ An chốt" |

## 5. Lỗi nhìn thấy khi scan (chưa sửa — báo thôi)

**Schema drift, uncommitted:** `catalog.py` working tree đã bump `rrt_convergence`
lên v2.0.0 với measurements mới (`success_rate_at_budget`,
`success_rate_at_high_budget`) nhưng `schemas/tools/rrt_convergence.result.json`
trên đĩa vẫn là bản cũ (`success_rate`) — **test drift trong
`tests/test_explanation_e5.py` sẽ đỏ**. Fix một lệnh:
`python scripts/export_tool_schemas.py` rồi commit kèm E6b.

Ghi chú phụ: E6b report §4 nói `AWAITING_SIDECAR` còn `{rrt_convergence}` nhưng
code working tree đã rỗng — report viết trước code, nên cập nhật report khi
commit E6b.
