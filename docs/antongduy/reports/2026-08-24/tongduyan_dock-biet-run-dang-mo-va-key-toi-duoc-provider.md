# Trợ lý biết được run đang mở, và key trong `.env` tới được provider

**Ngày:** 2026-08-24 · **Loại:** báo cáo đổi code
**Nhánh:** `tongduyan_verify-ai-analyst` — **không đụng `main`** trong lúc làm
**Nền:** `notes/2026-08-24/tongduyan_danh-gia-chat-luong-ai-advisor.md` ·
`reports/2026-08-24/tongduyan_va-loi-ai-advisor.md` (cùng ngày, phần trước)
**Kiểm chứng:** 129 test ở mọi vùng đã chạm, xanh · ruff sạch · An xác nhận trên UI

---

## 1. Bối cảnh

An mở dock trên trang một run và hỏi *"vì sao run này kết thúc như vậy"*. Trợ lý
gọi `list_decision_runs` rồi dừng. Câu hỏi An đặt ra đúng chỗ: **cơ chế nào cho hệ
biết đang trỏ tới run nào?**

Câu trả lời lúc đó: **không có cơ chế nào.** `askAgent` gửi đúng `{ message }`.
Không run id, không route. Điều An mong đợi là một tính năng chưa xây, không phải
một prompt viết sai.

Và sau khi xây xong, hoá ra còn một tầng nữa chặn phía sau: key trong `.env`
**chưa bao giờ** tới được nơi code đi tìm nó.

## 2. Dock mang theo run đang mở

### 2.1. Đọc từ route, không luồn prop

```ts
function runOnScreen(pathname: string | null): string {
  const match = /^\/decisions\/([^/]+)\/?$/.exec(pathname ?? "");
  return match ? decodeURIComponent(match[1]) : "";
}
```

Dock nổi trên mọi trang từ shell. Luồn prop qua từng trang để tới một component
không trang nào render là rất nhiều sửa đổi cho một sự thật mà URL đã mang sẵn.

### 2.2. Gửi định danh, không gửi chữ

```json
{ "message": "…", "context": { "run_id": "5753d464c9f6" } }
```

`ChatContext` khai `extra="forbid"`, chỉ hai trường id. Một mô tả ghép ở trình
duyệt là **chữ của trang tới đúng chỗ chỉ thị nằm** — và deployment thì chủ nó
muốn đặt tên gì cũng được. Cùng một luật với `<<<SOURCE` vừa làm cho advisor
sáng nay.

### 2.3. Server tra lại, qua gateway của chính user

`_resolve_context()` gọi `agent.gateway.get_decision_run(run_id)`. Hai tác dụng:

- id bịa ra không tới được model — một model được bảo rằng run X tồn tại sẽ nói
  về run X;
- run mà user không có quyền đọc thì cũng không gắn được, vì lookup đi qua đúng
  gateway mà tool đi qua.

Trả về là **định danh, không phải nội dung**. Dán cả run vào đây là trả lời từ
một snapshot endpoint tự chọn, trong khi luật trung thực ở `CHAT_SYSTEM` viết cho
**tool result**. Model vẫn phải gọi tool.

### 2.4. Preamble vào user turn, không vào system prompt

Người đọc đang mở trang nào là **một sự thật về câu hỏi**, không phải một trong
các luật model trả lời dưới đó. Đặt vào system prompt là để hiến pháp của model
đổi theo route.

### 2.5. Khai báo, không ngầm

Chip ngay dưới header: *"Đang hỏi về lượt chạy đang mở trên trang này"* + nút
*"Hỏi chuyện khác"*. Mặc định gắn; đổi trang thì gắn lại.

Gắn ngầm mà người đọc không thấy thì đúng là **hidden context** mà docstring của
`chat()` viết ra để tránh. Hiện lên thì nó là ngữ cảnh khai báo, và An từ chối
được.

Và khi context gửi đi mà **không tra ra**, câu trả lời mang một dòng nói rõ.
"Đã gửi rồi hỏng" khác hẳn "không gửi", và chỉ cái đầu mới đánh lừa: người đọc
vừa nhìn thấy chip nói câu hỏi này về run trước mặt.

## 3. Một lỗi trên đường, và vì sao test không bắt được

Bản đầu đọc `run["id"]`. `KeyError` ngay câu hỏi đầu tiên.

`get_decision_run` trả về **stored report**, không phải bản ghi run:

```python
def get_decision_run(self, run_id: str) -> dict[str, Any]:
    return dict(self._lookup_run(run_id).report or {})
```

Không có khoá `id`; `task_profile_id` nằm dưới `identity`.

**Ba test của tôi đều xanh.** Cả ba dùng stub tôi tự nghĩ ra hình dạng, thống
nhất với nhau về một khoá mà gateway thật chưa bao giờ có. Stub cùng tác giả với
code thì không kiểm được gì ngoài việc tác giả nhất quán với chính mình.

Sửa: id lấy từ **chính caller** — lookup trả về được đã là bằng chứng id có thật
và user đọc được; deployment lấy từ `report["identity"]["task_profile_id"]` có
fallback.

Và thêm `TestTheContextAgainstARealRun`: tạo task profile thật, chạy
`POST /decisions` thật, hỏi kèm run id đó, đòi `context_used is True`. Đi qua
nguyên stack, chạy 50 s. Đó là cái giá để phân biệt một hình dạng với một phỏng
đoán, và là test lẽ ra phải có từ đầu.

## 4. Key trong `.env` chưa bao giờ tới được provider

Context chạy rồi, trợ lý vẫn trả lời bằng mock. Hai luật, mỗi luật đúng riêng, và
chúng không gặp nhau:

- `config.py`: *"API keys are read from each provider's own environment variable —
  **never a PlanBench setting**, never stored in a config file in the repository."*
- `.env`: *"Paste the key for whichever provider you use."*

pydantic-settings đọc `.env` vào **object Settings**; `build_provider` đọc thẳng
`os.environ`. `PLANBENCH_AGENT_MODEL` tới nơi vì nó **là** một field của Settings.
`OPENAI_API_KEY` không phải field nào cả, nên nó nằm yên trong file.

Đo trước khi sửa:

```
agent_model = 'o4-mini'                            ← tới nơi
openai  ready=False  missing=set OPENAI_API_KEY    ← không
```

Cấu hình trông đầy đủ, `auto` không thấy provider nào sẵn sàng, rơi về mock. Im
lặng và trọn vẹn — và trên UI nó hiện thành một câu hoàn toàn hợp lệ
("Trả lời ngoại tuyến theo từ khoá"), chỉ là câu sai với người vừa dán key.

### Sửa

`load_provider_keys()` trong `config.py`, gọi ở startup **trước** khi dựng
provider. Ba ràng buộc:

- **Chỉ copy đúng các biến key**, theo danh sách tên mà chính `provider_status()`
  công bố — `.env` không với tay đặt được một biến process bất kỳ.
- **Shell thắng file.** Key export cho một lần chạy là chủ ý rõ hơn một dòng
  trong file.
- **Giá trị rỗng không phải là key.** `.env` liệt kê đủ 7 provider với 6 dòng
  trống; copy chúng là đặt biến thành chuỗi rỗng — trông như đã cấu hình mà
  không phải.

Key **vẫn không** trở thành field của Settings, nên luật "never a PlanBench
setting" giữ nguyên: nó không lọt vào bản dump settings hay dòng log nào in
settings. Startup log `provider keys read from .env: OPENAI_API_KEY`.

Kiểm chứng qua chính đường code khởi động:

```
keys filled from .env: ('OPENAI_API_KEY',)
  ready: openai
provider = openai | model = o4-mini | deterministic = False
```

## 5. Test đã thêm

| Test | Canh cái gì |
|---|---|
| `test_a_context_that_names_nothing_real_is_dropped` | §2.3 |
| `test_the_context_carries_identifiers_only` (422) | §2.2 |
| `test_a_resolved_run_names_itself_and_its_deployment` | §3, đúng shape thật |
| `test_a_report_with_no_identity_block_still_names_the_run` | report cũ thiếu trường |
| `test_a_run_the_caller_may_not_read_yields_no_context` | §2.3 |
| `TestTheContextAgainstARealRun` | §3 — đi qua gateway thật |
| `test_the_preamble_reaches_the_model_ahead_of_the_question` | §2.4 |
| `test_it_is_a_user_turn_not_a_rule` | §2.4 |
| `test_no_preamble_leaves_the_question_exactly_as_typed` | §2.4 |
| 5 test `load_provider_keys` | §4 — kể cả `PATH_TO_SOMETHING=/etc/passwd` bị chặn |

## 6. File đã đổi

```
apps/api/planbench_api/config.py              §4
apps/api/planbench_api/main.py                §4
apps/api/planbench_api/routers/agent.py       §2.2 §2.3 §3
services/agent_service/planbench_agent/workflow.py   §2.4 + accessor gateway
services/agent_service/planbench_agent/openai_provider.py   dọn SIM102 của phần trước
apps/web/src/lib/agent.ts                     §2.1 §2.2
apps/web/src/components/AgentDock.tsx         §2.1 §2.5
apps/web/src/app/globals.css                  §2.5
apps/web/src/lib/i18n/locales/{en,vi}.json    4 khoá mỗi ngôn ngữ, không đụng gì khác
tests/api/test_api_agent.py · tests/api/test_config.py · tests/test_agent_workflow.py
```

## 7. Còn nợ

**Không gửi history** — An đã chốt tạm để nguyên. Hội thoại nhiều lượt vẫn không
hoạt động: hỏi *"còn candidate B thì sao?"* là model mất trí nhớ. Lật quyết định
đó là một việc riêng, có lý do đã ghi rõ trong docstring.

**Ba test đỏ và ba lỗi tsc ở web** — đều có **trước** phần việc này. Chúng đòi
`paper.uploadHint`, `advice.do`, `preflight.check`, `reportAdvice.title`… mà kiểm
ở `HEAD` thì chưa từng tồn tại. Diff locale của tôi đúng 4 dòng mỗi ngôn ngữ.
Chưa dọn — chờ An quyết.
