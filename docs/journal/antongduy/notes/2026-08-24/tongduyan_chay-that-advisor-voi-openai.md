# Chạy thật AI Advisor với model OpenAI — hai lỗi chặn, và số đo đầu tiên

**Ngày:** 2026-08-24 · **Loại:** đánh giá hiện trạng, có gọi API thật — **không đổi
một dòng code repo nào**
**Nhánh:** `tongduyan_verify-ai-analyst`
**Phạm vi:** 3 run đã lưu × 2 loại advice (`diagnosis`, `outcome`) × 2 model =
12 lượt gọi. Ba run chọn theo ba hình dạng khác nhau, đúng bộ mà
`tests/test_report_advice.py` dùng: `gated` (1/2 candidate qua cổng, không card) ·
`carded` (card có khoảng tin cậy dứt khoát) · `tied` (khoảng vắt qua 0).
**Tiếp nối:** `tongduyan_danh-gia-chat-luong-ai-advisor.md` §5–§6 (viết lúc `.env`
chưa có key) — file này thay thế hai mục đó.
**Chi phí:** 79.318 token vào / 14.039 token ra, 12 lượt. Dưới 0,10 USD.

`gpt-o4-mini` không tồn tại; account có **cả hai** model bị trộn tên nên chạy cả hai:
`gpt-4o-mini` (thường) và `o4-mini` (reasoning).

---

## 1. Kết luận

**Advisor chưa từng chạy được với OpenAI.** Cả 12 lượt gọi đầu tiên đều trả HTTP
400 và **im lặng** rơi về tầng luật. Hai lỗi độc lập, cả hai đều nằm ở phía
PlanBench chứ không phải phía model:

| Lỗi | Trúng model nào | Hậu quả |
|---|---|---|
| Schema strict thiếu `do_not` trong `required` | **cả hai** | 400, không lượt nào tới được model |
| `ADVISOR_MAX_TOKENS = 32768` vượt trần 16.384 của gpt-4o-mini | gpt-4o-mini | 400 |

Vá tạm hai lỗi đó **trong script đo, không đụng repo**, thì cả hai model chạy được.
Và khi chạy được thì kết quả **tốt hơn mong đợi**: sàn luật nguyên vẹn 12/12 lượt,
không lượt nào bịa số, o4-mini tìm ra một bất nhất đo đạc mà tầng luật không thấy.

Nghĩa là: **cái hỏng là đường ống, không phải model.** Và cái hỏng đó ẩn được vì
`advise_with_model` nuốt mọi lỗi provider thành `refused` — đúng thiết kế, nhưng
không ai nhìn `refused` nên một lỗi 400 vĩnh viễn trông y hệt "model hôm nay không
thêm được gì".

## 2. Lỗi 1 — schema strict không hợp lệ, trúng mọi model

```
BadRequestError: 400 - Invalid schema for response_format:
In context=('properties','additions','items'), 'required' is required to be
supplied and to be an array including every key in properties. Missing 'do_not'.
```

`_schema_is_strict()` (`openai_provider.py:290`) **chỉ soi object ngoài cùng**:

```python
def _schema_is_strict(schema):
    if schema.get("additionalProperties") is not False:
        return False
    properties = set((schema.get("properties") or {}).keys())
    return properties == set(schema.get("required") or ())
```

`advisor_schema()` ở tầng ngoài thoả (đóng, mọi property required) nên đi kèm
`strict: true`. Nhưng object lồng trong `additions.items` khai `do_not` ở
`properties` mà **không** khai ở `required` — và luật strict của OpenAI áp
**đệ quy**. Server từ chối cả request.

**Hai chỗ đáng sửa, không phải một:**
- `advisor_schema()`: cho `do_not` vào `required` (strict mode vẫn cho phép
  optional bằng `type: ["string","null"]`).
- `_schema_is_strict()`: phải duyệt đệ quy. Hiện nó **hứa strict cho một schema
  chưa kiểm** — mọi schema khác trong repo có object lồng cũng dính lỗi này.

## 3. Lỗi 2 — trần token đặt cho reasoning model, chặn model thường

```
BadRequestError: 400 - max_tokens is too large: 32768.
This model supports at most 16384 completion tokens.
```

Comment ngay trên hằng số giải thích vì sao nó to:

```python
#: Reasoning models spend output budget thinking before the first token
#: of JSON; a small cap truncates the whole answer (measured: 8192 died
#: at 317 tokens on Gemini 3).
ADVISOR_MAX_TOKENS = 32768
```

Lý do đúng, nhưng một hằng số cứng cho mọi model thì **con số chữa cho model này
lại giết model kia**. gpt-4o-mini trần 16.384. Cần hỏi trần của model rồi lấy
`min(ADVISOR_MAX_TOKENS, trần_model)`, hoặc bắt riêng lỗi này và thử lại thấp hơn.

Đo được sau khi vá: o4-mini thực sự tiêu **1.261–2.681 token ra** một lượt (đúng
như comment cảnh báo), gpt-4o-mini chỉ **66–199**. Trần 32768 là đúng tinh thần,
sai cách áp.

## 4. Số đo sau khi vá — 12/12 lượt gọi tới được model

| model | case | kind | sàn luật | addition | fabricated | đổi bậc severity | vượt trần | token ra | giây |
|---|---|---|---|---|---|---|---|---|---|
| o4-mini | gated | diagnosis | nguyên | 3 | 0 | không | không | 2124 | 14,8 |
| o4-mini | gated | outcome | nguyên | 3 | 0 | không | không | 2681 | 18,3 |
| o4-mini | carded | diagnosis | nguyên | 2 | 0 | không | không | 1261 | 10,3 |
| o4-mini | carded | outcome | nguyên | 1 | **1** | không | không | 2656 | 18,2 |
| o4-mini | tied | diagnosis | nguyên | 3 | 0 | không | không | 2232 | 16,0 |
| o4-mini | tied | outcome | nguyên | 3 | 0 | không | không | 2492 | 17,2 |
| gpt-4o-mini | gated | diagnosis | nguyên | 0 | 0 | không | không | 76 | 2,8 |
| gpt-4o-mini | gated | outcome | nguyên | 1 | 0 | không | không | 199 | 3,0 |
| gpt-4o-mini | carded | diagnosis | nguyên | 0 | 0 | không | không | 67 | 1,3 |
| gpt-4o-mini | carded | outcome | nguyên | 0 | 0 | không | không | 66 | 4,0 |
| gpt-4o-mini | tied | diagnosis | nguyên | 0 | 0 | không | không | 90 | 1,8 |
| gpt-4o-mini | tied | outcome | nguyên | 0 | 0 | không | không | 95 | 1,6 |

Đọc bảng:

- **Sàn luật nguyên vẹn 12/12.** Không model nào bỏ được một advice luật nào.
- **Không lượt nào vượt trần 3 addition**, nên lỗ P9 (trần không thi hành ở server)
  hôm nay chưa nổ — nhưng nó vẫn là lỗ: không có gì chặn, chỉ là model tự ngoan.
- **Không lượt nào đổi bậc severity.** Lỗ P6 cũng chưa nổ.
- **`fabricated=1`** đúng một lượt: o4-mini/carded/outcome đề xuất một ý cite vào
  field không resolve được, bị bỏ và đếm. **Guard hoạt động đúng trên dữ liệu thật.**

### 4.1. Không có số nào bị bịa

Bộ lọc số của tôi kêu 5 lần, kiểm lại **cả 5 đều là báo nhầm**:

| Model viết | Trong source | Phán |
|---|---|---|
| "ΔU 0.03208, CI [0.03179, 0.03703]" | `0.03208101675705993`, `0.03178970745358651`, `0.037033078023420596` | làm tròn, không bịa |
| "70% success rate" | `success_rate: 0.7` | đổi đơn vị |
| "below the 95% requirement" | `success_rate_min: 0.95` | đổi đơn vị |

**Tỷ lệ bịa số trên dữ liệu thật: 0/12.** Cả hai model đều bám số nguồn.

### 4.2. Chênh lệch chất lượng giữa hai model rất rõ

**gpt-4o-mini** gần như không thêm gì: 1 addition trên 6 lượt, tiêu 66–199 token.
Nó xếp hạng lại và viết summary, hết. Với một lớp mà giá trị nằm ở *"ba ý luật
không nhìn thấy"* thì đây gần như là không có giá trị gia tăng.

**o4-mini** thêm 15 addition trên 6 lượt và ít nhất một ý **có giá trị thật**:

> `[material]` Candidate rrtstar+dwa's G5 `peak_search_nodes` is zero despite a
> nonzero memory estimate, indicating a measurement inconsistency
> — cite `report.candidates[1].gates.G5.peak_search_nodes`

Kiểm lại source: `peak_search_nodes` là `[31168, 0]`. **Đúng.** Candidate thứ hai
báo 0 node trong khi vẫn có ước lượng bộ nhớ khác 0 — một bất nhất đo đạc mà
không luật nào trong `GATE_ADVICE_CODES` bắt. Đây đúng loại việc đề bài giao cho
model: *"a mismatch between two fields, an assumption nobody declared"*.

Một ý khác cũng đúng trọng tâm:

> `[material]` The observed 3× difference in p99 latency arises partly from
> different `local_controller_config` settings (dwa_coarse vs dwa_balanced), not
> solely from global-planner sampling.

Đây là cảnh báo **quy kết nhầm thành phần** — đúng thứ §5.2 của note thiết kế
"vì sao" gọi là `interaction_not_isolated`. Model tự nhìn ra mà không ai dạy.

### 4.3. Điều phải nói cho công bằng

15 addition của o4-mini **chưa được chấm từng cái**. Tôi mới kiểm số và kiểm
citation, chưa kiểm *ý có đúng không*. Hai ý trên đúng; 13 ý còn lại chưa ai đọc
kỹ. Muốn có precision thật thì phải đọc tay cả 15 — việc nửa buổi, chưa làm.

## 5. Đề xuất sửa, xếp theo thứ tự

1. **`advisor_schema()`**: `do_not` vào `required`. Một dòng. Không có nó thì
   advisor **không chạy với OpenAI, chấm hết**.
2. **`_schema_is_strict()`**: duyệt đệ quy. Không có nó thì lỗi 1 sẽ quay lại ở
   schema tiếp theo có object lồng, và `critique.py` / `paper.py` / `plugin_author.py`
   cần được rà cùng.
3. **`ADVISOR_MAX_TOKENS`**: lấy `min(hằng số, trần của model)`.
4. **Đừng để lỗi provider chìm.** `refused` hiện chỉ là một trường trong response.
   Một lỗi 400 vĩnh viễn phải kêu ở log mức warning, và nên hiện trên UI — hiện
   người dùng bấm "hỏi model" và thấy đúng danh sách luật cũ, không cách nào biết
   là model chưa từng được gọi.
5. **Thêm một test smoke chạy schema thật qua validator strict của OpenAI** (không
   cần gọi mạng: viết lại luật strict thành hàm kiểm nội bộ). Đây chính là lỗ mà
   note trước gọi là B2 — mọi test đều dùng `MockProvider` nên hai lỗi trên sống
   sót qua toàn bộ suite.

Bốn lỗ trong note trước (trần addition không thi hành, đổi bậc severity, blocking
thiếu `do_not`, prompt injection) **vẫn còn nguyên** — hôm nay chưa nổ vì model
ngoan, không phải vì có ai chặn.

## 6. Trả lời gọn

| Câu hỏi | Trả lời |
|---|---|
| Advisor chạy được với OpenAI chưa? | **Chưa.** Hai lỗi 400, im lặng rơi về luật |
| Vá xong thì model làm được việc không? | **Có** — o4-mini rõ ràng có giá trị gia tăng |
| Model có bịa số không? | **Không.** 0/12 lượt |
| Model có phá sàn luật không? | **Không.** 12/12 nguyên vẹn |
| Chọn model nào? | **o4-mini.** gpt-4o-mini gần như không thêm gì (1 ý/6 lượt) |
| Giá? | 12 lượt hết dưới 0,10 USD. o4-mini chậm (10–18 s/lượt) |

---

## Phụ lục — chạy lại

```bash
# Bản như repo đang có: mọi lượt đều REFUSED
.venv/Scripts/python.exe docs/antongduy/notes/2026-08-24/tongduyan_advisor_live_eval.py

# Vá tạm hai lỗi trong bộ nhớ tiến trình, không đụng repo
ADVISOR_SCHEMA_FIX=1 ADVISOR_MAX_TOKENS_CAP=16000 \
  .venv/Scripts/python.exe docs/antongduy/notes/2026-08-24/tongduyan_advisor_live_eval.py
```

Cần `pip install openai` (đã cài vào `.venv` hôm nay — 3.3.1) và `OPENAI_API_KEY`
trong `.env`. Kết quả thô: `tongduyan_advisor_live_results_patched.json` và
`..._patched_4omini.json`.
