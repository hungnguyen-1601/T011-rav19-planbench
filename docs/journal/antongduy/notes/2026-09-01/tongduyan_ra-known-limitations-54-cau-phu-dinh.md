# Rà `KNOWN_LIMITATIONS.md`: 54 câu phủ định, bốn câu đã sai

Ngày 2026-09-01 · khảo sát, có sửa file được rà

README §9.5 trỏ vào `KNOWN_LIMITATIONS.md` như "danh sách đầy đủ, cập
nhật liên tục". File 1702 dòng, và đợt rà docs 31-08 chỉ kiểm đường dẫn
nó trích chứ không kiểm nội dung. Một README bảo lãnh cho thứ chưa ai
kiểm thì lời bảo lãnh đó là phần yếu nhất của cả README.

---

## Rà theo trục nào

Không rà tuần tự 1702 dòng. Rà theo **loại câu dễ mục nát nhất**: câu
khẳng định một thứ **không tồn tại**. Một câu "hệ chỉ hỗ trợ 2D" sai đi
thì cần cả một quyết định kiến trúc; một câu "chưa có endpoint X" sai đi
chỉ cần ai đó viết endpoint X vào tuần sau và không quay lại sửa dòng
này. Loại thứ hai là loại mục nát trong im lặng.

Lọc bằng regex trên `chưa có|chưa hỗ trợ|không hỗ trợ|không có
endpoint|...`: **54 câu**. Kiểm từng câu với code.

## Bốn câu đã sai

| Mục | Câu cũ | Bằng chứng ngược lại |
|---|---|---|
| 48 | "Chưa có endpoint model registry" | `routers/models.py`: 6 route (`GET /models`, `POST /models/upload`, `GET/PATCH/DELETE /models/{id}`, `POST /models/{id}/validate`) + trang **Kho mô hình** |
| 89 | "Backend lưu và trả về đầy đủ" (lịch sử hội thoại) | `/agent/chat` **stateless**, không lưu transcript nào |
| 47 | "trang replay chưa nối vào `obstacleSnapshots`" | `TraceViewer.tsx:159` dựng vật cản từ `trace.dynamic_obstacles` |
| 111 · 125 · 146 | neo vào "trang leaderboard" | Trang đó không còn trong `apps/web/src/app/`; route `GET /leaderboard` ở `library.py:267` thì còn |

**Mục 48 và 89 đáng chú ý hơn hai mục kia**, vì cả hai đều bị chính file
này bác bỏ ở chỗ khác:

- Mục 48 nói chưa có API model registry, trong khi cùng file có hẳn một
  mục lớn *"Model Registry và trợ lý hội thoại"* mô tả kỹ phần bảo mật
  của đường upload đó.
- Mục 89 nói backend **lưu** hội thoại, mục 49 nói mỗi lượt độc lập và
  không lưu gì. Hai câu về cùng một hệ thống, cách nhau 380 dòng.

Mục 89 sai theo hướng nguy hiểm nhất trong bốn: nó khẳng định hệ thống
**đang lưu** nội dung người dùng gõ vào. Ai đọc file này để trả lời một
câu hỏi về dữ liệu cá nhân sẽ trả lời sai.

## Đã kiểm và vẫn đúng

Origin xoay bị từ chối (`map.py:51`) · DWA không lùi
(`allow_reverse=False`) · không có refresh token (`routers/auth.py`) ·
không có `jsdom` (`vitest.config.ts:20` nói thẳng đó là chủ ý) · chưa có
adapter `MonolithicPolicy` (`candidates.py:255`) · `average_rank_score`
tính được nhưng không ai gọi · không có xuất PDF · không có retry lúc mở
database · đổi nickname chỉ có ở bước onboarding (`PUT
/users/me/nickname` có, nút bấm thì chỉ ở `welcome`).

## Đã sửa gì trong file

Không xoá mục nào. File này có một quy ước sẵn - gạch ngang mục cũ rồi
viết vì sao nó hết - và quy ước đó đúng: "chỗ này từng hỏng như thế nào"
có giá trị đúng bằng "chỗ này còn hỏng không". Nên:

1. **Khối đầu file**: nói thẳng đây là chồng lớp trầm tích chứ không phải
   ảnh chụp, và một mục "chưa có X" không đảm bảo hôm nay vẫn chưa có X.
2. **Mục "Đợt rà 2026-09-01"** ngay sau đó: bảng bốn chỗ sai, danh sách
   những chỗ đã kiểm và vẫn đúng, và **khai rõ cái chưa rà**.
3. **Sửa tại chỗ** mục 48, 89, 47 theo đúng quy ước gạch ngang.
4. Khai luôn **M1–M13 là từ vựng đã chết** từ đợt chuyển hướng 08-08 -
   giữ tiêu đề vì các mục trích lẫn nhau theo số, nhưng đừng đọc như lộ
   trình.

`README.md` §9.5 và `docs/03-gaps.md` cập nhật theo.

## Cái chưa rà, nói trước

**Phần số đo.** Đợt này chỉ kiểm những câu khẳng định một thứ *có hay
không có trong code* - loại kiểm được bằng cách mở file ra đọc. Mục nào
trích một con số ("đo được 0.42", "chậm 3×") thì con số đó chưa ai chạy
lại. Đó là một đợt rà khác, và nó tốn máy chứ không tốn mắt.

**Phần suy luận cũng chưa rà.** Vài mục dài giải thích *vì sao* một hạn
chế tồn tại. Lập luận có thể vẫn đúng trong khi tiền đề đã đổi, và loại
sai đó không lộ ra bằng grep.
