# Updater: bỏ API khỏi đường kiểm tra cập nhật

**Ngày:** 2026-08-26
**Nhánh:** `tongduyan_updater-cdn` → merge vào `main`
**Phát hành:** desktop 0.1.14

## Triệu chứng

An cập nhật lên 0.1.13 xong, mở app 0.1.12, **không thấy hộp thoại hỏi
cập nhật**. Build CI xanh, release publish đúng, `latest.json` ghi đúng
`0.1.13`, link tải cố định vẫn sống. Nhưng app im.

## Nguyên nhân

Log app nói thẳng — `%LOCALAPPDATA%\PlanBench\logs\planbench.log`:

```
10:31:46 INFO  planbench.desktop: checking for updates (anonymously)
10:31:46 INFO  planbench.desktop: PlanBench 0.1.12 is the newest release
14:18:16 INFO  planbench.desktop: checking for updates (anonymously)
14:18:16 WARN  planbench.desktop: update check failed:
               .../releases?per_page=30 answered 403
14:19:15 WARN  ... answered 403
```

Dòng 10:31 trả lời đúng ở thời điểm đó — 0.1.13 mãi 11:53 giờ máy mới
publish. Hai dòng 14:18 và 14:19 là sau khi publish, và cả hai đều 403.

Đo hạn mức ẩn danh ngay lúc đó:

```
anonymous core: 60 / 60   remaining 0
resets at     : 14:23:17 local
```

**GitHub cấp 60 lượt gọi API ẩn danh mỗi giờ, tính theo IP.** App chỉ tốn
1 lượt mỗi lần mở, nên nó gần như không bao giờ là thứ làm cạn hạn mức —
nó chỉ là thứ *phát hiện ra*. 59 lượt kia là git, là script kiểm CI, là
mọi thứ khác trên máy gọi GitHub ẩn danh.

Và khi hết hạn mức thì **hỏng im lặng**: một dòng WARNING trong log, UI
không nói gì, người dùng tin rằng mình đang chạy bản mới nhất.

Đây là lần thứ hai lỗi này cắn. Lần đầu là do chính tôi poll CI 30 giây
một lần; runbook đã ghi lại và hạ nhịp poll. Lần này **không ai poll cả**
— dùng git bình thường trên máy dev là đủ.

## Đã thử hướng vá cục bộ trước

An chọn hướng 1 trước: thêm `PLANBENCH_UPDATE_TOKEN` vào
`%LOCALAPPDATA%\PlanBench\.env`. Đã làm và đã kiểm chứng chạy được (xem
mục "Token vẫn giữ" bên dưới). Nhưng khi hỏi "việc này có ảnh hưởng đến
người tải mới không", câu trả lời làm rõ giới hạn của nó:

- Token của An **không** ảnh hưởng ai khác — installer không đóng gói
  `.env` nào, và template ở `provision.py:92` ghi dòng token ở dạng
  comment, sinh riêng trên từng máy.
- Nhưng người dùng mới **vẫn dính cùng lỗi** nếu ở sau NAT văn phòng
  dùng chung IP, hoặc trên máy dev bận. Và họ sẽ không bao giờ mở `.env`
  ra sửa.

Token vá cho một máy. Không tiêu hạn mức thì vá cho tất cả.

## Sửa

`apps/desktop/planbench_desktop/updater.py`. `latest_release()` tách làm
hai, thử manifest trước, API sau:

```python
try:
    return _latest_from_manifest(current)
except UpdateError as exc:
    logger.info("the published manifest was unusable (%s); asking the API", exc)
return _latest_from_api(current, credential)
```

`_latest_from_manifest` đọc
`github.com/<repo>/releases/latest/download/latest.json` — asset của
release, do CDN phục vụ, **không có hạn mức nào**.

### Ba quyết định, đều có lý do ghi trong code

**1. Request này gửi không ký.** CDN trả redirect sang URL storage đã
pre-sign, và URL đó *từ chối* request mang thêm credential. Ký nó sẽ làm
hỏng đường chính đúng cho những người đã chịu khó cấu hình token. Cũng
không cần: release là public.

**2. Giữ nhánh API làm fallback, không xoá.** `releases/latest` là
release mới nhất *thuộc bất kỳ loại nào*, mà repo này mang cả tag không
phải app này. Nên manifest không được tin chỉ vì nó là "cái mới nhất" —
nó phải tự khai `version` và một `asset` kết thúc bằng `.exe`. Thiếu một
trong hai thì raise, và caller rơi về API, nơi lọc được theo tag prefix
`desktop-v`. Đó là việc duy nhất API làm được mà manifest không.

**3. URL ghim theo tag, không theo `latest`.** Release trả về mang
`releases/download/desktop-v0.1.13/...` chứ không
`releases/latest/download/...`. Nếu có release publish xen giữa lúc check
và lúc tải, cái được đọc hash và cái được cài phải là cùng một file — mà
hash là thứ duy nhất đứng giữa việc tải về và việc chạy một executable
lạ với quyền của người dùng.

## Kiểm chứng

Chạy đúng hàm app gọi lúc khởi động, không token, trên release thật,
qua mạng thật:

```
token in env      : ''
result            : 0.1.13 / desktop-v0.1.13
installer url     : .../releases/download/desktop-v0.1.13/PlanBench-Setup.exe
anon budget before: 35 after: 35 -> spent 0
```

Không token, tìm ra bản mới, tốn **0 lượt** hạn mức.

| Kiểm | Kết quả |
|---|---|
| `tests/desktop/test_desktop_updater.py` | 37 pass (trước 30) |
| `tests/desktop` toàn bộ | 101 pass |
| `ruff check` + `ruff format` | sạch |

### Một bẫy trong chính bộ test

Fixture `api` khớp stub theo **chuỗi con của URL**. Key cũ là
`"/releases"` — sau thay đổi này nó khớp **cả hai** URL
(`/releases?per_page=30` và `/releases/latest/download/latest.json`), nên
manifest nhận nhầm payload dạng list và 8 test đỏ với
`AttributeError: 'list' object has no attribute 'get'`.

Đổi key sang `"per_page"` — chuỗi chỉ tồn tại ở URL API. Đây là loại lỗi
test-only nhưng đáng ghi: fixture khớp lỏng thì mỗi lần thêm một URL mới
là một lần có nguy cơ khớp nhầm.

### Test mới

Class `TestTheCheckThatDoesNotSpendTheApiBudget`:

- tìm được bản mới mà không chạm `api.github.com`
- đang up-to-date cũng không chạm API (đây là ca thường gặp, chạy mỗi
  lần mở app trên mọi máy)
- URL ghim theo tag, không chứa `/latest/`
- manifest hỏng thì fallback — 3 dạng hỏng: thiếu `version`, thiếu
  `asset`, `asset` không phải `.exe`
- CDN chết thì fallback

Đổi 1 test cũ thành `test_a_token_is_used_on_the_api_and_never_on_the_cdn`
— pin đúng tính chất ở quyết định (1): token đi vào request API, không
đi vào request CDN.

## Token vẫn giữ, không xoá

`PLANBENCH_UPDATE_TOKEN` đã ghi vào `%LOCALAPPDATA%\PlanBench\.env`
(dòng 24, thay đúng dòng comment mà `provision.py` đặt sẵn cho việc này).
Giữ lại vì nó là lưới an toàn cho nhánh API fallback.

PAT không scope, và repo là **public** (`private: False`) nên đó đúng mức
cần: token chỉ nâng hạn mức 60 → 5000, không mở được gì. Lộ ra cũng
không cho ai quyền gì.

Ghi chú kỹ thuật: lần ghi đầu tôi dùng `read_text`/`write_text` và nó đổi
**toàn bộ** file từ CRLF sang LF. Đã làm lại ở mức byte từ bản sao lưu,
chỉ đúng một dòng đổi. Bản gốc còn ở `.env.bak-before-update-token`.

## Đường ship, và cái bẫy của nó

Bản 0.1.12 An đang chạy mang updater **cũ** — nó vẫn tìm 0.1.14 qua API.
May là token đã có nên nó chạy được. Cài xong 0.1.14 thì đường CDN mới có
hiệu lực.

Đây đúng cái runbook đã ghi từ trước: *một lỗi trong updater không thể tự
gửi bản vá của chính nó đi*. Với người đang chạy bản cũ trên IP đã cạn
hạn mức, cách duy nhất là cài tay một lần từ link cố định:

`https://github.com/hungnguyen-1601/T011-rav19-planbench/releases/latest/download/PlanBench-Setup.exe`

Từ 0.1.14 trở đi thì hết class lỗi này.

## Docs

Cập nhật mục "The rate limit is shared with the running app" trong
`docs/DESKTOP-RELEASE.md`: ghi lần thứ hai nó cắn và lần này không ai
poll cả, ghi rằng từ 0.1.14 app không tiêu hạn mức nữa, và khuyến nghị
người theo dõi CI từ máy này dùng manifest CDN hoặc gọi có xác thực —
hạn mức 5000/giờ riêng, để phần ẩn danh cho thứ không xác thực được.
