# Frontend (M3 + M9)

`apps/web` — Next.js 15 + React 19 + TypeScript. Nguyên tắc xuyên suốt:
**UI chỉ render, không tính toán.** Không có mảnh logic simulator nào ở
client; mọi metric, mọi phán quyết đều do backend tính và UI chỉ hiển
thị. Nhờ vậy không bao giờ có chuyện số trên màn hình lệch số trong
report.

## Trang

| Route | Milestone | Vai trò |
|---|---|---|
| `/` | M3 | Dashboard: health, maps, simulation gần đây |
| `/maps`, `/maps/[id]` | M3 | Map editor Canvas 2D |
| `/library` | **M9** | Thư viện scenario theo thứ tự curriculum + import + preview 2.5D |
| `/simulate` | M3 | Chạy live qua WebSocket |
| `/benchmarks` | M4 | Tạo benchmark, danh sách |
| `/benchmarks/[id]` | M4 + M9 + **M11** | Run / Accept của chủ sở hữu, **send for review**, so sánh, replay (top-down / 2.5D), failure analysis, job progress |
| `/leaderboard` | **M9** | Xếp hạng, nhóm theo `conditions_checksum` |
| `/algorithms` | **M9** | Registry stack: benchmarkable, config bắt buộc |
| `/agent` | **M9** | Agent console (M8): chat, mission, evidence, report |
| `/login` | M4 + **M11** | Nút Google / GitHub (render từ `/auth/providers`), dev login khi được bật |
| `/auth/callback` | **M11** | Đổi code dùng một lần lấy session, rồi `router.replace` |
| `/welcome` | **M11** | Chọn nickname lần đầu, kiểm tra trùng theo từng ký tự (debounce 250 ms) |
| `/reviews` | **M11** | Review Inbox + Sent: approve, reject, comment, cancel |

## 2.5D

"2.5D" đúng theo nghĩa spec dùng: thế giới **thật sự phẳng**
(x, y, theta), chiều thứ ba chỉ để trình bày — tường được đùn lên một
độ cao cố định để đọc occupancy như khối thay vì như màu. Không có đại
lượng mô phỏng nào suy ra từ độ cao, và không có gì phản hồi lại vật lý.

Tách làm hai phần:

- **`src/lib/scene25d.ts`** — hình học thuần: phép chiếu trực giao, thứ
  tự vẽ, đùn tường, marker robot. Đây là phần dễ sai một cách âm thầm
  nên nó là phần được unit-test (23 test).
- **`src/components/Scene25D.tsx`** — renderer: chỉ chọn màu và nét vẽ.

Phép chiếu:

```
screen.x =  (x - y) * cos(azimuth) * scale
screen.y = -(x + y) * sin(elevation) * scale - z * scale
```

**Thứ tự vẽ dùng `x + y`, không dùng `sy`.** Dưới phép chiếu này một ô
chỉ bị che bởi ô có `x + y` lớn hơn, nên tổng đó sắp thứ tự toàn phần
cho cả cảnh. Sắp theo `sy` sẽ sai: mặt trên của một bức tường cao có
`sy` nhỏ nhưng vẫn thuộc phía sau thứ đứng trước nó.

**Ô UNKNOWN vẽ phẳng, không đùn lên.** Unknown là *thiếu thông tin*;
đùn nó lên sẽ đọc thành vật cản mà thực ra không biết là có.

**Renderer là Canvas 2D.** Với một occupancy grid
đùn lên, cảnh là vài nghìn quad lồi có thứ tự độ sâu toàn phần —
painter's algorithm xử lý *chính xác*, không cần depth buffer, và không
thêm dependency nào. Quan trọng hơn: `Scene25D.tsx` là file **duy nhất**
biết mình đang vẽ bằng gì. Đổi sang WebGL/React Three Fiber về sau chỉ
thay file đó; `scene25d.ts` và toàn bộ test của nó không đổi.

Spec liệt kê Three.js trong tech stack. Đã cân nhắc và **quyết định
giữ Canvas 2D** (2026-07-30, người dùng chọn). Đánh đổi đã chấp nhận:
không occlusion culling, không ánh sáng/bóng đổ. Xem
`KNOWN_LIMITATIONS.md` mục 44–45.

## Component dùng lại

| Component | Vai trò |
|---|---|
| `MapCanvas` | Top-down Canvas 2D: map, plan, trajectory, robot |
| `Scene25D` | Cùng dữ liệu, nhìn nghiêng, có slider rotate/tilt/wall-height |
| `FailureFindings` | Finding + evidence + **confidence hiển thị nổi** |
| `JobProgress` | Poll job khi đang chạy, dừng poll khi kết thúc, cancel |
| `MetricsPanel` | Metric của một episode |
| `SessionBar` | Avatar + nickname + email, badge Review Inbox, logout |
| `SendForReview` | Modal: nickname (autocomplete), stage, lời nhắn |

`FailureFindings` cố ý làm `confidence` nổi bật: một finding `low` là
**giả thuyết** khớp dữ liệu, không phải kết luận, và người đọc không
thấy điều đó sẽ tin quá mức.

`JobProgress` ngừng poll ngay khi job vào trạng thái kết thúc — một
timer cứ chạy vào job đã xong chỉ là tải vô ích.

## Leaderboard: vì sao không phải một bảng phẳng

Hai dòng chỉ có nghĩa khi cạnh nhau nếu chúng cùng `conditions_checksum`.
UI vì thế **luôn** nhóm, không bao giờ render một bảng duy nhất — làm
thế là mời người đọc so sánh xuyên điều kiện, đúng thứ mà fairness
record tồn tại để ngăn.

Khi bỏ tick "accepted results only", trang hiện cảnh báo đỏ: đó là kết
quả chưa ai nhận, không được publish thành kết luận.

## Đăng nhập và quyền (M11)

Trang login **không** có cờ build-time nào cả: nó gọi `/auth/providers`
và chỉ vẽ nút mà server thật sự bật. Deployment chưa cấu hình Google thì
không có nút Google — thay vì có nút dẫn tới trang lỗi.

Browser giữ đúng hai thứ trong `sessionStorage`: token PlanBench và
profile để hiển thị. **Không** giữ access token của provider, không giữ
client id, không giữ secret. Callback trả về một code dùng một lần chứ
không phải JWT, nên token không nằm lại trong history hay Referer.

`canRun` / `canAcceptResult` trong `lib/reviews.ts` quyết định **hiện**
nút, không quyết định **cho phép**. Backend kiểm tra độc lập trên mọi
request, và mỗi trường hợp trong hai hàm đó đều có một test API tương
ứng chứng minh server tự từ chối. Ẩn nút chỉ để người dùng không bấm vào
thứ chắc chắn sẽ lỗi.

## Agent console

Ba điểm cẩn thận, vì làm sai sẽ vô hiệu hoá bảo đảm mà backend cưỡng chế:

1. **Luôn hiện provider nào trả lời.** `deterministic: true` nghĩa là câu
   trả lời khớp từ khóa offline, không phải model viết. Người đọc không
   bao giờ phải đoán.
2. **Mission bị từ chối render thành refusal kèm lý do**, không phải lỗi
   và không phải kết quả rỗng.
3. **Không có nút approve ở đây.** Agent không tự mở gate được, trang
   này cũng vậy. Chủ sở hữu mở gate bằng nút **Run** ở trang benchmark
   detail — được ghi vào audit trail là `self_approved`, khác với
   `approve` của người thứ hai, nên đọc lịch sử luôn phân biệt được.

## Chạy

```bash
# Terminal 1 — backend
PYTHONPATH="packages/schemas:packages/planning:packages/metrics:\
packages/benchmark:services/simulator:services/tracking:\
services/agent_service:ml:apps/api" \
  .venv/bin/uvicorn planbench_api.main:app --port 8000

# Terminal 2 — frontend
cd apps/web && npm run dev          # http://localhost:3000
```

`NEXT_PUBLIC_API_URL` trỏ tới backend (mặc định `http://localhost:8000`).

```bash
cd apps/web
npm run typecheck    # tsc --noEmit
npm test             # vitest
npm run build        # next build
```

## Nếu về sau muốn đổi sang Three.js

```bash
cd apps/web && npm install three @react-three/fiber @types/three
```

Rồi viết lại **một** file `src/components/Scene25D.tsx` để tiêu thụ
`Scene25D` từ `scene25d.ts` (facets → mesh/instanced geometry).
`scene25d.ts` và 23 test của nó không cần sửa. Đây là lý do phần hình
học được tách ra ngay từ đầu.
