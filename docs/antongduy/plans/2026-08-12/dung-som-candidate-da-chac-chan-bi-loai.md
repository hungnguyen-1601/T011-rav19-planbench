# Kế hoạch: `stopped_early` — dừng một candidate khi nó **không thể** qua cổng nữa

> **Ngày lập:** 2026-08-12 · **Người lập:** An (cùng Claude) · **Trạng thái:** chờ approve, triển khai sau
> **Nguồn:** yêu cầu của dev sau khi dừng B1 giữa chừng — *"thêm tính năng `stopped_early` khi đã đủ
> bằng chứng để kết luận candidate không thể qua gate. Chỉ dừng sớm cho candidate đã chắc chắn bị
> loại, candidate còn lại vẫn chạy đủ số episode nếu chưa bị gate loại."*
> **Bằng chứng thúc đẩy:** `reports/2026-08-12/tongduyan_b1-kho-warehouse-va-run-bi-ngat.md` —
> 2,85 giờ máy cho một kết quả mà episode thứ 12 đã định đoạt.
> **Tách khỏi** plan 08-12 (`viec-con-lai-sau-mvp-v1.md`) vì đó là một phiên lập kế hoạch khác.

---

## 0. Câu một dòng

Một candidate đã **chắc chắn** trượt cổng thì mọi episode tiếp theo của nó là tiền vứt đi — nhưng
"chắc chắn" ở đây phải là **số học**, không phải thống kê, nếu không tính năng này biến thành cỗ
máy loại nhầm candidate xui.

---

## 1. Vì sao đáng làm — số của chính B1

`warehouse_a_v2`, 2 candidate × 300 episode, dừng tay ở 491/600 sau **2,85 giờ**.

| | `astar+dwa` | `rrtstar+dwa` |
|---|---:|---:|
| Va chạm đầu tiên | seed 3 (**episode #7**) | seed 5 (**episode #12**) |
| G3 hết đường cứu (>15 fail/300) | seed 110 (#221) | seed 109 (#220) |
| Kết cục thật sau 245 episode | fail G2 + G3 | fail G2 + G3 |

**Ở luật G2, cả hai đã bị định đoạt tại episode #12 trên 600.** Phần còn lại — 2,8 giờ — không đổi
một phán quyết cổng nào.

---

## 2. Nhưng nói ngay cái giá, trước khi nói cái lợi

Nếu tính năng này đã có và bật mặc định ở luật G2, run B1 kết thúc ở episode #12 và **ba phát hiện
giá trị nhất của ngày hôm đó không tồn tại**:

| Phát hiện | Cần bao nhiêu episode |
|---|---|
| `n_distinct` của A\* = **85/245** — nhiễu chưa chạm tới kho | hàng trăm |
| 78% cùng kết cục, chỉ **9/72** va chạm là chung — hai stack hỏng trên seed rời nhau | toàn bộ tập ghép cặp |
| Tỷ lệ va chạm ~14–15%, rải đều theo khối seed | hàng trăm |

Cái còn giữ được ở episode #12: *"A\* trên kho hỏng bằng va chạm, không bằng kẹt góc lồi như trên
sảnh"* — vì va chạm đầu tiên rơi vào seed 3.

**Kết luận rút ra, và nó định hình toàn bộ thiết kế:** cổng là *một* mục đích của việc chạy episode,
không phải mục đích duy nhất. Một run còn sinh ra **phân phối** — và phân phối là thứ nói cho ta
biết *vì sao* trượt, thứ quyết định việc tiếp theo làm gì. Nên:

- tính năng phải có **sàn episode tối thiểu** trước khi được phép dừng bất kỳ ai;
- và phải **tắt được**, với một cờ tường minh, cho những lượt mà câu hỏi là *"hỏng thế nào"* chứ
  không phải *"có qua không"*.

---

## 3. Luật dừng — cổng nào cho phép, cổng nào không

Nguyên tắc chặn: **chỉ dừng khi số học chứng minh không đảo được**, không bao giờ vì "trông có vẻ
thua". Xét từng cổng:

| Cổng | Điều kiện dừng | Hình dạng toán học | Được không |
|---|---|---|---|
| **G2** an toàn | `observed_collisions ≥ 1` | **Hấp thụ** — G2 đòi đúng 0, một va chạm không thể bị xoá bởi episode sau | ✅ **chắc chắn** |
| **G3** độ tin cậy | `failures > floor(N × (1 − success_rate_min))` | Đếm đơn điệu; success tốt nhất còn lại là `(N − failures)/N` | ✅ **chắc chắn** |
| **G1** tìm được đường | `no_path_count > floor(N × no_path_rate_max)` | Cùng dạng G3 | ✅ **chắc chắn** |
| **G5** bộ nhớ | `memory_estimate > available_ram_mb` | `peak_nodes` đơn điệu tăng theo episode | ✅ **chắc chắn** |
| **G4** thời gian thực | — | **p99 gộp KHÔNG đơn điệu**: thêm control step có thể **kéo p99 xuống** | ❌ **không có luật đúng** |
| **G6** tương thích quan sát | — | Tĩnh, đã quyết trước episode 1 | n/a |

**G4 phải bị từ chối tường minh trong code, kèm lý do**, chứ không phải bị quên. `p99` là phân vị
trên tập control step gộp; 5.000 step chậm trong 100.000 step đầu vẫn có thể chìm xuống dưới p99 khi
tổng lên 400.000 step. Một luật dừng "p99 hiện tại đã vượt T_cycle" sẽ loại nhầm candidate chỉ vì
nó khởi động chậm.

**Và điều bị cấm dứt khoát:** không dừng ai bằng luật **thống kê** — không "CI của ΔU nằm hoàn toàn
dưới 0", không "đang thua rõ". Đó là **N9 racing / successive halving**, một tính năng khác, thuộc
pha 2, có ràng buộc an toàn riêng (HĐ-9: chỉ loại khi CI nằm **hoàn toàn** dưới 0). Trộn hai thứ vào
một cờ là cách một candidate xui bị loại và không ai truy ra được vì sao.

---

## 4. Bốn bất biến không được phá

### 4.1. Ghép cặp chỉ cần đúng **giữa những candidate còn sống**

Đây là chỗ nguy hiểm nhất của cả tính năng. Nếu A dừng ở 12 và B chạy tới 300, chúng **không còn
chung tập episode** — mà HĐ-7.3 dựng toàn bộ bootstrap ghép cặp trên giả định đó.

Lối thoát đúng: **một candidate bị dừng là một candidate đã trượt cổng**, nên theo kiến trúc hai
tầng (N4) nó **không bao giờ đi vào `score_survivors`**, không có ΔU, không vào Pareto. Ghép cặp chỉ
cần đúng trong tập sống sót.

Nhưng điều đó **không tự đúng** — nó phải được cưỡng chế:

- `check_shared_contexts` hôm nay khẳng định **mọi** candidate chạy cùng tập context. Phải nới thành
  **mọi candidate sống sót**, và lời khẳng định phải in ra rõ nó đang nói về tập nào.
- Một test phải khoá: candidate bị dừng **không** xuất hiện trong bất kỳ phép tính ΔU nào.
- `manifest.episode_contexts` phải là tập của **candidate sống sót** — manifest là thứ người khác
  dựng lại card từ đó, và một tập context lẫn candidate đã dừng sẽ dựng ra card khác.

### 4.2. Không candidate nào bị dừng trước sàn episode tối thiểu

`min_episodes_before_stop`: cờ CLI › profile › **mặc định 30** (Q1). Lý do ở §2 — run còn phải sinh
phân phối, và 30 đủ thấy hình dạng của kiểu hỏng trong khi rẻ so với 300. Giá trị thật đã dùng phải
nằm trong report.

### 4.2b. Acceptance deployment không được dừng sớm, bất kể cờ

`deployment_role: acceptance` ⇒ `--stop-early` bị **từ chối tại chỗ** (Q3). Từ chối, không phải im
lặng bỏ qua: một cờ bị nuốt là một người dùng tin mình đang tiết kiệm trong khi không.

### 4.3. Số liệu của candidate bị dừng **không** so ngang được với candidate chạy đủ

`success_rate` trên 12 episode và `success_rate` trên 300 episode là hai con số không cùng đơn vị
tin cậy. Bảng cổng phải mang `n_episodes` **theo từng candidate**, và UI/report không bao giờ được
xếp hai con số đó cạnh nhau như một bảng xếp hạng.

### 4.4. Dưới 2 candidate qua cổng ⇒ **không có Decision Card**

Không đổi. Yêu cầu của dev nhắc lại điều này, và nó vốn đã là hành vi hiện tại
(`len(evidence) < 2`). Tính năng mới chỉ được làm cho nó **dễ xảy ra hơn**, không được làm nó yếu đi.

### 4.5. `stopped_early` **khác** `interrupted` — không được lẫn

Vừa thêm `interrupted` cho run bị giết (báo cáo 12-08). Hai thứ khác nhau về bản chất:

| | `interrupted` | `stopped_early` |
|---|---|---|
| Ai quyết | máy bị lấy lại / người bấm Ctrl+C | **nền tảng**, trên bằng chứng |
| Nói gì về candidate | không gì cả | **nó không thể qua cổng này** |
| Áp cho | cả run | **từng candidate** |
| Số episode | như nhau cho mọi candidate | **khác nhau giữa các candidate** |

Hai trường riêng, hai vị trí riêng trong report. Gộp chúng là biến *"máy bận"* thành *"candidate
tệ"*.

---

## 5. Lược đồ report

**Theo từng candidate**, trong `candidates[]`:

```json
{
  "candidate_id": "60c8e26fe591",
  "stack_label": "astar+dwa",
  "n_episodes": 30,
  "stopped_early": {
    "gate": "G2",
    "episodes_run": 30,
    "episodes_planned": 300,
    "rule": "observed_collisions >= 1 trong khi G2 đòi đúng 0 — không episode nào sau đó đảo được",
    "evidence": {
      "observed_collisions": 4,
      "first_collision_at": {"seed": 3, "episode_context_id": "54a91f47c4c0"}
    },
    "floor_applied": {"min_episodes_before_stop": 30, "would_have_stopped_at": 7}
  }
}
```

`floor_applied` có mặt vì nó trả lời câu người đọc sẽ hỏi ngay: *"nó biết từ episode 7, sao chạy tới
30?"* — và vì `would_have_stopped_at` là số liệu để sau này chỉnh sàn cho đúng.

**Ở tầng run**, cạnh `sample`:

```json
"stopped_early": [
  {"candidate_id": "60c8e26fe591", "gate": "G2", "episodes_run": 30},
  {"candidate_id": "db26440f6052", "gate": "G2", "episodes_run": 30}
],
"episodes_saved": 540
```

`episodes_saved` để cái giá và cái lợi của tính năng này **đo được**, thay vì được tin.

---

## 6. Chạm vào đâu

| File | Việc |
|---|---|
| `packages/benchmark/planbench_benchmark/pipeline.py` | `simulate` nhận một callback quyết định dừng; bỏ qua các cặp `(context, candidate)` của candidate đã dừng. Ghi một dòng `event: "stopped_early"` vào `run_journal.jsonl` |
| **mới** `packages/decision/planbench_decision/early_stop.py` | Luật số học thuần: `can_still_pass(gate, counters, N, constraints) -> bool`. Không đọc file, không biết simulator — test được bằng số |
| `packages/decision/planbench_decision/gates.py` | Bảng khai cổng nào có luật dừng; G4 mang lý do từ chối |
| `packages/benchmark/planbench_benchmark/selection.py` | Đếm tăng dần trong lúc chạy, gọi luật, gom `stopped_early` vào report; nới `check_shared_contexts` về tập sống sót |
| `scripts/compare.py` | `--stop-early` (mặc định **tắt**), `--min-episodes-before-stop` |
| `packages/schemas/planbench_schemas/task_profile.py` | trường mới `deployment_role` (mặc định `customer`) và `evaluation.min_episodes_before_stop` |
| `profiles/open_hall_v2.yaml` | khai `deployment_role: acceptance` — chuyển phát hiện của Q1 (plan 08-12) từ comment thành trường máy đọc được |
| `.gitignore` | không đổi — vẫn `comparison_report.json` + `run_journal.jsonl` |

**Vướng một chỗ về kiến trúc, phải giải trước khi gõ:** hôm nay `score` đọc **toàn bộ** trace của một
candidate rồi mới `gate_all`. Luật dừng cần bộ đếm **trong lúc** mô phỏng. Hai lối:

- **(a)** `simulate` trả về kết quả từng episode để `selection` cập nhật bộ đếm — rẻ, nhưng bộ đếm
  đến từ **bộ nhớ của tiến trình mô phỏng**, trong khi HĐ-5 nói mọi phán quyết phải tính lại **từ
  trace**.
- **(b)** chấm lại từ trace theo lô (ví dụ mỗi 10 episode) — đắt hơn, nhưng giữ nguyên luật "phán
  quyết đến từ file".

**Đề xuất (b)**, và lý do không phải hiệu năng: (a) mở đúng cái cửa mà HĐ-5 đóng — nếu một phán
quyết cổng có thể đến từ bộ nhớ, thì hai lần chạy có thể bất đồng mà không file nào giải thích được.
Chi phí của (b) nhỏ vì chỉ đọc lại trace đã ghi, và nó chạy song song với việc mô phỏng episode tiếp
theo về mặt ý nghĩa (vài chục ms so với 21 s/episode).

---

## 7. Test phải khoá

1. **Hấp thụ:** va chạm ở episode k ⇒ candidate dừng, `episodes_run == max(k, sàn)`.
2. **Đếm G3:** `floor(N × (1 − min))` failure vẫn chạy tiếp; thêm một cái nữa thì dừng. Kiểm ở đúng
   hai bên biên, không kiểm giữa.
3. **Candidate còn sống chạy đủ N** dù candidate kia đã dừng ở episode 12.
4. **G4 không bao giờ dừng ai** — kể cả khi p99 hiện tại đang vượt T_cycle. Test này là điều khoản
   an toàn, không phải test hồi quy.
5. **Sàn được tôn trọng:** `would_have_stopped_at < min_episodes_before_stop` ⇒ vẫn chạy tới sàn, và
   report ghi cả hai số. Kèm một test cho thứ tự ưu tiên cờ › profile › mặc định 30, và một test
   khẳng định sàn thật đã dùng **có mặt trong report** — không phải chỉ trong tiến trình đã chạy.
5b. **`deployment_role: acceptance` + `--stop-early` ⇒ từ chối tường minh**, không phải bỏ qua im
   lặng. Test khẳng định thông báo nêu lý do, và khẳng định run **không** chạy với dừng sớm bật.
5c. **Mặc định là tắt:** một run không gõ cờ nào phải chạy đủ N cho mọi candidate, kể cả candidate
   đã va chạm ở episode 1.
6. **Candidate bị dừng không vào ΔU**, không vào Pareto, không vào `manifest.episode_contexts`.
7. **`check_shared_contexts` nói về tập sống sót**, và đỏ nếu hai candidate **sống sót** lệch tập.
8. **Dưới 2 survivor ⇒ không card**, kể cả khi cả hai bị dừng sớm.
9. **`--no-stop-early` tái lập chính xác hành vi hôm nay** — cùng loại hàng rào M3 đã dùng: cả
   `test_compare.py` và `test_vertical_slice.py` phải xanh không sửa assertion nào.
10. **Journal ghi sự kiện dừng** như một dòng riêng, phân biệt được với dòng episode.
11. **`stopped_early` và `interrupted` cùng có mặt được** trong một report và không đè nhau.

---

## 8. Phân pha

| Pha | Nội dung | Ước lượng |
|---|---|---|
| **1** | Chỉ **G2**. Hấp thụ, đơn giản nhất, tiết kiệm nhiều nhất (episode #12/600 ở B1). Kèm sàn cài được (mặc định 30), cờ **tắt mặc định**, `deployment_role` + chặn acceptance, lược đồ report, và toàn bộ mục 7 trừ test 2 | **4–5 giờ** |
| **2** | Thêm **G1, G3, G5** — bộ đếm đơn điệu, cùng khung, khác công thức | **1,5–2 giờ** |
| **Không làm ở đây** | Dừng theo **thống kê** (N9 racing / successive halving). Khác bản chất, khác rủi ro, thuộc pha 2 của đề tài và cần điều kiện kích hoạt riêng (episode đắt) | — |

---

## 9. Ba câu hỏi — **dev đã chốt 2026-08-12**

### Q1 → sàn mặc định **30**, người dùng cài được

Nguyên văn: *"sàn bao nhiêu sau này người dùng có thể cài đặt được, trước mắt để giá trị mặc định
là 30."*

Nên `min_episodes_before_stop` là **tham số có mặc định**, không phải hằng số trong code:

```yaml
evaluation:
  min_episodes_before_stop: 30      # mặc định; cờ CLI --min-episodes-before-stop đè lên
```

Thứ tự ưu tiên: cờ CLI › profile › mặc định 30. Giá trị thật đã dùng **phải nằm trong report**
(`stopped_early[].floor_applied.min_episodes_before_stop`), vì hai run cùng profile dưới hai sàn
khác nhau cho hai bộ số liệu khác nhau — cùng họ với lỗ hổng `constraints` mà A4 vừa vá.

### Q2 → **tắt mặc định**, bật bằng `--stop-early`

Đúng đề xuất §2. Một tính năng tiết kiệm phải được **xin**, không được ngầm định: người mất dữ liệu
vì nó sẽ không biết mình đã mất gì.

### Q3 → **cấm hẳn trên acceptance deployment**

Nguyên văn lý do dev đưa: *"cấm hẳn trên acceptance deployment do lợi ích tiết kiệm nhỏ."*

Hai vế đều đúng và chúng cộng lại: ở acceptance deployment *"mọi failure đều là tín hiệu chẩn đoán"*
(Q1, plan 08-12) nên **cần nhiều mẫu chứ không cần phán quyết nhanh**; mà sảnh lại chính là
deployment **rẻ** — số giờ máy cắt được nhỏ. Đánh đổi tệ ở cả hai đầu, nên cấm chứ không để tuỳ chọn.

**Nhưng cấm dựa vào cái gì — đây là điểm phải giải trước khi gõ.** Hôm nay không có trường nào khai
`open_hall_v2` là acceptance deployment; nó chỉ có `success_rate_min: 1.00` cộng một comment. Suy
*"`success_rate_min == 1.0` ⇒ acceptance"* là **suy vai trò từ một con số** — đúng loại suy diễn mà
HĐ-1.4 đã từ chối với `experiment_scope` (*scope khai, không suy*), và vì cùng một lý do: ngày ai đó
khai một kho thật ở 1.00, nó sẽ bị cấm dừng sớm mà không ai hiểu vì sao.

**Đề xuất: thêm một trường khai tường minh vào profile.**

```yaml
deployment_role: acceptance | customer | instrument     # mặc định: customer
```

- `acceptance` ⇒ `--stop-early` **bị từ chối tại chỗ**, kèm thông báo nêu lý do, không phải im lặng
  bỏ qua cờ. Im lặng bỏ qua là cách người dùng tin họ đang tiết kiệm trong khi không.
- Trường này còn trả nợ một chỗ khác: Q1 của plan 08-12 đã phát hiện `open_hall` là **loại thứ ba**
  — không phải khách hàng, không phải dụng cụ — mà phát hiện đó tới giờ chỉ sống trong một comment.
  Decision Card in được vai trò của deployment là điều đáng có riêng.

Nếu dev thấy trường mới là quá tay cho phạm vi này thì phương án dự phòng chấp nhận được là: cấm khi
`success_rate_min >= 1.0`, **kèm comment nói rõ đây là phép suy tạm** và một test khoá lý do — nhưng
đề xuất vẫn là khai tường minh.

---

## 10. Đo tính năng bằng chính nó

Sau khi làm xong, chạy lại B1 trên `warehouse_a_v3` (bản có khai nhiễu — xem báo cáo 12-08 mục 7.1)
**hai lần**: một lần `--no-stop-early`, một lần `--stop-early`. So:

- `episodes_saved` thật là bao nhiêu;
- và **phán quyết cổng có giống hệt nhau không**. Nếu khác một chữ, luật dừng sai — vì mọi luật ở §3
  đều tuyên bố là *không đảo được*, và một luật không đảo được mà đổi kết quả thì nó không phải luật
  đó.

Phép kiểm này rẻ và nó là thứ duy nhất chứng minh tính năng an toàn thay vì nghe có vẻ an toàn.
