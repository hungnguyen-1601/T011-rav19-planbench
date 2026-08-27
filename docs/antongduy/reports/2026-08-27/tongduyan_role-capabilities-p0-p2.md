# Thi hành plan role: P0, P1 xong — P2 đang dở — 2026-08-27

Báo cáo lúc An bảo tạm dừng. Plan: `plans/2026-08-27/thiet-ke-role-engineer-reviewer-admin.md`
(bản cuối, 13 phase P0–P12). Khảo sát nền:
`notes/2026-08-27/tongduyan_khao-sat-hien-trang-role.md`.

## 0. Trạng thái một bảng

| Phase | Trạng thái | Commit |
|---|---|---|
| P0 — hợp đồng + docstring | **xong, đã commit** | `9d05905` |
| P1 — role, capability, profile, invariant | **xong, đã commit** | `1174261` |
| P2 — đóng auth, ownership, archive, WS ticket | **dở, chưa commit** | — |
| P3–P12 | chưa bắt đầu | — |

Nhánh: `tongduyan_roles-capabilities`, tạo từ `main`.
**Chưa push remote nào.**

## 1. Nhánh và chỗ An cần biết trước tiên

### 1.1. Có một stash của An đang treo

Lúc tạo nhánh, ba file tracked của An chặn checkout (`.gitignore`,
`.ai-log/archive/2026-08-26.jsonl`, `.ai-log/session.jsonl` — thuộc
nhánh `tongduyan_updater-cdn`, không thuộc việc role). Đã park:

```
stash@{0}  An: gitignore + ai-log on tongduyan_updater-cdn (parked by roles work 2026-08-27)
```

Về `tongduyan_updater-cdn` rồi `git stash pop` để lấy lại. Hai stash cũ
(`{1}`, `{2}`) là của An từ trước, không đụng tới.

### 1.2. `main` đang thiếu 5 commit của `tongduyan_updater-cdn`

An bảo lấy head `main`, đã làm đúng vậy. Hệ quả cần biết: nhánh này
**không có** `CLAUDE.md` (nó được track ở `tongduyan_updater-cdn`, còn
`main` vẫn ignore) và không có hai commit sửa release workflow. Việc role
không đụng gì tới các file đó nên merge sau sẽ không xung đột, nhưng nếu
An muốn nhánh role đứng trên bản mới nhất thì rebase lên
`tongduyan_updater-cdn` trước khi làm tiếp.

### 1.3. Nhánh AI analyst không bị ảnh hưởng

`tongduyan_ai-analyst-ban-8` nằm ở worktree riêng
(`E:/VinAI/RoboMind_project/P-011-analyst`). Không file nào của nó bị
chạm. Trong cây chính có vài file untracked của An
(`docs/antongduy/{notes,plans,reports}/2026-08-27/*analyst*`,
`*guide*`) — **không stage cái nào**, đúng luật §3.

---

## 2. P0 — hợp đồng nói lại đúng thứ đang chạy (`9d05905`)

**Vấn đề**: HĐ-14 mô tả hai vai `engineer`/`approver` và "một cột
`role`" — thứ đã bị xoá khỏi code từ lần refactor accounts. Hợp đồng nói
một đằng, hệ chạy một nẻo, suốt nhiều tháng.

**Đã làm**:

- Viết lại toàn bộ HĐ-14 thành 7 mục: ba tầng quyền, ba gói capability,
  publish gate cho thuật toán ngoài, duyệt ba bước, separation of duties,
  tách `approval.status` khỏi `reliance_status`, và các bất biến.
- `contracts_version` 6.9.0 → **7.0.0 (MAJOR)** + changelog + mục "Chi
  tiết 7.0.0" giải thích vì sao MAJOR và ba khái niệm bản cũ không có.
- Cập nhật docstring `accounts.py`, `auth.py`, `approval.py` — ghi lại
  quyết định đảo ngược và lý do, để lần sau không ai đọc thấy "there are
  no roles to require" rồi tưởng đó là thiết kế hiện hành.
- `docs/plugin_import_security.md` §5: `is_admin` → capability
  `algorithm.import`, và nói rõ import ≠ publish.

**Nghiệm thu**: `tests/test_vertical_slice.py` xanh (nghĩa vụ MAJOR theo
mục 0 luật 3), `tests/test_contract_version.py` xanh.

---

## 3. P1 — role thành gói capability (`1174261`)

### 3.1. Migration `0012_roles_and_ownership`

```
user_roles(user_id, role, granted_by_user_id, reason, granted_at)
  + partial unique index uq_single_demo_owner (role='demo_owner')
users.disabled_at, users.last_sign_in_at
account_events  (append-only: actor_roles, authorized_capability, reason, override)
maps.owner_user_id, maps.archived_at
scenarios.owner_user_id, scenarios.archived_at
task_profiles.archived_at, task_profiles.is_reference
backfill: mọi user → engineer; is_admin=true → + admin  (KHÔNG ai tự thành reviewer)
```

Đã chạy thật trên SQLite sạch: upgrade 0011 → head, backfill đúng, index
partial **cắn** (insert demo_owner thứ hai bị `IntegrityError`),
downgrade về 0011 sạch.

### 3.2. Code

- `accounts.py`: `Role`, `Capability` (22 giá trị), `CAPABILITIES`,
  `ALL_CAPABILITIES`, `capabilities_of`, `roles_granting`,
  `AccountEvent`, `LastAdministratorError`.
- `User.roles` là **nguồn thật**; `is_admin` thành property dẫn xuất.
  Cột `users.is_admin` còn trong bảng nhưng không đọc/ghi nữa (bỏ ở
  migration sau) — tránh hai bản ghi cùng một sự thật.
- `auth.py`: `require_capability(...)` một dependency; ba alias
  `ReadingUser` / `WritingUser` / `SimulatingUser`. Token bị từ chối nếu
  tài khoản `disabled`. 403 nêu role cần **và** ai đang giữ.
- `deployment.py` (mới): `DeploymentProfile` (production /
  desktop-single-user / demo), `SeparationOfDuties`, `DeploymentPolicy`,
  `load_policy`, `guard_stored_state`. Vắng biến = `production`;
  `relaxed` bị từ chối trên server dùng chung; production còn demo_owner
  ⇒ **từ chối khởi động**, thông báo nêu tên tài khoản và trỏ runbook.
- `PLANBENCH_SEED_USERS` khôi phục field giữa: `name:roles:password`
  (`engineer+reviewer+admin`). Reconcile **mỗi boot** cạnh chỗ đang
  reconcile password — chỉ **thêm**, không gỡ role đã gán qua UI, và chỉ
  trên profile một người.
- `apply_admin_policy` → `apply_role_policy`, cộng binding demo_owner
  theo verified email hoặc nickname; đổi env trỏ người khác khi đã có
  demo_owner ⇒ raise, không chuyển ngầm.
- Invariant "còn người quản trị": đếm **capability `user.manage`**,
  không đếm tên role; chạy trong cùng transaction (SQL) / trong cùng
  lock có rollback (in-memory).
- `/auth/me` trả thêm `roles` và `capabilities`.
- Repository: `set_roles`, `set_disabled`, `record_sign_in`,
  `list_with_role`, `record_account_event`, `list_account_events` — cả
  hai backend.

### 3.3. Test

`tests/test_roles.py` mới, **38 test**, chia sáu nhóm. Đáng chú ý:

- Union ba gói == `ALL_CAPABILITIES` ⇒ thêm capability mà quên xếp vào
  gói nào là **test đỏ**, không phải bug quyền phát hiện sau vài tháng.
- Ba gói **không lồng nhau** (pin tính chất, không pin danh sách).
- Admin không có `run.create` / `run.review` / `algorithm.publish` /
  `resource.write`.
- Invariant quản trị: pin trên **cả hai** backend, kèm ca "demo_owner
  cũng tính là quản trị" và "admin bị disable thì không tính".
- Reconcile: tài khoản tạo trước khi có role vẫn nhận đủ role sau boot;
  reconcile thêm mà không gỡ; production bỏ qua role trong seed.
- Role lạ trong DB không làm account không load được.

Ngoài ra sửa 2 test cũ: pin field `/auth/me` (thêm `roles`,
`capabilities`) và `test_admin_can_be_granted_and_revoked` (giờ đi qua
`set_roles` và phải có người quản trị khác).

### 3.4. Bằng chứng

Chạy `tests/api/` đầy đủ (943 test, 27 phút): **940 pass, 3 fail**.
Cả 3 đều **có sẵn từ trước P1**, đã xác minh:

| Test | Nguyên nhân | Có phải do tôi? |
|---|---|---|
| `test_api_advice.py::…::test_an_unknown_run_is_a_404` | `DecisionRunService` không có `trace_summary` — bug trên `main` | không (không chạm file decision nào) |
| `test_decision_export_golden.py` × 2 | golden `.md` checkout thành CRLF, so với `\n` | không (đúng thứ CLAUDE.md §6 dặn đừng pin) |

Cũng xác minh 24 lỗi `fixture 'client' not found` khi trộn `tests/*.py`
với `tests/api/*.py` trong **một** lần chạy pytest là **có sẵn** — dựng
worktree ở commit P0 chạy lại, ra đúng 24 lỗi y hệt. Cách tránh: chạy
`tests/` và `tests/api/` thành hai lần.

---

## 4. P2 — đang dở, chưa commit

### 4.1. Đã xong trong P2

- **Đóng lỗ auth** (đây là lỗ hổng thật, note 2026-08-24 xếp là blocker):
  - `simulations.py` 5/5 route: đọc cần `resource.read`, tạo/chạy cần
    `simulation.run`.
  - `maps.py`, `scenarios.py`: đọc `resource.read`, ghi `resource.write`.
  - `ws.py`: không còn accept vô điều kiện.
- **WS ticket** (`ws_tickets.py` mới): `POST /ws/tickets` đổi bearer
  token lấy ticket **dùng một lần, TTL 60 giây**, connect bằng
  `?ticket=`. Không dùng `?token=<jwt>` — JWT sống một giờ và sẽ nằm
  trong mọi access log dọc đường.
- **Ownership**: `owner_user_id` ghi lúc tạo map/scenario; sửa/archive
  của người khác ⇒ 403. Row `owner=NULL` = **chia sẻ** (legacy, hoặc map
  `adopt` trả về từ thư viện), ai có `resource.write` cũng sửa được —
  nếu không sẽ kẹt luôn những row đó.
- **Archive thay delete**: `DELETE /maps/{id}` và `/scenarios/{id}` giờ
  set `archived_at`; row còn nguyên nên run cũ vẫn nói được nó chạy trên
  cái gì. `list()` lọc archived. `delete()` cứng vẫn còn cho orphan sweep.
- **Fixture test đổi mặc định**: `client` giờ **đã đăng nhập** (alice),
  thêm fixture `anonymous` cho test về chuyện chưa đăng nhập. Lý do:
  306 lời gọi GET trong suite, chỉ 128 có header — sửa 178 chỗ là churn
  cơ học; đổi mặc định rồi sửa ~30 chỗ *thật sự nói về ẩn danh* thì mỗi
  sửa đổi đều có nghĩa. Seed user trong conftest giờ mang
  `engineer+reviewer`, profile test = `desktop-single-user`.

### 4.2. Điểm dừng chính xác — một dòng cần sửa đầu tiên khi resume

5 test WebSocket đang đỏ vì **route ticket bị đặt sai chỗ**:

```
apps/api/planbench_api/main.py:269
    app.include_router(ws.router)  # websockets are not under /api/v1
```

Router `ws` **không** mang prefix `/api/v1`, nên `POST /ws/tickets` nằm ở
`/ws/tickets`, trong khi `tests/api/conftest.py::ws_url` gọi
`/api/v1/ws/tickets` → 404.

Chọn một trong hai (chưa quyết, cần An hoặc tự chốt khi resume):

1. Sửa `ws_url` trong conftest gọi `/ws/tickets` — giữ nguyên chỗ mount.
2. Tách endpoint ticket sang một router **có** prefix (nó là HTTP thường,
   không phải websocket), để nó nằm cùng chỗ với mọi API khác. *Nghiêng
   phương án này*: ticket là request HTTP có auth như mọi request khác,
   nó ở ngoài `/api/v1` chỉ vì tình cờ ở chung file với socket.

Sau khi sửa, chạy lại:
`python -m pytest tests/api/test_api_maps.py tests/api/test_api_scenarios.py tests/api/test_api_simulations.py -q`
(hiện **38 pass / 5 fail**, cả 5 đều là WebSocket).

### 4.3. P2 còn thiếu gì

- **`resource.read` chưa áp lên `decisions.py`** — đây là phần lớn nhất
  còn lại của P2: trace, `report.md`, `report.xlsx`,
  `approved_config.yaml`, `/audit`, `/explanation`, `/exemplars`,
  `/replay-sync`, `/critique`, danh sách candidate và task-profile. Tất
  cả vẫn public. Cũng còn `episodes.py`, `library.py`, `models.py` GET.
- **`task_profiles` ownership + `is_reference`**: cột đã có trong 0012
  và trong model, **chưa** nối vào service/router; server chưa từ chối
  sửa deployment `is_reference`.
- ~30 chỗ test khẳng định 401 bằng `client` (giờ đã đăng nhập) chưa đổi
  sang `anonymous` — sẽ đỏ khi áp `resource.read` lên các route đó. Danh
  sách: `test_api_advice.py` (6), `test_api_auth.py` (7),
  `test_api_agent.py` (2), `test_api_decisions.py` (2), và mỗi file 1–2
  chỗ ở `generalization`, `m5`, `models`, `paper`, `plugin`,
  `plugin_import`, `profile_validation`, `recommendation`,
  `report_export`, `settings`, `tuning`, `users`, `test_bench`.
- Test cho ticket (hết hạn → 401, dùng lại lần hai → từ chối) chưa viết.

---

## 5. Việc chưa bắt đầu

P3 (plugin governance + `plugin_publications`) · P4 (pin identity
candidate) · P5 (cancel tại episode boundary) · P6 (review workflow
claim/ack) · P7 (reliance derive) · P8 (admin routes) · P9–P11 (web) ·
P12 (desktop, `.env` ba tài khoản, smoke gate ca upgrade).

Nhắc lại ràng buộc P12 vì nó chi phối cả P3–P7: **bản desktop đã phát
hành đang được ban giám khảo chấm bằng `admin:admin`**, nên khi tới P12
phải có ca smoke "DB + `.env` của 0.1.14 → boot bản mới → login
`admin:admin` → đủ capability". Cơ chế đỡ việc này đã nằm sẵn trong P1
(launcher `setdefault` profile + reconcile ở API startup), nhưng phần
launcher desktop **chưa viết** — hiện mới có phía API.

---

## 6. Việc đã khảo sát được, ghi để khỏi dò lại

- `_retire_previous()` (`plugin_service.py:264`) tự disable revision cũ
  ngay khi revision mới validate xong. P3 phải giữ nó dưới cờ off và xoá
  đúng lúc flip — đã ghi trong plan §2.2.
- `StoredDecisionRun` chỉ được tạo **sau khi job chạy xong**
  (`decision_service.py:486`), nên P4 không có parent row lúc enqueue —
  pin vào `Job.pinned`, persist cùng transaction với run.
- `decision_service` **không có** hook cancel hợp tác nào (`grep
  cancel|should_stop` rỗng); `BenchmarkCancelled` chỉ tồn tại ở luồng
  benchmark cũ (`services.py:477`). P5 là việc mới thật, không phải một
  dòng.
- `review_requests.benchmark_id` là `NOT NULL FK` tới `benchmarks`
  (migration 0002:72) ⇒ P6 phải recreate bảng bằng `batch_alter_table`.
- 17 thư mục run trong `artifacts/runs` có `manifest_checksum` — đủ để
  script backfill của P4 match bundle.
- `get_settings()` là `lru_cache` (`config.py:194`): mọi test đổi env
  phải `cache_clear()` trước và sau.

---

## 7. Lệnh để tiếp tục

```powershell
git switch tongduyan_roles-capabilities     # đang ở đây, không cần
git status --short                          # P2 đang dở, chưa commit
python -m pytest tests/test_roles.py -q                       # 38 pass
python -m pytest tests/api/test_api_maps.py tests/api/test_api_scenarios.py tests/api/test_api_simulations.py -q   # 38 pass / 5 fail (WS)
```

Không có gì đang chạy nền. Không push remote nào. `.ai-log/` chưa
commit — theo luật §3 phải commit mỗi phiên, nhưng phải **quét secret
bằng regex** trước; để lại cho lượt sau vì đang giữa chừng P2.
