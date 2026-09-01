# Báo cáo — Đợt B: Nối dây replanning vào `/simulate` và thêm nút bật ở UI

> **Ngày:** 2026-08-08
> **Plan nguồn:** `docs/antongduy/plans/2026-08-07/replanning-lien-tuc-va-noi-day-vao-simulate.md`, **Đợt B**
> **Nhánh:** `integrate-tongduyan`
> **Tiền đề:** Đợt A đã commit xong (xem
> `tongduyan_dot-a-p02-lop-quan-sat-khi-replanning.md`). Thứ tự bắt buộc
> A trước B đã được tôn trọng: giờ bật replanning từ UI không sinh ra số
> bị dán nhãn sai nữa.
> **Phạm vi:** chỉ Đợt B. **Không** đụng Đợt C (replan chu kỳ), **không**
> đụng Đợt D (hiệu chuẩn lại difficulty).

---

## 1. Vấn đề đang sửa

Replanning đã chạy thật từ Đợt 4.1, nhưng **mở app lên thì không thấy
gì**. Chỉ có một chỗ trong toàn hệ thống truyền luật replanning xuống
`run_stack()`:

| Nơi gọi | Trước Đợt B |
|---|---|
| `packages/benchmark/planbench_benchmark/runner.py` | có — `spec.replanning` |
| `apps/api/planbench_api/services.py` (`SimulationService.run`) | **không** |

`StoredSimulation` và `SimulationCreateRequest` không có trường
replanning, nên trang `/simulate` — **đúng cái trang người ta ngồi xem
robot bị kẹt** — không bao giờ replan được, dù có gọi API kiểu gì. Và
không có nút bật ở UI cho cả benchmark lẫn simulate: chỉ bật được bằng
cách gọi `POST /benchmarks` tay với body JSON.

## 2. Backend — một lát cắt dọc mỏng

### 2.1. Trường replanning đi hết chuỗi

| File | Thay đổi |
|---|---|
| `apps/api/planbench_api/schemas.py` | `SimulationCreateRequest.replanning`, `SimulationResource.replanning` |
| `apps/api/planbench_api/routers/simulations.py` | nhận từ request, echo lại trên resource |
| `apps/api/planbench_api/services.py` | `create(..., replanning)`; **`run()` truyền xuống `run_stack()`** — đây là dòng làm tính năng chạy được |
| `apps/api/planbench_api/repositories.py` | `StoredSimulation.replanning: ReplanningConfig = NO_REPLANNING` |
| `apps/api/planbench_api/repository_ports.py` | chữ ký `simulations.create()` |
| `apps/api/planbench_api/db/models.py` | `SimulationRow.replanning` — JSON, **nullable** |
| `apps/api/planbench_api/db/repositories.py` | dump khi ghi, `NULL` đọc ra `NO_REPLANNING` |
| `alembic/versions/0004_simulation_replanning.py` | **mới** — `add_column`, additive |

### 2.2. Ba quyết định

**Cột riêng, không nhét vào `config`.** `simulations.config` là tham số
của thuật toán; replanning là **luật áp lên run**. Nhét vào `config`
chính là đặt nó đúng chỗ mà benchmark tuyệt đối không được đọc từ đó
(cùng lý do 4.1 để `ReplanningConfig` trên `BenchmarkSpec` chứ không trên
`AlgorithmSpec.config`).

**Cột nullable, không backfill.** Mọi simulation lưu trước Đợt B chạy khi
đường code này chưa tồn tại. `NULL` **không** phải giá trị thiếu chờ điền
— nó là sự thật đã ghi. Repository đọc `NULL` thành `NO_REPLANNING` vì
đúng như vậy, và một lần backfill chỉ thay một câu trả lời đúng bằng bản
chép của chính nó. `NOT NULL` sẽ làm vỡ upgrade.

**`run()` đọc luật từ bản đã lưu, không từ mặc định.** Chạy lại một
simulation cũ tái hiện đúng điều kiện lúc nó được tạo, không phải mặc
định của hôm nay.

### 2.3. Migration — trả lời câu hỏi bỏ ngỏ của plan

Plan mục 3 điểm 6 hỏi "Đợt B có cần migration DB không (phải kiểm
`db/repositories.py` trước)". **Câu trả lời: có.** Khác với benchmark
(`BenchmarkRow.spec` là JSON nên 4.1 không cần migration), simulation lưu
`map_id`/`algorithm`/`config` thành cột riêng và không có chỗ trống nào
để nhét luật vào. Nên có `0004`, additive, downgrade là `drop_column`.

`tests/api/test_migrations.py::test_migration_matches_the_models` so
schema dựng bằng `upgrade head` với `Base.metadata` — nó pass, tức
migration và model không lệch nhau.

## 3. Frontend

### 3.1. Một component chung, không phải hai bản sao

`apps/web/src/components/ReplanningControls.tsx` phục vụ **cả**
`/simulate` **và** form tạo benchmark. Một component vì đây là một luật:
hai trang đặt nó cho hai thứ khác nhau (một run, hay cả sweep) nhưng ngữ
nghĩa và cảnh báo giống hệt, hai bản sao sẽ lệch nhau.

Ba tính chất được cài cứng:

1. **Mặc định tắt, và không nhớ giữa các lần load.** Không đi qua
   `persisted.ts` như các tùy chọn khác. Bật replanning là đổi lớp quan
   sát của global planner (Đợt A), nên nó phải là hành động có ý thức mỗi
   lần, không phải setting còn sót từ phiên trước.
2. **Không thể dựng ra trạng thái `enabled` với budget 0.** Bấm bật thì
   `max_replans` tự lên tối thiểu 1, ô số có `min={1}`. Server từ chối
   trạng thái đó với 422; UI không nên tạo ra được nó.
3. **Cảnh báo hiện ngay khi bật, trước khi chạy.** Robot phải đứng chờ
   hết cửa sổ stuck (mặc định 5 s) rồi mới được cấp đường mới, nên run
   lâu hơn hẳn. Không nói thì người xem tưởng app treo — đây là điểm plan
   B.2 nêu đích danh. Với benchmark, nói thêm rằng luật áp cho **mọi
   stack trong sweep**, không phải tham số của một thuật toán.

Payload **bỏ hẳn trường** khi tắt thay vì gửi `{enabled: false}`. Hôm nay
hai cách tương đương, nhưng bỏ hẳn là thứ bảo đảm một form chưa ai đụng
vào không bao giờ đổi `conditions_checksum` của benchmark.

### 3.2. Marker replan trên timeline replay

Benchmark detail vẽ chấm hổ phách ở mỗi thời điểm replan, dùng lại đúng
cơ chế của chấm đỏ va chạm (F08 mục 2.2). Màu khác vì **replan không
phải thất bại** và không được đọc thành thất bại.

Thời điểm lấy từ `result.events` (`type === "replan"`), **không** suy từ
trajectory — một lần replan không để lại dấu vết nào trong các mẫu, đó
chính là lý do engine phát event cho nó.

### 3.3. `MetricsPanel`

Thêm ô `Replans`, **chỉ hiện khi khác 0**. Một cột số 0 trên mọi run khác
không nói gì và làm loãng các metric có nói.

### 3.4. i18n

6 key mới ở **cả** `en.json` và `vi.json`: `replanning.enable`,
`replanning.hint`, `replanning.maxReplans`, `replanning.slowWarning`,
`replanning.benchmarkScope`, `metrics.replanCount`, `detail.replanAt`.

## 4. Gộp lại premise test của hai suite

`tests/blocked_route.py` (**mới**) giữ map hai cửa + scenario bị chặn.
Trước đây nó nằm trong `tests/test_replanning.py`; giờ suite API cũng
cần đúng premise đó.

Không phải để đỡ lặp code, mà để **không lệch nhau**:
`test_replanning.py` chứng minh engine replan được, `test_api_simulations.py`
chứng minh đường đi qua `/simulate` chạm tới engine đó. Nếu hai bản premise
trôi khỏi nhau, test API có thể pass trên một scenario chưa bao giờ bị
chặn — và đúng phần nối dây mà nó tồn tại để kiểm sẽ không được kiểm,
trong khi trông như đã kiểm.

## 5. Test — đối chiếu danh sách bắt buộc của plan (B.3)

| Plan B.3 yêu cầu | Test |
|---|---|
| Backend: tạo simulation có replanning → `run` thật sự replan trên scenario bị chặn | `test_the_same_run_reaches_the_goal_with_it` (`replan_count >= 1`, status `success`) |
| Backend: simulation cũ (payload không có field) chạy được, `replan_count = 0` | `test_a_payload_that_never_mentions_it_runs_with_it_off` |
| Backend: `enabled=true, max_replans=0` bị từ chối với thông báo đọc được | `test_enabled_with_a_zero_budget_is_refused_with_a_readable_reason` (422, message chứa "does nothing") |
| Frontend: form gửi đúng payload | `replanning-controls.test.tsx` — "the rule reaches the server" |
| Frontend: replay hiện marker replan | `benchmark-replay.test.tsx` — "marks every replan on the timeline" |
| Frontend: mặc định tắt | `replanning-controls.test.tsx` — "the switch is off unless somebody turns it on" |

Thêm ngoài danh sách:

- **Test đối chứng.** `test_a_blocked_robot_stays_blocked_without_it` —
  cùng map, cùng scenario, không bật: `stuck`, `replan_count == 0`. Không
  có test này thì test kế tiếp không chứng minh được gì; nó có thể pass
  trên một scenario mà robot vốn đã tới đích.
- **Event có mặt trong payload API.** Test khẳng định
  `result.events` chứa `type == "replan"` — đây đúng là thứ marker
  timeline đọc, nên kiểm ở tầng API là kiểm cả hợp đồng của UI.
- **Luật được echo lại** trên cả `POST` lẫn `GET /simulations/{id}`.
- **Không nhớ lựa chọn giữa các lần load** — test khẳng định `persisted`
  không xuất hiện gần `replanning` ở cả hai trang.
- **Payload bỏ hẳn trường khi tắt** — test ghim cả hai chỗ (`api.ts` và
  form benchmark).

## 6. Kiểm chứng

### 6.1. Backend

```text
python -m pytest tests/ -q --ignore=tests/api    981 passed, 4 skipped in 67s
python -m pytest tests/api -q                    448 passed, 1 skipped in 404s
                                       tổng:    1429 passed, 5 skipped
ruff format + ruff check                         sạch
```

Baseline sau Đợt A là `1424 passed, 5 skipped`. Chênh đúng **+5**, là số
test mới của `TestReplanningOverTheApi` trong `tests/api/test_api_simulations.py`.
**Không có fail mới.**

`tests/` trừ `tests/api` giữ nguyên **981** như sau Đợt A: đợt này không
thêm test ở đó, chỉ chuyển premise của `test_replanning.py` sang module
dùng chung (24 passed + 1 skipped, không đổi).

### 6.2. Frontend

```text
npm run typecheck    sạch
npm run build        Compiled successfully
npm test             455 passed / 1 failed + 1 suite fail — CẢ HAI PRE-EXISTING
```

Baseline sau Đợt A là `443 passed / 1 failed`. Chênh **+12**: 11 test mới
trong `replanning-controls.test.tsx` và 1 trong `benchmark-replay.test.tsx`.
Hai failure y hệt đã ghi ở report Đợt 3.2, 4.1 và A (`assistant-page`
đọc file không tồn tại trên nhánh; `dashboard-page` so path cứng
`"/system/page.tsx"` với path Windows). Không thêm và không sửa failure
nào.

## 7. Definition of Done của plan (B.4) — đối chiếu

- [x] Bật replanning từ UI `/simulate` và thấy robot đi đường vòng.
      (Chứng minh bằng test API chạy đúng luồng `POST /simulations` →
      `POST .../run`: `stuck` khi tắt, `success` khi bật, cùng map cùng
      scenario.)
- [x] Bật từ form benchmark.
- [x] Simulation/benchmark cũ vẫn đọc và chạy được (cột nullable,
      payload không có field).
- [x] Marker replan hiện trên timeline replay.
- [x] `npm run typecheck` + `npm run build` sạch.

## 8. Rủi ro và giới hạn còn lại

| Rủi ro / giới hạn | Ghi chú |
|---|---|
| **Đường toàn cục vẽ trên màn hình là đường của lần plan ĐẦU** — robot rời khỏi đường đang vẽ sau khi replan, trông như bug renderer | **#163.** Ảnh hưởng đúng vào tính năng vừa nối dây, nên phải nói rõ. Sửa đúng là thêm `StackRun.plans: tuple[PlanResult, ...]`, kéo theo payload WS, `SimulationResultResponse`, artifact episode và bản đọc ngược dữ liệu cũ — đổi contract, không nhét vào Đợt B |
| `/simulate` không có marker replan trên timeline | **#161.** Luồng WebSocket chỉ phát `start`/`state`/`result`, không phát `events`. Sửa đúng là cho WS phát events — đụng contract socket |
| Lựa chọn replanning không được nhớ giữa các lần load | **#160.** Chủ ý, có test khóa |
| `/simulate` tạo scenario row mới mỗi lần chạy | **#162.** Có từ trước Đợt B, nhưng giờ dễ gặp hơn khi bật/tắt rồi chạy lại |
| Migration `0004` chưa chạy trên deployment thật | Additive + nullable, downgrade sạch. `test_migrations.py` kiểm upgrade/downgrade/repeatable và so với model |

## 9. Việc kế tiếp theo plan

**Đợt C** (replan theo chu kỳ) vẫn chờ user chốt **sáu câu hỏi ở mục
C.3** của plan. Hai câu chặn nhất:

1. `replan_period` có được tune không — nếu có thì bắt buộc phải vào
   `SEARCH_SPACES` của P01 với cùng ngân sách cho mọi planner, nếu không
   thì đó đúng là bất công bằng kiểu S2 mà đề bài phê phán.
2. Chi phí chạy benchmark tăng bao nhiêu — mỗi replan là một lần chạy
   A\*/RRT\* đầy đủ; phải đo trên một scenario rồi mới chốt chu kỳ mặc
   định.

**Đợt D** chỉ sau A–C.

Ngoài plan: **#163 (đường vẽ là đường plan đầu)** nên được xử lý sớm —
nó là thứ người dùng nhìn thấy ngay khi bật tính năng vừa nối dây, và
`StackRun.plans` cũng là thứ Đợt C sẽ cần.
