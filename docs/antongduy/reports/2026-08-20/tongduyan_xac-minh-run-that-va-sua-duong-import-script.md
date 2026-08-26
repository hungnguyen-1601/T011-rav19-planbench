# Xác minh trên run thật — và một regression khiến mọi sweep đã gãy từ lâu

**Ngày:** 2026-08-20 · **Nhánh:** `tongduyan_3` · Nối tiếp E4.3

**Trạng thái:** xong, **chưa commit** phần sửa. Full suite chưa chạy.

Việc này **không cần plan** — không phải feature, là xác minh end-to-end thứ tới giờ
mới chỉ được assert trên fixture dựng tay.

---

## 1. Regression tìm được ngay bước đầu: sweep script không import nổi

Chạy `scripts/compare.py` lần đầu sau E4.1/E6b:

```
ModuleNotFoundError: No module named 'planbench_explanation'
```

**Vì sao không ai thấy.** Repo này *không đóng gói* — `pyproject.toml` nói rõ vậy.
Test lấy đường dẫn import từ `[tool.pytest.ini_options] pythonpath`. Script thì
không: mỗi script mang **bản sao riêng** của danh sách thư mục nguồn trong một
preamble `sys.path`.

Đó là **một sự thật bị nhân bản ra tám file**, và nó đã trôi. Từ lúc recorder của
tầng giải thích được nối vào `planbench_benchmark` — `episode.py` import
`planbench_explanation.sidecar_writer`, `selection.py` import packet builder —
**mọi sweep thật đều gãy**, trong khi full suite vẫn xanh suốt thời gian đó, vì
pytest cấp đúng cái đường dẫn mà script thiếu.

Sửa xong `packages/explanation` thì lộ tiếp `packages/plugin_sdk`. Cùng một lớp lỗi.

### Chặn lại bằng test, không phải bằng trí nhớ

`tests/test_script_import_paths.py` đọc preamble của từng script bằng `ast` (không
import — import sẽ *chạy* chính thứ đang kiểm) rồi so với `pythonpath` của suite.

Nó phát hiện thêm **4 entry thiếu** mà tôi chưa nhìn ra:
`services/tracking`, `services/agent_service`, `apps/api`, và `ml` (ở
`vertical_slice.py`).

Kiểm **bao hàm** chứ không kiểm khớp chính xác: tự suy ra script nào *cần* thư mục
nào là dựng lại đồ thị import ở một chỗ thứ hai — một ý kiến thứ hai về thứ mà
interpreter đã sở hữu, và sẽ phải suy lại mỗi lần một package mọc thêm phụ thuộc.
Thừa một thư mục trên `sys.path` không tốn gì; thiếu một cái thì mất cả sweep.

Tổng: 8 script được sửa, 11 test.

---

## 2. Chạm được nhánh ranked — lần đầu

Trước nay mọi sweep đều rơi vào nhánh **no-card**, nên `build_scoring_packet` ở nhánh
xếp hạng chưa từng chạy thật lần nào.

**Vì sao khó chạm.** G2 đòi `n_min = ceil(3 / collision_probability_max) = 30` episode
**phân biệt**, mà phân biệt được xét theo *kết quả đo được*, không theo context id.
Profile noise toàn 0 thì mọi seed phát lại y hệt một episode ⇒ 1 distinct.

Smoke `sudden_stop_v5` (đã có sẵn `lidar_range_sigma_m: 0.02`,
`wheel_slip_fraction: 0.02`), 3 episode, astar vs rrtstar:

```
astar+dwa      3 distinct  success 100%  p99 18.04 ms  fail ['G2']
rrtstar+dwa    3 distinct  success  67%  p99 26.82 ms  fail ['G2', 'G3']
```

RRT\* timeout ⇒ G3 fail ⇒ dù có 30 episode vẫn chỉ 1 candidate qua cổng ⇒ vẫn no-card.

Nên đổi cặp: **`astar+dwa:dwa_coarse` vs `astar+dwa:dwa_balanced`**, scope
`local_controller_selection`. Đây là **trục thiết kế đã khai sẵn** trong
`CONTROLLER_CONFIGS` với số đo ghi kèm (105 / 288 / 800 sample, p99 5.26 / ~11.6 /
29.40 ms so với ngưỡng 50 ms) — không phải vặn nút cho tới khi có cái qua cổng, thứ
mà HĐ-15.3 hỏi tới. Có ghim nhân, vì G4 đọc đồng hồ tường.

Kết quả, 30 episode:

```
astar+dwa  dwa_coarse    30 distinct  success 100%  p99  7.35 ms  pass
astar+dwa  dwa_balanced  30 distinct  success 100%  p99 17.89 ms  pass

ΔU median +0.036656, CI95 [+0.036521, +0.041770] trên 30 episode ghép cặp
decision_utility tái lập tới 6 chữ số: 0.877485
recommended: e1251e42a20b (CLEAR_RECOMMENDATION)
```

---

## 3. Packet nhánh ranked — cái chưa từng được dựng thật

```
packet.status       : CLEAR_RECOMMENDATION
packet.waterfall    : present
packet.observations : 2
packet.lattice      : 7
packet.exemplars    : 4
```

Phân rã waterfall:

| Trục | Trọng số | Đóng góp | CI95 |
|---|---|---|---|
| `U_R` | 0.30 | +0.000000 | [0, 0] |
| `U_S` | 0.10 | +0.000000 | [0, 0] |
| `U_E` | 0.25 | +0.000259 | [−0.00199, +0.00232] |
| `U_C` | 0.35 | **+0.038719** | [+0.03568, +0.04249] |

Đọc được và tự nhất quán: hai cấu hình chỉ khác nhau ở **mật độ sampling**, nên toàn
bộ biên nằm ở trục compute; `U_R` và `U_S` đúng bằng 0 (cùng 100% thành công, cùng an
toàn); `U_E` có CI **vắt qua 0**, tức hiệu quả không phân biệt được. Đây là đúng hình
dạng mà một so sánh sampling-density phải cho ra.

Lattice: `stuck_cluster ⇒ rules_out_component_specific_attribution`, 6 loại còn lại
`insufficient_contrast` — hợp lý, vì swap ở đây là local controller chứ không phải
global planner.

---

## 4. So sánh realtime E4.3 trên trace thật

Chạy thẳng `DecisionRunService.replay_sync` trên run vừa xong:

```
pair    : e1251e42a20b (coarse) vs 3b18dfbfa9e7 (balanced)
quality : reference_plan
rungs   : 40

first @  0.00 m  elapsed  0.00/ 0.00  margin 3.81/3.81  eff 0.000/0.000  compute 0.081/0.201  adv +0.0000
mid   @  5.54 m  elapsed 14.75/14.95  margin 1.89/2.11  eff 0.863/0.830  compute 0.133/0.318  adv +0.0390
last  @ 10.80 m  elapsed 21.95/22.40  margin 1.89/2.11  eff 0.908/0.886  compute 0.136/0.318  adv +0.0296
```

Bốn điều được xác nhận, mỗi điều trước nay chỉ có fixture làm chứng:

1. **`quality: reference_plan`** — lần đầu tiên arc length đo dọc **kế hoạch planner
   đã ghi**, không phải dọc quỹ đạo của một candidate. Sidecar E4.5 đã trả nợ đúng
   chỗ nó được dựng ra để trả.
2. **`path_efficiency` không phải 1.0** (0.863 / 0.830 rồi 0.908 / 0.886). Đây là
   kiểm chứng trực tiếp cho lỗi suýt ship hôm nay: bản dùng quãng đường đã chạy sẽ
   in ra 1.000 ở mọi nấc, mọi episode.
3. **`compute_budget` khớp độc lập với bảng cổng.** 0.136 so với 0.318 = tỉ lệ 2.34;
   p99 ở bảng cổng 7.35 ms so với 17.89 ms = tỉ lệ 2.43. Hai con số này đi hai đường
   khác nhau (một cái là p99 tích luỹ theo tick chuẩn hoá theo `T_cycle`, một cái là
   p99 gộp cả episode) và vẫn gặp nhau.
4. **`safety_margin` không hồi phục** — 1.89 / 2.11 ở nấc giữa và giữ nguyên tới nấc
   cuối. Đúng nghĩa min tích luỹ.

`partial_advantage` dương suốt, tức `dwa_coarse` dẫn — cùng chiều với khuyến nghị của
card. **Không phải một phép đối chiếu**: composite là hai trục trên một episode, ΔU
là bốn trục trên 30 episode. Cùng chiều thì đáng ghi nhận, không đáng dùng làm bằng
chứng cho nhau.

---

## 5. Còn lại

- Phần sửa (8 script + test drift) **chưa commit**.
- Run mới nằm ở
  `artifacts/runs/2026-08-20/sudden_stop_v5_local_controller_selection_de8dae2f`.
- Script xác minh để ở scratchpad, không đưa vào repo: một sweep 30 episode mất ~5
  phút nên không thuộc về test suite. Số đo giữ trong báo cáo này.
- Full suite vẫn chưa chạy.
