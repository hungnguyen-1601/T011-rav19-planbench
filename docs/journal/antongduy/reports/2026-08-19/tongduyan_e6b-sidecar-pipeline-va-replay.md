# E6b (một phần) — nối sidecar vào pipeline, và replay qua planner injection

**Ngày:** 2026-08-19 · **Nhánh:** `tongduyan_3` · **Plan:** §5 (E6b)

**Trạng thái:** blocker 1 và 2 đã gỡ, **chưa commit**. Full suite chưa chạy.
Blocker 3 (`rrt_convergence`) vẫn còn — nêu rõ ở mục 5.

---

## 1. Blocker 1 — chưa có dữ liệu

`run_stack` nhận `planning_recorder` từ E4.5, nhưng **không nơi nào** trong
`packages/benchmark/`, `services/`, `scripts/` truyền vào. Writer tồn tại, dữ liệu
không. Kiểm chứng bằng grep trước khi sửa.

**Địa chỉ: cạnh trace, cùng suffix.** `planning_inputs_path()` uỷ thác thẳng cho
`trace_path()` rồi đổi đuôi:

```
<root>/<evidence_class>/<fingerprint>/<candidate>/<episode>.parquet
<root>/<evidence_class>/<fingerprint>/<candidate>/<episode>.planning_inputs.jsonl
<root>/<evidence_class>/<fingerprint>/<candidate>/<episode>.snapshots/attempt-001.json
```

Không phải cây song song. Class + conditions fingerprint chính là thứ ngăn run
oracle ghi đè run production (H9A); sidecar để chỗ khác thì phải suy lại luật đó và
sớm muộn sẽ suy sai. Test cũ `list(tmp_path.iterdir()) == [tmp_path / "oracle"]`
vẫn xanh — dấu hiệu địa chỉ chọn đúng.

**`execution_environment_ref`**: `git:{resolve_git_sha()}`, `lru_cache(1)` — cùng
một giá trị cho mọi episode của một sweep, và shell ra git vài nghìn lần là một
phần đo được của thời gian chạy. Ném lỗi chứ không thay placeholder: admission của
replay kiểm field này **trước** mọi field khác.

**Mặc định bật.** Sweep chạy không có nó sinh ra những run mà cơ chế vĩnh viễn
không xác minh nổi quá mức `associated`, và **không gì tại thời điểm đó nói ra
điều ấy**. Cờ `record_planning_inputs=False` để cho script chẩn đoán, không phải
núm chỉnh hiệu năng.

**Phát sinh: `StackRun.replan_attempts`.** `close()` cần số đếm **của runner**, mà
pipeline chấm cố ý không dựng `EpisodeMetrics` (HĐ-5: file trace là đầu vào duy
nhất). Nên bộ đếm duy nhất tồn tại lại nằm đúng chỗ không với tới được. Nay
`StackRun` phơi nó ra.

**RLE — đo trước khi chọn.** Map thật là `warehouse_a` 800×500 = 400.000 ô:

| | |
|---|---|
| JSON mảng ô | **1.020 KB**/attempt |
| Run-length encoded | **21,6 KB** (2.575 run) |
| Tỉ lệ | **47×** |

Occupancy grid gần như toàn những đoạn dài cùng giá trị. Không nén thì sidecar tốn
đĩa hơn cả trace nó nằm cạnh — và đó là cách một tính năng ghi nhận bị người ta
tắt đi. Checksum vẫn tính trên **ô đã bung**: băm cách lưu thì hai writer cùng
grid mà chia run khác nhau sẽ bất đồng về việc có phải cùng một thế giới.

---

## 2. Blocker 2 — replay qua injection (lối 2 An chọn)

**`planbench_explanation.replay`** định nghĩa cái tối thiểu:

```python
class ReplayPlanner(Protocol):
    def replay(self, request: ReplayRequest) -> ReplayPlan: ...
```

`ReplayRequest` phẳng và nguyên thuỷ — cells, hình học, hai toạ độ, tên planner +
tham số + seed. Truyền **đối tượng grid** thì module này đã có ý kiến về loại grid
nào, đúng thứ ranh giới cần tránh. Có test đọc source và khẳng định
`planbench_simulator` và `planbench_planning` **không xuất hiện** trong file.

**`planbench_simulator.replay_planner`** là nửa còn lại: dựng `MapData` +
`OccupancyGrid` từ cells, tra planner theo tên trong map **đóng**, đặt config +
seed, chạy, băm path.

Ba điểm có nội dung:

**Grid dựng lại, không suy lại.** Snapshot giữ ô **sau** inflation và standing-room
relaxation. Adapter inflate thêm lần nữa là plan trên một thế giới run chưa từng
thấy, rồi báo phân kỳ như thể run không tái lập được.

**Harness khai danh tính của chính nó.** `planner_fingerprint` tính từ thứ adapter
thật sự cấu hình, `execution_environment_ref` là build đang chạy. Vọng lại giá trị
của record thì phép so luôn tự đồng ý — mà phép so ấy là thứ duy nhất đứng giữa
"cơ chế đã được xác minh" và "một planner nào đó trả cùng đáp án".

**Map planner đóng.** Tên không có trong map ⇒ `ReplayUnavailable("planner_not_in_harness")`.
Lấy cái gần nhất là replay một thuật toán khác. Sampling planner không có seed ⇒
`ReplayUnavailable("seed_not_recorded")`.

**Kết luận replay theo outcome đã ghi**, sau khi admission chấp nhận toàn bộ field:

| Ghi được | Replay ra | Verdict |
|---|---|---|
| `no_path` | `no_path`, cùng `failure_code` | **supported** — query thật sự bất khả thi với stack này |
| `path` | `path`, cùng checksum | **refuted** — planner tìm được đường, nên chuyện hỏng không phải vì query bất khả |
| bất kỳ lệch nào | | `not_checkable` — bằng chứng về **harness**, không phải về run |

---

## 3. Một test sai tiền đề, giữ lại thành hai

Test đầu tôi viết dùng planner kịch bản `RefusesAfterTheFirst` để tạo `no_path`.
Nó **hỏng** — và hỏng đúng: planner đó từ chối theo **bộ đếm lời gọi**, còn A* thật
trên cùng costmap tìm được đường qua cửa còn lại. Replay báo phân kỳ.

Đó là hệ chạy đúng thiết kế, nên tôi tách thành hai:

- `test_a_recorded_refusal_replays_to_a_supported_mechanism` — dựng tường thật
  ngang bản đồ 12×12, **chạy A* thật xác nhận nó thật sự bất khả** trước khi ghi,
  rồi replay ⇒ `supported`;
- `test_a_refusal_the_planner_does_not_reproduce_is_not_a_verdict` — giữ nguyên
  planner kịch bản, khẳng định `replay_did_not_reproduce`. Đây chính là hành vi
  ngăn một planner bị stub hoặc trôi phiên bản chế ra một cơ chế "đã xác minh".

---

## 4. `AWAITING_SIDECAR` co lại

Từ `{replay_global_plan, rrt_convergence}` xuống `{rrt_convergence}`. Host không có
planner injected vẫn trả `checker_not_implemented` cho `replay_global_plan` — không
phải lỗi của run, mà là host được dựng thiếu nửa biết chạy lại query.

---

## 5. Chưa xong — blocker 3 và phần sau

| Việc | Vì sao |
|---|---|
| **`rrt_convergence`** | Cần chạy lại **tập seed ở nhiều mức budget** để đo tỉ lệ chạm hành lang. Sidecar ghi **một** seed của attempt, không ghi seed set của deployment. Cần thêm nguồn evidence hoặc hạ card. **Chờ An chốt hướng.** |
| Run planted có sidecar | Một lượt chạy, cho `OFFICIAL_GOLDEN_READY` |
| Gate harness | Cần AnalystBundle nhóm AI + hidden suite |
| Nối `SimulatorReplayPlanner` vào host thật lúc phục vụ | Cùng nhóm quyết định với **E4.1** (dựng packet lúc nào) |
| Web | Không đụng |

---

## 6. Kiểm chứng

- `tests/test_explanation_e6b.py` — **15 test** mới, gồm replay end-to-end từ file
  trên đĩa và test khẳng định tầng giải thích không import planner.
- `tests/test_evidence_class_integration.py` — **+5 test** pipeline: sidecar ghi
  cạnh trace, cùng class/fingerprint, mọi record resolve được snapshot, grid lưu
  dạng encoded, và cờ tắt được.
- Toàn bộ test explanation: **465 passed** (15 file).
- `test_nav_stack` + `test_replanning` + API + test_bench: **82 passed, 1 skipped**.
- `ruff check` + `ruff format` sạch trên mọi file tôi đụng.
- **Full suite chưa chạy.**

---

## 7. Blocker 3 — `rrt_convergence`

**Quyết định: thêm nguồn evidence, không hạ card.** Hạ card giữ nguyên cái tên
"rrt_convergence" mà trả lời một câu yếu hơn — đúng kiểu sai lệch tầng này sinh ra
để chặn.

**Nó không phải replay.** Replay tái hiện một attempt; câu hỏi sampling là *ở
budget đã cấu hình, planner có tìm ra hành lang chỉ đôi khi không*. Trả lời được
thì phải chạy cùng query đó qua **tập seed** ở **hơn một budget** rồi nhìn tỉ lệ.

**Seed set lấy từ đâu.** Không có trong report — episode ở đó là hash context.
Không nhận từ caller — đúng cái giá trị tự khai mà `EvidenceIdentity` vừa phải bỏ.
Nguồn đúng là **chính các sidecar của run**: mỗi episode ghi seed nó đã dùng.
`convergence_evidence()` quét thư mục sidecar của candidate và gom lại.

**Budget preregistered**: `BUDGET_MULTIPLIERS = (1.0, 4.0)`, hằng số trong module.
Budget thứ hai chọn sau khi thấy kết quả lần một là budget chọn để tỉ lệ tăng.

**Ba kết cục, chỉ một là cơ chế:**

| Tỉ lệ ở budget | Ở 4× | Verdict |
|---|---|---|
| ≥ 0.9 | — | **refuted** — planner tìm thấy đều, budget không phải chỗ hỏng |
| < 0.9 | tăng ≥ 0.2 | **supported** — tìm được nhờ may, đúng claim |
| < 0.9 | gần như không đổi | **refuted** — tỉ lệ không nhúc nhích theo budget là chỉ vào **hình học**; báo "thiếu sample" sẽ đẩy người ta đi vặn nhầm núm |

Card đổi measurement (một tỉ lệ không phân biệt được "budget nhỏ" với "hành lang
không có ở đó" — cả hai đều là số thấp) ⇒ tool `rrt_convergence` **2.0.0**, catalog
**3.0.0**. `AWAITING_SIDECAR` nay **rỗng**.

---

## 8. Blocker 4 — run planted có sidecar

`scripts/plant_golden_runs.py`: dựng thế giới từng họ, chạy qua runner thật với
sidecar bật, rồi **đọc lại như một checker sẽ đọc** (validate attempt, resolve mọi
snapshot). File không tiêu thụ được thì hỏng ở đây chứ không hỏng trong gate run.

**Test tự bắt fixture sai của tôi.** Bản đầu đặt cửa 0,30 m trước robot 0,18 m và
gọi đó là "hẹp". Checker chạy và trả **refuted, 0% ở cả hai budget** — đúng như nó
phải nói: 0,30 m là **đóng về hình học** với robot cần 0,36 m. Thế giới đó planted
cơ chế **inflation** trong khi khai là sampling. Chính là lỗi width-vs-radius của
E6a, lần này nằm trong fixture của tôi.

Dò lại bằng đo, không đoán. Thế giới 120×100 @ 0,1 m, cửa 0,50 m, robot 0,18 m:

| Budget | Chạm hành lang |
|---|---|
| 120 (1×) | **0 / 12** |
| 480 (4×) | **7 / 12** |

0% → 58% chỉ do budget — đúng chữ ký. Cửa **đi lọt được** là điểm mấu chốt.

**Kết quả chạy thật, hai checker trên hai sidecar thật:**

```
rrt-001        supported  rate@budget 0.00  rate@4x 0.58  seeds 12
inflation-001  supported  paths_found 0     attempts 1
```

**2/6 họ.** Bốn họ còn lại script **in lý do** chứ không im lặng bỏ qua — một suite
thiếu bốn họ là suite mà macro average tính trên hai, và người đọc không được báo
sẽ tưởng là sáu:

- `dwa_local_minimum` — cần túi lõm mà local controller mắc kẹt trong khi global
  path vẫn tồn tại; dựng ổn định là bài toán hiệu chỉnh chứ không phải hình học;
- `expansion_latency` — cần nhiều episode khác nhau đủ để xếp hạng, là tính chất
  của một sweep chứ không của một thế giới;
- `negative_control` — cần một **cặp** candidate, thuộc về sweep;
- `insufficient_evidence` — dựng được, nhưng gap phải do packet builder khai, tức
  **E4.1**.

**`OFFICIAL_GOLDEN_READY` vẫn `False`, và script tự nói ra.** Còn thiếu: packet
dựng từ run (**E4.1**), và bốn họ kia. Đây là *run*, chưa phải *suite*.

## 9. Kiểm chứng sau blocker 3+4

- `tests/test_explanation_e6b.py` — **23 test** (+8 cho convergence: ba verdict,
  sweep chạy đủ seed × budget, quá ít seed, seed trùng, snapshot không ghi budget,
  budget preregistered, `AWAITING_SIDECAR` rỗng).
- Toàn bộ test explanation: **473 passed** (15 file).
- `tests/test_evidence_class_integration.py` + `test_nav_stack` + API: **30 passed**.
- Sweep RRT\* thật (12 seed × 2 budget trên lưới 120×100) **không nằm trong test
  suite** — khoảng một phút CPU. Nó nằm trong script planting, và số đo ghi ở mục 8.
- `ruff` sạch trên mọi file tôi đụng.
- **Full suite chưa chạy.**

---

## 10. Gate harness

E5 đã định nghĩa đủ mọi mảnh — `AnalystBundle` (nộp gì), `GoldenSuite` (chấm trên
gì), `score_suite` (chấm thế nào), `GateDecision` (phán quyết trông ra sao) — và
**không gì xếp chúng thành một hàng**. `gate.py` là cái hàng đó.

**Platform chạy bundle, nhóm AI không chạy gate.** Analyst tới đây dưới dạng một
callable harness gọi, mỗi case một lần, trong môi trường platform kiểm soát. Ba
seam đều là callable — `Analyst`, `PacketSource`, `SessionSource` — chứ không phải
đường dẫn: hidden set **không nằm trong repo này** và không được trở thành thứ
địa chỉ hoá được ở đây.

**Từ chối chấm trên bộ calibration.** `visibility="visible"` ⇒ `GateRefusal`. Chấm
trên bộ mà bên nộp đã tinh chỉnh là đo xem nó khớp bộ đó đến đâu. Có `allow_visible_suite`
cho dry run, và docstring nói thẳng: đừng gọi kết quả đó là gate.

**Từ chối bundle đóng băng theo wire contract khác.** Catalog đã lên 3.0.0; một
bundle khai 1.0.0 là một hệ thống khác mang cùng tên.

**Case nào ném thì bị chấm, không bị bỏ qua.** Analyst crash trên sáu case khó rồi
trả sạch phần còn lại thì sẽ được chấm trên phần còn lại. Nay exception được ghi,
case nộp thành một abstention **nó không hề đưa ra**, và `contamination` đếm riêng
— nên không crash vào được một bảng điểm sạch.

**Leak đọc từ packet, không từ case.** Packet là thứ analyst được xem; chấm nó theo
một luật nó không được cho biết là chấm điều nó không thể biết.

**`verify_gate_run`** — cùng bài học của claim ledger và gate decision: lời tự khai
của artifact về thứ nó đã chấm chính là phần đang bị nghi, nên identity và threshold
so lại với tham số caller đưa.

---

## 11. Ba họ planted, và vì sao ba họ kia cần sweep

Thêm `dwa_local_minimum`. Đo được: global planner trả tuyến 6,1 m vòng ra khỏi
miệng túi, robot dừng ở **x = 4,63 m** — ép vào tường sau ở 4,90 m, tức đã đi **sâu
thêm vào** túi. Trạng thái `stuck`, 0 replan. Cặp sự kiện đó chính là cơ chế: tuyến
tồn tại, và tầng phải đi theo nó thì không đi được. Start đặt **bên trong** túi có
chủ đích — robot phải tự đi vào trước thì việc kẹt lại phụ thuộc cách nó tiếp cận.

**Phát hiện cấu trúc về ba họ còn lại.** Không phải "chưa làm", mà là **không dựng
được bằng một episode**:

| Họ | Cần gì |
|---|---|
| `expansion_latency` | nhiều episode của một candidate, khác nhau đủ để xếp hạng — tính chất của **sweep** |
| `negative_control` | một **cặp** candidate có ΔU vắt qua 0 |
| `insufficient_evidence` | một gap được **packet builder** khai |

Và sâu hơn: **cả sáu họ đều cần sweep để có packet.** `build_case_packet` đòi
`DecisionFacts.waterfall`, waterfall là ΔU theo cặp, ΔU theo cặp cần hai candidate
chạy trên cùng tập episode context. Script planting sinh **run có sidecar** — đủ cho
hai checker replay — nhưng **không sinh được packet**. Nên `OFFICIAL_GOLDEN_READY`
không phải chờ "thêm vài thế giới", nó chờ **E4.1**.

## 12. Kiểm chứng cuối E6b

- `tests/test_explanation_gate.py` — **13 test** mới.
- `tests/test_explanation_e6b.py` — **23 test**.
- Toàn bộ test explanation: **291 + 195 = 486 passed** (16 file).
- `scripts/plant_golden_runs.py` sinh **3 run planted** có sidecar; hai checker chạy
  trên sidecar thật cho `supported` đúng cơ chế từng họ khai.
- `ruff` sạch trên mọi file tôi đụng.
- **Full suite chưa chạy.**

## 13. E6b — còn lại đúng ba thứ

1. **3 họ planted còn lại** — cần chạy sweep hai candidate qua pipeline chấm, không
   phải viết thêm thế giới.
2. **`OFFICIAL_GOLDEN_READY`** — chặn bởi **E4.1** (packet cần waterfall, waterfall
   cần sweep). Không phải thứ tôi nên tự lật.
3. **Một gate run thật** — chờ AnalystBundle nhóm AI nộp. Harness đã sẵn sàng nhận.

---

## 14. Đóng E6b — và ngã ba tìm thấy khi định làm nốt

Định làm nốt ba họ planted còn lại, và việc kiểm chứng dừng lại ở một chữ ký hàm:

```python
def build_waterfall(a: CandidateEvidence, b: CandidateEvidence, *, settings, ...)
```

`CandidateEvidence` **chỉ tồn tại trong lượt chấm**. Packet đòi
`DecisionFacts.waterfall`; waterfall đòi hai `CandidateEvidence`. Nên ba họ đó —
và `OFFICIAL_GOLDEN_READY`, và cả phần UI sau này — không chặn ở "thiếu vài thế
giới planted", chúng chặn ở **E4.1**. Đó là lý do tôi dừng và hỏi thay vì tự chọn:
lựa chọn này đổi schema report và đổi việc run cũ có giải thích được hay không.

**An chốt (19-08):**

1. **Dựng packet lúc chấm, ghi vào report.** Tái tạo `CandidateEvidence` từ report
   là viết một đường thứ hai tính ra cùng con số — đúng loại nguồn-thứ-hai mà HĐ-5
   cấm ở chỗ khác trong hệ này. Giá: bump schema `comparison_report`, run cũ không
   có packet.
2. **Thứ tự: E4.1 → UI → sweep golden.** Ba họ còn lại chỉ chặn gate run, mà gate
   run còn chờ AnalystBundle nhóm AI.

**E6b đóng ở phần nền tảng.** Những gì còn lại đều không phải code tôi viết thêm
được lúc này:

| Còn lại | Chặn bởi |
|---|---|
| 3 họ golden qua sweep | E4.1, và đã hoãn tới sau UI |
| `OFFICIAL_GOLDEN_READY` | như trên |
| Một gate run thật | AnalystBundle nhóm AI — harness đã sẵn sàng nhận |
