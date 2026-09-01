# Tầng cố vấn — nói việc nên làm, và gọi tên việc bị cấm

**Ngày:** 2026-08-18 · **Commit:** `7f6830f` (lõi), `7c4c48a` (nối vào người dùng)
**Quy mô:** 13 file +4.920 dòng · 26 file +3.812 −342

---

## 1. Khoảng trống

Mọi cổng trong nền tảng trả lời đạt hoặc trượt. Đó là hình dạng đúng cho
một **quyết định** và sai cho một **con người**: `G3 fail, 0.71 < 0.85`
đúng, kiểm được, và bỏ mặc người đọc tự nghĩ xem cách sửa là một phương
án tốt hơn, một cách chia scenario khác, hay — nước đi phá hỏng toàn bộ
ý nghĩa — hạ `success_rate_min` rồi chạy lại.

**Nước đi đó cách đúng một ô trong form mà chính người đó được phép
sửa.** Mọi cổng ở đây đều có một nước như vậy. Người chỉ được báo "trượt"
là đang bị mời đi tìm chúng.

## 2. Một kiểu dữ liệu, năm module

`packages/decision/planbench_decision/advice.py` — `Advice` là
`Finding` cộng hai trường:

```python
do:     str   # việc nên làm, cụ thể đủ để hành động
do_not: str   # nước đi làm triệu chứng biến mất mà không làm kết luận đúng lên
```

| Module | Luật | Trả lời |
|---|---|---|
| `planbench_benchmark/preflight.py` | 12 | trước khi chạy, cấu hình này sai chỗ nào |
| `planbench_decision/gate_advice.py` | 10 | cổng này trượt nghĩa là gì, làm gì tiếp |
| `planbench_metrics/trace_review.py` | 11 | episode này hỏng ra sao, từ chính trace |
| `planbench_benchmark/reproduction.py` | 6 | vì sao số khác bài báo |
| `planbench_decision/report_advice.py` | 18 | câu nào bằng chứng không cho phép viết |

**57 luật**, cộng 7 luật `outcome.py` thêm sau → 64.

## 3. Hai cạm bẫy ở nền — cả hai đều xoá lời khuyên trong im lặng

### 3.1 `resolve()` không phân biệt "vắng mặt" với "có nhưng null"

```
trường CÓ, giá trị null  → resolve = None
trường KHÔNG TỒN TẠI     → resolve = None
```

`keep_resolvable` dùng `resolve(...) is not None` nên **xoá cả hai**. Mà
loại thứ nhất chính là loại lời khuyên đáng nói nhất: *"run này không đo
effect size"* là một khẳng định **về** một null.

Thêm `exists()` phân biệt hai chuyện; `keep_resolvable` chuyển sang dùng
nó. Không đụng `resolve()` vì 15 luật `self_check` viết theo hợp đồng cũ.

### 3.2 Bộ duyệt đường dẫn kiểm `dict`, mọi module khai `Mapping`

```
dict thường      : exists = True  | giữ lại 1
MappingProxyType : exists = False | giữ lại 0   ← xoá sạch
```

Caller nào **làm đúng khai báo kiểu** — dùng `MappingProxyType` để trao
ra bản chỉ đọc — mất toàn bộ lời khuyên, không một thông báo. Và không
gì phát hiện được, vì trích dẫn bị xoá trông y hệt luật chọn không lên
tiếng.

Đã đổi sang `Mapping`/`Sequence`, đồng thời chặn `str` bị coi là dãy —
nếu không `note[0]` trả về một ký tự, tức một trích dẫn vô nghĩa lại
**qua được** đúng cái kiểm tra sinh ra để bắt trích dẫn vô nghĩa.

## 4. Ba lỗi lộ ra khi chạy dữ liệu thật

Không lỗi nào lộ qua đọc code:

1. **`Candidate.params` lồng dưới tên controller** (`{'dwa': {...}}`),
   không phẳng. Đọc phẳng ra `None` cho mọi tham số — biến một phép so
   hai cấu hình thành phép so với hư không.
2. **`PF_BUILD_FAILED` che chẩn đoán cụ thể hơn.** Người đọc nhận "không
   dựng được" thay vì "đây là bản tham chiếu, đừng xếp hạng với nó".
3. **`PF_GOAL_UNREACHABLE_FOR_RADIUS` khai trong `PREFLIGHT_CODES` mà
   không luật nào phát ra** — code chết. Nối vào phép kiểm mission-vừa-
   bản-đồ có sẵn.

## 5. Kiểm chứng

Mỗi trích dẫn được đối chiếu với source dict thật qua `exists()`, **vét
cạn chứ không lấy mẫu** — vì trích dẫn sai bị xoá im lặng, nên một lỗi gõ
trong đường dẫn trông hệt như luật chọn không lên tiếng.
