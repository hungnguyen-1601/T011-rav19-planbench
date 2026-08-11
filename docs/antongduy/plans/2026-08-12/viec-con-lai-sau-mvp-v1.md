# Kế hoạch 12-08: việc còn lại sau MVP v1

> **Ngày lập:** 2026-08-11 (cho ngày làm 2026-08-12) · **Người lập:** An (cùng Claude)
> **Trạng thái:** chờ approve
> **Bối cảnh:** MVP v1 đã chốt (M0–M4), Phase 6.1 lược đồ đã xoay lại ở `0006`, Phase 6.2 router
> đã xong, và dự án có **tấm Decision Card đầu tiên** trên nền đã kiểm công bằng.
> **Nguồn:** `reports/2026-08-11/tongduyan_phase-6-2-va-tam-decision-card-dau-tien.md`,
> `notes/2026-08-11/tongduyan_survey-hien-trang-va-duong-toi-mvp.md`,
> `plans/2026-08-11/hoan-thien-mvp-phep-so-dau-tien.md`

---

## 0. Đứng ở đâu

| | |
|---|---|
| Nền tảng đo | ✅ 6 cổng, 60+ test công bằng, nhiễu theo seed, ghim nhân, manifest đầy đủ |
| Nền tảng so | ✅ `pipeline` + `selection` dùng chung cho CLI và API |
| API | ✅ `/task-profiles`, `/candidates`, `/decisions` — lưu được cả run có card lẫn không |
| Decision Card | ✅ một tấm, `local_controller_selection` trên `open_hall_v2` |
| Candidate đã đo | 6 (2 global × 3 local) |
| Deployment đã chạy | 1 (`open_hall_v2`) — **kho chưa bao giờ chạy dưới nhiễu** |

**Nguyên tắc xếp hạng của bản này giữ nguyên như plan 08-11:** một phép **đo** hợp lệ trước, một
phép **so** hợp lệ sau, một **sản phẩm** sau nữa. Việc nào làm phép đo đúng hơn xếp trên việc
làm kết quả dễ xem hơn.

---

## A. Nợ kỹ thuật từ chính lượt hôm qua *(làm trước, rẻ)*

### A1. Card sinh bởi `compare.py` thiếu quét độ nhạy — **ưu tiên cao nhất**

`vertical_slice.py` chạy `weight_stability` và `anchor_stability`; `compare.py` thì không. Nên
tấm card đầu tiên có `weight_stability_margin: null` và `anchor_stability: null`.

HĐ-12 quy định null nghĩa là *"chưa đo"*, nên card **trung thực nhưng thiếu** — và HĐ-11.5 gọi
độ nhạy là tính năng quan trọng nhất (N1): nó trả lời *"khuyến nghị này có lật khi trọng số xê
dịch không"*. Một khuyến nghị `CLEAR_RECOMMENDATION` mà không ai biết nó lật ở đâu là một nửa
câu trả lời.

Sâu hơn: đang có **hai bộ sinh card với độ đầy đủ khác nhau**. Nguyên tắc một-chuỗi của M3 đã áp
cho tầng **đo** nhưng chưa áp cho bước **lắp card**.

**Việc:** rút phần lắp card (recommendation → sensitivity → pareto → card + manifest) ra khỏi
`vertical_slice.py` vào `planbench_benchmark.selection`, để cả hai script và API cùng gọi. Hàng
rào giống M3: `tests/test_vertical_slice.py` phải xanh, và nếu phải sửa assertion thì refactor
đã đổi hành vi.

**Ước lượng:** 2–3 giờ. **Kiểm:** chạy lại phép so `rrtstar` coarse vs balanced, card mới phải
có hai trường độ nhạy khác null và `decision_utility` **không đổi** so với tấm cũ.

### A2. `run_uri` trỏ vào thư mục run, không vào bộ trace

`DecisionRunService._store` đặt `run_uri = str(run_root)` — đúng thư mục gốc của mọi run, không
phải của run này. `run_checksum` thì luôn `None`.

D15 nói card lưu **URI + checksum**, và checksum là thứ làm tham chiếu đó đáng tin thay vì trang
trí: một URI trần không nói được rằng những file nó trỏ tới đúng là những file card này được
tính từ đó.

**Việc:** `run_uri` trỏ đúng thư mục của run (`selection.run_dir_name` đã sinh tên), và
`run_checksum` băm tập trace đã dùng. **Ước lượng:** 1 giờ.

### A3. `uv.lock` rỗng vẫn nằm trong cây làm việc

8 dòng, khai **không dependency nào**, trong khi `requirements.txt` ghim 20 gói. Xoá hoặc
gitignore — quyết định của dev, nhưng đừng để nó trôi vào commit nào.

---

## B. Đo cho đủ *(giá trị cao nhất về mặt khoa học)*

### B1. Kho `warehouse_a_v2` ở mức 1% — **deployment thật duy nhất chưa chạy**

Mọi kết luận hiện có đều trên `open_hall_v2`, mà sảnh là **dụng cụ đo**, không phải khách hàng.
Ngưỡng `success_rate_min: 0.95` của nó còn được chép từ kho và chưa bao giờ khai riêng cho sảnh
(xem C3).

Kho thì khác: 40×25 m, kệ thật, traffic thật, và 95% success **có nghĩa thật** ở đó.

**Hai ẩn số chỉ lần chạy mới trả lời được:**

1. `n_distinct` của `astar+dwa` trên kho **sau khi có nhiễu**. Trước nhiễu nó là 1/100. Nhiễu
   theo seed sửa đúng ca đó, nhưng trên kho thì chưa ai đo.
2. Có candidate nào qua đủ sáu cổng trên kho không. Trên sảnh chỉ RRT\* qua.

**Chi phí:** N_min = 300 ở mức 1%, hai candidate ⇒ 600 episode. Ở ~13 s/episode (kho lớn hơn
sảnh) là **~2,2 giờ**, cần máy rảnh và **chạy tuần tự** (HĐ-7.4: hai run ghim song song giành
cùng hai nhân).

**Đề xuất:** chạy `astar+dwa:dwa_coarse` vs `rrtstar+dwa:dwa_coarse`, scope
`global_planner_selection`. Đó là câu hỏi gốc của đề tài.

**Cảnh báo trước, để kết quả xấu không bị đọc nhầm:** nếu cả hai trượt G2 vì `n_distinct` thấp
thì đó là **nhiễu chưa đủ chạm tới kho**, không phải nhiễu hỏng — và hướng xử lý là **đo nhiễu
thật của LiDAR 2D và bánh vi sai rồi khai đúng**, không phải vặn σ lên tới khi `n_distinct` đẹp.

### B2. `astar+ppo` — candidate thứ ba chưa ai chạm

Có sẵn trong registry, `benchmarkable=True`, chưa từng vào phép so nào. Nó là stack **modular**
(A\* quy hoạch, PPO bám đường), nên **không** vướng nợ adapter monolithic ở C1.

Cần `torch` (nhóm optional, vài GB) và một checkpoint. **Ước lượng:** nửa ngày nếu checkpoint đã
có; không rõ nếu phải train.

**Giá trị:** đây là candidate đầu tiên có **lớp quan sát khác** hai stack cổ điển, nên nó là
phép thử thật đầu tiên của G6 và của P02.

---

## C. Nợ chặn tuyên bố "công bằng cho mọi thuật toán"

### C1. Adapter `MonolithicPolicy` + bất cân xứng lưới replan

Hai việc dính nhau và **phải làm cùng lượt**.

`nav_stack._replan` dựng lưới quy hoạch tạm với **vị trí thật** của vật cản động. Hôm nay công
bằng vì mọi candidate đều `modular` và nhận cùng lưới. Ngày adapter monolithic chạy được, một
policy end-to-end chỉ thấy `Observation` còn global planner của stack modular thấy vật cản
**thật sự ở đâu** — đúng đặc quyền mà G6 sinh ra để định giá, và nó ưu ái stack modular vì lý do
không liên quan tới chất lượng điều hướng.

HĐ-4.1 đã ghi luật: gỡ đặc quyền **trước** khi chấm candidate `monolithic`, và lời giải hợp lệ
là **replan từ `Observation`** — không phải cấp ground truth cho cả hai bên.
`test_only_modular_stacks_can_run_today` sẽ đỏ đúng ngày adapter được thêm.

**Ước lượng:** 1–2 ngày. **Vì sao không gấp:** chưa có candidate `monolithic` nào, nên chưa có
vấn đề. Nhưng tuyên bố *"nền tảng công bằng cho mọi thuật toán"* mới được chứng minh trên **hai
global planner cùng kiểu tìm đường trên lưới với một local controller** — phép thử thật của
tuyên bố đó chưa chạy.

### C2. Map vừa khó vừa đối xứng

`open_hall` đối xứng nhưng dễ; kho khó nhưng **chưa có kiểm đối xứng nào**. Một map vừa khó vừa
đối xứng là phép kiểm mạnh hơn cả hai. Điểm mù ② của survey 08-11.

**Ước lượng:** nửa ngày (đã có `scripts/make_fairness_map.py` làm mẫu, và bài học "sinh ra được
+ test khẳng định đối xứng" thay vì vẽ tay rồi tin).

### C3. `success_rate_min` của sảnh chưa bao giờ được khai riêng

Mọi hằng số khác trong `open_hall_v2.yaml` đều có comment giải thích; riêng `0.95` được chép từ
kho. Nên *"A\* trượt G3 trên sảnh"* phải đọc là **A\* đạt 70% trên sảnh**, và việc đó có phải
thất bại hay không còn phụ thuộc một ngưỡng chưa ai chủ động chọn.

**Việc:** khai có chủ ý kèm lý do viết ra — dù là 0.95 hay khác. Nếu khác thì phải vì **sảnh này
cần thế**, không phải vì A\* trượt (HĐ-15.3). **Ước lượng:** 30 phút suy nghĩ, 5 phút gõ.

---

## D. Bề mặt sản phẩm *(làm sau, không làm phép đo đúng hơn)*

### D1. Phase 6.3 — Approval → `approved_config.yaml`

Hạ tầng đã chạy thật: `approval.py` có `Role`, `Capability`, state machine, chống tự duyệt, audit
append-only.

**Một quyết định phải chốt trước khi gõ:** chỉ run **có card** mới duyệt được. Một run không rank
được không có gì để duyệt, và cho phép duyệt nó là biến *"đã đo"* thành *"đã chấp thuận"*.

**Ước lượng:** 2–3 giờ.

### D2. Phase 7 — trang `/decisions`

Ràng buộc đã ghi từ plan 08-11 và giờ có bằng chứng: trang phải render **cả hai** loại artifact.
Bốn trong năm phép so đã chạy **không ra card**. Một UI chỉ render được Decision Card sẽ tạo lại
đúng áp lực buộc mọi run phải rank được — áp lực đã sinh ra tấm card tuyên bố cận trên va chạm
từ một episode.

Nội dung theo backlog 08-08 mục 7.1–7.4, cộng: bảng cổng phải là **màn hình hạng nhất**, không
phải tab phụ.

---

## E. Nợ cũ chưa động, ghi để không rơi

- `instance_difficulty` chưa nối vào tầng quyết định (cache P03 khoá theo `scenario_name` cũ).
- `robustness_margin` vẫn null — cần Task Neighborhood (pha 2).
- `business_adjusted` có anchor tiền nhưng chưa demo được hai chân trời lật khuyến nghị (N3).
- Ghim nhân đã cưỡng chế trong code, nhưng **không có gì chặn hai run song song** — chỉ có điều
  khoản HĐ-7.4. Một cờ file khoá là rẻ nếu ai đó vấp thật.

---

## Thứ tự đề xuất cho ngày 12-08

```
A1 độ nhạy vào card    (2–3 h)  ─┐  hai việc này làm tấm card đang có
A2 run_uri + checksum  (1 h)    ─┘  trở nên đầy đủ, rẻ, và không cần máy rảnh
        │
        ├── C3 khai success_rate_min của sảnh   (35 ph, thuần suy nghĩ)
        │
        └── B1 kho ở mức 1%   (~2,2 h máy, chạy nền)
                   │
                   └── báo cáo: deployment thật đầu tiên
```

**Nếu chỉ có nửa ngày:** A1 + A2 + C3. Chúng làm tấm card hiện có đầy đủ và không tốn giờ máy.

**Nếu có máy rảnh cả ngày:** thêm B1, và bật nó chạy nền từ sáng.

**Cố ý không xếp vào ngày mai:** C1 (adapter monolithic, 1–2 ngày), B2 (`astar+ppo`, phụ thuộc
checkpoint), D1/D2 (bề mặt sản phẩm). Cả bốn đều đúng việc, không cái nào gấp hơn A và B.

---

## Ba câu hỏi mở cần dev quyết

1. **`success_rate_min` của `open_hall_v2` là bao nhiêu, và vì sao?** (C3) — không quyết thì mọi
   kết luận trên sảnh đều treo một ngưỡng chưa ai chọn.
2. **Kho chạy ở mức 1% (300 ep) hay 3% (100 ep) cho lượt đầu?** Contract nói rủi ro đến từ hiện
   trường chứ không từ ngân sách máy — nên nếu chọn 3% thì phải vì kho chấp nhận 3%, không phải
   vì 300 episode lâu.
3. **6.3 có cho duyệt run không-card không?** Đề xuất: không. Nhưng đó là quyết định về quy
   trình phê duyệt, không phải về code.
