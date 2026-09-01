# B1 và tám arm: số đo thật trên ba fixture

**Ngày chạy:** 2026-08-26 · **Model:** `o4-mini` (OpenAI) và `qwen3:8b` (Ollama
local) · **Bộ dữ liệu:** 3 golden fixture (development partition) · **Repeat:**
3, bypass cache · **eval_spec_checksum:** `cd06d54a…c029cc` ·
**preregistration:** `17354118…510a`

> **Exploratory.** Ba trong sáu họ, không có holdout, `OFFICIAL_GOLDEN_READY =
> False`. Preregistration nói rõ: dưới 12 case thì `pass^k` **không** báo dưới
> dạng tỷ lệ, và McNemar trên ba case là phép thử không đáng chạy. Bảng dưới là
> **quan sát**, không phải kết luận deployment.

## 1. Bảng số

Case đúng = **cả ba repeat** đúng (luật của preregistration: repeat tệ nhất là
case). Repeat đúng đếm riêng để thấy phần dao động.

| Arm | Case | Repeat | Subject | Abstain đúng | Guard drop | Token TB/repeat |
|---|---|---|---|---|---|---|
| **Sàn model-free** | **2/3** | — | — | — | 0 | 0 |
| `b1` (baseline, không M1/M2) | 1/3 | 3/9 | 2/9 | 4/9 | 8 | 9 399 |
| `e1_measurements` (+M1) | 0/3 | 3/9 | 3/9 | 4/9 | 9 | 16 781 |
| `e2_timelines` (+M1+M2) | 0/3 | 0/9 | 0/9 | 2/9 | 8 | 17 395 |
| `e3_knowledge` (+KB) | 0/3 | **5/9** | **5/9** | 5/9 | 5 | 21 925 |
| `e4a_shortlist` (W2 shortlist) | **1/3** | 4/9 | 4/9 | **7/9** | **4** | 14 859 |
| `e4b_options` (+verification options) | 0/3 | 2/9 | 2/9 | 5/9 | 7 | 15 600 |
| `e5a_filtered_menu` (W3 filter) | 0/3 | 0/9 | 0/9 | 1/9 | 10 | 23 863 |
| `e5b_auto_route` (W3 filter + route) | 0/3 | 0/9 | 0/9 | 1/9 | 10 | 25 178 |
| `b1` trên `qwen3:8b` local | 0/3 | 0/9 | 0/9 | 0/9 | 4 | 2 122 |

## 2. Đọc thẳng

**Không arm nào thắng sàn model-free.** Sàn đúng 2/3 case; arm tốt nhất đúng
1/3. Đây là lần đo thứ hai cho cùng kết luận (lần đầu ở `tongduyan_chay-that-
analyst-o4mini-va-local.md`), lần này với host thật, checker thật và tám cấu
hình khác nhau.

**Thứ giúp được là shortlist và knowledge, không phải thêm dữ liệu vào packet.**

- `e3_knowledge` cho **repeat đúng cao nhất** (5/9) — nhưng đắt nhất trong nhóm
  hữu ích (21.9k token/repeat, gấp 2,3 lần baseline).
- `e4a_shortlist` cho **guard drop thấp nhất** (4) và **abstain đúng cao nhất**
  (7/9): model bớt bịa cơ chế và biết từ chối đúng lúc hơn. Đây là arm duy nhất
  cải thiện đồng thời chất lượng hình thức lẫn hành vi từ chối.

**Thêm block dữ liệu vào packet không giúp, và có chỗ hại.** `e1` (+M1) giữ
nguyên 3/9 nhưng token gần gấp đôi. `e2` (+M2 timeline) rơi xuống **0/9** —
timeline chiếm ~40% byte packet (đo ở W1.3: ~1,6k token/3 packet) và đọc theo
đúng nghĩa là làm loãng phần model cần nhìn.

**W3 (lọc menu, auto-route) làm xấu đi trên bộ này.** `e5a`/`e5b` đều 0/9,
guard drop **10** — cao nhất — và đắt nhất (24–25k token). Một cách đọc: menu bị
cắt khiến model đi vòng, và số lượt `revisions_exhausted`/`no_progress` xuất
hiện đúng ở hai arm này. Cần E5a/E5b chạy sau khi `menu_recall = 1.0` được xác
nhận trên bộ lớn hơn — **không đủ dữ liệu để kết luận W3 sai**, chỉ đủ để nói
nó chưa trả công trên ba fixture.

**Local (`qwen3:8b`) vẫn không sản xuất được gì qua guard**: 0/9, đúng như đợt
trước. Rẻ hơn 4–10 lần (2,1k token/repeat) nhưng đầu ra không sống sót.

## 3. Cái bảng này **không** nói

- Không nói arm nào tốt hơn arm nào: 3 case × 3 repeat, chênh 1–2 repeat nằm
  trong nhiễu. Preregistration đã chốt trước rằng dưới 12 case chỉ báo counts.
- Không nói o4-mini kém: nó nói **trên ba fixture này, với prompt này**, nó chưa
  hơn một bảng tra cứu tất định.
- Không nói timeline vô dụng: nói rằng **ở cấu hình hiện tại**, chi phí của nó
  chưa được đền.

## 4. Việc kế tiếp mà số này chỉ ra

| Việc | Vì sao |
|---|---|
| Dựng nốt 3 họ còn thiếu (`OFFICIAL_GOLDEN_READY`) | 3 case là trần cứng của mọi kết luận ở trên |
| Chạy lại `e3` + `e4a` **kết hợp** | Hai thứ duy nhất có dấu hiệu giúp, chưa đo chung |
| Xem transcript của `e5a`/`e5b` | Menu bị cắt gây `revisions_exhausted` — cần biết cắt mất gì |
| Đo `menu_recall` trên nhãn thật trước khi tin arm có filter | Luật W3 đã ghi, chưa chạy trên bộ này |
| Sửa prompt cho nhánh `check` | Guard drop tập trung ở draft và ở citation |

## 5. Tái lập

```bash
python scripts/run_analyst_experiments.py --arm b1 --provider openai \
    --model o4-mini --repeats 3 --label o4mini
python scripts/run_analyst_experiments.py --arm e4a_shortlist --provider local \
    --model qwen3:8b --repeats 3 --label qwen3-8b
```

Artifact JSON nằm ở `artifacts/analyst-experiments/<label>/<arm>.json` (không
commit — nằm trong `.gitignore`), mỗi file mang `runtime_config_checksum`,
`eval_spec_checksum` và `prompt_version` của lượt chạy.

## 6. Cổng của phần này có răng

`docs/antongduy/notes/2026-08-26/tongduyan_analyst-bites-w0-w4.yaml` — **28
răng, tất cả cắn**, cộng một đối chứng dương. Trong đó có ba răng vào chính
scorer: nếu case tính đúng khi *một* repeat đúng, nếu nhãn mất mà vẫn báo điểm,
hoặc nếu draft bị chấm — cả ba đều làm suite đỏ.

Một răng đã bắt được lỗi thật khi viết bộ này: `test_a_draft_is_not_scored`
trước đó **xanh vì lý do sai** (provider hết script nên vòng kết thúc bằng
abstention, draft chưa từng tới scorer). Đã sửa test để vòng thật sự kết thúc
khi còn giữ draft (`revisions_exhausted`).
