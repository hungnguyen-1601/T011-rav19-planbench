# H4 — preflight resolver, fingerprint mở rộng, ownership accounting

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §8 H4
**Trạng thái:** xong, 22 test mới xanh, 139 passed trên lát cắt host, **chưa
commit**. Về full suite: xem mục 6 — lượt đang chạy **không dùng được**.

---

## 1. Đã tạo / sửa

| File | Việc |
|---|---|
| `packages/benchmark/.../fingerprint.py` | **mở rộng**, không tạo hash mới: thêm `HostConditions` + tham số `host` cho `execution_conditions_fingerprint` |
| `services/simulator/.../host/compatibility.py` | **mới**: `HostSupport`, `ProviderOwnership`, `CompatibilityReport`, `resolve_compatibility` |
| `.../host/provider_graph.py` | thêm `provenance_of()` — đầu vào của ownership split |
| `tests/test_compatibility_and_accounting.py` | **mới**, 22 test |

## 2. Điều khó nhất: mở rộng hash mà không làm mồ côi kho trace

§7.1 cấm tạo fingerprint song song, nên host phải chảy qua đúng
`execution_conditions_fingerprint`. Nhưng thêm field vào payload là đổi
**mọi** fingerprint đã lưu — đúng cái giá fail-closed mà 16-08 đã trả một
lần, trả lần hai là vô cớ.

Giải: `host` **vắng mặt khỏi payload** khi `None` hoặc rỗng. Đường legacy
không truyền gì ⇒ payload byte-identical với trước ⇒ hash không dịch.
Chỉ khi deployment thật sự khai provider/lane/adapter thì hash mới đổi —
và lúc đó nó *phải* đổi, vì đó là điều kiện chạy khác.

**Chứng bằng bytes trong git, không bằng số tính trong phiên:** test đọc
`execution_conditions_fingerprint` từ fixture H0 (commit `7a7c195`, sinh
trước khi host tồn tại) và so với giá trị tính hôm nay. Khớp.

Ba hướng đều có test: absent / empty / legacy đều không dịch; provider
deployment-owned, adapter chain, và **codec trong runtime profile** đều
làm dịch.

## 3. Một defect test bắt được, sửa ở model chứ không ở test

`test_provider_declaration_order_does_not` đỏ ngay lần chạy đầu: hai thứ
tự khai của cùng một tập provider cho hai hash. Tôi mới sort trong
`ProviderOwnership.hashable()`, không sort tại cửa `HostConditions` —
nên bất kỳ caller nào dựng model trực tiếp đều làm hash dịch.

Sửa bằng validator canonical hoá **tại model**, đúng bài học
`canonical_observations`. Kèm quyết định phân biệt: `providers` là
**tập** nên sort; `adapter_chain` là **chuỗi** nên giữ nguyên thứ tự —
hai adapter đảo thứ tự là một phép biến đổi khác.

## 4. Guard cho cánh cửa `CONDITION_ARGUMENTS` không canh

Guard cũ so chữ ký `run_stack`. Host conditions **không** đi qua
`run_stack`, nên nó không phủ. Thêm guard riêng: liệt kê
`HostConditions.model_fields`, dựng từng field một, khẳng định mỗi field
đều làm dịch fingerprint. Thêm field mà không quyết định ⇒ test đỏ.

Phòng thủ gốc vẫn là "băm từ object": `_canonical(host)` gọi
`model_dump` nên field mới tự động vào payload. Guard này ghim đúng lời
khẳng định đó, phòng ngày ai đó đổi sang dict dựng tay.

## 5. Preflight — quyết định thiết kế

**Báo mọi vấn đề trong một lượt.** Không return ở refusal đầu tiên: sửa
provider thiếu rồi mới phát hiện lane cũng thiếu là bắt người ta chạy
preflight hai lần cho một cấu hình sai.

**Nhưng state chỉ một, và thứ tự có lý do.** `incompatible` thắng
`missing_runtime` thắng `missing_provider`: cài provider **không** làm
plugin Ackermann chạy được trên host differential-drive, và bảo người ta
đi cài là phí buổi chiều của họ. Có test khoá đúng thứ tự này.

**Nhiều alternative = tương thích.** Plugin khai `["trajectory@1",
"continuous-velocity@1"]` nghĩa là "cái nào cũng được" — từ chối vì cái
không hỗ trợ là dựng lời từ chối bằng chính alternative nó đưa ra.

**Ownership ba ngả** (§7.1): candidate-owned đổi `candidate_id`;
deployment-owned và oracle-owned vào fingerprint. Test khoá rằng provider
candidate-owned **không** lọt vào `hashable()` — băm hai lần sẽ chẻ
episode của một candidate ra hai fingerprint cho thay đổi mà identity đã
ghi rồi.

**Fairness tới được preflight**: production policy từ chối graph có
oracle *trước episode*; research policy nhận và ghi `evidence_class =
oracle` vào report.

## 6. Kiểm chứng — và một lượt đo phải bỏ

| Kiểm | Kết quả |
|---|---|
| `tests/test_compatibility_and_accounting.py` (mới) | **22 passed** |
| Lát cắt host: H1a+H1b+H2+H3+H4 + execution_conditions | **139 passed** |
| `ruff check` toàn `packages/` + `services/` | sạch |
| Fingerprint legacy vs bytes commit `7a7c195` | **khớp** |
| **Full backend suite (lượt bẩn)** | 3 failed, **2896 passed**, 38:36 — verdict không dùng được, nhưng ba lỗi đáng đọc |

**Vì sao verdict của lượt đó không dùng được.** Nó khởi động ngay sau
khi commit H1a/H1b/gate, lúc `host/` chưa tồn tại và `candidates.py`
chưa sửa; H2/H3/H4 ghi đè file trong khi suite còn chạy, mà pytest import
module dần — nên lượt này đo một cây **đang thay đổi giữa chừng**. Số
2896/3 không thuộc về commit nào.

**Nhưng ba lỗi vẫn đáng phân loại, và phân loại xong thì 2 thật 1 nhiễu**
(kiểm lại từng cái trên cây sạch — xem report riêng
`tongduyan_ba-loi-full-suite.md`):

| Lỗi | Phán |
|---|---|
| `test_the_server_can_import_everything_the_suite_can` | **thật** — H1a thêm `packages/plugin_sdk` vào pythonpath của pytest mà quên `dev_stack.sh` |
| `test_a_monolithic_candidate_still_cannot_be_built` | **thật, và đúng thiết kế** — hàng rào 13-08 bắn đúng ngày A5 được trả |
| `test_the_ground_truth_hatch_...` | **nhiễu** — `inspect.getsource` đọc `engine.py` đang bị sửa ở số dòng cũ; xanh trên cây sạch |

Cả hai lỗi thật đã sửa. Full suite **sạch** chạy sau khi commit.

## 7. Kế tiếp

H5 — discovery + trusted Python runtime: entry-point discovery, synthetic
manifest hợp nhất vào đường discovery chung, dependency thiếu vẫn
registered-nhưng-không-runnable, discovery không execute plugin code.
