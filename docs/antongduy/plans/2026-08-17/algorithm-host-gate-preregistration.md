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

## 5. Chỗ ghi kết quả (điền lúc gate, không phải bây giờ)

| Trường | Giá trị |
|---|---|
| H1_actual (ngày) | _chưa đo_ |
| schedule_factor | _chưa đo_ |
| projected_remaining | _chưa đo_ |
| Verdict | _chưa quyết_ |
| Ngày quyết + người quyết | _chưa quyết_ |
