# Chạy thật AI Analyst: o4-mini và hai model local

**Ngày:** 2026-08-26 · **Loại:** đánh giá — chạy model thật, **không đổi dòng code nào**
**Nhánh:** `tongduyan_ai-analyst-ban-8` (worktree `../P-011-analyst`), **chưa merge**
**Dữ liệu:** 3 packet golden vừa dựng ở A6.5 (`fixtures/golden/visible/`)
**Harness:** `planbench_analyst.harness.compare_with_floor` (A6)
**Kịch bản chạy:** để ở scratchpad, không commit — nó đọc `.env`, và một script
đọc khoá không nên nằm trong repo.

---

## 1. Bốn lượt chạy, và con số

| Model | repeats | Thời gian | Crash | Abstain | Đề xuất **qua guard** | Sàn đề xuất | Token vào | Token ra | Tool gọi |
|---|---|---|---|---|---|---|---|---|---|
| `o4-mini` (OpenAI) | 1 | 70,1 s | **0** | 1/3 | **2** | 3 | 16.277 | 7.938 | 2 |
| `o4-mini` | 3 | 302,8 s | **0** | 1/3 | 2 | 3 | 15.704 | 9.348 | 3 |
| `qwen3:8b` (Ollama) | 1 | 81,4 s | **0** | **3/3** | **0** | 3 | 8.612 | **274** | 0 |
| `llama3.2:3b` (Ollama) | 1 | 36,5 s | **0** | **3/3** | **0** | 3 | 8.915 | 730 | 0 |

`pass^k` = 1,0 ở cả bốn lượt — nhưng đọc đúng nghĩa: harness tính `pass^k` là
**"không crash mọi lần"**, không phải "đúng mọi lần". Chưa có precision vì 3
fixture này chưa có đáp án trồng sẵn theo dạng `score_case` chấm được.

## 2. Kết luận ngắn

**Đường ống chạy thật, từ đầu đến cuối, không sửa gì.** Packet → prompt → model
→ parse → guard → declare → tool call → revise → finalize. Bốn model, ba nhà
cung cấp khác nhau, **0 crash**.

**o4-mini là model duy nhất đề xuất được thứ đi qua guard.** Hai đề xuất sống
sót, và nó **thật sự gọi tool** (`get_candidate_contrast`, `gap_vs_footprint`).

**Hai model local đề xuất được 0.** `qwen3:8b` abstain thẳng (274 token ra cho
cả ba case — nó chọn im lặng); `llama3.2` có đề xuất nhưng **guard drop sạch**.
Sàn model-free đề xuất 3 trên cùng ba packet. Ở quy mô 8 GB VRAM, local **chưa
dùng được** cho tầng này.

**Nhưng o4-mini cũng chưa thắng sàn.** So sánh ghép cặp: `discordant = 2`,
`p = 1,0`, `underpowered = True`. Ba case là quá ít để kết luận bất cứ điều gì —
đúng thứ harness được thiết kế để tự khai thay vì để người đọc tự suy.

## 3. Guard bắt được gì trên model thật

Đây là phần đáng giá nhất: **năm luật khác nhau nổ trên output thật**, mỗi luật
đúng loại lỗi nó được viết ra để chặn.

| Luật | Model | Cụ thể |
|---|---|---|
| **6** `citation_contradicts_subject` | o4-mini | dẫn `fact:robot.radius_m` (packet quy cho `costmap_inflation`) để đỡ cho claim về `global_planner` |
| **5** `wording_above_associated` | o4-mini | viết `"caused"` trong statement ở tầng đề xuất |
| **4** `check_arguments_rejected` | o4-mini | xin `get_event_neighborhood` thiếu `event_index` |
| **3** `claim_blocked_by_packet` | llama3.2 | đề xuất claim type mà `known_unknowns` của packet đã chặn (2 lần) |
| **1** `ref_not_in_packet` | llama3.2 | bịa một citation |

Luật 6 là luật **mới của bản 8**, sinh ra từ ca A15 hôm 24-08 ("citation resolve
≠ citation ủng hộ"). Nó nổ trên lượt chạy thật **đầu tiên**, đúng mẫu lỗi đã dự
đoán: model dẫn một fact có thật, giá trị đúng, nhưng nói về component khác.

Luật 2 (cấm số trong statement) **không nổ lần nào** với o4-mini — nó tuân đúng.

## 4. Runner bắt được gì

- **`no_progress` nổ 2/3 case** ở lượt r=1: model xin lại đúng check đã chạy.
  Checker là tất định, nên vòng đó dừng thay vì đốt thêm một model call để nhận
  đúng câu trả lời cũ. Không có luật này thì mỗi case tốn thêm ~2.700 token ra.
- **`revisions_exhausted`** nổ 1 lần ở r=3: model liên tục tìm được check mới,
  và trần vòng sửa dừng nó.
- **`host:missing_required_evidence` ×2** ⟶ `routing_failures: unnecessary_tool: 2`:
  xin tool mà run này không có bằng chứng để phục vụ. Seam A4-iii làm đúng —
  `available_evidence` suy từ packet, và tool xin bừa bị host từ chối chứ không
  phải trả về rác.

## 5. Chất lượng nội dung: o4-mini **kém cụ thể hơn sàn**

Đọc tay từng đề xuất:

| | o4-mini | Sàn model-free |
|---|---|---|
| `inflation-001` | *"Performance variance is attributable to different global_planner components"* — quy trách nhiệm chung chung | (abstain — packet không có observation nào) |
| `dwa-001` | *"The performance difference arises from the global_planner component"* | *"the detour … is consistent with sampling budget insufficiency"* + *"the stuck_cluster … is consistent with local minimum entrapment"* — **hai cơ chế có tên** |

Ở lượt r=3, o4-mini có một đề xuất tốt hơn hẳn: *"Inflated robot footprint from
costmap_inflation made passing narrow passages geometrically infeasible"* kèm
xin `gap_vs_footprint` — đúng cơ chế được trồng ở `inflation-001`. Nhưng nó
**không ổn định**: cùng packet, lượt r=1 chỉ ra được câu chung chung.

Nói thẳng: trên ba fixture này, **o4-mini chưa cho thấy nó hơn một bảng tra
detection→cơ chế 30 dòng**. Cái nó thêm được — và sàn không có — là gọi được
tool và khai `missing_evidence` cụ thể.

## 6. Chi phí

o4-mini: **~5.400 token vào + ~2.600–3.100 token ra mỗi case**, ~23 s/case.
Token ra cao vì o4-mini là reasoning model — phần lớn là reasoning token, không
phải câu trả lời (câu trả lời JSON chỉ vài trăm token).

Local: `qwen3:8b` ~27 s/case, `llama3.2` ~12 s/case, không tốn tiền. Nhưng đổi
lấy 0 đề xuất qua được guard.

## 7. Một lỗi môi trường, không phải lỗi code

Lượt chạy đầu **401 Incorrect API key**. Nguyên nhân: `.env` có **hai** dòng
`OPENAI_API_KEY`, và script đọc bằng `setdefault` nên lấy dòng **đầu** — khoá
chết. Đổi sang "dòng sau thắng" (đúng cách dotenv đọc) thì chạy được ngay.

Đáng ghi vì triệu chứng đánh lừa: 401 đọc ra như "khoá của tài khoản hỏng", còn
thực tế là "file có hai dòng và ai đó đọc nhầm dòng". Nếu An còn giữ dòng cũ
trong `.env` thì nên xoá — công cụ khác cũng sẽ vấp.

## 8. Việc còn lại trước khi merge

| Việc | Ai |
|---|---|
| Precision/recall thật: cần fixture có `expected_findings` khớp `score_case`, hiện 3 fixture chưa có | code |
| 9/12 case suite còn thiếu, 3/6 họ chưa stage được | code + dữ liệu |
| Ablation critic (bật/tắt) trên cùng fixture | code, rẻ |
| Chọn model: o4-mini là ứng viên duy nhất đang chạy được; local chưa đủ | An |
| Xoá dòng `OPENAI_API_KEY` chết trong `.env` | An |
