# `success_rate_min` của sảnh: cơ chế giữ lại, ngưỡng lùi về 0.95

**Ngày:** 2026-08-12 · **Hợp đồng:** `6.4.0` → `6.5.0` (MINOR) · **Điều khoản mới:** HĐ-8.4

> Báo cáo này ghi cả một quyết định **đã đảo trong ngày**. Bản đầu chốt "sảnh gác cổng, kho xếp
> hạng" (giữ 1.00); vài giờ sau đảo lại: giữ cơ chế, hạ ngưỡng về 0.95, để câu hỏi ngưỡng lại sau
> MVP. Cả hai lượt đều nằm đây, vì lượt sau chỉ đọc được nếu biết lượt trước.

---

## 1. Việc bắt đầu từ ba test đỏ

Full suite sau phase A + B1: **2182 pass, 6 skip, 3 fail**. Cả ba fail cùng một gốc:

```
AnchorError: anchor 'success_rate' resolves to good == bad == 1.0
             for task profile 'api_hall_tiny'; the metric would have no scale
```

Phạm vi, kiểm bằng `load_anchors().resolve()` không cần chạy episode nào:

| profile | `success_rate_min` | resolve |
|---|---|---|
| `open_hall_v1` | 1.00 | **RAISE** |
| `open_hall_v2` | 1.00 | **RAISE** |
| `warehouse_a_v2` | 0.95 | OK |

Nguyên nhân là hệ quả của một luật đã có, không phải bug mới. HĐ-8.3 luật 2 buộc `bad` của metric
có cổng phải trỏ vào chính ngưỡng của deployment:

```yaml
success_rate: {good: 1.00, bad: "${constraints.success_rate_min}"}
```

Deployment nào đặt ngưỡng **ngay tại điểm lý tưởng** thì `good == bad`. Sảnh làm đúng thế, theo
quyết định 11-08: *"sảnh tham chiếu dễ, đối xứng, mọi failure là tín hiệu chẩn đoán."*

## 2. Lượt một: quyết định (b) — và vì sao nó bị đảo

Chốt ban đầu: **giữ 1.00, chấp nhận sảnh là dụng cụ cổng thuần.** Kèm nhận định rằng (b) không
phải "để nguyên chỗ hỏng" — sảnh vẫn phải gác cổng được, chỉ mất phép xếp hạng.

Cái giá lộ ra khi triển khai xong: `U_R` chết trên sảnh · `measure.py` không còn
`decision_utility` · **tấm Decision Card duy nhất của dự án không tái lập được** · UI phải dựng
thêm một loại artifact nữa · và HĐ-8.4 mang theo một tuyên bố phân vai ("sảnh gác cổng, kho xếp
hạng") lớn hơn nhiều so với việc nó thực sự cần giải quyết.

Đảo lại vì cái giá đó lớn hơn cái được, **trong lúc MVP còn dở**. Không vì lập luận 1.00 sai.

## 3. Lượt hai: giữ cơ chế, lùi ngưỡng

Tách làm hai thứ vốn bị gộp:

| | |
|---|---|
| **Cơ chế** — hệ phải làm gì khi thang sập | **giữ.** Đã hiện thực, có test, biến một cú crash thành lời từ chối đọc được |
| **Chính sách** — sảnh nên khai ngưỡng bao nhiêu | **hoãn.** Về 0.95, ghi nợ, xử lý sau MVP |

`open_hall_v1` và `open_hall_v2` cùng về `0.95` — hai sảnh là **một chỗ**, và
`test_they_differ_only_in_id_and_noise` so cả khối `constraints`, nên chúng phải đi cùng nhau ở cả
hai chiều. A4 nâng cả hai cùng lúc thì hoàn lại cũng cùng lúc.

## 4. Đã sửa gì (phần cơ chế, giữ nguyên)

### 4.1. `anchors.py` — phân biệt hai loại sập thang

- **Metric có cổng, `bad` trỏ vào profile** ⇒ ghi vào `ResolvedAnchors.collapsed`, không raise.
  Deployment đang phát biểu một điều mạch lạc; nền tảng không sửa lời phát biểu đó.
- **Mọi trường hợp khác** (ví dụ `path_efficiency: {good: 0.65, bad: 0.65}`) ⇒ **vẫn fatal**.
  Không ngưỡng nào của deployment đặt được `good` chồng lên `bad` ở đó, nên đó là lỗi chính tả.

Thêm `gate_only_reason`. `u()` của metric đã sập từ chối **kèm tên**, không âm thầm trả về số.
`scaled()` mang theo `collapsed`, để phép quét nhạy cảm không chạy được ở nơi phép chấm thật từ
chối.

### 4.2. `pipeline.py` — từ chối có tên

`GateOnlyDeployment`, cố ý **không** kế thừa `AcceptanceFailure`: không có gì thất bại cả.
`score_survivors` ném nó **trước khi** tính objective nào, nên không có trạng thái chấm dở để ai
nhầm là kết quả thật.

Điểm cốt lõi: **từ chối toàn bộ phép xếp hạng, không bỏ metric chết rồi chấm tiếp.** Bỏ đi và tính
trên phần còn lại sẽ cho `decision_utility` đủ sáu chữ số thập phân, trên một tập objective **khác**
tập đã khai, và không có gì trong con số đó nói rằng một chiều đã biến mất.

`check_gates_reproducible`: tiêu chí 2 (HĐ-15.1) không mất hiệu lực trên deployment gác cổng, nó
**đổi đối tượng** — chấm lại trace phải ra đúng bảng cổng cũ.

### 4.3. `selection.py` — hai lý do không-có-card, hai câu khác nhau

`run_comparison` bắt `GateOnlyDeployment` và đi vào **đúng nhánh** đã có cho "không đủ hai candidate
qua cổng". Thêm trường `gate_only_deployment` (present-and-null mọi nhánh) vì hai lý do đòi **hai
hành động ngược nhau**: *"chỉ 1/2 candidate qua sáu cổng"* ⇒ đăng ký candidate tốt hơn;
*"deployment này không xếp hạng được"* ⇒ **không candidate nào** đổi được kết quả.

### 4.4. `measure.py` — đo được, không chấm

Trên deployment gác cổng: bỏ `build_evidence`, `objectives: null` (present-and-null), in cảnh báo,
đổi tiêu chí tái lập sang bảng cổng.

Kèm một lỗ hổng vá luôn: **`checks` của measure trước giờ chỉ in ra stdout, không vào report.**
Comparison report mang `checks` từ M3; measurement report in rồi vứt — bằng chứng duy nhất rằng
tiêu chí 2 có chạy là một terminal không ai giữ. Nay `checks` nằm trong report.

### 4.5. Hợp đồng `6.5.0` — HĐ-8.4

Ba ràng buộc thành luật: không bỏ metric chết rồi chấm tiếp · từ chối phải đọc được, nêu tên
deployment/metric/ngưỡng · phép đo vẫn còn giá trị nên vẫn phải chạy, và tiêu chí tái lập đổi sang
bảng cổng.

Sau khi đảo quyết định, điều khoản được **viết lại** để bỏ đoạn tuyên bố phân vai. Nay nó chỉ nói
**hệ phải làm gì**, không nói deployment nào nên đặt ngưỡng ở đâu — đó là việc của người khai
deployment, và HĐ-15.3 đã bắt trả lời trước khi chạy. Thêm một câu chặn cách dùng sai: điều khoản
tồn tại để 1.00 là lựa chọn *dùng được*, **không** để biến "hạ ngưỡng" thành lối thoát khi một lần
chạy không ra card.

MINOR vì: không xoá trường nào, không đổi ngữ nghĩa metric hay cổng nào, và **nới** một trường hợp
trước đây fatal.

## 5. Tấm card đầu tiên: tái lập được, **đã kiểm**

Không suy luận. Chạy lại từ trace cũ, không mô phỏng lại:

```
python scripts/compare.py --profile profiles/open_hall_v2.yaml \
  --candidates rrtstar+dwa:dwa_coarse,rrtstar+dwa:dwa_balanced \
  --scope local_controller_selection --episodes 30 --score-only --no-pin
```

```
✓ ΔU median +0.032081, CI95 [+0.031790, +0.037033] over 30 paired episodes
✓ decision_utility reproduced to 6 dp: 0.852213
recommended: db26440f6052 (CLEAR_RECOMMENDATION)
```

Đối chiếu từng trường với card cũ: `decision_utility` **giống hệt tới 16 chữ số**
(`0.8522126893392361`), `delta_u_vs_second`, `delta_u_mean`, `ci95`, `effect_size`, `n_episodes`
đều trùng khít. Nên `SUPERSEDED.md` viết ở lượt một **đã xoá** — cơ sở của nó không còn.

Ba trường **khác**, và cả ba là tiến bộ chứ không phải sai lệch:

| trường | card cũ (6.3.0) | dựng lại (6.5.0) |
|---|---|---|
| `weight_stability_margin` | `null` | `1.0` |
| `anchor_stability` | `null` | `unchanged_at_±10%` |
| `pareto_label` | `UNCERTAIN_DOMINANCE` | `PARETO_FRONTIER` |

Đó là A1 đang chạy: card cũ do `run_comparison` dựng **không** qua đường có sensitivity và Pareto;
nay cả hai đường dùng chung `assemble_card`.

Bản dựng lại giữ ở `artifacts/runs/2026-08-12/open_hall_v2_local_controller_selection_3edf8fe6_reissued/`.

### Ba việc còn nợ đóng luôn ở đây

Lần chạy này là **lần chạy có xếp hạng thật đầu tiên** sau phase A, nên nó xác minh sống ba thứ
trước giờ chỉ có test:

- **A1** — `weight_stability_margin` và `anchor_stability` có mặt trên card thật, không còn `null`.
- **A4** — manifest mang `constraints` đầy đủ (`success_rate_min: 0.95`, `collision_probability_max: 0.1`, …).
- **A2** — `run_uri` trỏ đúng thư mục của chính lần chạy, `run_checksum` = `947e4b5742156caf…`.

## 6. Test

Thêm 5 test ở `tests/test_anchors.py`: sập thang trên metric **không** có cổng vẫn fatal · metric
có cổng sập ⇒ deployment thành gác cổng, không raise · `u()` từ chối metric đã sập kèm chữ
"gate-only deployment" · deployment thường (0,95) **không** bị coi là gác cổng · `collapsed` sống
sót qua phép quét nhạy cảm.

Thêm 6 test ở `tests/test_measure.py` (`TestAGateOnlyDeploymentIsMeasuredButNotScored`), chạy trên
**fixture tổng hợp** đặt 1.00 — nên cơ chế vẫn được canh dù không profile nào của dự án còn kích
hoạt nó: report vẫn được ghi · sáu cổng vẫn có phán quyết · `objectives is None` · lý do nêu tên
deployment + metric · tiêu chí tái lập chuyển sang bảng cổng · deployment thường vẫn chấm được.

Ở `tests/api/test_api_decisions.py`, run không xếp hạng nay khẳng định `gate_only_deployment is
None` — tức nó **không** ra như vậy vì deployment mất thang, mà vì `astar+dwa` trượt G3. Hai lý do
không được lẫn.

## 7. Còn nợ

- **L6 — `success_rate_min` của sảnh.** Cơ chế đã có, **quyết định thì chưa**. 0.95 hiện không mang
  lập luận nào của riêng sảnh. Hẹn xử lý sau MVP; vài hướng chưa xét kỹ ghi ở
  `docs/KNOWN_LIMITATIONS.md`.
- `warehouse_a_v2` **chưa khai `sensor_noise`** (σ = 0). Khai vào là đổi thế giới ⇒ theo HĐ-3.1 phải
  ra `warehouse_a_v3`.
- A3 (`uv.lock` rỗng), B2 (`astar+ppo` chưa chạy), C1 (adapter monolithic), C2 (map khó + đối xứng),
  D1 (`reviewed`/`approved_config`), D2 (UI dựng cả hai loại artifact).
