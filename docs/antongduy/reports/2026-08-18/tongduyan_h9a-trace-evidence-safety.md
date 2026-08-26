# H9A — oracle trace không còn đè được production trace

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §13, khoản P0 thứ nhất
**Trạng thái:** xong sau một vòng rà giữa chừng của An (mục 7). **Chưa commit.**

---

## 1. Lỗ được đóng, và vì sao nó nặng hơn bốn khoản kia

Bốn khoản hở còn lại là **thiếu tính năng**. Khoản này **làm hỏng dữ
liệu**: trace được định địa chỉ bằng `candidate_id/episode_context_id` —
đúng hai id mà HĐ-3.1 cố ý **không** đưa môi trường vào — nên một
research run và một production run của cùng một candidate ghi vào **cùng
một file**, và cái sau xoá cái trước. Mọi chỗ khác trong host đều từ
chối; riêng chỗ này ghi đè.

## 2. Hai cơ chế, không cơ chế nào đủ một mình

**Địa chỉ chặn phía ghi:**

```text
root/<evidence_class>/<execution_fingerprint>/<candidate_id>/<context_id>.parquet
```

**Policy chặn phía đọc:** `TraceUsePolicy` — `PRODUCTION_USE`,
`REFERENCE_USE`, `RESEARCH_USE` — hỏi qua `load_trace_for_use` /
`metadata_for_use`, cộng `_check_address` bắt file phải khớp chỗ nó nằm.

Ghi thẳng vào docstring vì đây là chỗ dễ làm nửa vời: *guard lúc đọc mà
địa chỉ vẫn đụng nhau thì vẫn mất dữ liệu; địa chỉ tách mà không guard
thì file copy vẫn chấm được. Cả hai, hoặc không cái nào.*

## 3. `unknown` — trace cũ không được tự nâng lên production

`TraceMetadata.evidence_class` mặc định `"unknown"`, và **không policy
nào nhận `unknown`**. Coi "không nói" thành "production" sẽ nhận đúng
những trace nhiều khả năng có trước thay đổi nhất — cùng lập luận, cùng
câu trả lời fail-closed như fingerprint rỗng của 16-08.

Giá: **kho trace hiện có phải chạy lại một lượt.** Đã khai trước ở §13.

Kèm một trạng thái thứ hai: episode chạy **ngoài** contract pipeline
(test, script chẩn đoán) không có fingerprint, và rơi vào thư mục
`unfingerprinted/`. Luật cho nó không đổi — fingerprint rỗng vẫn bị reuse
và scoring từ chối — chỉ là giờ nhìn thấy được trong `ls` thay vì chỉ
hiện ra trong một lời từ chối.

## 4. `TraceLocator` — một chỗ tính địa chỉ, không phải sáu

Sáu call site trong `pipeline.py` từng tự dựng `trace_path(...)`. Khi địa
chỉ mọc thêm class và conditions hash thì sáu chỗ tính độc lập là sáu chỗ
để lệch nhau — và lệch giữa "ghi ở đâu" với "tìm ở đâu" đọc ra thành
*không có trace*, tức im lặng.

`_was_run_under` thành dead code và bị xoá; logic của nó nằm trong
`locator.usable()` cộng phép kiểm class.

## 5. Địa chỉ thứ tư: thư mục run và journal

`run_dir_name` nhận `evidence_class`; `production` **giữ nguyên tên cũ**
để mọi thư mục run đã lưu ở nguyên chỗ.

## 6. Amendment fixture parity — một trường, có kiểm chứng

Địa chỉ đổi ⇒ `trace.relative_path` trong fixture H0 đổi. **Amendment,
không regenerate**: giá trị mới suy từ **chính fixture** (fingerprint
`099276fee87e0c17`, candidate id và context id đều là bytes viết trước
khi host tồn tại), và script sửa tự `assert` rằng **không dòng nào khác**
dịch. Kết quả: 4 record, đúng 4 dòng, tất cả là `relative_path`.

## 7. Vòng rà giữa chừng của An — 7 điểm, **đúng cả 7**

Hai điểm nặng nhất là một cặp, và **#5 giải thích #1**.

| # | Vấn đề | Bản sửa |
|---|---|---|
| 1 | **Critical** — `evidence_class` không tới `run_contract_episode`, nên sweep chạy oracle vẫn ghi vào `production/` | `run_contract_episode(..., evidence_class=)` → recorder; `simulate` truyền `locator.evidence_class` |
| 2 | **High** — `run_dir_name` nhận class nhưng `run_comparison` không truyền ⇒ chỉ đúng ở unit test | knob `evidence_class` trên `run_comparison`, thread tới run dir, `simulate`, `paired_prefix` ×2, `score`, watcher, `trace_checksum` |
| 3 | **High** — amendment fixture mới mô tả, chưa làm | đã làm (mục 6) |
| 4 | **High** — API có thể trả production trace của **thế giới khác** (`matches[-1]`) | lọc theo fingerprint của chính run; nhiều match cùng điều kiện ⇒ `InvalidStateError` thay vì chọn bừa |
| 5 | **Medium** — test H9A không đi qua đường tích hợp mà nó tuyên bố | file test mới đi qua `simulate` / `simulate(reuse=True)` / `score` |
| 6 | **Medium** — regression chưa xanh + E501 | `test_partial_runs` xanh; ruff sạch trừ 2 file nợ cũ không thuộc phạm vi |
| 7 | Report còn "đang điền" | điền |

**#5 là điểm đáng nhớ nhất của cả phase.** Bộ test H9A đầu tiên pass
**16/16** trong khi `evidence_class` chưa bao giờ tới recorder: mọi test
gọi thẳng component — `TraceLocator.load`, `find_traces`,
`locator.usable` — nên chúng đồng ý với một hệ thống **chưa nối**. Namespace
đã tách và không có gì được định tuyến vào đó. *Một guard không ai đi tới
thì không phải guard, và unit test đúng là dụng cụ không phân biệt nổi
hai trường hợp đó.*

File test mới vì thế đi qua **đường một run thật đi**, và có cả chiều
ngược (production **có** reuse trace của chính nó) để lời từ chối không
phải một nhánh chẳng bao giờ chạy.

## 8. Một lỗi tự tìm ra khi sửa #5, cùng lớp, thấp hơn một tầng

Fixture của chính file test tích hợp ghép `make_profile` (map
`warehouse_a`) với map `doorway` — **sai cặp**, nên mọi episode kết thúc
ngay bằng `no_path` và sáu test "pass" mà chưa từng chạy một episode
được lái. Chạy hết trong 0.94 s, và tốc độ đó lẽ ra là dấu hiệu.

Đã đổi sang map của chính profile: cùng bảy test giờ mất **2:47** vì
episode chạy thật. *Một fixture mà hai nửa không khớp nhau là một test tự
đồng ý với mình.*

## 9. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/test_trace_evidence_safety.py` (mới, 16 test) | **16 passed** |
| `tests/test_evidence_class_integration.py` (mới, 7 test) | **7 passed**, 2:47 — episode chạy thật |
| `tests/test_trace.py` + `test_trace_checksum.py` | **47 passed** |
| `tests/test_partial_runs.py` | **6 passed** |
| Lát cắt trace + parity + API | **720 passed, 1 skipped**, 22:51 |
| **Parity trên fixture đã amend** | **xanh trọn** — nếu H9A làm dịch bất cứ thứ gì ngoài địa chỉ, lượt này đã đỏ ở một trường khác |
| `ruff check` `packages/` `services/` `apps/` | sạch |
| Amendment fixture | 4 dòng, tất cả `relative_path`, assert bằng script |

## 10. Kế tiếp

H9B — candidate provider identity.
