# Hai nợ hạ tầng: trace của thế giới cũ, và LiDAR nửa vòng

**Ngày:** 2026-08-16
**Phạm vi:** hai lỗi im lặng lộ ra khi làm plan tri giác, **không** liên
quan `dwa_predictive`.
**Trạng thái:** đã sửa, có test, chưa commit.

---

## 0. Vì sao hai lỗi này đáng làm riêng

Cả hai đều **không báo gì**. Không exception, không cảnh báo, không số
liệu lệch nhìn thấy được. Lỗi thứ nhất chỉ lộ ra vì một tạo tác tình cờ;
lỗi thứ hai chưa lộ ra bao giờ và đang chờ sẵn.

Chúng cũng không thuộc về candidate vừa bị rút. Lỗi (a) ảnh hưởng **mọi**
phép so; lỗi (b) ảnh hưởng **`dwa` thường**, tức candidate đang ship.

---

## 1. Nợ (a) — trace của thế giới cũ được dùng lại âm thầm

### Bằng chứng

Chạy lại `warehouse_crossing_v1` sau khi rút `v_obstacle_max`:

```
run_journal.jsonl:  120 bản ghi
  60 đầu:  toàn 'stuck'   (profile CÓ v_obstacle_max)
  60 sau:  toàn 'success' (profile ĐÃ rút)
  episode_context_id, cả hai khối:  b408516ece7f
```

Hai thế giới khác nhau, **một id**, một file. Người đọc file này kết luận
episode đó chập chờn.

### Ba cơ chế phải xếp hàng cùng lúc

| | |
|---|---|
| HĐ-3.1 đóng băng `episode_context_id` ở *(task profile, mission, variant, seed)* | **environment không nằm trong đó** |
| Trace định địa chỉ bằng `trace_root/candidate_id/episode_context_id.parquet` | không có gì khác trong đường dẫn |
| `--reuse-traces` chỉ kiểm `path.is_file()` (`pipeline.py:224`) | không hỏi trace đó từ đâu ra |

Cộng thêm: thư mục run đặt tên từ *(profile id, scope, candidate set)* —
không thứ nào đổi khi **thế giới** đổi — và journal mở chế độ append.

### Bản sửa

**Băm từ object, không từ danh sách field.** Lý do nằm trong lịch sử của
chính nó: bản liệt kê tay đầu tiên mắc **cả hai chiều lỗi** trong một
lần viết —

- **sót** `clearance_preference` — nó đổi planning grid nên đổi quỹ đạo;
- **thừa** `clearance_warning_m` — chỉ Metrics Engine đọc lúc chấm một
  trace đã có, đổi nó không việc gì phải mô phỏng lại.

Nên payload dựng từ **đúng năm tham số điều kiện `run_stack` nhận**:

```python
execution_conditions_fingerprint = sha256(
    map_data.checksum(),
    scenario_payload(scenario),   # trừ name, description, random_seed
    profile.replanning,
    profile.recovery,
    profile.environment.v_obstacle_max,
)
```

Thêm field vào `Scenario` là tự động được phủ, không ai phải nhớ.

Bốn điểm chặn:

```
ghi:           EpisodeTraceRecorder -> TraceMetadata
--reuse-traces: _was_run_under() lệch  -> mô phỏng lại
--score-only:   lệch                   -> StaleTraceError, TỪ CHỐI
journal:        truncate mỗi sweep     -> không nối hai run
```

**Score-only từ chối chứ không cắt ngắn.** Chấm điểm đọc lại trace đã
xong và không bao giờ mô phỏng lại, nên không có cách thay thế trace
hỏng. Cắt ngắn im lặng sẽ trả về report dựng một phần từ thế giới không
ai hỏi, và độ dài mẫu là manh mối duy nhất nó để lại.

**Fail-closed.** Trace cũ mang fingerprint rỗng; rỗng đọc là *không
biết*, không phải *khớp*. Coi hai thứ đó như nhau sẽ giữ nguyên lỗ hổng
cho đúng những trace nhiều khả năng có trước thay đổi đã mở nó ra. Giá:
mô phỏng lại kho trace hiện có một lần.

**Đọc metadata không đọc dòng nào.** `read_trace_metadata()` chỉ đọc
footer Parquet — phép kiểm chạy trên mọi trace trước mỗi sweep, đọc cả
episode để trả lời sẽ đắt hơn chính phần mô phỏng nó tiết kiệm.

### Guard chống trôi

`test_run_stack_has_not_grown_a_condition` so chữ ký `run_stack` với
`CONDITION_ARGUMENTS`. Thêm tham số điều kiện thứ sáu **mà không quyết
định** nó có vào hash hay không ⇒ test đỏ. Thêm thì được; thêm mà không
quyết định thì không.

### Một lỗi test bắt được

`test_different_seeds_share_conditions` đỏ ngay lần đầu: hai seed ra hai
fingerprint. Nguyên nhân — `scenario.description` là
`"<profile> · <mission> · seed <n>"`, **mang seed trong đó**. Thiết kế đã
ghi phải loại `description`, code chỉ loại `name` và `random_seed`.

Không có test đó thì fingerprint khác nhau mỗi episode và **vô hiệu hoá
toàn bộ cơ chế reuse** — mọi sweep mô phỏng lại từ đầu, im lặng. Một bản
sửa cho lỗi im lặng, tự nó hỏng im lặng.

---

## 2. Nợ (b) — `angle_span ≠ 2π` làm hỏng mọi candidate `lidar_only`

`LidarConfig` cho khai `angle_span` bất kỳ và simulator **tôn trọng đúng**
(`lidar.py:89`: `increment = angle_span / num_rays`). Nhưng phía tiêu thụ:

| nơi | làm gì |
|---|---|
| `dwa_core.obstacle_points` (`dwa_core.py:216`) | `span = 2.0 * math.pi` |
| clusterer của `dwa_predictive` | `spacing = 2π / rays` |

Cái thứ nhất là của **`dwa` thường**. Deployment khai LiDAR 180° sẽ nhận
scan đúng, rồi controller trải nó ra cả vòng tròn: mọi vật cản đặt sai
phương vị, **không gì báo**.

### Chọn chặn thay vì dạy consumer

Validator trên `LidarConfig` từ chối mọi giá trị ≠ `2π`, thông điệp nói
rõ ai sẽ sai và trỏ L20.

Đây là phán đoán phạm vi, không phải sở thích: truyền đặc tả cảm biến
xuống hai controller chạm planner protocol và golden trajectory của cả
hai — pha riêng. Cho tới lúc đó, trạng thái trung thực là trường này có
**một** giá trị được hỗ trợ, và cách nói ra là từ chối các giá trị khác
chứ không nhận rồi hành xử như chưa từng được hỏi.

---

## 3. Regression bắt được từ task 1

Full suite sau khi rút `dwa_predictive` đỏ hai test API:

```
dwa_predictive_balanced: 422 — 'astar+dwa_predictive' may not be offered as a candidate
```

`GET /local-controllers` vẫn **chào** `dwa_predictive_balanced` trong khi
`POST /candidates` từ chối mọi stack dùng được nó. Catalogue và đường
đăng ký bất nhất — đúng thứ mà việc *serve* catalogue (thay vì hardcode
trong browser) sinh ra để tránh, giờ tự nó gây ra.

**Sửa bằng dẫn xuất, không bằng danh sách thứ hai:**

```python
def offered_controller_configs():
    usable = {info.local_controller for info in list_algorithms() if info.benchmarkable}
    return {c: cfgs for c, cfgs in CONTROLLER_CONFIGS.items() if c in usable}
```

Rút một stack là rút luôn cấu hình của nó trong cùng một động tác, không
ai phải nhớ. `CONTROLLER_CONFIGS` giữ nguyên để run cũ vẫn đọc được.

Test `test_the_matching_configuration_registers_normally` đổi thành
`test_even_the_matching_configuration_is_refused_now`, và **khoá hai lời
từ chối phải khác nhau**: `"perception"` có, `"pairs a"` không — nếu
không, lỗi ghép cấu hình sai sẽ biến mất sau lỗi rút và không ai thấy
nữa.

---

## 3b. Nợ thứ tư, không định trước: một test flaky đã hiệu chuẩn ba lần

Full suite sau task 2+3: **2827 passed, 1 failed** — và lỗi đó không phải
regression.

```
FAILED tests/test_replanning.py::...::test_the_trace_carries_a_replan_row_with_the_planner_time_on_it
```

Bằng chứng nó có sẵn:

| kiểm | kết quả |
|---|---|
| chạy riêng | pass, 3.07 s |
| cả module (35 test) | pass |
| dưới tải 4 process CPU | pass, 5.73 s |
| trong full suite 46 phút | **fail** |
| có đi qua code vừa sửa không | **không** — dựng `EpisodeTraceRecorder` và gọi `run_stack` trực tiếp, fingerprint không được tính trong path này |

Gốc rễ: assertion so **hai phép đo wall-clock** với nhau —
`max(replans) > 2 * typical`, cả hai đều là thời gian trôi thật trên máy
đang tải. Comment của chính test ghi lại **hai lần hiệu chuẩn trước**:
`> 50 ms` cố định (hoá ra là thuộc tính của bản đồ), rồi p99 (thua cuộc
đua giữa hai lần rút mẫu: 12.8 so với 6.2 khi chạy riêng, 15.8 so với
16.0 trong suite), rồi median — sống lâu hơn, rồi hỏng đúng kiểu cũ.

Hiệu chuẩn lần thứ ba là vá triệu chứng lần thứ ba.

**Sửa tất định.** Đại lượng trả lời đúng câu hỏi đã nằm sẵn trong test:
`run.plans[1:]` là các lần replan, và `planning_time_seconds` của chúng
là thứ planner báo đã tiêu — đo độc lập với trace.

```python
replanned = run.plans[1:]
charged_ms = sum(plan.planning_time_seconds for plan in replanned) * 1000.0
assert sum(replans) >= charged_ms
```

Tổng chứ không phải max, vì `pending_replan_ms` cộng dồn rồi xả ở bước
điều khiển kế tiếp: **dòng nào mang lần replan nào là chi tiết hiện
thực; mọi lần replan đều tới được một dòng nào đó mới là hợp đồng.**

Không còn phép đo thứ hai, nên không còn gì để đua.

**Kiểm bằng mutation, vì một test xanh chưa chắc có răng.** Mutation
đầu (`pending_replan_ms += 0.0`) bị giết bởi assertion **khác** ở dòng
499 — sự kiện `replan` không bắn nữa nên không có dòng nào. Chưa chứng
minh được gì về assertion mới. Mutation thứ hai (tính đúng 25% thời gian
planner) giết đúng dòng **533**, tức assertion mới. Có răng.

---

## 4. Đổi gì

| file | việc |
|---|---|
| `packages/benchmark/.../fingerprint.py` | **mới** — hash + `CONDITION_ARGUMENTS` |
| `services/simulator/.../trace.py` | field mới, `read_trace_metadata()`, recorder param |
| `packages/benchmark/.../episode.py` | ghi fingerprint khi tạo trace |
| `packages/benchmark/.../pipeline.py` | `_was_run_under`, `StaleTraceError`, journal truncate |
| `packages/benchmark/.../selection.py` | truyền profile/map vào `paired_prefix` |
| `packages/benchmark/.../candidates.py` | `offered_controller_configs()` |
| `apps/api/.../routers/decisions.py` | catalogue dẫn xuất từ registry |
| `packages/schemas/.../sensor.py` | validator `angle_span` |
| `tests/test_execution_conditions.py` | **mới** — 13 test |
| `tests/api/test_api_decisions.py` | hai test cập nhật |
| `tests/test_replanning.py` | assertion timing đổi sang tất định |
| `docs/KNOWN_LIMITATIONS.md` | L20 chuyển sang **đã sửa** |

---

## 5. Còn lại

Nợ thứ ba (**G5 không đếm bộ nhớ tri giác**, `_tracks` không có trần
tường minh) **chưa làm**. Ưu tiên thấp nhất và gần như moot sau khi rút
candidate — công thức trần chỉ có nghĩa cho một tracker đang chạy.

Hai chỗ vẫn treo, cả hai đã ghi trong tài liệu: **L17** (rollout dùng
pose thật, đám mây điểm dùng pose robot tin là) — điều kiện cần cho mọi
hướng tri giác sau này; và việc truyền `LidarConfig` xuống controller,
tức trả nợ thật của (b) thay vì chặn.
