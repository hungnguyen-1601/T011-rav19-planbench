# API — bản đồ đường đi

**Nguồn sự thật là schema sinh ra, không phải file này.** FastAPI sinh
OpenAPI từ chính code:

| Đường dẫn | Dùng để |
|---|---|
| `/docs` | Swagger UI — thử endpoint ngay trên trình duyệt |
| `/redoc` | ReDoc — đọc dễ hơn khi cần tra kiểu |
| `/openapi.json` | Schema thô, dùng cho codegen |

File này chỉ làm một việc schema không làm được: nói **nhóm nào để làm
gì**, và **nhóm nào đã chết**.

Đối chiếu code: **2026-08-31** · 161 route, trong đó **18 đã deprecate**.

---

## Nhóm route

| Router | Prefix | Route | Vai |
|---|---|---|---|
| `decisions` | *(không prefix)* | **52** | Trung tâm sản phẩm: tạo và chạy phép so, cổng, Decision Card, advice, critique, outcome, exemplar, explanation, replay-sync, phân tích episode, hàng chờ duyệt, ký duyệt, xuất báo cáo |
| `models` | *(không prefix)* | 14 | Model registry (PPO), robot profile, kiểm tương thích |
| `plugins` | `/algorithms/plugins` | 12 | Vòng đời plugin: validate, publish, hold, disable, events |
| `admin` | `/admin` | 8 | Cấp/thu quyền, khoá tài khoản, nhật ký phân quyền, ops job |
| `maps` | `/maps` | 8 | CRUD map, validate |
| `auth` | `/auth` | 7 | OAuth provider, callback, session, dev login |
| `library` | *(không prefix)* | 7 | Thư viện scenario dựng sẵn, import |
| `scenarios` | `/scenarios` | 7 | CRUD scenario, validate, preview vật cản động |
| `episodes` | *(không prefix)* | 6 | Trace và kết quả từng episode |
| `reviews` | `/reviews` | 6 | Inbox, sent, nhận, đọc, ký duyệt, từ chối |
| `simulations` | `/simulations` | 5 | Sân thử: tạo, chạy headless, đọc kết quả |
| `users` | `/users` | 3 | Nickname, tìm người nhận review |
| `agent` | `/agent` | 2 | `/agent/chat`, `/agent/capabilities` |
| `algorithms` | `/algorithms` | 2 | Catalogue stack |
| `settings` | `/settings` | 2 | Cấu hình hệ thống |
| `tuning` | `/tuning` | 1 | Tuning siêu tham số |
| `health` | *(không prefix)* | 1 | `{status, app, version}` |
| `ws` | `/ws` | — | WebSocket, không phải route HTTP |
| ~~`benchmarks`~~ | `/benchmarks` | ~~18~~ | **Toàn bộ đã deprecate** — xem dưới |

Chi tiết từng route đọc ở `/docs`. Router nằm ở
`apps/api/planbench_api/routers/`, một file một nhóm.

---

## `/benchmarks` — cả router đã deprecate

**Cả 18 route đều mang `deprecated=True`.** Giao diện từng gọi chúng đã bị
gỡ ở đợt P6; việc chúng làm nay nằm ở chỗ khác:

| Trước | Nay |
|---|---|
| `/benchmarks`, `/benchmarks/[id]` (phép so) | `/decisions` |
| `/leaderboard` (xếp hạng) | *(bỏ — xếp hạng ngoài ngữ cảnh một deployment là phép so không cùng điều kiện)* |
| `/algorithms` (trang registry) | `/candidates` |
| Xem một episode | `/simulate` |

**Endpoint còn đó là có chủ đích**, không phải bỏ quên. Lý do ghi ngay
trong docstring `apps/api/planbench_api/routers/benchmarks.py`: gỡ endpoint
cùng lúc với gỡ trang là hai thay đổi lớn một lượt, hỏng thì không biết
cái nào gây ra; và bảng `benchmarks` giữ nguyên vì một deployment nào đó
có thể còn đọc nó, mà xoá dữ liệu thì redeploy không hoàn tác được.

Đánh dấu `deprecated=True` để **OpenAPI nói ra điều đó**, thay vì để sự
thật nằm trong một commit message. Gỡ hẳn là một đợt riêng, sau.

**Đừng viết code mới dựa vào nhóm này.**

---

## WebSocket

`/ws/simulations/{id}?speed=N&pace=true|false` — **không** nằm dưới
`/api/v1`.

- Simulation phải ở trạng thái `finished`. Episode chạy headless nhanh hơn
  thời gian thực; WS **phát lại** trajectory đã ghi, không chạy trực tiếp.
- `pace=true` (mặc định): server điều nhịp theo `sim_time/speed`, cap tần
  suất bởi `PLANBENCH_WS_MAX_RATE_HZ` (mặc định 60 Hz). Frame vượt cap bị
  **bỏ**, không bị trễ.
- `pace=false`: gửi **mọi** frame nhanh nhất có thể. Web UI dùng chế độ
  này vì nó tự điều nhịp (pause / scrub / speed).
- Message: `{type:"start", plan_path, steps}` → nhiều
  `{type:"state", time, x, y, theta, linear_velocity, angular_velocity}`
  → `{type:"result", status, reason, elapsed_time, metrics}`.
- Lỗi: `{type:"error", code:"not_found"|"not_ready"}` rồi đóng.

---

## Quy ước chung

- Kiểu domain sinh từ `packages/schemas/` (Pydantic). Đổi schema là đổi
  API — đó là chủ ý của nguyên tắc contract-first.
- Frontend giữ kiểu tương ứng ở `apps/web/src/lib/types.ts` và
  `platformTypes.ts`.
- Mọi ngưỡng đọc từ deployment profile, không từ query param.

---

## Hợp đồng API cũ

Bản hợp đồng viết tay trước lần chuyển hướng nằm ở
[`../archive/superseded/API_CONTRACT.md`](../archive/superseded/API_CONTRACT.md).
Nó mô tả kỹ nhóm `/benchmarks` và các API thời M4–M13, nên có ích khi cần
tra **vì sao** một endpoint cũ cư xử như vậy — nhưng nó **không nhắc 84
trong 137 endpoint đang sống**, và ghi nhóm `/benchmarks` như thể còn dùng
bình thường. Đừng dùng nó làm bản đồ hiện tại.
