# Vì sao một thuật toán thắng hay thua — số liệu ghép với bản chất

**Ngày:** 2026-08-19 · **Commit:** `faf7443` · 14 file, +885
**Module:** `packages/benchmark/planbench_benchmark/outcome.py` — 7 luật

---

## 1. Khoảng trống

Card nêu tên người thắng; bảng cổng nêu ai bị loại ở đâu. **Không ai nói
vì sao.** Người đọc không phân biệt được "kết quả này đúng như bản chất
hai thuật toán dự đoán" với "kết quả này bất thường, đáng đi tìm hiểu".

## 2. Hai thanh ghi, kiểm được riêng biệt

**Số liệu** — từ báo cáo đã lưu: chỉ số nào tách hai phương án, cách biệt
bao nhiêu, biên có vượt nhiễu không.

**Bản chất** — bảng `TRAITS`, 6 họ thuật toán. Mỗi mục **khai neo**: cờ
registry trước, cơ chế giáo khoa sau.

```python
"rrtstar": {
  "weaknesses": ("stochastic: một seed là một lần bốc...",
                 "đuôi độ trễ là cái giá của lấy mẫu..."),
  "anchor": "registry marks stochastic_global_planner=True; ..."
}
```

Bảng trait không neo là folklore của model khoác áo hằng số. Có test đối
chiếu neo với chính registry — cờ đổi thì bảng **đỏ ngay** thay vì tiếp
tục kể một tính chất đã biến mất.

## 3. Hai từ chối là cốt lõi, không phải tính năng phụ

**Bị loại ở cổng không bao giờ được kể là bị đánh bại.** Một phương án
chưa qua vòng loại thì chưa hề được đem so — "X thắng Y" là câu về một
phép so không xảy ra.

**Khoảng tin cậy chứa 0 không bao giờ nêu tên người thắng**, dù điểm ước
lượng nói gì.

## 4. Chạy thật trên báo cáo đã lưu

`open_hall_v2`, nơi `astar+dwa` trượt G3:

```
[material  ] OC_ELIMINATED_BY_GATE
   astar+dwa không thua xếp hạng — nó bị loại ở G3
   vì   : ...điểm yếu đã biết của dwa — tối ưu một horizon, nên cửa hẹp
          và ngõ cụt nó không nhìn qua được thành chỗ kẹt
   KHÔNG: mô tả đây là stack kia "thắng" — không ai được so

[disclosure] OC_METRIC_DRIVER
   tỷ lệ thành công là thứ tách hai bên: rrtstar+dwa 100% vs astar+dwa 70%

[disclosure] OC_SAME_CONTROLLER_ISOLATES_PLANNER
   cả hai dùng chung bộ điều khiển, nên kết quả này là astar vs rrtstar
```

## 5. `dwa_predictive` — bảng trait bắt được chuyện của An

Test *"mọi thành phần stack trong registry phải có trait"* đỏ, vì merge
mang về `dwa_predictive` mà bảng chưa có. Đọc mô tả registry thì đó là
một câu chuyện đầy đủ, và bảng trait giờ ghi đúng nó:

- ý tưởng đúng: với perception hoàn hảo, **11/11** cặp bất đồng nghiêng
  về nó (p = 0.0005, `intersection`, 15-08)
- rút lui 16-08: tracker LiDAR báo tới **1,9 m/s** chuyển động trên kho
  tĩnh, và không giữ được chút lợi thế nào

Nếu không có test đó, bảng sẽ kể một thế giới bảy stack bằng sáu mục.

## 6. Đến được người dùng ba đường

`GET /decisions/{id}/outcome` (kèm `use_model`) · panel *"Vì sao thắng,
vì sao thua"* trên trang run · tool chat `get_outcome`.

Hỏi trong chat *"vì sao rrtstar+dwa tốt hơn astar+dwa?"* → Gemini gọi 4
tool và trả lời từ số liệu thật: 100% vs 50%, cả 3 lần trượt cùng lý do
`stuck`, A* nhanh hơn ~5,65 ms vs ~6,69 ms p99 nhưng độ ổn định kém xa.
