# Trả nợ kỹ thuật — đợt 13-08

**Kiểm kê nguồn:** [`notes/2026-08-13/tongduyan_no-ky-thuat-ton-dong.md`](../../notes/2026-08-13/tongduyan_no-ky-thuat-ton-dong.md)
**D1** (test chống trôi lược đồ) nằm ở [report form, mục 9](tongduyan_khai-deployment-bang-form.md)
vì nó trả nợ do chính đợt form tạo ra. Từ đây là các mục còn lại.

---

## D2 — hai vệt đỏ thường trực

Tôi đã gọi hai test này là *"lỗi có sẵn từ trước, không liên quan"* **ba lần liên tiếp** mà
không chẩn đoán. Chẩn đoán ra thì chúng là **hai nguyên nhân khác hẳn nhau**, và cái thứ hai
không phải lỗi test.

### D2a. `dashboard-page` — dấu phân cách Windows

```
AssertionError: expected [ '\system\page.tsx' ] to deeply equal [ '/system/page.tsx' ]
```

`join()` cho `src\app\system\page.tsx` trên Windows, so với chuỗi POSIX viết tay thì trượt vì
một lý do **không liên quan gì tới điều đang được khẳng định** (rằng `API_BASE` chỉ xuất hiện ở
đúng một trang). Test này đỏ trên Windows **từ ngày nó được viết**.

Sửa: một hàm `asRoute()` chuẩn hoá `sep` về `/`. Khẳng định giữ nguyên từng chữ.

### D2b. `assistant-page` — **27 test chưa từng chạy**

Đây mới là chỗ đáng kể, và nó không phải lỗi Windows.

```
Error: ENOENT: no such file or directory, open '…/apps/web/src/app/models/page.tsx'
  ❯ src/app/__tests__/assistant-page.test.tsx:134:20
```

`describe("the model registry page")` đọc file **ở mức module**. File không có ⇒ đọc ném lúc
collect ⇒ vitest báo **một suite hỏng** và **kéo theo toàn bộ 27 test còn lại trong file**.

Chúng chưa bao giờ chạy. Suite web vẫn báo "xanh trừ hai lỗi có sẵn", và hai chữ "có sẵn" đã che
27 test suốt thời gian đó.

### D2c. Và vì sao file đó không có: **`/models` chưa từng tồn tại**

```
$ git log --all -- apps/web/src/app/models/page.tsx
(không có gì)
$ grep -n models apps/web/src/lib/navigation.ts
46:  { href: "/models", labelKey: "nav.models", icon: "library", session: true },
```

Trang **chưa từng nằm trong lịch sử git** — không phải bị xoá, mà là **chưa bao giờ được xây**.
Trong khi đó sidebar đã link tới nó từ đầu, và backend thì **đã xong** (`routers/models.py`,
`model_registry.py`).

Nghĩa là: **người dùng bấm vào mục Models trong sidebar sẽ nhận 404.** Đây là bug sản phẩm, và
nó nấp sau một lỗi collect suốt thời gian qua.

Quét toàn bộ 17 href trong `navigation.ts`: **đúng một** link chết, là `/models`.

### Sửa thế nào — **dev chốt: `/models` là việc của người khác, không can thiệp**

Bản nháp đầu tiên của tôi đi xa hơn thế: chuyển ba khẳng định thành một mục `MISSING_PAGES` kèm
lý do, và **thêm một test quét mọi href trong sidebar phải có trang**.

Dev bác, và bác đúng. Cái test nav ấy **giám sát khu vực của người khác**: nó biến "sidebar có
link tới trang chưa xây" thành một điều kiện mà workstream khác phải thoả mãn, trong khi quyết
định *xây trang hay gỡ link* không thuộc về đợt việc này. Một test như thế đỏ lên là đỏ vào mặt
người không gây ra nó.

**Đã làm cuối cùng, đúng phạm vi:**

- Bỏ khối `/models` khỏi file test. Không `describe.skip` — một test bị tắt trông như một test
  đang chạy, và đó là mùi hoàn-thành-giả.
- Không thêm test nav nào. File này **không khẳng định gì** về `/models`, kể cả chuyện sidebar
  có nên link tới nó hay không.
- Một comment tại chỗ nói khối đó từng ở đây, vì sao nó làm hỏng collect, và **đặc tả ba yêu
  cầu chuyển sang report này** cho người sẽ xây trang.

Ba yêu cầu đó, giữ lại nguyên vẹn ở đây:

> Trang model registry, khi được xây, phải: **giải thích PPO là gì** (`models.whatIsPpo`) ·
> **có empty state chứ không phải lỗi** khi chưa upload gì (`models.empty.title`) · **không bao
> giờ hiện vị trí lưu trữ** (không `storage_key`, không `model_path`) — cái cuối là toàn bộ lý
> do có một registry.

Backend đã sẵn sàng: `routers/models.py`, `model_registry.py`.

---

## Kết quả

| | trước D2 | sau D2 |
|---|---:|---:|
| Test file web | 29/31 pass, **1 fail + 1 không collect được** | **31/31** |
| Test web | 587 passed, 1 failed | **613 passed, 0 failed** |

**Lần đầu suite web xanh hoàn toàn** trong cả loạt việc này. +26 test so với trước, và **không
một cái nào là test mới** — chúng là test đã có từ lâu, giờ mới thực sự chạy. Đây là kiểu "tăng
số test" đáng giá nhất: không viết thêm gì, chỉ thôi che.

`tsc --noEmit` sạch. Chưa chạy full suite backend — dev chốt để sau.

---

## Còn lại trong hàng đợi

- **A4** — sinh lại map công bằng; `tests/test_fairness.py:310` đang **skip** vì thiếu file, nên
  bộ test công bằng không bảo vệ gì cả.
- **`/models` — đóng, không phải việc của đợt này.** Dev chốt 13-08: phần việc của người khác,
  để nguyên. Ba yêu cầu của trang ghi ở mục D2c trên cho người sẽ xây. Ghi lại ở đây một điều
  duy nhất, không phải để đòi ai làm gì mà để nó không rơi: **sidebar hiện vẫn dẫn tới một
  trang không tồn tại**, và người dùng bấm vào sẽ nhận 404.
- Phần còn lại theo thứ tự trong bản kiểm kê.
