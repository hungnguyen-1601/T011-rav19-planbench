# Plan — AI Analyst, đường ngắn: chứng minh luận điểm trước, dựng pháo đài sau

**Ngày:** 2026-08-24 · **Trạng thái:** đề xuất, **chờ An duyệt**
**Thay thế:** không. Đây là **đường vào** cho `plans/2026-08-19/ai-analyst-subsystem.md`
(bản 7), không phải bản thay thế — xem §1.
**Hiện trạng nền:** `notes/2026-08-24/tongduyan_tinh-trang-lane-2-ai-analyst.md`

---

## 1. Vì sao đề xuất đường khác, và giữ lại gì

Plan 19-08 ước lượng **10,5–16 ngày**. Đọc lại danh sách công việc của nó thì
phần lớn chi phí nằm ở: container sandbox · model gateway giữ credential ·
JSONL ABI giữa hai process · restricted artifact chống rò hidden suite qua
stderr · source-manifest hash byte-level · luật "không retry, minimum 3 lượt"
chống best-of-N.

**Toàn bộ khối đó tồn tại để phòng một bên thứ hai nộp bài mà platform không tin
được.** Nó là thiết kế đúng cho tình huống ấy. Nhưng hiện tại **An vừa là
platform vừa là nhóm AI**, và cái cần trả lời trước là câu hỏi của đề tài:
*hệ có nói được vì sao A thắng B không*.

Đề xuất tách đôi:

| | Nội dung | Khi nào làm |
|---|---|---|
| **Đường A** | Analyst chạy in-process, không container, không gateway. Trả lời câu hỏi đề tài. | **ngay** |
| **Đường B** | Nguyên khối sandbox của plan 19-08 (§A4.3, A4.4, A7 container) | **chỉ khi** có bên thứ hai thật sự nộp bundle |

Đường B **không bị xoá** — nó là plan 19-08, giữ nguyên. Đường A cố ý dựng theo
đúng seam mà plan 19-08 định nghĩa (`RoundHostProtocol`, `AnalystRunner`,
`PreparedRound`) để khi cần Đường B thì cắm vào, không viết lại.

**Cái KHÔNG được cắt, dù đi đường ngắn** — đây là phần bảo vệ chống overclaim,
tức lý do cả tầng này tồn tại:

- schema tước quyền: analyst chỉ trả `HypothesisProposal`, không có field số,
  không có status/confidence;
- guard 5 luật pre-submit (§A3 của plan 19-08), **đặc biệt luật cấm numeric
  quantity trong statement**;
- promotion matrix tất định giữ nguyên — analyst không đóng dấu;
- menu tool đóng, 16 card, không sinh check tự do;
- `analyst_visible` vẫn mặc định off, vẫn đòi `GateDecision`.

## 2. Các giai đoạn

### P0 — Vá ba blocker (0,5 ngày)

1. **`reference_analyst` che biến** (`integration.py:368`) — đổi tên biến vòng
   lặp. Kèm test dựng packet **≥2 loại detection đã map** và đòi cả hai đi qua
   đúng cổng blocked-claim. Đây là lỗi mà 12 fixture golden không chạm tới, nên
   test mới phải đi kèm, không chỉ sửa dòng.
2. **`RoundSource`-lite** (§A4.1 plan 19-08, bỏ phần container): dựng evidence
   source → suy `available_evidence` → dựng `AnalysisRequest` → dựng host từ
   **cùng** source. Trả cặp đã bind. Không có bước này thì mọi tool chết ở
   `missing_required_evidence`.
3. **`run_gate` kiểm `suite.status`** — plan 19-08 §A4.5 fail-closed. Rẻ, và bộ
   răng `bites` đã có sẵn chỗ để chứng minh nó cắn.

**Nghiệm thu:** `reference_analyst` chạy sạch trên 13/13 packet thật; abstain
đúng trên packet 0 observation; `bites` vẫn 14/14.

### P1 — `packet_view` + fact index (0,5 ngày)

`services/analyst_service/planbench_analyst/packet_view.py` — đúng §A1 plan
19-08: validate header version; fact index `{ref, value, unit, subject, scope}`;
serialize tất định.

Fact index không phải trang trí: nó là thứ **guard luật 1 và luật 2 dựa vào** —
mọi `supports`/`contradicts` phải trỏ vào một ref có thật, và mọi số hiển thị
phải do renderer lấy từ fact record chứ không do model viết ra.

**Nghiệm thu:** cùng packet ⇒ cùng chuỗi; header lệch ⇒ từ chối; identifier
(`B7`) tách khỏi quantity.

### P2 — Analyst engine + guard (1,5–2 ngày)

- `prompts.py` (hằng số, nguồn `prompt_checksum`) · `analyst.py` ·
  `guard.py`.
- Tái dùng thẳng `planbench_agent.provider` — và **dùng đúng bản vừa vá hôm
  nay**: `_schema_is_strict` đệ quy + retry theo trần model. Không có hai thứ
  đó thì analyst sẽ dính đúng hai lỗi 400 mà Lane 1 vừa mất một ngày để tìm.
- Guard 5 luật §A3. Luật 2 (cấm số) là luật quan trọng nhất, test 5 ca: thập
  phân · `%` · sci-notation · số viết bằng chữ (en + vi) · identifier hợp lệ
  phải **được phép** đi qua.
- `hypothesis_id` sinh từ content hash; trùng nội dung ⇒ dedupe.
- Offline lane: `MockProvider(script=[...])` cho test, `o4-mini` cho chạy thật
  (đã đo hôm nay: có giá trị gia tăng thật, gpt-4o-mini gần như không thêm gì).

**Nghiệm thu:** mỗi luật guard có test riêng; blocked-all ⇒ round abstention có
lý do; proposal bị chặn giữ audit artifact, không biến mất im lặng.

### P3 — Harness so sàn (0,5 ngày)

`harness.py`: chạy `reference_analyst` và LLM analyst trên **13 packet thật**,
báo cáo cạnh nhau.

Đo được ở bước này, và **chỉ** những thứ này:

- không crash;
- abstain đúng chỗ (packet 0 observation);
- số proposal, số check gọi, số bị host từ chối và **mã từ chối**;
- có thắng sàn không.

**Không** đo precision/recall ở đây. Nói rõ trong report — đây đúng chỗ dễ tự
lừa nhất.

### P4 — Golden có đáp án (1–1,5 ngày)

- Chạy `plant_golden_runs.py` cho **3 họ stage được**
  (`inflation-001`, `rrt-001`, `dwa-001`).
- Dựng `fixtures/golden/visible/<case_id>/packet.json` từ chính run vừa trồng.
- Chấm bằng `score_case`/`score_suite` có sẵn.
- **`OFFICIAL_GOLDEN_READY` vẫn `False`** cho tới khi đủ 6 họ. Report phải ghi
  rõ macro đang tính trên **3/6 họ** — plan 19-08 §CANNOT_STAGE_YET đã cảnh báo
  đúng chuyện này: một suite thiếu hai họ mà không nói thì người đọc mặc định là
  sáu.

**Nghiệm thu:** precision/recall@3/abstention trên 3 họ, so với
`CALIBRATION_TARGETS`, kèm câu "đây là 3/6 họ" ngay cạnh con số.

### P5 — Chỉ khi P4 đạt: nối vào UI (0,5–1 ngày)

Endpoint vòng analysis + hiện panel sau `analyst_visible`. Cờ vẫn đòi
`GateDecision`, nên trước khi có gate thật thì panel chỉ nằm ở trang phân tích,
**không lên Decision Card** — đúng §9 note thiết kế 18-08.

## 3. Tổng: 4–5,5 ngày tới chỗ trả lời được câu hỏi đề tài

So với 10,5–16 ngày của plan 19-08. Chênh lệch **không phải do cắt phần bảo vệ
chống overclaim** — phần đó giữ nguyên §1. Chênh lệch là do hoãn khối sandbox
chống một bên nộp bài chưa tồn tại.

## 4. Việc của An, không phải việc code

**Ký duyệt KB v1.** 5 entry đang `draft`; chưa entry nào `approved` thì không
claim nào dựa KB promote được. Nếu chưa muốn ký thì P2–P4 vẫn chạy được — chỉ
là mọi claim dừng ở `associated`, không lên `mechanism_verified` qua đường KB.

## 5. Rủi ro của chính plan này

| Rủi ro | Giảm nhẹ |
|---|---|
| Đường A dựng seam lệch, sau này Đường B phải viết lại | dùng đúng tên và hình dạng của plan 19-08 §A4.1: `RoundHostProtocol`, `AnalystRunner`, `PreparedRound` |
| 13 packet thật thành "bộ test" trá hình | P3 khai rõ không đo precision; số precision **chỉ** ra ở P4 |
| Macro trên 3/6 họ bị đọc thành 6/6 | in kèm câu "3/6 họ" ngay cạnh mọi con số; `OFFICIAL_GOLDEN_READY` giữ `False` |
| Bỏ container ⇒ analyst đọc được thứ không nên đọc | in-process lane **chỉ** dùng cho visible suite và packet thật; hidden gate vẫn đòi Đường B |
| Tự chấm bài mình | giữ `reference_analyst` làm sàn bắt buộc trong mọi report; LLM không thắng sàn thì không có lý do ship |

## 6. Câu hỏi cần An quyết trước khi bắt đầu

1. **Đi Đường A hay chạy thẳng plan 19-08?** Đường A nhanh hơn ~3×, đổi lại
   hoãn phần sandbox.
2. **Ký KB v1 bây giờ hay để sau?** Ảnh hưởng tới mức claim cao nhất đạt được.
3. **Có cần 6/6 họ golden không, hay 3/6 là đủ cho mốc này?** Ba họ còn lại cần
   sweep nhiều context chứ không phải một episode — đó là một hạng mục riêng,
   không phải một buổi.
