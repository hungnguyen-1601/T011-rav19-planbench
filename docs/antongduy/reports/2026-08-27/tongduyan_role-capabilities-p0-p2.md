# Thi hành plan role: P0–P8 xong, backend đã đủ — 2026-08-27

Báo cáo cập nhật lần 3. Bản đầu phủ P0–P2, bản hai phủ tới P6; bản này
phủ tới **P8 — toàn bộ phần backend của plan**. Tên file giữ nguyên để
link cũ không hỏng.

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
| P8 | Admin: users/roles, audit, break-glass | xong | (commit cuối) |
| **P9–P12** | **web (3 phase) + desktop** | **chưa bắt đầu** | — |

Nhánh `tongduyan_roles-capabilities` từ `main`, **16 commit**, chưa push.

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

## 4. Còn lại — P9 đến P12, toàn bộ web + desktop

Chưa động một dòng nào ở `apps/web`. Việc còn lại:

**P9 — web nền**: `SessionUser.roles/.capabilities` từ `/auth/me`;
`NavItem.capability` thay `NavItem.admin`; badge role; banner khi
`separation_of_duties=relaxed` và banner DEMO MODE không tắt được;
`HumanActs` thành ba bước Claim → Acknowledge → Approve; trang
`/algorithms` mới + detail + publications; candidate picker lọc theo
publication; nút "Tải cấu hình lịch sử" khi reliance ≠ active.

**P10 — web review**: Review Queue ba tab, dashboard theo role, modal
submit/takeover.

**P11 — web admin**: `/admin/*` bốn trang, dời `/settings` và `/system`.

**P12 — desktop**: launcher `setdefault` profile trong process; template
`.env` ba tài khoản (`admin` ba role, `engineer`, `reviewer`); smoke gate
**ca upgrade từ 0.1.14 với `.env` cũ**; `docs/DEMO-PROFILE.md`.

Nhắc lại ràng buộc chi phối P12: **bản desktop đã phát hành đang được ban
giám khảo chấm bằng `admin:admin`**. Cơ chế đỡ đã có từ P1 (reconcile
role ở API startup theo profile), nhưng **phần launcher chưa viết** —
nghĩa là hôm nay một bản cài cũ nâng cấp lên nhánh này sẽ rơi vào profile
`production` và `admin` chỉ còn role `admin`. **Đây là việc bắt buộc phải
làm trước khi phát hành bất cứ bản desktop nào từ nhánh này.**

Ngoài phạm vi plan (đã ghi từ đầu): governance cho PPO model, job queue
bền qua restart, đồng bộ settings nhiều worker, gỡ luồng benchmark cũ,
sandbox bảo mật thật cho plugin.

---

## 5. Quyết định phát sinh khi làm (plan không lường trước)

1. **`status` của plugin thêm giá trị thứ ba thay vì thêm cột.** Cột thứ
   hai sẽ là câu trả lời thứ hai cho câu hỏi cột `status` đã trả lời.
2. **`held` thay `quarantined`** — `QuarantinedPlugin` ở discovery (H5)
   đã nghĩa "manifest không parse được".
3. **Fixture `client` đăng nhập sẵn**, thêm fixture `anonymous`. 306 lời
   gọi GET, chỉ 128 có header; sửa 178 chỗ là churn cơ học.
4. **Thêm tài khoản seed `erin:engineer`** — alice/bob/carol mang
   `engineer+reviewer`, nên test "người không có quyền bị chặn" cần một
   người thật sự không có.
5. **Ticket router tách khỏi socket router** — socket ngoài `/api/v1`,
   ticket là POST có auth nên vào trong.
6. **Thứ tự refusal artefact-trước-người**: "run này không có card" và
   "chưa từng duyệt" trả lời trước "anh không giữ review này" / "thiếu
   lý do". Hỏi ngược sẽ đẩy người ta đi tìm một quyền không giúp được gì.
7. **`_decision_action()`** chọn `self_approve_config` khi một tài khoản
   vừa tạo run vừa ký.
8. **`acknowledged_under` nhận cả `review` lẫn `acknowledge`** — store
   ghi `review` từ trước khi lane này tồn tại, và những dòng đó là
   acknowledge thật.
9. **`ReviewConflict` → 409** (thua cuộc đua thì reload), tách khỏi
   `ReviewNotAllowed` → 403 (cần quyền khác) và `ReviewError` → 422.
10. **Claim tự nhả kiểm lúc đọc**, không chỉ ở chỗ gỡ role.
11. **`latest()` khác `current()`**: "chưa từng gửi" và "đã xong" là hai
    trạng thái, một query trả `None` cho cả hai sẽ bị gộp.
12. **`append_event` công khai** trên cả hai backend — cho những việc xảy
    ra *với* một quyết định chứ không *trong* nó.

---

## 6. Lệnh để tiếp tục

```powershell
git switch tongduyan_roles-capabilities     # đang ở đây, cây sạch
python -m pytest tests/test_roles.py tests/test_run_identity.py tests/test_sweep_stop.py tests/test_reliance.py -q
python -m pytest tests/api/test_api_admin.py tests/api/test_api_decision_review.py -q
```

Không có gì chạy nền. Không push remote nào. `.ai-log/` chưa commit —
phải quét secret bằng regex trước.
