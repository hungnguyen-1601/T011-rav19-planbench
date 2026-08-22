# Báo cáo — Phase 6.2, một lỗ hổng tự tạo, và tấm Decision Card đầu tiên

> **Ngày:** 2026-08-11 · **Nhánh:** `plannerselector_p2`
> **Nguồn:** `notes/2026-08-11/tongduyan_ra-soat-phase-6-sau-mvp-v1.md` (mục 1–3 làm trước 6.2),
> backlog 08-08 Phase 6.2, và bước ③ của danh sách bước-tiếp
> **Contract:** `6.3.0` (không bump; lược đồ DB không phải hợp đồng)
> **Kết quả quan trọng nhất:** dự án có **tấm Decision Card đầu tiên** trên nền đã kiểm công
> bằng. Trên đường tới đó, 6.2 tự tạo ra một lỗ hổng và nó chỉ lộ vì tôi đi tìm nhánh chưa
> từng chạy.

---

## 1. Lược đồ phải xoay lại trước, không phải sau

Note rà soát đã kết luận: **không revert, nhưng phải mở rộng lược đồ trước khi viết router.**
Lý do là `0005` khai `decision_cards.card NOT NULL` và
`recommended_candidate_id NOT NULL` — tức mã hoá giả định *mọi lần chạy đều kết thúc bằng một
xếp hạng*. MVP v1 vừa bác bỏ điều đó trong một ngày: ba trên ba phép so không ra card.

`0006` xoay bảng lại:

```
decision_runs
  report   NOT NULL     -- một lần chạy luôn sinh bằng chứng
  card     NULL         -- và ĐÔI KHI sinh một khuyến nghị
  manifest NULL
  recommended_candidate_id NULL
  status   NULL
  artifact_kind  NOT NULL, có index
```

Drop chứ không migrate: `decision_cards` chưa từng có repository, router hay một dòng dữ liệu.
Mang một bảng rỗng đi tiếp dưới cái tên mô tả sai hình dạng thì đắt hơn là bỏ.

**Nullability ở đây là hợp đồng, không phải trang trí**, và test nói thẳng điều đó — mỗi cột
optional có một thông điệp giải thích vì sao bắt nó NOT NULL sẽ tạo áp lực buộc mọi run phải
rank được. `artifact_kind` là **cột có index** chứ không phải trường JSON, vì *"cho tôi xem
những run không rank được"* là câu hỏi ngày đầu và câu trả lời không query được là câu người ta
thôi hỏi.

Kèm hai thứ note đã đề xuất: round-trip bằng **artifact thật** (`profiles/open_hall_v2.yaml`,
chỉ cắt ngân sách episode) chứ không phải dict bịa; và kiểm **profile trùng khít** khi ghi —
nạp lại một `task_profile_id` với nội dung khác trả **409**. Đó là bẫy HĐ-13 chuyển sang tầng
lưu trữ: `episode_context_id` không băm environment, nên sửa profile tại chỗ dưới id cũ sẽ khiến
mọi run đã lưu âm thầm mô tả một thế giới không còn tồn tại.

## 2. Router, và một nguyên tắc phải áp thêm một tầng

Ba resource dưới `/api/v1`: `POST/GET /task-profiles`, `POST/GET /candidates`,
`POST/GET /decisions`.

Nhưng `run_comparison` nằm trong `scripts/compare.py`, mà API **không được import script**. Để
nguyên sẽ thành **hai** orchestration — một trong script, một trong `planbench_api` — tự do bất
đồng về ý nghĩa của một phán quyết cổng. Đó đúng là thứ M3 vừa gỡ giữa slice/measure/compare,
chỉ ở tầng trên. Nên chuỗi chuyển vào `packages/benchmark/planbench_benchmark/selection.py`, và
CLI lẫn API cùng gọi.

**Tôi ghi đè nhầm một module đang có.** Lần đầu tôi đặt tên nó là `comparison.py` — mà
`planbench_benchmark/comparison.py` đã tồn tại từ P04 (thống kê ghép theo seed, 182 dòng). Phát
hiện qua `ImportError` từ `__init__.py`, khôi phục bằng `git checkout`, đổi tên thành
`selection.py`. Không mất gì, nhưng tôi đã không kiểm tên có trùng không trước khi ghi.

Hai quyết định thiết kế của router đáng ghi:

**`POST /decisions` trả 201 kể cả khi không có card.** Dưới hai candidate qua cổng ⇒ không ΔU,
và bảng cổng là toàn bộ deliverable. Trả 4xx là nói với caller rằng request của họ sai, trong
khi nền tảng đã trả lời đúng câu họ hỏi. Response mang `ranked: false`, và `?ranked=false` lọc
được.

**Chạy đồng bộ, không qua job queue.** Số episode đến từ rủi ro khai báo, nên ai xin 300 episode
trên kho là đang xin vài giờ và nên được đồng hồ nói thẳng thay vì một job id giấu đi. Thêm nữa
queue hiện có là bounded và dùng chung với benchmark; đỗ một selection ba tiếng vào đó sẽ bỏ
đói chúng. Đưa nó ra sau queue là một thay đổi có chủ ý kèm câu chuyện huỷ riêng, không phải
mặc định.

---

## 3. Lỗ hổng 6.2 tự tạo ra, và vì sao nó không bị bắt

`run_comparison` ghi `manifest.json` xuống đĩa nhưng **không trả nó trong report**. CLI không
sao — nó đọc lại thư mục. API thì lưu **thứ hàm này trả về**, nên nó lưu card kèm
`manifest: None`.

Điều đó phá đúng tiêu chí nghiệm thu của HĐ-13: *"đưa manifest cho người khác, họ dựng lại được
cùng một Decision Card"*. API phục vụ một tấm card **không có gì để dựng lại nó**.

**Vì sao không ai vấp:** mọi run qua API tới lúc đó đều **không có card**, nên `manifest` null
vì `card` cũng null. Nhánh ranked chưa từng chạy qua API.

**Và vì sao test không bắt:** có một test khẳng định cột `manifest` **được phép** null — nó
xanh. Một phép kiểm "cột này nullable" không bao giờ bắt được "cột này null nhầm". Cái bắt được
là **chạy nhánh chưa từng chạy**.

Sửa ba chỗ: nhánh ranked trả manifest; nhánh unranked đặt `report["manifest"] = None` — **có
mặt và null**, không vắng, để người đọc không phải biết nhánh nào đã chạy; service lưu nó.

Sáu test mới không dừng ở *"manifest có mặt"* mà hỏi *"có đủ để dựng lại không"*:
`episode_contexts` (id là hash, không đảo ngược), `bootstrap.seed` (khoảng tin cậy là một lần
rút ngẫu nhiên), `benchmark_host` (G4 đọc đồng hồ tường), `sensor_noise` (cùng seed khác σ là
hai thí nghiệm) — mỗi thứ được thêm vào HĐ-13 vì đã có một lần dựng lại hỏng khi thiếu nó. Cộng
một test khẳng định tập context trong manifest **trùng khít** tập đã chấm: một manifest ghi tập
khác sẽ dựng ra card khác mà trông vẫn hợp lệ.

---

## 4. Bước ③ — candidate thứ năm, và dự đoán ghi trước khi đo

`dwa_balanced` (12×24 = 288 mẫu) là **điểm thứ ba trên một trục thiết kế thật**, không phải núm
vặn tới khi qua cổng. Hai đầu đã đo trước và chúng kẹp lấy ngân sách 50 ms: 105 mẫu thừa sức,
800 mẫu trượt G4 đúng 0,28 ms. Câu hỏi mở không phải *"làm sao cho qua"* mà *"trên trục này
ngân sách hết ở đâu"*.

Vì tôi đã một lần khái quát sai từ 3 episode, lần này **dự đoán được ghi vào code trước khi
chạy**, bằng nội suy tuyến tính theo số mẫu:

| | dự đoán | đo được | lệch |
|---|---:|---:|---:|
| `astar+dwa` 12×24 | 11,6 ms | **14,04 ms** | +21% |
| `rrtstar+dwa` 12×24 | 17,7 ms | **19,30 ms** | +9% |

Mô hình tuyến tính giữ được về bậc độ lớn, và lệch **cùng một chiều** ở cả hai — chi phí tăng
hơi nhanh hơn tuyến tính theo số mẫu.

Trục lấy mẫu, ba điểm đo, cả hai stack:

| mẫu | `astar+dwa` p99 | success | `rrtstar+dwa` p99 | success |
|---:|---:|---:|---:|---:|
| 105 (`dwa_coarse`) | 5,26 ms | 70% | 6,06 ms | 100% |
| 288 (`dwa_balanced`) | 14,04 ms | 73% | **19,30 ms** | 100% |
| 800 (`dwa_default`) | 29,40 ms | 73% | 50,28 ms ✗G4 | 100% |

**Hai điều trục này nói ra:**

`astar+dwa` mua được **3 điểm phần trăm** success khi đi từ 105 lên 288 mẫu, rồi **không gì
nữa** từ 288 lên 800 — trong khi trả gấp 5,6 lần chi phí. Nó vẫn trượt G3 ở cả ba điểm. Kẹt góc
lồi không phải vấn đề lấy mẫu, và giờ có ba điểm đo nói điều đó thay vì hai.

`rrtstar+dwa` giữ 100% ở cả ba, nên với nó lấy mẫu **chỉ mua chi phí**. Ngân sách 50 ms hết ở
đâu đó giữa 288 và 800 mẫu.

---

## 5. Tấm Decision Card đầu tiên

```
recommended    rrtstar+dwa · dwa_coarse · db26440f6052
status         CLEAR_RECOMMENDATION
scope          MISSION_LEVEL · local_controller_selection
ΔU median      +0,032081     mean +0,034185
CI95           [+0,031790, +0,037033]     n = 30     effect size 4,74
pareto         UNCERTAIN_DOMINANCE        alternative: null
caveat         "G4 mới qua vòng sàng lọc — chưa xác nhận trên bo mạch đích"
manifest       30 context · σ = 2 cm / trượt 2% · affinity [0, 1]
```

Câu nó trả lời: *"trên deployment này, RRT\* nên ship với mật độ lấy mẫu DWA nào?"* Đáp: **thô
hơn**. Cùng 100% thành công, nhưng `dwa_coarse` rẻ hơn 3,2 lần về tính toán, và U_C là chỗ khác
biệt đó đi vào điểm.

Sáu tiêu chí nghiệm thu đều xanh, kể cả hai cái mà ba phép so trước phải treo vì không có phép
so: `ΔU` và CI không NaN, và `decision_utility` tái lập tới 6 chữ số.

### 5.1. Ba giới hạn của chính tấm card này

**`weight_stability_margin` và `anchor_stability` đều null.** `compare.py` không chạy quét độ
nhạy; `vertical_slice.py` thì có. Nên đang có **hai bộ sinh card với độ đầy đủ khác nhau** —
nguyên tắc "một chuỗi" của M3 đã áp cho tầng đo nhưng **chưa áp cho bước lắp card**. HĐ-12 quy
định null nghĩa là *"chưa đo"*, nên tấm card trung thực nhưng thiếu; và HĐ-11.5 gọi độ nhạy là
tính năng quan trọng nhất (N1). Đây là lỗ hổng thật, không phải chi tiết.

**`pareto_label: UNCERTAIN_DOMINANCE` đứng cạnh `CLEAR_RECOMMENDATION`.** Không mâu thuẫn —
chúng trả lời hai câu khác nhau. Nhãn thứ nhất nói *"không ai lấn át ai trên cả bốn objective"*;
nhãn thứ hai nói *"hiệu số utility ghép cặp rõ ràng khác 0"*. `alternative` rỗng vì nó chỉ lấy
từ `PARETO_FRONTIER`. Ai đọc card cần biết cả hai.

**Phạm vi là `local_controller_selection` trên một sảnh thử.** Card này **không** nói A\* hay
RRT\* tốt hơn — phạm vi đó là `global_planner_selection`, và phép so ấy không ra card vì A\*
trượt G3. Nó cũng không nói gì về kho hàng: `open_hall_v2` là dụng cụ đo, và ngưỡng
`success_rate_min: 0.95` của nó được chép từ kho, chưa bao giờ khai riêng cho sảnh.

---

## 6. Trạng thái

Full suite **2166 passed, 6 skipped** trước bước ③; ruff sạch. Chưa commit.

| | |
|---|---|
| 6.1 lược đồ | ✅ xoay lại ở `0006` |
| 6.2 router | ✅ ba resource, 23 test API |
| Decision Card đầu tiên | ✅ |
| 6.3 approval | ⏳ |
| Phase 7 UI | ⏳ |

**Việc phát sinh từ lượt này, theo mức nghiêm trọng:**

1. **Card sinh bởi `compare.py` thiếu độ nhạy.** Hai bộ sinh card, hai độ đầy đủ. Áp nốt nguyên
   tắc một-chuỗi cho bước lắp card (~2 giờ).
2. **6.3 chỉ duyệt được run có card.** Một run không rank được không có gì để duyệt, và cho
   phép duyệt nó là biến *"đã đo"* thành *"đã chấp thuận"*. Phải quyết trước khi làm.
3. **Kho ở mức 1%** vẫn là deployment thật duy nhất chưa chạy, và `n_distinct` của A\* ở đó sau
   khi có nhiễu vẫn là ẩn số.
