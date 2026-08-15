# Báo cáo — `stopped_early`: dừng một candidate khi số học đã chứng minh nó không thể qua cổng

> **Ngày:** 2026-08-12 · **Nhánh:** `plannerselector_p2`
> **Plan nguồn:** `plans/2026-08-12/dung-som-candidate-da-chac-chan-bi-loai.md` (dev đã chốt ba câu hỏi §9)
> **Trạng thái:** làm **cả hai pha** — G2 (pha 1) và G1/G3/G5 (pha 2) — vì chúng dùng chung một khung
> và tách ra sẽ phải quay lại đúng những file đó.
> **Kết quả quan trọng nhất:** tính năng chạy, và **thứ khó nhất không phải luật dừng mà là giữ cho
> phép so ghép cặp không gãy** khi hai candidate có số episode khác nhau.

---

## 1. Ba quyết định của dev, và chúng nằm ở đâu trong code

| Chốt | Hiện thực |
|---|---|
| Sàn mặc định **30**, người dùng cài được | `resolve_stop_floor()`: cờ CLI › `profile.min_episodes_before_stop` › `DEFAULT_MIN_EPISODES_BEFORE_STOP = 30`. Giá trị thật đã dùng đi vào report |
| **Tắt mặc định** | `--stop-early` phải gõ; `run_comparison(stop_early=False)` là mặc định |
| **Cấm hẳn trên acceptance deployment** | Trường mới `deployment_role`; `refuse_early_stop()` ném `AcceptanceFailure` |

Về Q3 tôi làm theo đề xuất trong plan chứ không làm phương án dự phòng: thêm trường
`deployment_role: acceptance | customer | instrument` (mặc định `customer`) và khai
`open_hall_v2` là `acceptance`. Suy vai trò từ `success_rate_min == 1.0` là **suy vai trò từ một
con số** — đúng hình dạng HĐ-1.4 đã từ chối với `experiment_scope`. Trường mới còn trả nợ chỗ
khác: phát hiện *"`open_hall` là loại thứ ba"* của Q1 plan 08-12 tới hôm nay mới chỉ sống trong
một comment, nơi không code nào đọc được.

Từ chối, không nuốt im lặng:

```
acceptance criterion failed: profile 'open_hall_v2' khai deployment_role='acceptance', nên
không được dừng sớm: ở đó mọi failure là một tín hiệu chẩn đoán chứ không phải một thống kê,
và chính các episode là sản phẩm.
```

---

## 2. Luật dừng: cùng một công thức, đánh giá ở tương lai tốt nhất

Toàn bộ `packages/decision/planbench_decision/early_stop.py` xoay quanh một câu:

> Giả sử **mọi episode còn lại đều tốt nhất có thể** — không va chạm, không thất bại, bộ nhớ
> không tăng — rồi hỏi lại chính cổng đó. Nếu vẫn trượt thì không chuỗi episode nào cứu được.

Điều làm cách phát biểu này đẹp hơn dự tính: biểu thức dùng để dự đoán **trùng khít** biểu thức
cổng tự tính. G3 chấm `successes/n`; ở tương lai tốt nhất `successes = N − failures`, nên dự đoán
là `(N − failures)/N` — cùng một phép chia, không có sai số float nào để lệch nhau.

| Cổng | Luật | Vì sao đảo không được |
|---|---|---|
| **G2** | `observed_collisions ≥ 1` | Hấp thụ — G2 đòi đúng 0, không có hạn mức để tiêu |
| **G3** | `failures > floor(N(1−min))` | Đếm đơn điệu tăng |
| **G1** | `no_path > floor(N × max)` | Cùng dạng G3 |
| **G5** | `max(memory_estimate) > RAM` | G5 lấy episode tệ nhất, max chỉ tăng |
| **G4** | *không có luật* | **p99 gộp không đơn điệu** |
| **G6** | *không có luật* | Quyết trước episode một, trong `build_candidates` |

`GATES_WITHOUT_A_RULE` là một dict có nội dung, không phải một chú thích — test đọc nó, nên xoá
một mục sẽ làm đỏ test chứ không âm thầm mở rộng tính năng. Và report in nó ra, để người đọc thấy
cổng nào **không** tham gia dừng sớm.

**Một tính chất phát hiện trong lúc viết, và nó cứu một lỗ hổng thật.** Luật phát biểu theo `N`,
nhưng một run có thể kết thúc ở `n < N` (bị ngắt — xem báo cáo trước). Chứng minh nhỏ:
`failures > N(1−thr) ≥ n(1−thr)` ⇒ `(n−failures)/n < thr`. Nghĩa là candidate bị dừng theo luật-N
**vẫn trượt cổng trên mẫu ngắn hơn nó thật sự có**. Không có tính chất này, một run bị ngắt có thể
chứa một candidate bị dừng sớm mà bảng cổng của chính nó lại ghi *pass* — và toàn bộ lập luận an
toàn ở §3 sụp.

---

## 3. Chỗ khó thật: ghép cặp

Luật dừng là phần dễ. Phần khó là: **nếu A dừng ở 5 episode và B chạy 40, chúng không còn chung
tập episode** — trong khi HĐ-7.3 dựng toàn bộ bootstrap ghép cặp trên đúng giả định đó.

Lối thoát, và nó chỉ đúng nhờ kiến trúc hai tầng của N4:

```
candidate bị dừng  ⇒  đã trượt cổng  ⇒  không vào score_survivors  ⇒  không có ΔU
```

Ghép cặp chỉ cần đúng **giữa những candidate sống sót**. Nhưng điều đó **không tự đúng**, nên nó
được cưỡng chế ở ba chỗ:

1. **`check_shared_contexts(..., among=...)`** — nới về tập sống sót, và **câu nó in ra nói rõ
   đang nói về tập nào**. Một phép kiểm âm thầm đổi thứ nó bảo đảm còn tệ hơn không có phép kiểm.
2. **`_refuse_a_retired_survivor()`** — ném nếu một candidate vừa bị dừng vừa qua đủ cổng. Theo
   §2 điều đó **không thể xảy ra**, nên nó ném chứ không cảnh báo: vi phạm nghĩa là một luật sai,
   không phải một run bất thường. Đây là tiền đề của cả tính năng, được **kiểm** thay vì **giả định**.
3. **`contexts_by_candidate`** — `SweepResult` mang tập episode của từng candidate, và
   `score`/`gate_all` chấm mỗi candidate trên đúng tập của nó. Không suy từ filesystem: một lần
   chạy lại với trace cũ dài hơn còn nằm đó sẽ suy ra sai.

Còn một ca nữa lộ ra khi chạy thử — **cả hai candidate cùng bị dừng**. Câu kiểm lúc đó in
*"no candidate ran any episode"*, sai sự thật: mọi candidate đều đã chạy, chỉ là không ai sống
sót. Sửa thành *"every one of the 2 candidates was retired early, so no ΔU is paired"*.

---

## 4. Đo bằng chính nó — trên trace kho có sẵn

Chạy lại B1 với `--reuse-traces --episodes 40 --stop-early --min-episodes-before-stop 5`:

```
dừng sớm: BẬT, sàn 5 episode (cổng không có luật dừng: G4, G6)
  ⏹ DỪNG SỚM  astar+dwa      G2 — đã quan sát va chạm trong khi G2 đòi đúng 0
  ⏹ DỪNG SỚM  rrtstar+dwa    G2 — đã quan sát va chạm trong khi G2 đòi đúng 0

  astar+dwa    dwa_coarse   2 distinct  success 80%  p99 5.18 ms  fail ['G2','G3']
  rrtstar+dwa  dwa_coarse   6 distinct  success 83%  p99 7.59 ms  fail ['G2','G3']

⏹ 60c8e26fe591  G2 sau 5/40 episode
⏹ db26440f6052  G2 sau 6/40 episode
   episode tiết kiệm: 69
```

**Phán quyết cổng giống hệt run đầy đủ** — cả hai vẫn `fail ['G2','G3']`. Đây là phép kiểm §10 của
plan yêu cầu, và nó là thứ duy nhất chứng minh luật dừng an toàn thay vì nghe có vẻ an toàn: mọi
luật ở §2 tuyên bố *không đảo được*, nên một luật đổi kết quả là một luật sai.

`episodes_saved: 69` được **in ra**, không để người đọc tự tính. Một tính năng đổi dữ liệu lấy giờ
máy phải hiện cả hai vế, nếu không nó sẽ bị đánh giá chỉ bằng vế dễ thấy.

---

## 5. Lược đồ report

Tầng run:

```json
"early_stop": {
  "enabled": true,
  "min_episodes_before_stop": 5,
  "deployment_role": "customer",
  "gates_without_a_rule": {"G4": "p99 gộp không đơn điệu…", "G6": "quyết trước episode một…"},
  "stopped": [{"candidate_id": "60c8e26fe591", "gate": "G2", "episodes_run": 5,
               "episodes_planned": 40, "rule": "…", "evidence": {…}}],
  "episodes_saved": 69
}
```

Từng candidate thêm `n_episodes` và `stopped_early` (null nếu không bị dừng), trong đó
`floor_applied` mang `would_have_stopped_at` — trả lời câu người đọc sẽ hỏi ngay: *"nó biết từ
episode 1, sao chạy tới 5?"*

`n_episodes` **theo từng candidate** là bắt buộc, không phải tiện ích: hai tỷ lệ success trên hai
mẫu số khác nhau không phải một bảng xếp hạng, và người đọc cần mẫu số nằm cạnh tỷ lệ để thấy điều đó.

---

## 6. Bốn quyết định thiết kế đáng ghi

**HĐ-5 giữ nguyên: bộ đếm đến từ trace, không từ bộ nhớ tiến trình.** `_EarlyStopWatch` gọi
`score_episode()` đọc lại file parquet vừa ghi. Lấy số simulator đang giữ sẵn sẽ nhanh hơn và phá
đúng điều HĐ-5 đóng — một phán quyết cổng đến từ bộ nhớ thì không dựng lại được, và hai run có thể
bất đồng mà không file nào giải thích. Tích luỹ từng episode (thay vì đọc lại cả run mỗi lần) giữ
nó tuyến tính: khác biệt giữa vài giây và vài giờ trên sweep 300 episode.

**Hook được hỏi cả trên episode dùng lại trace.** Nếu chỉ hỏi sau episode mới chạy thì
`--reuse-traces` sẽ ra phán quyết khác một run tươi — hai đường tới hai câu trả lời.

**Sự kiện dừng vào journal như một dòng riêng** (`"event": "stopped_early"`). Một candidate rời
run giữa chừng không bao giờ được phép phải **suy ra từ một lỗ hổng trong dãy số episode**.

**Thứ tự cổng cố định.** Một candidate có thể chết ở nhiều cổng cùng lúc; báo cáo cổng theo thứ tự
hợp đồng giữ lý do ổn định giữa các lần chạy, thay vì phụ thuộc phép kiểm nào được viết trước.

---

## 7. Nghiệm thu

| | |
|---|---|
| `tests/test_early_stop.py` | **14 pass** — luật số học thuần, kiểm ở đúng hai bên biên |
| `tests/test_early_stop_run.py` | **15 pass** — cờ tắt mặc định, chặn acceptance, sàn, tập sống sót, journal |
| `tests/test_partial_runs.py` | **6 pass** — journal, run dở, tiền tố ghép cặp |
| Hàng rào M3 | ✅ `test_compare.py` + `test_vertical_slice.py` + `test_measure.py` + `test_gates.py` = **113 pass**, **không sửa một assertion nào** |
| ruff | ✅ sạch (check + format) |

**Full suite chưa chạy** — dev yêu cầu chờ cho phép.

Test đáng nói nhất là hai cái không kiểm tính năng mà kiểm **giới hạn** của nó:
`test_a_slow_candidate_is_never_retired` (G4 không bao giờ dừng ai, kể cả p99 đang 5.000 ms) và
`test_a_retired_survivor_is_refused_outright`. Cả hai là điều khoản an toàn, không phải test hồi quy.

---

## 8. Ba việc còn lại

1. **`tests/api/test_api_decisions.py` vẫn 3 test đỏ** — lỗ hổng có sẵn từ commit `79f7b04` (A4),
   đã kiểm bằng stash ở báo cáo trước: `success_rate_min = 1.00` làm anchor `good == bad == 1.0`.
   **Tính năng này không sửa nó và cũng không làm nó tệ hơn**, nhưng giờ nó đứng cạnh một trường
   `deployment_role: acceptance` mới — và câu hỏi *"metric có cổng ở ngưỡng hoàn hảo thì chấm điểm
   trên phần dôi nào"* là câu hỏi của **cùng một vai trò deployment đó**. Hai việc nên quyết cùng lúc.

2. **`min_episodes_before_stop` để ở gốc profile**, không lồng trong khối `evaluation` như plan
   phác. Không có khối `evaluation` nào tồn tại, và tạo một khối cho đúng một trường là ngoại suy.
   Nếu sau này có thêm tham số cùng họ thì gom lại, kèm bump contract MINOR.

3. **Chưa đo trên run thật.** Phép kiểm ở §4 chạy lại từ trace có sẵn, không phải một sweep tươi
   dài nhiều giờ. Phép thử đúng nghĩa là chạy `warehouse_a_v3` (bản khai nhiễu — xem báo cáo B1
   mục 7.1) hai lần, `--stop-early` và không, rồi so **phán quyết cổng phải trùng khít**. Đó là
   §10 của plan, và nó cần deployment mới trước.
