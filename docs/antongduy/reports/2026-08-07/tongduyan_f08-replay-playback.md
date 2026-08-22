# Báo cáo — F08: Playback cho replay episode đã lưu (play/pause + timeline)

> **Ngày:** 2026-08-07
> **Nguồn:** yêu cầu trực tiếp của user sau khi chạy thử ("chỉ nhìn thấy maps chứ không chạy được").
> **Quan hệ với plan 05-08:** đây là mục **4.3 (F08)** của Đợt 4. User yêu cầu
> trực tiếp nên làm riêng phần này; **replanning (4.1) và map loader (4.2)
> không đụng tới**, vẫn chờ approve.
> **Nhánh:** `integrate-tongduyan`

---

## 1. Xác nhận trước: không phải user dùng sai

Replay episode đã lưu đúng là **ảnh tĩnh**: vẽ map + toàn bộ đường đi +
robot đứng ở frame cuối. Không có nút play nào để bấm. Đây là giới hạn
đã ghi ở KNOWN_LIMITATIONS #46 từ trước, plan xếp vào Đợt 4.3.

## 2. Cái đã làm

### 2.1. Hook `useTrajectoryPlayback` (`apps/web/src/lib/useTrajectoryPlayback.ts`)

Playback thuần client trên trajectory đã lưu — mọi frame đã nằm sẵn
trong payload `/episodes/{id}/replay`, không cần backend mới.

- Đồng hồ chạy bằng `requestAnimationFrame`: `playhead += Δt_thực × speed`,
  clamp tại duration.
- **Không nội suy giữa các frame**: robot luôn được vẽ ở sample cuối
  cùng có `time ≤ playhead` (binary search) — hình chỉ hiển thị trạng
  thái mà simulator thực sự sinh ra, đúng nguyên tắc "UI không tự tính
  simulation" của repo.
- Mở replay mới là reset đồng hồ (không mang playhead của run cũ sang
  map của run mới).
- Trạng thái ban đầu: **đứng ở cuối, pause** — giữ nguyên lượng thông
  tin của ảnh tĩnh cũ (nhìn phát biết kết cục); bấm Play từ cuối tự
  quay về 0 chạy lại.
- **Tách riêng khỏi `useEpisodeStream`** (WebSocket của `/simulate`),
  đúng plan 4.3 "không ảnh hưởng live simulation": bug ở replay không
  có đường chạm vào live sim. Test khẳng định `/simulate` không import
  hook mới.

### 2.2. Panel replay của benchmark (`apps/web/src/app/benchmarks/[id]/page.tsx`)

Tách thành component `ReplayViewer`, thêm dưới canvas:

- Nút **Play / Pause / Restart** (nhãn dùng lại i18n của `/simulate`).
- **Scrubber** `<input type="range">` 0 → duration, bước 0.05 s, kéo
  được cả khi đang phát.
- **Chọn tốc độ** 0.25× / 0.5× / 1× / 2× / 4× / 8× — cùng dải với
  `/simulate`.
- Đồng hồ `playhead / duration` (giây mô phỏng).
- **Trajectory vẽ tới playhead** — không vẽ "tương lai" dưới chân robot
  đang đi giữa chừng.
- **Vật cản động vẽ theo thời gian**: mỗi `TrajectoryPoint` đã mang
  snapshot ground-truth vị trí vật cản (ghi cho replay, planner không
  bao giờ thấy — docstring schema nói rõ); giờ frame hiện tại của
  playhead được đổ vào `MapCanvas.dynamicObstacles` kèm nhãn `t = …s`.
- **Điểm va chạm đánh dấu trên timeline**: chấm đỏ tại thời điểm va
  chạm (tooltip ghi giây), X đỏ trên map chỉ hiện khi playhead chạy tới
  thời điểm đó.
- View 2.5D cũng chạy theo playhead (robot + trajectory); vật cản động
  trong 2.5D thì chưa — `Scene25D` chưa có renderer cho nó, ghi ở
  KNOWN_LIMITATIONS #47.

### 2.3. Types

`TrajectoryPoint` (frontend) thêm `obstacles?: {name,x,y,radius}[]` —
optional vì payload lưu trước khi engine ghi snapshot không có field
này; thiếu thì đơn giản không vẽ vật cản, không lỗi.

## 3. File thay đổi

| File | Thay đổi |
|---|---|
| `apps/web/src/lib/useTrajectoryPlayback.ts` | **mới** — hook playback |
| `apps/web/src/app/benchmarks/[id]/page.tsx` | `ReplayViewer` + controls, bỏ wiring "robot = frame cuối" |
| `apps/web/src/lib/types.ts` | `TrajectoryPoint.obstacles?` |
| `apps/web/src/lib/i18n/locales/{en,vi}.json` | key `detail.collisionAt` |
| `apps/web/src/app/__tests__/benchmark-replay.test.tsx` | **mới** — 8 test |
| `docs/KNOWN_LIMITATIONS.md` | #46 gạch (đã xong), #47 cập nhật phạm vi còn lại |

Backend **không đổi một dòng** — payload replay đã đủ từ trước.

## 4. Test

8 test mới (`benchmark-replay.test.tsx`, source-level như các test
chart — môi trường Node không có jsdom):

- page dùng hook, robot pose lấy từ playhead chứ không ghim frame cuối;
- có scrubber, play/pause, speed;
- trajectory cắt tại playhead;
- vật cản động lấy từ snapshot của frame hiện tại;
- collision marker trên timeline;
- hook không mở WebSocket, không import stream hook; `/simulate` không
  import hook mới;
- không nội suy;
- đồng hồ RAF × speed, dừng và clamp ở cuối.

## 5. Kiểm chứng

```text
npm test             443 passed / 1 failed + 1 suite fail — pre-existing
                     (2 lỗi đã ghi từ report Đợt 3.2, không liên quan)
npm run typecheck    sạch
npm run build        Compiled successfully
```

## 6. Giới hạn còn lại

- Vật cản động chưa hiện trong view **2.5D** (KNOWN_LIMITATIONS #47).
- Chưa có test render thật cho playback (môi trường Node, không jsdom —
  cùng giới hạn #144 của biểu đồ).
- Tua bằng bàn phím (mũi tên khi focus slider) dùng hành vi mặc định
  của `<input type="range">`, chưa có phím tắt space/J-K-L.
