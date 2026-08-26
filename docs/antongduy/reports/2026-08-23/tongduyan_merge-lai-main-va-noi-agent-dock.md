# Merge lại `main`, nối agent dock, trả mục Agent về sidebar

**Ngày:** 2026-08-23
**Nhánh:** `main`
**Commit:** `21c1771`, `92da6f2`, `5559a6a`

---

## 1. Bối cảnh

Nhánh `tongduyan_3` conflict với `main`. Tôi resolve trên nhánh riêng
`merge-main-into-tongduyan_3` theo bốn ràng buộc An đặt ra:

1. Merge trên nhánh riêng lấy head từ `tongduyan_3`, không merge thẳng
2. Conflict nặng thì ưu tiên UI `tongduyan_3`
3. Từ vựng "candidate" tiếng Việt là **"ứng viên"**
4. Giữ nguyên cả 4 panel advisory của `main`
5. Log trong `.ai-log` **tuyệt đối không xoá phần việc người khác**

Song song, Hung Nguyen tự merge `tongduyan_3` vào `main` (`0860d93`,
21:49). Bản đó lên `origin/main` trước. An pull về rồi yêu cầu resolve
lại theo bản của tôi.

---

## 2. Bản merge của Hung mất gì

Hung resolve bằng cách mỗi file conflict lấy **nguyên một phía** — sáu
trên bảy file lấy phía `tongduyan_3`. UI của An sống, nhưng mọi thứ
`main` viết trong cùng file đó mất theo.

| Mất gì | Số lượng |
|---|---|
| 4 panel advisory trong `decisions/[id]/page.tsx` | 322 dòng |
| `FromPaperPanel` trong `candidates/page.tsx` | 1 panel |
| Test của main trong `candidates-page.test.tsx` | 311 dòng |
| Log `.ai-log/archive/2026-08-20.jsonl` | 855 dòng |
| Log `.ai-log/session.jsonl` | 288 dòng (thay nguyên file) |
| Chuẩn hoá từ vựng `vi.json` | 1732 key lệch vs `en` 1682 |

Bốn endpoint advisory vẫn sống trên API mà không màn hình nào gọi, vì
định nghĩa panel nằm ngay trong file bị thay.

`vi.json` còn 64 chuỗi tiếng Việt mang nguyên chữ Anh "candidate".

---

## 3. Đã làm

### 3.1 Resolve lại (`21c1771`)

Lấy từ `0aa38c5` (bản resolve của tôi) cho 7 file. **Không đụng**
`docker/Dockerfile.api` và `presentation/pitch_deck.pptx` — hai file của
Phạm Thái Sơn, đến sau merge, revert là xoá việc người khác.

Log không lấy một phía mà **union ba nguồn** (đĩa, bản của tôi, bản trên
main), sắp theo `ts`, chỉ gộp dòng trùng byte-identical:

```
archive/2026-08-20.jsonl  dia=1372 ban-toi=2227 tren-main=1372 -> 2227
archive/2026-08-23.jsonl  dia=279  ban-toi=427  tren-main=279  -> 427
session.jsonl             dia=162  ban-toi=378  tren-main=148  -> 540

mat cua dia = 0   mat cua ban-toi = 0   mat cua main = 0
```

### 3.2 Từ vựng: ghi đè quyết định của main

`origin/main` có test **cố ý cấm** từ "ứng viên", kèm lập luận: trong
tiếng Việt nó nghĩa là người xin việc hoặc người ra tranh cử. Họ chọn
"phương án".

An chọn ngược lại. Tôi **lật test chứ không lật từ** — đổi thành cấm
"phương án", sửa `topbar.test.tsx`, và ghi lý lẽ mới vào comment của
test. Đây là chỗ ghi đè quyết định có lý lẽ của người khác, cần bàn với
Hung khi có dịp.

Kết quả: `vi` 1682 key khớp hệt `en`, 0 chuỗi "phương án", 0 chuỗi
"candidate" (trừ tên field `candidate_id`/`candidate_a`).

### 3.3 Nối `AgentDock` vào agent thật (`92da6f2`)

Dock ship dưới dạng placeholder khoá ô nhập. Nhưng agent **đã chạy sẵn**
— `POST /agent/chat`, backend của Hung, 130 test pass — chỉ là sau khi
mục sidebar bị bỏ thì lối vào duy nhất là ô trên dashboard. Tức app có
một hộp chat chết ở mọi trang và một hộp chat sống sau một cái link.

Nối vào `lib/agent`. Quyết định trong lúc làm:

- **Chưa đăng nhập thì khoá ô nhập và nói lý do.** `authFetch` trả 401
  sau khi người ta đã gõ xong.
- **Đóng panel không huỷ request đang bay.** Chỉ panel unmount, state ở
  component; câu trả lời về lúc đang đóng vẫn còn khi mở lại. Muốn rút
  thì bấm Stop.
- **Cờ `deterministic` đọc từ response**, không gọi `/agent/capabilities`
  lúc mở — nếu gọi thì mỗi trang tốn một request dù không ai gõ.
- **Hiện `truncated` và `tool_errors`.** Câu trả lời hết lượt gọi công cụ
  trông y hệt câu trả lời xong xuôi nếu không nói ra.
- **Dock không nhận file.** Bài báo, nháp plugin, bảng quyền hạn ở
  `/agent`, có link ở cuối panel.

Thêm 8 key `agentDock.*`, sửa 2 key mô tả trạng thái "chưa nối".

### 3.4 Trả mục Agent về sidebar (`5559a6a`)

Về đúng slot cũ, đầu section `account`. Lý do đảo lại: dock và trang
**không phải một phòng** — dock trả lời tại chỗ, trang đọc bài báo, dựng
nháp plugin, công bố agent được phép làm gì.

---

## 4. Test

| Mốc | Test | Fail |
|---|---|---|
| `main` của Hung | 1819 | 18 |
| Sau khi resolve lại | 1860 | 19 |
| Sau khi nối dock + sidebar | **1876** | **18** |

18 fail còn lại **không cái nào mới**:

- **16** thiếu key i18n — tra cả bốn mốc (`base`, `tongduyan_3`, `main`
  trước merge, `main` bây giờ), không mốc nào từng có. An đã hoãn.
- **2** CRLF ở `deployments-page` và `simulate-page`.

`tsc --noEmit`: 7 lỗi, đều trong `candidates-page.test.tsx` của main
index đúng mấy key thiếu đó. Cùng gốc. Token ratchet pass.

---

## 5. Còn tồn

**5.1 — 18 key i18n của trang `/agent` chưa có.** Trang hiện chữ raw:

```
agent.placeholder   agent.boundaries   agent.attach       agent.stop
agent.cannotPlain   agent.canReadPlain agent.readPaper    agent.toolsUsed
agent.mock          agent.noTools      agent.tooBig       agent.truncated
agent.attachRemove  agent.attachedPlaceholder             agent.paperRegister
agent.toolErrors    plugin.build       plugin.buildNoStack
```

Cộng 13 key advisory nữa. Phần của Hung, chưa động theo ý An.

**5.2 — CRLF trong 2 test tôi viết.** Chúng đọc file nguồn rồi
`toContain` chuỗi nhiều dòng viết bằng `\n`; `core.autocrlf=true` và repo
không có `.gitattributes`. Trước pass chỉ vì file do tôi tự ghi LF. Máy
Windows nào clone mới cũng gãy. Chưa vá.

**5.3 — `pandas`/`pyarrow` chưa khai báo.** `tests/test_trace_review.py`
của main import nhưng không có trong `requirements.txt`.

**5.4 — Dock và trang `/agent` là hai luồng hội thoại riêng.** Cùng
backend nhưng transcript nằm ở state từng component. An đã nêu, sẽ bàn
tiếp về UI.

**5.5 — Chưa push.** Ba commit đang ở local `main`.
