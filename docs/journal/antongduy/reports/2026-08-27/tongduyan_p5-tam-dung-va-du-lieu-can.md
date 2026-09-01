# P5 — tạm dừng: đã làm được gì, chưa làm được gì, và cần dữ liệu gì

Ngày 2026-08-27 · nhánh `tongduyan_analyst-episode` · worktree `P-011-merge`

Báo cáo này viết theo lệnh tạm dừng. Chi tiết kỹ thuật nằm ở
`tongduyan_ai-analyst-theo-episode.md` (mục P5 phần 1–4); đây là bản tổng kết
trạng thái và **một yêu cầu dữ liệu cụ thể**.

---

## 1. Đã làm được

### P0–P6 của plan: xong, đã merge

Toàn bộ phần code của plan `ai-analyst-theo-episode.md` đã xong và merge vào
`main` (commit `e122494`), full suite đúng 13 waiver pre-existing.

### P5 — hai lỗi tìm ra từ dữ liệu thật, đã sửa

**Rò id candidate vào prompt.** Lượt chạy thật đầu tiên (1,00 USD) cho ra câu
như *"The local_controller of `e1251e42a20b` experienced a latency spike"* —
hash định danh candidate mà model **chưa bao giờ được cho xem**. Năm chỗ rò
trong `episode_view.py`; chỗ tệ nhất là `identifiers` nhận id làm **tên hợp
lệ**, nên rule 2 cho câu chứa hash đi qua. Sửa cả năm. Đếm rò 38 → 0. Thêm 2
răng chốt hai hướng ⇒ bộ răng **22/22 cắn**.

**Hard constraint đếm nhầm thứ.** Ba veto đếm `outcome.blocked` — tức đếm rule
**bắn**. Lượt chạy đo 55 lần rule 2 bắn trên trần 0, nghe như thảm hoạ; thực ra
là 55 câu guard **đã gỡ**. Arm bị phạt vì cư xử đúng. Sửa: mọi veto đọc trên
proposal **giữ lại**, đổi tên `*_in_final`; ba số cũ đổi thành `*_blocked` và
chỉ đọc là công sức guard. Thêm veto thứ tư `candidate_ids_in_final`. Có test
cưỡng chế hậu tố `_in_final`, và cưỡng chế mọi tên veto phải là tên scorer thật
sự phát ra.

Việc sửa định nghĩa **sau khi thấy dữ liệu** ghi thẳng trong docstring của
`EpisodePreregistration`, kèm lý do: định nghĩa cũ sai trên chính điều khoản của
nó, không phải sai vì số xấu — nó đọc y như vậy nếu con số có đẹp; và sửa
**trước khi** bất kỳ arm nào được chọn.

### P5 — hai stage đã chạy trên view sạch

| Stage | Cấu hình | Vòng | USD | Vi phạm veto |
|---|---|---|---|---|
| 1 | 6 arm × 12 episode × 1 lượt | 72/72 | 0,87 | **0** |
| 2 | 2 arm × 12 episode × 3 lượt | 72/72 | 0,89 | **0** |

Stage 1:

| Arm | Abstain | Proposal giữ | Guard gỡ | Tỷ lệ gỡ |
|---|---|---|---|---|
| `ep_b1` | 10/12 | 2 | 12 | 0,86 |
| `ep_shortlist` | 6/12 | 11 | 10 | 0,48 |
| `ep_knowledge` | 7/12 | 6 | 13 | 0,68 |
| `ep_shortlist_knowledge` | 4/12 | 8 | 13 | 0,62 |
| `ep_no_union` | 4/12 | 12 | 9 | **0,43** |
| `ep_run_context` | 8/12 | 6 | 12 | 0,67 |

Stage 2 (`ep_b1` vs `ep_no_union`, 3 lượt): `ep_b1` abstain 28/36, giữ 11, gỡ
34, tỷ lệ 0,76. `ep_no_union` abstain 20/36, giữ 21, gỡ 36, tỷ lệ **0,63**. Đếm
thô đảo chiều so với stage 1; tỷ lệ thì không.

Luật chọn arm của preregistration cho ra **4** arm đủ điều kiện cho **2** ghế,
mà không nói cắt thế nào. Đã ghi tie-break thành amendment (baseline luôn qua +
ít guard-gỡ nhất + hoà xét theo tên) thay vì chọn bằng mắt.

### Công cụ mới

| File | Việc |
|---|---|
| `scripts/score_episode_stage.py` | Đọc artifact, in veto / tỷ lệ gỡ / chi phí / per-cluster, tự áp luật chọn arm. Tách khỏi runner vì runner tiêu tiền. |
| `scripts/blind_rubric_sheet.py` | Sinh sheet chấm tay **không mang tên arm**; thứ tự mục sinh từ hash danh tính của chính mục đó, không xáo lại được. |
| `scripts/compare_with_imported.py` | `compare.py` + nạp plugin từ DB deployment (**read-only**). |
| `tests/test_episode_experiment_scoring.py` | 5 test cưỡng chế định nghĩa veto. |

### Đã ghi nhận, chưa endpoint nào đo

`ep_b1` abstain 10/12 (stage 1) và 28/36 (stage 2), **toàn bộ** lý do là
`quantity_in_statement`: model viết câu có số, guard gỡ sạch, không còn gì để
nộp. Đây là prompt baseline không nói rõ "câu không được mang số", không phải
model kém. Ứng viên sửa rẻ nhất trong cả bảng.

---

## 2. Kết quả: cái gì trả lời được, cái gì không

**Trả lời được.** Không arm nào vi phạm veto nào trên 144 vòng, trong đó rò id
= 0. `ep_no_union` để guard phải sửa ít nhất theo tỷ lệ (0,43 rồi 0,63) và
abstain ít nhất. Chi phí ~0,012 USD mỗi episode mỗi arm với o4-mini.

**Không trả lời được — blocker.** Endpoint chính
`contrast_holds_up_rate_cluster_level`. Trên 144 vòng, đúng **1** proposal sống
sót mang register `contrast`. Không phải model kém: dựng lại 16 packet từ các
run đã ghi thì có **1** contrast strength `support` trên 36 contrast. Hợp đồng
bằng chứng đòi `contrast_support`, mà packet gần như không chứa cái đó.

---

## 3. Chưa làm được

| Việc | Trạng thái |
|---|---|
| Chấm tay rubric r0.1.0 | Sheet đã sinh (84 + 80 mục), **chưa chấm** |
| Endpoint chính | **Không đo được** trên dữ liệu hiện có |
| P2.5 traits arm | Chưa làm — cần anh ký bộ traits |
| Vòng revise + tool call scope episode | Chưa làm — `run_episode_round` vẫn một lượt |
| `SpendLedger` / `InFlightRegistry` bền qua restart | Chưa — vẫn trong bộ nhớ |

---

## 4. Cần anh tạo dữ liệu — đặc tả chính xác

### Vì sao tự dò không ra

Đếm trên **150 episode** (120 đã ghi + 30 vừa sinh):

| Run | Contrast support | Người thắng từng episode | Dùng được? |
|---|---|---|---|
| `demo_hall_global_planner_selection` | 0/30 | một bên thắng cả 30 | không |
| `sudden_stop_v5_local_controller_selection` | 0/30 | một bên thắng cả 30 | không |
| **`sudden_stop_v6_full_stack_selection`** | **11/30** | **10 / 11 / 9 hoà** | **được** |
| `sudden_stop_full_stack_selection` (mới sinh) | 30/30 | VFH+ thắng cả 30 | không |
| `sudden_stop_4_full_stack_selection` (mới sinh) | 30/30 | VFH+ thắng cả 30 | không |
| `sudden_stop_v5_full_stack_selection` (mới sinh) | 30/30 | VFH+ thắng cả 30 | không |
| `sudden_stop_3_full_stack_selection` (mới sinh) | — | 0/2 candidate qua cổng | không |

0/30 vô dụng vì không có gì để giải thích. **30/30 cũng vô dụng**: cả 30 episode
giống hệt nhau — cùng người thắng, cùng detector (`stuck_cluster` bắn ở DWA,
không bắn ở VFH+). Analyst viết một câu rồi lặp 30 lần được điểm tuyệt đối, và
mọi arm đều gần trần nên không phân biệt được arm nào hơn arm nào.

Chỉ `sudden_stop_v6` dùng được, và nó là **một** cluster. Endpoint đọc theo
cluster, nên một cluster là một quan sát.

### Cái tôi cần: **3 run**, mỗi run một map khác nhau

Mỗi run = 1 task profile + 1 cặp candidate + 30 paired episode. Điều kiện, theo
thứ tự quan trọng:

**(1) Bắt buộc — phải có decision card.** Cả hai candidate qua đủ sáu cổng.
Không card ⇒ không `comparison_pair` ⇒ không dựng được packet nào.
`sudden_stop_3` chết ở đây.

**(2) Bắt buộc — người thắng phải trộn.** Không bên nào thắng quá ~60% số
episode, và có ít nhất vài episode **hoà** (|Δutility| < 0,005). Hình mẫu là v6:
10 thắng / 11 thắng / 9 hoà.

**(3) Bắt buộc — detector bắn một bên ở khoảng 1/3 đến 1/2 số episode.** Phần
còn lại bắn cả hai bên hoặc không bên nào. v6 là 11/30. Nếu 30/30 thì hỏng như
trên.

**(4) Rất nên có — đôi khi detector bắn ở phía *thắng*.** Đây là bẫy cần thiết:
một arm nhầm "có detection" thành "đây là lời giải thích" sẽ bị bắt tại chỗ. Nếu
detection luôn nằm ở phía thua thì không phân biệt được arm đọc hiểu với arm
đoán.

**(5) Nên có — vài episode không có contrast support nào.** Để đo
`abstention_correctness`: arm đúng phải **từ chối** ở đó, arm tệ vẫn viết bừa.

### Cụ thể hoá cho dễ làm

Cặp candidate: giữ nguyên **`astar+dwa:dwa_coarse`** vs
**`astar+org.vinai.vfh-plus:org.vinai.vfh-plus_defaults`**, scope
`full_stack_selection`, 30 episode. Cặp này đã chứng minh sinh được contrast
support; biến số duy nhất còn lại là **map**.

Điều kiện về map, nói theo hành vi: **map mà DWA-coarse bị kẹt *đôi khi*** — cỡ
30–50% số episode — chứ không phải luôn kẹt (3 map tôi vừa thử) và không phải
không bao giờ kẹt (3 run cũ). Map `b92f3f964633__v1` của `sudden_stop_v6` đang ở
đúng ngưỡng đó; tôi cần **thêm 2 map nữa cùng ngưỡng, khác bố cục**.

Nếu anh thấy cách khác dễ hơn để chạm ngưỡng đó — chỉnh nhiễu cảm biến trong
profile, chỉnh mật độ vật cản, chỉnh ngưỡng cổng — cũng được. Tôi cần **kết quả
hành vi**, không cần cách làm cụ thể.

### Giao cho tôi thế nào

Chỉ cần **task profile trong `planbench.db`** (như `sudden_stop_v6`) + file map
trong `maps/custom/`. Cho tôi biết **id task profile**; tôi tự đọc DB read-only,
tự chạy `compare_with_imported.py` sinh run và trace, tự dựng packet, tự đo.
Không cần anh chạy comparison.

### Nếu không có map như vậy

Phương án lùi, không cần dữ liệu mới: kết luận P5 chỉ trên phần đo được (veto,
tải guard, abstain, chi phí) cộng chấm tay 164 mục đã sinh, và ghi rõ endpoint
chính không đo được trên dữ liệu này cùng lý do. Không tiêu thêm đồng nào.

---

## 5. Chi tiêu và trạng thái nhánh

| Lượt | USD |
|---|---|
| Stage 1 lần đầu (view rò id — **bỏ**) | 1,00 |
| Stage 1 chạy lại | 0,87 |
| Stage 2 | 0,89 |
| **Tổng** | **2,76** / trần 3,00 |

Sinh dữ liệu bằng sim: **0 USD**, ~28 s mỗi episode-pair.

Nhánh `tongduyan_analyst-episode` đứng trước `main` **11 commit**, cây sạch. Run
sinh ra nằm ở scratchpad, **không** ghi vào `artifacts/runs` của anh; DB chỉ mở
read-only.
