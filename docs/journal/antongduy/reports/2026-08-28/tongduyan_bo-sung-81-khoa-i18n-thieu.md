# Bổ sung 81 khoá i18n chưa từng tồn tại

Ngày 2026-08-28 · **đã sửa code**, chưa commit

Phát hiện lúc An thử luồng duyệt run: trang decision hiện thẳng tên khoá
lên màn hình — `OUTCOME.TITLE`, `advice.load`, `critique.subtitle`,
`reportAdvice.hint`.

---

## 1. Nguyên nhân

`translate()` fallback `?? key` khi không tra được. Không phải lỗi
fallback — fallback đúng như thiết kế. Lỗi là **chưa ai thêm khoá**.

Ban đầu em đếm 10 khoá An nhìn thấy trên ảnh. Quét toàn bộ
`t("...")` trong `apps/web/src` thì ra **73**, cộng 8 khoá dựng động mà
regex không bắt được (`advice.${severity}`, `critique.severity.*`,
`critique.source.*`) — **81**.

Không phải rải rác. Là **cả sáu vùng chức năng** chưa có dòng dịch nào:

| Vùng | Khoá | Màn hình |
|---|---|---|
| `advice.*` | 15 | bảng khuyến nghị dùng chung ở preflight, cổng, báo cáo |
| `critique.*` | 18 | panel phản biện kết quả |
| `paper.*` | 30 | đọc phương pháp từ bài báo |
| `plugin.*` | 8 | bản nháp plugin do model dựng |
| `preflight.*` | 4 | nút kiểm trước khi chạy |
| `outcome.*`, `reportAdvice.*` | 4 | vì sao episode hỏng · trước khi trích dẫn |

Kiểm trên `main`: **thiếu y hệt**. Không do nhánh role sinh ra. Trên
`main` có `advice.title`, `advice.case.*`, `advice.why.*` — tức là ai đó
đổi cách đặt tên khoá ở component mà không mang từ điển theo.

---

## 2. Đã làm

Thêm 81 khoá vào **cả** `en.json` lẫn `vi.json`. Viết bằng cách đọc từng
component chứ không dịch máy từ tên khoá, nên chữ nói đúng việc panel đó
làm. Ví dụ `advice.hint` không phải "gợi ý" mà là *"Chưa kiểm gì. Mục
này đọc bảng cổng rồi nói cái gì được phép triển khai — và cái gì không
được phép khẳng định."*

Script có **cổng chặn ghi đè**: khẳng định khoá mới chưa tồn tại trước
khi ghi. Cổng đó bắt được một cái — `plugin.build` đã có sẵn với nội
dung *"Draft a plugin from this paper"*. Em bỏ bản của mình, giữ bản
đang dùng. Không có cổng đó thì em đã lặng lẽ đổi chữ trên một nút đang
chạy.

---

## 3. Nghiệm thu

```
khoá còn thiếu sau khi sửa : 0   (quét lại bằng chính script đã đếm 73)
en.json / vi.json          : 2080 khoá mỗi bên, tập khoá trùng khít
npx tsc --noEmit           : sạch — kể cả 3 lỗi paper.* trước đây
```

**Test: 28 → 17 đỏ, 0 regression.** So từng test một với nền dựng ở
worktree tại `f10fb1a`:

```
baseline failures: 28   now: 17
FIXED by the keys: 11
NEW (regressions):  0
```

11 test đỏ mà các báo cáo trước ghi là "có sẵn, không sửa" thì **chính
là lỗi này** — `advisory-ui.test.tsx` 8 và một phần `decisions-page`,
`candidates-page`. Em đã xếp chúng vào loại "khoá chưa từng tồn tại" và
dừng ở đó; đúng chẩn đoán, nhưng đáng lẽ phải sửa thay vì ghi nhận.

17 cái còn lại vẫn có sẵn ở `f10fb1a`, ngoài phạm vi việc này: token CSS
(`rem`), `agent-dock` đọc file em không đụng, và mấy test bám ký tự `×`
trong JSX.

Ba lỗi `paper.*` mà `tsc` báo suốt các phiên trước cũng hết — chúng là
test index vào kiểu của `en.json`, và giờ khoá đã có thật.

---

## 4. Chưa làm

**Chưa commit.**

**Chưa nhìn bằng mắt trên trình duyệt.** Em chứng minh được khoá tra ra
chữ, không chứng minh được chữ nằm vừa khung. Vài câu tiếng Việt dài hơn
bản tiếng Anh — `advice.hint`, `critique.subtitle`, `paper.subtitle` —
An liếc qua giúp xem có tràn không.

**Chưa rà chất lượng bản dịch cùng An.** 81 chuỗi là do em viết. Chỗ nào
An thấy sai giọng hoặc sai thuật ngữ thì sửa thẳng trong `vi.json`, một
khoá một dòng.

---

## 5. File đã đụng

| File | Việc |
|---|---|
| `apps/web/src/lib/i18n/locales/en.json` | +81 khoá |
| `apps/web/src/lib/i18n/locales/vi.json` | +81 khoá |

Không đụng component nào — tên khoá component đang gọi đều giữ nguyên.
