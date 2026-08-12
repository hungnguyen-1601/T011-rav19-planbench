# Báo cáo — B1: kho `warehouse_a_v2`, và một run bị ngắt vẫn phải để lại bằng chứng

> **Ngày:** 2026-08-12 · **Nhánh:** `plannerselector_p2`
> **Plan nguồn:** `plans/2026-08-12/viec-con-lai-sau-mvp-v1.md`, mục **B1**
> **Kết quả quan trọng nhất:** kho được đo lần đầu, và nó nói ra hai điều mà sảnh không nói được —
> **cả hai stack đều va chạm**, và **A\* chỉ sinh 85 episode phân biệt trên 245**. Nhưng phải nói
> ngay giới hạn: `warehouse_a_v2` **không khai nhiễu cảm biến**, nên ẩn số số 1 của B1 —
> *"`n_distinct` của A\* trên kho **sau khi có nhiễu**"* — **vẫn chưa được trả lời**.

---

## 1. Chạy cái gì

```
compare.py --profile profiles/warehouse_a_v2.yaml
           --candidates astar+dwa:dwa_coarse,rrtstar+dwa:dwa_coarse
           --scope global_planner_selection
```

Không gõ `--episodes`: số episode là hệ quả của rủi ro đã khai (`collision_probability_max: 0.01`
⇒ N_min = 300), không phải một lựa chọn. Ghim 2 nhân, một process, tuần tự — HĐ-7.4.

**Đo trước khi chạy, và số khác plan:** smoke 4 episode cho **20,9 s/episode**, không phải 13 s
như plan ước hay ~2,9 h như comment trong profile. Tổng dự kiến ~3,5 h.

**Run bị dừng ở 491/600 episode theo lệnh dev**, khi đã rõ không candidate nào ra được cổng.
Cặp hoàn chỉnh cả hai bên: **245/300**. Thời gian máy thực tế: **2,84 giờ**.

---

## 2. Bảng cổng — 245 episode ghép cặp

| | `astar+dwa:dwa_coarse` | `rrtstar+dwa:dwa_coarse` |
|---|---:|---:|
| **n_distinct** | **85 / 245** | **245 / 245** |
| success | 211 (86,1%) | 207 (84,5%) |
| **collision** | **34** | **38** |
| stuck / no_path | 0 | 0 |
| p99 gộp | 9,20 ms | 14,10 ms |
| G1 tìm được đường | pass | pass |
| **G2 an toàn** | **fail** | **fail** |
| **G3 độ tin cậy** | **fail** | **fail** |
| G4 thời gian thực | pass (`screened_on_host`) | pass (`screened_on_host`) |
| G5 bộ nhớ | pass (13,5 MB / 3277) | pass (9,2 MB / 3277) |
| G6 tương thích quan sát | pass | pass |

**0/2 candidate qua đủ sáu cổng ⇒ không có Decision Card.** Bảng cổng là deliverable, và câu hỏi
gốc của đề tài — *A\* hay RRT\* cho kho này* — có câu trả lời: **chưa ai đủ tư cách để hỏi tiếp.**

G2 in đúng câu phải in, không bịa cận trên:

> *"34 va chạm quan sát trong 245 lần chạy; quy tắc số ba chỉ áp dụng cho dữ liệu không có sự
> kiện, nên không có cận trên nào được nêu ở đây"*

---

## 3. Ba điều dữ liệu nói ra

### 3.1. Trên kho, A\* hỏng theo kiểu khác hẳn trên sảnh

Trên `open_hall_v2`, `astar+dwa` trượt G3 ở 70% vì **kẹt góc lồi** — stuck. Trên kho: **0 stuck**
qua 245 episode, và nó hỏng vì **va chạm**. Hai deployment, cùng một stack, hai cơ chế hỏng khác
nhau. Đây đúng là điều §1.1 của đề tài nói: *"cùng một candidate có thể được khuyến nghị cho kho A
và bị bác cho bệnh viện B"* — ở đây còn mạnh hơn, vì **lý do bị bác cũng đổi**.

### 3.2. Hai stack đâm trên những seed gần như rời nhau

| | |
|---|---:|
| seed ghép cặp | 245 |
| cùng kết cục | 191 (78,0%) |
| **cả hai cùng đâm** | **9** |
| chỉ A\* đâm | 25 |
| chỉ RRT\* đâm | 29 |

Tổng 72 va chạm, chỉ 9 seed là "seed xấu ai cũng chết". Tỷ lệ gộp gần trùng (86,1% vs 84,5%)
trong khi kết cục từng episode lệch nhau **1/5 số lần**.

Đây là chỗ **thiết kế ghép cặp trả tiền về** (N8): so hai tỷ lệ rời rạc sẽ kết luận *"không phân
biệt được"*, trong khi hiệu ghép cặp từng episode còn cấu trúc để nói. Cấu trúc này giữ nguyên qua
ba lần kiểm giữa chừng (180, 229, 245 seed) — 78%, 79%, 78% — nên nó không phải một dải seed.

### 3.3. `n_distinct` 85/245 của A\* — và vì sao nó **chưa** trả lời ẩn số của B1

A\* tất định. Trên kho, thứ duy nhất thay đổi giữa các seed là **pha của forklift**
(`seed_time_offset: 24.0`, offset đều trong `[0, 24)`). Với 160/245 seed, robot đi hết tuyến mà
quỹ đạo **trùng khít** một episode khác — forklift không kịp chạm tới nó. RRT\* thì lấy mẫu theo
seed nên 245/245 phân biệt, và sự khác biệt đó **không nói gì về chất lượng điều hướng**.

So với trước: A\* trên kho từ **1/100** (v1, `seed_time_offset` 6 s) lên **85/245** (v2, một chu kỳ
đầy đủ). M2 sửa đúng chỗ, nhưng vẫn còn xa N_min = 300.

**Và đây là chỗ tôi phải sửa lại chính báo cáo tiến độ của mình.** Ba lần báo cáo trong lúc chạy,
tôi viết *"va chạm dưới nhiễu đã khai"*. Sai. `identity.sensor_noise` của run này là:

```json
{"lidar_range_sigma_m": 0.0, "wheel_slip_fraction": 0.0}
```

`warehouse_a_v2.yaml` **không có khối `sensor_noise`**. M1 thêm nhiễu theo seed vào
`open_hall_v2` (σ = 2 cm / trượt 2%, và bump id v1→v2 vì lý do đó); bump v1→v2 của kho là cho
`seed_time_offset` và `control_period`, **không phải cho nhiễu**.

Hệ quả, và nó là kết luận quan trọng nhất của lượt này:

| Ẩn số B1 đặt ra | Trả lời được chưa |
|---|---|
| `n_distinct` của A\* trên kho **sau khi có nhiễu** | **Chưa** — run này chạy ở σ = 0 |
| Có candidate nào qua đủ sáu cổng trên kho không | **Rồi: không ai** |

Muốn trả lời ẩn số thứ nhất phải thêm `sensor_noise` vào profile kho, và theo HĐ-13/HĐ-3.1 điều đó
buộc **đổi `task_profile_id` lên `warehouse_a_v3`** — `episode_context_id` không băm biên độ nhiễu,
nên sửa tại chỗ dưới id cũ sẽ khiến `--reuse-traces` phục vụ episode của một thế giới khác. **245
episode vừa chạy sẽ không dùng lại được.** Đó là lý do dừng run sớm không mất gì thêm.

Cảnh báo mà plan viết sẵn — *"nếu cả hai trượt G2 vì `n_distinct` thấp thì đó là nhiễu chưa đủ chạm
tới kho, và hướng xử lý là đo nhiễu thật của LiDAR 2D và bánh vi sai rồi khai đúng, không phải vặn
σ lên tới khi `n_distinct` đẹp"* — hoá ra đúng, và đúng theo nghĩa chặt hơn dự tính: **σ trên kho
chưa bao giờ được khai, chứ không phải khai chưa đủ.**

---

## 4. Việc thứ hai: một run bị ngắt phải để lại bằng chứng

Dev nêu yêu cầu ngay sau khi dừng run: *"mỗi lần mô phỏng cũng cần phải lưu lại chứ không phải là
chạy không hết số episode thì không lưu lại"*. Đúng, và lỗ hổng lớn hơn nó trông.

`simulate` **đã** chạy context-outer từ trước, và docstring nói rõ lý do là để một sweep bị ngắt
vẫn là một phép so nhỏ hơn hợp lệ. Nhưng **không ai thu hoạch lời hứa đó**: `comparison_report.json`
chỉ được ghi sau episode cuối. Nên 2,84 giờ episode nằm trên đĩa và **không một file nào nói đã đo
được gì**. Bảo đảm được thiết kế đúng, chỉ là không có đường dẫn nào từ nó ra artifact.

Bốn thay đổi:

| Thay đổi | Ở đâu | Vì sao |
|---|---|---|
| **`run_journal.jsonl`** — một dòng JSON mỗi episode, flush ngay | `pipeline.simulate` | Sống sót qua **kill cứng**, thứ mà `try/except` không bắt được. Mỗi dòng đủ để nối ngược về episode: `candidate_id`, `episode_context_id`, `seed`, `status`, `wall_clock_s` |
| **Thư mục run tạo trước khi mô phỏng** | `selection.run_comparison` | Tên thư mục chỉ phụ thuộc profile + scope + tập candidate — biết trước episode đầu tiên. Run chết ở phút đầu giờ vẫn để lại dấu nó đã được thử |
| **`paired_prefix()`** + bắt `KeyboardInterrupt` | `pipeline` / `selection` | Ctrl+C ⇒ chấm trên **tiền tố** episode mà **mọi** candidate đều có. Lấy *tập* thay vì tiền tố sẽ để một candidate mang episode candidate kia không chạy — HĐ-7.3 mất mà không gì đỏ |
| **`--score-only`** | `compare.py` | Đường phục hồi cho run đã bị giết: chấm những gì có trên đĩa, không mô phỏng lại, không sửa tay JSON |

Và `sample` của report nay khai hai trường mới:

```json
"n_episodes": 245, "n_episodes_requested": 300, "interrupted": true
```

Phân biệt này là toàn bộ lý do trường tồn tại: *"chúng tôi chọn 245"* và *"máy bị lấy lại ở 245"*
là hai tuyên bố khác nhau về cùng một con số, và chỉ một cái đúng ở đây. Bản tóm tắt in thêm:

> ⚠ RUN BỊ NGẮT — chấm trên 245/300 episode đã xin. Đây là một phép đo nhỏ hơn, không phải một
> lựa chọn về cỡ mẫu

`.gitignore` mở khe thứ năm cho `run_journal.jsonl`, cùng lý do đã mở cho `comparison_report.json`
— lần này ghi luôn vào comment rằng nó là artifact **duy nhất** của một run không tới đích.

**Journal của chính run B1 được dựng lại từ stdout** (491 dòng) và mỗi dòng mang
`"source": "reconstructed_from_stdout"` kèm ghi chú thiếu dấu thời gian tuyệt đối — nó được ghi
trước khi tính năng tồn tại, và không nên trông giống một journal ghi trực tiếp.

---

## 5. Nghiệm thu

| # | Tiêu chí | Kết quả |
|---|---|---|
| 1 | Cùng tập `episode_context_id` | ✅ 245 id, cả hai candidate |
| 2 | Đủ 6 cổng kèm `n_runs` và `n_distinct_episodes` | ✅ |
| 3 | `L_ref ≤ path_length + goal_tolerance` | ✅ 418 episode thành công |
| 4 | `peak_search_nodes ≤ costmap_cells` | ✅ |
| 5 | ΔU và CI không NaN | ⏸ n/a — không có phép so |
| 6 | Tái lập `decision_utility` | ⏸ n/a — không có card |

`tests/test_compare.py` **35 pass** (thêm 6 test mới cho journal, tiền tố, và nhãn ngắt);
`test_vertical_slice.py` + `test_measure.py` xanh — **71 pass** cả ba file. ruff sạch.

**Full suite chưa chạy** — dev yêu cầu chờ cho phép.

---

## 6. Một lỗ hổng có sẵn, không thuộc lượt này

`tests/api/test_api_decisions.py` có **3 test đỏ**:

```
AnchorError: anchor 'success_rate' resolves to good == bad == 1.0
             for task profile 'api_hall_tiny'; the metric would have no scale
```

Đã kiểm bằng cách stash đúng năm file tôi sửa rồi chạy lại — **vẫn đỏ**. Nguồn là commit `79f7b04`
(Phase A4) đặt `open_hall_v2.constraints.success_rate_min: 1.00` theo quyết định Q1 của dev.
`tiny_profile()` trong test API kế thừa profile sảnh, nên `success_rate.bad = ${constraints.
success_rate_min} = 1.0` đụng `good = 1.0`, và `load_anchors().resolve()` từ chối vì metric không
còn thang.

Đây không phải lỗi của A4 — luật *"`bad` của metric có cổng phải neo vào chính ngưỡng cổng"*
(HĐ-8.3 law 2, N2 của đề tài) là đúng. Nó là **hệ quả chưa ai tính** của việc một acceptance
deployment khai ngưỡng **1.00**: khi ngưỡng cổng bằng giá trị hoàn hảo thì *"vượt ngưỡng bao
nhiêu"* không còn chỗ để đo, và điều khoản N4 *"gate chấm trên ngưỡng, điểm chấm trên phần dôi"*
mất phần dôi.

Cần một quyết định, không phải một bản vá — ghi để không rơi:

- `success_rate` có nên **rời khỏi Score** khi `success_rate_min = 1.0` (chỉ còn là gate)?
- hay `open_hall` cần một anchor riêng cho vai acceptance deployment?

---

## 7. Trạng thái và việc kế tiếp

| | |
|---|---|
| Deployment đã đo | 2 (`open_hall_v2`, **`warehouse_a_v2`**) |
| Kho có candidate qua cổng | **không ai** |
| Decision Card | vẫn đúng 1 tấm, trên sảnh |
| Nhiễu cảm biến trên kho | **chưa bao giờ khai** |

**Theo thứ tự:**

1. **Khai nhiễu thật cho kho ⇒ `warehouse_a_v3`.** Đo σ thật của LiDAR 2D và trượt bánh vi sai rồi
   khai đúng, không vặn tới khi `n_distinct` đẹp. Đổi id là bắt buộc; 245 episode hiện có không
   dùng lại được. Đây là điều kiện cần để ẩn số số 1 của B1 có câu trả lời.
2. **Quyết `success_rate` anchor khi ngưỡng = 1.00** (mục 6) — nó đang chặn 3 test API.
3. **Kho không có ai qua cổng là một phát hiện, không phải bế tắc.** Lối ra hợp lệ theo HĐ là
   **đăng ký candidate mới**, không nới `success_rate_min` và không sửa traffic. Đã có sẵn một
   plan nháp cho hướng đó (`plans/2026-08-11/them-theta-star-va-regulated-pure-pursuit.md`).
4. Chưa động, giữ nguyên thứ tự plan 08-12: A2 (`run_uri` + checksum, đang có người làm), B2
   (`astar+ppo`), C1 (adapter monolithic), C2 (map vừa khó vừa đối xứng), D1/D2.

**Artifact của lượt này:**
`artifacts/runs/2026-08-12/warehouse_a_v2_global_planner_selection_ce26fe87/`
— `comparison_report.json` (bảng cổng, 245/300, `interrupted: true`) và `run_journal.jsonl`
(491 dòng, mọi episode đã chạy kể cả 55 dòng nằm ngoài tiền tố ghép cặp).
