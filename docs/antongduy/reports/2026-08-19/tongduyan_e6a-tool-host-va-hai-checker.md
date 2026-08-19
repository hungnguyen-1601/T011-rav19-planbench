# E6a — tool host thật và hai mechanism check chạy được

**Ngày:** 2026-08-19 · **Nhánh:** `tongduyan_3` · **Plan:** `docs/antongduy/plans/2026-08-18/tang-giai-thich-vi-sao.md` §5 (E6)

**Trạng thái:** xong phần E6a, **chưa commit**. Không đụng web.
Full suite chưa chạy.

---

## 1. Vì sao chỉ làm E6a

An hỏi "tiến hành E6 nếu không có blocker". Có blocker thật, khảo sát cụ thể:

| Checker | Trạng thái | Bằng chứng |
|---|---|---|
| `gap_vs_footprint` | **làm được** | map, footprint, inflation đều có (`services/simulator/grid.py`, `episode_runner.py:56`) |
| `latency_vs_expanded_nodes` | **làm được, sau khi sửa card** | xem mục 3 |
| `replay_global_plan` | **chặn** | thiếu `planning_inputs`, `planner_parameters`, `planner_implementation_version` |
| `rrt_convergence` | **chặn** | thiếu thêm `seed_set` |

`grep PlanningInputEvidence` ngoài package explanation: **không có kết quả**. Writer
sidecar E4.5 chưa tồn tại, mà plan lại hoãn E4.5 sau H4/H6.

Gate harness còn chặn hai lớp nữa: hidden packet cần run planted có sidecar, và
`OFFICIAL_GOLDEN_READY=False` từ chối preregister. Chưa có `AnalystBundle` thật
nào để chấm.

An chọn **E6a** — host thật + hai checker làm được. Đó cũng là phần duy nhất kiểm
chứng được ngay.

---

## 2. Ba trách nhiệm tách rời

```
ToolSession.admit()      →  đã có từ E5, module này không viết lại một dòng nào
EvidenceSource           →  một method cho mỗi thứ tool cần
checkers.*               →  hàm thuần, không biết request id, không biết card
ToolHost                 →  chỗ duy nhất ba thứ gặp nhau, và chỗ duy nhất
                            được phép sinh ToolResult
```

**Checker là hàm thuần của bằng chứng.** Không đọc file, không mở thư mục run,
không biết session là gì — host lấy bằng chứng rồi truyền vào. Nhờ vậy ai có
input cũng chạy lại được mà không cần quyền truy cập nền tảng, và test được mà
không cần một run trên đĩa.

**Checker trả phán quyết, không trả kết luận.** `supported`/`refuted`/
`inconclusive` về đúng một mệnh đề, cộng các measurement mà card khai. Nó có
thành claim hay không là việc của promotion matrix, và lên tới mức nào thì phụ
thuộc trần card, provenance và known unknowns của packet — ba thứ checker không
biết và không nên biết.

**Vắng mặt có mã, không bao giờ có số 0.** Mọi đường không có bằng chứng đều trả
`not_checkable` kèm failure code từ card hoặc từ `HOST_FAILURE_CODES`.

---

## 3. Sửa card `latency_vs_expanded_nodes` — bắt buộc, không phải tuỳ chọn

Card E5 viết: *"Ticks carrying larger expansions took correspondingly longer, over
this run's recorded replans."* Khi đi hiện thực mới thấy **không tính được**.

`TRACE_SCHEMA` của HĐ-5 (`services/simulator/trace.py:88`) có
`planner_latency_ms` **mỗi dòng** và **không có cột expanded nodes** nào. Schema
đó là một trong ba khoá cứng contract — không được đụng. Nên bản per-replan mà
card hứa không thể tính từ thứ mà run thực sự ghi, và làm gần đúng nó đồng nghĩa
với bịa số.

Cái **tính được** là liên hệ **giữa các episode** của một candidate: episode nào
search mở rộng nhiều node hơn thì ghi nhận latency cao hơn. Yếu hơn, thật, và vẫn
trần `associated`. Card nay nói đúng điều đó:

| | Trước | Sau |
|---|---|---|
| Đơn vị | replan tick | episode |
| `required_evidence` | `trace`, `replan_rows` | `episode_expanded_nodes`, `episode_latency` |
| measurement | `n_replans` | `n_episodes` |
| argument | candidate + episode (tuỳ chọn) | chỉ candidate |
| failure modes | `no_replan_rows`, … | `expansion_counts_missing`, `insufficient_episodes`, `no_variation_to_rank` |

**Và nó nằm trong phạm vi một candidate.** Benchmark đã tách sẵn expanded node của
grid search khỏi tree size của sampling planner (`peak_search_nodes` /
`peak_tree_nodes`) vì hai thứ đếm hai đại lượng khác nhau. Xếp hạng cái này với
cái kia giữa các candidate là đo đơn vị, không phải đo run.

Ba câu ghi thẳng vào `notes` của card để người sau không phải suy lại.

---

## 4. Hai checker

### `gap_vs_footprint`

So `narrowest_passage_m` — cross-section hẹp nhất **bị chặn hai bên** — với
`robot_radius + inflation_radius`. Không đụng tới lower bound: "ít nhất 0.3 m"
không chứng minh được "hẹp hơn 0.74 m", và bản detector trước từng với tay sang
nó chính là với sang kết luận duy nhất nó không đỡ được.

Route mà map chưa từng chặn hai bên ⇒ **không có phán quyết nào**, `CheckerRefusal`,
host dịch thành `ambiguous_passage_geometry`. Không phải `inconclusive` kèm một
con số bịa.

Passage đủ rộng ⇒ **`refuted`**, không im lặng. "Hình học ổn" là một phát hiện, và
nó giết một giả thuyết.

Điểm đáng nói: check này **về cấu hình, không về robot**. Cùng robot, cùng lối đi,
đổi inflation từ 0.48 xuống 0.30 thì phán quyết đảo. Có test.

### `latency_vs_expanded_nodes`

Spearman chứ không Pearson: câu hỏi là hai thứ có đi cùng nhau không, chứ không
phải có tuyến tính không, và một episode chạy lồng không được tự mình gánh cả
tương quan. Rank có xử lý ties (trung bình), nếu không thì Spearman không xác định.

- `< 8` episode ⇒ từ chối. Ít hơn thế là cái hình mà một nắm điểm tình cờ tạo ra.
- Một cột hằng ⇒ **`None`**, không phải 0.0. Hai thứ chưa từng so hạng được với
  nhau; báo "không có liên hệ" là một phát hiện về dữ liệu không thể sinh ra phát
  hiện đó.
- Luật một chiều: `rho >= 0.4` ⇒ supported. Rho âm mạnh ⇒ **refuted** — search lớn
  mà chạy *nhanh hơn* là bằng chứng chống lại mệnh đề, không phải liên hệ mạnh ủng
  hộ nó. Có test.

---

## 5. `ReportEvidence` — đọc từ report thật

Thêm hai cột vào episode row lúc chấm (`selection.py`): `peak_search_nodes` và
`peak_tree_nodes`, giữ nguyên hai cột như HĐ-6 đã tách. **Không cộng lại.**

`ReportEvidence._node_column()` chọn cột mà candidate thực sự dùng, và trả `None`
khi **cả hai** đều có số dương: candidate khai cả frontier lưới lẫn cây sampling là
candidate mà reader này không có luật, và chọn bừa một cột là đoán được trình bày
như đo. Có test.

Latency dùng `p99_latency_ms` — con số control-tick gộp. Mỗi replan ghi dòng
control-step riêng mang latency của global planner (ghi chú `replan_count` của
HĐ-6), nên episode có search lớn sẽ lộ ra ở đó. Nó là p99 trên tick chứ không phải
wall time của riêng search — thêm một lý do nữa để trần card là `associated`.

---

## 6. Giới hạn còn lại, nói rõ

**Chữ ký host là tuyên bố ý định, chưa phải bằng chứng.** `implementation_ref` là
thứ caller khai. Trong một process, thứ thực sự ràng buộc result vào round vẫn là
request đã admit — test E6 kiểm lại đúng điểm này: một session lạ từ chối result
của host với `unknown_request`. Chữ ký chỉ thành trọng yếu khi result đi qua ranh
giới process, và `host.py` là chỗ sẽ phải làm việc đó.

**`AWAITING_SIDECAR`** là một `frozenset` chứ không phải điều kiện rải rác trong
dispatch, để bỏ một tên khỏi đó là một diff nhìn thấy được.

---

## 7. Chưa làm

| Việc | Vì sao |
|---|---|
| `replay_global_plan`, `rrt_convergence` | cần planning input ghi lúc chạy — **E4.5** |
| Gate harness chạy AnalystBundle | cần hidden packet (E4.5) + bundle từ nhóm AI |
| Hidden suite | platform giữ, không nằm trong repo |
| Endpoint HTTP cho analysis round | cùng nhóm quyết định với **E4.1** |
| Web | không đụng |

---

## 8. Kiểm chứng

- `tests/test_explanation_e6.py` — **24 test**.
- Toàn bộ test explanation: **405 passed** (12 file). API: **7 passed**.
- `tests/test_explanation_report_wiring.py` chạy trên report thật: **5 passed**
  sau khi thêm hai cột.
- `ruff check` + `ruff format` sạch.
- **Full suite chưa chạy.**
