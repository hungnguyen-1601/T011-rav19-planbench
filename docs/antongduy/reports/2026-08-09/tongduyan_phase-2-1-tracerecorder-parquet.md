# Báo cáo — Phase 2.1: TraceRecorder Parquet (HĐ-5) + hợp nhất contract 2.0.0

> **Ngày:** 2026-08-09
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **2.1**
> **Nhánh:** `plannerselector_p2`
> **Phạm vi:** 2.1 + một việc chặn đường phát sinh (contract phân kỳ) + phần code phải theo hợp đồng mới.
> **Kết quả:** trace schema (khóa cứng #3) đã hiện thực và đóng băng. `contracts_version` 1.1.0 → **2.0.0**.
> **Test:** `pytest tests/ -q` → **1613 passed, 6 skipped** (baseline sau Phase 1.4: 1575) — không vỡ test nào.

---

## 1. Việc chặn đường phát hiện trước khi viết dòng code đầu

`contracts/CONTRACTS.md` trong working tree **không phải** bản 1.1.0 đã commit ở
HEAD. Hai bản phân kỳ, mỗi bản có thứ bản kia không có:

| | HEAD 1.1.0 (đã commit, Phase 1) | Working tree (chưa commit, tự khai 2.0.0) |
|---|---|---|
| `dynamic_obstacles` HĐ-2.3, HĐ-7.0 từ vựng quan sát, bảo lưu sim-only, §18, §16 bảng ánh xạ | có | **mất** |
| G5 rework: `resource_profile`, `memory_estimate_mb`, `peak_rss_mb` xuống Diagnostic | không | có |
| **HĐ-5 metadata** | 8 trường | **11 trường** (thêm `peak_search_nodes`, `peak_tree_nodes`, `costmap_cells`) |

`pytest tests/test_contract_version.py` khi đó **3 failed** — đúng cái mà 4 test
version của Phase 1.4 sinh ra để bắt.

Điểm khiến nó chặn 2.1 chứ không phải một việc dọn dẹp: **hai bản khai HĐ-5 khác
nhau**, mà HĐ-5 là schema mà 2.1 hiện thực và là một trong ba thứ §0 cấm đổi.
Ghi theo bản hẹp rồi sau phải thêm 3 trường = mọi trace đã ghi mồ côi + chạy lại
toàn bộ evaluation set.

**User chốt hướng hợp nhất.** Lấy HEAD 1.1.0 làm nền (giữ toàn bộ Phase 1), áp
phần G5 rework lên trên, bump **2.0.0**.

## 2. Contract 2.0.0 — nội dung hợp nhất

| # | Mục | Loại | Nội dung |
|---|---|---|---|
| 1 | **HĐ-7.3 viết lại** | **MAJOR** | G5 bỏ `peak_rss_mb ≤ available_ram_mb`, thay bằng `memory_estimate_mb` tính từ số lượng cấu trúc dữ liệu. Kèm bảng hai pha riêng của G5 |
| 2 | **HĐ-1.5 mới** | thêm trường bắt buộc | `resource_profile`: `structural` (khai `bytes_per_*` theo hiện thực đích) hoặc `artifact` (model + runtime) |
| 3 | **HĐ-2.4 mới** | thêm trường bắt buộc | `available_ram_mb` phải kèm `total_ram_mb` + `ram_budget_breakdown`, validator kiểm tổng |
| 4 | **HĐ-5** | thêm 3 metadata | `peak_search_nodes`, `peak_tree_nodes`, `costmap_cells` |
| 5 | Kéo theo | — | HĐ-6, bảng cổng HĐ-7, anchor HĐ-8, `U_C` HĐ-9, khối `G5` của card HĐ-12, tiêu chí nghiệm thu thứ 6 ở HĐ-15.1, §17 cấm 13–14 |

Ba thứ của 1.1.0 được giữ nguyên vẹn: `dynamic_obstacles` + luật
`seed_time_offset > 0`, HĐ-7.0, bảo lưu sim-only, §16 bảng ánh xạ, §18.

**Hai chỗ tôi viết thêm khi hợp nhất, không có ở bản nào:**

1. **`resource_profile` không vào `candidate_id`** (ghi vào HĐ-1.5). Bản 2.0.0 gốc
   không nói. Nếu hash nó thì sửa một con số kế toán bộ nhớ sẽ tách một candidate
   đã chạy 300 episode thành hai candidate mồ côi — trong khi robot chạy y hệt.
   Đây là loại lỗi mà 1.3 đóng băng để chống, nên phải nói thẳng chứ không để suy.
2. **Bảo lưu sim-only áp cho cả G5** (ghi vào HĐ-7.3). Bảng của bản 2.0.0 có dòng
   `memory_gate.status: verified_on_target`, mâu thuẫn với bảo lưu 1.1.0 rằng dự án
   không có bo mạch đích. Không nối hai chỗ này thì §17 cấm số 12 (`verified_on_target`)
   chỉ chặn G4, còn G5 lọt.

**Về việc đụng HĐ-5 — schema đã đóng băng.** Ghi thẳng lý do vào §18: chưa có
file trace nào tồn tại (TraceRecorder chính là việc đang làm), `artifacts/runs/`
rỗng. Đây là thời điểm cuối cùng thay đổi này còn miễn phí. Các **cột** không
đổi; chỉ metadata được thêm.

Chữ ký: đã ký 1 (Dev B). Vẫn **chưa đủ 2** theo mục 0, và 2.0.0 là MAJOR nên còn
nợ nghĩa vụ chạy lại lát cắt dọc — lát cắt dọc chưa tồn tại (Phase 4), nghĩa vụ
rơi vào lần đầu chạy nó. Đã ghi vào chỗ ký.

## 3. Code phải theo hợp đồng mới (điều kiện để 2.0.0 không chỉ là chữ)

Không làm phần này thì contract khai "BẮT BUỘC" cho những trường loader **bỏ qua
trong im lặng** — đúng loại trôi mà cả đề tài tồn tại để chống.

- `HardwareSpec` (HĐ-2.4): thêm `total_ram_mb` + `RamBudgetItem` (4 khoản, `extra="forbid"`),
  validator `|total − Σbreakdown − available| ≤ 1% total`. Dung sai 1% cho ngân sách
  viết tay bằng MB tròn; hẹp hơn thì không đủ để nuốt một khoản bị quên.
- `Candidate.resource_profile` (HĐ-1.5): discriminated union theo `kind`, **bắt buộc**.
  Luật hình dạng: `modular ⇒ structural`, `monolithic ⇒ artifact`. Lý do không cho tự do:
  planner cổ điển thì sim **đếm được** — cho khai số thay cho đếm là bỏ một phép đo
  đang có; policy học máy thì sim **không đếm được** — `bytes_per_node` không làm ra
  con số đó. Hybrid (modular có tầng học máy) sẽ phải sửa hợp đồng, cố ý.
- `candidates.py`: `DEFAULT_STRUCTURAL_PROFILE` (cpp_ros2, 40/40/1/3/8 theo ví dụ contract)
  cho mọi stack registry, có tham số để ghi đè.
- `CONTRACTS_VERSION = "2.0.0"`; 4 test version của Phase 1.4 xanh lại.

## 4. Phase 2.1 — TraceRecorder

`services/simulator/planbench_simulator/trace.py` (mới, ~430 dòng kể cả docstring).
Đặt ở sim theo §16 (sim giữ HĐ-4, HĐ-5); `packages/metrics` đã import
`planbench_simulator` sẵn nên 2.3 đọc trace không tạo vòng import.

### 4.1. Đúng schema HĐ-5

`TRACE_SCHEMA` khai **tường minh** bằng pyarrow chứ không để suy từ dữ liệu. Suy
kiểu là bẫy: một episode mà `event` toàn null sẽ ra cột kiểu `null`, một episode
mà `t` toàn số nguyên ra `int64` — hai file của **cùng một bộ episode** khác kiểu
nhau và không concat được. Đúng loại vỡ âm thầm mà schema đóng băng sinh ra để chặn.

Metadata (11 trường HĐ-5) đi trong **footer Parquet** dạng JSON, không lặp xuống
từng dòng: nó là một giá trị cho cả episode, lặp xuống dòng là mở cửa cho một file
mà các dòng bất đồng ý về việc candidate nào đã chạy. Đọc lại bằng `read_trace()`;
file không có khối metadata bị **từ chối** chứ không mặc định — trace không biết
candidate nào thì không ghép cặp được, và đoán theo tên thư mục sẽ làm một file
đặt nhầm chỗ trông vẫn hợp lệ.

### 4.2. `clearance_m` tính lúc ghi — điểm thiết kế chính

Có mỗi quỹ đạo thì **không ai** dựng lại được xe nâng ở đâu lúc t = 7,4 s: vật cản
động đã đi tiếp, muốn biết phải phát lại toàn bộ trạng thái ngẫu nhiên của episode.
Nên recorder nhận một callable `clearance` và gọi nó ở mỗi mẫu — đúng khoảnh khắc
duy nhất câu trả lời còn tồn tại. Đây cũng là lý do `min_clearance` và
`near_miss_rate` (HĐ-6) sau này là hàm thuần của file.

`clearance_probe(grid, static_obstacles, robot_radius, dynamic_obstacles_now)`:
nửa tĩnh đóng gói một lần, nửa động là **callable** (thường là
`engine.dynamic_obstacles_now`) gọi lại mỗi mẫu — chụp snapshot một lần thì cả
episode báo cùng một con số và near-miss đo rỗng. Có test riêng cho đúng điểm này.

Grid là tham số bắt buộc chứ không optional: nó là thứ giữ giá trị **hữu hạn**.
Không vật cản nào thì clearance tới một tập rỗng là vô cực, và một `inf` trong cột
sẽ phá mọi phân vị tính từ file; có grid thì biên bản đồ luôn trả lời.

Ghi chú lớp quan sát: probe đọc ground truth, nhưng đây là **phép đo, không phải
tri giác** — không gì nó thấy đi tới planner, nên khai báo P02/G6 không bị đụng.

### 4.3. Từ chối tại chỗ ghi

Mỗi thứ dưới đây sống sót qua một lần chạy trong im lặng và chỉ lộ ra thành một
con số lạ trên Decision Card vài tuần sau, lúc episode sinh ra nó đã mất:

| Từ chối | Vì sao |
|---|---|
| `t` không tăng | mọi rate và phân vị tính từ file sai theo |
| event ngoài từ vựng HĐ-5 | consumer switch theo giá trị sẽ rơi vào nhánh default và đếm episode thành thứ khác |
| giá trị không hữu hạn (NaN/inf) | lan vào mọi tổng hợp |
| trace rỗng | file rỗng vẫn được đếm là **một quan sát ghép cặp**; thiếu file an toàn hơn |
| ghi sau `close()` / `close()` hai lần | file trên đĩa và bộ nhớ bất đồng |
| không có probe lẫn `clearance_m` | xem 4.2 — không lấy lại được sau |

### 4.4. Những thứ nhỏ nhưng có lý do

- **Context manager ghi cả khi episode ném exception.** 400 mẫu của một episode
  crash là bằng chứng; file thiếu là một lỗ hổng trong phép so ghép cặp.
- **Đường dẫn `artifacts/runs/<candidate_id>/<episode_context_id>.parquet`** —
  luật ghép cặp HĐ-3.2 nhìn thấy được bằng `ls`: hai candidate chạy cùng tập
  context cho hai thư mục **cùng danh sách tên file**.
- **`peak_search_nodes` / `peak_tree_nodes` truyền lúc `close()`**, không phải
  `__init__`: chúng là đỉnh, chỉ biết khi episode xong.
- **`peak_rss_mb` đo không cần thêm dependency** — `/proc/self/statm` trên Linux,
  `GetProcessMemoryInfo` qua ctypes trên Windows, `getrusage` cho phần còn lại;
  không đo được thì trả 0.0 chứ không ném (một chỉ số chẩn đoán không được phép
  làm hỏng episode). Bẫy Windows đã dính và đã sửa: không khai
  `GetCurrentProcess.restype = c_void_p` thì pseudo-handle `-1` bị cắt còn 32 bit,
  hàm fail âm thầm và **mọi trace báo 0 MB**.
- **`event_for_status()`**: `NO_PROGRESS` → `stuck` (HĐ-5 và `failure_reason` HĐ-6
  chỉ có một ô cho cả hai); `STOPPED`/`RUNNING` → `None`, vì episode bị người vận
  hành dừng không phải là thất bại của candidate.

### 4.5. Test — `tests/test_trace.py` (27 test)

Round-trip · đường dẫn ghép cặp · context manager (cả đường exception) ·
9 ca từ chối · probe đọc vật cản động đúng thời điểm · từ vựng event ·
metadata (`sample_set` `neighborhood` phải sống sót — gộp nó vào cận trên va chạm
là vi phạm HĐ-11.4).

Test cuối là **một episode thật**: `SimulationEngine` chạy tới đích, ghi trace,
rồi tính lại quãng đường, min clearance, p-latency, event kết thúc **chỉ từ file
đọc lên** — đúng câu hỏi HĐ-6 sẽ hỏi. Kèm assert tiêu chí HĐ-15.1 #6
(`peak_search_nodes ≤ costmap_cells`).

`pyarrow==25.0.0` vào `requirements.txt` (không phải optional: thiếu nó thì không
episode nào ghi được bằng chứng).

## 5. Chưa làm — cố ý

- **Chưa nối TraceRecorder vào batch runner / `run_stack()`.** 2.1 là schema +
  recorder; đường dây chạy thật là việc của lát cắt dọc (Phase 4), lúc đã có
  `definitions.py` để nghiệm thu bằng số chứ không bằng mắt.
- **Chưa có bộ đếm `peak_search_nodes` / `peak_tree_nodes` thật trong planner.**
  Recorder nhận chúng qua tham số; A\* hiện có `expanded_nodes`, RRT\* có số node
  cây — nối vào là việc của 2.3/Phase 4. Ghi lại để không rơi.
- **`memory_estimate_mb`** (công thức HĐ-7.3) chưa viết: nó là metric, chỗ của nó
  là `metrics/definitions.py` (2.3), không phải recorder.

## 6. Trạng thái Phase 2

| Mục | Trạng thái |
|---|---|
| 2.1 TraceRecorder Parquet (HĐ-5) | ✅ — khóa cứng #3 đóng băng |
| 2.2 Map loader PGM/YAML | chưa — song song được |
| 2.3 `metrics/definitions.py` | chưa — giờ đã có input (trace) để bắt đầu |

Ba khóa cứng của §0 giờ đủ cả ba: `candidate_id` (1.2), `episode_context_id` (1.3),
trace schema (2.1). Từ đây, đổi bất kỳ cái nào = MAJOR + chạy lại dữ liệu đã ghi.
