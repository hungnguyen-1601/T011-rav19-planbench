# Preregistration — decision gate sau H1b (Algorithm Host)

> Bản ghi gate theo plan `algorithm-host-mo-rong-cho-global-va-local-planner.md`,
> mục "Decision gate sau H1b". **Phải nằm trong lịch sử git trước khi H0
> bắt đầu.** Các ô đánh dấu `[AN ĐIỀN]` là quyết định của decision owner,
> không phải của người thực thi; điền xong mới commit.
>
> Đi cùng file này: `configs/latency-screening-v1.yaml` (§5.9 luật 5).

## 1. Số liệu khai trước

| Trường | Giá trị | Nguồn |
|---|---|---|
| H1 (H1a+H1b) ideal effort | 2.5–3 ngày (+0.5–1 nếu vướng nửa monolithic) | plan §8 H1 |
| ideal(H2..H8) | 10–13 ngày (H2 1.5–2 · H3 2 · H4 1–1.5 · H5 1–1.5 · H6 1.5–2 · H7 1.5–2 · H8 1.5–2) | plan §8 |
| allocated host calendar budget | `3` tuần | An |
| remaining project calendar | `10` (tính từ ngày commit file này) | An |
| decision owner | An (Tống Duy An) | plan |

## 2. Trạng thái critical-path của research debt — khai trước, không quyết sau H1b

| Mục | Trạng thái đề xuất | An xác nhận |
|---|---|---|
| `robustness_margin` (F1) — đề tài gọi là điểm khác biệt học thuật mạnh nhất, chưa đo | **trên critical path kết luận đề tài** | `đồng ý`  |
| L17 — rollout dùng pose thật, đám mây điểm dùng pose robot tin là | điều kiện cần cho mọi hướng tri giác sau này; **không chặn host** | `đồng ý` |
| Truyền `LidarConfig` xuống controller (nợ thật của L20b, hiện chặn bằng validator) | không chặn host; trả khi mở angle_span | `đồng ý` |
| Full backend suite sau P6 (mục treo 8 của tổng kết P0–P6) | đã chạy 08-16: 2815 passed / 8 skipped | đã đóng |

## 3. External plugin demand

| Câu hỏi | Trả lời |
|---|---|
| Có thuật toán ngoài cụ thể (tên, người dùng) đang chờ tích hợp không? | `Chưa có` |
| Host có là deliverable chiến lược độc lập với đề tài không? | `Có` |

## 4. Công thức gate (đo sau H1b, không sửa sau khi commit)

```text
schedule_factor     = H1_actual / H1_ideal
projected_remaining = schedule_factor × ideal(H2..H8)
```

Tiếp H2–H8 khi và chỉ khi **đồng thời**:

1. `projected_remaining ≤ allocated_host_budget`;
2. host là deliverable chiến lược **hoặc** có external algorithm thật chờ
   integration (mục 3);
3. không có research blocker ưu tiên cao hơn trên critical path (mục 2).

Không đạt ⇒ dừng sạch theo plan: khoá `protocol_version`, H2–H8 vào
backlog. H1b đã trả SDK + synthetic manifests + loader + A5 trước gate.

## 5. Kết quả gate — đo 2026-08-18

| Trường | Giá trị | Cơ sở |
|---|---|---|
| H1_actual (ngày) | **1 ngày kỹ thuật** | H1a + H1b hoàn thành trọn trong 18-08 (hai report cùng ngày, một phiên). Thực tế ~0.5 ngày; lấy tròn 1 để nghiêng về hướng khắt khe |
| schedule_factor | **0.33–0.40** | `1 / (2.5–3.0)` |
| projected_remaining | **3.3–5.2 ngày kỹ thuật ≈ 1.3–2.1 tuần lịch** | `factor × ideal(H2..H8) = 0.33×10 … 0.40×13`; quy lịch bằng hệ số ×2 đã khai ở mục 1 |
| Verdict | **ĐẠT — tiếp H2–H8**, kèm hai ràng buộc bên dưới | ba điều kiện đối chiếu bên dưới |
| Ngày quyết + người quyết | 2026-08-18 · An (chốt bằng chính commit file này) | decision owner mục 1 |

### Đối chiếu ba điều kiện

1. `projected_remaining ≤ allocated_host_budget`: **2.1 tuần ≤ 3 tuần** ở
   đọc khắt khe nhất — **đạt**.
2. Host là deliverable chiến lược: An khai **"Có"** ở mục 3 (external
   demand "Chưa có" — vế OR thoả bằng nhánh chiến lược) — **đạt**.
3. Research blocker: `robustness_margin` (F1) **trên critical path** (mục
   2, An xác nhận) nhưng **không tranh ngân sách host**: remaining 10
   tuần − ~2 tuần host = ~8 tuần cho research, và chính việc An cấp
   riêng 3 tuần cho host trong prereg này (đồng thời khai host là
   deliverable chiến lược *độc lập với đề tài*) là hành vi xếp hạng ưu
   tiên trong phạm vi budget đó. F1 giữ nguyên vị trí critical path,
   không bị host phủ quyết và không phủ quyết host — **đạt, có điều
   kiện**.

### Hai ràng buộc đi kèm verdict

- **Trần 3 tuần vẫn cứng.** H2–H8 trượt tới mức chạm trần ⇒ dừng tại
  phase đang dở, phần còn lại vào backlog — không thương lượng lại trần
  giữa chừng.
- **F1 không bị đẩy lùi thêm.** Nếu lịch đề tài siết (remaining < 8
  tuần trước khi host xong), F1 thắng, host dừng tại phase gần nhất
  hoàn tất.
