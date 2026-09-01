# Báo cáo — Dọn nợ trước Phase 5: anchor an toàn, anchor tiền, tốc độ, quy trình duyệt

> **Ngày:** 2026-08-10 · **Nhánh:** `plannerselector_p2`
> **Nguồn:** `docs/antongduy/notes/2026-08-10/tongduyan_quyet-dinh-truoc-phase-5.md` — sáu
> quyết định dev đã chốt sau khi Phase 4 đóng.
> **Contract:** `3.0.0` → **`4.0.0`** (MAJOR) · anchor file `v1.0` → `v1.2`
> **Suite:** `1876 passed, 6 skipped` (10 phút 17). Baseline sau Phase 4 là 1854 — **thêm 22
> test, không vỡ test nào**. Ruff sạch.

---

## 1. Bốn việc đã làm, hai việc không

| # | Quyết định | Đã làm gì |
|---|---|---|
| 1 | Anchor `min_clearance` sang thang mặt robot | ✅ `U_S` từ hằng số 0 thành 0,079 — mục 2 |
| 2 | Giữ khe `.gitignore` cho card + manifest | ✅ không cần đụng gì, đã đúng từ Phase 4 |
| 3 | Bypass quy trình ≥2 chữ ký | ✅ ghi ngoại lệ tường minh vào §0 — mục 5 |
| 4 | Cache lưới inflate | ⚠️ **làm (a), bỏ (b)** — mục 4, lý do là số đo |
| 5 | Manifest lưu context đầy đủ | ⏳ đúng kế hoạch, để Phase 6.1 cùng migration |
| 6 | Thêm anchor tiền | ✅ `business_adjusted` tính được thật — mục 3 |

---

## 2. `U_S` sống lại — và nó vẫn thấp, đúng như phải thế

Sửa đúng một dòng trong `contracts/metric_anchors.yaml`:

```yaml
min_clearance: {good: "${robot.radius}", bad: 0.0}   # v1.0: radius*2.0 / radius*1.05
```

Lý do đầy đủ đã nằm trong báo cáo Phase 4 mục 5.2, không nhắc lại. Cái đáng ghi ở đây là
**`bad: 0.0` không phải một con số được chọn.** `clearance_m` của HĐ-5 và tầng va chạm của
simulator cùng trả `khoảng_cách − bán_kính_robot − bán_kính_vật_cản`, nên 0,0 **là** biên va
chạm và đại lượng âm khi robot đã nằm trong vật cản. Sàn của thang là một sự thật hình học;
chỉ `good` mới là lựa chọn.

Điều đó kéo theo một hệ quả đẹp ngoài dự tính ở phép quét độ nhạy ±10% (HĐ-8.3 luật 3):
`scaled()` nhân cả hai đầu, nên `bad = 0` đứng yên và **chỉ `good` dịch**. Đó đúng là câu hỏi
mà phép quét muốn hỏi — "đầu thang mà ta *chọn* có chọn khéo không" — chứ không phải đi làm
nhiễu hình học. Có test khẳng định.

**Kết quả tính lại từ chính bộ trace cũ** (không mô phỏng lại — HĐ-5 đặt trace làm nguồn duy
nhất, nên nghĩa vụ "MAJOR ⇒ chạy lại lát cắt dọc" ở đây tốn vài giây):

```
HĐ-15.1(1) ✓ cả hai candidate chạy đúng cùng 30 episode context
HĐ-15.1(2) ✓ decision_utility tái lập tới 6 chữ số: 0.820518
HĐ-15.1(3) ✓ đủ sáu cổng cho 2 candidate, kèm N
HĐ-15.1(4) ✓ ΔU trung vị +0.025551, CI95 [+0.005207, +0.045315] trên 30 episode ghép cặp
HĐ-15.1(5) ✓ L_ref ≤ path_length + dung sai trên cả 60 episode thành công
HĐ-15.1(6) ✓ peak_search_nodes ≤ costmap_cells trên mọi episode
```

| | Trước (anchor v1.0) | Sau (v1.2) |
|---|---:|---:|
| `U_S` | **0,000000** | **0,078999** |
| `decision_utility` | 0,812618 | 0,820518 |
| ΔU trung vị | +0,027037 | +0,025551 |
| Khuyến nghị | `astar+dwa` CLEAR | `astar+dwa` CLEAR |

Ba điều đáng đọc trong bảng này:

**Khuyến nghị không lật.** Tôi đã cảnh báo trước rằng nó có thể lật, vì RRT\* có clearance
trung vị cao hơn (0,070 so với 0,041). Nó không lật, nhưng dấu vết của việc đó nằm ở dòng ΔU:
**biên thắng thu hẹp** từ +0,027 xuống +0,025. RRT\* thật sự có nhận được nhiều hơn từ lần
sửa này — chỉ là không đủ để bù chênh lệch latency.

**0,079 vẫn là một điểm an toàn thấp, và đó là số đúng.** Robot 0,52 m trong khe kệ hẹp nhất
0,68 m còn 0,04 m mỗi bên. Anchor mới cho khe đó chấm 0,154 trên thang clearance; trung bình
với `near_miss_rate` ra 0,079. Deployment này **thật sự** chật. Khác biệt so với trước không
phải là điểm cao hơn mà là **điểm phân biệt được** — trước đó mọi candidate đều 0,000 và
`w_S = 0,10` là một trọng số nhân với hằng số.

**`U_S` giờ mới có tư cách đi vào Phase 5.** Pareto (5.2) xét lấn át trên **từng** objective;
với `U_S ≡ 0` thì mọi cặp candidate hòa vĩnh viễn ở chiều an toàn và điều kiện
`∀j: LCB₉₅(ΔU_j) ≥ −ε` thành ra dễ thỏa một cách vô nghĩa. Sửa trước Phase 5 là đúng thứ tự.

### 2.1. Vì sao đánh MAJOR chứ không MINOR như tôi ước lượng trong notes

Bản ghi quyết định của tôi đề xuất MINOR và mời dev bác. Khi làm thì tôi tự bác mình.

Lập luận cho MINOR: anchor file có `version` riêng, HĐ-13 bắt manifest ghi
`anchor_config_version`, nên hợp đồng đã lường trước việc anchor đổi mà không cần bump MAJOR.

Lập luận thắng: §8.2 **in thẳng cặp số này trong hợp đồng**, và mọi `U_S` — do đó mọi
`decision_utility`, mọi ΔU, mọi nhãn CLEAR/NEAR_EQUIVALENT — tính dưới `v1.0` **không so sánh
được** với bản tính dưới `v1.2`. Đó đúng là định nghĩa "đổi ngữ nghĩa" mà §0 luật 2 viết. Dùng
ranh giới file để né nghĩa vụ của luật 3 là lách chính luật đó, trong khi ở đây nghĩa vụ ấy
gần như miễn phí.

## 3. Anchor tiền — phần khó không phải công thức, mà là chỗ đặt con số

`business_adjusted` trước đây validate đủ nhưng **từ chối tính**. Giờ tính được. Công thức là
phần dễ, đúng N3:

```
engineering_cost_per_mission = (tuning_wall_clock_h × engineer_cost_per_hour
                                + hardware_upgrade_cost) / deployment_horizon_missions
```

Phần đáng bàn là câu hỏi tôi đã nêu trong notes và đây là câu trả lời.

**Cám dỗ:** viết `engineering_cost_per_mission: {good: 0.0, bad: 5.0}` vào
`metric_anchors.yaml` cho xong.

**Vì sao đó là sai, và sai đúng vào luật của chính dự án:** mọi anchor khác trong file lấy
thang từ ngoài tập candidate — vật lý bài toán (đường dài hơn tối ưu 35% là đường tệ), hình
học robot, hoặc một ngưỡng deployment đã khai. **Không có sự thật nào nói một nhiệm vụ tốn 5
đồng là đắt.** Con số đó sẽ là nền tảng tự đặt ngân sách hộ khách hàng rồi chấm điểm khách
hàng theo ngân sách mình vừa đặt — đúng lỗi rank-reversal của HĐ-8.3 luật 1 trong bộ áo khác.

**Giải pháp — HĐ-8.3 luật 4 (mới):** metric đo bằng tiền thì `bad` **phải** là tham chiếu tới
ngân sách khách hàng khai, giống hệt cách metric có cổng neo vào ngưỡng cổng ở luật 2.

```yaml
engineering_cost_per_mission: {good: 0.0, bad: "${constraints.cost_per_mission_max}"}
```

Cưỡng chế bằng validator trong `AnchorSet`, không bằng lời dặn — viết số cứng ở đó là
`ValidationError` kèm câu *"Physics fixes what a bad clearance is; nothing fixes what an
expensive mission is except the customer saying so"*.

### 3.1. Một vấn đề phát sinh và cách xử lý: anchor không giải được

Thêm anchor trỏ vào `constraints.cost_per_mission_max` làm **hỏng mọi deployment chạy chế độ
`technical`** — họ không có lý do gì phải khai ngân sách, mà `resolve()` thì fail cả file khi
một tham chiếu không giải được.

Ba hướng đã cân nhắc, và vì sao chọn hướng ba:

1. *Cho `cost_per_mission_max` một giá trị mặc định* — nền tảng bịa ngân sách, đúng cái vừa
   cấm ở luật 4. Loại.
2. *Bỏ qua im lặng anchor nào không giải được* — mất anchor mà không có triệu chứng, đúng loại
   lỗi mà cả HĐ-8.3 tồn tại để chặn. Loại.
3. **Ghi lại là `unresolved` kèm lý do, và chỉ từ chối khi có ai chấm chính metric ấy** — kèm
   **tên trường còn thiếu**, không phải câu "thiếu anchor" chung chung.

Hướng ba đòi một phân biệt mà `getattr(obj, name, None)` không làm được: **trường có mà để
trống** (deployment không khai — unresolved) khác **trường không tồn tại** (lỗi chính tả —
vẫn fatal). Thêm sentinel `_MISSING` để tách hai ca. Có test cho cả hai chiều, gồm một test
khẳng định `${constraints.cost_per_mision_max}` (thiếu chữ `s`) vẫn nổ đúng như trước.

### 3.2. `currency` bắt buộc khai

Ba con số tiền cộng một ngân sách trần đem so với chúng, mà không nói đơn vị, là một phép so
xuyên tiền tệ chờ xảy ra. Nền tảng **không quy đổi và không giả định** đơn vị nào; nó bắt khai
`currency` và mang chuỗi đó lên card trong khối `declared_assumptions`.

### 3.3. β4 chấm trên đúng một thang, không bao giờ cả hai

`technical` chấm số giờ thô theo anchor `tuning_wall_clock_h`; `business_adjusted` **thay
thế** số hạng đó bằng `engineering_cost_per_mission`. Hai thang cho cùng một đại lượng, nên
cộng cả hai là nhân đôi trọng số công tinh chỉnh **ngay bên trong U_C** — đúng loại lỗi §17
cấm 9 chặn ở giữa các objective, nhưng ở một tầng sâu hơn nên dễ lọt hơn. Có test phát hiện
được nếu ai đó cộng nhầm: 80 giờ vượt `bad` của thang giờ nên `technical` chấm 0, trong khi
80 × 30 / 1.000 = 2,40 trên trần 10,0 chấm 0,76 — hai số khác nhau chứng minh một số hạng,
không phải hai.

### 3.4. Luận điểm của đề tài, viết thành hai bất đẳng thức

Đây là thứ N3 hứa và tới bản này mới chạy được — và là slide mở đầu của cả dự án:

```python
assert utility(tuned,   50_000) > utility(untuned, 50_000)
assert utility(untuned,    200) > utility(tuned,      200)
```

Hai candidate giống nhau trừ một đánh đổi: bản đã tinh chỉnh tốn 24 giờ công và chạy 10 ms,
bản tham số mặc định tốn 0 giờ và chạy 40 ms. **Không một số đo nào khác nhau giữa hai lần
chạy. Chỉ chân trời khai báo khác.** Trên 50.000 nhiệm vụ, 24 giờ là 0,0144/nhiệm vụ trên trần
1,0 — không đáng kể, bản nhanh thắng. Trên pilot 200 nhiệm vụ, cũng 24 giờ ấy là 3,60/nhiệm vụ
— áp đảo, bản mặc định thắng.

### 3.5. Chưa làm, và lý do hẹp hơn "chưa làm"

`travel_time_accounting: monetized_cost` **vẫn bị từ chối**. Quy tiền công tinh chỉnh cần đúng
hai khai báo mà `business_profile` đã có (đơn giá giờ công, chân trời). Quy tiền **thời gian di
chuyển** cần một khai báo thứ ba mà chưa profile nào mang: một nhiệm vụ throughput đáng bao
nhiêu tiền. Thiếu nó mà vẫn đẩy thời gian di chuyển ra khỏi O3 thì nó bị chấm bởi **không gì
cả** — tệ hơn hẳn để nguyên ở O3, nơi thang đo ít nhất là vật lý.

**Cũng chưa làm, có chủ ý: không thêm `cost_per_mission_max` vào
`profiles/warehouse_a_v1.yaml`.** Cơ chế đã có test đầy đủ, nhưng profile đó đại diện cho một
khách hàng, và đặt vào đó một ngân sách trần mà không lần chạy nào dùng thì chính là bịa một
con số vào đúng chỗ dễ bị đọc nhầm là thật nhất. Nó thuộc về Phase 7.4 khi dựng demo K1–K4.

## 4. Tốc độ: làm (a), rồi số đo giết (b)

Notes đề xuất làm (a) vector hoá `inflate` trước, đo lại, **rồi mới quyết** có cần (b) cache
`_planning_grid` không. Làm đúng thứ tự đó, và (b) chết.

**(a) — `OccupancyGrid.inflate` viết lại thành binary dilation.** Bản cũ là vòng lặp Python
lồng ba lớp: mỗi ô OCCUPIED nhân với ~350 offset trong disk bán kính 0,54 m ở 5 cm. Trên bản
đồ kho 800×500 = 400.000 ô, đó là ~140 triệu lượt thăm ô. `scipy.ndimage.binary_dilation` làm
đúng số lượt ấy bằng C. Đo trên chính bản đồ kho:

| | Thời gian | |
|---|---:|---|
| Vòng lặp cũ | **5.516,7 ms** | |
| `binary_dilation` | **35,5 ms** | **nhanh gấp 155 lần** |

**Đúng từng ô, không phải xấp xỉ.** Kiểm bằng hai cách: 15 lưới ngẫu nhiên (kích thước, độ phân
giải, bán kính, và cả ô UNKNOWN đều ngẫu nhiên) trùng khít 0 sai lệch, và bản đồ kho thật trùng
khít. Hai chỗ một phép dilation *có thể* lệch khỏi vòng lặp đều được kiểm riêng: disk đối xứng
nên không có chuyện gốc structuring element bị lật, và `binary_dilation` coi ngoài biên là
không-set, khớp với vòng lặp chỉ duyệt nguồn trong biên. Cả hai thành test thường trực —
`_inflate_by_definition` trong `tests/test_grid.py` là bản chậm-và-hiển-nhiên giữ lại **để so**,
không để dùng.

**(b) — không làm, và đây là lý do bằng số.** Đo lại một episode thật sau khi có (a):

| | Trước | Sau |
|---|---:|---:|
| Thời gian mỗi episode | ~20 s | **17,15 s** |
| Chi phí inflate mỗi lần | 5,52 s | 35,5 ms |

Cache `_planning_grid` cứu được nhiều nhất 35 ms trên một episode 17 s, tức **0,2%**, đổi lấy
một lớp cache có vòng đời và có khả năng trôi (stale) trên đúng đường dữ liệu mà HĐ-5 muốn
đơn nghĩa. Lý do làm nó đã biến mất cùng lúc với việc (a) chạy xong.

Ghi lại để Phase 5.1 biết: 300 episode × 2 candidate × 17 s ≈ **2,8 giờ** một lượt. Chi phí
chi phối giờ nằm ở vòng mô phỏng và DWA, **không** còn ở inflate. Muốn nhanh hơn nữa thì phải
đo lại xem nó nằm ở đâu, không đoán — đúng cách đã dùng ở đây.

## 5. Quy trình duyệt — ghi ngoại lệ thay vì tiếp tục vi phạm im lặng

§0 luật 4 đòi ≥2 người approve. Các bản từ `2.0.0` tới `3.0.0` đều được viết, hiện thực và
nghiệm thu trong cùng một luồng làm việc — điều khoản đó **đã bị vi phạm im lặng qua sáu lần
bump**. Dev chốt bypass, tạm thời một người duyệt là đủ.

Không im lặng thi hành. Ghi thành một khối ngoại lệ ngay dưới luật 4, kèm ngày, lý do, và —
quan trọng nhất — **ranh giới của cái được nới**:

> Điều **không** được nới cùng: mọi luật khác của mục 0 vẫn áp dụng nguyên vẹn — vẫn phải nêu
> rõ sửa hợp đồng nào và vì sao, vẫn bump semver đúng loại, và MAJOR vẫn bắt buộc chạy lại lát
> cắt dọc. Ngoại lệ này chỉ nói về **số chữ ký**, không nói về mức cẩn thận.

Kèm điều kiện gỡ: khi nhóm có ≥2 người đọc được contract thì tăng PATCH và xóa khối này.

Lý do viết ra thay vì lặng lẽ bỏ qua: một hợp đồng có điều khoản không ai theo thì mọi điều
khoản còn lại cũng mất trọng lượng. Một ngoại lệ có ngày tháng và điều kiện gỡ vẫn là hợp
đồng; một điều khoản bị lờ đi thì không.

## 6. Test

+22 test, chia ba nhóm:

- **Anchor an toàn (2):** thang mặt robot cho khe kệ thật 0,04 m điểm > 0 thay vì 0; chạm vật
  cản và nằm trong vật cản đều vẫn 0. Cộng một test khẳng định phép quét ±10% để yên sàn vật lý.
- **Anchor tiền (11):** luật 4 hai chiều (số cứng bị từ chối, file shipped tuân thủ) · anchor
  không giải được (4 test, gồm ca lỗi chính tả vẫn fatal và ca lý do sống sót qua `scaled()`) ·
  business mode (7 test: khấu hao, giá phần cứng một lần, **lật khuyến nghị theo horizon**, từ
  chối khi chưa khai ngân sách, một-thang-không-phải-hai, nhãn card, bắt buộc `currency`).
- **`inflate` (2):** trùng khít bản định nghĩa trên lưới nhiều vật cản qua 5 bán kính, và khi
  disk tràn khỏi mọi cạnh bản đồ.

Test cũ sửa **có chủ ý**, không phải sửa cho xanh:

- `test_safety_is_half_clearance_half_near_miss` — điểm giữa thang đổi từ 0,3965 sang 0,13 vì
  thang đổi. Ý định test không đổi.
- `test_the_preference_profile_can_flip_the_ranking` — hai fixture clearance 0,52 / 0,30 đều
  vượt `good` mới (0,26) nên cùng chấm 1,0 và không còn phân biệt được gì. Đổi sang 0,26 / 0,04.
  Test này khẳng định luận điểm trung tâm của đề tài nên **phải** giữ cho nó thật sự phân biệt,
  không chỉ giữ cho nó xanh.
- `test_business_mode_is_validated_but_not_computable_yet` → `test_monetized_travel_time_is_still_refused`.
  Test cũ khẳng định đúng cái vừa được hiện thực.

## 7. Trạng thái

| Phase | Trạng thái |
|---|---|
| 1 Schema gốc · 2 Đường dữ liệu · 3 Decision core | ✅ |
| 4 Lát cắt dọc | ✅ — 6/6 xanh, đã chạy lại dưới anchor `v1.2` |
| **Nợ trước Phase 5** | ✅ đóng, trừ nghĩa vụ manifest để Phase 6.1 |
| 5 Engine đầy đủ | sẵn sàng mở |

**Không còn blocker cho Phase 5.** `U_S` phân biệt được nên Pareto (5.2) và sensitivity (5.3)
có đủ bốn objective để làm việc.

Hai thứ Phase 5 nên biết trước:

1. **5.1 tốn ~2,8 giờ một lượt** (300 × 2 × 17 s). Không còn tối ưu rẻ nào nằm sẵn trên bàn;
   muốn nhanh hơn phải profile lại vòng mô phỏng.
2. **Nghĩa vụ manifest (HĐ-13) vẫn treo.** Từ giờ tới Phase 6.1, manifest chưa tái lập được
   metric một cách độc lập nếu mất object `EpisodeContext` trong bộ nhớ. Lát cắt chạy một mạch
   nên không sao; nó chỉ cắn khi có run chạy qua worker.
