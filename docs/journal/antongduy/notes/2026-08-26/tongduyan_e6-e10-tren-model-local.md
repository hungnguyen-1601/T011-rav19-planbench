# E6–E10 trên model local, bộ sáu họ

**Ngày:** 2026-08-26 · **Model:** `qwen3:8b`, `llama3.2:latest` (Ollama) ·
**Bộ:** 6 golden fixture, mỗi họ một case · **Repeat:** 3, bypass cache ·
**Hosted (o4-mini):** hết token, không chạy đợt này

> **Exploratory.** Sáu họ nhưng **sáu case**, không phải mười hai;
> `OFFICIAL_GOLDEN_READY = False`. Preregistration nói dưới 12 case chỉ báo
> counts. Không có kết luận deployment nào ở đây.

## 1. Bảng số

Case đúng = **cả ba repeat** đúng.

| Model | Arm | Case | Repeat | Abstain đúng | Guard drop | Token TB | Wall TB | Sàn |
|---|---|---|---|---|---|---|---|---|
| qwen3:8b | `b1` | 0/6 | 0/18 | 6/18 | 11 | 1 569 | — | 3/6 |
| qwen3:8b | `e6_free_schema` | 0/6 | 0/18 | 6/18 | **17** | 1 706 | — | 3/6 |
| qwen3:8b | `e7_no_critic` | 0/6 | 0/18 | 6/18 | 10 | 1 795 | — | 3/6 |
| qwen3:8b | `e8_model` | 0/6 | 0/18 | 6/18 | 18 | 2 005 | 42,1 s | 3/6 |
| llama3.2 | `e8_model` | 0/6 | 0/18 | 5/18 | 9 | 6 064 | 25,6 s | 3/6 |

`model_failed` (provider lỗi hoặc trả không đúng schema): qwen3 2–3 lượt mỗi
arm; llama3.2 0 lượt.

## 2. Đọc được gì

**Cả hai model local đều 0/6 case.** Sàn model-free đúng 3/6 trên chính bộ này.
Đây là lần đo thứ ba cho cùng một câu: trên bộ hiện có, lớp AI **chưa** hơn một
bảng tra cứu tất định.

**E6 — union có tác dụng hình thức, đo được.** Bỏ discriminated union
(`e6_free_schema`) làm guard drop tăng **11 → 17** trên cùng model, cùng case,
cùng repeat. Chất lượng không đổi (đều 0), nhưng số câu bị guard vứt tăng 55%.
Nói đúng phạm vi: union **không** làm model đúng hơn, nó làm model **sai ít hơn
về hình thức** — và đó chính là thứ nó được thiết kế để làm.

**E7 — critic chưa chứng minh được gì.** Tắt critic: drop 11 → 10, chênh một
đơn vị trên 18 lượt. Không đủ để nói critic có hại hay có lợi. Critic hiện là
tất định (xếp hạng + gắn cờ "mỏng"), không tốn lượt gọi model, nên chi phí giữ
nó ≈ 0; nhưng cũng chưa có bằng chứng nó đáng giữ.

**E8 — hai model local khác nhau ở đâu.** Không khác ở chất lượng (0/6 cả hai).
Khác ở **hình thức và giá**:

- `llama3.2` ít vi phạm hơn (9 vs 18) và **nhanh hơn** (25,6 s vs 42,1 s/case)
  nhưng **tốn token gấp ba** (6 064 vs 2 005) — nó viết dài và lặp.
- `qwen3:8b` rẻ token, chậm hơn về wall-clock (reasoning), và **hỏng schema
  nhiều hơn** (3 lượt `model_failed`).

**E9 — chặn.** Hosted (o4-mini) hết token. Số o4-mini có sẵn chạy trên bộ **ba
case trước G6**, khác bộ hiện tại, nên **không so được**. Muốn E9 phải chạy lại
hosted trên bộ sáu.

## 3. E10 — router, tính offline

`scripts/router_eval.py`, không gọi model thêm. Utility preregistered:
`U = 1,0·quality − 0,02·cost_k − 0,005·latency_s`.

| Arm | Case đúng | Cost (k token) | Utility |
|---|---|---|---|
| `floor_only` | **3** | 0,0 | **+3,000** |
| `always_default` (llama3.2) | 0 | 36,9 | −1,465 |
| `always_strong` (qwen3:8b) | 0 | 11,1 | −1,289 |
| `oracle_router` | 3 | 0,0 | +3,000 |
| `frozen_cascade` | 0 | 36,9 | −1,465 |

**Oracle router chính là sàn.** Trên bộ này, quyết định tối ưu ở *mọi* case là
"đừng gọi model" — nên regret của floor-only bằng 0, còn mọi arm có model đều
regret ≈ +4,3…4,5.

- **Router recall: không định nghĩa được.** Số case mà model đắt hơn đúng còn
  model rẻ hơn sai = **0**. Không có gì để router bắt.
- **Bậc thứ hai âm**: `frozen_cascade` − `always_strong` = **−0,175**. Escalate
  chỉ làm tốn thêm.
- Tên arm lệch thực tế: "default" (llama3.2, model nhỏ hơn) lại **đắt token
  gấp ba** "strong". Kích cỡ model không dự đoán được chi phí ở đây.

**Kết luận đúng phạm vi:** với hai model local này, cascade **không có cơ sở**.
Không phải "router thiết kế tồi" — mà là không có case nào mà việc gửi đi đâu
tạo ra khác biệt, vì không arm model nào đúng case nào.

## 4. Một lỗ hổng đã bịt trong lúc chạy

Utility preregistered tính latency, mà **không gì đo giây**. Nếu để nguyên thì
E10 hoặc phải bỏ hạng tử latency, hoặc tệ hơn là đặt nó bằng 0 — biến một arm
chậm thành arm nhanh. Đã thêm `RoundOutcome.elapsed_ms` → `RepeatScore.latency_s`;
`router_eval.py` báo **ABSENT** (không phải 0) cho run không có số. Các run
E6/E7/b1 chạy trước bản vá nên không có latency; hai run E8 thì có.

## 5. Việc còn lại

| Việc | Ghi chú |
|---|---|
| E9 hosted vs local | Cần token o4-mini; phải chạy lại trên bộ sáu case |
| Sáu biến thể thứ hai của các họ | Trần cứng của mọi kết luận — dưới 12 case không báo tỷ lệ |
| Duyệt traits | 6/6 đang draft, chờ An |
| E1–E5 trên bộ sáu case | Đợt trước chạy trên bộ ba case; muốn so cùng thước phải chạy lại (hosted) |

## 6. Tái lập

```powershell
python scripts/run_analyst_experiments.py --arm b1 --arm e6_free_schema `
    --arm e7_no_critic --provider local --model qwen3:8b --repeats 3 --label qwen3-8b
python scripts/run_analyst_experiments.py --arm e8_model --provider local `
    --model llama3.2:latest --repeats 3 --label llama32
python scripts/router_eval.py --default-label llama32 --strong-label qwen3-8b
```
