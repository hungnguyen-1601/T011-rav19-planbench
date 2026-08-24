# Đường vào trên UI cho thuật toán ngoài — kế hoạch

**Ngày:** 2026-08-24 · **Nhánh:** `tongduyan_verify-ai-analyst` · **Trạng thái: chờ An duyệt, chưa viết dòng code nào.**

Mục tiêu An nêu: *một người dùng, không phải dev, import được một thuật toán mới
và thực sự dùng nó để mô phỏng.* Chỗ đặt: trong phần **Models**.

Kế hoạch này thay thế `plans/2026-08-20/tab-import-thuat-toan.md` ở đúng một
điểm — nguồn import — và giữ lại toàn bộ phần còn lại của nó. Lý do thay ở §2.

---

## 1. Hai quyết định An đã chốt trong phiên này

| Câu hỏi | Chốt |
|---|---|
| UI nhận gì | **Bundle `.zip` có code** (`planner.py` + `plugin.json`), giải nén phía server |
| Runtime lane | **Subprocess bắt buộc** cho mọi plugin import qua UI |

Cả kế hoạch dưới đây dựng trên hai chốt đó.

---

## 2. Vì sao đổi quyết định "chỉ nhận plugin.json" của ngày 20-08

Quyết định cũ đúng với thông tin lúc đó. Nó sai với thông tin bây giờ, vì hai lý
do độc lập nhau:

**(a) Manifest-only không đạt được mục tiêu.** Manifest **khai** entry point,
không **chứa** code. Import một manifest cho code chưa cài trên máy chạy sweep
cho ra `registered_but_missing_runtime`. Chính plan 20-08 §3 đã nêu ràng buộc
này. Nên với manifest-only, người dùng vẫn cần một dev cài `planner.py` — tức
mục tiêu An vừa nêu không đạt được, chỉ đổi chỗ nút bấm.

**(b) Lý do "không đưa code lạ lên máy chủ" đã không còn mô tả đúng hệ thống.**

- `_build_ppo` ([registry.py:107](../../../../packages/benchmark/planbench_benchmark/registry.py:107))
  gọi `load_ppo_planner(path, ...)` trên file `.zip` do người dùng upload. SB3
  `PPO.load` unpickle checkpoint — **unpickle là thực thi code tuỳ ý**.
- Benchmark chạy trong `ThreadPoolExecutor` ngay trong tiến trình API
  ([worker.py](../../../../apps/api/planbench_api/worker.py)).
- `ValidationStatus` docstring viết: *"deserialising a user-uploaded file runs
  their code, so it never happens inside the API process"* — và
  `ValidationStatus.LOADED` **chưa từng được sinh ra ở đâu** (grep toàn repo: chỉ
  có khai báo, không có nơi gán). Tức lời hứa đó hiện chưa có ai giữ.

Nên nhận bundle code **không mở ra lớp rủi ro mới**. Nó dùng lại đúng lớp rủi ro
đã chấp nhận cho PPO. Điều nó đòi là: nói thật về lớp rủi ro đó, và đặt plugin
vào lane có cô lập tốt hơn PPO đang có — đó là lý do chốt thứ hai.

**Điều phải viết vào UI, không được lược:** subprocess lane cho **cô lập crash và
interpreter**, *không* phải security sandbox. Worker thừa kế environment,
filesystem và quyền mạng của người chạy host — author guide §10 và docstring
`subprocess_lane.py` đều nói thẳng. Chạy code thật sự không tin cậy cần container
hạ quyền, nền tảng chưa có.

---

## 3. Phần đã có, dùng lại được nguyên

| Cần | Đã có ở đâu |
|---|---|
| Parse manifest từ dict + mọi refusal | `parse_manifest(data, source=)`, `manifest_checksum` |
| Kiểm khai báo không chạy code | `check_declarations` → `ConformanceReport` |
| "Chạy được ở host này không" | `resolve_compatibility()` → `CompatibilityReport` |
| Bốn trạng thái đăng ký | `RegistrationState` |
| Chính sách công bằng, evidence class | `host/fairness_policy.py` |
| Lane subprocess, deadline thật, kill khi treo | `SubprocessRuntime`, `SubprocessPlugin` |
| **`search_paths`** để trỏ vào thư mục bundle đã giải nén | `SubprocessRuntime(search_paths=...)` |
| Conformance suite bốn phép kiểm | `check_local_plugin`, `check_global_plugin` |
| Lưu file streaming + checksum + trần dung lượng | `model_storage.py` (`save`, `CHUNK`, `storage_key`) |
| State machine `status` / `validation_status` | `model_registry.py` |
| Gắn tài liệu `.pdf` | `attach_document`, `DocumentKind.DOCUMENT` |
| Liên kết robot profile, `used_by`, quyền sở hữu | `registry_service.py` |
| Vỏ trang, tabs, i18n, bảng | `apps/web/src/app/models/page.tsx` |

Không viết lại cái nào.

---

## 4. Phần còn thiếu

- Không có endpoint nhận bundle.
- Không có chỗ lưu plugin đã import, không có bảng.
- Không có bước giải nén có kiểm và cài đặt.
- **Catalogue chỉ có một nguồn**: `algorithms_catalogue()`
  ([services.py:770](../../../../apps/api/planbench_api/services.py:770)) trả thẳng
  `list_algorithms()`, tức dict `ALGORITHMS` khai cứng.
- Toàn bộ UI.

---

## 5. Năm chokepoint — toàn bộ bề mặt phải chạm

Đã grep hết call site. Mọi đường tới `ALGORITHMS` đi qua đúng năm hàm trong
`packages/benchmark/planbench_benchmark/registry.py`:

| Hàm | Dòng | Call site ngoài registry |
|---|---|---|
| `algorithm_info` | 489 | leaderboard, candidates ×2, outcome, preflight |
| `list_algorithms` | 500 | services.py:772, candidates:444, legacy_plugins ×2, recommendation |
| `validate_algorithm_config` | 513 | services.py:106, candidates:269 |
| `build_local_planner` | 522 | services.py:248, candidates ×2, runner |
| `build_global_planner` | 528 | services.py:251, candidates:580, runner |

Khoảng mười chỗ. **Lối B của plan 20-08** — catalogue là hợp của hai nguồn — đặt
nguồn thứ hai *sau* năm hàm này. Không phải sửa mười chỗ gọi.

Lối C (built-in cũng thành plugin, một nguồn sự thật) vẫn là hướng đúng về sau,
và vẫn không phải việc của lần này.

---

## 6. Món quà kiến trúc: identity đã sẵn sàng

`candidate_from_stack` ([candidates.py:210](../../../../packages/benchmark/planbench_benchmark/candidates.py:210))
đặt `local_version` mặc định = **checksum source code của controller** cộng phần
core dùng chung, chứ không phải chuỗi `"v1"`.

Với plugin, thứ tương đương là **checksum của bundle** — đã tính sẵn ở bước lưu
file. Rơi đúng vào chỗ đó, không phải chế thêm khái niệm identity nào. Hai bản
bundle khác nhau một dòng là hai candidate khác nhau, tự động.

---

## 7. Ba món nợ phải trả trước khi nối đường chạy

Cả ba đã xác minh trong mã trong phiên khảo sát này, không phải phỏng đoán.

**N1 — `episode_seed` không tới nơi trên đường channel-native.**
`GraphBackedLocalPlanner.reset` ([graph_source.py:165](../../../../services/simulator/planbench_simulator/host/graph_source.py:165))
dựng `LocalResetRequest` mà không truyền `episode_seed`, nên nhận default `0`.
Chỉ `HostBackedLocalPlanner` ([facades.py:109](../../../../services/simulator/planbench_simulator/host/facades.py:109))
truyền thật. Hệ quả: mọi plugin rút số ngẫu nhiên sẽ dùng **cùng một seed cho mọi
episode**, và thống kê đo một thứ khác với thứ nó khai. Phải sửa trước P3.

**N2 — hai lane, hai contract cho cùng một `step()`.**
In-process đòi trả `LocalPlanResult`; trả dict thì
[algorithm_host.py:192](../../../../services/simulator/planbench_simulator/host/algorithm_host.py:192)
biến mọi tick thành safe stop, **không exception nào**. Subprocess nhận dict và
tự convert ([subprocess_lane.py:204](../../../../services/simulator/planbench_simulator/host/runtimes/subprocess_lane.py:204)).
Author guide §3 dạy trả dict — đúng cho subprocess, sai cho in-process. Đã chốt
subprocess bắt buộc nên v1 nhất quán, **nhưng author guide phải nói rõ điều kiện**,
nếu không người viết plugin cho lane kia sẽ dính im lặng.

**N3 — `ValidationStatus.LOADED` được khai mà chưa ai sinh ra.**
Không phải bug, là một chỗ trống. P2 dưới đây là chỗ nó có nghĩa lần đầu.

---

## 8. Ràng buộc phạm vi mới, do chốt subprocess sinh ra

`SubprocessPlugin` chỉ có `reset` và `step`
([subprocess_lane.py:164](../../../../services/simulator/planbench_simulator/host/runtimes/subprocess_lane.py:164)).
**Không có `plan()`.** Lane subprocess hôm nay chạy được `local` và `monolithic`,
**không chạy được `global`**.

Nên chốt "subprocess bắt buộc" ⇒ phải chọn một trong hai:

- **v1 chỉ nhận plugin `local`/`monolithic`.** UI từ chối `role: "global"` kèm
  đúng lý do đó. Rẻ, trung thực, và VFH+ nằm trong phạm vi.
- **Mở rộng lane cho role `global`** — thêm một roundtrip `plan`, encode
  `GlobalPlanRequest`, decode `GlobalPlanResponse`. Ước +1 ngày, và cần test
  riêng vì `channels` của global mang payload `planning-grid` (grid object), tức
  codec JSON phải diễn đạt được nó hoặc phải cấp qua đường khác.

**Đề xuất: v1 chỉ local/monolithic**, ghi global thành đợt P6 tuỳ chọn. Lý do:
phép thử đầu tiên nên chứng minh đường vào, không nên đồng thời mở một codec mới.

Một ràng buộc nữa: `SubprocessRuntime.load` đòi **`control_period_s` bắt buộc**,
cố ý không có default — nó là ngưỡng gate G4 và phải đến từ deployment.
`RobotProfileRequest` **từ chối** trường `control_period` với lý do dài
([models.py:63](../../../../apps/api/planbench_api/routers/models.py:63)): nó thuộc
deployment, không thuộc robot. Nên P2 phải lấy số này từ deployment của benchmark,
không phải từ robot profile chọn lúc upload.

---

## 9. Các đợt

### P0 — Chốt và viết ra, không code · 0.5 ngày

- Threat model một trang: chạy code người lạ ở đâu, với quyền gì, ai chịu.
- Câu chữ hiển thị trên UI về mức cô lập. Không được nhẹ hơn `subprocess_lane.py`
  docstring.
- Ai được import: mọi member, hay cần cờ riêng.
- Chốt v1 = local/monolithic (§8).

**Xong khi:** có văn bản, An duyệt. Không có nó thì P1 sẽ tự chế câu chữ an toàn
giả.

### P1 — Nhận và đăng ký bundle, chưa chạy gì · 1.5 ngày

- `POST /api/v1/algorithms/plugins`, multipart: `bundle` (`.zip`), `name`,
  `version`, `robot_profile_id`, `description`, `document` (`.pdf`, tuỳ chọn).
- `inspect_bundle(data) -> list[str]` — **cùng khuôn `inspect_archive`**, đọc
  table of contents, **không giải nén, không import**:
  - zip magic, `testzip()`
  - member path an toàn: không tuyệt đối, không `..`, không `\`, không symlink
  - đúng **một** `*/.planbench-plugin/plugin.json`; không có, hoặc có hai, là hai
    lỗi khác nhau với hai thông điệp khác nhau
  - `parse_manifest(json.loads(...))` — mọi refusal của H1a rơi ra ở đây
  - `manifest.role` ∈ {local, monolithic}; `production_lane == "python_in_process"`
    bị từ chối kèm lý do (§8, và host không bao giờ fallback lane)
  - trần dung lượng và trần số file
- Bảng mới `plugin_bundles`, alembic `0010`. Cột: id, name, version, plugin_id,
  manifest_json, manifest_checksum, storage_key, file_checksum, file_size,
  original_filename, uploaded_by_user_id, robot_profile_id, status,
  validation_status, validation_message, created_at, updated_at.
- `GET /algorithms/plugins`, `GET {id}`, `PATCH {id}` (chỉ `status`, `description`).
  **Không có DELETE** — cùng lý do trang Models không có nút xoá: một plugin là
  thứ một benchmark *đã chạy*, xoá đi biến kết quả thành bản ghi của hư không.
  Disable là cách nghỉ hưu trung thực.
- **Trạng thái tính lại lúc đọc**, không tin cột đã lưu: host cài thêm provider
  thì một plugin hôm qua không chạy được hôm nay chạy được.

**Xong khi:** upload bundle hỏng → 422 kèm đường dẫn field; upload bundle tốt →
201 kèm `CompatibilityReport`. Chưa có dòng code plugin nào được thực thi.

### P2 — Cài đặt và chứng minh nó chạy được · 2 ngày

- `install_bundle(record) -> Path`: giải nén vào `var/plugins/{plugin_id}/{version}/`,
  idempotent, kiểm lại checksum trước khi giải, từ chối member vượt ra ngoài thư
  mục đích (zip-slip) **lần nữa** ở thời điểm giải nén — kiểm lúc đọc TOC và kiểm
  lúc ghi là hai thời điểm khác nhau.
- `PluginRuntimeService`:
  - `PluginRegistry().discover_directory(install_root)`
  - `resolve_compatibility(manifest, available, graph, policy=FairnessPolicy.production())`
  - `SubprocessRuntime(search_paths=(install_dir,))`
- **Conformance tự động ngay sau khi cài**, trong subprocess: `check_local_plugin`
  với request dựng từ robot profile đã chọn. Kết quả:
  - passed → `validation_status = LOADED` ← **N3 có nghĩa lần đầu ở đây**
  - failed → `FAILED`, `validation_message` = `report.render()` nguyên văn
- Trả nợ **N1** (`episode_seed`) và cập nhật author guide cho **N2**.

**Xong khi:** một bundle mẫu upload qua API → cài → conformance chạy trong tiến
trình con → trạng thái `loaded`. Và một bundle cố tình sai determinism → `failed`
kèm finding đúng chỗ.

### P3 — Catalogue hợp nhất và đường chạy · 1.5 ngày

- `plugin_algorithm_info(record) -> AlgorithmInfo`, dựng **từ manifest**, không
  đoán: `config_schema` lấy nguyên, `requires_global_path` từ manifest,
  `local_observation_class` suy từ `requirements` bằng **đúng bảng
  `_CLASS_REQUIREMENTS`** mà `legacy_plugins.py:84` đang dùng, đảo chiều. Không
  có ánh xạ nào thì từ chối, không đặt mặc định — `AlgorithmInfo` cố ý không cho
  observation class có default, và lý do ghi ngay tại chỗ khai.
- Ghép cặp: plugin local + global built-in ⇒ id `astar+org.vinai.vfh-plus`.
  **Phải kiểm `stack_id.partition("+")` chịu được nửa sau chứa `.` và `-`** —
  `candidate_from_stack:257` dùng `partition`, nên dấu `+` đầu tiên là ranh giới;
  id plugin không được chứa `+` (pattern manifest đã cấm).
- Năm chokepoint nhận nguồn thứ hai. Mỗi hàm một nhánh, không hàm nào đổi chữ ký.
- `build_local_planner` cho plugin trả về `GraphBackedLocalPlanner` bọc
  `AlgorithmHost` bọc `SubprocessPlugin`.
- `control_period_s` lấy từ deployment (§8), không từ robot profile.

**Xong khi:** `GET /algorithms` trả cả plugin đã import; một benchmark spec đặt
`astar+<plugin-id>` chạy được đầu-cuối; `run.algorithm` mang đúng tên; candidate
id băm theo checksum bundle.

### P4 — UI trong phần Models · 1.5 ngày

- Mode thứ ba cạnh `upload` / `edit`: **Import algorithm**. Cùng vỏ, cùng bảng,
  cùng badge trạng thái.
- Form: bundle `.zip`, name, version, robot profile, description, `.pdf` tuỳ chọn.
- Sau khi upload, hiển thị **`CompatibilityReport` nguyên văn**: registration
  state, provider graph đã resolve, runtime lane, evidence class, và **mọi**
  blocker một lượt. Không diễn giải lại thành câu dễ nghe hơn — các trường lý do
  đã có sẵn, UI render chúng.
- Cột phân biệt hai loại "không dùng được", giữ nguyên nguyên tắc trang Models
  đang theo: `status` là quyết định của người, `validation_status` là file hoá ra
  là cái gì.
- Câu chữ về mức cô lập từ P0, hiển thị **trước** nút upload chứ không phải trong
  tooltip.
- Chỉ plugin **vừa `registered_and_runnable` vừa conformance passed** mới hiện ở
  `CandidatePicker`. Ba trạng thái còn lại vẫn hiện trong tab, xám, kèm lý do.
- i18n cả `en` và `vi`. Phần quyết định tách sang `lib/` để test được (repo không
  có jsdom).

**Xong khi:** người dùng không chạm terminal, upload bundle, thấy báo cáo, thấy
plugin trong danh sách candidate.

### P5 — Xác minh đầu-cuối bằng một thuật toán thật · 0.5 ngày

VFH+ (xem `notes/2026-08-24/tongduyan_de-xuat-thuat-toan-de-thu-import.md`).
Import qua UI, chạy sweep ngắn `doorway`, kiểm trong report: candidate identity,
evidence class `production`, runtime lane `subprocess`, `invalid_outputs == 0`.

Không có đợt này thì bốn đợt trên chỉ được chứng minh bằng fixture.

### P6 — Tuỳ chọn: role `global` trong subprocess lane · +1 ngày

Chỉ làm nếu An muốn nhận JPS/Hybrid A\*. Xem §8.

---

**Tổng: 7–7.5 ngày** (không tính P6).

**P1 + P4 đã tự nó dùng được**: import và xem thuật toán có chạy được ở host này
không, mà chưa đụng đường chạy. Nếu An muốn thấy sớm thì dừng ở đó rồi đánh giá.

---

## 10. Những chỗ tôi sẽ từ chối làm tắt

- **Không đoán requirement từ id plugin.** Manifest khai gì đọc đúng thế.
- **Không import code plugin để lấy metadata**, kể cả khi tiện. Discovery không
  import là thuộc tính chịu lực.
- **Không lưu `runnable` rồi tin nó.**
- **Không cho chọn plugin chưa runnable làm candidate** chỉ vì nó đã trong danh
  sách.
- **Không tự chế thông điệp lỗi.** `CompatibilityReport` đã có trường lý do.
- **Không gọi subprocess lane là sandbox.** Nó là cô lập crash và interpreter.
- **Không fallback lane.** Manifest khai in-process thì từ chối, không âm thầm
  chạy chỗ khác.
- **Không giải nén trước khi preflight xanh.**

---

## 11. Rủi ro

| Rủi ro | Vì sao thật | Giảm thế nào |
|---|---|---|
| Code người lạ chạy với quyền của user chạy host | Đúng như docstring lane nói; không phải giả định | P0 nói thẳng trên UI; container hạ quyền ghi vào backlog |
| Zip-slip lúc giải nén | Member path độc hại là chuyện thường của zip upload | Kiểm hai lần: lúc đọc TOC và lúc ghi file |
| Plugin treo làm nghẽn worker pool | Pool chỉ vài slot, benchmark chạy trong API process | Lane subprocess **có** deadline thật và kill; đây là lý do chọn nó |
| Trạng thái lưu lệch trạng thái thật | Provider đổi, deployment đổi | Tính lại lúc đọc, luôn luôn |
| `+` trong id gây nhập nhằng khi tách stack | `partition("+")`, id plugin chứa `.` và `-` | Test riêng cho id có dấu; pattern manifest đã cấm `+` |
| Người dùng tưởng import xong là so sánh được với built-in | Plugin có thể là bản cài sai của một thuật toán tốt | Conformance là điều kiện cần, không phải điều kiện đủ; report ghi rõ evidence class |

---

## 12. Câu hỏi còn mở cho An

1. **Ai được import?** Hiện `/models` chỉ cần đăng nhập. Plugin có cần cờ riêng
   không, hay member nào cũng được?
2. **Trần dung lượng và trần số file** cho một bundle? Model đang dùng
   `max_model_upload_mb`; plugin nên có trần riêng nhỏ hơn nhiều.
3. **P6 có làm không** — tức có nhận plugin `global` trong lần này không?
4. **Dừng ở P1+P4 để xem trước**, hay chạy thẳng tới P5?

---

## 13. Ghi chú

Chưa viết một dòng code nào cho việc này. §3, §4, §5, §7, §8 là kết quả đọc mã
hiện có và chạy hai lệnh CLI đọc-thôi, không phải mô tả thứ sẽ xây.
