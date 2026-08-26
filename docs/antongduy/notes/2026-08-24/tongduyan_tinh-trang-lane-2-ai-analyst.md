# Tình trạng Lane 2 — AI Analyst "vì sao thuật toán này thua"

**Ngày:** 2026-08-24 · **Loại:** đánh giá hiện trạng — không đổi code
**Nhánh:** `tongduyan_verify-ai-analyst` (Lane 1 đã commit xong)
**Đối chiếu:** `plans/2026-08-19/ai-analyst-subsystem.md` (bản 7, baseline `05e67de`) ·
`notes/2026-08-19/tongduyan_ra-soat-e5-e6a-cho-plan-analyst.md`

---

## 1. Kết luận

Nền platform **tốt hơn plan 19-08 giả định**. Ba thứ plan còn ghi là blocker đã
xong: sidecar chạy thật và đang sinh file, bốn checker đều sống
(`AWAITING_SIDECAR` rỗng), schema drift đã vá. Và quan trọng nhất:
**13 case packet thật đã tồn tại trong `artifacts/runs/`, xây được 13/13** —
plan viết lúc chưa có cái nào.

Cái thiếu vẫn là **chính con agent**: `services/analyst_service/` không tồn tại.

Và có một blocker mới, không nằm trong plan: **`reference_analyst` — sàn model-free
mà LLM phải thắng — crash trên 11/13 packet thật** vì một lỗi che biến một dòng.

## 2. Đã có (platform)

| Thứ | Trạng thái | Bằng chứng |
|---|---|---|
| Contract E0–E6 | **xong**, 37 module, 14.742 dòng | `packages/explanation/` |
| Tool catalog | **16 card**, version `3.0.0` | `catalog.py` |
| Mechanism checker | **4/4 sống** | `AWAITING_SIDECAR = frozenset()` (rỗng) |
| Sidecar E4.5 | **chạy thật**, mặc định bật | `episode.py:150 record_planning_inputs=True`; file `.planning_inputs.jsonl` đã có trong `artifacts/traces/production/` |
| Case packet thật | **13 run mang packet, dựng được 13/13** | 2–6 observation, 1–4 loại detection mỗi packet |
| Gate + promotion + scoring | **xong, có test** | 175 test E5/E6/E6b xanh |
| Schema drift (note 19-08 §5) | **đã vá** | `schemas/tools/rrt_convergence.result.json` mang `success_rate_at_budget` |
| Endpoint `/decisions/{id}/explanation` | **chạy** — panel tất định | `decisions.py:1769` |

## 3. Chưa có

| Thứ | Ghi chú |
|---|---|
| `services/analyst_service/` | **không tồn tại** — toàn bộ AI1–AI5 |
| Endpoint vòng analysis (E4.1) | chỉ có route explanation tất định |
| `fixtures/golden/visible/` | **thư mục không tồn tại**; 12/12 `packet_ref` treo |
| `OFFICIAL_GOLDEN_READY` | `False` |
| Họ stage được | **3/6** (`plant_golden_runs.py --dry-run`) |
| KB v1 | **5/5 entry `draft`** — chưa entry nào approved, nên không claim nào dựa KB promote được. **Chờ An ký** |
| Gate harness / hidden suite | chỉ có schema; hidden suite off-repo by design |
| Web surfacing `analyst_visible` | chưa |

## 4. Ba blocker

### B1 · `reference_analyst` crash trên packet thật — lỗi che biến

`integration.py:341` tính tập claim bị chặn:

```python
blocked = {kind for unknown in packet.known_unknowns for kind in unknown.blocks_claim_types}
```

rồi **trong vòng lặp**, dòng 368 gán đè lên chính tên đó:

```python
blocked = BLOCKED_BY_ARGUMENT.get(detection_type)   # trả None cho hầu hết loại
```

Vòng lặp kế tiếp chạy `if proposition in blocked` với `blocked = None`:

```
TypeError: argument of type 'NoneType' is not iterable
```

**Hai hậu quả, cái thứ hai tệ hơn:**

- Packet có **≥2 loại detection đã map** thì crash. Packet thật gần như luôn có:
  11/13 mang 3–4 loại (`stuck_cluster`, `latency_spike`, `replan_storm`,
  `near_miss_cluster`).
- Nếu loại đầu tiên tình cờ là `narrow_gap_refusal`, `blocked` thành **tuple hai
  chuỗi** thay vì None — không crash, nhưng `proposition in blocked` từ đó so
  nhầm, và **cổng chặn blocked-claim bị vô hiệu trong im lặng** cho mọi detection
  sau cái đầu. Đây đúng cái mà `golden.py` đếm là "blocked-claim leak".

175 test xanh vì 12 fixture golden không có cái nào mang ≥2 loại detection đã map.

Ảnh hưởng: `reference_analyst` là **sàn** mà harness A6 phải báo cáo LLM so với.
Sàn không chạy được thì không có phép so.

### B2 · `available_evidence` mặc định rỗng — seam chưa nối

`protocol.py:191` khai `available_evidence: frozenset[str] = frozenset()`, và
`admit()` (`protocol.py:560`) từ chối mọi tool có `required_evidence`. Plan 19-08
đã bắt đúng điểm này (§A4.1 `RoundSource`) và đó là rủi ro số 1 trong bảng §8 của
plan: **host dựng sau request là quá muộn**. Chưa có gì nối.

### B3 · KB 5/5 `draft`

Không entry nào `approved`, nên không claim nào dựa KB promote được. Một chữ ký,
không phải một việc kỹ thuật — nhưng nó chặn cả một nhánh bằng chứng.

## 5. Một ghi chú về phép đo

13 packet thật **không có đáp án trồng sẵn**. Chạy analyst trên chúng đo được:
không crash · abstain đúng chỗ (có 1 packet 0 observation) · có thắng sàn không.
**Không** đo được precision/recall — cái đó cần planted run, và hiện chỉ stage
được 3/6 họ.

Nói cách khác: hai phép đo khác nhau, đừng trộn. Packet thật trả lời *"nó có chạy
và có nói gì đáng nghe không"*; planted run trả lời *"nó nói đúng bao nhiêu phần
trăm"*.
