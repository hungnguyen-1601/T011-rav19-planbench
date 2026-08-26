# Báo cáo thi hành — AI Analyst bản 8 (lớp AI cố vấn "vì sao A thắng B")

**Plan:** `plans/2026-08-26/ai-analyst-ban-8.md` · **Verify nền:**
`notes/2026-08-26/tongduyan_verify-plan-ai-analyst.md`
**Nhánh:** `tongduyan_ai-analyst-ban-8`, tách từ `main` tại `738ee1f`
**Quy ước:** một file cho cả plan; mỗi phase một mục, viết ngay sau khi commit
phase đó.

| Phase | Trạng thái | Commit |
|---|---|---|
| A-1 vá sàn model-free | **xong** | (xem §A-1) |
| A0 skeleton + hạ tầng | chưa | |
| A1 packet view + fact index | chưa | |
| A2 hypothesis engine | chưa | |
| A3 guard + critic + biên vào | chưa | |
| A4 seam + lane + gateway | chưa | |
| A5 knowledge provider | chưa | |
| A6 dev calibration + harness | chưa | |
| A6.5 ba họ golden | chưa | |
| A7 freeze + official calibration | chưa | |

---

## A-1 — Vá sàn model-free

### Đã làm gì

**1. `reference_analyst` không còn mất cổng chặn blocked-claim từ detection thứ hai.**

`integration.py` dựng `blocked` = tập claim type mà `known_unknowns` của packet
chặn, rồi **trong vòng lặp** gán đè lên chính tên đó bằng
`BLOCKED_BY_ARGUMENT.get(detection_type)`. Đổi tên biến trong vòng lặp thành
`short_of`, kèm comment nói rõ nó phải ở tên khác và vì sao.

Hai hậu quả của lỗi cũ, cái thứ hai tệ hơn:

- `BLOCKED_BY_ARGUMENT` chỉ có **một** entry, nên với mọi loại detection khác,
  `blocked` thành `None` ở vòng sau ⟶ `TypeError: argument of type 'NoneType' is
  not iterable`. Sàn chết.
- Khi detection đầu tiên là `narrow_gap_refusal`, `blocked` thành tuple hai
  chuỗi tên-tool, `proposition in blocked` từ đó **so nhầm mà không chết**, và
  cổng chặn blocked-claim tắt trong im lặng cho mọi detection sau đó. Đây đúng
  cái `golden.py` đếm là blocked-claim leak.

**2. Hai test mới, và chúng cắn.**

- `test_the_blocked_claim_gate_is_still_on_for_the_second_detection` — packet có
  `narrow_gap_refusal` + `latency_spike`, kèm một `KnownUnknown` chặn
  `expansion_latency_association`. Đòi **đúng một** proposal sống sót. Đây là
  nhánh im lặng, nên nó được kiểm bằng *cái gì sống sót*, không bằng exception.
- `test_several_mapped_detections_do_not_kill_the_floor` — packet có
  `latency_spike` + `stuck_cluster`, đòi hai proposal. Đây là nhánh raise.

Tiêm lại lỗi cũ vào bản sao tạm: **cả hai test đỏ**, một cái vì `TypeError`, một
cái vì proposal bị chặn vẫn được nộp. Khôi phục: xanh.

**3. Một răng mới trong bộ `bites`.**

`FLOOR_SECOND_DETECTION_UNGATED` trong
`notes/2026-08-24/tongduyan_ai-explain-bites.yaml`: tiêm
`blocked = short_of = BLOCKED_BY_ARGUMENT.get(...)` — tái dựng đúng phép che
biến — và đòi cổng đỏ đúng tên test. **CẮN**, exit 1.

### Bằng chứng

| Phép kiểm | Kết quả |
|---|---|
| `pytest tests/test_explanation_e5.py` | **112 passed**, 0,36 s |
| Sàn chạy trên **packet thật** (17 run có `case_packet` trong `artifacts/runs/`) | **17/17 không raise**; 13 packet sinh 1–3 proposal, 4 packet 0 observation ⟶ abstain đúng |
| Răng `GATE_SUITE_MISMATCH_IGNORED` (trượt hôm 24-08) | **CẮN** |
| Răng `ADVISOR_ADDITION_CAP_OFF` (trượt hôm 24-08) | **CẮN** |
| Răng `FLOOR_SECOND_DETECTION_UNGATED` (mới) | **CẮN** |
| `ruff check` trên hai file đã sửa | sạch |

Số packet thật đã tăng từ 13 (đo hôm 24-08) lên **17** — bốn run mới ngày 25-08.
Bốn packet abstain đều là packet 0 observation, tức abstain vì đúng lý do.

Kịch bản chạy sàn trên packet thật để ở scratchpad, **không commit**: A6 sẽ có
`harness.py` thật trong service, và một script tạm nằm trong repo là thứ sau này
không ai biết có còn đúng không.

### Đã đổi kế hoạch một điểm

Plan bản 8 §A-1 xếp **`run_gate` kiểm `suite.status == "preregistered"`** vào
phase này. **Đã chuyển sang A4**, lý do kỹ thuật chứ không phải để tránh việc:

- `GoldenSuite` từ chối `status="preregistered"` khi `OFFICIAL_GOLDEN_READY` còn
  `False`, và một suite preregistered hợp lệ đòi **đủ 6 họ × ≥12 biến thể = ≥72
  case** (`MIN_VARIANTS_PER_FAMILY = 12`). Mọi test gate hiện tại dùng
  `hidden_suite()` với `status="calibration"` và **một** case.
- Nghĩa là thêm luật fail-closed bây giờ sẽ phải dựng lại toàn bộ fixture của
  `tests/test_explanation_gate.py`, rồi **dựng lại lần nữa** ở A4 khi
  `allow_visible_suite` đổi tên thành `dry_run`, `DryGateRun` tách khỏi
  `GateRun`, và điều kiện thứ ba (`PacketArtifact.fixture_kind == "recorded"`)
  ra đời. Ba điều kiện fail-closed của plan bản 7 §A4.5 là **một** thay đổi.
- Rủi ro để lại trong lúc chờ bằng không: chưa có analyst nào để gate.

### Còn nợ sau A-1

Không. `available_evidence` mặc định rỗng vẫn còn nguyên — đúng thiết kế, nó là
việc của `RoundSource` ở A4.
