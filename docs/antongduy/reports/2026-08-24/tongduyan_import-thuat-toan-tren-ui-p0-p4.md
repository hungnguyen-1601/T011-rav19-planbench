# Đường vào UI cho thuật toán ngoài — P0 đến P4

**Ngày:** 2026-08-24 · **Nhánh:** `tongduyan_plugin-import-ui` (tạo mới, **không đụng `main`**)
**Plan:** `plans/2026-08-24/tab-import-thuat-toan-tren-ui.md`
**Trạng thái:** P0–P4 xong, mỗi phase một commit. P5 và P6 chưa làm (An dặn dừng ở P4).

Năm commit, theo thứ tự:

| Commit | Phase |
|---|---|
| `23bc7e6` | P0 — threat model |
| `4e4c126` | P1 — nhận và đăng ký bundle |
| `e8a5ae1` | P2 — giải nén và chạy conformance |
| `e6544de` | P3 — catalogue hợp nhất, chạy được episode thật |
| `5e2f1f9` | P4 — UI trong Models |

---

## 1. Kết quả: người dùng không phải dev làm được gì

Đăng nhập bằng tài khoản admin → **Models → tab "Nhập thuật toán"** → chọn tệp
`.zip` → bấm nhập. Sau đó:

- Server đọc mục lục zip, parse `plugin.json`, **không giải nén, không import**.
- Nếu manifest hợp lệ: giải nén vào thư mục riêng, nạp plugin trong **tiến trình
  con**, chạy bộ conformance của SDK.
- Nếu plugin hành xử đúng: nó xuất hiện trong `GET /algorithms` cạnh
  `astar+dwa`, và **chạy mô phỏng được ngay** dưới tên `astar+<plugin-id>`.

Không chạm terminal dòng nào. Có test đầu-cuối chứng minh: upload qua HTTP →
tạo simulation → chạy → episode có `steps > 5`, tiến trình worker thật sự chạy.

---

## 2. Hai quyết định An chốt trong phiên, và vì sao chúng đổi plan

| Câu hỏi | Chốt |
|---|---|
| UI nhận gì | Bundle `.zip` **có code** |
| Lane | **Subprocess bắt buộc** |

Quyết định cũ ngày 20-08 là "chỉ nhận `plugin.json`". Nó không đạt được mục tiêu
An nêu, vì manifest khai entry point chứ không chứa code — người dùng vẫn cần một
dev cài `planner.py` lên máy sweep.

Và lý do đứng sau quyết định cũ — "không đưa code lạ lên máy chủ" — **đã không
còn mô tả đúng hệ thống**: `_build_ppo` gọi `PPO.load()` unpickle checkpoint
người dùng upload, ngay trong tiến trình API. Nhận bundle code không mở ra lớp
rủi ro mới; nó dùng lại lớp đã chấp nhận, và đặt plugin vào lane cô lập tốt hơn
PPO đang có.

---

## 3. Từng phase đã làm gì

### P0 — `docs/plugin_import_security.md`

Threat model một trang, không code. Nội dung chịu lực:

- **Thứ tự** các bước, và bước nào còn từ chối được (mọi bước trước khi conformance chạy).
- **Quyền thật của code**: subprocess = cô lập crash và interpreter, **không phải
  sandbox**. Worker thừa kế environment, `PYTHONPATH`, quyền filesystem và mạng.
  Câu này đã có ở docstring lane và author guide §10; đây là chỗ thứ ba, và ba
  chỗ đồng ý là cố ý — đây là tuyên bố dễ bị làm nhẹ đi nhất khi kể lại.
- **Ai được import**: admin (`user.is_admin`), một lần kiểm ở một chỗ.
- **Bốn trần** với lý do từng cái. `max_plugin_extracted_mb` là cái quan trọng và
  dễ quên: dung lượng nén không nói gì về thứ giải nén ghi ra.

Trần đặt rộng như An dặn: 50 MB zip · 500 member · 200 MB sau giải nén · 64 KB manifest.

### P1 — nhận và đăng ký, chưa chạy gì

- `POST /api/v1/algorithms/plugins` (multipart), `GET`, `GET {id}`, `PATCH {id}`.
  **Không có DELETE** — cùng lý do trang Models không có: một bundle là thứ một
  benchmark *đã chạy*.
- `inspect_bundle()` đọc mục lục: zip magic, member path an toàn, số member, tổng
  sau giải nén, đúng một `*/.planbench-plugin/plugin.json`, kích thước manifest,
  JSON hợp lệ, rồi `parse_manifest` của SDK.
- **Refusal của SDK trả nguyên văn.** Tác giả plugin gặp đúng câu mà CLI sẽ nói;
  viết lại cho dễ nghe là cho một người hai từ vựng cho cùng một lỗi.
- Bảng `plugin_bundles` + alembic `0010`. **Unique trên `(plugin_id,
  plugin_version)`**, không phải `(owner, name, version)` như bảng `models`: định
  danh candidate lấy từ manifest, nên hai upload cùng một phiên bản plugin là hai
  câu trả lời cho "cái gì tạo ra kết quả này".

**Một chỗ cố ý khác `models`:** bundle mà manifest không parse được thì **từ chối
luôn**, không lưu thành `FAILED`. Model có định danh từ form nên còn chỗ ghi lý
do; bundle lấy định danh từ manifest — không manifest thì không có `plugin_id`,
và bảng khoá trên nó sẽ đụng ngay upload hỏng thứ hai.

29 test.

### P2 — giải nén và chạy thật

- `install_bundle()`: kiểm checksum trước khi giải, idempotent theo checksum,
  thay nguyên thư mục chứ không trộn.
- **Kiểm thoát thư mục lần thứ hai** lúc ghi file. P1 đã chặn tên xấu lúc đọc mục
  lục, nhưng chỉ kiểm ở thời điểm ghi mới biết file sẽ rơi vào đâu.
- Chạy `check_local_plugin` của SDK **qua lane subprocess**, deadline riêng 5 s
  (cố ý không phải control period: G4 hỏi có kịp chu kỳ của robot cụ thể không,
  còn đây hỏi có trả lời được và trả lời giống nhau hai lần không).
- `ValidationStatus.LOADED` lần đầu tiên trong đời dự án thật sự được sinh ra.

**Lỗ hổng tự tìm ra và bịt:** ở lane subprocess, plugin sập **không** ném lỗi —
handle biến worker chết thành **safe stop**, tức một `LocalPlanResult` hợp lệ
mang vận tốc 0. Nên một plugin sập mọi tick trả `(0, 0)` hai lần và **qua được
phép kiểm determinism bằng cách hỏng một cách đáng tin cậy**. Bộ suite không thấy
được vì nó đang nhìn lệnh, mà safe stop là một lệnh. Đã thêm phép đọc
`failure_reason`, có test riêng.

**Không chạy thì không gọi là qua.** Plugin đòi capability mà bên ngoài một
episode không dựng được (ví dụ `static-costmap`) thì để nguyên `structural` kèm
câu nói rõ capability nào chặn — không nhét dữ liệu giả rồi báo kết quả như bằng
chứng.

11 test.

**Trả hai món nợ đã ghi trong note ngày 24-08:**

- **N1:** `GraphBackedLocalPlanner.reset` không truyền `episode_seed` ⇒ mọi
  plugin channel-native nhận seed 0 ở **mọi** episode. Không có gì hỏng khi nó
  sai: một controller ngẫu nhiên chỉ rút đúng một mẫu cho cả sweep trong khi
  thống kê ghép cặp vẫn coi các lần rút là độc lập. Đã sửa, có test.
- **N2:** author guide dạy `step()` trả dict — đúng cho subprocess, **sai cho
  in-process** (host biến mọi tick thành safe stop, không exception nào). Guide
  giờ nói rõ hai lane hai kiểu trả về, kèm cảnh báo triệu chứng "robot đứng im mà
  không có lỗi".

### P3 — catalogue hợp nhất

- `packages/benchmark/planbench_benchmark/plugin_stacks.py`: dựng `_Entry` từ
  manifest. `config_model` sinh từ `config_schema` (extra="forbid", field nào
  không set thì không truyền, để default của plugin ở yên).
- `registry.py`: thêm `EXTERNAL_ALGORITHMS` + `_all_entries()`. Năm chokepoint
  (`algorithm_info`, `list_algorithms`, `_entry`, và hai `build_*`) đọc cả hai
  nguồn. **Built-in thắng khi trùng tên.**
- **Observation class từ chối chứ không đặt mặc định.** `AlgorithmInfo` cố ý
  không cho nó có default; ở đây lý do còn nặng hơn — hậu quả tệ nhất không phải
  candidate không nhãn mà là candidate **sai nhãn**, khi bảng xếp hạng trông công
  bằng trong lúc so một planner có cảm biến với một planner đọc ground truth.
- **Controller tự mang seam của nó.** `run_stack` hỏi `local_planner` xem có
  `channel_source` không khi caller không truyền. Vẫn một protocol, vẫn không
  nêu tên thuật toán nào — guard test cũ vẫn xanh.
- Catalogue dựng lại **theo đường ghi** (import / validate / đổi status / khởi
  động), không theo đường đọc: tập thuật toán đổi khi có người ghi, chứ không đổi
  theo việc ai vừa hỏi.

10 test, trong đó có **một episode thật**: bundle upload qua HTTP → simulation →
worker process → trajectory.

### P4 — UI

- Tab thứ ba trong Models cạnh Upload / Edit.
- **Cảnh báo cô lập nằm trên nút bấm**, không phải trong tooltip.
- **Báo cáo của host render nguyên trường**, không tóm tắt lại: registration
  state, evidence class, lane, đồ thị provider, mọi danh sách blocker, và câu
  `why` của chính host đặt cuối.
- Bảng thuật toán đã nhập, kèm **stack id** (`astar+org.vinai.vfh-plus`) — thứ
  report sẽ trích, để người đọc kết quả khớp được về hàng nào.
- Chỉ `active` **và** `loaded` mới được coi là chọn được. `structural` không phải
  đạt cũng không phải trượt — nó là "chưa ai chạy".
- i18n đủ `en` và `vi` (30 khoá mỗi bên). Phần quyết định để ở `lib/plugins.ts`
  và test riêng, vì repo không có jsdom. 8 test.

---

## 4. Một lỗi có sẵn của repo, tìm ra lúc làm P4

`.gitignore` dòng 140 là `models/` — **không neo**, nên nó khớp mọi thư mục tên
`models` ở mọi độ sâu, kể cả `apps/web/src/app/models/`.

**Toàn bộ trang Models chưa từng được commit.** Và `git status` sạch, vì file bị
ignore không hiện ra ở đó. Nếu không làm P4 thì không ai phát hiện — cho tới lúc
có người clone repo và trang Models 404.

Đã sửa thành `/models/` (neo gốc) cộng `/artifacts/models/` và
`/artifacts/plugins/` cho đúng thứ luật đó vốn định chặn. Commit P4 vì thế mang
theo 900 dòng `page.tsx` chưa từng vào git.

---

## 5. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/api/test_api_plugin_import.py` (mới) | 29 passed |
| `tests/api/test_api_plugin_conformance.py` (mới) | 11 passed |
| `tests/api/test_api_plugin_catalogue.py` (mới) | 10 passed |
| `tests/test_proof_plugins.py` (thêm 1) | 15 passed |
| `tests/test_algorithm_host.py`, `test_candidate_bridge.py`, `test_api_simulations.py` | 51 passed |
| `tests/api/test_api_models.py`, `test_api_plugin.py`, `test_api_sql_backend.py` | 69 passed, 1 skipped |
| `tests/test_conformance_and_cli.py` | xanh |
| `ruff check` apps/api, packages, services, tests | sạch |
| `tsc --noEmit` (web) | không lỗi mới (3 lỗi `paper.*` có sẵn từ trước, đã đối chứng bằng stash) |
| `vitest` `lib/plugins.test.ts` | 8 passed |

Full suite **chưa chạy** — theo lệnh An, chỉ chạy phần vừa sửa.

---

## 6. Việc còn lại

- **P5** — import VFH+ thật qua UI và chạy sweep ngắn. Chưa làm. Không có đợt này
  thì bốn đợt trên mới chỉ được chứng minh bằng bundle test tự dựng, chưa bằng
  một thuật toán thật ai đó cài từ bài báo.
- **P6** — role `global` trong lane subprocess (An đã duyệt "có làm"). Hiện
  `SubprocessPlugin` chỉ có `reset`/`step`, không có `plan`, nên v1 từ chối
  `role: "global"` kèm đúng lý do đó.
- **Chưa nối vào `CandidatePicker`** của trang Candidates/Decisions. Plugin đã
  vào `/algorithms` nên picker *sẽ* thấy nó, nhưng chưa rà lại giao diện đó.
- `ValidationStatus` docstring vẫn viết "deserialising a user-uploaded file …
  never happens inside the API process" — câu đó không đúng với đường PPO. Đã ghi
  vào threat model §3, chưa sửa docstring.

## 7. Ghi chú

Chưa merge, chưa push. Nhánh `tongduyan_plugin-import-ui`, năm commit, `main`
không bị đụng.
