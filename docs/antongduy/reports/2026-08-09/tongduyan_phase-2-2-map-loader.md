# Báo cáo — Phase 2.2: Map loader PGM/YAML + bản đồ tham chiếu

> **Ngày:** 2026-08-09
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **2.2**
> **Nhánh:** `plannerselector_p2`
> **Phạm vi:** 2.2 + một bản đồ tham chiếu thật (phát sinh, xem mục 3).
> **Contract:** không đổi — vẫn `2.0.0`.

---

## 1. Trạng thái trước khi làm

`packages/schemas/planbench_schemas/map_io.py` **đã có** từ Phase 1A: parse P5/P2
PGM + YAML sidecar, đúng công thức pixel → occupancy của `map_server`. Nhưng nó
nhận **bytes/text**, không nhận đường dẫn — và `grep` cho thấy nó chỉ có test gọi,
không có một chỗ nào trong repo dùng thật.

Nên khoảng trống của 2.2 không phải "viết parser" mà là:

1. `TaskProfile.environment` khai hai **đường dẫn** (`map`, `map_yaml`) mà không ai
   biến chúng thành `MapData`;
2. repo **không có một file `.pgm` nào** — nghĩa là chưa từng có bản đồ thật nào
   được nạp, và câu "chặn mọi demo" trong backlog đúng theo nghĩa đen.

## 2. Việc đã làm

### 2.1. `packages/benchmark/planbench_benchmark/task_map.py` (mới)

Đặt ở benchmark (`runner/` theo §16) vì nó là tầng duy nhất biết **cả** task
profile **và** filesystem; `schemas` giữ nguyên tính chất không đụng đĩa.

**Nạp.** `load_environment_map(env, base_dir=...)` → `MapData`.
`base_dir` để profile viết đường dẫn tương đối vẫn có nghĩa cố định — nếu không
thì cùng một profile chạy từ hai thư mục khác nhau lại trỏ hai bản đồ khác nhau.

**Cache theo (đường dẫn + size + mtime).** Một bộ evaluation là 300+ episode trên
một bản đồ; parse lại 400.000 pixel mỗi episode là vài phút vứt đi. Có mtime trong
key nên sửa bản đồ thì cache tự hỏng — một phiên dài không được tiếp tục plan trên
bức tường của bản trước. Đo: **63 ms** lần đầu, **0,24 ms** khi hit.

**Kiểm `image:` của sidecar.** YAML của `map_server` tự khai tên file ảnh của nó.
Profile trỏ `warehouse_a.pgm` nằm cạnh một YAML khai `warehouse_b.pgm` sẽ nạp
**trót lọt**: pixel lấy từ A, còn resolution/origin/threshold lấy từ B. Mọi toạ độ
trong run lệch đi theo origin của B và **không có gì trông sai**. Giờ bị từ chối.

### 2.2. Từ chối profile mà bản đồ mâu thuẫn — phần đáng giá nhất

`validate_missions_on_map()` bắt 5 kiểu bất đồng, tất cả đều **ra số chứ không ra
lỗi** nếu để yên:

| # | Bất đồng | Nếu để yên thì thấy gì |
|---|---|---|
| 1 | pose ngoài bản đồ | robot xuất phát ở hư không |
| 2 | pose trên ô occupied/unknown | start = va chạm tức thì; goal = đích không tới được |
| 3 | tâm robot lọt nhưng **robot** không lọt | no_path của candidate, thực ra là của profile |
| 4 | **không có tuyến nào** từ start tới goal với robot bán kính này | mọi candidate no_path, G1 loại sạch cả bảng vì một tính chất của bản đồ |
| 5 | start nằm trong goal tolerance của goal | episode success ở t = 0, đo được đúng số 0 |

Điểm cần nói rõ: mọi kiểm tra phát biểu theo **bán kính robot**, không theo điểm
tâm. Một goal cách tường 3 cm là tới được với một điểm và không tới được với robot
0,26 m — và chính khác biệt đó quyết định `no_path_rate` của G1 là sự thật về
candidate hay về profile.

Kiểm 3 và 4 dùng chung một phép tính: **không gian tự do bị co lại theo bán kính
robot** (`scipy.ndimage.binary_dilation` trên mask blocked, đệm biên = blocked vì
mép bản đồ là tường). Mask đó chính là chỗ robot có thể đứng, nên "robot lọt
không" là một phép tra, "có tuyến không" là hai pose có cùng connected component
không (`ndimage.label`). Đo trên bản đồ 400k ô: **21 ms**. (Đường khác — gọi
`OccupancyGrid.inflate()` sẵn có — mất **5,8 s**, không dùng.)

Mọi vấn đề gom lại báo **một lần**, không dừng ở lỗi đầu: sửa profile theo kiểu
mỗi lần chạy phát hiện một lỗi là cách tiêu cả buổi cho một bản đồ vốn không bao
giờ chạy được.

### 2.3. Siết hai trường YAML âm thầm đổi nghĩa bản đồ (`map_io.py`)

- **`mode`.** `map_server` có `trinary | scale | raw`; loader cũ **bỏ qua** trường
  này. Với `scale`, một pixel xám giữa là ô **bị chiếm một phần**, không phải ô
  unknown — đọc bản đồ scale như trinary biến một hành lang đầy đồ lộn xộn màu
  xám nhạt thành sàn trống, và mọi candidate cùng plan xuyên qua nó. Giờ chỉ nhận
  `trinary`, các mode khác **từ chối** chứ không xấp xỉ.
- **`free_thresh` ≥ `occupied_thresh`.** Đảo thứ tự thì mọi pixel rơi vào dải giữa,
  cả bản đồ đọc thành UNKNOWN, và (với `unknown_as_occupied`) thành một khối tường
  đặc cho mọi candidate `no_path` như nhau. Giờ từ chối tại chỗ parse.

### 2.4. Vector hoá `_pixels_to_cells`

Vòng lặp Python trên 400.000 pixel chạy mỗi lần nạp bản đồ. Đổi sang numpy, giữ
nguyên `_pixel_to_cell` làm phát biểu đọc được của quy tắc (và là thứ test ghim).

## 3. Phát sinh: bản đồ tham chiếu `maps/warehouse_a.{pgm,yaml}`

Contract HĐ-2.1 và §6.2 của tài liệu đề tài đều viện dẫn **một** deployment cụ thể:
kho 40 × 25 m ở 0,05 m, khe kệ hẹp nhất 0,68 m, robot rộng 0,52 m. Mọi con số phía
sau dựa vào nó — ước lượng bộ nhớ HĐ-7.3 giả định 400.000 ô, G1 giả định lối đi
thật sự đi được. Bản đồ đó **phải tồn tại**, không thể chỉ được mô tả.

Làm theo kiểu **script sinh + asset commit**: `scripts/make_warehouse_map.py` là chỗ
các bức tường kiểm được bằng mắt, `maps/warehouse_a.pgm` là thứ loader đọc (không
cần bước build). Có test khẳng định hai thứ **không trôi khỏi nhau** — nếu trôi
thì bản đồ đang được benchmark không còn là bản đồ đã được mô tả.

Kết quả sinh: 800 × 500 px = **400.000 ô đúng như contract**, 30,6% occupied
(tường biên + 2 dãy × 4 khối kệ, khe 0,68 m giữa các khối, hành lang ngang 3 m).

**Kiểm chứng bản đồ dùng được thật** — chạy A\* trên grid đã inflate
(0,26 + √2 × 0,05):

```
success=True  path_length=46.1 m  expanded_nodes=115241  t=4.16 s
```

Hai điều rút ra:

1. `peak_search_nodes` (115.241) **≤** `costmap_cells` (400.000) — đúng tiêu chí
   nghiệm thu HĐ-15.1 #6, lần đầu kiểm được trên bản đồ thật.
2. **4,16 s cho một lần plan.** Con số này mâu thuẫn với giả định "1.000
   episode/phút" ở N9 của tài liệu đề tài — giả định đó tính cho scenario 2D nhỏ,
   không phải cho A\* trên 400k ô bằng Python. Ở quy mô MVP (2 candidate × 300
   episode) đây là **~40 phút chỉ riêng phần global planning**. Chưa sửa gì; ghi
   lại vì nó đụng thẳng vào điều kiện kích hoạt của N9 (racing/successive halving)
   và cần được cân lại ở Phase 5.1 khi chốt N thật. Không phải việc của 2.2.

## 4. Test

| File | Thêm | Nội dung |
|---|---|---|
| `tests/test_task_map.py` (mới) | **21** | nạp bản đồ tham chiếu · base_dir · thiếu file (nêu đúng tên trường) · cache hit + invalidate khi sửa file · sidecar khai sai ảnh · 5 luật mission/map · gom nhiều lỗi một lần · asset khớp generator |
| `tests/test_map_io.py` | **+4** | `mode: scale` bị từ chối · `mode: trinary` được nhận · mode lạ · threshold đảo |

Hai test đáng nói:

- **`test_goal_walled_off_from_the_start`** dựng một bản đồ 4 × 2 m có cửa 0,30 m:
  tuyến tồn tại cho một điểm, không tồn tại cho robot 0,26 m. Đây đúng ca mà kiểm
  tra theo tâm robot sẽ cho qua.
- **`test_reference_map_is_actually_traversable`** — thứ làm cho việc commit asset
  có nghĩa: lối đi của `warehouse_a` nối được start tới goal cho robot này.

Full suite: `pytest tests/ -q` → **1638 passed, 6 skipped** (12 phút 44). Baseline
sau Phase 2.1 là 1613 — thêm đúng 25 test (21 + 4), **không vỡ test nào**.
`ruff check` và `ruff format --check` sạch trên toàn repo.

## 5. Chưa làm — cố ý

- **Chưa nối vào runner/`run_stack()`.** 2.2 cho ra bản đồ; đường dây chạy thật
  vẫn là việc của lát cắt dọc (Phase 4).
- **Chưa hỗ trợ PNG** — giữ nguyên giới hạn đã ghi từ Phase 1A (cần Pillow).
- **Chưa hỗ trợ `mode: scale`/`raw`** — từ chối có thông báo rõ, thêm khi có bản
  đồ thật cần tới.
- **Chưa có bản đồ thứ hai.** Neighborhood (N5, Phase 5) sẽ cần biến thể; sinh
  biến thể là việc của Perturbation Generator, không phải của loader.

## 6. Trạng thái Phase 2

| Mục | Trạng thái |
|---|---|
| 2.1 TraceRecorder Parquet (HĐ-5) | ✅ |
| 2.2 Map loader PGM/YAML | ✅ + bản đồ tham chiếu chạy được |
| 2.3 `metrics/definitions.py` | chưa — giờ đã đủ đầu vào (trace + bản đồ thật cho `L_ref` Dijkstra) |
