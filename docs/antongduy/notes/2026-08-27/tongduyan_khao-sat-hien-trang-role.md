# Khảo sát hiện trạng role (admin / reviewer / engineer) — 2026-08-27

Khảo sát trước khi thiết kế lại role. Không đổi dòng code nào. Plan
thiết kế ở `plans/2026-08-27/thiet-ke-role-engineer-reviewer-admin.md`.

## 1. Kết luận một câu

**Code hiện không có role engineer/reviewer.** Chỉ có một loại tài khoản
`member` cộng cờ `is_admin`; quyền dựa trên *ownership* (ai tạo thì được
sửa) và trên *review opt-in* (owner tự chọn một member khác làm reviewer
cho từng run). Ba cái tên An nhắc — admin, reviewer, engineer — tồn tại
ở ba nơi khác nhau và không khớp nhau, nên mới "nhạt nhòa".

## 2. Ba nguồn nói ba kiểu

| Nguồn | Nói gì | Trạng thái |
|---|---|---|
| `contracts/CONTRACTS.md` HĐ-14 | Hai vai `engineer` / `approver`, "một bảng, một cột `role`" | Là luật, nhưng code không còn cột `role` trên `users` |
| `apps/api/planbench_api/accounts.py`, `auth.py` docstring | Gỡ role có chủ đích ở "accounts refactor": "there are no roles to require: every signed-in person is a member"; lý do: một người làm việc một mình phải sign-out/sign-in để qua cổng duyệt của chính mình | Đang chạy |
| `apps/api/planbench_api/approval.py::Role` | Giữ enum `ENGINEER, APPROVER, OPERATOR, REVIEWER, MEMBER, ADMIN` chỉ để đọc audit cũ; "nothing assigns any of the four" | Nhãn lịch sử |

Tiến hoá theo docs: đề bài gốc đòi ≥2 vai (`phan-tich-de-bai…` mục 4:
Engineer / Tech Lead) → F10/F11 làm xong với `OPERATOR/REVIEWER/ADMIN` +
`require_roles()` (note 2026-08-04) → refactor accounts gỡ về ownership
(không có note/plan riêng ghi lại quyết định này) → plan tab import
2026-08-20 mục 7 hỏi "Ai được import? có cần vai trò riêng không?" và
**chưa có câu trả lời**.

## 3. Những gì đang thực sự gate quyền

### Backend

| Chỗ | Cơ chế | Ai được |
|---|---|---|
| `plugin_service._require_admin` | `user.is_admin` | Chỉ admin được import / revalidate plugin. `docs/plugin_import_security.md` §5 tự gọi đây là "interim rule… a review queue is expected later" |
| `plugin_service._require_owner_or_admin` | ownership | Sửa metadata bundle: người upload hoặc admin |
| `routers/settings.py` PUT | `Forbidden` nếu không admin | Ghi API key |
| `decisions.py::decide_config` | `actor == created_by` → 409 | **Ai cũng duyệt được** trừ người tạo run (HĐ-14 separation of duties) |
| `decisions.py::review` | không chặn | Ai cũng "mark reviewed" được, một lần |
| `services.py::capabilities` (benchmark legacy) | OWNER / REVIEWER (được nêu tên) / ADMIN | Máy trạng thái 11 state + `review_requests` (spec/result) — luồng benchmark cũ, deprecated route |
| `registry_service` (robot profile, model PPO) | ownership + admin | Ai đăng nhập cũng upload model được |
| `routers/simulations.py`, `scenarios.py`, `maps.py` (trừ `materialise`), `ws.py` | **không có auth** | Người vãng lai chạy được `POST /simulations/{id}/run` — note 2026-08-24 đã xếp là blocker deploy |

Quan sát: `Capability.REVIEWER` trong `approval.py` là "được nêu tên trên
request đang pending", không phải role. Đây là mô hình tốt cho *một* run
nhưng không trả lời "ai được phép là reviewer" — engineer cũng gửi cho
engineer khác được.

### Frontend (`apps/web/src`)

- Gate role duy nhất: `is_admin` → ẩn mục `/settings` (`Sidebar.tsx:32`,
  `navigation.ts:151`), badge "Admin" (`UserMenu.tsx:68`), khoá form API key
  (`settings/page.tsx:96`).
- Còn lại là gate "đã đăng nhập chưa" (`session === null`) và so
  `session.user.id === run.created_by` ở `DecisionDetail.tsx:1197` — chỉ
  cosmetic, server là người quyết.
- `lib/reviews.ts::canRun / canAcceptResult` — viết cho luồng benchmark cũ,
  có test, **không có call site** trong app.
- `/reviews` page = inbox/sent của `review_requests` (benchmark cũ), không
  nối với decision run. `SendForReview.tsx` cũng thuộc luồng cũ.
- Tab "Import algorithm" nằm trong `/models` (tab thứ ba), không có trang
  thuật toán riêng.

### Schema

- `users`: `id, nickname, email, display_name, avatar_url, is_admin,
  password_hash` — **không có cột `role`** (migration 0002).
- `decision_runs` (0006/0007): `created_by, review_state, reviewed_by,
  config_state, config_decided_by` + bảng `decision_run_reviews` append-only.
- `plugin_bundles` (0010/0011): `status` (active/disabled),
  `validation_status` (pending/structural/loaded/failed), `uploaded_by_user_id`,
  revision. `usable = active ∧ validation ∈ {structural, loaded}` — **không
  có trạng thái "đã duyệt cho engineer dùng"**; validate xong là dùng được.
- `review_requests`: keyed theo `benchmark_id` (luồng cũ).

### Admin được cấp thế nào

`PLANBENCH_ADMIN_NICKNAMES` / `PLANBENCH_ADMIN_EMAILS` — đọc **lúc tạo
account** (`account_service.apply_admin_policy`), không có UI đổi role,
`set_admin()` trong repository có nhưng không route nào gọi. Desktop
`provision.py` sinh `admin:admin` + `PLANBENCH_ADMIN_NICKNAMES=admin` lần
chạy đầu; bản desktop là một máy một người, **người đó tạo run thì không
tự duyệt được** vì `created_by` check — hạn chế đang tồn tại, chưa ai ghi.

## 4. Hệ quả cho thiết kế

1. Muốn ba role thật thì phải **đảo ngược** quyết định ở `accounts.py`
   docstring. Cần ghi rõ vì sao đảo: ownership trả lời "bản ghi nào",
   role trả lời "loại hành động nào" — hai câu hỏi khác nhau, cái sau
   chưa có ai trả lời. Lý do gỡ role ngày trước (một người tự chặn mình)
   giải quyết bằng `is_admin`/self-approve có audit, không phải bằng
   cách bỏ role.
2. HĐ-14 phải bump: `engineer/approver` → `engineer/reviewer/admin`, và
   ghi ngoại lệ self-approve cho desktop một người (mục 0 đã có tiền lệ
   "quy trình duyệt một người").
3. Reviewer "kiểm soát thuật toán" cần thêm một trạng thái trên bundle
   (published / unpublished) — chính là "review queue" mà
   `plugin_import_security.md` §5 hứa.
4. Ba nhóm route không auth phải đóng cùng lúc, nếu không role chỉ gate
   được nửa hệ thống.
5. `/reviews` + `review_requests` của benchmark cũ: hoặc mở rộng sang
   decision run (thêm `subject_kind`), hoặc để nguyên legacy. Quyết định
   ghi trong plan (Q5).
