# Thiết kế role: engineer · reviewer · admin · demo_owner — 2026-08-27 (bản cuối)

**Trạng thái: An đã duyệt mô hình sau bảy vòng phản biện trong phiên
2026-08-27. Sẵn sàng thi hành từ P0.** Khảo sát nền ở
`notes/2026-08-27/tongduyan_khao-sat-hien-trang-role.md`. Mục 12 là sổ
quyết định (D1–D39) kèm lý do một dòng — mở lại quyết định nào thì đọc
lý do trước.

Ràng buộc cứng xuyên suốt: **bản desktop đã phát hành đang được ban giám
khảo chấm với `admin:admin`; sau update, tài khoản đó phải dùng được toàn
bộ app ngay trên máy đã cài, không sửa gì.**

---

## 0. Ba tầng trả lời ba câu hỏi

| Tầng | Câu hỏi | Cơ chế |
|---|---|---|
| Role → capability | được làm **loại hành động** nào | `user_roles(user_id, role)`; mỗi role là một gói capability cố định trong code |
| Ownership | được làm trên **bản ghi** nào | `owner_user_id / created_by` |
| Separation of duties | có được duyệt **thứ mình tạo** không | `created_by` / `uploaded_by` check; nới bằng setting tường minh (mục 5) |

```
allowed = has_capability(user, "resource.write") and owns(user, resource)
```

Ba gói nghiệp vụ **độc lập, không lồng nhau**. Một người mang nhiều
role; dev cần kiểm thuật toán mang `admin + reviewer`, publish vẫn ghi
audit là hành động reviewer. Server quyết, UI chỉ ẩn; mọi 403 nói người
dùng làm gì tiếp.

---

## 1. Ma trận capability

`✅` trong gói · `🔒` + ownership · `🟡` điều kiện ở ghi chú · `❌` không · `⚡` break-glass (mục 7).

| Capability | engineer | reviewer | admin | Ghi chú |
|---|---|---|---|---|
| `resource.read` — mọi GET/download: deployment, map, scenario, candidate, run, trace, report, `approved_config.yaml` | ✅ | ✅ | ✅ | **đăng nhập bắt buộc** cho mọi GET (hiện public) |
| `resource.write` — tạo/sửa/**archive** map, scenario, deployment | 🔒 | ❌ | ⚡ | reference deployment từ chối sửa/archive |
| `simulation.run` — test bench `/simulate` | ✅ | ✅ | ❌ | không sinh evidence duyệt được |
| `run.create` — decision run `purpose=production` | ✅ | ❌ | ❌ | 409 lúc tạo nếu candidate không resolve tới publication current |
| `run.cancel` | 🔒 | ❌ | ⚡ | job có `created_by` |
| `run.submit` | 🔒 | ❌ | ❌ | reviewer tuỳ chọn; không nêu ⇒ pool |
| `run.review` — claim / takeover / release / acknowledge / approve / reject | ❌ | 🟡 | ❌ | không phải run mình tạo (strict); comment bắt buộc |
| `run.withdraw` | ❌ | ✅ | ⚡ | bất kỳ reviewer, comment bắt buộc |
| `algorithm.catalogue` — built-in + publication current; tên + trạng thái bundle khác; nửa manifest | ✅ | ✅ | ✅ | mục 4.4 |
| `algorithm.inspect` — manifest đầy đủ, entry point, checksum, conformance log, revision, events | ❌ | ✅ | ❌ | |
| `algorithm.import` / `algorithm.validate` | ❌ | ✅ | ❌ | |
| `algorithm.validation_run` — decision run `purpose=validation`, candidate nêu `bundle_id` tường minh | ❌ | ✅ | ❌ | mục 3.3 |
| `algorithm.publish` / `unpublish` / `hold` / `release_hold` | ❌ | 🟡 | ❌ | không publish revision mình upload (strict) |
| `algorithm.disable` — governance, terminal | ❌ | ✅ | ❌ | `authorized_capability=algorithm.disable` |
| `system.kill_switch` — cùng hiệu ứng disable, lý do sự cố | ❌ | ❌ | ✅ | route riêng |
| `model.upload` / `model.validate` — PPO | ❌ | ✅ | ❌ | governance PPO **ngoài phạm vi** (mục 13) |
| `user.manage` | ❌ | ❌ | ✅ | không xoá cứng; invariant 4.6 |
| `system.configure` | ❌ | ❌ | ✅ | |
| `system.operate` | ❌ | ❌ | ✅ | huỷ job người khác = ⚡ |
| `audit.read` | ❌ | 🟡 projection run + algorithm | ✅ | một route, server cắt theo capability |
| Agent dock / `/agent` | ✅ | ✅ | ✅ | |

### 1.1 `demo_owner` — ngoại lệ theo deployment profile, không phải role nghiệp vụ

Role thứ tư, **chỉ tồn tại dưới `PLANBENCH_DEPLOYMENT_PROFILE=demo`**
(máy trình bày của An), đúng một người mỗi database, mang **toàn bộ**
capability trên — liệt kê tường minh, không wildcard:

```python
ALL_CAPABILITIES = frozenset({...22 capability của mục 1...})
CAPABILITIES[Role.DEMO_OWNER] = ALL_CAPABILITIES
# test pin: union(CAPABILITIES[engineer|reviewer|admin]) == ALL_CAPABILITIES
#           CAPABILITIES[demo_owner] == ALL_CAPABILITIES
# ⇒ thêm capability mới mà quên xếp vào gói nào thì test đỏ
```

*Vì sao có nó dù ba role gộp đã đủ:* một badge khi trình bày, một tài
khoản provision tự động, không phải giải thích vì sao một người mang ba
role, và có quy trình gỡ rõ trước production.

**Toàn quyền nhưng không phá invariant** — đi qua đúng state machine:
Submit → Claim → Acknowledge → Approve (self-approve vì demo chạy
`relaxed`); validation run vẫn không approve; bundle disabled vẫn không
dùng cho run mới; audit append-only; không hard-delete evidence;
break-glass vẫn đòi `reason`. Audit: `actor_roles=["demo_owner"]`,
`authorized_capability="run.review"`, `action="self_approve_config"`.

**Đúng một người:** partial unique index `uq_single_demo_owner ON
user_roles(role) WHERE role='demo_owner'` + service 409. **Không gán được
từ `/admin/users`** (nếu admin gán được thì admin nào cũng tự thành
superuser); chỉ role policy dưới profile demo gán, bind theo verified
email (`PLANBENCH_DEMO_OWNER_EMAIL`, tái dùng cơ chế
`PLANBENCH_ADMIN_EMAILS`) hoặc nickname cho local account
(`PLANBENCH_DEMO_OWNER_NICKNAME`); gán lên **user_id** bất biến. Env trỏ
sang người khác khi đã có demo_owner ⇒ **startup từ chối**.

**Production guard, fail-closed:** profile `production` — startup từ chối
nếu còn user active mang `demo_owner`, từ chối
`separation_of_duties=relaxed`, từ chối mọi `PLANBENCH_DEMO_OWNER_*`; API
gán role từ chối `demo_owner` ở mọi profile; smoke production xác nhận
không có demo_owner.

**Gỡ sau demo** (runbook `docs/DEMO-PROFILE.md`): backup DB + export
audit → gán role production thật (server cưỡng chế qua 4.6) → xoá row
`user_roles(…, demo_owner)` → profile `production`, SoD `strict`, xoá
`PLANBENCH_DEMO_OWNER_*` → readiness check. **Không xoá** audit row có
`actor_roles=["demo_owner"]`; literal giữ trong parser vĩnh viễn — cùng
lý do `approval.Role` giữ `OPERATOR/APPROVER`.

---

## 2. Dữ liệu — mỗi sự thật một chỗ, bốn migration đi cùng phase đầu dùng nó

### 2.1 `0012_roles_and_ownership` (P1)

```
user_roles (user_id, role, granted_by_user_id, reason, granted_at)   PK (user_id, role)
  role ∈ {engineer, reviewer, admin, demo_owner}
  UNIQUE INDEX uq_single_demo_owner ON user_roles(role) WHERE role = 'demo_owner'
  backfill: mọi user → engineer; is_admin=true → + admin
  (server KHÔNG tự + reviewer, KHÔNG tự + demo_owner; role theo profile do reconcile 4.1 lo)
users.disabled_at, users.last_sign_in_at
users.is_admin  giữ một bản (đọc = 'admin' ∈ roles), bỏ ở migration sau
account_events (append-only): sequence, user_id, actor_user_id, actor_roles,
  authorized_capability, action ∈ {created, role_granted, role_revoked, disabled,
  enabled, password_reset, signed_in}, previous, new, reason, override, created_at

maps.owner_user_id NULL, maps.archived_at            (MapRow hiện không có owner)
scenarios.owner_user_id NULL, scenarios.archived_at
task_profiles.archived_at, task_profiles.is_reference BOOL DEFAULT false
  owner_user_id NULL = legacy/shared, KHÔNG có nghĩa reference
```

### 2.2 `0013_plugin_governance` (P3)

```
plugin_bundles.status → operational_status ∈ {active, held, disabled}
  held     = reviewer rút tạm, có release_hold
  disabled = TERMINAL, không có enable; muốn dùng lại → upload revision mới
plugin_bundles.validation_status giữ {pending, structural, loaded, failed}
plugin_bundles.disabled_at, disabled_by_user_id, disabled_reason

plugin_publications (append-only lịch sử):
  id, plugin_id, bundle_id FK plugin_bundles.id, revision,
  published_by_user_id, published_at,
  superseded_at NULL,                 -- set khi revision KHÁC được publish
  unpublished_at NULL, unpublished_by_user_id NULL, reason
  UNIQUE (plugin_id) WHERE superseded_at IS NULL AND unpublished_at IS NULL   -- "current"

plugin_events (append-only): bundle_id, revision, actor_user_id, actor_roles,
  authorized_capability, action ∈ {imported, validated, validation_failed, published,
  superseded, unpublished, held, hold_released, disabled, metadata_changed},
  reason, created_at
```

*Vì sao publication là lịch sử chứ không phải con trỏ upsert theo
`plugin_id`:* reliance (mục 8) cần phân biệt **unpublish** (suspended)
với **supersede** (vẫn active); con trỏ ghi đè xoá mất dấu vết. *Vì sao
không có cột `lifecycle`, không có state `quarantined`:* "vừa import chưa
duyệt" suy được từ ba trục; thêm state là hai cách ghi một sự thật;
`QuarantinedPlugin` trong discovery (H5) đã nghĩa "manifest không parse
được".

Projection UI (không lưu): `disabled → "Đã tắt"; held → "Đang giữ";
validation=failed → "Hỏng"; là current publication → "Đã publish";
loaded ∧ không current → "Chờ publish" ("Revision mới" nếu plugin đang
có current khác; "Legacy · chờ publish" nếu chưa từng có publication);
pending/structural → "Chờ kiểm"`.

**Bất biến:** bundle đã xuất hiện trong bất kỳ run nào không bao giờ
hard-delete (hôm nay không có route DELETE; ghi thành luật).

**Cutover cho plugin hiện hữu — không grandfather.** DB đang có bundle
`active + loaded` đang được dùng, sẽ không có row nào trong
`plugin_publications` sau 0013.

| Giai đoạn | Catalogue / runtime | `_retire_previous()` (`plugin_service.py:264`) | Governance routes |
|---|---|---|---|
| Flag **off** (P3 → trước P7 flip) | resolver **cũ** (`active + loaded`) | **giữ**, chỉ chạy dưới flag off | 404 |
| Flag **on** (P7) | resolver **mới**: chỉ current publication; **không fallback** | xoá | mở |

- Bundle cũ giữ nguyên dữ liệu. Reviewer **publish tường minh** từng
  revision muốn giữ; hệ thống không tự tạo publication mang chữ ký
  reviewer.
- Import/revalidate **không bị chặn** khi flag off — chặn là regression
  trong cửa sổ P3–P7; hai resolver là nợ tạm chết ở P7.
- **Preflight bật flag** (admin): liệt kê mọi external stack đang được
  candidate đã đăng ký hoặc queued job tham chiếu; từ chối bật nếu có
  stack không resolve tới **đúng một** current publication.
- Desktop nâng cấp: màn hình đầu sau upgrade hiện bước **"Review
  imported algorithms"** — danh sách bundle legacy, nút Publish từng cái
  (reviewer / admin:admin mang reviewer), không publish ngầm.
- Nếu về sau buộc grandfather tự động (không khuyến nghị): event
  `legacy_publication_migrated`, `authorized_capability=migration`, UI
  không ghi "published by reviewer".

### 2.3 `0014_decision_candidate_identity` (P4)

```
decision_run_candidates (
  run_id FK decision_runs.id ON DELETE CASCADE, slot,
  stack, local_config,
  bundle_id NULL, plugin_id NULL, revision NULL, archive_checksum NULL,
  provider_fingerprint, runtime_profile,
  PRIMARY KEY (run_id, slot)
)
decision_runs.purpose ∈ {production, validation}  DEFAULT production
```

Persist **cùng transaction** với `decision_runs` khi run xong (4.2).
Không có run shell lúc enqueue — queue in-memory, ngoài phạm vi.

**Run trước 0014 không có identity.** Migration chỉ tạo bảng, **không
đọc đĩa**. Backfill bằng `scripts/backfill_run_candidates.py`: đọc
`manifest.json` từng run, lấy `manifest_checksum` trong candidate
identity (H9B, `candidate.py:217` — checksum của `plugin.json`, không
phải archive checksum), match bằng cách hash `plugin.json` trong archive
đã lưu của từng bundle cùng `plugin_id`; in báo cáo. Trên máy này 17
thư mục run có `manifest_checksum`. Không match → `bundle_id NULL` →
reliance `unknown` (mục 8), không đoán.

### 2.4 `0015_decision_review_workflow` (P6)

```
review_requests — recreate bằng batch_alter_table (SQLite):
  subject_kind ∈ {benchmark, decision_run}  DEFAULT benchmark   (backfill benchmark)
  subject_id   (đổi từ benchmark_id; không còn FK trực tiếp; integrity decision_run
                enforce trong service transaction; property benchmark_id chỉ hợp lệ
                khi subject_kind=benchmark)
  requested_reviewer_user_id NULL    -- engineer chọn; lịch sử, KHÔNG bao giờ xoá
  available_to_pool BOOL NOT NULL DEFAULT false   -- "hiện tại pool có được lấy không?"
  claimed_by_user_id NULL, claimed_at NULL
  status ∈ {open, claimed, acknowledged, approved, rejected, cancelled}
    acknowledged = terminal CHỈ cho run không card
    run có card: claimed —ack event—> vẫn claimed —decide—> approved | rejected
  INDEX (subject_kind, subject_id, status)
  backfill legacy: reviewer_user_id → requested_reviewer_user_id, available_to_pool=false

subject_kind=benchmark: GIỮ luật cũ (review_service.py:131) — chỉ requested_reviewer
  trả lời, không claim/takeover; service rẽ nhánh theo subject_kind.
subject_kind=decision_run: workflow 3.2.

decision_runs.current_review_request_id NULL
  (review_state / config_state giữ; submission và claimant KHÔNG lưu trên run — derive)
decision_run_reviews.action += {acknowledge, claim, takeover, release, submit,
  cancel_submit, self_approve_config, self_reject_config, algorithm_disabled_after_approval}
  giữ giá trị cũ `review` để row lịch sử parse được; event mới ghi `acknowledge`
  + cột review_request_id, actor_roles, authorized_capability, override
  (reviewed_by / reviewed_at trên run = lần đầu; mọi acknowledge là event, không overwrite)
```

### 2.5 Job (in-memory, `worker.py:29`)

Thêm `created_by`, `run_id`, `purpose`, `pinned` (identity 2.3),
`failure_reason`. Restart mất queue — giới hạn có sẵn.

### 2.6 Reference deployment

Seed 1–2 `task_profile` `is_reference=true`, `owner_user_id NULL`
(`Reference — corridor`, `Reference — warehouse`). Server từ chối
sửa/archive khi `is_reference`.

---

## 3. Lifecycle

### 3.1 Run — hai trục, assignment derive từ request

```
submission (derive từ current_review_request):
  none ──submit──> open ──claim──> claimed ──decide / ack(no-card)──> closed
   ▲               │  ▲              │
   │               │  └──release─────┘ (về pool; requested_reviewer giữ nguyên)
   │               └──cancel_submit (owner) → cancelled
   └── withdraw: current_review_request_id = NULL (request approved GIỮ NGUYÊN)

config_state:  not_applicable (không card) | pending ──approve──> approved ──withdraw──> pending
                                           |         └──reject──> rejected
review_state:  unreviewed ──acknowledge (lần đầu)──> reviewed
```

*Vì sao hai trục:* 4/5 phép so đầu tiên không ra card; run không card
vẫn phải được acknowledge (bằng chứng loại trừ), không có gì để approve
(`decisions.py:43-54` đã tách đúng). *Vì sao withdraw không đổi request:*
request là kết quả review lịch sử; withdrawal là sự kiện sau, nằm ở
audit. *Vì sao withdraw → `none`:* owner tự chọn chạy mới hay gửi lại;
`closed + pending` là state không lối ra.

### 3.2 Claim → Acknowledge → Approve/Reject

Concurrency lạc quan, mọi update `WHERE claimed_by_user_id IS expected`:

```
submit(reviewer=NULL)  → available_to_pool=true
submit(reviewer=A)     → requested_reviewer=A, available_to_pool=false
claim(request_id)      # được phép khi available_to_pool  HOẶC  requested_reviewer == self
                       # atomic WHERE claimed_by_user_id IS NULL
takeover(request_id, expected_claimed_by: A | NULL, reason)
                       # mọi trường hợp claim không được phép: directed chưa claim của người khác
                       # (expected=NULL) hoặc đang claim bởi A (expected=A)
                       # atomic WHERE claimed_by_user_id IS expected; reason bắt buộc;
                       # audit + thông báo A và engineer; requested_reviewer KHÔNG đổi
release(request_id, expected=self, reason?)
                       → claimed_by=NULL, available_to_pool=true  (A vẫn claim lại được)
mất run.review (A)     → mọi claim của A release; directed chưa claim tới A: available_to_pool=true
acknowledge(run_id)   → event {actor=claimant, review_request_id=current}
                        no-card: request → acknowledged (terminal)
decide_config(run_id, approve|reject, comment):
  require request.status == claimed  and  claimed_by == actor
  require ∃ acknowledge event: actor_user_id == claimed_by
          and review_request_id == current  and  acknowledged_at >= claimed_at
  require comment non-empty
  require purpose == production and card exists
  require actor != created_by  (strict; mục 5)
```

*Vì sao cần `available_to_pool` riêng:* A claim rồi release mà luật
"directed chỉ A" đọc `requested_reviewer=A` ⇒ B không claim được; A chưa
claim rồi nghỉ ⇒ `takeover(expected=A)` không khớp `claimed_by=NULL`.
Một cột "pool lấy được không", một cột "engineer đã yêu cầu ai". *Vì
sao một `takeover`:* hai endpoint cùng invariant, khác đúng một chỗ.
*Vì sao ack theo claimant:* A ack rồi release, B claim rồi ký dựa trên
ack của A — B chưa đọc. Khoảng Ack → Approve là bằng chứng trình tự và
dwell time.

### 3.3 Validation run = cùng đường, khác cờ

`POST /decisions` với `purpose: validation`. Không code path riêng —
loại run thứ hai đi vòng `nav_stack.py::run_stack()` (CLAUDE.md §8).

- chỉ `algorithm.validation_run`; candidate spec nêu **`bundle_id`
  tường minh** (alias `astar+<plugin_id>` chỉ resolve tới current);
- không submit/approve; `config_state` khoá `not_applicable`; trace
  `evidence_class` tương ứng (H9A); nhãn "validation run — không dùng để
  kết luận";
- comparator prefill baseline built-in theo `role` (global → `astar`,
  local → `dwa`), reviewer đổi được;
- **không phải publish gate**; gate = structural + conformance suite
  (H8). *Vì sao:* để kết quả benchmark quyết code vào catalogue là để
  reviewer chọn deployment cho plugin qua — §8 cấm.

### 3.4 Algorithm

Publish (transaction): đòi `active ∧ loaded` (không nhận `structural`);
insert publication row; set `superseded_at` trên current cũ; event
`published` + `superseded`. Unpublish: set `unpublished_at` trên current.
Republish cùng revision: row mới. Engineer catalogue/runtime resolve
current. Disable terminal. Tác động lên run và approval: mục 8.

---

## 4. Backend

### 4.1 `accounts.py` / `auth.py` — role, capability, profile, reconcile

```python
class Role(StrEnum): ENGINEER, REVIEWER, ADMIN, DEMO_OWNER
CAPABILITIES = {
    Role.ENGINEER: {"resource.read", "resource.write", "simulation.run", "run.create",
                    "run.cancel", "run.submit", "algorithm.catalogue"},
    Role.REVIEWER: {"resource.read", "simulation.run", "run.review", "run.withdraw",
                    "algorithm.catalogue", "algorithm.inspect", "algorithm.import",
                    "algorithm.validate", "algorithm.validation_run", "algorithm.publish",
                    "algorithm.disable", "model.upload", "model.validate", "audit.read"},
    Role.ADMIN:    {"resource.read", "algorithm.catalogue", "system.kill_switch",
                    "user.manage", "system.configure", "system.operate", "audit.read"},
    Role.DEMO_OWNER: ALL_CAPABILITIES,        # mục 1.1; test pin union == ALL
}
def require_capability(name): ...   # một dependency; Forbidden nêu role cần + ai đang giữ
```

`GET /auth/me` trả `roles` + `capabilities`; UI không tự map.
`decode_token` từ chối `disabled_at`. `approval.Role` cũ giữ cho audit.

**Deployment profile** `PLANBENCH_DEPLOYMENT_PROFILE ∈ {production,
desktop-single-user, demo}`, **mặc định `production` khi vắng** — server
đang chạy không có biến này và phải rơi vào nhánh chặt nhất. Launcher
desktop tự đặt profile trong process (mục 10) nên desktop không phụ
thuộc `.env`.

**Role policy** (`apply_role_policy`, thay `apply_admin_policy`):
- `PLANBENCH_ADMIN_NICKNAMES/EMAILS` gán `admin` lúc tạo account (như nay).
- `PLANBENCH_DEMO_OWNER_EMAIL/NICKNAME` gán `demo_owner` **chỉ dưới demo**.
- `PLANBENCH_DEFAULT_ROLES` chỉ nhận `engineer` hoặc rỗng; **từ chối**
  `reviewer`/`admin`/`demo_owner`.
- Env không gỡ role đã gán qua UI.

**Seed account có role — `PLANBENCH_SEED_USERS=name:roles:password`.**
`_parse_seed_entry` đang nhận dạng ba phần rồi **bỏ** field giữa; khôi
phục nghĩa: `roles` = danh sách nối `+` (`engineer+reviewer+admin`),
dạng hai phần `name:password` vẫn hợp lệ (= không ép role). **Reconcile
mỗi boot** cạnh `_ensure_password_user` (nơi đang reconcile password
mỗi boot): dưới `desktop-single-user` và `demo`, role của seed user được
đưa về đúng danh sách khai — thêm thiếu, **không** gỡ role admin gán
thêm qua UI; dưới `production`, field roles **bị bỏ qua kèm warning**
(role production luôn gán tay). `demo_owner` không được nêu trong seed;
đi qua `PLANBENCH_DEMO_OWNER_*`.

### 4.2 Pin identity lúc request, recheck lúc start, persist cùng run

Hiện `submit()` giữ `candidate_specs` là chuỗi, resolve khi chạy
(`decision_service.py:452`); `StoredDecisionRun` chỉ tạo khi job xong
(`:486`).

1. `POST /decisions` và `/decisions/jobs`: preflight **resolve và pin**
   identity 2.3 — sync path giữ trong request, async vào `Job.pinned`.
   Production: mọi candidate plugin phải resolve tới publication current,
   không thì 409 nêu tên.
2. Job start: production recheck từng bundle `là current ∧ active`;
   deployment `provider_fingerprint` == pinned. Lệch ⇒ job **fail có tên
   lý do** vào `Job.failure_reason`, không resolve lại. Validation chỉ
   recheck `≠ disabled`.
3. Run xong: insert `decision_runs` + `decision_run_candidates` **một
   transaction**. Fail/cancel: không tạo run.
4. `approved_config.yaml` và mọi tra cứu về sau resolve **theo
   `bundle_id` đã pin**.

UI nói rõ: sửa deployment khi run đang queue ⇒ job fail có lý do.

### 4.3 Route

| Route | Capability | Ghi chú |
|---|---|---|
| Mọi GET/download tài nguyên, kể cả `/traces/…`, `/report.*`, `/approved_config.yaml`, `/audit` của run | `resource.read` | hiện public — đóng hết |
| `POST/PUT` task-profiles, maps, scenarios; `DELETE` → archive | `resource.write` + owner | 409 khi `is_reference` |
| `simulations.py` tất cả | `simulation.run` | |
| `POST /ws/tickets` → `GET /ws/simulations/{id}?ticket=` | `simulation.run` | one-time, TTL 60 s; không `?token=` |
| `POST /decisions`, `/decisions/jobs` | `run.create` / `algorithm.validation_run` theo `purpose` | 4.2 |
| `DELETE /decisions/jobs/{id}` | `run.cancel` + owner | |
| `POST /decisions/{id}/submit`, `/submit/cancel` | `run.submit` + owner | body `reviewer?`, `comment` |
| `POST /reviews/{req}/claim`, `/takeover`, `/release` | `run.review` | 3.2 |
| `POST /decisions/{id}/review` (acknowledge) | `run.review` | claimant hiện tại |
| `POST /decisions/{id}/config-approval` | `run.review` | 3.2 |
| `POST /decisions/{id}/config-approval/withdraw` | `run.withdraw` | comment; request giữ; `current_review_request_id=NULL` |
| `GET /algorithms`, `/algorithms/plugins`, `/{id}` | `algorithm.catalogue` | field cắt theo `inspect` |
| `GET /algorithms/plugins/{id}/events`, `/conformance-log`, `/publications` | `algorithm.inspect` | |
| `POST /algorithms/plugins`, `/{id}/validate`, `PATCH` | `algorithm.import` / `validate` | `_require_admin` xoá |
| `POST …/{id}/publish`, `/unpublish`, `/hold`, `/release-hold` | `algorithm.publish` | `uploaded_by` check khi strict |
| `POST …/{id}/disable` | `algorithm.disable` | `reason`; terminal |
| `POST /admin/kill-switch/algorithms/{id}` | `system.kill_switch` | `reason`; cùng hiệu ứng |
| `POST /models/upload`, `/validate` | `model.upload` / `validate` | |
| `PUT /settings/agent`, `GET/PUT /admin/settings` | `system.configure` | 4.5 |
| `/admin/users*` | `user.manage` | 4.6; từ chối `demo_owner` |
| `GET /audit` | `audit.read` | reviewer projection run + algorithm |
| `/admin/ops/*`; `POST /admin/ops/jobs/{id}/cancel` | `system.operate` | cancel người khác = ⚡ |
| `GET /auth/providers` | — | thêm `suggested_accounts` khi profile desktop và dev-login bật (mục 9.1) |

Route publish/unpublish/hold/disable/kill-switch nằm sau cờ
`PLANBENCH_ALGORITHM_GOVERNANCE` (mục 11), 404 khi tắt.

### 4.4 Nửa manifest cho engineer

Thấy: `id, version, role, config_schema, supports, requirements,
compatibility verdict + provider thiếu, projection, current revision`.
Không thấy: `entry_point`, file listing, storage path, checksum chi
tiết, conformance log, revision history, publications, events. Cắt tại
`PluginBundleSummary.of(record, viewer, inspect: bool)` — một chỗ.
*Vì sao thấy `config_schema`:* engineer cần nó để đặt `local_config`.

### 4.5 Settings — một nguồn, hiệu lực từng cái

`get_settings()` là `lru_cache` (`config.py:194`). **Không** DB settings
store. `.env` = bootstrap; `app.state.runtime_settings` = authoritative;
mỗi lần ghi = ghi `.env` + cập nhật `app.state` + rebuild service liên
quan (pattern `settings.py` với provider).

| Setting | Hiệu lực |
|---|---|
| `separation_of_duties` | ngay |
| `default_roles` | sign-up kế tiếp |
| `analyst_mode`, `algorithm_governance` | ngay |
| API key / model | rebuild provider ngay (đã có) |
| `jwt_ttl_minutes` | token kế tiếp; token cũ không thu hồi — UI nói rõ |
| `auth_secret`, DB URL, OAuth client, seed users | nhãn **restart required** |

Giới hạn: multi-worker không đồng bộ; app một process.

### 4.6 Invariant "còn người quản trị" — đếm capability, không đếm tên role

Một transaction: từ chối revoke role hoặc `disable` tài khoản nếu sau
thao tác **không còn user active nào có `user.manage`**. *Vì sao không
đếm role `admin`:* với `demo_owner` đếm tên sai hai chiều; đếm capability
thì bước "gán role thật trước khi xoá demo_owner" được server cưỡng chế.

### 4.7 Hợp đồng

HĐ-14 viết lại theo bản này; `demo_owner` ghi là ngoại lệ theo
deployment profile. **MAJOR**; lát cắt dọc = chạy
`tests/test_vertical_slice.py`.

---

## 5. Separation of duties

| Luật | `strict` (production, mặc định) | `relaxed` (desktop-single-user, demo) |
|---|---|---|
| Decide run mình tạo | ❌ | ✅ nếu có `run.review`; `self_approve_config` / `self_reject_config`; card `approval: self` |
| Publish revision mình upload | ❌ | ✅; `self_published` |
| Approve validation run | ❌ | ❌ — không setting nào nới |
| Decide run không claim / chưa ack | ❌ | ❌ |

`PLANBENCH_SEPARATION_OF_DUTIES`, banner khi `relaxed`. Không đếm
headcount reviewer — headcount đổi khi disable một tài khoản là luật lật
im lặng. Withdraw: bất kỳ reviewer + comment.

---

## 6. Audit

Mọi event: `actor_user_id`, `actor_roles` (snapshot),
`authorized_capability` (endpoint quyết), `override`, `reason`.
`algorithm.disable` / `system.kill_switch` tách nên không nhập nhằng;
`resource.read` không sinh audit.

---

## 7. Break-glass = `reason` + `override=true`, không phải mode

Bốn hành động admin làm **thay** người khác: sửa/archive tài nguyên
người khác; huỷ run/job người khác; withdraw khi không còn reviewer
active; gỡ claim treo. Không impersonate. Admin cần publish ⇒ gán thêm
reviewer.

---

## 8. Sự kiện sau approval — lịch sử giữ, reliance derive

> Không sự kiện nào trên bundle sửa hoặc xoá approval. Chúng chỉ đổi
> khả năng **dựa vào** approval cho việc mới. Artifact vẫn tải được;
> `reliance_status` derive lúc đọc từ trạng thái bundle đã pin.

```
reliance(run) — với mỗi candidate, lấy mức xấu nhất:
  built-in                                                    → active
  external stack, bundle_id NULL (run trước 0014, chưa backfill) → unknown
  operational_status == disabled                              → revoked      (terminal)
  operational_status == held                                  → suspended
  ∃ plugin_publications(bundle_id) với unpublished_at IS NULL → active       (kể cả đã superseded)
  else (unpublished / legacy chưa publish)                    → suspended
thứ tự xấu → tốt: revoked > unknown > suspended > active
```

| Sự kiện sau approval | Reliance | Tự phục hồi? |
|---|---|---|
| Hold | suspended | release_hold cùng revision → active |
| Unpublish | suspended | republish cùng revision → active |
| Revision mới thay (supersede) | **active** | — |
| Disable / kill-switch | revoked | không; cần run + approval mới |
| Identity không pin được (run cũ) | unknown, warning `identity_not_pinned` | backfill match được → derive lại |

*Vì sao supersede vẫn active:* "có bản mới" không chứng minh bản cũ sai.
`unknown` xếp như suspended trên UI nhưng không nói dối là revoked.

Tác động của disable (reviewer) / kill-switch (admin), giống nhau:

| Đối tượng | Hành vi |
|---|---|
| Picker, run mới | biến mất / 409 nêu tên |
| Job queued pin revision đó | cancel, lý do vào `Job.failure_reason` |
| Job đang chạy | dừng **tại episode boundary** — hook cancel hợp tác trong `selection` loop (chưa có; `BenchmarkCancelled` chỉ ở luồng cũ `services.py:477`) — P5 |
| Evidence, trace, run | không xoá |
| Run `approved` pin revision đó | `config_state` **vẫn `approved`**; **không** tự withdraw (hệ thống không giả làm reviewer); append event `algorithm_disabled_after_approval` {bundle_id, revision, disabled_by, reason} |
| `approved_config.yaml` | HTTP 200; `reliance_status` + khối `warning` đầu file khi ≠ active; UI "Tải cấu hình lịch sử"; bỏ khỏi "đang áp dụng được" |

```yaml
artifact: approved_config
reliance_status: revoked            # active | suspended | revoked | unknown (derive)
warning:
  code: algorithm_disabled_after_approval   # hoặc algorithm_held / algorithm_unpublished / identity_not_pinned
  message: >
    Thuật toán của cấu hình này đã bị vô hiệu hoá sau khi cấu hình được
    phê duyệt. File được giữ để kiểm toán và tái lập bằng chứng; không
    dùng cho một mô phỏng mới.
  bundle_id: mppi
  revision: 3
  disabled_at: "…"
  disabled_by: user-123
  reason: "…"
candidate:
  candidate_id: …
  stack: astar+mppi
  bundle: {bundle_id: …, plugin_id: mppi, revision: 3, archive_checksum: …}   # từ decision_run_candidates
approval:
  status: approved                  # "con người đã quyết gì lúc đó"
  approved_by: reviewer-a
  approved_at: "…"
```

`approved_config` hiện chỉ xuất `stack, params_ref, manifest_ref,
run_checksum` (`decision_service.py:950`) — thêm `candidate.bundle`.

---

## 9. UI

### 9.1 Chung

`SessionUser.roles/.capabilities` từ `/auth/me`; `NavItem.capability`;
badge mọi role đang mang; nút thiếu capability = disabled + tooltip nêu
role và ai giữ; khu admin ẩn hẳn; banner `relaxed`; "validation run
(subprocess lane)", không "sandbox" (`plugin_import_security.md` §4);
i18n cả `en.json` và `vi.json`.

**Màn login desktop** (profile desktop, dev-login bật): ba gợi ý tài
khoản từ `/auth/providers.suggested_accounts` — `admin` (mọi vai),
`engineer`, `reviewer` — mỗi cái một dòng mô tả vai, bấm là điền sẵn.
Giám khảo đổi vai bằng sign out / sign in.

### 9.2 Engineer

Sidebar: Dashboard · Deployments · Maps & Scenarios · Simulate ·
Runs/Decisions · Algorithms (catalogue) · Review status · Agent.

- Dashboard: Đang chạy / Chờ duyệt / Đang duyệt (ai claim) / Bị trả lại
  / Đã duyệt / Cấu hình lịch sử (reliance ≠ active). Nút: Tạo mô phỏng,
  Test bench.
- Decision detail: status strip + "Gửi duyệt" (reviewer tuỳ chọn +
  comment); sau reject: "Chạy lại với cấu hình mới" (run mới, prefill);
  reliance ≠ active: banner + "Tải cấu hình lịch sử"; directed reviewer
  mất quyền: gợi gửi lại.
- Candidate picker: built-in + current publication; bundle khác mờ với
  chip projection ("Chờ reviewer", "Đang kiểm", "Đang giữ", "Đã tắt").
- `/algorithms`: bảng + drawer nửa manifest. Không Import.
- Review status: request đã gửi, ai claim, kết quả.

### 9.3 Reviewer

Sidebar: Dashboard · Review Queue · Algorithms · Models · Simulate ·
Runs (đọc) · Agent.

- Dashboard: *Runs chờ tôi* (pool + đích danh + đang claim), *Algorithms
  chờ* (Chờ kiểm · Chờ publish · Revision mới · Đang giữ).
- Review Queue `/reviews`: tab Runs (Open · Claimed · Approved ·
  Rejected · Acknowledged), tab Algorithms, tab Legacy (benchmark cũ).
- Decision detail: **Claim → Acknowledge → Approve/Reject** một panel;
  bước sau mờ tới khi bước trước xong và có comment; takeover đòi
  reason; run không card kết thúc ở Acknowledge; validation run: banner
  "không duyệt được"; run mình tạo (strict): panel nói rõ.
- Algorithm Detail: Manifest & capability · Checksum/fingerprint ·
  Conformance · Runtime compatibility · Validation runs (link) ·
  Publications (current/superseded/unpublished) · Revision history ·
  Audit timeline. Hành động: Revalidate · Run validation (prefill
  reference + baseline) · Publish (confirm revision + checksum) ·
  Unpublish · Hold / Release hold · Disable (reason, cảnh báo terminal).

### 9.4 Admin

Sidebar: Dashboard · Users & Access · Audit · System Settings ·
Operations · Runs (đọc) · Algorithms (catalogue) · Agent.

- Users & Access: bảng roles (chip nhiều); gán/gỡ role (reason),
  disable/enable, reset password (dev-login), tạo tài khoản dev-login;
  invariant 4.6 → 409; `demo_owner` read-only "managed by deployment
  profile".
- Audit: timeline gộp; lọc actor / loại / ngày / `override`; CSV.
- System Settings: bảng 4.5; SoD cảnh báo đỏ; `algorithm_governance`
  với preflight (2.2).
- Operations: health/version, job queue (huỷ = ⚡), artifact usage,
  retention, backup/restore, plugin host health, Kill-switch (reason).

### 9.5 Demo profile

Badge duy nhất **[Demo Owner]**; sidebar hiện toàn bộ. Banner cố định,
**không tắt được**: "DEMO MODE — Demo Owner có toàn bộ capability và
separation of duties đang ở relaxed. Không sử dụng cấu hình này cho
production."

---

## 10. Ba deployment profile

| Profile | Ai | Role | SoD | Banner | Guard startup |
|---|---|---|---|---|---|
| `production` (**mặc định khi vắng biến**) | server nhiều người | ba gói, gán tay; field roles trong seed bị bỏ qua | strict; từ chối relaxed | — | từ chối demo_owner, `PLANBENCH_DEMO_OWNER_*` |
| `desktop-single-user` (bản phát hành) | người cài app, ban giám khảo | seed ba tài khoản (dưới) | relaxed | "relaxed" | — |
| `demo` (An tự set trên máy trình bày) | một mình An | `demo_owner` | relaxed | DEMO MODE, không tắt | từ chối demo_owner thứ hai; env trỏ người khác ⇒ từ chối |

*Vì sao desktop shipped ≠ demo:* bản desktop đã phát hành, ban giám khảo
đang chấm với `admin:admin` — desktop **là** sản phẩm được chấm, không có
bước "chuyển sang production"; banner DEMO và runbook gỡ role không có
nghĩa ở đó.

### 10.1 Desktop — ba tài khoản, nâng cấp tại chỗ không mất quyền

Template `.env` desktop:

```
PLANBENCH_DEPLOYMENT_PROFILE=desktop-single-user
PLANBENCH_SEPARATION_OF_DUTIES=relaxed
PLANBENCH_ENABLE_DEV_LOGIN=true
PLANBENCH_SEED_USERS=admin:engineer+reviewer+admin:admin,engineer:engineer:engineer,reviewer:reviewer:reviewer
PLANBENCH_ADMIN_NICKNAMES=admin
```

| Tài khoản | Role | Giám khảo thấy |
|---|---|---|
| `admin` / `admin` | engineer + reviewer + admin | ba badge, mọi menu; tự chạy hết Submit → Claim → Ack → Approve (relaxed, audit `self_approve_config`) — **đúng như hôm nay, không mất gì** |
| `engineer` / `engineer` | engineer | workspace tạo evidence; nút Import mờ có tooltip; không có Approve |
| `reviewer` / `reviewer` | reviewer | Review Queue, Algorithm governance; không tạo được production run |

Luồng strict thật cũng chạy được trên desktop bằng hai tài khoản:
`engineer` submit → `reviewer` claim/ack/approve. Password trùng nickname
là chủ ý, cùng lý do `admin:admin` hiện nay (`provision.py` docstring):
API bind `127.0.0.1`, bảo vệ là máy của người dùng.

**Nâng cấp tại chỗ — ba chốt để `admin:admin` không mất quyền.** Máy
giám khảo có `.env` cũ **không có** profile và **không có** hai tài khoản
mới; `provision.py` chỉ sinh `.env` khi chưa có.

1. **Launcher desktop tự đặt profile trong process** —
   `os.environ.setdefault("PLANBENCH_DEPLOYMENT_PROFILE", "desktop-single-user")`
   trước khi `Settings` load. Launcher *biết* nó là desktop; `.env` có
   giá trị thì thắng (cách An bật `demo`). "Vắng = production" chỉ còn
   áp cho server.
2. **Reconcile ở API startup** cạnh `_seed_users` (nơi đang reconcile
   password mỗi boot): dưới profile desktop, seeded `admin` được đưa về
   `engineer + reviewer + admin` kể cả khi `.env` cũ chỉ có `admin:admin`
   (launcher cung cấp seed mặc định của profile khi `.env` thiếu); hai
   tài khoản `engineer`/`reviewer` được tạo nếu chưa có. Provision chạy
   trước khi có DB nên không làm ở đó.
3. **Smoke gate thêm ca upgrade**: DB + `.env` của 0.1.14 → boot bản mới
   → login `admin:admin` → `/auth/me` đủ capability → chạy hết workflow;
   login `engineer`/`reviewer` → capability đúng gói.

### 10.2 Demo trên máy An

Sửa `.env` của bản desktop đã cài: `PLANBENCH_DEPLOYMENT_PROFILE=demo`,
`PLANBENCH_DEMO_OWNER_NICKNAME=admin`, giữ dev-login và relaxed.
Reconcile mỗi boot: tài khoản `admin:admin` hiện có (không tạo mới, không
đổi password) có `demo_owner`, không có thứ hai; **không** gán thêm ba
role kia — badge và audit không có bốn role dư. Hướng dẫn bật/tắt và
runbook gỡ ở `docs/DEMO-PROFILE.md`.

---

## 11. Phase

Mỗi phase kết thúc bằng test phần vừa sửa; full suite chạy nền khi hết
plan (§6 CLAUDE.md). Test theo lối repo: đọc source, pin quyết định,
văn xuôi *vì sao*. Migration đi cùng phase đầu dùng nó, **không sửa
migration đã apply**.

**P3–P7 là một release unit**: schema và service vào sau cờ
`PLANBENCH_ALGORITHM_GOVERNANCE=off` (route governance 404), chỉ bật khi
P7 xong. *Vì sao:* P3 mở kill-switch mà P4 mới pin, P5 mới cancel job,
P7 mới xử lý approved config — cửa sổ không an toàn.

| Phase | Việc | Pin |
|---|---|---|
| P0 | HĐ-14 MAJOR + changelog; docstring `accounts.py`/`auth.py`/`approval.py`; `plugin_import_security.md` §5 | `test_vertical_slice.py` |
| P1 | **0012** (+ `demo_owner`, `uq_single_demo_owner`); `Role`, `CAPABILITIES`, `ALL_CAPABILITIES`, `require_capability`; `/auth/me`; `apply_role_policy` + demo binding; deployment profile + guard startup; seed `name:roles:password` + reconcile role mỗi boot theo profile; disabled; invariant `user.manage` transaction; `DEFAULT_ROLES` từ chối admin/reviewer/demo_owner | union ba gói == ALL; demo_owner == ALL; profile vắng = production; production từ chối demo_owner/relaxed, bỏ qua roles trong seed kèm warning; demo_owner thứ hai 409; env trỏ người khác ⇒ startup từ chối; gỡ role cuối có `user.manage` 409 dưới hai request song song; seed reconcile thêm thiếu không gỡ thừa |
| P2 | `resource.read` mọi GET; write routes; WS ticket; archive; `is_reference` từ chối sửa | 401 từng route; ticket hết hạn |
| P3 | **0013**; ba trục + `plugin_publications` + `plugin_events`; resolver mới + cũ theo cờ; `_retire_previous` chỉ dưới cờ off; projection "Legacy · chờ publish"; governance routes sau cờ | cờ off: catalogue **y hệt** hôm nay; cờ on: unpublish ≠ supersede |
| P4 | **0014** (chỉ tạo bảng); pin ở preflight/`Job.pinned`; recheck lúc start; persist cùng run; `purpose`; production 409; validation `bundle_id` tường minh; comparator; seed reference; `scripts/backfill_run_candidates.py` + báo cáo | job fail có tên khi unpublish giữa queue; run không match → `bundle_id NULL` |
| P5 | Cancel hợp tác tại episode boundary trong `selection` loop; `Job.created_by/run_id/pinned/failure_reason`; disable cancel queued + dừng running | dừng ≤ 1 episode sau disable |
| P6 | **0015**; `available_to_pool`; submit/claim/takeover/release atomic; ack theo claimant; `decide_config` 5 điều kiện; withdraw không đụng request; SoD setting + `self_*`; auto-release khi mất `run.review`; legacy benchmark giữ luật cũ | A ack → release → B claim OK; directed A chưa claim → B claim 403, takeover(expected=NULL) OK; benchmark pending trước migration vẫn chỉ người nêu tên approve |
| P7 | Reliance derive (+ `unknown`); event `algorithm_disabled_after_approval`; `approved_config` thêm `candidate.bundle` + warning; **preflight bật cờ** + xoá resolver cũ và `_retire_previous` khi flip; desktop bước "Review imported algorithms" | supersede → active; unpublish → suspended; disable → revoked; `bundle_id NULL` → unknown; preflight từ chối khi còn stack đang dùng chưa publish |
| P8 | Admin routes: users/roles, `/audit` projection, settings runtime, ops; break-glass `reason` + `override` | huỷ job người khác thiếu reason → 422 |
| P9 | Web: session roles/capabilities, nav, badge (kể cả [Demo Owner]), banner relaxed + DEMO MODE không tắt, login gợi ý ba tài khoản, `HumanActs` ba bước, `/algorithms` + detail + publications, picker, "Tải cấu hình lịch sử" | vitest `navigation`, `HumanActs`, `algorithms`, `login`; `tsc --noEmit`; banner demo không có nút đóng |
| P10 | Web: Review Queue, dashboard theo role, submit/takeover modal | vitest |
| P11 | Web: `/admin/*`, dời `/settings` và `/system`; `demo_owner` read-only trong Users | vitest |
| P12 | Desktop: launcher `setdefault` profile + seed mặc định của profile; template `.env` ba tài khoản; smoke gate cả ba profile **+ ca upgrade từ 0.1.14 với `.env` cũ**; bump VERSION; `docs/DEMO-PROFILE.md` | `smoke_stage.py`: `admin:admin` sau upgrade đủ capability; `engineer`/`reviewer` đúng gói |

Ước lượng: backend P0–P8 ~5 ngày; web P9–P11 ~3 ngày; P12 nửa ngày. Cắt
được P10/P11 sang plan sau mà ba role vẫn có nghĩa từ P9.

---

## 12. Sổ quyết định

| # | Quyết định | Lý do một dòng |
|---|---|---|
| D1 | Ba gói độc lập, multi-role, không bậc thang | admin không phải super-reviewer; publish luôn mang chữ ký reviewer |
| D2 | Validation run = cùng `POST /decisions`, cờ `purpose`, `bundle_id` tường minh | không fork `run_stack()`; alias chỉ resolve current |
| D3 | Reference deployment `is_reference=true` | `owner NULL` đang nghĩa legacy/shared |
| D4 | Withdraw: bất kỳ reviewer + comment; → `none`; request approved giữ nguyên | không kẹt; request là lịch sử, withdrawal là audit |
| D5 | Run hai trục; `submission` derive từ `review_requests` | run không card ack được; assignment một nguồn |
| D6 | SoD `strict/relaxed` bằng setting | không luật suy ngầm từ headcount |
| D7 | Engineer thấy nửa manifest | cần `config_schema` |
| D8 | Break-glass = `reason` + `override`, 4 hành động | override không thành thao tác thường |
| D9 | Submit: reviewer tuỳ chọn ⇒ pool; `requested_reviewer` ≠ `claimed_by`; atomic | hai sự thật hai cột; không đua |
| D10 | Không "sandbox" trên UI | subprocess lane không cô lập bảo mật |
| D11 | Test bench trong gói reviewer | không sinh evidence duyệt được |
| D12 | PPO upload thuộc reviewer; governance PPO ngoài phạm vi | `MonolithicPolicy` chưa xong |
| D13 | Plugin ba trục, `lifecycle` projection; `held` thay `quarantined` | một sự thật một chỗ; tên đã có nghĩa khác |
| D14 | Pin lúc request/`Job.pinned`, recheck lúc start, persist cùng run | TOCTOU; không có run shell lúc enqueue |
| D15 | Claim → Ack → Decide; ack theo claimant hiện tại | takeover không thừa hưởng ack; dwell time là bằng chứng |
| D16 | `.env` bootstrap + `app.state` runtime, không DB store | hai nguồn cho một setting |
| D17 | Validation run không phải publish gate | kết quả benchmark không quyết code vào catalogue (§8) |
| D18 | Tách `algorithm.disable` / `system.kill_switch` | endpoint không đoán role |
| D19 | Sự kiện sau approval: `approval.status` giữ, `reliance_status` derive, 200 + warning, không tự withdraw | lịch sử không biến mất; không nhầm approval cũ với cấu hình còn khuyến nghị |
| D20 | `resource.read` = đăng nhập mọi GET; WS ticket | trace/report/approved_config đang public |
| D21 | `DEFAULT_ROLES` chỉ `engineer` hoặc rỗng | reviewer/admin gán tay |
| D22 | `plugin_publications` là lịch sử với partial unique "current" | unpublish ≠ supersede, reliance phải derive được |
| D23 | Xoá `_retire_previous` khi flip cờ | lý do tồn tại đã thay bằng current publication |
| D24 | Reliance `active \| suspended \| revoked \| unknown`, derive; supersede → active | "có bản mới" không chứng minh bản cũ sai |
| D25 | Disable terminal, không có enable | `held`/`release_hold` lo tạm ngưng |
| D26 | Bốn migration 0012–0015 đi cùng phase; `review_requests` recreate + `subject_kind` | không sửa migration đã apply; SQLite |
| D27 | Reconcile role mỗi boot theo profile, cạnh reconcile password | máy đã cài nâng cấp được; server không tự thành reviewer |
| D28 | P3–P7 một release unit sau cờ `algorithm_governance` | kill-switch trước pin/cancel/reliance là cửa sổ không an toàn |
| D29 | Giữ action `review` cho row cũ, event mới `acknowledge` | audit cũ phải parse được |
| D30 | `available_to_pool` tách khỏi `requested_reviewer`; một `takeover(expected: A \| NULL)` | directed release / chưa claim đều không kẹt |
| D31 | `subject_kind=benchmark` giữ luật named-reviewer cũ | migration không đổi quyền request pending |
| D32 | Cutover không grandfather: hai resolver theo cờ, preflight bật cờ, reviewer publish tường minh | không tự tạo publication mang chữ ký reviewer; không chặn import |
| D33 | Run trước 0014: backfill script, không match → `unknown` | migration không đọc đĩa; không đoán identity |
| D34 | `demo_owner`: capability tường minh == union ba gói (test pin), một người/DB, không gán từ UI, chỉ dưới profile demo | badge và provision cho demo, không phá invariant |
| D35 | Ba profile; **vắng biến = production** cho server; launcher desktop tự đặt profile | desktop shipped là sản phẩm; fail-closed cho server đang chạy |
| D36 | Invariant quản trị đếm `user.manage` | demo_owner làm đếm tên sai hai chiều |
| D37 | Template desktop giữ `desktop-single-user`; `demo` chỉ trên máy An | giám khảo đang dùng `admin:admin`; demo_owner là công cụ trình bày |
| D38 | Launcher `setdefault` profile; reconcile ở API startup; smoke gate ca upgrade | `.env` cũ không có biến mới — không được làm `admin:admin` mất quyền lúc chấm |
| D39 | Desktop seed `admin` (ba role) + `engineer` + `reviewer`; `PLANBENCH_SEED_USERS=name:roles:password`; login gợi ý ba tài khoản | giám khảo thấy workspace bị giới hạn của từng vai; luồng strict chạy được trên một máy |

---

## 13. Ngoài phạm vi

- Governance lifecycle cho PPO model.
- Job queue bền qua restart / run shell lúc enqueue.
- Đồng bộ runtime settings giữa nhiều worker.
- Gỡ luồng benchmark cũ (`/reviews` tab Legacy, route deprecated).
- Sandbox bảo mật thật cho plugin (blocker deploy public, note 2026-08-24).
