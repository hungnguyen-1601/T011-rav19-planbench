# Vá tầng AI Advisor — hai lỗi chặn hoàn toàn, năm lỗ, một cổng chết trên Windows

**Ngày:** 2026-08-24 · **Loại:** báo cáo đổi code
**Nhánh:** `tongduyan_verify-ai-analyst` (tách từ `main` tại `cadf1ec`) — **không đụng `main`**
**Nền:** ba note cùng ngày trong `notes/2026-08-24/`
**Kiểm chứng:** 313 test ở mọi vùng đã chạm, xanh trong 1,12 s · bộ răng `bites`
**14/14 cắn** (trước: 12/14) · probe đối kháng **6/12 lọt** (trước: 11/12) · 12/12 lượt
gọi OpenAI thật thành công (trước: 0/12)

---

## 1. Đã sửa gì

### 1.1. `_schema_is_strict()` chỉ soi tầng ngoài cùng — advisor chết với mọi model OpenAI

`openai_provider.py`. Hàm quyết định có gắn `strict: true` vào request hay không, và
nó chỉ kiểm object ngoài cùng. `advisor_schema()` thoả ở tầng ngoài nên được gắn
`strict`, nhưng object lồng trong `additions.items` khai `do_not` ở `properties` mà
không khai ở `required` — luật strict của OpenAI áp **đệ quy**, nên server từ chối
cả request:

```
400 - In context=('properties','additions','items'), 'required' is required to be
supplied and to be an array including every key in properties. Missing 'do_not'.
```

Hàm cũ **hứa strict cho một schema chưa kiểm**. Sửa thành duyệt đệ quy: mọi object
(kể cả trong `items`, `anyOf`/`oneOf`/`allOf`) phải đóng và khai đủ `required`; node
lá không mang luật nào.

Rà lại bốn schema đang gửi đi sau khi sửa: `advisor` ✓ · `critique` ✓ · `paper` ✓ ·
`plugin_author` ✗ — nhưng `plugin_author` **đã** ✗ dưới luật cũ, nên không có
regression, chỉ có một chỗ vốn đã không dùng strict.

### 1.2. `advisor_schema()` thiếu `do_not` trong `required`

Một dòng. `do_not` vào `required`; addition không có nước cấm thì gửi chuỗi rỗng.
Không có dòng này thì advisor **không chạy với OpenAI, chấm hết**.

### 1.3. `ADVISOR_MAX_TOKENS = 32768` vượt trần của model thường

Comment trên hằng số giải thích vì sao nó to (reasoning model tiêu budget để nghĩ
trước khi ra token JSON đầu tiên). Lý do đúng, nhưng một hằng số cứng cho mọi model
thì con số chữa cho model này lại giết model kia:

```
400 - max_tokens is too large: 32768. This model supports at most 16384.
```

Sửa ở `openai_provider.complete()`: bắt đúng lỗi đó, **đọc trần ra khỏi chính thông
điệp lỗi** (`_completion_ceiling()`), log warning, gọi lại một lần dưới trần. Đọc từ
thông điệp chứ không lập bảng model: bảng sẽ sai đúng tuần một model mới ra, còn API
thì nói thẳng con số trong cùng câu từ chối. Lỗi không nêu trần thì **không** thử lại.

Đo được sau khi sửa: o4-mini tiêu 1.983–3.539 token ra một lượt (đúng như comment
cảnh báo), gpt-4o-mini 72–430. Trần 32768 đúng tinh thần, sai cách áp.

### 1.4. Trần `MAX_MODEL_ADVICE` không được thi hành ở server

`maxItems` trong JSON Schema là **lời đề nghị gửi provider**, không phải bảo đảm —
nó không nằm trong hợp đồng strict mode, và `_Payload.additions` không có
`max_length`, vòng lặp không cắt. Probe đưa 8 addition vào thì **xuất bản đủ 8**.

Sửa: cắt trong vòng lặp sau khi qua kiểm citation.

### 1.5. Model đẩy được advice `blocking` xuống dưới `disclosure`

`_ranked` cho hoán vị tuỳ ý; `AdviceListView.tsx:50` render đúng thứ tự server trả,
không sắp lại. Vị trí được người đọc hiểu là mức khẩn.

Sửa: khoá sort theo `(severity, vị trí model khai, thứ tự gốc)`. Model vẫn sắp được
**trong từng bậc** severity, không đổi được bậc.

### 1.6. Addition `blocking` không phải nêu nước cấm

Tầng luật bị bắt buộc nêu `do_not` cho mọi mục blocking; addition của model chỉ bắt
buộc `do`. Sửa: blocking mà `do_not` rỗng thì hạ xuống `material` — giữ lại nội
dung, không giữ sức nặng nó chưa trả giá.

### 1.7. `source` cắt giữa JSON, và không phân biệt dữ liệu với chỉ thị

`json.dumps(source)[:60_000]` cắt theo ký tự. Report dài làm JSON đứt giữa chừng;
model đọc lệch key rồi cite những path **vẫn resolve được**, nên bộ kiểm bịa đặt cho
qua. Đã xác nhận: `json.loads` trên nửa SOURCE thất bại.

Sửa bằng `_pack()`: rút ngắn các list dài nhất theo bậc (200 → 50 → 20 → 5 → 1 → 0),
giữ nguyên hình dạng object, và **nói trong chính tài liệu** cái gì bị bỏ
(`"… N more entries not shown"`). Đo lại: 44.949 ký tự, parse JSON được.

Cùng chỗ, bọc source trong delimiter và nói rõ đây là **giá trị đã ghi, không phải
chỉ thị** — tên deployment và `candidate_id` là do người dùng nhập.

### 1.8. Lỗi provider chìm mất

Mọi đường degrade giờ đi qua `_refused()`, có `logger.warning`. `refused` là câu trả
lời cho **người đọc**; nó không phải câu trả lời cho **người vận hành**. Một request
sai định dạng bị từ chối ở mọi lượt gọi trông y hệt một model không có gì để thêm —
đó là lý do hai lỗi §1.1 và §1.3 sống sót qua cả bộ test.

### 1.9. `GateRun` — check suite mismatch chưa từng được kiểm

`gate.py:118` từ chối một `GateDecision` khai `hidden_suite_version` khác suite đã
chạy. Vô hiệu hoá dòng đó thì **193 test vẫn xanh**. Thêm hai test (bundle mismatch
và suite mismatch). Lưu ý: pydantic bọc refusal của validator, nên biên là
`ValidationError` mang thông điệp `GateRefusal`.

### 1.10. Trên Windows, 78 test của tầng advice không chạy được

`path.read_text()` không khai encoding → Python rơi về cp1252 → chết ở byte `0x8f`
(report có dấu Δ và tiếng Việt có dấu). Thêm `encoding="utf-8"` ở hai chỗ.
`tests/test_gate_advice.py` + `tests/test_report_advice.py`: **93 test xanh**, trước
đó 6 đỏ + 72 lỗi.

## 2. Test đã thêm hoặc sửa

| Test | Canh cái gì |
|---|---|
| `test_the_model_cannot_push_a_blocking_finding_below_a_disclosure` | §1.5 |
| `test_the_cap_holds_when_the_provider_ignores_the_schema` | §1.4 — thay cho test tự quy chiếu cũ |
| `test_a_blocking_addition_that_names_no_barred_move_is_not_blocking` | §1.6 |
| `test_an_oversized_source_still_parses_as_json` | §1.7 |
| `test_the_source_is_marked_as_data_not_instruction` | §1.7 |
| `test_strict_is_judged_all_the_way_down` | §1.1 |
| `test_the_real_advisor_schema_qualifies_for_strict_mode` | §1.1–1.2 — smoke test không cần mạng |
| `test_the_ceiling_is_read_out_of_the_refusal` + 3 test nữa | §1.3 |
| `test_a_decision_naming_another_suite_is_refused` (+ bundle) | §1.9 |
| `test_a_forgotten_code_is_kept_at_the_end_not_dropped` | sửa: dùng hai mục cùng severity để §1.5 không nhiễu phép đo |

**Test cũ giữ nguyên ý nghĩa**: test trần theo schema (`maxItems == MAX_MODEL_ADVICE`)
được **giữ lại** bên cạnh test mới — nó vẫn có ích để bắt việc quên bump schema, chỉ
là nó không bao giờ đỏ được một mình.

## 3. Bằng chứng

### 3.1. `bites` — 14/14 răng cắn

Trước: 12/14. Hai răng trượt (`GATE_SUITE_MISMATCH_IGNORED`, `ADVISOR_ADDITION_CAP_OFF`)
giờ đều cắn, và cắn vào **đúng tên test** mới thêm chứ không chỉ "exit khác 0".

Hai răng khác báo `LỖI KHAI` sau khi sửa vì chuỗi tiêm không còn tồn tại — đúng như
skill dặn, **sửa răng chứ không sửa cổng**: trỏ lại vào hình dạng code mới, cả hai
cắn tiếp.

### 3.2. Probe đối kháng — 11/12 lọt xuống 6/12

Chặn được: `P5` blocking thiếu `do_not` · `P6` đổi bậc severity · `P9` vượt trần 3 ·
`P10` source không đánh dấu · `P11` cắt giữa JSON.

Còn lọt, **đều là thiết kế chấp nhận, trừ một cái**:

| Probe | Vì sao còn lọt |
|---|---|
| P3, P4 | `summary` là văn tự do, không đòi citation. Chặn được thì phải bỏ luôn summary |
| P7 | citation **resolve** không có nghĩa là **ủng hộ** claim. Xem §4 — đây là lỗ có thật, đã bắt được một ca |
| P8 | `exists()` nhận `null` **có chủ đích** (§docstring `self_check.exists`) |
| P2 | số trong claim không đối chiếu với source |
| **P1** | **addition mâu thuẫn với luật vẫn đi thẳng ra UI.** Chưa sửa — chặn tất định đòi so nghĩa hai câu |

### 3.3. OpenAI thật — 0/12 lượt thành công thành 12/12

Chạy **bản repo, không vá tạm**:

```
openai: gpt-4o-mini caps completions at 16384; retrying below the requested 32768
  gpt-4o-mini  gated   diagnosis  rules=3/3 add=3 fab=0 ok    430tok  8.7s
  ...
  o4-mini      tied    outcome    rules=2/2 add=3 fab=0 ok   2672tok 19.3s
```

Sàn luật nguyên vẹn 12/12. Retry §1.3 kêu ở log rồi chạy tiếp, đúng như thiết kế.

## 4. Chưa sửa, và vì sao

**P1 — model mâu thuẫn với luật.** Docstring hứa *"may not remove, soften or
contradict"*. Sau lần vá này **remove** và **soften** (qua severity) đã có cơ chế;
**contradict** thì chưa. Chặn tất định đòi so nghĩa hai câu, không làm được bằng
lexical. Bậc trung gian rẻ, chưa làm vì đụng cả API và UI: addition nào cite **cùng
`field_path`** với một advice luật `blocking` thì đánh dấu "phản biện một luật" cho
người đọc, thay vì trộn chung một danh sách.

**P7 — citation resolve ≠ claim đúng.** Đây không còn là rủi ro lý thuyết: chấm 16
addition thật của o4-mini bắt được **một ca** (§note chấm điểm, A15) — model dẫn
`clearance_warning_m` (có thật, 0.35) rồi kèm một khoảng clearance đọc sai. Bộ kiểm
citation cho qua vì path resolve.

**Advisor vẫn không hiện lỗi lên UI.** `refused` đã có trong response và giờ đã vào
log, nhưng `AdviceListView` chưa render nó. Người dùng bấm "hỏi model" mà provider
chết vẫn thấy đúng danh sách luật cũ. Là việc phía web, để riêng.

## 5. File đã đổi

```
services/agent_service/planbench_agent/advisor.py          §1.2 §1.4 §1.5 §1.6 §1.7 §1.8
services/agent_service/planbench_agent/openai_provider.py  §1.1 §1.3
tests/test_advisor.py                                      5 test mới, 1 sửa
tests/test_agent_providers_multi.py                        6 test mới
tests/test_explanation_gate.py                             2 test mới
tests/test_gate_advice.py                                  §1.10
tests/test_report_advice.py                                §1.10
```

Không đụng `apps/`, không đụng `packages/`. Chưa commit — chờ An.
