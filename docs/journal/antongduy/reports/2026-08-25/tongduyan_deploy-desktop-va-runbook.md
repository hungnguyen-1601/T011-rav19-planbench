# Đưa PlanBench lên desktop app và chốt quy trình release

- **Ngày:** 2026-08-25
- **Nhánh:** làm trên `tongduyan_desktop-app`, đã merge `main`; sau đó merge tiếp `tongduyan_plugin-config-and-edit`
- **Runbook (thứ session sau sẽ đọc):** [docs/DESKTOP-RELEASE.md](../../../../reference/DESKTOP-RELEASE.md)
- **Tài liệu người dùng + người build:** [docs/DESKTOP.md](../../../../reference/DESKTOP.md)
- **Plan:** [desktop-app-windows.md](../../plans/2026-08-24/desktop-app-windows.md)
- **Khảo sát nền:** [tongduyan_khao-sat-deploy-len-app.md](../../notes/2026-08-24/tongduyan_khao-sat-deploy-len-app.md)

---

## 1. Kết quả

Sản phẩm đã **thật sự deploy được và đang chạy** trên máy An: installer
Windows, link tải cố định, tự cập nhật.

| | |
|---|---|
| Link tải | `https://github.com/hungnguyen-1601/T011-rav19-planbench/releases/latest/download/PlanBench-Setup.exe` |
| Đăng nhập | `admin` / `admin` |
| Bản đã phát hành | 0.1.0 → 0.1.8 (0.1.8 đang build lúc viết) |
| Auto-update | **đã nghiệm thu thật**: 0.1.5 → 0.1.6 tự chạy trên máy An |

Cách release từ nay: sửa `apps/desktop/planbench_desktop/VERSION`,
commit, push, rồi `git tag desktop-v<X.Y.Z>` và push tag. CI lo phần
còn lại. Chi tiết trong runbook.

## 2. Vì sao có runbook riêng

Tám lần release, mỗi lần hỏng một kiểu **khác nhau**, và không lần nào
code báo trước. Đó là loại tri thức chỉ có được bằng cách vấp, nên tôi
gom vào `docs/DESKTOP-RELEASE.md` — viết cho người làm release lần sau,
kể cả khi đó là một session Claude Code mới không nhớ gì về phiên này.

Kèm một memory entry trỏ tới file đó, để session sau tự nạp được con
trỏ thay vì phải mò.

Sáu điều kiện riêng của dự án này, đều đã trả giá để biết:

1. **Version nằm ở ba chỗ phải khớp nhau** — file `VERSION`, tag git,
   và `latest.json`. Workflow **cố ý fail** khi tag lệch stamp: nếu
   không, release tên một đằng, app báo một nẻo, và updater mời mãi
   cùng một bản.
2. **Link cố định chỉ sống khi tên asset không đổi.** Đưa version trở
   lại tên file là vô hiệu hoá mọi bản link đã gửi đi, và người phát
   hiện là người bấm vào.
3. **Bug trong updater không tự ship được bản vá của chính nó** —
   thứ phải đi lấy bản vá lại là thứ đang hỏng. Đã xảy ra hai lần; cách
   thoát duy nhất là cài tay một lần.
4. **Bản cài không có `.git`**, mà manifest Decision Card từ chối ghi
   `unknown`. Build đóng dấu commit vào; **không được nới lỏng luật từ
   chối đó** để card ghi được.
5. **Migration chạy trên máy người dùng, không ai ngồi xem.** Launcher
   backup `planbench.db.bak` trước khi nâng.
6. **Quota GitHub API dùng chung với app đang chạy** — 60 request/giờ
   theo IP. Tôi poll build mỗi 30 giây và làm app của An nhận 403 ở
   chính lượt kiểm tra cập nhật của nó. Nhìn y hệt một bug trong updater.

## 3. Bảy lỗi thật đã tìm và sửa

Không cái nào bị đơn vị test bắt được — tất cả chỉ tồn tại lúc đóng gói
hoặc lúc chạy thật.

| # | Lỗi | Sửa ở |
|---|---|---|
| 1 | Launcher ghi `PLANBENCH_DATABASE_URL` vào `.env` nhưng không export sang environment; Alembic đọc environment | 0.1.0 |
| 2 | `SpaStaticFiles` bắt `HTTPException` của FastAPI, còn Starlette ném lớp cha — compile được, không bao giờ chạy | 0.1.0 |
| 3 | Export thật có `404.html` nên Starlette **trả** 404 thay vì ném; fixture test thiếu file đó nên xanh giả | 0.1.0 |
| 4 | Tải manifest bằng `Accept: application/json` — GitHub trả metadata của asset, không có `sha256` | 0.1.3 |
| 5 | Chuỗi `cmd` nối bằng `&` nuốt mất lệnh installer ở giữa | 0.1.6 |
| 6 | `.env` đúng nhưng database giữ hash mật khẩu cũ — seed chỉ tạo, không cập nhật | 0.1.5 |
| 7 | Bản cài không có `.git` nên Decision Card không đọc được commit | 0.1.7 |

Cộng ba lỗi trong chính script build, tự bắt được khi chạy thật:
`web_root()` tìm `app/web` trong khi cây cài để `web/` ngang hàng;
`$LASTEXITCODE` của `robocopy` lẫn sang guard kiểm commit; workflow chọn
`dist/*.exe` đầu tiên trong thư mục còn bản cũ.

**Điểm chung của cả bảy**: đơn vị test đều xanh. Lỗi 3 và 4 đáng nhớ
nhất — test của tôi *mô phỏng sai* thế giới thật (fixture thiếu
`404.html`, fake transport bỏ qua header `accept`), nên nó xác nhận một
hành vi không tồn tại. Giờ cả hai đều có test khoá đúng điểm đã thủng.

## 4. Cổng smoke — thứ đáng giá nhất

`scripts/desktop/smoke_stage.py` chạy **giữa** lúc dựng stage và lúc
đóng installer, **bằng chính interpreter đóng gói**, và fail thì không
ra release. Nó kiểm sáu thứ mà bộ test về mặt cấu trúc không thể kiểm,
vì suite chạy trên CPython thường từ checkout nơi các cơ chế đó không
tồn tại: import đủ 12 source root · process con còn thấy `PYTHONPATH` ·
plugin thật chạy out-of-process · launcher provision/migrate/serve/stop
· Decision Card đọc được commit · UI export trả lời kể cả deep link.

Nó đã bắt ba lỗi trong bảng trên trước khi chúng ra khỏi máy.

## 5. Việc còn nợ

**Chưa phân loại** (An bảo để sau): 12 test golden đỏ
(`test_host_parity_golden` 5, `test_dwa_core_refactor` 5,
`test_decision_export_golden` 2) — chưa xác định do phiên này hay có
sẵn. Tôi không đoán.

**Nợ có sẵn từ trước, không phải phiên này:** CI trên `main` đỏ vì
`ruff format --check` đòi format lại 26 file và `tests/test_trace_review.py`
import `pandas` không khai ở requirements nào (pytest chết ở collection);
8 error `test_outcome.py` do encoding cp1252 trên Windows;
`planbench_plugin_sdk` thiếu trong `known-first-party` của `ruff.toml`
(thêm vào sẽ re-sort 16 file của người khác nên tôi ghi lại thay vì gộp).

**Flaky, chưa chẩn đoán:** hai test plugin
(`test_a_re_import_of_the_same_version_is_refused`,
`test_the_same_archive_cannot_be_imported_twice`) đỏ đúng một lần trong
một lượt chạy gộp, và xanh ở mọi lần chạy lại — riêng lẻ, theo file, và
chạy lại đúng lệnh cũ (176 passed). Nghi thư mục giải nén plugin dùng
chung. Cần dòm vì flaky vùng này sẽ làm CI đỏ ngẫu nhiên.

**Cắt khỏi v1 có chủ đích:** code signing (nên có cảnh báo SmartScreen),
delta update, tray icon, OAuth, macOS/Linux.

**Việc của An:** `git stash drop stash@{0}` — stash do subagent tạo lúc
dựng baseline, nội dung đã nằm trọn trong HEAD; tôi không tự drop vì là
thao tác huỷ.

## 6. Một giới hạn không phải lỗ hổng

Decision run xếp hàng **một lúc một** (`JobQueue(1)`), vì HĐ-7.4 cấm hai
run đánh giá trên cùng máy — cả hai pin cùng nhân và mỗi cái thành
background load của cái kia. Đó là hợp đồng đo lường, không phải setting
hiệu năng, và không được nới để phục vụ nhiều người.
