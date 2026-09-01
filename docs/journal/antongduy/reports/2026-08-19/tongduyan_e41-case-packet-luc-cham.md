# E4.1 — dựng case packet lúc chấm, và endpoint phục vụ nó

**Ngày:** 2026-08-19 · **Nhánh:** `tongduyan_3` · **Plan:** §5 (E4.1)

**Trạng thái:** code xong, unit + API test xanh. **Sweep thật đang chạy nền** để
kiểm chứng end-to-end — chưa có kết quả lúc viết dòng này, sẽ báo riêng. Chưa commit.

---

## 1. Vì sao "lúc chấm", nhắc lại bằng chữ ký hàm

```python
def build_waterfall(a: CandidateEvidence, b: CandidateEvidence, *, settings, ...)
```

`CandidateEvidence` chỉ sống trong `run_comparison`. Dựng lại nó từ report nghĩa là
viết **đường thứ hai** tính ra cùng ΔU — đúng loại nguồn song song mà HĐ-5 cấm ở
mọi chỗ khác trong hệ này, đặt vào đúng tầng có nhiệm vụ làm cho mọi con số truy
được về nơi nó sinh ra. Nên packet dựng tại chỗ, và hai cái giá trả công khai:
report mọc thêm một khối, và run chấm trước E4.1 **không có** packet và không thể
được cấp một cái.

---

## 2. `packet_builder.py`

Tầng giải thích vẫn **không import simulator**. Trace tới dưới dạng mapping cột —
đúng hình dạng API đang phục vụ — nên bên đọc Parquet là caller, không phải module
này.

| Phần | Cách dựng |
|---|---|
| observations | detector chạy trên **mọi** episode; mẫu số là *số episode đã nhìn*, truyền vào chứ không đếm từ trace parse được |
| lattice | đọc cho **cả 7** loại detection, không phải chỉ loại đã kích hoạt — "không candidate nào có" cũng là một phát hiện |
| exemplars | `select_exemplars_from_report`; thiếu ΔU per-episode ⇒ ghi omission |
| width | `2*(radius + margin)`, cùng công thức checker validate; margin lấy từ `hard_clearance` — con số hai tầng buộc phải đồng ý |

**Trace bị detector từ chối thì được báo, không bị bỏ.** Nó là một episode ít đi
sau mọi tỉ lệ trong packet, và điều đó thuộc về report.

**Phần không dựng được là một `omission` có lý do**, không phải một mảng rỗng.
`PacketBuildReport` tách `skipped_episodes` khỏi `omissions` vì "packet không có
observation" và "detector từ chối 9 episode" nhìn từ ngoài giống hệt nhau, mà chỉ
cái thứ hai là chuyện phải xem.

---

## 3. Nối vào `run_comparison`

Chèn sau khối `comparison_pair`, nơi `evidence`, `recommendation`, `settings`,
`gate_reports` còn trong tay. Ba chi tiết:

**Manifest ghi trước packet.** Header packet gọi tên manifest bằng checksum, mà
checksum của bytes thì cần bytes. Report vẫn ghi cuối cùng, nên bất biến cũ giữ
nguyên: mọi file report nhắc tới đều đã nằm trên đĩa trước nó.

**Trace đọc lần thứ hai.** Scoring đã đọc để tính lại metric; giữ toàn bộ trace của
mọi candidate trong RAM tới đây còn đắt hơn đọc lại một file OS vẫn đang cache.
Nói ra vì "đọc trace hai lần" là loại thứ trông như sơ suất khi ai đó profile.

**Hỏng thì không làm hỏng sweep.** Một comparison report không có packet vẫn dùng
được; một sweep chết sau episode cuối vì detector từ chối là vài giờ đổ đi. Lỗi
được ghi vào `omissions` và in ra một dòng cảnh báo.

---

## 4. Hai sự thật suýt bị gộp

`_explanation_packet` ghi `{"packet": None, "omissions": [...]}` khi build hỏng.
Bản đầu của `packet_from_block` trả về **cùng một câu** cho ca đó và cho run cũ:
"scored before E4.1". Sai — khối *có mặt* nghĩa là builder **đã chạy**. Báo nhầm
sẽ đẩy người ta đi chạy lại cả một sweep trong khi thứ họ cần đã nằm trong
`omissions`. Nay hai câu tách hẳn, có test cho từng câu.

---

## 5. `DETECTOR_VERSION`

Header artifact có trường `detector_version` và **không module nào sở hữu giá trị**
— mỗi caller tự gõ `"0.1.0"`. Đó là một version sẽ trôi ngay lần đầu hai caller bất
đồng. Hằng số nay nằm trong `detectors.py`, cùng chỗ với các luật nó mô tả.

---

## 6. Endpoint

`GET /decisions/{run_id}/explanation` → packet + `omissions` + `skipped_episodes`.
Run cũ trả **409** (cùng lý do route exemplars dùng 409: request không sai, run
đang ở trạng thái không có packet).

**Claim không có trong này, và đó không phải thiếu sót.** Claim đến từ promotion
matrix chạy trên checker result, mà chưa analyst nào qua gate. Nên câu trả lời
trung thực là **bằng chứng, chưa có kết luận rút ra trên nó**. Panel đã biết cách
render trạng thái đó; thứ nó thiếu là bằng chứng.

---

## 7. Kiểm chứng

- `tests/test_explanation_e41.py` — **18 test**.
- `tests/api/test_api_explanation.py` — **+4 test** cho route mới (11 tổng).
- Regression: `e4`, `e5`, `e6`, `contracts`, `detectors` — **258 passed**.
- `ruff check` + `ruff format` sạch.
- **Sweep thật (30 episode × 2 candidate) đang chạy nền** — đây là kiểm chứng
  end-to-end duy nhất chứng minh một run có xếp hạng thật sự ghi ra packet. Lần
  chạy 4-episode trước đó **không** xếp hạng được (cả hai candidate trượt G2 vì
  N_min = 30), nên nó không chứng minh gì về nhánh này.
- **Full suite chưa chạy.**

## 8. Còn lại trước khi sang UI

Không có gì chặn. UI cần đúng ba thứ và cả ba đã có: endpoint, `showWaterfall` /
`showClaims` (đã khai trong `explainPanel.ts`, chưa component nào đọc), và packet
mang đủ waterfall + observations + lattice + known-unknowns.

---

## 9. E4.2 — run không có card vẫn nhận xét được

An hỏi: không có card thì tầng này có nhận xét giữa hai thuật toán không. Đọc code
xong thì câu trả lời lúc đó là **không**, và có một khoảng hở phải nêu.

**Thiết kế vốn đúng một nửa.** Ma trận panel đã bật `show_trace_evidence` và
`show_gate_table` cho cả `no_survivors`, `gate_only`, `interrupted` — tức nó **đã
dự định** cho xem bằng chứng ở những run đó. Nhưng `_explanation_packet` tôi nối ở
E4.1 nằm **trong nhánh xếp hạng**, nên những run ấy không có packet nào cả:
detector không chạy, endpoint trả 409. Panel biết phải hiện gì; không có gì để hiện.

Đây cùng loại lệch An bắt ở vòng rà E4 (`showExemplars=false` ẩn luôn trace), nhưng
nặng hơn một bậc: không phải **ẩn**, mà **không dựng**.

**Sửa:**

- `DecisionFacts.waterfall` → `Waterfall | None`;
- `_explanation_packet` gọi trên **cả hai** nhánh, `waterfall=None` ở nhánh không card;
- `_decomposition()` tách riêng, để "run này không có cặp" không bị lẫn với
  "dựng waterfall hỏng";
- schema **từ chối** packet có exemplar mà không có waterfall — ba trong bốn vai
  định nghĩa theo cặp ΔU, nên exemplar không có xếp hạng là bốn episode đeo nhãn
  không ai kiếm được;
- thiếu cặp là một `omission` **có lý do**, không phải trường rỗng.

**Kiểm chứng trên run thật** (`sudden_stop`, 30 episode, `astar+dwa` trượt G2 nên
không có card):

```
card: False | packet: True
status: NO_DECISION_CARD | waterfall: None
obs: 5 | lattice: 7 | gates: 2 | width: 0.52 | skipped: 0

lattice:
  rules_out_component_specific_attribution   [stuck_cluster]
  supports_component_specific_attribution    [near_miss_cluster, replan_storm, latency_spike]
  insufficient_contrast                      [detour, oscillation, narrow_gap_refusal]
```

Đọc được ngay: **cả hai** stack đều kẹt (`stuck_cluster` 30/30 hai bên) nên lattice
**loại trừ** quy kết cho global planner; còn `replan_storm`, `latency_spike`,
`near_miss` chỉ xuất hiện ở một bên nên **ủng hộ** quy kết theo component. Đó là
nhận xét thật giữa hai thuật toán, trên một run không có card.

**Hai lỗi của chính tôi lộ ra khi làm:**

1. `hard_clearance(profile.robot, profile.safety_envelope)` — `TaskProfile` không
   có `safety_envelope`. Envelope suy từ sensor noise của environment, đúng cách
   `nav_stack` làm. Unit test **không bắt được** vì chúng gọi thẳng builder, không
   qua hàm nối; chỉ lần chạy thật mới lộ. Fallback đã làm đúng việc của nó: run
   sống, lý do nằm trong `omissions`.
2. `test_a_clean_run_produces_no_sightings_and_that_is_an_answer` dùng
   `all(...)` trên tuple **rỗng** ⇒ vacuous. Sửa thành `== ()`, và thêm một test
   đối chứng có sighting để nó không thể pass bằng cách không chạy gì.

## 10. Kiểm chứng cuối (E4.1 + E4.2)

- `tests/test_explanation_e41.py` — **19 test**; `tests/test_explanation_e42.py` — **6**.
- `tests/api/test_api_explanation.py` — **12 test**.
- Regression `e4`/`e5`/`e6`/`contracts`: **264 passed** cùng lượt.
- **Run thật, không card**: packet dựng được, số liệu ở mục 9.
- **Run thật, có card**: chưa chạy được — trên hai profile đã thử, `astar+dwa`
  luôn trượt G2 (`n_distinct_episodes = 1` trên profile một mission). Nhánh xếp
  hạng mới chỉ có unit test đứng sau. Nói rõ chứ không suy từ nhánh kia.
- `ruff` sạch. **Full suite chưa chạy.**
