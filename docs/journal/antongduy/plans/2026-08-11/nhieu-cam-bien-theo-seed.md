# Kế hoạch (hoãn): nhiễu cảm biến và odometry theo seed

> **Ngày lập:** 2026-08-11 · **Trạng thái:** đã chốt làm, **hoãn thi công** theo chỉ đạo của
> An — làm sau khi có kết quả của phương án đổi mission.
> **Nguồn:** phát hiện của Phase 5.1, xem
> `reports/2026-08-11/tongduyan_phase-5-1-mot-tam-card-noi-doi.md`.

---

## 1. Vấn đề, phát biểu chính xác

Simulator hiện tại **tất định hoàn toàn**. Nguồn ngẫu nhiên duy nhất phụ thuộc seed là pha của
vật cản động (`seed_time_offset`) và bản thân planner nếu nó ngẫu nhiên.

Hệ quả: một candidate **tất định** (`astar+dwa`) trên một nhiệm vụ mà vật cản không chạm tới sẽ
sinh ra **cùng một episode cho mọi seed**. Bộ 100 episode có số mẫu hiệu dụng bằng 1, và quy tắc
số 3 của G2 không chặn được gì.

Đo được ở Phase 5.1:

| Traffic cách tuyến | `n_distinct` của A\* | Ghi chú |
|---|---:|---|
| ~2,5 m | **1**/100 | không phản ứng |
| ~1,0 m | **2**/10 | vẫn không phản ứng ở 8/10 seed |
| xuyên tâm tuyến | — | va chạm 31%, trượt G3 |

**Cửa sổ giữa "không phản ứng" và "đâm vào" rộng khoảng 14 cm**, vì DWA cấu hình
`horizon_seconds: 1.0` với `v_max = 0.8` chỉ nhìn trước 0,8 m, còn chạm nhau ở 0,66 m. Không có
cách đặt traffic nào lọt vừa khe đó một cách bền vững.

## 2. Vì sao nhiễu cảm biến là lời giải đúng, không phải một cách vá

Robot thật **không bao giờ** chạy hai lần giống hệt nhau: bánh trượt, sàn ướt, LiDAR có nhiễu,
odometry tích lũy sai số. Tài liệu mẹ đã liệt kê đúng những nguồn này ở N5 (bảng trục nhiễu:
*"Nhiễu cảm biến & odometry — LiDAR σ = 2 cm, trượt bánh 2%"*).

Nên đây không phải "thêm ngẫu nhiên để bộ mẫu trông đẹp". Đây là **sửa một chỗ simulator đang
lạc quan hơn thực tế**, và cái giá của sự lạc quan đó là G2 tuyên bố cận trên va chạm mà bằng
chứng không đỡ được.

Ba tính chất khiến nó tốt hơn hẳn cách đặt traffic:

1. **Áp cho mọi deployment**, không phụ thuộc tuyến đường có gặp vật cản hay không.
2. **Áp cho mọi candidate**, kể cả tất định — đó chính là ca đang hỏng.
3. **Không đánh đổi với va chạm**: nhiễu nhỏ làm episode khác nhau mà không đẩy robot vào vật cản.

## 3. Phạm vi đề xuất

| Nguồn nhiễu | Biên độ (theo N5) | Ghi chú |
|---|---|---|
| Nhiễu đo LiDAR | σ = 2 cm | Cộng vào tia quét, không vào ground truth va chạm |
| Trượt bánh / odometry | 2% | Lệch giữa lệnh điều khiển và chuyển động thật |

**Ba ràng buộc thiết kế phải giữ:**

- **Seed từ `EpisodeContext`, không từ đồng hồ.** Cùng context ⇒ cùng nhiễu ⇒ episode tái lập
  được. HĐ-13 đòi người khác dựng lại đúng tấm card; nhiễu lấy từ `time` sẽ phá điều đó.
- **Nhiễu vào *phép đo*, không vào *sự thật*.** Va chạm phải được phán quyết trên vị trí thật.
  Nếu tầng va chạm cũng đọc pose đã nhiễu thì ta đang đo một thế giới khác chứ không phải một
  robot đo kém.
- **Khai báo được, mặc định tắt.** Biên độ thuộc `TaskProfile.environment` (deployment mô tả
  hiện trường của nó), không thuộc candidate. Mặc định 0 để mọi profile cũ giữ nguyên hành vi —
  bật lên là một thay đổi có chủ ý và nhìn thấy trên manifest.

## 4. Ảnh hưởng tới hợp đồng

- **HĐ-2** thêm khối nhiễu vào `EnvironmentSpec` (MINOR — trường có mặc định).
- **HĐ-3.3** hiện định nghĩa bộ evaluation là *mission × lần hiện thực vật cản × seed*. Thêm
  nhiễu nghĩa là "lần hiện thực" bao gồm cả nhiễu cảm biến, nên câu chữ cần nới. Cân nhắc kỹ:
  đây là chỗ dễ vô tình mở đường cho việc gộp bộ `neighborhood` vào bộ `evaluation`, mà HĐ-11.4
  cấm.
- **HĐ-13** manifest phải ghi biên độ nhiễu; hai run cùng seed nhưng khác σ là hai thí nghiệm.

## 5. Quan hệ với Task Neighborhood (N5) — đừng nhầm hai thứ

Cùng danh sách trục nhiễu, **khác mục đích, và không được trộn**:

| | Trả lời câu gì | Thuộc bộ nào |
|---|---|---|
| Nhiễu cảm biến ở đây | "cùng một hiện trường, robot chạy lần này khác lần kia thế nào" | `evaluation` |
| Task Neighborhood | "nếu bản đồ tôi đưa bị lệch chút thì khuyến nghị có đổi không" | `neighborhood` |

Cái đầu là biến thiên **trong** một deployment và **được** dùng cho cận trên va chạm. Cái sau là
bất định **về chính deployment** và HĐ-11.4 **cấm** đưa vào cận trên. Hiện thực chung một cơ chế
nhiễu là hợp lý; gộp chung một sample set thì không.

## 6. Vì sao ghi ra đây thay vì chỉ nhớ

Phase 1.4 đã dự đoán chính xác lỗi số mẫu hiệu dụng, ghi *"đã ghi lại để không rơi"*, và nó rơi.
Bài học đã ghi vào contract: **một ghi chú "nhớ làm ở phase sau" không phải một biện pháp bảo vệ.**

Nên bản kế hoạch này **không** phải biện pháp bảo vệ. Biện pháp bảo vệ đã được cài ở Phase 5.1
và đang chạy: `n_distinct_episodes` ở G2. Chừng nào nguồn nhiễu này còn thiếu, mọi bộ evaluation
của một candidate tất định sẽ **tự khai** số mẫu hiệu dụng thật của nó và G2 sẽ từ chối chặn.
Kế hoạch này là **cách chữa**; phép kiểm kia là thứ bảo đảm không ai quên rằng cần chữa.
