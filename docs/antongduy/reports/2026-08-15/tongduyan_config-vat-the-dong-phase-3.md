# Phase 3 — đóng phần test còn lại, và nói rõ phần không đóng được

> Plan: `docs/antongduy/plans/2026-08-15/config-vat-the-dong-tren-form-deployment.md` (v5, Phase 3).
> Ngày làm: 2026-08-15. Nhánh: `tongduyan_plannerselector`. **Chưa commit.**

## Trạng thái vào Phase 3

Phần lớn Phase 3 đã làm xen kẽ trong Phase 2b và bốn vòng review: test
hàm thuần (`traffic.test.ts`, 58 ca), test thứ tự đan xen
(`sequencer.test.ts`, 8 ca), thay guard cũ đã hết đúng
(`TestTrafficIsAuthorable`), dry-run API test, test tích hợp adapter.
Còn lại **hai lỗ hổng**, và chúng khác loại nhau.

## Lỗ hổng 1 — component chưa từng được render lần nào

Mọi thứ về TrafficEditor tới giờ được kiểm bằng **dữ liệu**
(`lib/traffic`) hoặc bằng **tìm chuỗi trong mã nguồn**. Không cái nào
phát hiện được một component ném lỗi ngay lần vẽ đầu tiên: một `switch`
qua bốn luật chuyển động, một hint bốn nhánh, hơn chục key i18n — chưa
dòng nào từng chạy.

Đã thêm `apps/web/src/components/__tests__/traffic-editor.test.tsx`
(**22 ca**), dùng `renderToStaticMarkup` như phần còn lại của suite web:

- khối rỗng nói "chưa khai vật cản" thay vì im lặng;
- đủ **bốn** luật trong picker, và luật đang dùng được đánh dấu `selected`;
- **mỗi luật chỉ hiện field của chính nó** — bảng 4 ca kiểm cả mặt có
  lẫn mặt không có (periodic không có ô speed, waypoint không có period);
- `sudden_stop` **không** có nút đặt điểm cuối;
- bốn trạng thái head start: nút "Suggest (45s)" đúng con số của
  deployment đang ship, câu cho random walk ("Zero is legal here"), câu
  cho lộ trình một lần, câu cho input chưa đủ;
- hai `seed_offset` hiện hai nhãn khác nhau;
- lỗi server: path `environment` hiện ở đầu khối, path sâu hiện **cạnh
  đúng row**, path lạ vẫn hiện chứ không bị lọc mất, và không có gì khi
  lần kiểm cuối sạch;
- `disabled` lan xuống **mọi** control;
- nút placement sáng đúng field đang chờ click.

**Nó bắt được một defect thật ngay lần chạy đầu.** React cảnh báo
`Received NaN for the value attribute` khi một ô số đang gõ dở: `value`
nhận `NaN`, hiển thị thành ô trống *kèm cảnh báo* — nghĩa là không phân
biệt được với ô chưa điền. Sửa: coi giá trị không hữu hạn là chuỗi rỗng.
Không "sửa hộ" số cho người dùng, vì cái gì hợp lệ là việc của server;
một form âm thầm thay `NaN` bằng con số hợp lý là form nộp một
deployment không ai gõ.

## Lỗ hổng 2 — click và canvas, vẫn chưa đóng được

`vitest` chạy Node, không jsdom, không Testing Library
(`apps/web/vitest.config.ts:15-18`), và **không có playwright** trong
repo. Nên bốn hành vi sau **chưa có test nào**, ở bất kỳ tầng nào:

1. click lên canvas gom waypoint;
2. hai click cho `sudden_stop` ra heading;
3. preview vẽ đúng vị trí ở ba nguồn map;
4. khung 2.5D hiển thị traffic mà không sửa được.

Phần *quyết định* đằng sau chúng đã tách ra và test được
(`placeOnMotion`, `previewRequestOf`, `snapshotsOf`, `createSequencer`).
Phần *nối dây tới con chuột* thì không.

Hai đường đóng, cả hai cần An quyết:

- **Thêm `jsdom` + `@testing-library/react`** — một dependency, và mở
  ra cả lớp test hành vi (bấm Preview rồi sửa field trong lúc chờ, đúng
  lớp lỗi bốn vòng review vừa bắt).
- **Hoặc giữ checklist tay** dưới đây và chấp nhận nó là kiểm thủ công.

## Checklist thủ công — chưa ai chạy

Tôi **không chạy được** phần này: không có công cụ điều khiển trình
duyệt trong môi trường. Ghi ra để An (hoặc bất kỳ ai) chạy, mỗi mục là
một câu hỏi có/không:

| # | Thao tác | Kỳ vọng |
|---|---|---|
| 1 | Mở `/deployments`, tab form, bấm "Add an obstacle" | Một row hiện ra, `seed_time_offset` đã có sẵn số > 0 |
| 2 | Bấm "Add waypoints" rồi click 3 điểm trên bản đồ | Đếm waypoint tăng đúng 3, **không** tăng vọt |
| 3 | Giữ chuột và **kéo** ngang bản đồ khi đang ở mode waypoint | Đếm waypoint **không đổi** (kéo chỉ thuộc về start/goal) |
| 4 | Bấm "Place the start" rồi kéo | Start di chuyển mượt theo chuột |
| 5 | Đổi kind sang "Straight, then stops", click 2 điểm | Điểm 1 là start; điểm 2 **chỉ** đổi ô Heading, không tạo điểm mới |
| 6 | Đổi kind qua lại waypoint ↔ periodic | Field cũ biến mất hẳn; tab YAML không còn `waypoints` trong motion periodic |
| 7 | Bấm Preview với map thư viện | Vật cản vẽ lên canvas ở vị trí ứng với t |
| 8 | Lặp mục 7 với map từ store và map vẽ tay | Cả hai đều vẽ được |
| 9 | Đổi ô Time thành 40 | Ảnh cũ **biến mất ngay**, không chờ tới lúc bấm Preview |
| 10 | Bấm Preview rồi sửa ngay tốc độ vật cản trong lúc chờ | Ảnh cũ **không** quay lại vẽ đè |
| 11 | Chọn map A rồi chọn map B thật nhanh | Kết thúc ở B, kể cả khi A trả lời chậm hơn |
| 12 | Chọn map A rồi chọn option rỗng ngay | Không có map nào bị commit |
| 13 | Đặt hai vật cản cùng độ dài tên, cùng `seed_offset`, bấm "Check with the server" | Lỗi hiện ở **đầu khối traffic**, nói về clock key |
| 14 | Đặt radius âm, bấm Check | Lỗi hiện **cạnh đúng row**, có chữ `radius:` |
| 15 | Đặt start pose vào trong tường rồi bấm Preview | Khối "will not run as it stands" hiện, liệt kê lý do |
| 16 | Chuyển sang khung 2.5D | Traffic vẽ được; không đặt được điểm ở khung này |
| 17 | Bấm Check rồi thử gõ vào một ô bất kỳ | Mọi input khoá trong lúc đang kiểm |
| 18 | Khai đủ và bấm "File it" | Nộp thành công; sửa một ô rồi nộp lại cùng id → bị từ chối 409 |

Mục 10, 11, 12 là ba con race bốn vòng review vừa bắt — chúng có test ở
tầng `sequencer`, nhưng đường từ tầng đó tới con chuột thì chỉ checklist
này chạm được.

## Bằng chứng

| Kiểm | Kết quả |
|---|---|
| `npx vitest run traffic-editor.test.tsx` | **22 passed** (bắt 1 defect ở lần chạy đầu, đã sửa) |
| `npm run typecheck` | sạch |
| `npm run test` (web) | **766 passed / 35 file** |
| `npm run build` (Next production build) | **thành công** — biên dịch 4.4 s, sinh tĩnh 17/17 trang, `/deployments` 12.3 kB |

Bản build production là phép kiểm mà unit test không thay được: nó chạy
lint, kiểm kiểu ở chế độ build, và **sinh thật cả 17 trang** — một lỗi
chỉ xuất hiện lúc server-render trang `/deployments` sẽ đỏ ở đây chứ
không đỏ ở `vitest`.
