# Agentic AI (M8)

> Bản đồ đầy đủ "AI làm được gì, kiểm ở đâu" nằm ở
> [`AI_CAPABILITIES.md`](AI_CAPABILITIES.md). Tài liệu này đi sâu kiến
> trúc tầng agent.

Tầng agent nằm ở `services/agent_service/planbench_agent/`. Nguyên tắc
chi phối toàn bộ thiết kế: **LLM đề xuất, hệ thống quyết định**. Mọi câu
trả lời đều phải truy ngược được về dữ liệu đã ghi, và mọi hành động
thay đổi trạng thái đều đi qua một cổng do code kiểm soát.

## Module

| Module | Vai trò |
|---|---|
| `provider.py` | Abstraction `LLMProvider` + kiểu message/tool. **Không có tên nhà cung cấp nào ở đây.** |
| `anthropic_provider.py` | Adapter Anthropic (native API), import SDK lazy |
| `openai_provider.py` | Adapter cho **mọi** provider nói giao thức OpenAI Chat Completions: OpenAI, Gemini, OpenRouter, Groq, DeepSeek, xAI, model local |
| `deterministic.py` | Responder rule-based cho `MockProvider`: chạy được toàn bộ M8 khi không có API key. |
| `factory.py` | Chọn provider + báo trạng thái sẵn sàng của từng cái |
| `gateway.py` | Protocol `AgentGateway` — đúng bằng những gì agent được phép làm |
| `tools.py` | Tool registry, phân loại `Effect.READ/WRITE`, policy |
| `paper.py` | Đọc paper người dùng tải lên → candidate draft, mỗi giá trị kèm câu nguồn |
| `critique.py` | Phản biện một decision run, chồng lên luật tất định của `planbench_decision.self_check` |
| `workflow.py` | State machine phiên làm việc + vòng lặp tool |

Adapter phía API: `apps/api/planbench_api/agent_gateway.py`.
Router: `apps/api/planbench_api/routers/agent.py`.

## Provider abstraction

Domain code chỉ import `planbench_agent.provider`. Không có tên vendor
nào trong domain logic; hai adapter là chỗ duy nhất biết vendor tồn tại.

### Provider hỗ trợ sẵn

| Tên | Biến môi trường | SDK | Endpoint |
|---|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` | `anthropic` | native API |
| `openai` | `OPENAI_API_KEY` | `openai` | mặc định của SDK |
| `gemini` | `GEMINI_API_KEY` | `openai` | `generativelanguage.googleapis.com/v1beta/openai/` |
| `openrouter` | `OPENROUTER_API_KEY` | `openai` | `openrouter.ai/api/v1` |
| `groq` | `GROQ_API_KEY` | `openai` | `api.groq.com/openai/v1` |
| `deepseek` | `DEEPSEEK_API_KEY` | `openai` | `api.deepseek.com` |
| `xai` | `XAI_API_KEY` | `openai` | `api.x.ai/v1` |
| `local` | *(không cần)* | `openai` | `localhost:11434/v1` (Ollama/vLLM) |
| `mock` | *(không cần)* | *(không cần)* | offline, tất định |

**Vì sao một adapter cho nhiều vendor.** OpenAI định nghĩa giao thức
Chat Completions; Google phơi Gemini qua endpoint tương thích OpenAI
chính thức; OpenRouter, Groq, DeepSeek, xAI, vLLM, Ollama đều cài đặt
nó. Viết **một** adapter cẩn thận cho giao thức đó phủ được tất cả và
giữ một code path duy nhất trong test — tốt hơn nhiều adapter mỗi cái
viết theo trí nhớ về SDK của từng hãng. Vendor nào có tính năng ngoài
giao thức này (ví dụ grounding native của Gemini) vẫn thêm adapter
riêng được — đó chính là lý do có `LLMProvider`; domain không đổi.

Hai khác biệt so với wire format của Anthropic mà adapter phải xử lý:
tool result là **mỗi cái một message** (`role: "tool"`) chứ không gom
vào một user turn; và tool arguments về dưới dạng **chuỗi JSON** chứ
không phải object.

### Assistant turn phải phát lại nguyên văn

Adapter **không** dựng lại assistant message từ text + tool_calls đã
parse. Nó giữ nguyên payload provider trả về (`ProviderTurn`) và gửi lại
y hệt.

Lý do cụ thể: Gemini ký mỗi function call bằng `thought_signature` và
**từ chối lượt tiếp theo** nếu chữ ký không quay lại —
`Function call is missing a thought_signature`. Dựng lại từ các trường
đã parse làm mất nó. Anthropic có cùng vấn đề ở dạng khác: thinking
block phải được echo lại nguyên vẹn khi lượt chưa kết thúc.

Giữ nguyên văn thay vì nhặt đúng một trường có nghĩa là adapter **không
cần biết** hãng nào đặt tên metadata là gì — hãng sau thêm trường mới
vẫn chạy.

`ProviderTurn.format` đánh dấu **wire format**, không phải vendor
(`openai-chat` / `anthropic-messages`). Turn của format khác bị bỏ qua
và dựng lại — một transcript có thể sống lâu hơn một lần đổi provider,
và nhồi content block của Anthropic vào request Chat Completions còn tệ
hơn là dựng lại.

Lỗi provider trả về HTTP **502** (`provider_error`) kèm nguyên văn thông
báo của hãng; thiếu key trả **503** (`provider_unavailable`) kèm cách
sửa. Trước đây cả hai rơi vào handler chung và thành `500 internal server
error`, làm mất đúng phần có ích.

### Chọn provider

`build_provider("auto")` thử theo thứ tự `AUTO_ORDER` (Anthropic trước,
vì adapter đó viết theo tài liệu first-party), lấy provider đầu tiên có
đủ key **và** SDK; không có gì thì rơi về mock tất định. Thiếu key làm
agent yếu đi chứ **không** làm hỏng platform.

`local` **không** nằm trong `AUTO_ORDER`: một cổng localhost không ai
nghe không nên âm thầm trở thành provider được chọn. Phải gọi tên nó.

Chọn provider tường minh mà không dùng được thì **không** âm thầm hạ
cấp: `ProviderUnavailable` nêu đúng thứ còn thiếu.

`PLANBENCH_AGENT_MODEL` là **bắt buộc** với mọi provider trừ
`anthropic`. Model id ở các hãng đó đổi đủ thường xuyên để một giá trị
hardcode sớm muộn cũng 404, và đoán một cái còn tệ hơn là hỏi. Nếu có
key nhưng thiếu model, `auto` bỏ qua provider đó và ghi log lý do.

Key **chỉ** đọc từ biến môi trường của chính nhà cung cấp. Nó không phải
setting của PlanBench, không nằm trong file config nào trong repo.

### Dán key vào

```bash
cp .env.example .env          # .env đã nằm trong .gitignore
# sửa .env: PLANBENCH_AGENT_PROVIDER, PLANBENCH_AGENT_MODEL, và key

# cần phê duyệt trước khi cài:
.venv/bin/pip install openai        # openai / gemini / openrouter / groq / deepseek / xai / local
.venv/bin/pip install anthropic     # anthropic

# kiểm chứng bằng một lần gọi thật trước khi tin
PYTHONPATH="packages/schemas:packages/planning:packages/metrics:\
packages/benchmark:services/simulator:services/tracking:\
services/agent_service:ml:apps/api" \
  .venv/bin/python scripts/check_agent_provider.py
```

`scripts/check_agent_provider.py` in bảng provider nào đã sẵn sàng, rồi
gọi **một** request thật: một completion thường, và một lần structured
output (mission parsing phụ thuộc vào nó — model không hỗ trợ
`json_schema` thì agent sẽ từ chối thay vì đoán, an toàn nhưng vô dụng).

`GET /agent/capabilities` cũng trả `providers[]` gồm `ready` và
`missing`, nên câu hỏi "sao vẫn đang dùng mock?" trả lời được từ API
chứ không phải từ log server.

**Mock provider không phải LLM.** Nó khớp từ khóa, không hiểu ngôn ngữ.
Điều nó bảo đảm là mọi lớp bảo vệ xung quanh — validate schema, cổng
approval, kiểm tra trích dẫn — được chạy thật. Mọi response đều mang
`provider` / `deterministic` để người đọc không nhầm câu trả lời khớp
từ khóa với câu trả lời do model viết.

## Điều agent **không** làm được

Không phải bằng prompt, mà bằng việc không tồn tại đường dẫn tới chúng:

| Bị cấm | Cơ chế |
|---|---|
| Điều khiển `/cmd_vel`, actuation | `AgentGateway` không có method nào như vậy |
| Sửa/bịa map, scenario | Chỉ chọn được tên có sẵn trong `SCENARIO_LIBRARY`; map do `build_scenario()` dựng |
| Bịa metric, kết quả | Không có tool ghi metric; evidence lấy thẳng từ storage |
| Approve benchmark (gate 1) | Không có tool; `run_benchmark` kiểm tra state `approved` trước, gateway kiểm tra lần hai |
| Accept/reject kết quả (gate 2) | Không có tool; báo cáo trước khi được accept luôn gắn nhãn PROVISIONAL |
| Kết luận planner an toàn | Prompt cấm + `contains_safety_claim()` + disclaimer gắn vào mọi báo cáo |

Danh sách được ghi tường minh trong `tools.FORBIDDEN_CAPABILITIES` để
người thêm tool sau này phải **xóa một dòng nói rằng đừng làm thế**,
chứ không chỉ quên mất.

**`astar+ppo` không nằm trong menu của agent.** Stack này cần
`model_path` trỏ tới checkpoint đã train. Agent không có cách nào biết
checkpoint nào là đúng, và bịa một đường dẫn chính là kiểu bịa mà spec
cấm — nên mọi stack có config bắt buộc đều bị loại khỏi
`agent_selectable_algorithms()`. Muốn benchmark PPO thì người dùng tự
tạo benchmark qua endpoint thường và chỉ định checkpoint.

## Mission → spec

```
mission text
  → provider (structured output, schema enum hóa scenario + algorithm)
  → MissionDraft (Pydantic, extra="forbid")
  → validate_draft() đối chiếu registry thật
  → DRAFT benchmark → submit → PENDING_APPROVAL  ⟵ dừng ở đây
```

Hai lớp kiểm tra độc lập đứng giữa câu trả lời của model và một benchmark
được lưu. Trượt lớp nào cũng là **refusal**: phiên chuyển sang `REFUSED`,
không có gì được tạo. Refusal trả về HTTP 201 kèm `refusal` chứ không
phải lỗi — "tôi không biến được câu đó thành benchmark, và đây là lý do"
là một kết quả hợp lệ.

## Evidence và citation

Citation có dạng `[kind:locator]`, ví dụ `[aggregate:a1b2c3d4e5f6#astar+dwa]`.
Cố tình xấu và máy đọc được: `extract_citations()` bắt hết, rồi
`generate_report()` đối chiếu với `EvidenceBundle`. Một id không có
trong bundle → `FabricatedCitation`, **hủy toàn bộ báo cáo**. Trích dẫn
bịa nguy hiểm hơn không có báo cáo, vì nó trông có vẻ kiểm chứng được.

Ba trường hợp đều là refusal, trả về như một giá trị chứ không ném lỗi:

- không đủ bằng chứng (`INSUFFICIENT EVIDENCE`);
- model tự nói không đủ bằng chứng;
- văn bản không có trích dẫn nào → không kiểm chứng được → hủy.

Endpoint `/agent/benchmarks/{id}/evidence` phơi bày bundle riêng, để
reviewer audit được đầu vào của báo cáo mà không cần đọc báo cáo.

## Không có kho tài liệu, và đó là thiết kế

Trước đây tầng này có một corpus TF-IDF trên `docs/` và `contracts/` —
136 tài liệu, 3.023 chunk. Nó đã bị gỡ bỏ hoàn toàn.

Lý do: hơn một nửa corpus là tài liệu nội bộ của team — nhật ký thiết
kế, kế hoạch, ghi chú khoá học. Một tài liệu lệch khỏi code không làm
agent dốt đi, nó làm agent **sai một cách tự tin**, và câu trả lời sai
đó lại kèm citation id trông rất đáng tin. Chuyện này không phải giả
định: một tài liệu kiến trúc trong `docs/` ghi bảy stack và một
`dwa_predictive` chưa từng tồn tại.

Agent giờ lấy thông tin từ đúng hai nguồn, cả hai đều kiểm chứng được:

**Database.** Mười công cụ chỉ đọc (`list_*`, `get_*`) trả về deployment,
candidate, scenario, decision run, decision card, bảng cổng và critique
đã lưu. Không công cụ nào có động từ ghi, và `FORBIDDEN_CAPABILITIES`
công bố danh sách cấm qua API để kiểm được thay vì phải tin.

**Paper do người dùng cung cấp.** `paper.py` đọc một tài liệu, do một
người chọn, và mỗi tham số trích ra **phải kèm câu nguồn có thật trong
tài liệu đó**; câu không khớp thì giá trị bị loại và đếm vào `unquoted`,
hiển thị công khai. Đó là hợp đồng khác hẳn một corpus không ai đọc lại.

## Endpoint

| Method | Path | Role | Ghi chú |
|---|---|---|---|
| GET | `/api/v1/agent/capabilities` | operator, reviewer | provider, model, tool, danh sách cấm |
| POST | `/api/v1/agent/chat` | operator, reviewer | một lượt hội thoại có tool |
| POST | `/api/v1/agent/missions` | operator | parse mission, tùy chọn `submit` |
| POST | `/api/v1/agent/benchmarks/{id}/run` | operator | 409 nếu chưa được approve |
| GET | `/api/v1/agent/benchmarks/{id}/evidence` | operator, reviewer | bundle bằng chứng |
| POST | `/api/v1/agent/benchmarks/{id}/report` | operator, reviewer | báo cáo có trích dẫn |

Agent chạy **dưới danh nghĩa user đang gọi**, nên benchmark do agent tạo
được quy về một người thật và separation of duties vẫn áp dụng: người đó
không được tự approve.

## Cấu hình

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `PLANBENCH_AGENT_PROVIDER` | `auto` | `auto`, `mock`, `anthropic`, `openai`, `gemini`, `openrouter`, `groq`, `deepseek`, `xai`, `local` |
| `PLANBENCH_AGENT_MODEL` | `` | **Bắt buộc** trừ `anthropic` (mặc định `claude-opus-5`) |
| `PLANBENCH_AGENT_BASE_URL` | `` | Ghi đè endpoint (self-host hoặc proxy) |
| `PLANBENCH_AGENT_KNOWLEDGE_DIRS` | `docs` | Thư mục Markdown để index, phân tách bằng dấu phẩy |
| `PLANBENCH_AGENT_MAX_EPISODES` | `60` | Trần số episode agent được đề xuất trong một benchmark |
| `ANTHROPIC_API_KEY` | — | Của nhà cung cấp, **không** phải setting PlanBench |

## Trạng thái kiểm thử

**Chưa provider ngoài nào được chạy thật** — môi trường này không có key
nào, và cả `anthropic` lẫn `openai` đều chưa cài. Cụ thể:

| Phần | Đã kiểm chứng thế nào |
|---|---|
| Dịch request/response (nơi bug thật nằm) | Test với object giả, không đụng mạng |
| Bảng preset, chọn provider, báo trạng thái | Test với env giả lập |
| Cổng approval, trích dẫn, refusal | Test end-to-end với mock tất định |
| Gọi mạng thật tới OpenAI/Gemini/... | **Chưa** — cần key |

Nói thẳng: adapter OpenAI-compatible viết theo giao thức đã tài liệu
hoá, nhưng chưa lần nào chạm một endpoint sống. Lần đầu dán key vào,
chạy `scripts/check_agent_provider.py` trước; nó tồn tại chính vì lý do
này. Nếu một hãng lệch giao thức ở chỗ nào đó, script sẽ lộ ra ngay
trong một request thay vì lộ ra giữa lúc chạy benchmark.
