# Thi hành plan role: P0–P5 xong, P6 dở — 2026-08-27

Báo cáo cập nhật lần 2, lúc An bảo tạm dừng. Bản đầu chỉ phủ P0–P2;
bản này phủ tới P6. Tên file giữ nguyên để link cũ không hỏng.

Plan: `plans/2026-08-27/thiet-ke-role-engineer-reviewer-admin.md` (13
phase P0–P12). Khảo sát nền: `notes/2026-08-27/tongduyan_khao-sat-hien-trang-role.md`.

## 0. Trạng thái một bảng

| Phase | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| P0 | Hợp đồng HĐ-14 + docstring | **xong** | `9d05905` |
| P1 | Role, capability, profile, invariant | **xong** | `1174261` |
| P2 | Đóng auth, ownership, archive, WS ticket | **xong** | `8ccb20a` |
| P3 | Plugin governance + publication | **xong** | `b957d3f` |
| P4 | Pin định danh candidate | **xong** | `8ec02f1` |
| P5 | Dừng hợp tác tại episode boundary | **xong** | `e977df8` |
| P6 | Luồng duyệt claim/ack/decide | **dở, chưa commit** | — |
| P7–P12 | reliance, admin, web, desktop | chưa bắt đầu | — |

Nhánh `tongduyan_roles-capabilities`, tạo từ `main`. **Chưa push remote nào.**

**Nhánh này giờ mang hai luồng việc.** Ngoài 7 commit của tôi, An đã
commit 5 bản ghi AI-analyst lên cùng nhánh (`3f7f0b4`, `7a4b10f`,
`27a6035`, `a644369`, `dfcbed4`) — toàn bộ là `docs/antongduy/`, không
đụng dòng code nào của phần role. Không xung đột, nhưng nếu An định mở
PR riêng cho từng luồng thì phải tách trước.

Stash `stash@{0}` của An (gitignore + ai-log của `tongduyan_updater-cdn`)
vẫn treo — chi tiết ở mục 1.1 bản báo cáo đầu, không đổi.

---

## 1. P2 — đã hoàn thành sau khi resume (`8ccb20a`)

Điểm dừng lần trước là 5 test WebSocket đỏ. Nguyên nhân đúng như đã
đoán: router `ws` mount ngoài `/api/v1`.

**Sửa**: tách làm hai router. Socket ở ngoài prefix (nó không phải tài
nguyên có version); endpoint ticket là POST có auth như mọi route khác
nên vào dưới `/api/v1`. Gộp chung chỉ *trông* gọn — nó để route duy nhất
trong file cần bearer token nằm chỗ không client nào tìm.

Phần còn lại của P2 làm nốt:

- `resource.read` áp cho **mọi GET tài nguyên**: `decisions.py` (trace,
  `report.md`, `report.xlsx`, `approved_config.yaml`, `/audit`,
  `/explanation`, `/exemplars`, `/replay-sync`, candidate, task-profile,
  job), `library.py`, `algorithms.py` (dùng `algorithm.catalogue`).
- `is_reference` nối vào `decision_service.delete` — deployment tham
  chiếu từ chối xoá, và thông báo nói vì sao (nền cố định để so validation
  run, hai lần chạy chỉ so được nếu nền không đổi giữa chúng).
- 30 test khẳng định 401 đổi sang fixture `anonymous`. Thêm fixture
  `sql_client` đăng nhập sẵn (8 test SQL backend).
- `tests/api/test_api_access.py` mới, **18 test**: writes/reads bị chặn,
  evidence không public, ownership, archive, ticket (dùng một lần, hết
  hạn, cần tài khoản).

**Nghiệm thu**: `tests/api/` 973 pass / 5 fail, trong đó 3 có sẵn và 2
mới đã sửa ngay (xem mục 7).

---

## 2. P3 — publish thành một hành động (`b957d3f`)

**Vấn đề**: bundle validate xong là vào picker mọi người ngay, và
`_retire_previous()` tự disable revision cũ đúng lúc revision mới qua
kiểm — máy quyết định cái gì đang chạy, không ai ký.

**Migration `0013`**:

```
plugin_bundles.status  → thêm giá trị 'held'   (active | held | disabled)
plugin_bundles.disabled_at / disabled_by_user_id / disabled_reason
plugin_publications  (append-only: published_at, superseded_at, unpublished_at)
  + partial unique uq_plugin_publication_current
plugin_events        (append-only: actor_roles, authorized_capability, reason)
```

**Publication là lịch sử, không phải con trỏ.** Đây là chỗ tôi phản biện
An ở vòng thiết kế và giữ nguyên khi làm: publish revision mới **đóng
dấu** `superseded_at` lên dòng cũ, reviewer rút thì đóng dấu
`unpublished_at` — hai cột khác nhau vì hai sự thật khác nhau. Upsert
theo `plugin_id` sẽ làm cả hai thành cùng một sự vắng mặt, và approval
gắn với revision đó về sau không phân biệt được "có bản mới" với "bị rút".

**Cờ `PLANBENCH_ALGORITHM_GOVERNANCE`, mặc định tắt.** Cờ tắt thì
resolver giữ nguyên luật cũ (`_retire_previous` vẫn chạy) — bản đang
chạy không bị đổi nền. Route governance trả **404** khi tắt, không phải
403: "bạn không được phép" và "deployment này chưa bật" là hai câu trả
lời khác nhau, client phân biệt được thì ẩn nút thay vì mời bấm rồi hỏng.

Khác: `_require_admin` → `_require_capability(algorithm.import)`;
revalidate mang `algorithm.validate` (cùng gói, khác việc, audit phải
nói đúng); `PluginBundleSummary.of(..., inspect=)` cắt manifest/checksum
cho người không có `algorithm.inspect`; disable **terminal**, không có
route enable.

**Test**: `tests/api/test_api_plugin_governance.py`, **17 test** —
gồm hai pin quan trọng: cờ tắt thì catalogue y hệt hôm nay, và cờ bật
thì `unpublish ≠ supersede` trong bảng publications.

**Sửa flaky có sẵn**: `bundle_zip()` trong test dùng `writestr` đóng dấu
thời gian hiện tại, mà dấu thời gian zip có độ phân giải 2 giây — build
hai lần trong cùng giây ra cùng bytes, khác giây thì khác. Vì định danh
bundle là checksum của bytes đó, test "cùng archive không import hai
lần" xanh trên máy nhanh và đỏ trên máy tải nặng. Ghim `ZipInfo(date_time=…)`.

---

## 3. P4 — pin định danh candidate (`8ec02f1`)

**Vấn đề**: tên stack là con trỏ; hàng đợi đặt thời gian giữa lúc theo
con trỏ và lúc chạy. Reviewer publish revision mới hoặc rút một cái ở
giữa ⇒ job đo thứ không ai chọn, lưu dưới id nói ngược lại.

**Module mới `run_identity.py`**: `resolve()` theo con trỏ **một lần**
lúc nhận request; `recheck()` lúc job start so với cái đã pin — khác biệt
là một cái *kiểm* thì fail được và nói tên thứ đã đổi, còn resolve lần
hai thì không nhận ra gì.

**Migration `0014`**: `decision_run_candidates` (bundle_id, plugin_id,
revision, archive_checksum, provider_fingerprint, runtime_profile) +
`decision_runs.purpose`. Ghi **cùng transaction** với run.

Luật: production chỉ pin được cái đã publish; validation được pin cái
chưa publish nhưng **phải nêu `bundle_id`** — alias resolve tới bản
published theo định nghĩa, nên nó sẽ trả reviewer đúng bản họ *không*
định xem.

`scripts/backfill_run_candidates.py`: khớp run cũ bằng
`manifest_checksum`, mặc định chỉ in báo cáo, `--write` mới ghi. Không
khớp ⇒ để trống ⇒ reliance `unknown` (câu trả lời đúng).

**Test**: `tests/test_run_identity.py`, **16 test**.

---

## 4. P5 — dừng tại ranh giới episode (`e977df8`)

`JobQueue.cancel` **vẫn luôn nói** job đang chạy "stops at its next
cooperative check", và không chỗ nào trong đường decision hỏi cả. Nên
sweep 3 tiếng không huỷ được, và thuật toán bị tắt giữa chừng vẫn được
đo tiếp rồi lưu thành bằng chứng.

- `simulate(..., should_stop=)` hỏi ở **đầu mỗi cặp (episode, candidate)**
  — dừng giữa episode để lại trace viết dở đúng loại artefact mà
  `TraceLocator` sau đó phải đoán.
- Dừng kiểu này **raise** (`SweepStopped`), không chấm phần đã có. Ngược
  hẳn với `KeyboardInterrupt`: interrupt nghĩa là người ta muốn thôi
  chờ nên phần trên đĩa vẫn là một run nhỏ hơn trung thực; cái này nghĩa
  là thứ đang đo thôi đúng giữa chừng, và nửa phép so trong điều kiện đó
  là thí nghiệm khác chứ không phải ngắn hơn.
- `Job` mang `created_by`, `purpose`, `run_id`, `pinned`, và `submit()`
  đóng dấu chúng **trước khi** job có thể chạy (queue rảnh thì job chạy
  ngay, field ghi sau `submit` trả về có thể bị đọc rỗng).

**Test**: `tests/test_sweep_stop.py`, **7 test**.

---

## 5. P6 — đang dở, chưa commit

### 5.1. Đã xong trong P6

- **Migration `0015`** (đã chạy, models khớp, `test_migrations` xanh):
  `review_requests` recreate bằng `batch_alter_table` — `subject_kind` /
  `subject_id`, `requested_reviewer_user_id`, `claimed_by_user_id`,
  `claimed_at`, `available_to_pool`; `benchmark_id` và `reviewer_user_id`
  thành nullable; `decision_runs.current_review_request_id`.
- **`review.py`**: `ReviewSubject`, status mới (`open`, `claimed`,
  `acknowledged`), `LIVE_STATUSES`, `ReviewConflict`, `claimable_by()`.
- **`decision_review.py`** (mới): submit / cancel / claim / takeover /
  release / close / `require_claimant` / `acknowledged_under` /
  `release_lost_claims`. Cộng `submission_of()` — `submission` **derive**
  từ request đang sống, không có cột.
- **Routes**: `/decisions/{id}/submit`, `/submit/cancel`, `/claim`,
  `/takeover`, `/release`, `/review-state`.
- **`decide_config`**: thêm 5 điều kiện — có card, comment bắt buộc,
  đang claim bởi chính người đó, **có acknowledge dưới claim hiện tại**,
  và `actor ≠ created_by` (nới được bằng `relaxed`, khi đó audit ghi
  `self_approve_config`).
- **Thứ tự refusal**: "run này không có card" trả lời **trước** "anh
  không giữ review này" — cái đầu là sự thật về artefact, cái sau về
  người hỏi; hỏi ngược sẽ đẩy người ta đi tìm một quyền không giúp được gì.
- `tests/api/test_api_decisions.py::TestTheTwoHumanActsOverHttp` cập
  nhật để đi qua luồng mới — **4 test xanh**.

### 5.2. Điểm dừng chính xác

`tests/api/test_api_decision_review.py` (mới, ~25 test) **chưa chạy
được**: fixture `ranked_run` sai.

Hai lỗi đã tìm ra, lỗi thứ hai chưa sửa:

1. ~~`local_config: dwa_fine` không tồn tại~~ → đã đổi `dwa_default`.
2. **Còn lại**: scope mặc định `global_planner_selection` đòi tầng local
   **giống hệt** ở mọi candidate, nên hai candidate khác `local_config`
   bị `ExperimentScopeViolation` → 500. Muốn có run **ranked** (có card
   để ký) phải dùng deployment của lát cắt dọc, đúng như
   `test_api_decisions.py::…::ranked_run` đang làm:

```python
from test_vertical_slice import write_profile
profile_path = write_profile(tmp_path)
app.state.decision_map_root = tmp_path          # profile trỏ map tương đối
payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
created = client.post(f"{API}/task-profiles", json=payload, headers=alice_headers)
# rồi astar+dwa vs rrtstar+dwa, episodes=6
```

Sửa fixture đó là việc đầu tiên khi resume. Bản vá đã soạn nhưng **chưa
ghi vào file** (lệnh bị dừng giữa chừng), nên `tests/api/test_api_decision_review.py`
hiện vẫn giữ fixture cũ.

### 5.3. P6 còn thiếu gì

- Chạy và làm xanh `test_api_decision_review.py`.
- `release_lost_claims` đã viết nhưng **chưa ai gọi** — phải nối vào chỗ
  gỡ role và disable tài khoản (P8 có route đó; hoặc gọi tạm từ
  `set_roles`/`set_disabled`).
- Withdraw (`/config-approval/withdraw`) chưa đổi theo plan: hiện vẫn là
  route cũ, chưa cho **bất kỳ reviewer** rút, chưa bắt comment, chưa đưa
  `submission` về `none`.
- `benchmark` lane: service mới đã từ chối động vào, nhưng chưa có test
  pin rằng request benchmark cũ **không** claim/takeover được.
- Chưa chạy full `tests/api/` sau P6.

---

## 6. Việc chưa bắt đầu

P7 (reliance derive + `approved_config` mang `candidate.bundle` + bật
cờ governance) · P8 (admin routes) · P9–P11 (web) · P12 (desktop, `.env`
ba tài khoản, smoke gate ca upgrade).

Nhắc lại ràng buộc chi phối P12: **bản desktop đã phát hành đang được ban
giám khảo chấm bằng `admin:admin`**. Cơ chế đỡ đã có từ P1 (reconcile
role ở API startup), nhưng phần launcher desktop `setdefault` profile
**chưa viết**.

---

## 7. Test — con số và cái gì có sẵn

| Bộ | Kết quả |
|---|---|
| `tests/test_roles.py` | 38 pass |
| `tests/test_run_identity.py` | 16 pass |
| `tests/test_sweep_stop.py` | 7 pass |
| `tests/api/test_api_access.py` | 18 pass |
| `tests/api/test_api_plugin_governance.py` | 17 pass |
| `tests/api/` (sau P3) | 973 pass / 5 fail |
| `tests/` trừ api (sau P1) | 3546 pass / 10 fail / 8 error |

**Năm lỗi ở `tests/api/` sau P3**, đã phân loại hết:

| Test | Nguyên nhân | Của tôi? |
|---|---|---|
| `test_api_advice.py::…::test_an_unknown_run_is_a_404` | `DecisionRunService` thiếu `trace_summary` — bug trên `main` | không |
| `test_decision_export_golden.py` × 2 | golden `.md` checkout CRLF, so với `\n` | không |
| `test_migrations.py::test_migration_matches_the_models` | ba cột `disabled_*` tôi chèn nhầm vào bảng `models` thay vì `plugin_bundles` | **của tôi, đã sửa** |
| `test_api_plugin_import.py::…::test_the_same_archive_cannot_be_imported_twice` | flaky dấu thời gian zip (mục 2) | có sẵn, **đã sửa** |

**10 lỗi + 8 error ở `tests/` trừ api** — đều có sẵn, khớp đúng danh
sách note 2026-08-26: `test_host_parity_golden` (5),
`test_dwa_core_refactor` (5), `test_outcome.py` (8 error,
`UnicodeDecodeError: 'charmap'` — lỗi encoding cp1252 trên Windows).

**Đã xác minh bằng worktree**: 24 lỗi `fixture 'client' not found` khi
trộn `tests/*.py` với `tests/api/*.py` trong **một** lần chạy pytest là
có sẵn ở commit P0. Chạy hai lần riêng thì không có.

---

## 8. Quyết định thiết kế phát sinh khi làm (không có trong plan)

Ghi lại vì chúng đổi hoặc làm rõ plan:

1. **`status` của plugin thêm giá trị thứ ba thay vì thêm cột.**
   `operational_status` riêng sẽ là câu trả lời thứ hai cho câu hỏi cột
   `status` đã trả lời. Ba giá trị `active | held | disabled`, wire-
   compatible với hai giá trị cũ.
2. **`held` thay `quarantined`** như plan D13 — nhưng lý do cụ thể hơn:
   `QuarantinedPlugin` trong discovery (H5) đã nghĩa "manifest không
   parse được".
3. **Fixture test `client` đăng nhập sẵn.** 306 lời gọi GET, 128 có
   header; sửa 178 chỗ là churn cơ học. Đổi mặc định rồi sửa ~30 chỗ
   *thật sự nói về ẩn danh* — mỗi sửa đổi đều có nghĩa.
4. **Thêm tài khoản seed `erin:engineer`** trong conftest. Alice/bob/carol
   mang `engineer+reviewer`, nên test "người không có quyền bị chặn" cần
   một người thật sự không có.
5. **Ticket router tách khỏi socket router** (mục 1).
6. **Thứ tự refusal artefact-trước-người** (mục 5.1).
7. **`_decision_action()`** chọn `self_approve_config` khi một tài khoản
   vừa tạo run vừa ký — kết quả giống nhau, bản ghi thì không.

---

## 9. Lệnh để tiếp tục

```powershell
git switch tongduyan_roles-capabilities      # đang ở đây
git status --short                           # P6 dở, chưa commit

python -m pytest tests/test_roles.py tests/test_run_identity.py tests/test_sweep_stop.py -q
python -m pytest tests/api/test_api_decisions.py -q          # 70 pass
python -m pytest tests/api/test_api_decision_review.py -q    # ĐỎ: sửa fixture ranked_run trước
```

Không có gì chạy nền. Không push remote nào. `.ai-log/` chưa commit —
phải quét secret bằng regex trước.
