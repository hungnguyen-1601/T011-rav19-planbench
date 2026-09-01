# Đăng nhập xong ở lại dashboard, và hai chỗ app desktop im lặng khi hỏng

Ngày 2026-08-29 · nhánh `tongduyan_signin-landing-and-updater`

Bốn việc, hai nửa. Nửa web là hai thay đổi An đặt ra ở UI. Nửa desktop
là hai lỗi tìm ra khi truy nguyên câu "tôi mở app thì không thấy auto
update mà nhận được là system unavailable".

---

## 1. Đăng nhập xong ở lại dashboard

`apps/web/src/app/login/page.tsx`, `app/auth/callback/page.tsx`,
`app/welcome/page.tsx`.

Cả ba cửa vào đều `router.push("/decisions")`. Đó là **một** việc trong
số nhiều việc app này làm, và với người mở lần đầu thì hạ cánh xuống đó
đọc như thể so sánh là toàn bộ mục đích của sản phẩm. Ba chỗ đều chuyển
sang `/`.

Ba chứ không phải một, vì có ba cửa: form mật khẩu, callback của
provider, và trang hỏi tên cho tài khoản mới. Sửa một cửa để hai cửa kia
còn nguyên là kiểu lỗi chỉ lộ ra khi ai đó đăng nhập bằng đường khác.

## 2. Ô hướng dẫn vận hành trên dashboard

`apps/web/src/app/page.tsx`, `globals.css`, `en.json`, `vi.json`.

Nằm **giữa** hàng số đếm và hàng nút tắt. Vị trí là một khẳng định chứ
không phải trang trí: đặt trên hàng số thì nó đẩy đi bằng chứng rằng có
một workspace tồn tại; đặt dưới hàng nút thì nó đến sau khi người đọc đã
bị bắt chọn một việc. Người mở lần đầu vừa đọc bảy con số về một nơi họ
chưa hiểu, và thứ ngay dưới đó là một hàng động từ - tạo, chạy, duyệt -
giả định họ đã biết mình muốn cái nào.

**Hiện với mọi người, không chỉ lần đầu.** Không có cách nào đáng tin để
biết đâu là lần đầu: session nằm trong `sessionStorage` nên không sống
qua một tab mới, người quen dùng vẫn trông như người mới mỗi sáng. Và
một hàng lúc hiện lúc không là hàng người ta không tìm lại được đúng lúc
cần.

Hai khoá mới, đủ cả `en.json` và `vi.json`.

## 3. Updater: token hỏng không được làm mất cập nhật

`apps/desktop/planbench_desktop/updater.py`.

`PLANBENCH_GITHUB_TOKEN` là **tuỳ chọn** - nó mua thêm hạn mức API cho
một repo vốn đã public. Nhưng một token hết hạn, bị thu hồi hay gõ sai
thì GitHub trả 401, và `_request` ném `UpdateError` cho mọi lần gọi. Kết
quả: `offer()` ghi một dòng log rồi trả `False`, app lặng lẽ ngừng cập
nhật, còn nguyên nhân nằm trong một biến môi trường không ai nghĩ tới.

Máy có token hỏng phải đứng đúng chỗ máy không có token, không được tệ
hơn. Nay 401 - và **chỉ** 401 - làm request thử lại một lần không ký.

403 thì không thử lại. 403 từ API này gần như luôn là hạn mức giờ chứ
không phải credential, mà hạn mức ẩn danh nhỏ hơn hạn mức đã ký - bỏ
token đi để thử lại là đổi một lần chờ lấy một lần bị từ chối.

Bốn test. Cái đáng kể nhất đi hết luồng với token hỏng và bắt phải đi
qua **đường API**: manifest vốn đã gửi không ký nên nó sống sót qua
token hỏng mà chẳng cần sửa gì; chỉ có listing mang credential, và cách
duy nhất chạm tới listing là làm manifest không dùng được - đúng thứ máy
nào cũng gặp khi tag mới nhất của repo không phải bản desktop.

## 4. Cửa sổ mở lên một instance đã chết phải nói tại sao

`apps/desktop/planbench_desktop/main.py`.

Mở app lúc app đang chạy thì **không** dựng server thứ hai - một file
SQLite, một người ghi - nên cửa sổ mới trỏ vào cổng của tiến trình thứ
nhất. Đóng cửa sổ thứ nhất, server đi theo, và cửa sổ thứ hai còn lại
một trang mà triệu chứng duy nhất là cái pill trên header ghi "System
unavailable". Câu đó đúng, và nó không nêu nguyên nhân lẫn cách xử lý.

Nay cửa sổ đi mượn có một thread canh cổng đó. Ba lần trượt liên tiếp
mới thay trang, không phải một: một lần trượt là hình dạng của một máy
đang bận, còn thay trang dưới tay người đang làm việc là cái sai nặng
hơn trong hai cái. Trang thay thế viết cả tiếng Việt lẫn tiếng Anh, vì
lúc đó cửa sổ không còn truy cập được bản dịch của app nữa - app đã đi.

Cửa sổ của chính chủ server thì **không** canh gì cả: nó *là* server.
Canh ở đó là poll một cổng chỉ ngừng trả lời khi tiến trình đã trên
đường đóng, và có thể chạy đua với shutdown để hiện thông báo này ngay
lúc đang tắt.

---

## Kiểm chứng

| Bộ | Kết quả |
|---|---|
| `tests/desktop/test_desktop_updater.py` | 41 pass |
| `tests/desktop/test_desktop_launcher.py -k Window` | 4 pass |
| `dashboard-page.test.tsx` | 18 pass |
| `i18n.test.ts`, `dashboard.test.ts`, `topbar.test.tsx` | 55 pass |
| `npx tsc --noEmit` | sạch |
| `ruff check`, `ruff format` | sạch |

Không chạy full suite - theo luật §6.

## Còn lại cho An

Hai sửa ở phần desktop **chỉ tới tay người dùng qua một bản phát hành**.
Bản đang phát hành là 0.1.15; muốn hai lỗi này tới máy giám khảo thì cần
bump 0.1.16 và đẩy tag. Chưa làm, vì phát hành là quyết định của An.

Vẫn còn: máy An đang cài 0.1.13 và bản đó không tự cập nhật được - phải
cài tay một lần, xem `docs/DESKTOP-RELEASE.md` §133.
