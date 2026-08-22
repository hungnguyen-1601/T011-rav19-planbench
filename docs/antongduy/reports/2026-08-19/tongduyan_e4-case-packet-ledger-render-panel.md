# E4 — case packet, claim ledger, render template, ma trận panel

**Ngày:** 2026-08-19
**Plan:** `plans/2026-08-18/tang-giai-thich-vi-sao.md` §5, đợt **E4**
**Thiết kế nguồn:** `notes/2026-08-18/tongduyan_giai-phap-giai-thich-vi-sao-thuat-toan-thang.md` §6–§7
**Tiền đề:** E0 (`d28ff20`), E1 (`cf7967c`), E2 (`1d93d05`), E3 (`c6ad5af`)
**Trạng thái:** **deterministic core + outcome header xong; end-to-end chưa**
(endpoint packet/ledger = E4.1, chờ An chốt cách dựng packet). Đã qua **hai vòng
rà của An** (mục 7: sáu điểm; mục 9: ba điểm). 50 test mới xanh. **Chưa commit.**
Full suite chưa chạy.

---

## 1. Giao cái gì

| Module | Nội dung |
|---|---|
| `case_packet.py` | hồ sơ analyst được đọc — và là **thứ duy nhất** nó được đọc |
| `ledger_store.py` | chạy từng proposal qua matrix, **giữ cả cái bị từ chối** |
| `render.py` | template khoá cách nói theo mức và theo `impact_kind` |
| `panel.py` | ma trận năm kết cục run |
| `apps/web/src/lib/explainPanel.ts` | cùng ma trận đó ở phía UI |

## 2. Packet: analyst không bao giờ mở Parquet

Đưa cho một model 546 dòng telemetry thì nó sẽ sinh ra một con số **trông như**
phép đo. Đưa cho nó packet thì mọi con số trong câu trả lời hoặc có mặt trong
packet, hoặc là số nó tự bịa — và đó là khác biệt người rà soát **nhìn là thấy**.

Packet gồm: task (map feature + robot) · candidates **full stack** · decision
(waterfall E1 + gates) · lattice (contrast E3) · observations (detector E3) ·
representative episodes (exemplar E2) · known unknowns · evidence class · header
E0 với năm version.

**Không có gì trong packet là một claim.** Observation là pattern, lattice là
ràng buộc lên phép quy kết, map feature là số đo. Thứ duy nhất packet **không**
được chứa là kết luận vì sao một candidate thắng — đó là việc của analyst, rồi
của promotion matrix.

**Known unknowns bắt buộc, và là dữ liệu chứ không phải lời nhắc.**
`STANDING_UNKNOWNS` mang sẵn hai lỗ hổng H4/H0; `extra_unknowns` **cộng thêm**
chứ không thay thế — người biết thêm một lỗ hổng không được phép làm rơi những
lỗ hổng luôn đúng. Packet với danh sách rỗng bị từ chối: nó đang tuyên bố
platform biết mọi thứ về run này.

Bốn phép kiểm nữa, tất cả cùng một hình dạng "đừng giải thích một phép so khác":
waterfall so hai candidate không có trong packet ⇒ từ chối · observation nói về
candidate lạ ⇒ từ chối · exemplar về cặp khác ⇒ từ chối · knowledge base version
trên header khác bản đang chạy ⇒ từ chối (citation resolve sang bản khác thì
không ai đọc lại được).

## 3. Ledger: giữ cả cái bị từ chối

Ledger chỉ giữ claim là ledger không phân biệt được **"chưa ai soi"** với **"ba
check đã bác bỏ"** — trên panel cả hai đều là khoảng trắng. Nên mọi lần adjudicate
đều vào ledger, kèm **reasons của chính matrix**. Panel render claim; **audit đọc
toàn bộ**.

`build_ledger()` đọc `blocked_claim_types` **từ packet** và truyền vào mọi lần
promote. Không có tham số nào để tắt: người tắt được lỗ hổng H4 là người promote
được một quy kết latency mà platform không làm nổi.

Ledger mang checksum của packet nó trả lời — kết luận mà không nói được nó trả
lời bằng chứng nào là kết luận về bằng chứng vô danh. Và mọi claim trong một
ledger phải cùng `promotion_matrix_version` với header: hai phiên bản luật trong
một file là file không ai suy luận được.

## 4. Render: template khoá theo mức, và khoá theo loại impact

Một frame cho mỗi rung (`Measured:` / `Consistent with:` / `Verified for:` /
`Caused by:` + scope), rồi **chạy chính câu vừa render qua lại whitelist lexical**
của E0. Nhìn thì thừa — template viết ra là đã tuân thủ — nhưng đó đúng là phép
kiểm sống sót sau khi ai đó sửa template hai tháng nữa.

Hai loại impact đọc **gần giống hệt nhau** nếu không cẩn thận, nên mỗi loại một
câu riêng: `observed_contribution` nói "cơ chế xuất hiện trong các episode mà
objective bất lợi; **phần nó gây ra chưa được xác lập**", còn
`attributable_effect_estimate` nói "ước lượng đóng góp một phần… theo phương pháp
X" kèm qualifier `estimated`. Impact `profile_weighted` thì tên profile nằm
**cùng dòng** với con số — tách ra là để một sở thích đọc thành một phép đo.

**Không con số nào ledger không giữ.** `ImpactRef` cố ý không mang float, nên câu
render chỉ tên objective/kind/method và trỏ tới artifact.

`render_no_claim()` cho chỗ trống một câu chữ: panel trống bị đọc là "không có gì
đáng nói", còn panel nói "một check đã bác bỏ" thì được đọc đúng — khác nhau đúng
một chuỗi.

## 5. Ma trận năm kết cục

`clear` · `near_equivalent` · `no_survivors` · `gate_only` · `interrupted`.

Ba kết cục không-card **không phải một trạng thái**: `no_survivors` đòi một
candidate tốt hơn, `gate_only` đòi một deployment có ngưỡng chừa chỗ phía trên,
`interrupted` đòi chạy nốt. Cùng một tấm card trống, ba việc khác nhau.

`PanelPlan` **từ chối tồn tại** nếu một kết cục không có phép so ghép cặp mà lại
bật waterfall/claim/exemplar: không có ΔU thì không có gì để phân rã.
`outcome_of()` đặt `interrupted` lên trước trong nhóm không-card — một run dừng
sớm **cũng có thể** không ai sống sót, và "chưa chạy xong" mới là sự thật làm cái
thứ hai không diễn giải được.

Cùng ma trận đó có bản TS ở `lib/explainPanel.ts` (trang phải render trước khi
endpoint nào trả lời). Nhân đôi có chủ ý và có ghi lý do; luật nó bảo vệ được
test ở cả hai phía.

## 6. Kiểm chứng

- `tests/test_explanation_e4.py` — 24 test: packet (7), template (6), ledger (5),
  panel (6).
- `apps/web/src/lib/__tests__/explain-panel.test.ts` — 5 test.
- **247 passed** trên toàn bộ test explanation; web **980 passed**;
  `tsc --noEmit` sạch; `ruff check` sạch.
- **Full suite chưa chạy.**

## 7. Vòng rà của An — sáu điểm

**HIGH-1 — run bị ngắt trước khi rank vẫn hiện waterfall.** Đây là **lỗi ghép**:
`outcome_of` trả `interrupted` đúng, plan của `interrupted` bật waterfall đúng
cho ca đã rank, và **không ai kiểm** rằng run này từng có ΔU. Mỗi hàm test riêng
đều xanh. Nay `PANEL_PLANS` khoá theo **cặp** `(outcome, has_comparison)` —
`interrupted` có hai plan — `plan_for()` bắt buộc truyền `has_comparison` (không
default: mặc định sẽ cho người chưa nghĩ tới nó bản vẽ nhiều nhất), và có
`panel_for()` tính cả hai trong một lời gọi để không ai ghép sai nữa. Bản TS
`explainPanel.ts` sửa y hệt.

**HIGH-2 — ledger đọc lại có thể chứa claim/sentence không thuộc adjudication.**
Đúng, và nó phá thẳng câu "UI chỉ render claim deterministic-gated" — câu đó chỉ
đáng giá bằng các phép kiểm trên chính file được render. Nay `LedgerEntry` kiểm
**mọi liên kết chéo**: `claim.record_ref` khớp record, `proposition_type` và
`subject` khớp proposal, `supports` khớp proposal, và **`sentence` được render
lại từ claim** rồi so — sentence tự do khác claim là sentence tự do nói mạnh hơn.
Entry không có claim cũng phải mang đúng câu no-claim của reasons nó.

**HIGH-3 — packet chưa khoá đủ cặp candidate.** Hai chỗ: `ContrastFinding.pairs`
không bị kiểm (một lattice từ run khác lọt vào được), và exemplar so bằng **set**
nên cặp đảo chiều vẫn qua — trong khi `strongest_for_winner` định nghĩa **theo
chiều**. Nay kiểm mọi id trong lattice pairs, và so exemplar bằng **tuple có thứ
tự**.

**HIGH-4 — caller tự tuyên bố H4 đã xong.** `h4_accounting_complete` là tham số
public của `build_ledger` ⇒ chỉ cần truyền `True` là trần của
`perception_provider`/`runtime_transport` được nâng. Bên bị chấm tự khai hạ tầng
hoàn tất — đúng là trust hole. Nay tham số **biến mất khỏi API**; trạng thái là
hằng số platform `subjects.H4_ACCOUNTING_COMPLETE = False`, đổi nó là sửa code
kèm bump promotion-matrix version, nhìn thấy trong diff. Test khẳng định tham số
không còn trong chữ ký.

**HIGH-5 — `profile_weighted` không lưu tên profile.** Boolean trần khiến hai run
dưới hai profile khác nhau render **giống hệt**, mà test cũ chỉ kiểm chuỗi chung
"preference profile" — test đặt tên là "names the profile" nhưng không kiểm tên
nào cả. Nay `ImpactRef.profile_ref` **bắt buộc** khi `profile_weighted=True` (và
bị từ chối khi khai ngược lại), renderer in thẳng id đó, test kiểm đúng id.

**Phạm vi — E4 chưa end-to-end.** Đúng, và tôi đã viết "E4 xong" trong khi ba
mảnh còn thiếu. Đóng hai trong ba ngay trong lượt này: **panel đã cắm vào trang**
(`ExplanationHeader` đọc `panelPlan(run)`, caveat render **phía trên** bằng chứng
— qualifier dưới màn hình thì không qualify gì; và `TracePanel` trả `null` khi
`showExemplars` tắt, để hai canvas không xuất hiện cho một run chưa từng so cặp),
và **14 khoá i18n** `explain.*` đã có ở cả `en` lẫn `vi`. Còn lại **endpoint
packet/ledger** — xem mục 9.

## 8. Kiểm chứng sau vòng rà

- `tests/test_explanation_e4.py` — **33 test** (thêm 7 test hồi quy: interrupted
  chưa rank, claim gắn nhầm record, sentence không khớp claim, claim đổi
  proposition/subject, cờ H4 biến mất khỏi API, lattice lạ, exemplar đảo chiều,
  impact thiếu tên profile).
- **256 passed** trên toàn bộ test explanation; web **982 passed** (thêm test
  panel không-so-cặp và test trang cắm header); `tsc --noEmit` sạch; `ruff` sạch.
- **Full suite chưa chạy.**

## 9. Chưa làm — nói rõ

- **Endpoint packet/ledger vẫn chưa có**, và đây là mảnh duy nhất còn lại của E4.
  Nó vướng một quyết định thật: dựng packet phải đọc trace **mọi episode** để
  chạy detector, nên hoặc dựng lúc chấm (rẻ khi đọc, phải bump report), hoặc dựng
  theo yêu cầu và cache (report không đổi, request đầu tiên nặng). Chưa chốt nên
  chưa làm — không phải quên.
- **Chưa có analyst nào** sinh `HypothesisProposal` ngoài test; giao thức là E5.
- **Prevalence exemplar** vẫn chưa nối (nguyên liệu đã đủ từ E3).
- **`topology`/ngã rẽ** vẫn ở **E3.5**.

## 10. Vòng rà thứ hai — ba điểm

**HIGH-1 — ledger chưa chứng minh claim là kết quả của matrix.** Đúng, và đây là
điểm sâu nhất trong bốn phase. Các phép kiểm chéo tôi thêm ở vòng trước chỉ chứng
minh entry **nhất quán nội bộ** — sửa `level` lên `intervention_supported`, render
lại sentence cho khớp, giữ nguyên matrix version, và mọi phép kiểm đều qua. Schema
**không thể** làm hơn: một record có kiếm được mức đó hay không phụ thuộc tool
catalog và known unknowns của packet, cả hai đều **không nằm trong file**.

Nên tách rõ hai thao tác, và nói thẳng trong docstring:

| Thao tác | Trả lời câu gì |
|---|---|
| `ClaimLedger.model_validate` | file có đúng hình dạng và nhất quán nội bộ không |
| **`verify_ledger(ledger, packet, catalog=…, scope=…)`** | **có phải matrix tạo ra nó không** |

`verify_ledger` **chạy lại promote()** cho từng proposal/record đã lưu với packet
và catalog **do caller cung cấp**, rồi so claim, reasons và sentence. Biên tin cậy
là tham số, không phải artifact. Nó trả về ledger **vừa dựng lại** chứ không trả
input: cùng nội dung theo cấu tạo, nhưng khiến người gọi không thể verify xong rồi
tiếp tục render bản chưa verify.

Về checksum: An nói đúng — checksum do chính artifact mang **không** ngăn ai sửa
rồi tính lại. Nó chỉ còn dùng để bắt "ledger này trả lời packet khác", và
`verify_ledger` so nó với packet **được truyền vào**, không so với chính nó.

Test hồi quy dựng đúng ca An probe: nâng level **và** render lại sentence cùng
lúc ⇒ `model_validate` nhận, `verify_ledger` từ chối. Cộng ca giả mạo `reasons`
của một entry bị từ chối. (Vòng rà thứ ba đổi thông điệp lỗi sang dạng đường dẫn
— xem mục 12.)

**MEDIUM-2 — `showExemplars=false` đang ẩn toàn bộ trace.** Tôi gộp nhầm hai thứ.
Không có ΔU **không** đồng nghĩa không có trace: candidate trượt gate vẫn có
quỹ đạo, và đó đúng là thứ người hỏi "vì sao nó trượt" cần mở. Nay `PanelPlan` có
`show_trace_evidence` (**true ở cả năm kết cục**), `show_exemplars` chỉ điều khiển
bốn chip preregistered, và validator từ chối ca bật exemplar mà tắt viewer — bốn
cái link không dẫn đi đâu. Trang gate viewer theo `showTraceEvidence`, gate chip
theo `showExemplars`.

**Phạm vi.** Đúng, và tôi sửa cách ghi trạng thái ở đầu report: **deterministic
core + outcome header xong, end-to-end chưa**. Endpoint packet/ledger nằm ở
**E4.1** trong plan, chờ An chốt: dựng packet lúc chấm hay dựng theo yêu cầu +
cache.

## 11. Kiểm chứng sau vòng rà thứ hai

- `tests/test_explanation_e4.py` — **39 test** (thêm 6: forge level + sentence,
  verify trả bản dựng lại, verify sai packet, forge reasons, trace vẫn hiện khi
  không có so cặp, exemplar không có viewer).
- **262 passed** trên toàn bộ test explanation; web **982 passed**;
  `tsc --noEmit` sạch; `ruff` sạch.
- **Full suite chưa chạy.**

## 12. Vòng rà thứ ba — hai điểm

**HIGH-3 — `verify_ledger()` lấy câu hỏi từ chính câu trả lời.** Điểm này đúng và
nó vô hiệu hoá phần lớn giá trị của vòng rà trước. `_statement_of(entry)` đọc
`claim.statement`, nên statement đưa vào matrix để dựng lại **chính là** thứ đang
bị nghi ngờ. An probe: đổi statement sang kết luận về **B9** trong khi
proposal/record nói về **B7**, render lại sentence — matrix được chạy lại bằng
statement đã sửa, đồng ý với nó, verifier chấp nhận và **trả về một ledger mới
chứa nội dung giả**. Tệ hơn cả không verify, vì đầu ra được đóng dấu "đã kiểm".

Sửa: statement thành field riêng, `LedgerEntry.promotion_statement`.

- `build_ledger()` ghi đúng statement nó đã đưa vào `promote()`, cho **cả entry
  bị từ chối** — sentence no-claim chỉ mang reasons, nên không có gì trong một
  entry bị từ chối dựng lại được statement, và `proposal.hypothesis_statement` là
  một câu khác viết cho mục đích khác (fixture: `"inflation closes the gap"` vs
  `"the B7 passage is narrower than the required clearance"`). Fallback sang nó
  là đi xử lại một thứ chưa từng được xử.
- Validator của entry bắt `claim.statement == promotion_statement`, nên phép
  tráo của An **chết ngay lúc parse**, không đợi tới verify.
- `verify_ledger()` dựng lại từ `promotion_statement`, không đụng tới claim.

**Lỗ còn lại, nói rõ trong docstring.** Re-adjudication chứng minh kết luận suy
ra được từ input **nằm trong file**. Sửa đồng bộ cả `promotion_statement`,
proposal và record thì được một artifact tự nhất quán và cái này sẽ verify sạch.
Bắt loại đó cần digest giữ ở nơi artifact không với tới — ký, hoặc run store giữ
— module này không có. Ghi ra thay vì để người sau tự suy ra ngược.

**MEDIUM-3 — verifier chưa so toàn bộ bản dựng lại.** Cũng đúng, và cách hỏng thì
đúng như dự đoán: danh sách field do người chọn chỉ bảo vệ những field người đó
nghĩ ra. `run_id` không nằm trong danh sách, nên ledger bị gắn nhãn `forged-run`
verify sạch và **âm thầm** trả bản dựng lại mang `run_017` — file khai một nguồn
gốc, object đã verify khai một nguồn gốc khác. Trái đúng câu docstring tự viết.

Nay so **toàn bộ canonical dump** hai bên (`_differences()` đệ quy dict/list),
và exception mang **đường dẫn** chỗ lệch:
`entries.0.claim.level: file 'intervention_supported' vs matrix 'mechanism_verified'`.
"Verification failed" không phải audit; một đường dẫn thì phải. `header`,
`claim_id`, `run_id`, mọi field của record/proposal — tất cả vào diện so.

Vẫn trả bản dựng lại (An đồng ý điểm này): sau khi so bằng nhau thì nội dung
giống nhau theo định nghĩa, và trả bản mới khiến caller không thể verify xong rồi
tiếp tục render bản chưa verify.

## 13. Kiểm chứng sau vòng rà thứ ba

- `tests/test_explanation_e4.py` — **43 test** (thêm 4: verifier không lấy câu
  hỏi từ câu trả lời; refusal giữ statement gốc; ledger đổi `run_id` bị từ chối;
  failure nêu đúng đường dẫn `header.detector_version`).
- **271 passed** trên toàn bộ test explanation. `ruff check` + `ruff format` sạch.
- **Full suite chưa chạy.** Không đụng web ở vòng này.
