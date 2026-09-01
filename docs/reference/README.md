# Tra cứu

Tài liệu tra khi đang làm việc. Onboarding thì đọc
[`../README.md`](../README.md) trước.

Cột **kiểm** ghi lần cuối nội dung được đối chiếu với code, không phải lần
cuối file được sửa chữ.

---

## Kiến trúc và hợp đồng

| File | Nội dung | Kiểm |
|---|---|---|
| [architecture_planner_selector.md](architecture_planner_selector.md) | Kiến trúc chi tiết: toán, ký hiệu, ánh xạ HĐ | 08-31 |
| [decision-log.md](decision-log.md) | **D01–D15 + trạng thái hôm nay.** Bốn quyết định còn là bất biến đang chạy và **code trích bằng ID** | 08-31 |
| [`../../contracts/CONTRACTS.md`](../../contracts/CONTRACTS.md) | **Luật.** Khi mâu thuẫn với bất kỳ file nào ở đây, contract thắng | — |

## API

| File | Nội dung | Kiểm |
|---|---|---|
| [api.md](api.md) | **Bắt đầu từ đây.** Bản đồ 161 route theo nhóm, và nhóm nào đã deprecate | 08-31 |
| `/docs` · `/openapi.json` | **Nguồn sự thật** — FastAPI sinh từ chính code | luôn đúng |

> Hợp đồng API viết tay cũ đã chuyển vào
> [`../archive/superseded/API_CONTRACT.md`](../archive/superseded/API_CONTRACT.md):
> nó không nhắc 84 trong 137 endpoint đang sống và mô tả nhóm `/benchmarks`
> (đã deprecate toàn bộ) như thể còn dùng bình thường.

## Tầng AI

| File | Nội dung | Kiểm |
|---|---|---|
| [AI_CAPABILITIES.md](AI_CAPABILITIES.md) | **Bắt đầu từ đây.** 13 điểm AI can thiệp, mỗi cái kèm endpoint và test. Đã đối chiếu: 12/12 endpoint tồn tại, 18/18 test tồn tại | 08-31 |
| [AGENT_AI.md](AGENT_AI.md) | Kiến trúc `services/agent_service/` — provider, tool registry, workflow. **Không gồm analyst** | 08-31 |
| [EVAL_EVIDENCE.md](EVAL_EVIDENCE.md) | Năm tình huống chạy thật trên tầng phản biện, provider thật. Hồ sơ có ngày | 08-16 |

> **AI Analyst** (`services/analyst_service/`) là service riêng, scope theo
> episode. Nó là mục 5g trong `AI_CAPABILITIES.md`; số đo thật ở
> [`../02-features.md`](../02-features.md) §3.

## Giao diện

| File | Nội dung | Kiểm |
|---|---|---|
| [FRONTEND.md](FRONTEND.md) | Kiến trúc `apps/web`, bảng route, nguyên tắc "UI chỉ render, không tính toán" | 08-31 |

## Vận hành và phát hành

| File | Nội dung | Kiểm |
|---|---|---|
| [DESKTOP-RELEASE.md](DESKTOP-RELEASE.md) | **Runbook release desktop.** Đọc trước mọi lần release | 08-28 |
| [DESKTOP.md](DESKTOP.md) | Kiến trúc bản đóng gói Windows | 08-25 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | PostgreSQL + Docker Compose, hai backend lưu trữ | 08-17 |
| [DEMO-PROFILE.md](DEMO-PROFILE.md) | Ba deployment profile và cách gỡ profile demo. *Tiếng Anh* | 08-28 |
| [ROS2_INTEGRATION.md](ROS2_INTEGRATION.md) | ROS2 + Nav2. Đã đối chiếu: 5/5 package khớp `ros2_ws/` | 08-31 |

## Cắm thuật toán ngoài

| File | Nội dung | Kiểm |
|---|---|---|
| [plugin_author_guide.md](plugin_author_guide.md) | Viết một plugin: manifest, entry point, conformance CLI | 08-24 |
| [plugin_import_security.md](plugin_import_security.md) | Ranh giới tin cậy, lane subprocess, deadline | 08-28 |

## Giới hạn và bằng chứng

| File | Nội dung | Kiểm |
|---|---|---|
| [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) | **Đọc trước khi trích bất kỳ số nào.** ~90 mục, 110 KB | 08-23 |
| [TEST_REPORT.md](TEST_REPORT.md) | Ảnh chụp output test có ngày. **Không phản ánh trạng thái hôm nay** — muốn biết thì chạy `pytest` | 08-17 |

> Bản rút gọn có xếp hạng của `KNOWN_LIMITATIONS.md`:
> [`../03-gaps.md`](../03-gaps.md).

---

## Đã dọn trong đợt rà 2026-08-31

| Việc | Chi tiết |
|---|---|
| `API_CONTRACT.md` → archive | 84/137 endpoint không được nhắc; 13 endpoint deprecate ghi như bình thường. Thay bằng [api.md](api.md) |
| `decision-log.md` tách ra | D01–D15 bị chôn trong `architecture.md` đã archive, trong khi code còn trích bằng ID |
| Bảng route `FRONTEND.md` | `/benchmarks`, `/leaderboard` đã gỡ khỏi app; viết lại theo `apps/web/src/app/` thật |
| Dòng 5g `AI_CAPABILITIES.md` | Bảng thiếu hẳn AI Analyst |
| Phạm vi `AGENT_AI.md` | Nói rõ không bao gồm analyst |
| Chỉ dẫn `architecture_planner_selector.md` | Nó khẳng định `ARCHITECTURE.md` là template chưa điền — sai từ 08-23; và trỏ `docs/architecture_diagram.md` chưa từng tồn tại |
| Khung `TEST_REPORT.md` | Đọc như trạng thái hiện tại, thật ra là ảnh chụp 08-17 |

Không xoá file nào. Thứ hết hiệu lực thì chuyển sang `../archive/`, vì
chúng còn giải thích được **vì sao** hệ hôm nay như vậy.
