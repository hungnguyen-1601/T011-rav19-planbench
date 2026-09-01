# Ba lỗi full suite — hai thật, một nhiễu

**Ngày:** 2026-08-18
**Nguồn:** lượt full suite chạy nền trong lúc H2/H3/H4 đang được viết.
**Kết quả lượt đó:** 3 failed, 2896 passed, 8 skipped, 38:36.

---

## 0. Verdict của lượt đó bỏ, ba lỗi thì không

Lượt suite khởi động khi `host/` chưa tồn tại rồi chạy xuyên qua ba lần
ghi file. Con số tổng vì thế vô nghĩa. Nhưng ba tên test đỏ vẫn là manh
mối, nên phân loại từng cái **bằng cách chạy lại trên cây sạch** thay vì
đoán.

Kết quả: **2 thật, 1 nhiễu.**

## 1. Thật — `dev_stack.sh` thiếu `packages/plugin_sdk` (regression H1a)

```
tests/test_dev_stack_pythonpath.py::test_the_server_can_import_everything_the_suite_can
```

H1a thêm `packages/plugin_sdk` vào `pythonpath` trong `pyproject.toml`
và **quên** `PY_PATH` trong `scripts/dev_stack.sh`. Docstring của chính
guard nói đúng hậu quả: *"A package the suite can import and the server
cannot is a green test run over code that will not start."*

Đúng loại lỗi im lặng repo này hay dính: suite xanh, server chết lúc
khởi động, và không ai nối hai việc với nhau. Guard tồn tại chính vì thế
và đã làm đúng việc.

**Sửa:** thêm một dòng `PY_PATH` cho `packages/plugin_sdk`.

## 2. Thật và **đúng thiết kế** — hàng rào 13-08 bắn đúng ngày

```
tests/test_simulator_fairness.py::test_a_monolithic_candidate_still_cannot_be_built
```

Note 13-08 (`tongduyan_no-ky-thuat-ton-dong.md`, mục A1) đã viết sẵn:
*"`test_only_modular_stacks_can_run_today` sẽ đỏ đúng ngày adapter được
thêm — hàng rào đã đặt sẵn."* H1b trả A5, `stack_id_for` bỏ chuỗi
`"does not exist yet"`, hàng rào bắn.

**Không xoá test.** Xoá là vứt luôn câu hỏi mà nó được đặt ra để ép hỏi.
Tách làm hai, mỗi cái ghim một nửa:

- `test_a_monolithic_candidate_can_now_be_built` — ghim **trạng thái
  mới**: `build_policy` dựng được `MonolithicPolicy` từ một
  `Candidate(type="monolithic")`. Tiền đề cũ đã hết, và điều đó được ghi
  chứ không bị im lặng.
- `test_g6_has_still_never_priced_an_observation_difference` — **nạp lại
  hàng rào cho sự kiện thật**. Cảnh báo gốc chưa bao giờ là về *dựng*
  một policy; nó về **so sánh** một policy với stack modular. G6 định
  giá `observation_requirements`, mà mọi candidate từ trước tới nay khai
  **cùng một bộ** — điều khoản đó xanh vì chưa bị thử, không phải vì
  đúng.

  Điều đó **chưa đổi**: policy duy nhất đang đăng ký là reference D12,
  không bao giờ là contender. Test mới đỏ đúng ngày ai đó đăng ký một
  policy có thể là contender — tức đúng lúc phải kiểm định giá, trước
  khi công bố phép so chứ không phải sau.

## 3. Nhiễu — `inspect.getsource` đọc file đang bị sửa

```
tests/test_simulator_fairness.py::test_the_ground_truth_hatch_is_used_by_the_stack_not_by_a_planner
```

Test đọc source của `get_observation` + `_measured_ranges` bằng
`inspect.getsource`. H3 thêm property `steps` vào `engine.py` **ở phía
trên** hai method đó, dời số dòng đi 13. Module đã import từ trước (code
object giữ số dòng cũ), còn `getsource` đọc file mới ⇒ trả về đoạn text
lệch ⇒ assert đỏ.

Chạy lại trên cây sạch: **xanh**. Không có gì để sửa.

Đáng ghi vì nó minh hoạ chính xác vì sao verdict lượt đó phải bỏ: một
test dựa trên `inspect.getsource` là **không an toàn khi cây thay đổi
giữa chừng**, và suite này có vài test như thế.

## 4. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `test_dev_stack_pythonpath.py` + `test_simulator_fairness.py` sau sửa | **57 passed** |
| Full suite sạch | chạy sau khi commit |

## 5. Bài học ghi lại

Đừng chạy full suite nền trong lúc còn viết code. 38 phút đo một cây
đang đổi cho ra một verdict không thuộc về commit nào — và tệ hơn, nó
trộn lỗi thật với nhiễu, nên vẫn tốn công phân loại lại từ đầu. Rẻ hơn
là chạy sau khi cây đứng yên.
