# Thi hành plan role: P0–P8 + P12 xong, P9 dở — 2026-08-27

Báo cáo cập nhật lần 4. Bản đầu phủ P0–P2, bản hai tới P6, bản ba tới
P8; bản này thêm **P12 (desktop)** và **nửa đầu P9 (web)**. Tên file giữ
nguyên để link cũ không hỏng.

Plan: `plans/2026-08-27/thiet-ke-role-engineer-reviewer-admin.md` (13
phase). Khảo sát nền: `notes/2026-08-27/tongduyan_khao-sat-hien-trang-role.md`.

## 0. Trạng thái một bảng

| Phase | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| P0 | Hợp đồng HĐ-14 + docstring | xong | `9d05905` |
| P1 | Role, capability, profile, invariant | xong | `1174261` |
| P2 | Đóng auth, ownership, archive, WS ticket | xong | `8ccb20a` |
| P3 | Plugin governance + publication | xong | `b957d3f` |
| P4 | Pin định danh candidate | xong | `8ec02f1` |
| P5 | Dừng hợp tác tại episode boundary | xong | `e977df8` |
| P6 | Luồng duyệt claim/ack/decide | xong | `56d1f2d` |
| P7 | Reliance dẫn xuất + cảnh báo trên config | xong | `74456a9` |
| P8 | Admin: users/roles, audit, break-glass | xong | `a2c4e51` |
| **P12** | **Desktop: launcher, ba tài khoản, ca upgrade** | **xong (làm sớm)** | (commit) |
| P9 | Web: session/nav/badge/banner + duyệt ba bước | **một nửa** | 2 commit |
| P10–P11 | Web: Review Queue, dashboard, `/admin/*` | chưa bắt đầu | — |

Nhánh `tongduyan_roles-capabilities` từ `main`, **20 commit**, chưa push.

**P12 làm sớm, ra trước P9–P11.** Nó là thứ chặn phát hành, nhỏ, và
không phụ thuộc web — để sau thì nhánh này nằm ở trạng thái "không được
release" lâu hơn cần thiết.

**Nhánh mang hai luồng việc.** Ngoài commit role của tôi, An đã commit 5
bản ghi AI-analyst lên cùng nhánh (`3f7f0b4`, `7a4b10f`, `27a6035`,
`a644369`, `dfcbed4`) — toàn bộ `docs/antongduy/`, không đụng code. Muốn
mở PR riêng cho từng luồng thì phải tách trước.

Stash `stash@{0}` của An (gitignore + ai-log của `tongduyan_updater-cdn`)
vẫn treo.

---

## 1. Backend giờ làm được gì

Ba gói capability **không lồng nhau**, một người mang nhiều gói:

| | engineer | reviewer | admin |
|---|---|---|---|
| Tạo/chạy run, sửa map/scenario/deployment của mình | ✅ | ❌ | ❌ |
| Gửi run đi duyệt | ✅ | ❌ | ❌ |
| Claim / acknowledge / approve / withdraw | ❌ | ✅ | ❌ |
| Import / validate / publish / disable thuật toán | ❌ | ✅ | ❌ |
| Gán role, khoá tài khoản, đọc audit đầy đủ | ❌ | ❌ | ✅ |

Cộng `demo_owner` — ngoại lệ theo deployment profile, mang toàn bộ
capability, đúng một người mỗi database, **không gán được từ
`/admin/users`**, và profile `production` từ chối khởi động khi còn ai
mang nó.

---

## 2. Từng phase — cái gì đã đổi

### P0–P2 (đã mô tả ở bản báo cáo trước)

Hợp đồng HĐ-14 viết lại + bump 7.0.0 MAJOR; `user_roles` +
`require_capability` + deployment profile + invariant; đóng auth mọi
route ghi và mọi GET tài nguyên; WS ticket dùng một lần; ownership +
archive cho map/scenario.

### P3 — publish thành hành động (`b957d3f`)

`plugin_publications` là **lịch sử append-only**: publish revision mới
đóng dấu `superseded_at` lên dòng cũ, reviewer rút thì đóng dấu
`unpublished_at`. Hai cột vì hai sự thật — upsert theo `plugin_id` sẽ làm
cả hai thành cùng một sự vắng mặt. `held` là tạm ngưng, `disabled` là
**terminal**. Cờ `PLANBENCH_ALGORITHM_GOVERNANCE` mặc định **tắt**; route
governance trả 404 khi tắt.

### P4 — pin định danh (`8ec02f1`)

`run_identity.py`: theo con trỏ stack **một lần** lúc request, **recheck**
lúc job start. `decision_run_candidates` ghi cùng transaction với run.
Production chỉ pin cái đã publish; validation phải nêu `bundle_id`.
Script `backfill_run_candidates.py` cho run cũ.

### P5 — dừng tại ranh giới episode (`e977df8`)

`simulate(should_stop=)`. `SweepStopped` **raise**, không chấm phần dở —
ngược với `KeyboardInterrupt` có chủ ý. `Job` mang `created_by`,
`purpose`, `run_id`, `pinned`.

### P6 — duyệt là bốn bước (`56d1f2d`)

Migration `0015`: `subject_kind`/`subject_id`,
`requested_reviewer_user_id` tách khỏi `claimed_by_user_id`, cộng
`available_to_pool`.

Luật cốt lõi: **acknowledge thuộc về claim, không thuộc về run.** A đọc
rồi nhả, B nhận — nếu chỉ hỏi "có ai đọc chưa" thì B ký được mà chưa mở
gì, và trail nhìn vẫn đủ. Điều kiện: có sự kiện acknowledge với
`actor == claimed_by` và `acknowledged_at >= claimed_at`.

Route mới: `/submit`, `/submit/cancel`, `/claim`, `/takeover`,
`/release`, `/review-state`. `decide_config` có 5 điều kiện. Run không
card đóng ở `acknowledged`. Withdraw: **bất kỳ reviewer**, comment bắt
buộc. Claim tự nhả khi người giữ mất `run.review` — kiểm lúc đọc, vì
quên nhả xảy ra ở mọi chỗ khác chứ không chỉ chỗ gỡ role.

Lane benchmark giữ nguyên luật cũ, có test pin.

### P7 — reliance dẫn xuất (`74456a9`)

`reliance.py`: `active | suspended | revoked | unknown`, **tính lúc đọc**.
`approval.status` không bao giờ đổi. Revision bị **thay** vẫn `active`;
bị **rút** thì `suspended`; bị **disable** thì `revoked`.

`approved_config.yaml` vẫn trả **200** khi thuật toán bị tắt, mang
`reliance_status`, khối `warning` ở đầu file, và `candidate.bundle`
(bundle_id / revision / checksum). Disable ghi thêm sự kiện
`algorithm_disabled_after_approval` vào journal mỗi run đã duyệt —
**không** tự withdraw, vì disable có thể vì lỗi bảo mật, crash,
dependency hay đang điều tra, không ca nào chứng minh khuyến nghị sai.

### P8 — admin (commit cuối)

`/admin/users` (list, grant/revoke role có lý do, disable/enable),
`/admin/audit` (một route, projection theo capability),
`/admin/ops/jobs` + cancel break-glass có `reason`.

Hai luật đáng test riêng: **không ai tự cấp `demo_owner`** (422, kể cả
admin), và **không ai để deployment mất người quản trị** — đếm theo
capability `user.manage`, không theo tên role, trong cùng transaction.

---

## 3. Test — chỉ chạy phần vừa sửa

An nhắc (2026-08-28): **không chạy full suite**, chỉ chạy test của phần
vừa sửa. Đã ghi vào memory. Con số dưới là các bộ liên quan:

| Bộ | Kết quả |
|---|---|
| `tests/test_roles.py` | 38 pass |
| `tests/test_run_identity.py` | 16 pass |
| `tests/test_sweep_stop.py` | 7 pass |
| `tests/test_reliance.py` | 16 pass |
| `tests/api/test_api_access.py` | 18 pass |
| `tests/api/test_api_plugin_governance.py` | 19 pass |
| `tests/api/test_api_decision_review.py` | 21 pass |
| `tests/api/test_api_admin.py` | 15 pass |
| `tests/api/test_api_decisions.py` | 70 pass |
| `tests/api/test_test_bench.py` | 29 pass |

**Tổng test mới viết: 150.**

Lần cuối chạy `tests/api/` đầy đủ (sau P6, trước khi An nhắc):
**996 pass / 3 fail**, cả ba có sẵn trên `main`:

| Test | Nguyên nhân |
|---|---|
| `test_api_advice.py::…::test_an_unknown_run_is_a_404` | `DecisionRunService` thiếu `trace_summary` |
| `test_decision_export_golden.py` × 2 | golden `.md` checkout CRLF, so với `\n` |

Ngoài ra, **hai lỗi do tôi gây và đã sửa trong lúc làm**: ba cột
`disabled_*` chèn nhầm vào bảng `models` thay vì `plugin_bundles`
(migration-vs-models bắt được), và một flaky có sẵn ở đường import
plugin — `zipfile.writestr` đóng dấu thời gian hiện tại, độ phân giải 2
giây, nên cùng nội dung build hai lần qua ranh giới giây ra hai checksum
khác nhau; đã ghim `ZipInfo(date_time=…)`.

---

## 4. P12 — desktop, làm sớm vì nó chặn phát hành

**Đã đo trước khi sửa.** Dựng đúng tình huống (DB schema 0011 + tài
khoản `admin` có `is_admin=1` + `.env` cũ) rồi boot code mới:

| | trước khi vá | sau khi vá |
|---|---|---|
| App boot, login `admin:admin` | được | được |
| profile | `production` | `desktop-single-user` |
| roles | `engineer + admin` | `engineer + reviewer + admin` |
| `run.review` | **không** | có |
| `algorithm.import` / `publish` | **không** | có |

Nghĩa là trước khi vá, giám khảo vẫn chạy được so sánh nhưng **không
duyệt được cấu hình nào và không import được thuật toán**.

**Vá launcher đặt profile thôi là chưa đủ** — đo riêng và xác nhận: kết
quả y hệt. Lý do: `.env` cũ dùng dạng hai phần `admin:admin`, không khai
role nào, nên reconcile không có gì để thêm. Launcher phải cấp **cả
profile lẫn seed roles lẫn SoD** khi file im lặng, và cấp **mỗi lần
launch** chứ không chỉ lần đầu — file viết từ hai bản trước sẽ không bao
giờ tự mọc thêm dòng.

Ba luật giữ kèm: cái gì `.env` nói rõ thì thắng (kể cả ai chọn `demo`);
password đang có được giữ nguyên; tài khoản đã đổi tên thì cấp role cho
đúng tên đó chứ không dựng thêm tài khoản mẫu bên cạnh.

Cộng: template `.env` mới seed **ba tài khoản** (`admin` ba role,
`engineer`, `reviewer`) để một máy có thể trình bày luồng theo cả hai
kiểu — một người làm hết, và hai vai tách nhau. Và `docs/DEMO-PROFILE.md`
— cách bật demo trên máy đã cài, và quy trình gỡ trước production.

`tests/desktop/test_upgrade_keeps_access.py`, **9 test**, khẳng định
**kết quả** chứ không khẳng định cơ chế: đăng nhập sau nâng cấp và làm
được việc. Đó là dạng duy nhất bắt được lỗi thứ hai, vì lỗi đó qua được
mọi assertion về profile.

---

## 5. P9 — web, mới xong một nửa

**Đã làm (2 commit):**

- `SessionUser` mang `roles` + `capabilities`; helper `can()` và hằng
  `CAPABILITIES`. Session khôi phục từ store bản cũ mặc định **rỗng**,
  không phải "đủ mọi quyền".
- `NavItem.capability` thay `NavItem.admin`; Sidebar lọc theo capability
  server gửi, không theo tên role.
- Badge hiện **mọi** role đang giữ; `demo_owner` hiện một mình.
- `DeploymentBanner` — banner `relaxed` và `DEMO MODE` không tắt được,
  đọc từ `/health` (đã thêm khối `deployment` vào endpoint đó), có cả ở
  trang login.
- `HumanActs` thành bốn bước: Send → Claim → Acknowledge → Approve, kèm
  nút Take over (đòi lý do) và Put it back. Câu dưới nút nói **thiếu
  bước nào**.
- API client: `fetchReviewState`, `submitForReview`, `claimReview`,
  `takeoverReview`, `releaseReview`, `cancelSubmission`.
- 34 khoá i18n mới, **cả `en.json` lẫn `vi.json`**.

**Còn lại trong P9:**

- Trang `/algorithms` (đã thêm mục vào rail, **chưa có route**) + detail
  + publications + audit timeline.
- Candidate picker lọc theo publication current, hiện chip trạng thái
  cho bundle chưa publish.
- Nút "Tải cấu hình lịch sử" + cảnh báo reliance trên trang decision
  (khoá i18n đã có, chưa nối vào component).
- Trang `/admin/users` (đã thêm mục vào rail, **chưa có route**).

**Nghiệm thu web**: `npx tsc --noEmit` sạch; `vitest` 1080/1081 pass.
Lỗi còn lại là `agent-dock.test.tsx`, đọc file tôi không đụng — có sẵn.
Hai lỗi khác gặp lúc làm (`decision-prose`, `decisions-page`) cũng có
sẵn: đã đối chiếu tập khoá `en.json` trước/sau, **không mất khoá nào**,
và hai khoá chúng đòi (`preflight.disabledDerived`, `outcome.title`)
chưa từng tồn tại.

---

## 6. Còn lại

**P10** — Review Queue ba tab (Runs / Algorithms / Legacy), dashboard
theo role, modal submit/takeover.

**P11** — `/admin/*` bốn trang, dời `/settings` và `/system` vào đó.

**Phần đuôi P9** — bốn mục ở §5.

Ngoài phạm vi plan (ghi từ đầu): governance cho PPO model, job queue bền
qua restart, đồng bộ settings nhiều worker, gỡ luồng benchmark cũ,
sandbox bảo mật thật cho plugin.

**Nhánh này giờ phát hành desktop được** — ràng buộc giám khảo đã có
test giữ. Nhưng hai mục rail (`/algorithms`, `/admin/users`) đang trỏ
tới route chưa tồn tại, nên **đừng release trước khi xong P9 + P11**,
nếu không người dùng bấm vào sẽ ra 404.

---

## 7. Quyết định phát sinh khi làm (plan không lường trước)

1. **`status` của plugin thêm giá trị thứ ba thay vì thêm cột.**
2. **`held` thay `quarantined`** — tên cũ đã có nghĩa khác ở discovery.
3. **Fixture `client` đăng nhập sẵn**, thêm fixture `anonymous`.
4. **Thêm tài khoản seed `erin:engineer`** cho test "bị chặn".
5. **Ticket router tách khỏi socket router.**
6. **Thứ tự refusal artefact-trước-người** — áp cho cả `decide_config`
   lẫn `withdraw_config`.
7. **`_decision_action()`** chọn `self_approve_config`.
8. **`acknowledged_under` nhận cả `review` lẫn `acknowledge`.**
9. **`ReviewConflict` → 409**, tách khỏi 403 và 422.
10. **Claim tự nhả kiểm lúc đọc**, không chỉ ở chỗ gỡ role.
11. **`latest()` khác `current()`** — "chưa gửi" và "đã xong" là hai
    trạng thái.
12. **`append_event` công khai** trên cả hai backend.
13. **`/health` mang khối `deployment`** — banner phải lên được trước
    khi ai đăng nhập.
14. **`ReviewAssignment` chứ không phải `ReviewState`** ở web —
    `ReviewState` đã nghĩa "đã đọc chưa".
15. **Launcher cấp profile + seed roles + SoD, mỗi lần launch** (§4).

---

## 8. Lệnh để tiếp tục

```powershell
git switch tongduyan_roles-capabilities     # đang ở đây, cây sạch
python -m pytest tests/desktop/ -q                        # 110 pass
python -m pytest tests/test_roles.py tests/test_reliance.py -q
cd apps/web; npx tsc --noEmit; npx vitest run src/lib/__tests__ src/components/__tests__
```

Không có gì chạy nền. Không push remote nào. `.ai-log/` chưa commit —
phải quét secret bằng regex trước.
