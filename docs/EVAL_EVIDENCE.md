# Bằng chứng đánh giá — tầng phản biện

Năm tình huống chạy thật, kết quả chép nguyên từ terminal. Không có số
nào trong tài liệu này được viết tay.

| | |
|---|---|
| Ngày chạy | 2026-08-16 |
| Commit | `bcab3b0` |
| Provider | `gemini` / `gemini-3-flash-preview`, `deterministic=false` |
| Dữ liệu | 10 `comparison_report.json` thật trong `artifacts/runs/` |

Lệnh tái lập nằm ở cuối tài liệu.

## Hệ thống được đánh giá

Hai tầng chồng nhau, và việc tách chúng ra chính là phép đo:

- **Bộ luật** — 15 luật Python thuần trong
  `planbench_decision.self_check`. Tất định, chạy offline, không cần key.
- **Lớp LLM** — `planbench_agent.critique`. Đọc report *cùng với* kết quả
  của luật, xếp thứ tự, và được thêm tối đa 3 phản biện. Không được bỏ
  phản biện nào của luật; mọi trường nó trỏ tới phải tồn tại thật, không
  thì bị loại và đếm vào `fabricated`.

Bộ luật vừa là tính năng, vừa là **baseline** để đo xem LLM có thêm được
gì thật hay không.

---

## TC1 — Run có lỗi thật

**Đầu vào:** `warehouse_a_v2_global_planner_selection` — một phép so đã
chạy, lưu từ trước, không do ai dàn dựng.

**Kết quả:**

```
luat=9  model=3  fabricated=0  refused=-
summary: The benchmark fails to substantiate the 'global_planner_selection'
scope because all candidates failed the safety and reliability gates,
leaving no valid configuration to select...

[MODEL] UNSUPPORTED_SCOPE            -> identity.experiment_scope
[MODEL] MEMORY_ESTIMATE_DISCREPANCY  -> candidates[0].gates.G5.memory_estimate_mb
[MODEL] INACTIVE_PLANNER_MEASUREMENT -> candidates[1].gates.G5.peak_search_nodes
```

**Đọc thế nào:** Bộ luật bắt 9 phản biện, trong đó 2 cái mức chặn — chạy
245 lần nhưng chỉ 85 episode phân biệt, và 245/300 episode so với mức tối
thiểu contract đòi. Model thêm 3 phản biện mà luật không nhìn ra, cả 3
đều trỏ vào trường có thật, `fabricated = 0`.

**Đã kiểm chứng bằng tay:** `candidates[1].gates.G5.peak_search_nodes`
đúng là bằng `0` trong khi success rate là `0.8449`. Một planner lấy mẫu
không thể thành công 84% mà không mở rộng node nào — đây là **bộ đếm
hỏng**, không phải bộ nhớ nhỏ. Luật không bắt được vì cần biết thuật toán
lấy mẫu hoạt động ra sao.

## TC2 — Run tốt hơn, chỉ chạy luật

**Đầu vào:** `open_hall_v2_local_controller_selection` — một phép so
xếp hạng được, có Decision Card, trạng thái `CLEAR_RECOMMENDATION`.

**Kết quả:**

```
luat=3
[material]   HOST_NOT_PINNED
[disclosure] G4_HOST_ONLY
[disclosure] G4_HOST_ONLY
```

**Đọc thế nào:** Không có phản biện mức chặn nào. Ba cái còn lại đều
đúng và đều là thứ cần công bố chứ không phải lỗi: độ trễ đo trên máy
chủ không ghim nhân, và gate G4 mới qua vòng sàng lọc chứ chưa đo trên
bo mạch đích.

**Quan trọng:** report này có khoảng tin cậy `[0.0318, 0.0370]` không
chứa 0 và `effect_size = 4.74`, nên hệ thống **không** phản biện kết
luận — đúng như mong đợi.

## TC3 — Tiêm lỗi đã biết

**Đầu vào:** đúng report của TC2, cắt `sample.n_episodes` từ 30 xuống 12.

**Kết quả:**

```
luat=4
[blocking]   SAMPLE_BELOW_N_MIN     <- MỚI so với TC2
[material]   HOST_NOT_PINNED
[disclosure] G4_HOST_ONLY
[disclosure] G4_HOST_ONLY
```

**Đọc thế nào:** Đúng một phản biện mới xuất hiện, đúng cái tương ứng với
lỗi đã tiêm, và ba phản biện cũ không đổi. Đây là phép đo recall ở dạng
nhỏ nhất: tiêm một lỗi biết trước, thu về đúng lỗi đó, không kéo theo
báo động giả.

Bộ tiêm lỗi đầy đủ nằm trong `tests/test_self_check.py` (hằng `FAULTS`),
phủ cả 15 luật.

## TC4 — Không có gì để nói

**Đầu vào:** một report rỗng `{}`.

**Kết quả:**

```
luat=0
```

**Đọc thế nào:** Không ném exception, không bịa ra phản biện nào. Mỗi
luật chỉ đọc trường nó cần và bỏ qua khi trường vắng mặt — trường thiếu
**không phải** bằng chứng có vấn đề. Đây là ràng buộc cho phép tỉ lệ báo
động giả đo được: nếu hệ thống nói gì đó ở đây thì mọi con số phía sau
mất nghĩa.

## TC5 — Gọi model hai lần trên cùng đầu vào

**Kết quả:**

```
lan 1: model=3 fabricated=0
lan 2: model=3 fabricated=0
```

**Đọc thế nào:** Cùng số phản biện, cùng số bịa đặt. Nhưng phải nói rõ:
**đây không phải bằng chứng tất định.** LLM không tất định kể cả ở
temperature 0; hai lần trùng nhau là dấu hiệu ổn định, không phải bảo
đảm. Phần tái lập được của hệ thống là bộ luật, và đó là lý do nó chạy
trước và không bị model ghi đè.

---

## Tổng hợp

| Tình huống | Kỳ vọng | Thực tế |
|---|---|---|
| TC1 — run có lỗi thật | Bắt được lỗi, model thêm giá trị | 9 luật + 3 model, 0 bịa đặt |
| TC2 — run tốt | Không phản biện kết luận đúng | 0 mức chặn, 3 điểm cần công bố |
| TC3 — tiêm lỗi | Thu đúng lỗi đã tiêm | Đúng 1 phản biện mới, đúng loại |
| TC4 — đầu vào rỗng | Im lặng, không crash | 0 phản biện |
| TC5 — lặp lại | Ổn định | Trùng khớp 2/2 lần |

**Chỉ số quan trọng nhất là `fabricated = 0`.** Nó nghĩa là mọi thứ model
nói đều trỏ về một trường người đọc mở ra kiểm chứng được. Con số này
được công bố trong API response chứ không giấu — vì "model bịa 2 cái" là
một phép đo đáng có, không phải điều đáng che.

## Giới hạn của bộ bằng chứng này

Nêu ra trước thay vì để bị hỏi:

- **Năm tình huống là ít.** Đủ để cho thấy hệ thống hoạt động, không đủ
  để suy ra tỉ lệ. Đánh giá quy mô lớn (tiêm lỗi hàng loạt, tách recall
  lỗi hiện diện với lỗi thiếu sót, đo tỉ lệ báo động giả) là việc tiếp
  theo.
- **Ba phản biện của model ở TC1 mới kiểm chứng tay được một.** Hai cái
  còn lại hợp lý nhưng chưa được xác nhận độc lập.
- **Kết luận chỉ có giá trị trong phạm vi mô hình.** Không tuyên bố gì về
  hành vi robot thật.
- **Chưa có baseline người.** Chưa đo được một người review cùng report
  này sẽ tìm ra bao nhiêu phản biện.

## Cách chạy lại

```bash
cd ~/projects/Project_RAV19
set -a; source .env; set +a

# TC2, TC3, TC4 — chỉ luật, không cần key
PYTHONPATH="packages/decision:packages/schemas" .venv/bin/pytest \
  tests/test_self_check.py -v

# TC1, TC5 — có LLM
PYTHONPATH="services/agent_service:packages/decision:packages/schemas:packages/benchmark:packages/planning:packages/metrics:services/simulator:apps/api:." \
  .venv/bin/python -c "
import json, glob
from planbench_agent.critique import critique_with_model
from planbench_agent.factory import build_provider
from planbench_api.config import get_settings
s = get_settings()
p = build_provider(s.agent_provider, model=s.agent_model or None)
f = [x for x in glob.glob('artifacts/runs/*/*/comparison_report.json') if 'warehouse' in x][0]
r = critique_with_model(json.load(open(f)), p)
print('fabricated:', r.fabricated)
print(r.summary)
" 2>&1 | grep -v '^{'
```

Bộ test tự động phủ cùng những hành vi này: 53 ca cho bộ luật (kèm tiêm
lỗi cho từng luật), 17 ca cho lớp LLM (chín trong số đó là đường thất
bại), 10 ca cho endpoint.
