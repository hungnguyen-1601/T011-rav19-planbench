# Decision log D01–D15

**Vì sao file này tồn tại riêng.** Nhật ký quyết định vốn nằm trong
`docs/architecture.md` — tài liệu đã lỗi thời và nay ở
[`../archive/superseded/architecture.md`](../archive/superseded/architecture.md).
Nhưng nhật ký thì **chưa** lỗi thời: bốn quyết định trong đó vẫn là bất
biến đang chạy, và **code đang trích dẫn chúng bằng ID**. Tách ra để phần
còn sống không bị chôn theo phần đã chết.

Đối chiếu code: **2026-08-31**.

---

## Trạng thái từng quyết định

| ID | Quyết định | Lý do / đánh đổi | Nay |
|---|---|---|---|
| D01 | Branch chính `main` (đổi từ `master` trước commit đầu) | Khớp quy ước GitHub | ✅ còn |
| D02 | Python 3.12, venv `.venv` + pip | Tương thích ROS2 Jazzy / Ubuntu 24.04 | ✅ còn |
| D03 | Monorepo; chỉ tạo thư mục khi có file thật | Tránh cấu trúc rỗng | ✅ còn |
| D04 | Frontend: Canvas 2D trước, R3F 2.5D sau | Giảm rủi ro; logic điều hướng vẫn 2D | ✅ còn |
| D05 | Storage: in-memory trước, PostgreSQL + Alembic sau | MVP nhanh; chốt schema khi domain ổn định | ✅ còn — in-memory vẫn là mặc định, có chủ đích |
| D06 | Map nội bộ JSON; import PGM/YAML (ROS `map_server`) sau | Ổn định định dạng nội bộ trước khi thêm converter | ✅ còn |
| **D07** | **Cell value theo chuẩn ROS (FREE=0, OCCUPIED=100, UNKNOWN=−1) ngay từ đầu** | ROS2 bridge không phải phiên dịch giá trị | ✅ **bất biến đang chạy** |
| **D08** | **Tiếp xúc biên = va chạm** (`clearance <= EPS`) | Bảo thủ về an toàn cho hệ benchmark robot | ✅ **bất biến đang chạy** — `services/simulator/planbench_simulator/collision.py` |
| **D09** | **Origin xoay chưa hỗ trợ**: validator từ chối `origin.theta ≠ 0` (trong EPS), không âm thầm bỏ qua | Tránh sai lệch toạ độ ngầm | ✅ **bất biến đang chạy** |
| **D10** | **Inflation**: chỉ cell OCCUPIED là nguồn; UNKNOWN giữ nguyên trừ khi bị đĩa inflation phủ lên; khi truy vấn, UNKNOWN mặc định bị coi là occupied (`unknown_as_occupied=True`) | Phân biệt rõ "không biết" với "chắc chắn có vật cản" | ✅ **bất biến đang chạy** — `services/simulator/planbench_simulator/grid.py` |
| D11 | Pytest `pythonpath` thay vì editable install | Đơn giản ở giai đoạn đầu | ✅ còn |
| **D12** | **Pure-pursuit follower chỉ là adapter tạm, không phải thuật toán benchmark** | Tránh nhầm lẫn khi so sánh | ✅ **bất biến đang chạy, và đã cứng hoá** — xem dưới |
| D13 | So sánh **theo stack** (A\*+DWA với A\*+PPO), không so trực tiếp global planner với local planner | Công bằng về vai trò thuật toán | ✅ còn, và đã cứng hoá thành **HĐ-1.4** — `global_planner_selection` đòi local layer giống hệt nhau, và ngược lại |
| D14 | LLM chỉ ở tầng điều phối; tuyệt đối không xuất `/cmd_vel`; mọi output qua schema + validation; kết luận phải trích evidence thật | An toàn + chống bịa | ✅ còn, và đã mở rộng — xem [`../01-architecture.md`](../01-architecture.md) §4 |
| D15 | Trajectory/artifact lớn lưu ra file; DB chỉ giữ metadata, URI, checksum | Tránh phình DB, dễ replay | ✅ còn — `artifacts/runs/` |

**Không có D16.** Nhật ký dừng ở D15. Hai chỗ từng trích "quyết định D16"
(`apps/web/src/lib/useEpisodeStream.ts` và hợp đồng API cũ) là trích nhầm;
thứ chúng muốn nói là hành vi phát lại WebSocket, nay ghi ở
[`api.md`](api.md) mục WebSocket.

---

## D12 — cái bẫy dễ đọc nhầm nhất

`astar+pure_pursuit` và `rrtstar+pure_pursuit` **có** trong registry, nên
nhìn danh sách stack sẽ tưởng chúng là ứng viên. **Không phải.** Cả hai
mang `reference=True` trong
`packages/benchmark/planbench_benchmark/registry.py`, và mô tả của chúng
nói thẳng:

> *"Temporary pipeline reference only — it ignores sensing, so it must not
> be used to draw benchmark conclusions."*

Chúng tồn tại để **chạy thử đường ống**, không để tranh thắng thua. Một
stack bỏ qua cảm biến mà được khuyến nghị chính là thất bại mà bộ cổng
sinh ra để chặn.

Quyết định này nay được **cấu trúc bảo vệ**, không còn là một lời dặn:
`production_eligible` được **suy ra** (`not reference and not withdrawn`),
và `benchmarkable` chỉ là alias tính toán của nó. Không ai đặt tay được
cờ đó — truyền `benchmarkable=` vào là no-op có cảnh báo.

Trích danh sách stack ở đâu thì phải trích kèm cờ này.

---

## EPS

`EPS = 1e-9`, định nghĩa **đúng một nơi**: `planbench_schemas.geometry`.
Mọi so sánh float trong dự án dùng nó. Đây là lý do D08 viết được thành
`clearance <= EPS` chứ không phải `clearance <= 0`.

---

## Đọc thêm

Quy ước cốt lõi ở dạng gọn (đơn vị SI, chuẩn hoá góc, cell value, xác
định tính): [`../01-architecture.md`](../01-architecture.md) §8.

Bất biến nghiệp vụ dễ phá — thứ khác với decision log, và đã bị phá thật:
[`../01-architecture.md`](../01-architecture.md) §7.
