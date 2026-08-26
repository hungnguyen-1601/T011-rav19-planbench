# E4.5 — sidecar writer: ghi input của planner ngay lúc planner được hỏi

**Ngày:** 2026-08-19 · **Nhánh:** `tongduyan_3` · **Plan:** `docs/antongduy/plans/2026-08-18/tang-giai-thich-vi-sao.md` §5 (E4.5)

**Trạng thái:** xong, đã qua **một vòng rà của An** (mục 10), **chưa commit**.
E6a đã commit ở `f6ef43f`; vòng rà này sửa cả một số điểm thuộc E6a.
Không đụng web. Full suite chưa chạy.

---

## 1. Vì sao phải ghi lúc chạy, không ghi sau

Đây là phần **duy nhất** của tầng giải thích chạy **bên trong** một episode.
Mọi thứ còn lại đọc artifact sau khi xong.

Trace Parquet không giữ costmap, cũng không giữ plan. `StackRun.plans` giữ những
đường **tìm được** — không giữ query đã sinh ra chúng, và không giữ những lần
không tìm được gì. Costmap mà planner nhìn thấy ở lần replan thứ mười bảy —
obstacle theo cái robot **tin**, inflation theo cấu hình, standing room nới quanh
robot — tồn tại đúng bằng thời gian một lời gọi rồi biến mất.

Dựng lại sau đó là provenance `reconstructed`, mà ladder cắt trần ở `associated`,
và không sự cẩn thận nào sau đó nâng nó lên được. Nên: **ghi tại lời gọi, hoặc
không có gì để ghi.**

---

## 2. Giao cái gì

| File | Nội dung |
|---|---|
| `sidecar_writer.py` | `PlanningInputRecorder` · `SidecarHeader` · `costmap_checksum` · `planner_fingerprint` · `read_sidecar`/`write_sidecar` |
| `nav_stack.py` (sửa) | `_record_attempt` + `_plan_checksum`; `planning_recorder` tuỳ chọn trên `plan_global_path`, `_replan`, `run_nav_stack`/`run_stack` |
| `golden.py` (sửa) | docstring `OFFICIAL_GOLDEN_READY` nói chính xác cái còn thiếu |

`tests/test_explanation_e45.py` — **21 test**, trong đó sáu test chạy **episode
thật** qua `run_stack`.

---

## 3. Bốn quyết định có nội dung

**Ghi ngay từng dòng, không buffer.** Cùng lý lẽ với trace recorder: episode nổ
giữa chừng vẫn để lại thứ nó đã thu, còn buffer flush lúc cuối thì không để lại gì
đúng vào lúc có chuyện. `abandon()` đóng file mà **không** validate — episode
hỏng có sidecar dở dang, và đó là artifact trung thực; validate ở đó là biến một
lỗi thành hai và giấu mất lỗi đầu.

**Băm grid được đưa cho planner, không băm map trên đĩa.** Đo được trên run thật:

```
attempt 1  path   5e848b75dd  tick 0
attempt 2  path   ba68786659  tick 278
map trên đĩa      861ae24d01
```

Ba checksum khác nhau. Nếu băm map nguồn thì hai attempt trông y hệt, và một replay
sẽ **trông như** tái lập được trong khi không phải.

**Số thứ tự attempt do recorder giữ, không do caller.** Có hai chỗ gọi — plan đầu
và vòng replan — và mỗi chỗ tự giữ một số là hai số sẽ lệch nhau.

**`close()` bắt buộc truyền `expected_attempts`.** Đếm của recorder (`attempts`)
được để ở property riêng và docstring nói thẳng nó **không phải** kỳ vọng: một
validator được cho ăn chính đầu vào của nó thì chỉ có thể đồng ý với nó. Số đúng
là `replan_count` của runner cộng một. Có test: recorder ghi 1 attempt,
`close(expected_attempts=2)` ⇒ `SidecarViolation`.

---

## 4. Seam vào runner

Theo đúng thành ngữ sẵn có trong codebase — `recorder=None` của trace:

```python
run_stack(..., planning_recorder=writing)
```

Tuỳ chọn, và run không có nó chạy **y hệt như cũ**. Có test so ba thứ: status,
`replan_count`, `elapsed_time` (approx) giữa run có writer và run không có.

`nav_stack.py` **không** import package explanation ở đầu module — import nằm
trong `_record_attempt`, để tầng simulator không phụ thuộc tầng giải thích. Cùng
lý do `costmap_checksum` nhận cells/width/height/resolution chứ không nhận
`OccupancyGrid`.

`_plan_checksum` làm tròn tới **milimet** trước khi băm. Path là số thực; hai lần
chạy cùng planner tất định trên cùng input có thể lệch bit cuối, và một checksum
đổi theo bit cuối sẽ báo mọi replay là mismatch — vô hiệu hoá phép so ở đúng chiều
duy nhất nó được phép dùng (refuter).

---

## 5. Attempt thất bại — chỗ cả wave này sinh ra vì nó

Test dùng planner có kịch bản (`RefusesAfterTheFirst`) chứ không dựa vào bản đồ:
trên two-doorway map lần replan **thành công** qua cửa còn lại, nên nếu để tự
nhiên thì nhánh `no_path` không bao giờ chạy và assertion sẽ pass **vì không được
thực thi**. Đây là loại test vacuous mà An đã bắt ở vòng trước.

Với planner kịch bản, khẳng định được đúng điều cần:

```python
assert len(run.plans) < len(writing.records)
```

Lần từ chối nằm trong sidecar và **không** nằm trong `StackRun.plans`.

---

## 6. Gỡ được gì cho E6b

| | Trước | Sau |
|---|---|---|
| Replay attempt có ghi | không tồn tại | `mechanism_verified` (test) |
| Replay không ghi | `reconstructed`, trần `associated` | **không đổi** — và chính sự tương phản đó là lý do wave này đáng làm |

Test cũng giữ luật "replay một lần từ chối phải từ chối **vì cùng lý do**":
`no_global_path` và `planner_timeout` đều là `no_path` nhưng là hai cơ chế khác
nhau, mà cơ chế chính là chủ đề của claim đang được kiểm.

**Nhưng E6b chưa mở hết, nói rõ:**

- seam đã có, **bộ replay chưa viết** — `replay_global_plan` và `rrt_convergence`
  vẫn nằm trong `AWAITING_SIDECAR` và vẫn trả `checker_not_implemented`;
- và cần **run thật có sidecar**. Writer tồn tại ≠ dữ liệu tồn tại.

---

## 7. `OFFICIAL_GOLDEN_READY` vẫn `False` — và lý do đã đổi

Trước: "chưa có writer". Nay writer có rồi, nên docstring phải nói chính xác cái
còn thiếu — **run planted được chạy kèm recorder**. Packet fixture dựng từ một run
có trước writer mang planning input tái dựng, và threshold chốt trên đó sẽ nướng
lỗi tái dựng vào chính cái bar. Lật hằng số này là một code change có diff, làm
sau khi những run đó tồn tại và sidecar của chúng validate sạch.

---

## 8. Chưa làm

| Việc | Vì sao |
|---|---|
| Bộ replay (`replay_global_plan`, `rrt_convergence`) | **E6b** |
| Nối recorder vào pipeline chấm (benchmark runner) | cần quyết định đặt sidecar ở đâu trong cây artifact — cùng nhóm câu hỏi với **E4.1** |
| Run planted có sidecar | một lượt chạy, không phải một module |
| Gate harness | E6b + bundle nhóm AI |
| Web | không đụng |

---

## 9. Kiểm chứng

- `tests/test_explanation_e45.py` — **17 test** (4 test chạy episode thật).
- `tests/test_replanning.py` + `tests/test_nav_stack.py`: **63 passed, 1 skipped**
  — seam không làm hỏng runner.
- Toàn bộ test explanation: **422 passed** (14 file).
- `ruff check` + `ruff format` sạch.
- **Full suite chưa chạy.**

---

## 10. Vòng rà của An — sáu điểm

Đúng cả sáu. Điểm HIGH đầu tiên là điểm nghiêm trọng nhất từ đầu dự án tới giờ:
**wave này không làm được việc nó sinh ra để làm**, mà test vẫn xanh.

### HIGH-1 — sidecar chỉ lưu checksum, không lưu thứ replay được

Đúng, và An chỉ ra đúng lý do test không bắt được: `ReplayObservation` trong test
được dựng bằng cách **sao chép các trường của record**, nên nó chứng minh
admission logic chứ không chứng minh planner chạy lại được. Checksum xác minh một
grid **ai đó đã có**; nó không sinh ra grid.

Sửa: record trở thành **chỉ mục**, không phải bằng chứng.

| | |
|---|---|
| Record giữ | thứ replay **so sánh** — checksum, query, fingerprint — cộng `snapshot_ref` |
| Snapshot giữ | thứ replay **nạp** — `GridSnapshot` (cells + width/height/resolution/origin), start/goal, `planner_name`, **`planner_parameters` dạng giá trị**, `seed` |

Cấu hình lưu **dạng giá trị chứ không phải fingerprint**: fingerprint trả lời "có
phải cùng cấu hình không", replay cần "cấu hình là gì" — hai câu hỏi khác nhau và
chỉ một cái hash trả lời được. `seed` là `int | None`, và `None` là **một phát
biểu**: replay RRT\* không có seed cho ra cây khác, nên snapshot không nêu được
seed thì phải nói ra chứ không mặc định 0.

`snapshot_for(sidecar_path, record)` nạp và **kiểm grid vừa nạp đúng là grid
record đặt tên** — thư mục snapshot lệch khỏi sidecar sẽ nổ ở đây, chứ không nổi
lên dưới dạng "reconstruction sai".

**Test An yêu cầu, đã có:** nạp snapshot, dựng lại `OccupancyGrid`, **chạy
`AStarPlanner` thật**, so `_plan_checksum` với checksum trong record. Đó là khẳng
định mà bộ test cũ không đưa ra được.

### HIGH-2 — contract đổi mà version giữ nguyên

Đúng, và trái thẳng nguyên tắc bundle bất biến. `latency_vs_expanded_nodes` đổi
đơn vị, argument, required evidence, tên measurement, failure mode, và cả nghĩa
mệnh đề — mà vẫn `1.0.0`.

Bump: tool → **2.0.0** (cả `gap_vs_footprint`, vì nó cũng đổi tên measurement ở
HIGH-3), catalog → **2.0.0**, 32 schema sinh lại. Có test khẳng định
`TOOL_CATALOG.card("latency_vs_expanded_nodes", "1.0.0")` **ném**
`ToolNotInCatalog` — bản cũ biến mất chứ không bị diễn giải lại âm thầm.

Việc bump lộ ngay một chỗ hỏng thật: `reference_analyst` ghi cứng `"1.0.0"`, nên
sau khi bump nó **im lặng ngừng đề xuất** hai loại detection — lookup fail và vòng
lặp bỏ qua. Đã sửa thành tra theo tool id. Caller ghim một version nó không sở hữu
là caller sẽ câm khi chủ sở hữu đổi.

### HIGH-3 — công thức trộn bán kính với bề rộng

Đúng, và **sâu hơn E6a**: detector E3 (`_narrow_gap_refusal`) cũng so
`narrowest_passage_m` (cross-section) với `required_clearance_m` mà doc ghi là
"radius plus the costmap's inflation" — một bán kính. Test tôi viết pass chỉ vì
fixture chọn 0.26 + 0.48 = 0.74.

Chọn phương án 1 của An và làm triệt để — **một định nghĩa, tên mang đơn vị**:

- `required_clearance_m` ⇒ **`required_passage_width_m`** ở cả 9 file;
- định nghĩa: `2 × (radius + inflation_margin)`;
- `RobotFacts` thêm `inflation_margin_m` và property `derived_passage_width_m`;
- `GapEvidence` **nhận** width do platform tính, **và** validator kiểm nó suy ra
  đúng từ các phần — một con số không suy ra được từ các phần là một định nghĩa
  thứ hai.

Test ghim đúng lỗi: cửa 0.50 m với robot 0.26 m + margin 0.11 m ⇒ cần 0.74 m ⇒
`supported`. Công thức cũ cho 0.37 m và đọc thành đi lọt.

### HIGH-4 — EvidenceSource chưa ràng buộc với packet

Đúng. Host nhận hai thứ độc lập, nên packet A + report/map của run B sẽ admit sạch
mọi request rồi trả result đóng dấu `recorded` — và **không gì ở downstream nêu
tên một run để mà phát hiện**.

Thêm `EvidenceIdentity` (run_id, source_manifest_ref + checksum, task_profile_id,
tập candidate) và `identity_of(packet)`; constructor của `ToolHost` từ chối lệch,
**trước khi có checker nào để sai**, và exception nêu đúng field nào lệch.

Map checksum **cố ý không có trong đó**: CasePacket không mang map checksum nên
host không kiểm được, và một field không ai so là một field đọc như bảo đảm mà
không phải bảo đảm. Ghi rõ trong docstring: khi packet có, cái này có.

### MEDIUM-5 — `evidence_artifact_ref` trỏ tới file không được tạo

Đúng. Một trường truy vết mà truy về hư không còn tệ hơn không có, vì nó **trông
như sự cẩn thận**.

Thêm `EvidenceSink`: `store(tool_id, request_id, payload) -> StoredEvidence`.
Host chỉ trả `ToolResult` **sau khi** sink đã ghi, và `evidence_artifact_ref` +
`evidence_checksum` lấy **từ sink**, không tự bịa. Hai hiện thực:
`InMemoryEvidenceSink` (không phải null sink — null sink là đặt lại đúng cái lỗ)
và `FileEvidenceSink`. Test đọc file trên đĩa và so `artifact_checksum` với
checksum trên result.

### MEDIUM-6 — failure code suy từ nội dung exception

Đúng — `"same expanded-node" in str(error)` nghĩa là sửa một câu văn sẽ đổi mã lỗi.

`CheckerRefusal(code, detail)` với `RefusalCode` là Literal đóng. Host **chuyển
tiếp** `error.code`, không parse prose.

## 11. Kiểm chứng sau vòng rà

- `tests/test_explanation_e45.py` — **21 test** (+4: mọi record trỏ snapshot nạp
  được; **chạy lại planner thật từ snapshot**; snapshot lệch sidecar bị bắt; seed
  của sampling planner được ghi hoặc nói rõ là không có).
- `tests/test_explanation_e6.py` — **33 test** (+9: width ≠ radius; width không
  suy ra từ các phần bị từ chối; source khác run bị từ chối; source khác manifest
  bị từ chối; identity lấy từ packet; artifact được ghi thật; checksum là của thứ
  đã ghi; catalog lên 2.0.0; card 1.0.0 biến mất).
- Toàn bộ test explanation: **435 passed** (14 file).
- `tests/test_nav_stack.py` + `tests/test_replanning.py` + API: **53 passed, 1 skipped**.
- 32 schema sinh lại sau khi bump version.
- `ruff check` + `ruff format` sạch. **Full suite chưa chạy.**

---

## 12. Vòng rà thứ hai — năm điểm

Đúng cả năm. Điểm bảo mật là điểm phải sửa ngay.

### HIGH — runner chưa ghi planner parameters và seed

Đúng, và đây là HIGH-1 vòng trước **chưa đóng hết**: snapshot *hỗ trợ*
`planner_parameters` và `seed`, nhưng `_record_attempt` chỉ truyền `planner_name`,
nên mọi snapshot sinh từ `run_stack` có parameters rỗng và `seed=None`. Test seed
gọi `record()` trực tiếp nên không chứng minh seam runner ghi được — đúng loại
test đi vòng qua chỗ cần chứng minh.

Sửa: `_record_attempt` nhận **đối tượng planner**, đọc `.name`, `.config`
(pydantic dump, giữ scalar), `.episode_seed` hoặc `config.seed`. Hai test mới chạy
`run_stack` thật: A* với `connectivity=4` ⇒ snapshot ghi `4`; RRT\* với
`episode_seed=17`, `max_iterations=800` ⇒ snapshot ghi cả hai.

Về fingerprint: recorder **không còn nhận** nó từ caller. Nó **suy ra** từ chính
snapshot (`snapshot.fingerprint`). Trước đây caller ghi được hash của planner A
cạnh cấu hình của planner B và không gì so hai cái đó.

### HIGH — integrity chưa bao phủ toàn bộ planning input

Đúng. `costmap_checksum` bỏ `origin` — mà origin là thứ biến chỉ số ô thành toạ độ
thế giới, nên start/goal replay sẽ rơi chỗ khác. Đã đưa origin vào hash.

Và `snapshot_for` chỉ kiểm grid + số attempt, nên snapshot bị thay start, goal,
planner config hay seed vẫn nạp sạch: **đúng thế giới, khác câu hỏi**.

Làm đúng phương án An đề xuất: `PlanningInputEvidence.snapshot_checksum` — SHA-256
trên canonical serialization của **toàn bộ** `PlanningSnapshot`. `snapshot_for`
kiểm hash tổng **trước**, rồi mới liệt kê field nào lệch — người vừa được báo
"hash khác" muốn biết field nào trước khi mở diff bốn mươi nghìn ô.

Test: đổi `goal_x` (grid không đụng, `grid.checksum` vẫn khớp) ⇒ bị bắt; đổi
`max_iterations` ⇒ bị bắt.

### HIGH — evidence identity vẫn là giá trị caller tự khai

Đúng, và cách An diễn đạt chính xác: nó **ngăn miswiring vô ý nhưng chưa phải
trust boundary**.

`ReportEvidence` nay dựng **từ packet** (`ReportEvidence(report, packet=...)`):

- identity suy từ packet, không nhận từ caller;
- kiểm `report["identity"]["task_profile_id"]` khớp packet;
- kiểm report có dòng cho **mọi** candidate packet so sánh;
- **robot facts lấy thẳng từ packet** — radius, margin, required width. Hai nguồn
  cho một sự thật là thừa một nguồn, và packet là nguồn analyst đã được xem.
- run không ghi inflation ⇒ `gap_evidence` trả `None`, không đoán.

Thứ **không** kiểm được thì gọi tên chứ không bỏ qua: `run_uri`, `run_checksum`
không có đối chiếu trên packet, và map checksum thì packet chưa mang. Chúng nằm ở
property `unverified_report_identity` — đọc được, và **không** được coi là đã xác
minh.

### HIGH — path traversal qua `request_id`

Đúng, và là lỗi bảo mật. `request_id` do analyst cung cấp và được dán thẳng vào
đường dẫn; `../../outside` ghi ra ngoài artifact root.

Hai lớp phòng thủ độc lập, vì một lớp là phán đoán về chuỗi còn lớp kia là sự thật
về đường dẫn:

1. tên file là **digest** của `request_id` (băm chứ không lọc — bộ lọc phải đoán
   trước mọi cách viết "lùi một cấp", digest không phải đoán gì); `request_id`
   gốc nằm **trong** artifact nên người đọc không mất gì;
2. `path.resolve().is_relative_to(root)` kiểm trước khi ghi.

Cộng lớp thứ ba ở protocol: `ToolRequest.request_id` giới hạn
`^[A-Za-z0-9_.:-]+$`, tối đa 128 ký tự.

### MEDIUM — in-memory sink mặc định

Đúng: `memory://…` sống lâu hơn cái dict nó trỏ vào là một con trỏ treo mang lược
đồ nghe hợp lý. `sink` nay **bắt buộc**; chọn `InMemoryEvidenceSink` là một tuyên
bố rằng result không được giữ lại.

## 13. Kiểm chứng sau vòng rà thứ hai

- `tests/test_explanation_e45.py` — **27 test** (+6: fingerprint suy từ snapshot;
  origin thuộc identity của grid; goal bị tráo bị bắt; planner parameters bị tráo
  bị bắt; runner ghi config thật của A*; runner ghi seed thật của RRT\*).
- `tests/test_explanation_e6.py` — **41 test** (+8: report khác task profile bị từ
  chối; report thiếu candidate bị từ chối; host từ chối source bind packet khác;
  thứ report tự khai mà packet không xác nhận được gắn nhãn; robot facts lấy từ
  packet; run không ghi inflation không gap-check được; `../../outside` không ra
  khỏi root; `request_id` giữ trong artifact; protocol chặn id không hợp lệ; host
  không mặc định sink).
- Toàn bộ test explanation: **449 passed** (14 file).
- `tests/test_nav_stack.py` + `tests/test_replanning.py` + API: **53 passed, 1 skipped**.
- `ruff check` + `ruff format` sạch trên mọi file tôi đụng. (Ba file lint bẩn sẵn —
  `test_api_profile_validation.py`, `test_capability_grants.py`,
  `test_evidence_class_integration.py` — tôi không đụng, để nguyên.)
- **Full suite chưa chạy.**
