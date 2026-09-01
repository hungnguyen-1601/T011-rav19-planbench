# Hai môi trường, và hai dependency chưa bao giờ được khai

**Ngày:** 2026-08-12 · **Loại:** quan sát/chẩn đoán · **Khởi từ:** báo lỗi `No module named 'pyarrow'`

---

## 0. Kết luận trước

Không có xung đột môi trường. Có **hai môi trường Python**, và cái mà README chỉ định (`.venv`)
thiếu gói — trong khi cái tôi đã dùng suốt (conda base) tình cờ đủ. Ba vấn đề độc lập lộ ra, xếp
theo mức nghiêm trọng tăng dần:

1. `.venv` cũ, thiếu `pyarrow` + `jsonschema` — **khai báo đúng, môi trường cũ**.
2. `scripts/dev_stack.sh` bảo dựng `.venv` từ **sai file** requirements.
3. **`psutil` chưa bao giờ được khai ở đâu cả**, mà thiếu nó thì ghim nhân CPU trên Windows không
   hoạt động — tức biện pháp bảo vệ phép đo của HĐ-7.4 vắng mặt.

## 1. Vấn đề đầu: `.venv` cũ

| | `pyarrow` | `jsonschema` |
|---|---|---|
| `C:\Users\Admin\miniconda3\python.exe` | ✅ 25.0.0 | ✅ 4.26.0 |
| `E:\...\P-011\.venv` | ❌ | ❌ |

Đối chiếu `.venv` với `requirements.txt`: ghim 18 gói, **thiếu đúng 2, không lệch phiên bản nào**.

`.venv` dựng `2026-08-04`. Hai gói thêm vào sau, ở commit `fa9df8a` (TraceRecorder Parquet). Từ đó
chưa ai chạy lại `pip install -r requirements.txt` trong `.venv`.

**Không liên quan tới việc xoá `uv.lock` sáng nay.** `.venv/pyvenv.cfg` ghi
`command = ...python.exe -m venv ...` — nó do `python -m venv` tạo, chưa bao giờ đi qua `uv`. Và
`uv.lock` cũ khai **0 dependency**, nên `uv sync` cũng chẳng cài gì. Thiếu hụt có từ 11-08.

**Đã sửa:** cài `requirements.txt` vào `.venv`.

## 2. Vấn đề thứ hai: script bảo dùng sai file

`scripts/dev_stack.sh:180` in ra hướng dẫn dựng môi trường:

```
.venv/bin/pip install -r docker/requirements-api.txt
```

Đó là file cho **image Docker**. Nó không có `pytest`, `ruff`, `pytest-cov`, `httpx`. Ai làm theo
sẽ có một `.venv` chạy được server mà **không chạy nổi test suite**.

Trong khi README dòng 221 nói rõ *"Bạn không cần đụng tới nó khi làm việc cục bộ"*, và CI
(`.github/workflows/ci.yml:30`) dùng `requirements.txt`. Ba nơi, hai đáp án.

**Đã sửa:** thông điệp trong `dev_stack.sh` trỏ về `requirements.txt`, kèm giải thích vì sao không
phải file kia. Đã rà: không chỗ nào khác trỏ sai.

## 3. Vấn đề thứ ba, và là cái đáng lo nhất: `psutil`

Chạy full suite bằng `.venv` — **lần đầu tiên** — ra 2 test đỏ mà conda base không có:

```
FAILED tests/test_hostinfo.py::TestPinning::test_it_pins_and_reports_the_mask_the_os_granted
FAILED tests/test_hostinfo.py::TestPinning::test_the_host_record_says_who_pinned_it
    assert 'inherited' == 'script'
```

Truy nguyên: **Windows không có `os.sched_setaffinity`** (chỉ Linux có). `hostinfo.py` rơi về
`psutil` ở đó. Thiếu `psutil` ⇒ `pin_to_cores()` trả `None` ⇒ **run không được ghim**.

`psutil` **không được khai ở bất kỳ file requirements nào**. Nó chạy được suốt vì môi trường conda
tình cờ có sẵn (Anaconda ship kèm) — một `.venv` dựng đúng theo README thì không.

Mỉa mai nhất: `hostinfo.py:50` có sẵn comment

```python
except ImportError:  # pragma: no cover - psutil is a pinned dependency
```

Code **tin rằng** nó đã được ghim. Chưa bao giờ.

### Hệ quả, nói chính xác

Ghim nhân là biện pháp bảo vệ phép đo của HĐ-7.4: G4 đọc độ trễ theo đồng hồ tường, và **cùng một
stack đo được 59,30 ms không ghim so với 16,10 ms khi ghim 2 nhân** — chênh lệch lớn hơn khoảng
cách giữa các candidate với nhau.

Hệ thống **có báo**: `affinity_source: inherited`, cộng cảnh báo trên report và trên stdout. Nó suy
giảm có tiếng chứ không âm thầm — đó là thiết kế đúng. Nhưng *biện pháp bảo vệ* thì vắng mặt, và
đó mới là điều đáng kể.

### Đã kiểm: không phép đo nào bị vô hiệu

```
open_hall_v2_global_planner_selection_ce26fe87   affinity=[0,1]  source=script
open_hall_v2_local_controller_selection_3edf8f   affinity=[0,1]  source=script
open_hall_v2_local_controller_selection_4c62ec   affinity=[0,1]  source=script
open_hall_v2_local_controller_selection_50980d   affinity=[0,1]  source=script
warehouse_a_v2_global_planner_selection_ce26fe   affinity=[0,1]  source=script
open_hall_v2_local_controller_selection_3edf8f   affinity=[0..19] source=inherited   <- bản dựng lại
```

Mọi run thật đều ghim thật, vì chúng chạy bằng conda base. Dòng cuối là bản dựng lại tấm card đầu
tiên hôm nay: tôi truyền `--no-pin` và nó `--score-only` (chấm lại từ trace có sẵn, không mô
phỏng), nên độ trễ đến từ file đã ghi và việc không ghim không ảnh hưởng gì.

**Đã sửa:** khai `psutil==7.2.2` vào `requirements.txt` kèm lý do đầy đủ. **Không** thêm vào
`docker/requirements-api.txt`: image là Linux, `os.sched_setaffinity` có sẵn, nhánh psutil không
với tới được. Đã ghi comment vào file đó nói rõ sự bất đối xứng là cố ý, để lần sau không ai "sửa"
theo chiều nào cả.

Sau khi cài: `tests/test_hostinfo.py` 12 passed.

## 4. Lỗi của tôi

Toàn bộ test hôm nay (2277 passed) tôi chạy bằng **conda base**, không phải `.venv` mà README chỉ
định từ đầu. Nên con số đó **không nói gì về `.venv`**, và chính vì conda base tình cờ đủ gói mà cả
`pyarrow` lẫn `psutil` nằm im.

Đây đúng dạng lỗi mà dự án này tồn tại để chặn: **một phép kiểm xanh trên môi trường không phải môi
trường đang được nói tới.** Bài học giống hệt `n_distinct_episodes` — con số trông đúng, mẫu thì
không phải cái người ta tưởng.

**Đã thêm vào README** một mục: sau `git pull` phải cài lại, kèm triệu chứng thật, cách kiểm bằng
`pip install --dry-run`, và cảnh báo rằng gõ `pytest` trần có thể xanh trên một môi trường không
phải của dự án.

## 5. Vấn đề thứ tư, tìm ra khi thêm job Windows: **CI đang đỏ sẵn**

`ci.yml` chạy `ruff format --check .`. Lệnh đó **exit 1 trên HEAD**, trước mọi thay đổi hôm nay —
xác minh bằng `git stash`:

```
5 files would be reformatted, 303 files already formatted
```

Năm file: `decision_service.py`, `routers/decisions.py`, `test_api_decisions.py`,
`test_migrations.py`, `test_simulator_fairness.py`. Toàn bộ khác biệt là **nối dòng thuần tuý** —
8 dòng thêm, 20 dòng bớt, không có gì ngữ nghĩa. `ruff` trong `.venv` là `0.16.0`, đúng phiên bản
`requirements.txt` ghim, nên đây chính là kết quả CI sẽ ra.

Nghĩa là bước lint của CI đã fail một thời gian mà không ai thấy. Đã chạy `ruff format .`; giờ
exit 0, và 69 test trên hai file test bị chạm vẫn xanh.

## 6. Job Windows đã thêm

`ci.yml` chuyển sang matrix `[ubuntu-latest, windows-latest]`, `fail-fast: false`, timeout 90 phút.
Hai bước `ruff` chỉ chạy trên Linux — quy tắc format và lint do `ruff.toml` quyết, không phụ thuộc
nền tảng, chạy hai lần chỉ tốn phút để tới một kết luận đã có.

**Chạy toàn bộ suite trên cả hai, không phải một tập con "nhạy nền tảng" trên Windows.** Chọn tập
con nghĩa là đoán trước dependency chưa khai trong tương lai sẽ làm hỏng test nào — mà khoảng
trống `psutil` **không nhìn thấy được từ mã nguồn**: không chỗ nào trong `hostinfo.py` import
psutil ở mức module, và nhánh có import thì không với tới được trên nền tảng CI đang chạy.

**Một giới hạn phải nói rõ của chính job này.** Test ghim nhân **tự skip** trên máy dưới ba nhân
logic — đúng, vì `pin_to_cores(2)` từ chối chiếm trọn một máy hai nhân (chiếm hết nhân không phải
là ghim). Nên trên runner nhỏ, nhánh psutil bị **skip chứ không được chạy**, và job này sẽ xanh
xuyên qua đúng cái lỗ hổng nó sinh ra để bắt. Nếu image Windows của GitHub quay về hai nhân thì
lớp phủ đó biến mất lặng lẽ — dấu hiệu duy nhất là số skip, nên **đọc số skip, đừng chỉ đọc màu**.
Đã ghi vào comment trong `ci.yml`.

## 7. Còn để ngỏ

- **`.venv` không có gì kiểm nó còn khớp `requirements.txt`.** Lệnh
  `pip install --dry-run -r requirements.txt` làm được việc đó trong một giây; chưa nối vào đâu.
- **CI vẫn không bắt được vấn đề ① và ②** — chúng là chuyện môi trường cục bộ, CI luôn dựng môi
  trường sạch từ `requirements.txt` nên không bao giờ gặp một `.venv` cũ hay một script chỉ sai
  file. Chỉ có README và `dev_stack.sh` đứng chắn, và cả hai đã sửa.
