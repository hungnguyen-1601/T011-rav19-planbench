# Báo cáo — M3 và M4: ba phép so, và không một tấm card nào

> **Ngày:** 2026-08-11 · **Nhánh:** `plannerselector_p2`
> **Plan nguồn:** `plans/2026-08-11/hoan-thien-mvp-phep-so-dau-tien.md`, phase **M3** và **M4**
> **Contract:** `6.3.0` (thêm một điều khoản vào HĐ-7.4, không bump)
> **Kết quả quan trọng nhất:** nền tảng chạy đúng như thiết kế, và điều nó nói ra là **trên sảnh
> tham chiếu, đúng một trong bốn candidate đáng đem triển khai**. Ba phép so, ba lần không có
> Decision Card — mỗi lần vì một lý do khác nhau, và cả ba đều là kết quả hợp lệ.

---

## 1. M3 — một chuỗi, ba lối vào

Chuỗi đo chuyển vào `packages/benchmark/planbench_benchmark/pipeline.py`. Ba script
(`vertical_slice`, `measure`, `compare`) thành lớp mỏng gọi nó; chúng chỉ khác nhau ở chỗ **làm
gì với** kết quả, không ở cách đo. Nếu khác cả cách đo thì hai lần chạy có thể bất đồng mà không
ai nói được khác biệt đến từ candidate hay từ việc dùng script nào.

`decide()` tách thành `gate_all()` + `score_survivors()`. `decide` **ném** khi dưới hai candidate
qua cổng — semantics của lát cắt; `compare.py` phải **sống được** với ca đó, nên nó gọi hai mảnh
và tự quyết thay vì bắt exception để lái luồng điều khiển.

### 1.1. Guardrail đã nổ, và nó bắt được gì

Điều kiện tự đặt: `tests/test_vertical_slice.py` phải xanh **không sửa một dòng**. Nó đỏ 2 test.

Kiểm ra: cả hai `monkeypatch.setattr(slice_module, "run_contract_episode", …)` rồi gọi
`slice_module.simulate`, mà `simulate` nay ở `pipeline`. Mọi assertion đều về **thứ tự dispatch**
và không đổi. Guardrail bắt được **coupling theo đường module**, không phải đổi hành vi.

Sửa đúng mục tiêu patch, assertion nguyên vẹn: diff **3 dòng**. `test_measure.py` tương tự **2
dòng** — `check_l_ref` nay nhận dict thay vì list.

Đây là lý do đặt guardrail: không phải để nó không bao giờ nổ, mà để khi nổ thì có người đọc xem
nó bắt được gì.

### 1.2. Không viết bản single-candidate riêng

`measure.py` từng có bản sao `score`, `check_l_ref`, `check_reproducible`, `check_node_counts`
theo chữ ký một-candidate. Xoá hết, dùng chung bản dict-based và gọi với
`{candidate_id: metrics}`. Một candidate là **ca suy biến**, không phải phép kiểm khác — hai bản
riêng là cách chúng trôi tới chỗ bất đồng về cái gì là pass.

### 1.3. `compare.py`

`--candidates 'stack[:local_config]'`. Hậu tố `:local` là thứ khiến câu hỏi *"cùng stack, hai
controller"* **nói ra được** — câu hỏi mà vụ kẹt góc lồi để lại từ 08-11.

Scope **khai**, không suy: `validate_experiment_scope` từ chối một set không đỡ nổi tuyên bố, và
suy scope từ set sẽ biến từ chối đó thành một lần đổi tên.

Dưới hai candidate qua cổng thì **vẫn ghi** `comparison_report.json`, với `decision_card: null`
và `why_no_card` nói rõ. Bảng cổng là **deliverable** chứ không phải đường lỗi. Một công cụ chỉ
thành công khi rank được sẽ tạo áp lực buộc mọi run phải rank được — đúng thứ áp lực đã sinh ra
tấm card tuyên bố cận trên va chạm từ một episode.

---

## 2. M4 — ba phép so trên `open_hall_v2`

30 episode ghép cặp, ghim 2 nhân, nhiễu σ = 2 cm / trượt 2%.

| scope | stack | local | distinct | success | p99 gộp | verdict |
|---|---|---|---:|---:|---:|---|
| `global_planner_selection` | `astar+dwa` | `dwa_coarse` | 30/30 | 70% | 5,26 ms | **fail G3** |
| | `rrtstar+dwa` | `dwa_coarse` | 30/30 | 100% | 6,06 ms | **PASS** |
| `local_controller_selection` | `astar+dwa` | `dwa_coarse` | 30/30 | 70% | 5,26 ms | **fail G3** |
| | `astar+dwa` | `dwa_default` | 30/30 | 73% | 29,40 ms | **fail G3** |
| `local_controller_selection` | `rrtstar+dwa` | `dwa_coarse` | 30/30 | 100% | 6,06 ms | **PASS** |
| | `rrtstar+dwa` | `dwa_default` | 30/30 | 100% | **50,28 ms** | **fail G4** |

**Bốn candidate phân biệt, đúng một qua đủ sáu cổng.** Không cặp nào có hai candidate cùng qua,
nên **không phép so nào ra được Decision Card** — và đó là kết quả, không phải sự cố.

### 2.1. Câu hỏi treo từ 08-11 đã có câu trả lời

*Kẹt góc lồi là tính chất của stack A\*+DWA, hay của lấy mẫu thô 7×15?*

Lấy mẫu mịn hơn **7,6 lần** (20×40) mua được **3 điểm phần trăm** success (70% → 73%) và tốn
**5,6 lần** độ trễ (5,26 → 29,40 ms). Cả hai vẫn trượt G3 (cần 95%).

**Là tính chất của stack.** Đây là câu hỏi đã treo từ lượt kiểm 08-11 và là lý do `dwa_coarse`
bị nghi ngờ; nay nó được trả lời bằng dữ liệu, và lời nghi ngờ đó được gỡ: lấy mẫu thô **không**
phải thứ sản xuất ra phát hiện "A\* kẹt góc lồi".

### 2.2. `rrtstar+dwa_default` trượt G4 đúng **0,28 ms**

p99 gộp 50,28 ms trên ngưỡng 50,00 ms — vượt **0,6%**.

Đây là con số cầu xin được "sửa" bằng cách nới `control_period`, và đó **chính xác** là chỗ lệch
đã gỡ ở F0.1. Không làm. Không chạy lại tới khi có số khác. Không đăng ký lại cùng candidate.

Phải nói thẳng giới hạn của kết luận này: biên 0,28 ms nằm trong khoảng mà độ chính xác của phép
đo bắt đầu quan trọng. HĐ-7.2 cho phép suy một chiều — *trượt trên máy benchmark nhanh ⇒ chắc
chắn trượt trên bo mạch đích chậm hơn* — nhưng suy luận đó chỉ vững nếu giá trị thật ≥ 50 ms, mà
ở 50,28 ms thì chưa chắc chắn được điều đó. Nên phát biểu đúng là: **G4 trượt theo số đo được,
biên mỏng, và không có lý do hợp lệ nào để đo lại cho tới khi có kết quả khác.**

Ai muốn một điểm ở giữa thì nước đi hợp lệ là **đăng ký một candidate mới** với lấy mẫu trung
gian, không phải nới cổng.

### 2.3. Ba lý do trượt, ba loại khác nhau

Đáng ghi vì nó cho thấy sáu cổng không phải một cái sàng duy nhất:

- `astar+dwa` (cả hai cấu hình) trượt **G3** — *không đủ thành công*. Vấn đề điều hướng.
- `rrtstar+dwa:dwa_default` trượt **G4** — *quá chậm*. Vấn đề chi phí tính toán.
- Không candidate nào trượt **G2** — nhờ M1, cả bốn đều có 30/30 episode phân biệt.

Trước M1, mọi candidate tất định sẽ trượt G2 trên sảnh này và ba dòng trên sẽ không tồn tại.

---

## 3. Ba lỗi của tôi trong lượt này

### 3.1. Tôi khái quát từ ba mẫu

Probe 3 episode cho `astar+dwa:dwa_default` ra **stuck 3/3**, và tôi báo cáo nó như một tín hiệu
(*"lấy mẫu mịn hơn không cứu được góc lồi, dấu hiệu ban đầu là nó còn tệ hơn"*). Chạy đủ 30 cho
**73% thành công**.

Đó là **đúng loại lỗi mà cả dự án này sinh ra để chặn**, và tôi mắc nó trong khi đang xây thứ
chặn nó. Ba episode không phải bằng chứng về bất cứ điều gì — đó là toàn bộ nội dung của HĐ-7.1
và của lần chạy 100 episode đã sinh ra tấm card nói dối.

### 3.2. `compare.py` ghi đè kết quả của chính nó

Mọi run ghi vào `{profile}_compare`. Phép so thứ hai trong ngày **xoá mất** phép so thứ nhất —
hai câu hỏi khác nhau, một thư mục, và câu trả lời trước biến mất không cảnh báo, vì từ góc nhìn
filesystem thì chỉ là một lần chạy lặp lại.

Tìm được bằng cách mất một kết quả thật (E1). Sửa: `{profile}_{scope}_{hash 8 ký tự}`, băm trên
**tập `candidate_id`** — id đã bao trọn stack và mọi tham số (HĐ-1.3). Chạy lại cùng phép so thì
ghi đè chính nó (đúng); đổi bất kỳ candidate nào thì rơi chỗ khác (cũng đúng); đổi thứ tự gõ đối
số thì **không** đổi thư mục (nếu không, một câu hỏi có hai câu trả lời và chúng được phép bất
đồng). Bốn test khoá cả bốn tính chất đó.

### 3.3. `comparison_report.json` bị gitignore — quên lần thứ hai

Khe whitelist trong `.gitignore` mở cho `decision_card.json`, `manifest.json`,
`measurement_report.json`, `SUPERSEDED.md` — và không cho artifact mới. Mọi kết quả E1/E2/E3 vô
hình với git.

Đây là **lần thứ hai** cùng một lỗ hổng: `measurement_report.json` đã bị quên đúng như vậy hôm
F1. Ghi chú trong `.gitignore` giờ nói ra điều đó, để lần thêm artifact thứ tư có người đọc.

---

## 4. Nghiệm thu M4.4

| # | Tiêu chí | Kết quả |
|---|---|---|
| 1 | Cùng tập `episode_context_id`, bằng assert | ✅ 30 id, cả ba run |
| 2 | Tái lập `decision_utility` tới 6 chữ số | ⏸ cần một phép so — không run nào có |
| 3 | Đủ 6 cổng kèm `n_runs` và `n_distinct_episodes` | ✅ |
| 4 | ΔU và CI không NaN | ⏸ n/a ở nhánh B |
| 5 | `L_ref ≤ path_length + goal_tolerance` | ✅ 43–60 episode thành công mỗi run |
| 6 | `peak_search_nodes ≤ costmap_cells` | ✅ |
| 7 | **Bộ kiểm công bằng xanh trước khi công bố** | ✅ 69 test |
| 8 | Manifest ghi affinity **và** biên độ nhiễu | ✅ sau khi sửa — xem dưới |

**Tiêu chí 8 lộ một lỗ thật.** Nhánh B không ghi manifest, nên biên độ nhiễu không được ghi ở
**đâu cả** — đúng cái bẫy mà HĐ-13 vừa được mở rộng để chặn ở M1. `episode_context_id` không băm
biên độ (HĐ-3.1), nên hai report cùng seed khác σ sẽ giống hệt nhau tới từng context id trong khi
là hai thí nghiệm. Sửa: `comparison_report.identity.sensor_noise`, và ba report đã sinh lại.

Hai tiêu chí treo (2 và 4) chỉ áp dụng cho nhánh A. Theo §8 của plan, *"Decision Card **hoặc**
một bảng cổng nói rõ ai bị loại ở đâu sau bao nhiêu lần chạy — và **cả hai đều là kết quả đạt**"*.

---

## 5. Một điều khoản mới, từ chính M0.2

Ghim nhân giờ là mặc định và luôn lấy `count` nhân **đầu** — tất định. Nên **hai run đánh giá
chạy song song sẽ ghim vào đúng cùng một mask**, giành nhau chính hai nhân đó: mỗi run trở thành
tải nền của run kia và G4 của cả hai đo một cái máy không tồn tại.

Trước khi ghim là mặc định, hai run song song chỉ đơn giản là chậm hơn. Sau M0.2 chúng **làm hỏng
số liệu của nhau**. Đó là một biện pháp bảo vệ sinh ra một mối nguy mới, và nó đáng ghi vào hợp
đồng vì không có gì trong code chặn được: HĐ-7.4 nay ghi luật chạy tuần tự, hoặc `--no-pin` cộng
`taskset` cấp mask rời nhau.

Mọi run của M4 đều chạy tuần tự.

---

## 6. Trạng thái

| Phase | |
|---|---|
| M0.1 commit · M0.2 ghim nhân | ✅ |
| M1 nhiễu theo seed | ✅ |
| M2 `open_hall_v2` + cổng `n_distinct` | ✅ |
| M3 `pipeline.py` + `compare.py` | ✅ |
| M4 phép so đầu tiên | ✅ **theo nhánh B**, ba lần |

**MVP theo định nghĩa của plan: đạt.** Nền tảng đo được, so được, và từ chối kết luận khi dữ liệu
không đỡ. Điều nó nói ra trên sảnh tham chiếu là *đúng một trong bốn candidate đáng đem triển
khai* — và nó nói ra điều đó thay vì xếp hạng bốn thứ trong đó ba thứ không nên chạy.

**MVP theo nghĩa "có một tấm Decision Card": chưa.** Cần hai candidate cùng qua sáu cổng, và tập
candidate hiện tại không có cặp nào như thế trên deployment này. Nước đi hợp lệ duy nhất là
**đăng ký candidate mới** — không sửa map, không sửa mission, không nới cổng.

**Việc chưa làm, theo thứ tự:**

1. **Một candidate thứ năm** nếu muốn có card trên sảnh: lấy mẫu DWA trung gian (ví dụ 12×24) có
   thể nằm dưới ngưỡng G4 mà vẫn giữ 100% của RRT\*. Đó là suy đoán — phải đo.
2. **Kho `warehouse_a_v2` ở mức 1%** (300 episode, ~3 giờ, cần máy rảnh). `n_distinct` của A\*
   trên kho sau khi có nhiễu vẫn là **ẩn số chưa đo**.
3. Nợ cũ chưa động: adapter `MonolithicPolicy`, lưới replan ground truth, `instance_difficulty`,
   `robustness_margin`, API `/decisions`, trang web.
