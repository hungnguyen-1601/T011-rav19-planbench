# Khảo sát: triển khai PlanBench lên web miễn phí — có khả thi không

- **Ngày:** 2026-09-03
- **Người viết:** Tống Duy An (cùng Claude khảo sát)
- **Câu hỏi:** desktop app đã phát hành (GitHub Releases, đang được chấm).
  Muốn thêm một bước triển khai web, ràng buộc: **miễn phí**. Khả thi không?
- **Nguồn:** note 08-24 `tongduyan_khao-sat-deploy-len-app.md`,
  `docker-compose.yml`, `docker/requirements-api.txt`,
  `apps/api/planbench_api/routers/` (grep auth), `docs/reference/DEPLOYMENT.md`,
  `docs/reference/DEMO-PROFILE.md`, fetch thử `planbench-web.onrender.com`.

---

## 1. Kết luận

**Khả thi — ở mức demo/showcase công khai có kiểm soát. Không khả thi ở mức
"chạy decision run tin cậy được trên hạ tầng miễn phí".** Ranh giới không
phải do thiếu hạ tầng (compose 4 service đã chạy thật) mà do hai thứ:

1. `httpx` vẫn thiếu trong `docker/requirements-api.txt` (kiểm lại
   2026-09-03) — OAuth callback sẽ nổ `ModuleNotFoundError` đúng lúc
   đăng nhập. **Đính chính cùng ngày:** bản đầu của note này viết cả
   blocker auth (#2 của note 08-24) còn nguyên — sai. Grep đầu dùng
   pattern `ActiveUser|current_user` nên trượt; đọc thẳng file cho thấy
   `scenarios.py` / `simulations.py` / `ws.py` đã phủ auth từ contract
   7.0.0 (`ReadingUser`/`WritingUser`/`SimulatingUser`, WebSocket dùng
   ticket một-phút qua `POST /api/v1/ws/tickets`). Blocker #2 đã đóng.
2. Bản chất decision run: sweep CPU-bound nhiều phút tới hàng giờ, pin core
   (HĐ-7.4), `JobQueue(1)`, worker in-process — free tier nào cũng hoặc
   cho 0.1 vCPU, hoặc ngủ giữa chừng (mất job, không retry), hoặc cả hai.
   Con số đo trên CPU share không có giá trị làm bằng chứng.

Cách đóng khung đúng cho bản web: **trưng bày** — trang decision, Decision
Card, tầng giải thích, replay episode từ dữ liệu đã chạy sẵn ở máy mạnh —
chứ không hứa "bấm nút là có phép so mới đáng tin".

## 2. Hiện trạng liên quan

- Đã từng có bản Render chạy tay: `https://planbench-web.onrender.com/`.
  Fetch hôm nay trả **503 Retry-After: 5** — đúng hành vi free tier đang
  ngủ/spin-up hoặc đã bị suspend. Không có `render.yaml` trong repo, deploy
  đó không tái lập được từ git.
- `PLANBENCH_DEPLOYMENT_PROFILE=demo` đã tồn tại (DEMO-PROFILE.md): một
  `demo_owner` giữ mọi capability, banner không tắt được — **khớp đúng**
  kịch bản web demo công khai, không phải viết thêm.
- Artifact store là `file://` URI trên volume — mất volume là mất replay
  (D15). Mọi free tier không disk bền (Render free, HF Spaces free) sẽ
  mồ côi episode sau mỗi restart, trừ khi artifact demo được nướng thẳng
  vào image.
- Web Next.js: `NEXT_PUBLIC_API_URL` nướng vào bundle lúc build — đổi
  domain API là rebuild image web; CORS hardcode `localhost:3000` trong
  compose. Bốn biến URL phải đổi cùng nhau (note 08-24 mục 4.4).

## 3. Các phương án miễn phí, xếp hạng

| # | Phương án | CPU/RAM | Ngủ? | Disk bền? | Đánh giá |
|---|---|---|---|---|---|
| 1 | **Oracle Cloud Always Free** — 1 VM ARM 4 OCPU / 24 GB, chạy nguyên `docker-compose.yml` | tốt nhất nhóm free, always-on | không | có | **Khuyến nghị.** Gần nhất với "VPS always-on" mà note 08-24 đề xuất, giá 0đ. Giá phải trả: cần thẻ tín dụng lúc đăng ký, capacity theo region hên xui, phải build image arm64 (numpy/scipy/pyarrow/psycopg đều có wheel aarch64 — không chặn), và Oracle thu hồi instance idle lâu. |
| 2 | **Hugging Face Spaces (Docker)** | 2 vCPU / 16 GB | ngủ sau 48h idle | không (trả phí mới có) | CPU thật nhất trong nhóm PaaS free. Một container duy nhất — phải gộp api+web vào một image hoặc tách web sang Vercel. Dữ liệu demo nướng vào image, SQLite ephemeral. Hợp cho showcase. |
| 3 | **Render free (đường cũ)** + Neon/Supabase free Postgres | 0.1 vCPU / 512 MB | ngủ sau 15 phút, cold start ~1 phút | không | Đường ít việc nhất vì đã có sẵn service. Đủ cho "bấm xem UI + dữ liệu seed". Decision run coi như tắt. Nếu giữ thì commit `render.yaml` để tái lập. Postgres free của Render hết hạn 30 ngày — dùng Neon (0.5 GB) hoặc Supabase (500 MB, pause sau 7 ngày idle) thay. |
| 4 | **Vercel free cho web** + API ở #2 hoặc #3 | — | — | — | Web Next.js lên Vercel là chuẩn bài và nhẹ nhất; chỉ giải quyết nửa frontend. Serverless **không chạy được API này** (JobQueue in-process, WebSocket, run dài) — đã loại từ note 08-24, vẫn đúng. |
| 5 | Fly.io / Railway | — | — | — | Không còn free tier thật cho người mới. Loại. |

## 4. Việc bắt buộc trước khi mở công khai (mọi phương án)

Theo thứ tự, ước lượng từ note 08-24:

1. Thêm `httpx` vào `docker/requirements-api.txt` — một dòng.
2. ~~Phủ auth ba router~~ — **đã xong từ trước** (contract 7.0.0, xem
   đính chính ở mục 1).
3. Lọc env trước khi spawn subprocess plugin (allowlist, chặn `*_API_KEY`).
   Với bản demo không cấp admin cho ai thì rủi ro đứng sau cửa admin-only,
   nhưng key LLM thật thì **đừng đặt lên bản free công khai** ngay từ đầu —
   mock advisor là đủ cho showcase.
4. Externalize `PLANBENCH_CORS_ORIGINS` + chốt 4 biến URL cho domain thật.
5. Bật `PLANBENCH_DEPLOYMENT_PROFILE=demo`, `AUTH_SECRET` cố định, seed
   dữ liệu demo (decision + artifact từ máy local) vào image/volume.
6. Rate limit tối thiểu nếu mở link công khai rộng (KL #18 — chưa có).

## 5. Giới hạn phải nói trước với người xem bản web

- Decision run mới trên free tier: chậm (CPU share), có thể chết giữa chừng
  (instance ngủ/restart = mất job), và con số không mang giá trị bằng chứng
  (pin core vô nghĩa trên vCPU share). Bản web là nơi **đọc** bằng chứng đã
  chạy ở máy đo thật.
- Cold start free tier (Render/HF): người mở link lần đầu chờ 30–60s.
  Đừng để giám khảo là người đầu tiên trong ngày mở link — tự mở trước.
- Desktop app đang được chấm với `admin:admin` — bản web là deployment
  tách biệt, không đụng `.env` của bản desktop đã phát hành.

## 6. Đề xuất

Hai đường, tuỳ khẩu vị công sức:

- **Ít việc nhất (~2–3 ngày):** vá mục 4.1–4.2, dựng lại Render free bằng
  `render.yaml` commit vào repo + Neon Postgres + seed demo, profile demo.
  Chấp nhận cold start và decision run tắt/chậm.
- **Đáng nhất nếu chịu friction đăng ký (~3–4 ngày):** Oracle Always Free
  ARM VM, `docker compose up` nguyên bản (build arm64), disk bền, không
  ngủ. Gần bản chất "một máy always-on" nhất mà vẫn 0đ.

Chưa quyết định phương án nào — chờ An chọn rồi mới lập plan chi tiết.
