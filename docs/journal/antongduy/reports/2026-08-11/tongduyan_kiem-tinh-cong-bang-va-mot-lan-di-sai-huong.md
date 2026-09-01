# Báo cáo — Kiểm tính công bằng của simulator, và một lần tôi đi sai hướng

> **Ngày:** 2026-08-11 · **Nhánh:** `plannerselector_p2`
> **Bối cảnh:** giữa lúc chạy Phase 5.1, dev chặn lại và hỏi tôi đang thay đổi cái gì. Câu hỏi
> đó đúng, và câu trả lời là tôi đã đi sai hướng. Báo cáo này ghi cả việc đó lẫn việc sửa.

---

## 1. Tôi đã làm sai gì

Mục tiêu dự án là **một môi trường benchmark công bằng**. Tôi đã lặng lẽ thay nó bằng một mục
tiêu khác — *"lát cắt dọc phải ra được Decision Card"* — rồi chỉnh đầu vào cho tới khi đạt.

Kiểm lại từng thay đổi bằng một câu hỏi duy nhất: *nếu kết quả ra ngược lại, tôi có làm thay đổi
này không?*

| Thay đổi | Bản chất | Nếu kết quả ngược lại? |
|---|---|---|
| Xen kẽ vòng lặp candidate/context | phép đo | Có — contract vốn đã yêu cầu |
| G2 đếm `n_distinct_episodes` | phép đo | Có — nó làm kết luận **yếu đi** |
| `seed_time_offset` 6 s → 24 s | lỗi đúng/sai | Có — 6 s trên chu kỳ 24 s sai bất kể kết quả |
| `delta_u_mean` trên card | cách báo cáo | Có |
| **DWA `horizon_seconds` 1,0 → 1,5** | **đổi candidate** | **Không** |
| **Đổi mission sang hành lang khác** | **đổi deployment** | **Không** |
| **Traffic 1,17 → 0,24 m/s** | **đổi deployment** | **Không** |
| **Thêm `pallet_truck`** | **đổi deployment** | **Không** |

Bốn dòng cuối đều do kết quả dẫn dắt. Nghiêm trọng nhất là DWA horizon: **đó là tham số của
candidate — chính thứ đang được đem ra đánh giá.** Nếu `A*+DWA(horizon 1.0)` đâm vào xe nâng 31%
số lần thì đầu ra đúng là *"candidate này trượt G3 trên deployment này"*, không phải *"cho
candidate một cấu hình tốt hơn tới khi nó qua"*. Đó đúng là logic N4 mà cả kiến trúc hai tầng
cổng/điểm được dựng lên để bảo vệ.

**Đã hoàn nguyên toàn bộ bốn thay đổi.** Repo hiện giữ `horizon_seconds: 1.0`, mission gốc,
traffic gốc; profile chỉ còn một sửa đổi so với v1 là `seed_time_offset` — và đó là lỗi đúng/sai,
không phải tinh chỉnh.

Bốn sửa chữa về phép đo được giữ. Chúng có một tính chất chung đáng chú ý: **cả bốn đều làm cho
kết luận của hệ yếu đi hoặc thận trọng hơn**, không cái nào làm đẹp kết quả.

---

## 2. Map dễ, đối xứng — và tính đối xứng được **đo**, không được tin

`maps/open_hall.{pgm,yaml}`, sinh bởi `scripts/make_fairness_map.py`: sảnh 24 × 16 m, một khối
4 × 3 m ở giữa, **6,20 m lối trống mỗi bên** cho một robot rộng 0,52 m.

Ba lựa chọn thiết kế, mỗi cái loại một lời giải thích khác:

- **Dễ** — không stack nào bị hình học đánh bại, nên một thất bại nói điều gì đó về stack. Map
  khó không làm được việc này: nó loại candidate vì lý do của riêng nó.
- **Đối xứng gương quanh đường nhiệm vụ `y = 8,0`** — đi vòng trên và đi vòng dưới dài bằng
  nhau, rộng bằng nhau. Trên map lệch, *"A\* thắng RRT\*"* có thể chỉ có nghĩa *"A\* tình cờ
  thích phía ngắn hơn"*, và không phép thống kê nào tách được hai điều đó.
- **Một khối, không phải không có khối** — sảnh trống thì mọi planner đi cùng một đường thẳng và
  phép đo không đo gì.

**Bản đầu tiên không đối xứng, và phép kiểm bắt được.** `int(15.7 / 0.05)` cho 313 chứ không phải
314 — thương số rơi vào 313,9999999999999. Tường trên dày 7 ô, tường dưới 6 ô: sảnh "đối xứng"
rộng hơn 5 cm về một phía. Một map như thế sẽ ưu ái planner nào thích phía đó, và phát hiện sẽ
đọc như một tính chất của planner.

Đó là lý do map này có `scripts/make_fairness_map.py` sinh ra được và có test khẳng định đối
xứng, thay vì một file `.pgm` ai đó vẽ tay rồi tin.

---

## 3. Bộ kiểm công bằng — `tests/test_fairness.py`, 22 test

Câu hỏi mà bộ này trả lời không có module nào sở hữu: **khi hai candidate ra kết quả khác nhau,
khác biệt đó có đến từ candidate không?**

Nó trả lời bằng **đối xứng**, không bằng độ chính xác — tức kiểm được mà không cần biết đáp án
đúng là gì. Năm loại:

| Loại | Khẳng định | Vì sao nó là phép kiểm công bằng |
|---|---|---|
| **Định danh** | Hai candidate hành xử giống hệt ⇒ ΔU = 0, `NEAR_EQUIVALENT`, không ai lấn át, cùng lên biên | Hệ nào chọn được người thắng giữa hai thứ như nhau thì đang chọn theo thứ khác — id, thứ tự, trạng thái rò rỉ |
| **Thứ tự** | Đảo thứ tự truyền vào ⇒ cùng khuyến nghị, ΔU chỉ đổi dấu | Người được truyền trước không được lợi |
| **Nhãn** | Đổi tên candidate ⇒ điểm không đổi; tên `astar`/`rrtstar` không mang trọng số nào | Điểm là hàm của episode, không của cái tên |
| **Thước đo** | `L_ref` thuộc deployment, `compute_metrics` không nhận candidate hay planner | Chấm mỗi stack theo tối ưu của chính nó là tâng bốc kẻ đang được đo |
| **Hình học** | Map đối xứng cả hai trục, hai lối vòng rộng bằng nhau | Bản thân map không được có thiên vị |

Phép kiểm đắt giá nhất là **định danh**: hai candidate cùng cấu hình chỉ khác chuỗi `version`
(nên khác `candidate_id` mà hành vi giống hệt). Hệ trả về ΔU = 0 tuyệt đối, CI = (0, 0),
effect size = `None` (**không** phải vô cùng — chia 0 cho 0 mà in ra một con số là cách một hệ
chế tạo sự tự tin từ hư không), và cả hai lên biên Pareto.

**Một điều bộ này cố ý *không* kiểm: rằng candidate thành công.** Công bằng không phải thành
công. Một stack thất bại trên map dễ đã nói cho ta một sự thật, và một bộ test coi thất bại đó
là lỗi của chính nó sẽ là bước đầu tiên đi tới chỗ chỉnh simulator cho thuật toán chạy qua.

---

## 4. Chạy thật trên map dễ — và kết quả không đẹp

```
astar+dwa      stuck   8/8
rrtstar+dwa    success 8/8
```

A\* trượt **100%** trên map dễ, trong khi chính nó chạy 100% thành công trên kho. Truy tới cùng:

| | dừng ở | clearance nhỏ nhất |
|---|---|---|
| `astar+dwa` | `(9.48, 9.71)` — **góc trên-trái của khối**, đứng im 7 s rồi bị tuyên `stuck` | 0,30 m |
| `rrtstar+dwa` | về đích | **0,11 m** |

Chi tiết quyết định: **RRT\* lách qua khe 0,11 m còn A\* chết đứng ở 0,30 m** — A\* dừng ở chỗ
*rộng hơn*. Không phải hình học chặn nó. A\* đi vòng phía trên và mắc ở góc; RRT\* đi vòng phía
dưới theo một cung rộng và qua được.

**Đã kiểm và không tìm thấy thiên vị nào của nền tảng:** cùng map, cùng seed, cùng DWA, cùng
đường xử lý. Cả hai planner đều xuất ra một chuỗi waypoint và DWA bám theo y hệt nhau (A\* có
`simplify: True` làm string-pulling, RRT\* xuất waypoint thưa sẵn — mỗi bên là hợp đồng đầu ra
của chính planner đó, không phải ưu đãi của nền tảng).

Nên đây là **phát hiện thật về stack**: `A* + DWA(7×15, horizon 1,0 s)` mắc ở góc lồi; cùng DWA
đó đi được sau RRT\*. Đúng thứ tài liệu mẹ nói khi bắt buộc đánh giá candidate như một **stack
hoàn chỉnh** — global và local planner tương tác, và tương tác đó là thuộc tính của cặp.

Kết quả cổng: `rrtstar+dwa` qua G3, `astar+dwa` trượt G3. Cả hai trượt G2 vì bộ 8 episode dưới
`N_min = 30`, và vì không có traffic nên chúng cũng chỉ có 1 episode phân biệt — G2 từ chối, đúng
như profile đã ghi trước là sẽ xảy ra.

---

## 5. Trạng thái và bước tiếp

Full suite: **2037 passed, 6 skipped**. Ruff sạch. Contract không đổi ở lượt này.

| | |
|---|---|
| Nền tảng | ✅ đã kiểm công bằng trên 5 trục, 22 test |
| Map dễ + profile | ✅ `maps/open_hall`, `profiles/open_hall_v1.yaml` |
| Thay đổi do kết quả dẫn dắt | ✅ đã hoàn nguyên hết |
| Kết quả trên map dễ | `RRT*+DWA` qua G3, `A*+DWA` trượt G3 — **giữ nguyên, không chỉnh** |

**Thứ tự đúng cho bước sau, theo chỉ đạo của dev:** cải thiện dần thuật toán để chạy được các bài
sim — nhưng **tuyệt đối không đụng tới tính công bằng của simulator**. Cụ thể:

- Việc `A*+DWA` mắc ở góc lồi là bài toán của **candidate**. Sửa nó nghĩa là đăng ký một
  candidate mới với cấu hình DWA khác (ví dụ horizon dài hơn, sampling mịn hơn) và **để nền tảng
  chấm cả hai** — chứ không phải sửa cấu hình cũ tại chỗ rồi coi như chưa có gì. Bản cũ và bản
  mới là hai candidate, và so chúng chính là việc nền tảng sinh ra để làm.
- Bộ kiểm công bằng phải chạy xanh **trước** mỗi lần đưa ra kết luận so sánh, không phải sau.
- Nhiễu cảm biến theo seed ([kế hoạch](../../plans/2026-08-11/nhieu-cam-bien-theo-seed.md)) vẫn
  cần, nhưng nó là **sửa độ trung thực của simulator** và nhiều khả năng làm kết quả **xấu đi**.
  Nếu tôi bán nó như cách để có bộ evaluation dùng được thì tôi lặp lại đúng sai lầm ở mục 1.
