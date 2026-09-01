# Báo cáo — Phase 5.3: Độ nhạy trọng số và anchor (HĐ-11.5)

> **Ngày:** 2026-08-10 · **Nhánh:** `plannerselector_p2`
> **Plan nguồn:** `plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **Phase 5.3**
> **Contract:** `4.0.0` → **`4.1.0`** (MINOR — HĐ-11.5 viết đủ, không đổi trường nào)
> **Vì sao làm trước 5.1 và 5.2:** dev không có ~3 giờ máy rảnh mà 5.1 đòi. 5.3 không đụng
> simulator, chạy trên bộ 30 episode đã có trên đĩa, và là thứ tài liệu mẹ gọi là *"tính năng
> quan trọng nhất của cả dự án"* (N1).

---

## 1. Vì sao thứ tự backlog nhường được

Backlog xếp 5.3 sau 5.2 với lý do *"nhãn Pareto đi vào card mà sensitivity quét trên card"*.
Đọc lại thì đó là thuận tiện, không phải phụ thuộc: Pareto quyết `pareto_label` và
`alternative`; sensitivity quyết ba trường `evidence.*_stability`. Hai nhánh khác nhau của
HĐ-12, không nhánh nào đọc nhánh kia.

Cái 5.3 **thật sự** cần là (a) objective theo từng episode và (b) hai candidate qua cổng —
cả hai có từ Phase 3.3 và Phase 4.

---

## 2. Kết quả trên kho tham chiếu

Chạy `--reuse-traces` trên đúng bộ 30 episode của Phase 4, thêm khoảng **4 giây**:

```
status:         CLEAR_RECOMMENDATION
recommended:    astar+dwa (ac187ee7a77e)
decision_utility: 0.820518
weight margin:  0.2606
  Để 2baaad3628e1 lật ngược khuyến nghị, trọng số w_s phải tăng từ 0.10 tới 0.33
anchor ±10%:    unchanged_at_±10%
  scale left the domain under the shift: ['success_rate']
```

Sáu tiêu chí HĐ-15.1 vẫn xanh, `decision_utility` không đổi tới chữ số cuối — sweep chỉ đọc,
không sửa gì trên đường chính.

**Dòng thứ hai là toàn bộ điểm của N1.** Trước phase này, câu trả lời cho *"anh dựa vào đâu mà
nói trọng số an toàn là 0,10?"* là im lặng. Giờ là: *anh không cần biết nó là bao nhiêu — chừng
nào anh chưa coi an toàn quan trọng gấp hơn ba lần con số anh đã khai, khuyến nghị vẫn là
A\*+DWA.* Người đọc ra quyết định được mà không phải tự chấm điểm mình.

Biên 0,2606 > ngưỡng 0,10 nên **không** dán nhãn `SENSITIVE_TO_PREFERENCES`. Hướng lật là
`w_s` **tăng**, hợp lý: RRT\* có clearance trung vị cao hơn (0,070 so với 0,041), nên coi trọng
an toàn hơn thì nó thắng.

---

## 3. Bốn quyết định thiết kế

### 3.1. Sweep chạy lại pipeline thật, không tự tính lại utility

Cách rẻ là lấy bốn objective đã lưu rồi nhân với trọng số mới. Cách đó tạo **bản sao thứ hai
của công thức utility**, và hai bản sao sẽ trôi khỏi nhau — đúng lỗi dự án đã phải sửa một lần
ở luật ghép cặp (Phase 3.4 mục 2). Nên sweep gọi thẳng `build_evidence` → `recommend` với đúng
một đầu vào bị đổi.

Cái giá là ~450 lần chạy lại tầng quyết định cho một sweep đầy đủ. Trên 30 episode × 2
candidate đó là **4 giây**, vì không lần nào chạm simulator.

### 3.2. Quét lưới trước, chia đôi sau — không phải ngược lại

Cám dỗ là chia đôi ngay: tìm biên lật bằng bisection từ [0, 1]. Sai, vì **khuyến nghị không
đảm bảo đơn điệu theo độ lệch**. Bisection giả định đúng một lần cắt; gặp hai lần cắt là nó
bước qua cả hai và báo cáo *"ổn định"* — sai theo đúng chiều nguy hiểm nhất, vì một biên rộng
sai còn tệ hơn không có biên nào.

Nên: quét lưới 40 bước (bước 0,025 — nhỏ hơn ngưỡng 0,10 mà nhãn phụ thuộc vào, nên một lần
lật đủ sức đổi nhãn không thể lọt giữa hai mẫu), rồi chia đôi **bên trong khoảng lưới đã bắt
được**. Lưới quyết định cái gì có thể bị bỏ sót; bisection chỉ làm sắc nét cái lưới đã tìm ra.

Có test khẳng định biên báo cáo là biên thật: ngay dưới nó khuyến nghị còn đứng, ngay trên nó
đã đổi.

### 3.3. Mỗi hướng quét chỉ đổi đúng một giả định

Khi `w_s` đi về một cực, ba trọng số còn lại **giữ nguyên tỷ lệ với nhau** và chia phần dôi.
Nếu chúng tự sắp xếp lại thì một lần lật không quy được cho trọng số nào — báo cáo mất tính
quy trách nhiệm, là toàn bộ giá trị của nó.

`margin = 1.0` khi không hướng nào lật. Đây là **phát biểu thật, không phải phép tìm kiếm bỏ
cuộc**: `shift = 1` là cực của simplex (trọng số về 0, hoặc lên 1 với ba cái kia về 0), nên
"không lật ở đâu trong tám hướng" nghĩa là không bộ trọng số không âm nào trên các tia đó đổi
được kết quả. Có test dùng một candidate tốt hơn ở **mọi** objective và khẳng định đúng 1.0.

Một ca biên phải xử lý có ý thức: profile dồn hết trọng số vào một objective rồi quét **khỏi**
nó — không còn tỷ lệ nào để giữ. Chia đều cho ba cái còn lại, vì mọi lựa chọn khác là bịa ra
một thứ tự ưu tiên người dùng chưa từng phát biểu.

### 3.4. Tiêu chí lật là candidate, không phải nhãn

Một lần quét giữ nguyên candidate nhưng đi từ `CLEAR_RECOMMENDATION` sang `NEAR_EQUIVALENT`
**không đổi lời khuyên**. Tính nó là bất ổn định sẽ làm mọi biên trông tệ hơn thực tế, và biên
bị thổi phồng theo chiều bi quan vẫn là biên sai.

---

## 4. Phát hiện: phép quét ±10% giết chết một metric

`anchor_stability` báo `unchanged_at_±10%` — nhưng kèm dòng thứ hai:

```
scale left the domain under the shift: ['success_rate']
```

`success_rate` neo ở `{good: 1.00, bad: 0.95}`. Nhân cả hai đầu +10% ra `{1.10, 1.045}` — **cả
thang nằm ngoài miền giá trị mà metric có thể nhận**, vì tỷ lệ thành công không bao giờ vượt
1,0. Mọi giá trị thật clip về 0, `U_R` chết cho **cả hai** candidate.

Khuyến nghị "không đổi" dưới phép dịch đó, nhưng **không đổi vì metric đã chết, không phải vì
lựa chọn bền**. Đây đúng loại kết luận trấn an mà cả HĐ-8.3 tồn tại để chặn: một dòng
`unchanged_at_±10%` trên card, đọc một mình, nói rằng thang đo đã được thử thách và đã đứng
vững. Nó không đứng vững; nó vắng mặt.

**Chưa sửa, có chủ ý.** Sửa đúng là cho `ResolvedAnchors.scaled` biết metric nào bị chặn trên —
tức đổi ngữ nghĩa HĐ-8.3 luật 3 ⇒ MAJOR, và nó nằm ngoài phạm vi 5.3. Cái làm được trong phạm
vi là **không để nó vô hình**: `AnchorStability.degenerate_metrics` liệt kê ra, lát cắt in ra,
và HĐ-11.5 giờ bắt buộc báo cáo nó.

**Cần dev quyết trước khi card này đến tay người ngoài.** Hai hướng:

1. **Kẹp phép dịch theo miền của metric** — `success_rate` chỉ dịch được đầu `bad`, giống cách
   `min_clearance` chỉ dịch được đầu `good` vì `bad = 0` là biên va chạm. Đúng về ngữ nghĩa,
   nhưng là MAJOR.
2. **Giữ nguyên phép dịch, để nguyên cảnh báo** — rẻ, trung thực, nhưng người đọc card phải
   hiểu dòng cảnh báo, và người đọc card là PM và khách hàng.

Tôi nghiêng về (1) và đề nghị gộp vào lần MAJOR tiếp theo thay vì bump riêng.

---

## 5. Hai chốt chặn chống nói dối bằng số

Ba trường stability trên card có một kiểu hỏng riêng mà `null` không có: **một con số đúng của
run khác**. `null` đọc là "chưa đo"; một con số sai đọc là sự thật.

**Chốt 1 — sweep phải thuộc về đúng run đang in card.** Cả hai sweep tự tính lại khuyến nghị
gốc, nên `sweep.recommended_id` khác `card.recommended_id` không phải sai số làm tròn — nó
nghĩa là số đến từ một field khác, một bộ anchor khác, hoặc một settings khác.
`build_decision_card` từ chối. Test cả hai sweep.

**Chốt 2 — kết quả quét tự khai là kết quả quét.** Một lần chấm dưới trọng số đã dịch ghi
`preference_profile: "kho_ban_dem (perturbed)"`, không ghi `"kho_ban_dem"`. Cùng luật mà
`ResolvedAnchors.scaled` đã theo từ Phase 3.1 khi đóng dấu `v1.2±+10%` vào version string.

---

## 6. Một lỗi thật do test bắt được

`AnchorStability.verdict` in cứng chuỗi `"unchanged_at_±10%"` — kể cả khi được gọi với
`sweep=0.30`. Card sẽ ghi `±10%` về một thí nghiệm 30%.

Lộ ra khi tôi dò biên độ để dựng fixture cho test "phép quét làm lật khuyến nghị": chạy
`sweep=0.5` và thấy verdict vẫn nói `±10%`. Sửa: `AnchorStability` mang theo `sweep` và dựng
chuỗi từ nó; ở mặc định 0,10 nó ra đúng chuỗi HĐ-12 viết trong ví dụ. Có test khẳng định
`sweep=0.30` ra `unchanged_at_±30%`.

Loại lỗi này là loại không bao giờ nổ — chỉ ghi sai vào một hồ sơ mà ba tháng sau không ai
dựng lại được.

---

## 7. Fixture knife-edge được **đo**, không được đoán

Test `SENSITIVE_TO_PREFERENCES` cần một cặp candidate mà biên lật thật sự dưới 0,10. Lần đầu
tôi đoán hai giá trị clearance sát nhau (0,128 / 0,132) — chạy ra `margin = 1.0`, tức fixture
không lật ở đâu cả và test khẳng định nhãn cảnh báo trên một trường hợp không hề nguy hiểm.

Dò bằng số: giữ clearance A = 0,13 / B = 0,26 rồi quét latency của B.

| `p99_latency_ms` của B | margin | hướng lật |
|---:|---:|---|
| 30,0 | 0,2405 | `w_c` tăng |
| **33,0** | **0,0626** | `w_c` tăng 0,35 → 0,391 |
| 36,0 | 0,0153 | `w_s` tăng |

Chọn 33,0. Cùng fixture đó cũng lật dưới phép quét anchor ±10% thật (`changed_at_-10%`), nên
test cảnh báo anchor cũng chạy trên một ca thật thay vì trên một biên độ phóng đại.

**Một fixture được khẳng định là knife-edge thì phải thật sự là knife-edge**, nếu không thì
test xanh mà thứ nó bảo vệ không tồn tại.

---

## 8. Test

`tests/test_sensitivity.py`: **49 test**, cộng 4 test chốt chặn card ở `test_decision_card.py`.

- **Số học trọng số (11):** tổng luôn bằng 1 qua 4 trọng số × 2 hướng × 3 độ lệch · lệch 0 là
  vector gốc · lệch 1 tới đúng cực · ba cái còn lại giữ tỷ lệ · β đi qua nguyên vẹn (nếu dựng
  lại từ mặc định sẽ âm thầm phá renormalise của `measured_only`) · vector suy biến chia đều ·
  lệch ngoài [0, 1] bị từ chối.
- **Biên trọng số (6):** tìm được lật và in đúng câu N1 · **biên là biên thật** (dưới thì giữ,
  trên thì đổi) · candidate lấn át mọi objective ra đúng 1.0 · knife-edge ra nhãn contract ·
  báo cáo mọi hướng lật chứ không chỉ hướng gần nhất · tái lập.
- **Anchor (4):** chuỗi contract · lật nêu đúng hướng · **verdict không bao giờ khai sai biên
  độ của chính nó** · liệt kê metric thang chết, và `min_clearance` **không** nằm trong đó (sàn
  vật lý 0,0 nên chỉ đầu trên dịch).
- **Từ chối (3):** một survivor không sweep được · candidate trượt cổng không bao giờ vào sweep
  (HĐ-7: cổng không phải chuyện sở thích) · thiếu metric thì từ chối chứ không bỏ qua.
- **Card (4):** null khi chưa quét · in ra khi đã quét · sweep của run khác bị từ chối (cả hai
  loại).

---

## 9. Chưa làm — cố ý

- **`robustness_margin`** — trường thứ ba của HĐ-11.5, cần Task Neighborhood (N5), thuộc Phase
  5.1 trở đi. Vẫn `null`.
- **Sửa phép dịch anchor cho metric bị chặn trên** — mục 4, cần dev quyết, và là MAJOR.
- **Quét đồng thời nhiều trọng số** — hiện mỗi hướng đổi đúng một trọng số, đúng như HĐ-11.5
  viết. Quét cả simplex là bài toán khác và đắt hơn nhiều bậc.

## 10. Trạng thái

| Phase | Trạng thái |
|---|---|
| 1–4 | ✅ |
| **5.3 Sensitivity** | ✅ — hai trường stability đã có số thật trên kho tham chiếu |
| 5.1 Evaluation distribution N=300 | chưa — cần ~2,8 giờ máy rảnh |
| 5.2 Pareto | chưa — code được ngay, kết luận cần 5.1 |

**Khi 5.1 chạy, sensitivity không phải viết lại gì**: nó chạy lại trên bộ 300 episode và cho
số chặt hơn miễn phí.

Nhắc lại ràng buộc của 5.1, vì nó vừa suýt bị vi phạm lần nữa: HĐ-7.4 đòi mọi candidate chạy
cùng máy cùng mức cấp CPU, nên 2,8 giờ đó cần **máy rảnh** — không vừa chạy vừa code, không
vừa chạy vừa chạy test. Đó chính là lỗi đã loại nhầm A\* ở G4 trong lần chạy đầu của Phase 4.
