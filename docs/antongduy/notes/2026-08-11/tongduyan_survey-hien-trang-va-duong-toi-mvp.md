# Survey: dự án đã đúng hướng chưa, đang có gì, và còn thiếu gì để có MVP

> **Ngày:** 2026-08-11 · **Loại:** khảo sát hiện trạng, **không đổi một dòng code nào**
> **Yêu cầu nguồn:** An — *"dự án đã theo đúng định hướng xây dựng mô phỏng chưa? Hiện có gì,
> thiếu gì để có MVP đầu tiên?"*
> **Bám theo:** `plans/2026-08-11/nen-tang-cong-bang-truoc-thuat-toan.md` (F0–F5) và định hướng
> gốc do dev phát biểu: *"một môi trường benchmark công bằng cho mọi thuật toán, để xem trong
> một điều kiện cụ thể thuật toán nào tối ưu — không sửa simulator cho thuật toán chạy qua."*
> **Cách kiểm:** đọc code và chạy đếm thật (`pytest --collect-only`, `ls`, `grep`), không dựa
> vào báo cáo cũ.

---

## 1. Trả lời ngắn

**Đã đúng hướng — nhưng mới đúng lại từ hôm nay, và cần nói rõ điều đó.**

Ba tuần trước hôm nay, dự án chạy theo mục tiêu *"lát cắt dọc phải ra được Decision Card"*.
Đó là một mục tiêu khác, và nó dẫn tới việc chỉnh đầu vào cho tới khi card ra. Hôm nay, sau
lượt F0, thứ tự đã đảo lại: **phép đo phải tự đứng vững trước, phép so đến sau.**

Bằng chứng cho "đúng hướng" không phải lời hứa mà là ba thứ có thể kiểm trong 30 giây:

| Bằng chứng | Kiểm ở đâu |
|---|---|
| **60 test công bằng**, khoá cả tầng chấm điểm lẫn tầng thế giới | `tests/test_fairness.py` (22) + `tests/test_simulator_fairness.py` (38) |
| **Công bằng là điều khoản hợp đồng**, không phải thói quen tốt | CONTRACTS HĐ-15.1 tiêu chí **7**, HĐ-15.3 câu hỏi bắt buộc |
| **Artifact của phép đo tách khỏi artifact của phép so** | `measurement_report.json` vs `decision_card.json` |

Điểm quan trọng nhất và cũng dễ bỏ sót nhất: **bốn chỗ lệch tìm được hôm 08-11 không cái nào
thiên vị candidate nào.** Chúng nới đều cho cả hai bên, nên 60 test đối xứng đều xanh với
chúng. Chúng không phá *tính công bằng*; chúng phá *tính đúng đắn* — hệ so đúng luật, nhưng so
trong một thế giới đã nới cho vừa thứ code làm nổi. Đó là lý do HĐ-15.3 phải thêm câu hỏi thứ
hai (*"con số này đến từ hiện trường, hay từ thứ máy tôi chạy nổi?"*): câu hỏi cũ không bắt
được loại này.

---

## 2. Đang có gì — kiểm kê theo tầng

### 2.1. Tầng mô phỏng (cái dự án gọi là "môi trường")

| Thành phần | File | Trạng thái |
|---|---|---|
| Engine thời gian liên tục, kinematics vi sai | `services/simulator/.../engine.py`, `kinematics.py` | ✅ |
| LiDAR 2D | `lidar.py` | ✅ — **tất định, không có mô hình nhiễu** (ghi rõ trong docstring) |
| Va chạm + clearance từ mặt robot | `collision.py` | ✅ |
| Lưới chiếm dụng + inflate | `grid.py` | ✅ |
| Nav stack (global + local + replan) | `nav_stack.py` | ✅ — kèm một đặc quyền thông tin đã biết (mục 4.3) |
| Vật cản động theo hàm đóng `(t, seed)` | `planbench_schemas/dynamic.py` | ✅ |
| Ghi trace Parquet | `trace.py` | ✅ |
| Nạp map PGM/YAML chuẩn `map_server` | `planbench_schemas/map_io.py` | ✅ |

**Sáu bất biến công bằng của thế giới đều được giữ bằng cấu trúc, không bằng quy ước.** Điểm
tựa là một dòng: `scenario_for(profile, context)` **không nhận candidate**. Thế giới là hàm
thuần của `(deployment, episode)`. Có test kiểm **chữ ký hàm**, không chỉ hành vi — vì tham số
`candidate` chính là thứ người ta thêm vào khi một planner cần "chỉ một gợi ý nhỏ".

### 2.2. Tầng thuật toán (cái được đem ra đo)

| Stack | Loại | Chạy được? |
|---|---|---|
| `astar+dwa` | modular | ✅ |
| `rrtstar+dwa` | modular | ✅ |
| `astar+ppo` | modular (PPO bám đường) | ✅ (chưa từng đưa vào phép so nào) |
| `astar+pure_pursuit`, `rrtstar+pure_pursuit` | reference-only | ⛔ `benchmarkable=False` theo thiết kế |
| Candidate `monolithic` (policy end-to-end) | — | ⛔ **chưa có adapter `MonolithicPolicy`** |

Local controller thật sự chỉ có **một** (DWA), nay có hai cấu hình đã đăng ký:
`dwa_coarse` (7×15) và `dwa_default` (20×40), hai `candidate_id` khác nhau.

**Nhận xét thẳng: tầng nền đo đang mạnh hơn hẳn tầng thuật toán.** Hai global planner, một local
controller. Đó đúng theo kế hoạch (nền trước, thuật toán sau) nhưng phải nhớ rằng "công bằng cho
mọi thuật toán" hiện mới được chứng minh trên một họ thuật toán rất hẹp.

### 2.3. Tầng đo và tầng quyết định

| Thành phần | Trạng thái | Ghi chú |
|---|---|---|
| `metrics/definitions.py` — nơi **duy nhất** định nghĩa metric HĐ-6 | ✅ | `L_ref` vừa được sửa từ +2,41% xuống +0,0027% |
| Gates G1–G6 | ✅ | ngưỡng đọc từ profile, không hardcode |
| Anchors + `u()` | ✅ | `metric_anchors.yaml` có version |
| 4 objective + `decision_utility` | ✅ | per-episode và per-set |
| Paired bootstrap ΔU + nhãn | ✅ | |
| Pareto non-inferiority | ✅ | |
| Sensitivity (trọng số + anchor ±10%) | ✅ | |
| Decision Card + Manifest + schema JSON | ✅ | |
| **Measurement Report** (một candidate) | ✅ **mới** | `scripts/measure.py` |
| Ghi máy đo thật vào manifest | ✅ **mới** | affinity + cảnh báo không ghim |

### 2.4. Hạ tầng phía trên

| | Trạng thái |
|---|---|
| Bảng DB `task_profiles` / `candidates` / `decision_cards` | ✅ migration `0005_decision_layer` |
| Router `/decisions`, `/task-profiles`, `/candidates` | ⛔ **chưa có** (routers hiện có: benchmarks, scenarios, maps, algorithms, …) |
| Trang web `/decisions` | ⛔ **chưa có** (`apps/web/src/app` có leaderboard, simulate, scenarios, …) |
| RBAC + Approval + Docker + OAuth | ✅ từ trước, không đụng tới |

### 2.5. Tài sản để chạy

| | |
|---|---|
| Deployment | `warehouse_a_v2` (kho, có traffic), `open_hall_v1` (sảnh đối xứng, không traffic) |
| Map | `warehouse_a.{pgm,yaml}`, `open_hall.{pgm,yaml}` — cái sau sinh lại được bằng script và **có test khẳng định đối xứng** |
| Kết quả đã lưu | `artifacts/runs/2026-08-11/open_hall_v1_db26440f6052/measurement_report.json` (mới, hợp lệ) · `artifacts/runs/2026-08-11/b60dbd94882d/` (card cũ — **trace đã mồ côi**) |
| Suite | **2084 passed, 6 skipped** |

---

## 3. MVP — phải phân biệt hai cái, nếu không sẽ tự lừa mình

Từ "MVP" trong dự án này đang chỉ hai thứ khác nhau. Trả lời gộp sẽ ra một câu sai.

### MVP-A — *"đo được một thuật toán trên một map, trả về thông số quan trọng"*

Đây là MVP mà dev đã chốt ở plan F1. **Đã xong hôm nay.**

```
profile open_hall_v1 · rrtstar+dwa · dwa_coarse · 30 episode
  ✓ L_ref ≤ path_length + tolerance (30/30)
  ✓ decision_utility tái lập tới 6 chữ số (0.845397)
  ✓ bảng cổng đủ 6 cổng
  ✓ peak_search_nodes ≤ costmap_cells
30 chạy, 30 phân biệt · success 100% · p99 gộp 18,76 ms (ngưỡng 50) · G1–G6 pass
```

Bốn tiêu chí nghiệm thu xanh, sáu cổng xanh, report ghi ra đĩa, 18 test khoá.

### MVP-B — *"một phép so công bằng đầu tiên giữa hai thuật toán"*

**Chưa có, và chưa từng có.** Mọi Decision Card đang tồn tại trong repo đều được sinh **trước**
lượt F0, tức dưới bốn chỗ lệch đã sửa; trace của chúng nay mồ côi vì `candidate_id` đổi.

Đây mới là thứ trả lời được câu hỏi của đề tài (*"thuật toán nào tối ưu trong điều kiện này"*),
nên phần còn lại của survey này nói về nó.

---

## 4. Thiếu gì để có MVP-B

### 4.1. Chặn cứng: simulator không có nguồn ngẫu nhiên theo bước *(plan F3)*

Đây là **cái duy nhất thực sự chặn**, và nó chặn theo một đường không hiển nhiên.

Simulator hiện tất định hoàn toàn. Nguồn phụ thuộc seed chỉ có hai: pha vật cản động
(`seed_time_offset`), và bản thân planner nếu nó ngẫu nhiên. Hệ quả dây chuyền:

```
A* tất định + traffic không cắt tuyến  ⇒  mọi seed cho CÙNG một episode
                                       ⇒  n_distinct = 1
                                       ⇒  G2 từ chối (đúng luật, mới sửa ở 6.0.0)
                                       ⇒  A* bị loại ở cổng
                                       ⇒  chỉ còn 1 candidate qua cổng
                                       ⇒  không có ΔU, không có card
```

`open_hall_v1` **cố ý không có traffic** (nó là dụng cụ đo tính đối xứng, không phải deployment
thật), nên trên đó A\* chắc chắn vướng dây chuyền này.

Còn trên kho: Phase 5.1 đo được `n_distinct = 1/100` cho A\* với `seed_time_offset = 6 s`. Offset
đã sửa thành 24 s (trọn chu kỳ), nhưng **profile mới chưa từng được chạy** — nên `n_distinct` của
A\* trên kho hiện là một **ẩn số**, không phải một điều đã biết. Đây là chỗ dễ tưởng nhầm là đã
giải quyết.

Nhiễu cảm biến/odometry theo seed sửa cả hai trường hợp cùng lúc, và quan trọng hơn, nó sửa một
chỗ **simulator đang lạc quan hơn thực tế** — robot thật không bao giờ chạy hai lần giống hệt.
Kế hoạch chi tiết đã có sẵn: `plans/2026-08-11/nhieu-cam-bien-theo-seed.md`.

> **Cách đọc nó, và điều này quan trọng:** nếu bán F3 như *"cách để có bộ evaluation dùng
> được"* thì đó là lặp lại đúng sai lầm đã dọn hôm nay. F3 là **sửa độ trung thực của
> simulator**, và nhiều khả năng làm mọi con số **xấu đi**. Đó là dấu hiệu nó đúng.

**Ước lượng:** ~1 ngày. **Rủi ro:** phải đi qua bất biến 3 — generator riêng, seed từ
`EpisodeContext`, nhiễu vào *phép đo* chứ không vào *sự thật* (va chạm vẫn phán quyết trên pose
thật). Hai test `test_a_planners_draws_cannot_move_the_world` và
`test_planning_leaves_the_global_streams_untouched` phải chạy **trong lúc** làm, không phải sau.

### 4.2. Thiếu công cụ: chưa có runner cho phép so tuỳ ý *(chưa có trong plan)*

`scripts/measure.py` chạy **đúng một** candidate. `scripts/vertical_slice.py` chạy **đúng hai**
stack hardcode (`astar+dwa`, `rrtstar+dwa`) với `dwa_coarse` hardcode — nó nhận `--profile`
nhưng không nhận danh sách candidate.

F4.2 của plan cần ma trận 2 global × 2 local = 4 candidate. Không chạy được bằng công cụ hiện
có. Cần `--candidates` / `--local` cho `vertical_slice.py`, hoặc một `compare.py` dùng chung
tầng với `measure.py`.

**Ước lượng:** ~2 giờ. Không khó, nhưng chưa ai viết, và nó đứng chắn giữa F4.1 và F4.2.

### 4.3. Nợ đã biết, chưa chặn MVP-B nhưng phải nhớ

| # | Món nợ | Khi nào cắn |
|---|---|---|
| 1 | **Ghim nhân là quy trình vận hành**, không cưỡng chế bằng code | Ngay khi ai đó quên. G4 đọc đồng hồ tường; cùng candidate đo 59,30 ms không ghim và 16,10 ms có ghim. Giờ ít nhất được **ghi lại và cảnh báo** (F0.5), nhưng cảnh báo không phải hàng rào |
| 2 | **Lưới replan thấy vật cản thật** (`nav_stack.py:166`) | Ngày có candidate `monolithic`. Đã ghi thành luật ở HĐ-4.1 + có chốt chặn `test_only_modular_stacks_can_run_today` |
| 3 | **Adapter `MonolithicPolicy` chưa tồn tại** | Khi muốn so PPO end-to-end với stack modular — tức khi "công bằng cho *mọi* thuật toán" bị đem ra kiểm thật |
| 4 | `instance_difficulty` chưa nối vào tầng quyết định | Cache P03 khoá theo `scenario_name` cũ, không có entry cho profile mới. Và luật "difficulty chọn số episode" **chưa ai viết** — không tự đặt |
| 5 | `robustness_margin` vẫn `null` | Cần Task Neighborhood (pha 2) |
| 6 | Trace kho cũ mồ côi | Chạy lại ở F4.3: 1% ⇒ 300 episode ≈ 3 giờ |

### 4.4. Ngoài MVP-B: API và UI *(plan F5)*

Bảng DB đã có; **router và trang `/decisions` chưa có**. Không chặn MVP-B — MVP-B là một lệnh CLI
và một file JSON. Nhưng cần nhớ một ràng buộc đã ghi trong plan: khi làm UI, nó phải render
được **cả hai** loại artifact. UI chỉ render được Decision Card sẽ tạo áp lực ép mọi run ra
card — tức lặp lại vấn đề vừa tránh, ở tầng trên.

---

## 5. Đường ngắn nhất tới MVP-B

```
F3 nhiễu cảm biến theo seed   (~1 ngày)   ◄── chặn cứng duy nhất
   │
   ├── kiểm: A* trên open_hall cho n_distinct > 1?
   │
F4.0 runner cho phép so tuỳ ý (~2 giờ)
   │
F4.1 so astar+dwa vs rrtstar+dwa trên open_hall  (~nửa ngày + giờ chạy)
   │        └── Decision Card ĐẦU TIÊN trên nền đã kiểm công bằng
   │
F4.2 thêm dwa_default: ma trận 4 candidate       (~nửa ngày + giờ chạy)
            └── trả lời "kẹt góc lồi là của stack hay của lấy mẫu thô?"
```

Tổng tới MVP-B: **khoảng 2 ngày làm việc**, chưa kể giờ máy chạy.

Ba điều phải giữ khi đi đoạn này, cả ba đều đã là luật chứ không còn là lời khuyên:

1. **Bộ kiểm công bằng phải xanh trước khi công bố phép so** (HĐ-15.1 tiêu chí 7).
2. **Kết quả xấu giữ nguyên.** `A*+DWA` kẹt góc lồi 8/8 trên map dễ là *một phát hiện*, không
   phải một lỗi phải sửa. Cách sửa hợp lệ duy nhất là **đăng ký candidate mới** và để nền tảng
   chấm cả hai.
3. **Mọi hằng số mới trong profile phải trả lời được** *"đến từ hiện trường hay từ thứ máy tôi
   chạy nổi?"* (HĐ-15.3).

---

## 6. Ba điểm mù tôi thấy được, nêu ra để dev quyết

**① "Công bằng cho mọi thuật toán" mới được chứng minh trên một họ rất hẹp.** Hai global
planner cùng kiểu tìm đường trên lưới, một local controller. Phép thử thật của tuyên bố đó là
ngày một policy end-to-end chạy — và đúng ngày đó, món nợ 4.3.2 (lưới replan ground truth) trở
thành lỗi công bằng thật. Hiện đã có chốt chặn và điều khoản; chưa có lời giải.

**② Nền tảng chưa bao giờ được kiểm bằng một map khó có đối xứng.** `open_hall` đối xứng nhưng
dễ; kho khó nhưng chưa có kiểm đối xứng nào. Một map vừa khó vừa đối xứng sẽ là phép kiểm mạnh
hơn cả hai — chưa có trong plan, và tôi không tự thêm.

**③ Hai lỗi nặng nhất của tuần này đều tìm được bằng *chạy*, không bằng *đọc*.** Lỗ hổng G4
không đếm tần suất gọi controller, và `L_ref` dôi 2,41% — cả hai nằm im qua mọi lượt review và
qua ~2000 test. Cái thứ hai bị bắt vì F1 dựng một tiêu chí kiểm **đối chiếu với một tối ưu tính
được bằng tay**, thay vì kiểm bằng chặn trên/chặn dưới như mọi test trước đó.

Bài học rút ra, và nó nên định hình cách viết test sau này: **một phép kiểm bằng chặn xanh suốt
trong khi con số sai có hệ thống.** Ở đâu có đáp án đúng tính được — hình học đơn giản, đối
xứng, bảo toàn — thì kiểm bằng đáp án đó, đừng kiểm bằng khoảng.
