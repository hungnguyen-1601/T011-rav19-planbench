# Khảo sát: deploy PlanBench thành app — đánh giá và ý kiến

- **Ngày:** 2026-08-24
- **Người viết:** Tống Duy An (cùng Claude khảo sát)
- **Câu hỏi:** sản phẩm hiện tại deploy lên thành app được chưa, nếu deploy thì deploy kiểu gì, phải sửa gì trước.
- **Nguồn:** đọc toàn bộ docs/antongduy từ 2026-08-08, `docs/DEPLOYMENT.md`, `docs/KNOWN_LIMITATIONS.md`, `docker-compose.yml`, ba Dockerfile, `requirements*.txt`, `apps/api/planbench_api/{main,config,worker}.py`, các router, `docs/plugin_import_security.md`.

---

## 1. Kết luận trước

**Deploy được ngay ở mức demo/internal có kiểm soát. Chưa deploy được ở mức
multi-user công khai.** Khoảng cách giữa hai mức không phải là "viết thêm
hạ tầng" — hạ tầng compose của repo này tốt hơn mặt bằng chung — mà là **bốn
lỗi/lỗ cụ thể sửa được trong vài ngày** (mục 4) cộng **một giới hạn bản chất
không sửa bằng deploy được** (mục 6: máy đo chỉ chạy một run một lúc).

Xếp hạng ba kịch bản:

| Kịch bản | Sẵn sàng | Điều kiện |
|---|---|---|
| **A. Demo nội bộ / trình thầy-khách** (compose trên một VPS, người dùng được mời) | ✅ gần như ngay | vá `httpx`, set `AUTH_SECRET`, Postgres + volume |
| **B. Pilot cho một nhóm ngoài tin cậy** (Render/VPS, OAuth thật, domain thật) | ⚠️ sau ~1 tuần việc | thêm mục 4 đủ 4 điểm + mục 5 phần vận hành |
| **C. Public SaaS ai cũng đăng ký** | ❌ chưa | plugin/PPO thực thi code người dùng bằng quyền process API — phải sandbox thật; cộng rate limit, worker tách process |

## 2. Sản phẩm đang có gì (tóm tắt để người đọc sau khỏi đào)

PlanBench / Planner Selector: web app chọn stack điều hướng robot cho một
deployment cụ thể, đầu ra là Decision Card có kiểm định thống kê (paired
bootstrap ΔU, 6 cổng G1–G6, manifest tái lập). Luồng chính đầu-cuối **đã
chạy thật**: form khai deployment → sweep candidate×seed → trace Parquet →
metrics → gates → Decision Card → trang decision → export Excel/MD → share →
approval. Cộng: Algorithm Host + import plugin `.zip` qua UI (admin-only,
conformance trong subprocess), tầng giải thích E0–E6b, AI Advisor chạy thật
với OpenAI (12/12 lượt không bịa số sau vá 08-24), RBAC + audit trail.
~2815 test backend + 1566 test web xanh.

Chưa có: AI Analyst Lane 2 ("vì sao A thắng B" — `services/analyst_service/`
không tồn tại), golden suite chưa chấm, và **chưa có Decision Card hợp lệ
nào trên map giống khách hàng** (warehouse dừng 245/300, cả hai candidate
trượt G2+G3; mọi kết luận hiện có nằm trên `open_hall` — dụng cụ đo, không
phải deployment thật).

## 3. Hạ tầng deploy hiện có — điểm mạnh

Đánh giá thật lòng: phần này **trên mức trung bình rõ rệt**, phần lớn việc
khó của "đưa lên app" đã làm từ trước:

- `docker-compose.yml` 4 service: `db` (postgres:17) → `migrate` (one-shot
  `alembic upgrade head`, phải exit 0) → `api` → `web`, nối bằng
  `service_healthy` / `service_completed_successfully`. Migrate tách khỏi
  API start là đúng bài (2 replica cùng upgrade là race).
- Image API: multi-stage, user non-root uid 10001, copy chọn lọc, healthcheck
  `/api/v1/health`. Web: Next standalone, Node 22 alpine.
- Đã chạy thật trên PostgreSQL 17 hai lần (08-03, 08-05), không phải chỉ
  parse YAML.
- Config 12-factor sạch: `PLANBENCH_*` qua pydantic-settings; **API key LLM
  cố ý không là field Settings** (không lọt log dump), nạp qua
  `load_provider_keys()` — shell thắng file. Thiếu key ⇒ mock offline, không chết.
- Artifact store là interface, DB ba backend (in-memory / sqlite / postgres)
  cùng Protocol, payload lớn nằm ngoài DB (URI + checksum).
- Threat model plugin viết đàng hoàng (`docs/plugin_import_security.md`),
  nói thẳng subprocess ≠ sandbox thay vì nói dối.
- Dependency đã verify trên `.venv` sạch bằng 4 phép độc lập (note 08-16).
- Đã có bản chạy tay trên Render (`https://planbench-web.onrender.com/`).

## 4. Bốn blocker chặn cứng trước khi cho người ngoài dùng

Theo thứ tự sửa:

1. **`httpx` thiếu trong `docker/requirements-api.txt`** trong khi
   `oauth.py:221,256,263` import lazy. Image build được, API lên, health xanh
   — và OAuth callback nổ `ModuleNotFoundError` đúng lúc đổi code lấy token.
   Đăng nhập là cửa duy nhất nên đây là blocker số một. Sửa: một dòng.
   (Cùng loại lỗi "boot được, chết ở request đầu" mà pattern secret-không-default
   cảnh báo — health check không chạm dependency thì không thấy.)
2. **12 endpoint ghi/chạy không có auth**: `scenarios.py` 7/7 không auth
   (gồm POST/PUT/DELETE), `simulations.py` 5/5 không auth (gồm
   `POST /{id}/run` — mở CPU server cho người vãng lai), `ws.py` accept
   vô điều kiện. Trong khi benchmarks/models/decisions/plugins phủ gần đủ.
   Đây là sót không đều, không phải thiết kế.
3. **Hai đường thực thi code người dùng bằng quyền process API**:
   - plugin bundle: subprocess lane kế thừa **toàn bộ env (gồm mọi API
     key)**, PYTHONPATH chứa repo, cùng quyền FS/mạng
     (`subprocess_lane.py:358-366`);
   - PPO checkpoint: `PPO.load()` unpickle **ngay trong worker thread của
     API** — RCE thẳng, tệ hơn plugin (KL #77-78).
   Hiện chắn bằng admin-only — đủ cho kịch bản A/B, **không đủ cho C**.
   Mức tối thiểu cho B: lọc env trước khi spawn worker (allowlist, không
   truyền `*_API_KEY`), giữ import PPO admin-only.
4. **CORS + 4 biến URL phải đổi cùng nhau khi có domain thật**:
   `PLANBENCH_CORS_ORIGINS` compose đang hardcode `localhost:3000`;
   `NEXT_PUBLIC_API_URL` nướng vào bundle lúc build (đổi domain API =
   rebuild image web); OAuth callback suy từ `PLANBENCH_API_PUBLIC_URL`.
   Quên một trong bốn là app "lên mà không đăng nhập được / không gọi API được".

## 5. Việc vận hành cho kịch bản B (không chặn A)

- **Worker in-process** (`ThreadPoolExecutor` trong API): restart = mất job,
  không retry (KL #24). Chấp nhận được cho pilot; production thật cần tách.
- **Rate limit chưa có** (KL #18); upload đã có 4 trần (50 MB zip / 500
  member / 200 MB giải nén / 64 KB manifest) nhưng HTTP thì không.
- **JWT TTL 60 phút, không refresh token, không server-side logout** (KL #17).
- **Postgres đa người dùng chưa kiểm chứng dưới tải** — pool 5+5, DEPLOYMENT.md
  tự khai. Không retry connect lúc boot (#56) ⇒ cần restart policy.
- `AUTH_SECRET` bắt buộc set cố định — rỗng là random mỗi process, restart
  là đăng xuất cả app (#98).
- **`/docs` + `/openapi.json` đang mở công khai**, không theo `debug`.
- **Đổi `PLANBENCH_ARTIFACT_DIR` sau khi ghi là hỏng mọi URI `file://` đã
  lưu** (#54) — chọn path volume một lần, đúng ngay từ đầu; backup = DB +
  artifacts + models cùng lúc.
- Share email là `mailto:` (không SMTP), MLflow file-store local-only —
  không chặn, nói trước để không hứa nhầm với người dùng.
- Dọn rác trước khi build: `planbench.db.bak-before-0010` (17.5 MB),
  `vfh_plus_import/`, `vfh_plus_iterated/`, `README.old.md`, `node_modules/` root.
- **Makefile lỗi thời hoàn toàn** (trỏ `src/` scaffold) — đừng ai deploy bằng nó.
  Root `Dockerfile` cũng lệch đời (cài cả pytest/ruff vào image, COPY cả repo);
  đường chính thống là `docker/Dockerfile.api` + compose.

## 6. Hai giới hạn bản chất — deploy không sửa được, phải nói rõ khi bàn giao

1. **`JobQueue(1)` cho decision run là ràng buộc đo lường, không phải bug**
   (HĐ-7.4: pin core, không cho hai selection run song song trên một máy).
   Nhiều người bấm "chạy" cùng lúc ⇒ xếp hàng. Muốn phục vụ song song phải
   **tách máy đo riêng** (API/web một nơi, worker đo một nơi) — đó là việc
   kiến trúc pha sau, không phải config.
2. **Giá trị khoa học của output chưa phủ đến deployment thật** (mục 2).
   Deploy app lên không làm Decision Card đáng tin hơn. Người dùng đầu tiên
   sẽ chạy trên map của họ — và kịch bản warehouse hiện tại đang trượt cổng.
   Cần quản lý kỳ vọng: app là "nền tảng chạy phép so + bằng chứng", chưa phải
   "máy trả lời đúng cho mọi deployment".

## 7. Ý kiến: deploy kiểu gì

**Trục chọn platform là timeout, không phải giá.** Một decision run là sweep
candidate×episode×seed chạy nhiều phút đến hàng giờ, CPU-bound, có pin core
⇒ **loại hẳn serverless** (Lambda/Vercel functions trần 5–15 phút, và
scale-to-0 phá phép đo latency). Job đã async qua JobQueue + WebSocket theo
dõi nên HTTP request không dài — nhưng process phải sống bền và một mình
một máy lúc đo.

**Khuyến nghị: một VM/VPS always-on chạy đúng `docker-compose.yml` hiện có**
(4–8 vCPU, ≥8 GB RAM; api + web + postgres + volume). Lý do:

- compose 4 service đã là artifact chạy thật, không phải viết mới;
- pin-core cần máy vật lý ổn định, autoscale là kẻ thù của phép đo;
- Render hiện tại (bản demo đang chạy) hợp cho web+api nhẹ nhưng
  không kiểm soát được chuyện "một mình một máy lúc đo", và deploy
  đang thủ công qua dashboard — **không có IaC trong repo, không tái lập
  từ git** (không `render.yaml`). Nếu giữ Render thì ít nhất commit
  `render.yaml` để deploy tái lập được.

**Thứ tự việc đề xuất (kịch bản B, ~1 tuần):**

1. Thêm `httpx` vào `docker/requirements-api.txt` (nửa ngày cả test image).
2. Phủ auth `scenarios.py`, `simulations.py`, `ws.py` (1 ngày, có sẵn
   `ActiveUser` dùng theo mẫu các router kia).
3. Lọc env cho subprocess lane (allowlist, chặn `*_API_KEY`) (1 ngày).
4. Đưa `PLANBENCH_CORS_ORIGINS` thành biến ngoài trong compose; viết một
   trang "đổi domain = đổi 4 biến nào" vào DEPLOYMENT.md; bổ sung
   `PLANBENCH_PLUGIN_DIR` + `PLANBENCH_MAX_PLUGIN_*` vào bảng env (nửa ngày).
5. Rate limit tối thiểu (middleware token bucket hoặc reverse proxy limit
   ở Caddy/nginx trước app) (1 ngày).
6. Dựng VPS: compose up, `AUTH_SECRET` cố định, OAuth app đăng ký với
   domain thật, backup định kỳ DB+artifacts (1 ngày).
7. Cập nhật README §9.2 (đang nói ngược với code về import plugin) và
   KL #51 (mâu thuẫn nội bộ về "đã từng compose up") — nợ tài liệu, làm
   trước khi ai đó ngoài team đọc repo.

Chưa nên hứa: public đăng ký tự do (C) trước khi có sandbox thật cho
plugin/PPO; AI Analyst Lane 2 trong bản deploy đầu (chưa tồn tại).

## 8. Đối chiếu nhanh checklist agent-deploy

| Pha | Trạng thái |
|---|---|
| 0. Platform theo timeout | Chọn đúng hướng nếu theo mục 7; serverless bị loại có lý do |
| 1. Service deploy được | ✅ config/env/probe/health có; ⚠️ secret LLM đọc đúng cách từ 08-24; ⚠️ health không chạm DB (chấp nhận được, có `migrate` gate) |
| 2. Container | ✅ multi-stage, non-root, slim; ⚠️ thiếu `httpx`; root Dockerfile lệch đời |
| 3. Cổng vào | ⚠️ auth có nhưng phủ thủng 12 endpoint; ❌ rate limit; ✅ cost guard phía LLM = mock-fallback + key tách khỏi Settings |
| 4. State & reliability | ✅ state ra DB+artifact volume; ❌ worker in-process, mất job khi restart; ❌ không graceful drain cho run đang chạy |
| 5. CI/CD | CI test có (matrix ubuntu+windows); ❌ không deploy pipeline, Render thủ công, không IaC |
