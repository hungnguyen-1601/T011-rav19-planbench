# E5 — AI enablement: giao thức, catalog, bundle, contract, golden

**Ngày:** 2026-08-19 · **Nhánh:** `tongduyan_3` · **Plan:** `docs/antongduy/plans/2026-08-18/tang-giai-thich-vi-sao.md` §3, §5, §6

**Trạng thái:** deterministic core xong, đã qua **ba vòng rà của An** (mục 11, 13,
15), **chưa commit**.
Không đụng web ở đợt này. Full suite chưa chạy.

---

## 1. Giao cái gì

Tám module mới trong `packages/explanation/planbench_explanation/`:

| File | Nội dung |
|---|---|
| `catalog.py` | 16 ToolCard đủ 4 lớp §3.3, `TOOL_CATALOG_VERSION = "1.0.0"` |
| `protocol.py` | `AnalysisRequest` · `ToolRequest` · `ToolResult` · `AnalysisResponse` · `ToolSession` |
| `bundle.py` | `AnalystBundle` · `GateDecision` · `MetricTargets` · `verify_gate_decision` · `analyst_visible` |
| `knowledge_contract.py` | `KnowledgeQuery` · `MechanismReferenceCandidate` · `resolve_candidates` |
| `research_spec.py` | `ResearchSpecification` + ba hàm dựng, `execution_authorized: Literal[False]` |
| `golden.py` | `PlantedCase` · `GoldenSuite` · `score_case`/`score_suite` |
| `golden_fixtures.py` | `VISIBLE_SUITE` — 12 case, 6 họ × 2 biến thể, calibration |
| `integration.py` | `MockToolHost` · `reference_analyst` · `run_round` |

Cộng một chỗ siết ở `tools.py` (E0): card lớp `research_proposal` giờ **bắt buộc**
`supported_proposition_types` rỗng — một bản đặc tả thí nghiệm chưa chạy không
thiết lập được gì.

`tests/test_explanation_e5.py` — **110 test** (72 ban đầu, +16 vòng rà một, +15 vòng rà hai, +7 vòng rà ba — mục 11, 13 và 15).

---

## 2. Catalog: 16 card, và ba chỗ dễ mất khi sửa

**Fact-query phần lớn không đỡ mệnh đề nào.** Chúng trả **số**, và số không
phải phán quyết. `get_objective_decomposition` đưa ra phân rã ΔU; phân rã đó có
nghĩa là component nào đáng trách hay không thì không fact-query nào trả lời.
Chỉ hai fact-query đỡ được mệnh đề, cả hai ở mức `observed`: kể lại detector
thấy gì, và kể lại hai candidate khác nhau đúng một trục.

**Evidence-navigation không đỡ gì theo cấu trúc** — schema card từ chối. Chúng
trả **con trỏ**: episode nào, cửa sổ nào, đoạn nào. Con trỏ là chỗ để nhìn,
không phải điều đúng.

**`latency_vs_expanded_nodes` trần `associated` dù tất định hoàn toàn.** Đếm node
mở rộng và đo latency tick là số học, và số học đó chính xác. Cái nó **không**
cho thấy là expansion *gây ra* latency chứ không phải cả hai cùng theo sau một
query khó. Tất định mua được khả năng tái lập, không mua được nhân quả. Đây là
chỗ phân biệt ấy được cưỡng chế thay vì được hy vọng.

`replay_global_plan` nhận `reconstructed` — run cũ không có input recorded, và
provenance ceiling sẽ tự cắt. Từ chối thẳng ở card thì không run cũ nào xem lại
được nữa.

---

## 3. Protocol: cổng hẹp nằm ở đâu

Plan viết "chỉ tool host được tạo/ký ToolResult — model không tự tạo được".
Chữ "ký" ở đây dễ hiểu nhầm thành chữ ký mật mã. Trong một process thì thứ thực
sự giữ được là **ràng buộc vào request đã được admit**, nên tôi hiện thực cái đó
chứ không thêm một field `signature` mà analyst cũng điền được.

```
analyst dựng ToolResult hoàn hảo về hình thức
        ↓
session.record(result)
        ↓
không có admitted request mang request_id đó  ⇒  ProtocolRejection("unknown_request")
```

Analyst hoàn toàn dựng được một `ToolResult` hợp lệ — model là public, mọi field
điền được. Cái nó **không** làm được là bắt một session chưa từng thấy request đó
chấp nhận. Test `test_a_result_for_a_request_nobody_admitted_has_nowhere_to_attach`
giữ đúng điểm này.

**Admission** kiểm 11 thứ, mỗi thứ một mã đóng: `unknown_tool`,
`catalog_version_mismatch`, `packet_mismatch`, `analysis_run_mismatch`,
`bundle_mismatch`, `duplicate_request_id`, `sequence_out_of_order`,
`request_budget_exhausted`, `missing_required_evidence`,
`execution_not_authorized`, cộng các mã ở phía result.

Hai chỗ đáng nói:

**`available_evidence` là tham số của round.** Đây là bài học từ E2: một run cũ
không có trace per-episode. Analyst hỏi `get_episode_observations` thì phải bị
**từ chối kèm lý do**, không phải nhận kết quả rỗng — kết quả rỗng bị đọc thành
phát hiện. `missing_evidence_for()` đưa trước cả danh sách để một round không
tiêu ba lượt phát hiện lại cùng một sự vắng mặt.

**Host đóng dấu `unsupported_inferences`, checker không tự gõ.** Đây không phải
thứ checker chọn theo lần chạy; nó là `forbidden_inference_types` của card, chép
lên mọi result để lời từ chối **đi cùng bằng chứng**. `stamped_result()` lấy từ
card, và `record()` từ chối result nào lệch — bỏ sót một cái là cách một cách đọc
quá đà trở thành được phép, ở đầu bên kia, âm thầm.

**`record()` trả `ToolResult`, không trả `CheckerResult`.** Phần lớn tool không
sinh dòng ledger: fact-query đưa số, navigation đưa bốn id episode, không cái nào
xử một mệnh đề. `session.checker_results` lọc **theo card**, không theo việc result
có rỗng hay không — một mechanism-check chạy hỏng vẫn là checker result, và ledger
cần nó để phân biệt "check bác bỏ" với "không ai check".

---

## 4. Bundle: vì sao chấm bundle chứ không chấm endpoint

Endpoint do nhóm AI vận hành có thể log hidden packet, đổi prompt giữa chừng,
deploy code mới trong lúc chấm, hoặc nhận ra đang bị chấm. Report từ đó không tái
lập được, mà số tái lập được chính là toàn bộ mục đích của gate.

`identity_checksum` tính trên 9 field cấu hình. **`bundle_id` và `created_at`
cố ý nằm ngoài**: chúng là nhãn, và hai lần nộp cùng một cấu hình dưới hai id là
cùng một hệ thống. Đổi một ký tự prompt thì checksum đổi, nên `GateDecision` cũ
**tự động** không còn trỏ đúng thứ đang chạy — không cần ai để ý.

`GateDecision` không có field "passed". Câu trong bản đầu của report — "không có
đường nào để một decision mang metric chưa đạt mà vẫn passed" — **sai**, và chính
test của vòng rà một chứng minh nó sai: decision tự hạ threshold thì
`internally_passed=True`. Vòng rà hai đổi tên và tách API, xem mục 13.

Feature flag: `analyst_visible(bundle, decision, catalog_version=..., targets=...)`
— **năm** cách để không hiện, một cách để hiện (sửa ở vòng rà, xem mục 11). Mặc
định là không hiện. `why_not_visible()` giữ luật; `analyst_visible` chỉ là nó bỏ
lý do đi, nên hai hàm không lệch nhau được.

**Rủi ro tồn dư khai thẳng trong docstring:** hidden packet vẫn rời platform tới
vendor API (giảm nhẹ bằng rotation, không bằng bí mật); và bundle không khoá được
nondeterminism của API (đo bằng repeated run, không giả vờ đã xử lý).

---

## 5. Knowledge contract: RAG chỉ được trả khoá

`MechanismReferenceCandidate` **không có field nào** cho mechanism text, source,
applicability condition hay review status — và `extra="forbid"` biến việc gửi thêm
thành lỗi validate ở biên, không phải field bị lặng lẽ bỏ qua. Provider tự khai
`review_status: approved` chính là nước cờ H3 đã chặn khi provider khai
`provenance="oracle"` về dữ liệu của chính nó.

Bốn cách một candidate chết: base lạ · entry không có · lệch version · đã withdrawn.
Cách thứ năm **không phải** từ chối: entry `draft` vẫn resolve và trả về, nhưng
`may_support_a_claim=False`. Toàn bộ KB v1 là draft, nên hôm nay đó là đường đi
thông thường chứ không phải ngoại lệ.

Lệch `kb_version` thì từ chối **cả result**, không phải từng candidate — provider
index một version khác không phải nhầm về một entry, mà đang trả lời về một base khác.

`ResolutionOutcome` giữ cả phần bị từ chối. Một retrieval trả năm entry mà ba cái
không tồn tại là một retrieval có vấn đề, và cách duy nhất ai đó biết là nếu
rejection sống sót qua lời gọi.

---

## 6. Research spec: mô tả được, chạy không được

`execution_authorized: Literal[False]` — hằng theo kiểu, không phải mặc định.
`required_lane: Literal["research"]`.

Ba validator có nội dung:

- axis một level ⇒ từ chối ("đó là run đã chạy rồi");
- axis nằm trong `held_constant` ⇒ từ chối (một trong hai là nhầm, schema không
  đoán được cái nào);
- `held_constant` rỗng ⇒ từ chối (mọi khác biệt có nhiều nguyên nhân ứng viên,
  thí nghiệm không trả lời cái nào).

`PreregisteredOutcome` bắt buộc **cả** `supports_if` **và** `refutes_if`. Tiêu chí
thành công không kèm tiêu chí thất bại là tiêu chí không thể trượt: mọi kết quả
chưa đạt đều thành "chưa kết luận, cần thêm episode".

---

## 7. Golden: ba thứ được chấm, chỉ một là tỉ lệ

**Invariant cấu trúc là đếm và phải bằng 0.** Không đánh đổi với độ chính xác.
Analyst tìm ra mọi mechanism mà rò một blocked claim là **trượt** — cái rò đó
đúng là thứ cả tầng này sinh ra để chặn. Trong `score_case`, đề xuất một
`forbidden_claim` tính vào `structural_violations`, **không** tính là mất precision.

**Tách "tìm ra mechanism" khỏi "gọi đúng tên component".** Khớp
`(proposition_type, subject)` cho attribution, khớp mỗi `proposition_type` cho
recall. Gộp lại thì giấu mất analyst đang hỏng ở khâu nào.

**Recall@3** — panel hiện một nắm, analyst chôn đáp án ở hạng chín thì chưa tìm ra.

**Chọn checker chấm riêng.** Đúng kết luận mà không hỏi check nào là **may**, và
điểm phải phản ánh điều đó.

**Macro trước micro.** Sáu họ lệch kích thước gộp chung thì họ lớn nhất gánh điểm.
Test dựng đúng ca đó: micro 0.8, macro 0.5.

**Metric không đo được thì chấm 0.0, không biến mất.** `_ratio` trả `None` khi mẫu
số bằng 0 (một họ không có ca abstain thì không có tỉ lệ abstain, bịa ra là hoặc
tâng bốc hoặc phạt oan). Nhưng `MetricTargets.evaluate` quy `None` về `0.0` — gate
nào lặng lẽ bỏ metric nó không đo được là gate qua được bằng cách nộp bộ đo không
đo gì.

**Case không ai trả lời bị chấm như trả lời tệ**, không bị bỏ qua — nếu bỏ qua thì
crash ở các case khó lại làm điểm đẹp lên.

**Không suite nào được preregister trước khi có writer.** `OFFICIAL_GOLDEN_READY
= False` là hằng số nền tảng ở cùng module, cùng lý do với `H4_ACCOUNTING_COMPLETE`:
nó quyết định platform được chứng nhận cái gì, và bên bị chứng nhận không được
truyền nó vào như tham số. `status="preregistered"` ⇒ `GoldenRefusal`. Chấm analyst
trên input tái dựng rồi gọi kết quả là gate sẽ nướng lỗi tái dựng vào chính cái bar.

`VISIBLE_SUITE`: 12 case, 6 họ × 2 biến thể, **7/12 kỳ vọng abstain** — cố ý.
Analyst tinh chỉnh trên bộ mà cái gì cũng sai sẽ học rằng cái gì cũng sai.

---

## 8. Integration stub: thật ở phần admission, giả ở phần chạy

`MockToolHost` admit qua **đúng** `ToolSession` thật — cùng luật, cùng mã từ chối,
cùng tra card — rồi phục vụ fact-query/navigation từ packet (packet thật sự giữ
dữ liệu đó). Mechanism-check trả `not_checkable` +
`failure_code="checker_not_implemented"`. Đó là câu trả lời trung thực hôm nay, và
quan trọng hơn: nó là **hình dạng analyst phải xử lý dù sao** — checker chạy không
được là kết cục bình thường trong production, không phải hiện vật của mock.

`reference_analyst` là **sàn**, không phải baseline để chép: nó đọc detection, đề
xuất mechanism tương ứng, và abstain khi không có gì. Bundle nào không vượt được
nó trên bộ visible thì chưa chứng minh model đóng góp gì. Nó cố ý nông — đề xuất
từ detection mà không cân nhắc map, contrast hay phân rã.

Nó cũng tôn trọng `known_unknowns`: mechanism bị chặn thì không đề xuất. Test kiểm
chứng cả hai chiều (không chặn ⇒ có đề xuất; chặn ⇒ abstain).

---

## 9. Chưa làm — nói rõ

| Việc | Vì sao |
|---|---|
| **Checker thật** | E6. Mọi mechanism-check hôm nay là `not_checkable`. |
| **Packet fixture cho golden** | Cần run planted có sidecar ghi planning input đúng lúc xảy ra ⇒ **E4.5**. `PlantedCase.packet_ref` là đường dẫn chưa resolve. |
| **Hidden suite** | Platform giữ, mở một lần mỗi version bundle, **không** nằm trong repo này. |
| **Gate harness chạy bundle** | E6. Ở đây chỉ có schema quyết định + luật flag. |
| **Endpoint HTTP cho analysis round** | Chưa nối API. Cùng nhóm câu hỏi với E4.1 (dựng packet lúc nào), nên chờ An chốt E4.1 trước. |
| **Duyệt KB v1** | Cần người đọc và ký. Tới lúc đó `resolve_candidates` vẫn trả `may_support_a_claim=False` cho mọi entry. |
| **Web** | Không đụng. Feature flag mới ở tầng Python; nối vào trang là việc sau khi có gate thật. |

---

## 10. Kiểm chứng

- `tests/test_explanation_e5.py` — **72 test passed**.
- Toàn bộ test explanation: **343 passed** (11 file).
- `tests/api/test_api_explanation.py`: **7 passed**.
- `ruff check` sạch, `ruff format` sạch.
- **Full suite chưa chạy** (theo lệnh của An).

---

## 11. Vòng rà của An — năm điểm

Đúng cả năm. Hai điểm HIGH là lỗ contract thật, không phải chuyện diễn đạt.

### HIGH-1 — `GateDecision` "pass" khi thiếu metric bắt buộc

`passed` suy ra từ "mọi metric **có mặt** đều đạt", nên một decision chỉ mang
`precision` đạt là **pass** — năm metric sẽ trượt chỉ đơn giản là vắng mặt, và
`analyst_visible()` bật cờ. Test cũ của tôi còn xác nhận đúng đường đó: fixture
decision chỉ có hai metric.

Sửa bằng hai luật, đúng như An đề xuất:

**Đủ bộ.** `REQUIRED_GATE_METRICS` — sáu metric — phải có mặt **hết**. Thiếu ⇒
`BundleRefusal` ("gate decision is silent about …"). Thừa cũng từ chối: metric
nghĩ ra lúc chấm là metric được chọn để đạt.

**Không tự mang thang đo.** `MetricTargets` chuyển sang `bundle.py` (cạnh chính
cái nó phán xét), có `checksum`. `GateDecision` mang `targets_checksum`.
`verify_gate_decision(decision, *, targets)` **dựng lại** threshold/direction từ
targets do caller cung cấp và từ chối nếu lệch. Đúng bài học của claim ledger:
artifact tự mô tả rồi được phán xét bằng chính mô tả của nó thì không phải là
được phán xét.

`analyst_visible` giờ nhận `targets` bắt buộc, và **là** `why_not_visible(...) is None`
— một chỗ giữ luật, hai hàm không thể lệch nhau.

Test mới: decision chỉ một metric bị từ chối · decision bịa metric bị từ chối ·
decision hạ threshold về 0.0 **tự nhất quán, `passed=True`**, nhưng
`verify_gate_decision` bắt được · decision chấm theo bar khác bị từ chối.

### HIGH-2 — catalog chưa khoá hình dạng dữ liệu

Đúng: catalog khoá được "tool nào" và "kết luận được gì", chưa khoá "nhận/trả
dữ liệu hình gì". Để E6 hiện thực trên nền đó thì mỗi checker tự phát minh
contract riêng.

`ToolIO` vào `ToolCard`:

- `arguments: tuple[ArgumentSpec, ...]` — tên (`^[a-z][a-z0-9_]*$`), kiểu
  (`string|integer|number|boolean`), bắt buộc hay không, mô tả.
- `measurement_keys: tuple[str, ...]` — tập đóng key mà `measurements` được dùng.

Cưỡng chế: `admit()` kiểm arguments (thiếu / thừa / sai kiểu, **báo hết một
lượt** chứ không từng cái một), `record()` kiểm measurement key. Bẫy Python
`bool` là con của `int` đã đóng — `True` không lọt vào chỗ đòi integer.

Về `input_schema_ref`/`output_schema_ref` mà plan nêu: tôi **sinh** file từ
`ToolIO` chứ không viết tay cạnh nó — hai bản mô tả tay của cùng một contract
rồi sẽ lệch, và bản không ai chạy là bản mục. `scripts/export_tool_schemas.py`
ghi **32 file** vào `schemas/tools/`; hai property trên card là **dẫn xuất** từ
`tool_id` (lưu thành field thì thành chuỗi ai trỏ đâu cũng được). Có test
regenerate-và-so-sánh: sửa card mà quên export thì hỏng ở test, không phải ở
production.

Một chỗ phát sinh khi làm: `region_id` của `get_map_region_features` chuyển thành
**tuỳ chọn** — bỏ trống thì đo cả tuyến, đúng như `measure_route` của E3 vẫn làm.

### MEDIUM-HIGH-3 — `hypothesis_id` chưa được kiểm

Đúng: mã `unknown_hypothesis` có trong enum mà không đường nào ném ra.
`run_round` né được vì tự dựng request từ response, nhưng contract công khai
không cưỡng chế.

Thêm `ToolSession.declare(proposals | response)` — **gọi được nhiều lần**, vì một
analyst thật đề xuất, kiểm, rồi đề xuất tiếp sau khi thấy bằng chứng; contract chỉ
cho khai một lần sẽ bắt nó đoán trước toàn bộ mạch suy luận. `admit()` từ chối
hypothesis ngoài tập đã khai. `run_round` khai trước khi gửi request đầu tiên.

### MEDIUM-4 — `failure_code` chưa khoá theo card

Đúng, và mock host của tôi chính là bằng chứng: nó trả `checker_not_implemented`
không có trong card nào.

Tách đúng hai loại như An đề xuất: `HOST_FAILURE_CODES`
(`checker_not_implemented`, `checker_timeout`, `host_internal_error`,
`tool_unavailable`) là lỗi của nền tảng — card không nên phải liệt kê các cách
platform tự hỏng; `card.failure_modes` là lỗi của tool. `record()` kiểm theo
**union đóng** của hai tập.

### LOW-5 — plan tự mâu thuẫn về phạm vi golden

Đúng, và là drift trong plan chứ không phải trong code. Sửa §6: tách rõ **E5**
(schema + scorer + visible calibration skeleton) · **E4.5** (packet fixture có
provenance chính thức) · **E6** (hidden suite, gate harness, preregistration thật);
dòng "6 họ × 12–20" ghi rõ là bộ **chính thức** thuộc E4.5+E6.

## 12. Kiểm chứng sau vòng rà

- `tests/test_explanation_e5.py` — **88 test** (từ 72; thêm 16: đủ bộ metric,
  metric bịa, threshold tự hạ, bar khác, argument thiếu/thừa/sai kiểu, bool≠int,
  measurement key lạ, failure code lạ, host code hợp lệ, hypothesis chưa khai,
  khai bổ sung giữa round, schema tồn tại và không stale, schema khớp cái host
  cưỡng chế, analyst không đoán argument).
- Toàn bộ test explanation: **359 passed** (11 file). API: **7 passed**.
- `schemas/tools/` — 32 file sinh ra, `scripts/export_tool_schemas.py`.
- `ruff check` + `ruff format` sạch. **Full suite chưa chạy.**

---

## 13. Vòng rà thứ hai — bốn điểm

Đúng cả bốn. Điểm HIGH là số 0 tự sinh ra ở đúng chỗ nguy hiểm nhất.

### HIGH — thiếu structural metric vẫn quy 0 và pass

`value=0.0 if measured is None` đúng cho metric `at_least`: không đo precision thì
0 và trượt. Nhưng `structural_violations` là `at_most 0` — **cùng một quy tắc, kết
quả ngược lại**: harness không đo invariant cấu trúc và hệ ghi "không có vi phạm".
`GateDecision` sau đó vẫn đủ sáu dòng, `verify_gate_decision` cũng không thấy gì
bất thường, vì số 0 đó **hợp lệ về hình thức**.

Chiều so sánh quyết định một sự vắng mặt phải trượt về phía nào. `evaluate()` giờ
từ chối khi thiếu bất kỳ metric `at_most` nào:

> `['structural_violations'] were not measured. They are counted invariants judged
> at_most, so treating an absence as zero would record 'no violations' for a run
> nobody checked.`

Metric thống kê thiếu vẫn quy 0 và trượt, như cũ.

### MEDIUM-HIGH — output schema mới khoá key, chưa khoá đủ

Đúng, và ba thiếu sót An nêu là ba thiếu sót thật:

**Không có required.** `measurement_keys` chặn key lạ nhưng một result `completed`
với `measurements={}` vẫn hợp lệ. **Báo cáo không có số không phải là kiểm ra
không thấy gì.** Nay `MeasurementSpec` có `required`, và `check_measurements` kiểm
theo trạng thái: completed thì thiếu required là từ chối; không completed thì
không đòi gì — bắt một checker chạy hỏng phải nộp số là bắt nó bịa.

**Không có đơn vị và mô tả.** Thêm `unit` (tập đóng `m`/`s`/`ms`/`count`/`ratio`/
`correlation`/`flag`) và `description` bắt buộc cho từng measurement. `0.68` là
mét ở checker này và centimet ở checker kia — đó là cách hai hiện thực đều đúng
mà vẫn mâu thuẫn.

**Navigation trả số đếm thay vì con trỏ.** Đúng như An chỉ ra ở
`find_exemplar_episodes`: `n_exemplars: 4` nói cần mở **mấy** episode chứ không
nói **những cái nào**. Nguyên nhân là mọi output bị ép qua `dict[str, float]`.
Nay có `EvidenceReference(kind, ref, label)` với `ReferenceKind` đóng
(`episode`, `replay_window`, `trajectory_segment`, `trace_rows`, `map_region`);
card khai `references`, và card nào khai `required` thì result completed thiếu là
bị từ chối. Cả bốn tool navigation cộng ba tool khác giờ có con trỏ.

Result schema sinh ra theo đó: `measurements` có `required` + `unit` +
`description` từng key, `references` là mảng có `kind` enum.

### MEDIUM — hypothesis khoá theo ID, chưa khoá theo nội dung

Đúng. `set[str]` để lọt việc khai lại `hyp-004` với proposition/subject khác —
bằng chứng đã thu dưới id đó **âm thầm chuyển sang một claim khác**.

Nay là `dict[hypothesis_id, checksum(proposal)]`: cùng id cùng nội dung là
idempotent, cùng id khác nội dung ⇒ `hypothesis_redefined`. Và `declare()` nhận
`AnalysisResponse` thì kiểm `analysis_run_id` + `analyst_bundle_id` **trước khi
đăng ký gì** — response sai round hoặc sai bundle không khai được dù chỉ một
proposal.

### LOW — report nói quá về `passed`

Đúng, và tôi đã sửa câu đó ở mục 4. `passed` cũng đúng là API nguy hiểm để public
— E6 vô tình gọi thẳng thì mất luôn phần verify.

Chọn cả hai lối An gợi ý:

- `passed` ⇒ **`internally_passed`**, docstring nói rõ nó chỉ trả lời "file này có
  tự nhất quán không", và tên đặt cho khó chịu để ai với tay nhầm thì nhận ra;
- **`passes(targets)`** là API công khai: verify trước, rồi mới đọc so sánh.

`why_not_visible` dùng `passes()`. Không tạo type `VerifiedGateDecision` — thêm
một type nữa cho một luật đã có một chỗ giữ thì tăng bề mặt mà không tăng đảm bảo.

### Phát sinh khi sửa

`MockToolHost` không còn bịa được số: tool nào packet không trả lời được thì nó
trả `not_checkable` + `tool_unavailable`, thay vì điền 0.0 cho các required
measurement. Một stub điền 0.0 là một stub **tạo bằng chứng** — đúng thứ hệ này
sinh ra để chặn.

## 14. Kiểm chứng sau vòng rà thứ hai

- `tests/test_explanation_e5.py` — **103 test** (+15: invariant không đo bị từ
  chối, rate không đo vẫn về 0, `internally_passed` vs `passes`, completed thiếu
  measurement, not_checkable không nợ số, navigation thiếu con trỏ, con trỏ sai
  kind, mọi measurement có unit + mô tả, result schema nêu đúng required, optional
  đúng hai key có điều kiện, khai lại idempotent, đổi nội dung cùng id bị từ chối,
  response sai round, response sai bundle, mock không bịa số).
- Toàn bộ test explanation: **374 passed** (11 file). API: **7 passed**.
- 32 schema file sinh lại; test drift so trên đĩa.
- `ruff check` + `ruff format` sạch. **Full suite chưa chạy.**

---

## 15. Vòng rà thứ ba — hai điểm

### MEDIUM — JSON Schema yếu hơn runtime ở reference bắt buộc

Đúng, và đây là kiểu lệch tệ nhất trong hai chiều: schema **lỏng hơn** host thì
nó nói với integrator rằng payload của họ ổn, rồi host từ chối. Lỗi lộ ra ở chỗ
xa nhất khỏi nguyên nhân.

`result_schema()` giờ:

- thêm `"references"` vào `required` top-level khi card có
  `required_reference_kinds`;
- `minItems: 1`;
- **một `contains` cho từng kind bắt buộc** (`allOf`) — dùng một `minItems`
  chung là sai: tool cần một episode **và** một window không được thoả bằng hai
  episode;
- thêm `minLength: 1` cho `ref`, khớp `Field(min_length=1)` phía runtime.

Về ý cuối của An — drift test chỉ chứng minh **file khớp generator**, chưa chứng
minh **generator khớp runtime** — đúng, và đó là hai câu hỏi khác nhau. Thêm
`test_the_generator_and_the_host_read_the_same_card`: với mọi card, đọc ngược từ
schema ra tập required measurement, tập measurement, enum kind, tập kind bắt buộc
(từ các `contains`), và so với `card.io.*` mà `ToolSession` thật sự cưỡng chế.
Test cũ giữ file khỏi cũ; test này giữ generator khỏi nói dối.

### MEDIUM — `declare()` chưa atomic

Đúng. Vừa kiểm vừa ghi trong một vòng lặp, nên batch bị từ chối ở proposal thứ ba
đã ghi xong hai cái đầu. Caller bắt exception và tin rằng mình chưa khai gì;
session thì đã đổi. Hai bên không còn đồng ý với nhau về nội dung của round —
tệ hơn là chỉ đơn thuần lỗi.

Nay hai lượt: tính checksum và kiểm **toàn bộ** batch trước — gồm cả **trùng ID
nội bộ trong chính batch** (`staged`), điểm An nêu rõ — rồi mới `update()` state
một lần.

Ba test hồi quy: batch hỏng giữa chừng ⇒ `declared_hypotheses` không đổi · batch
tự mâu thuẫn ⇒ không ghi gì · batch lặp nguyên văn một proposal ⇒ vẫn hợp lệ.

## 16. Kiểm chứng sau vòng rà thứ ba

- `tests/test_explanation_e5.py` — **110 test** (+7).
- Toàn bộ test explanation: **381 passed** (11 file). API: **7 passed**.
- 32 schema file sinh lại sau khi đổi generator.
- `ruff check` + `ruff format` sạch. **Full suite chưa chạy.**

E5 sẵn sàng đóng phase từ phía tôi. Chưa commit — chờ lệnh của An.
