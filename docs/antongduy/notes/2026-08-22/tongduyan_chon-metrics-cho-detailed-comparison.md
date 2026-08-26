# Chọn metric cho sheet `Detailed Comparison`

Ngày: 2026-08-22 · Nhánh `tongduyan_4` · Không sửa code, chỉ khảo sát và chọn.

Tiếp nối [tongduyan_verify-export-excel-share-email.md](tongduyan_verify-export-excel-share-email.md).
An chốt: bộ cột `metric | unit | A | B | delta | winner | weight | note`
là gợi ý chung, được phép uốn theo bài toán. Ghi chú này khảo sát toàn
bộ metric hệ thống thực sự có, rồi chọn bộ phù hợp.

**Hai kết luận sửa lại ghi chú trước** — nêu ngay để không đọc nhầm:

1. Cột `weight` **lấy được ngay hôm nay**, không cần nối dây backend.
   `run.manifest` là cột DB có thật
   ([models.py:556](../../../../apps/api/planbench_api/db/models.py#L556)),
   được ghi từ `report["manifest"]`
   ([decision_service.py:985](../../../../apps/api/planbench_api/decision_service.py#L985)),
   và manifest mang `preference_profile`
   ([card.py:436](../../../../packages/decision/planbench_decision/card.py#L436)).
   Tên profile tra ra bộ số qua `PREFERENCE_PROFILES`.
   Ghi chú trước nói cần nối dây — sai.
2. Nhưng phần lớn metric **không có weight**, và đó là kết quả đúng chứ
   không phải thiếu sót. Lý do ở §3.

---

## 1. Toàn bộ metric hệ thống đang có

### 1.1 Cấp candidate, nằm sẵn trong `run.report` — dùng được ngay

Nguồn: [selection.py:735–805](../../../../packages/benchmark/planbench_benchmark/selection.py#L735),
[selection.py:1359](../../../../packages/benchmark/planbench_benchmark/selection.py#L1359).

| Field | Đơn vị | Hướng tốt |
|---|---|---|
| `success_rate` | % | cao |
| `pooled_p99_latency_ms` | ms | thấp |
| `worst_clearance_m` | m | cao |
| `median_travel_time_s` | s | thấp |
| `n_distinct_episodes` | count | cao |
| `n_episodes` | count | — (mẫu số) |
| `replan_count` | count | **không hướng** |
| `objectives.U_R / U_S / U_E / U_C` | 0–1 | cao |
| `decision_utility` | 0–1 | cao |
| `recommendation_eligible` | bool | — |
| `stack_label`, `local_controller_config`, `components` | — | nhãn |
| `global_observation_class`, `local_observation_class` | — | nhãn |
| `cleared_gates`, `blocking_gates`, `stopped_early` | — | trạng thái |

### 1.2 Trong payload gate — dùng được ngay

| Gate | Field | Đơn vị | Hướng | Ngưỡng khai báo |
|---|---|---|---|---|
| G1 | `no_path_rate` | % | thấp | `threshold` |
| G2 | `observed` | count | thấp | 0 (tuyệt đối) |
| G2 | `upper_bound_95` | % | thấp | — |
| G2 | `n_distinct_episodes` | count | cao | — |
| G3 | — | — | — | `threshold` (ngưỡng cho `success_rate`) |
| G4 | — | — | — | `threshold_ms` (ngưỡng cho p99) |
| G5 | `memory_estimate_mb` | MB | thấp | `available_ram_mb` |
| G6 | — | — | — | quyết trước episode 1, không có số chạy |

### 1.3 Chỉ có ở cấp episode, không có tổng hợp cấp candidate

`collision_count`, `min_clearance`, `travel_time_s`, `p99_latency_ms`,
`failure_reason`, `episode_decision_utility`, `replan_count`,
`peak_search_nodes`, `peak_tree_nodes`.

### 1.4 Có trong mô hình chấm điểm nhưng **không ghi vào report**

`path_efficiency`, `time_efficiency` (đầu vào U_E) · `near_miss_rate`
(đầu vào U_S) · `cpu_time_per_mission_s` (β3 của U_C) ·
`tuning_wall_clock_h` / `engineering_cost_per_mission` (β4 của U_C).

Đây là trường của `EpisodeMetricSet`, được `objectives.py` tiêu thụ để
tính U, nhưng `selection.py` không viết chúng ra report ở bất kỳ cấp
nào. **Không đưa vào export được** cho tới khi report mang chúng.

---

## 2. Metric bị loại, kèm lý do

| Metric | Vì sao loại |
|---|---|
| `peak_search_nodes` / `peak_tree_nodes` | HĐ-6 cố tình tách hai cột vì **chúng đếm hai thứ khác nhau**: node mở rộng của tìm kiếm trên lưới với kích thước cây của planner lấy mẫu. Đặt A và B cạnh nhau trên một dòng là so hai đơn vị. Cộng lại thì ra "một con số về đơn vị". Loại. |
| `path_efficiency`, `time_efficiency`, `near_miss_rate`, `cpu_time_per_mission_s`, `tuning_wall_clock_h` | §1.4 — không có trong report. Đây là thiếu sót thật, nhưng thuộc `selection.py`, không thuộc export. |
| `collision_count` cấp episode | Đã có bản tổng ở G2 `observed`. Lấy từ gate, không đếm lại — đếm lại là định nghĩa thứ hai, tự do trôi khỏi cái verdict đã dựa vào. |
| `n_episodes` | Là mẫu số, không phải thành tích. Thuộc sheet `Summary`, để cạnh `n_distinct_episodes`. |
| `episode_decision_utility` trung bình | Đúng nguyên văn cảnh báo trong [candidateMetrics.ts](../../../../apps/web/src/lib/candidateMetrics.ts): lấy mean ở đây là **đường chấm điểm thứ hai**, và nó không trùng với card vì hai cấp khác nhau ở U_R. Card là nơi con số đó sống. |
| G6 | Quyết trước episode đầu tiên, không sinh số chạy nào để so. |

---

## 3. Vì sao cột `weight` phần lớn phải để trống — và vì sao đó là điều đúng

Trọng số **không gắn vào metric**, nó gắn vào **objective**. Cây trọng số
thật, đọc từ [objectives.py](../../../../packages/decision/planbench_decision/objectives.py):

```
decision_utility = w_r·U_R + w_s·U_S + w_e·U_E + w_c·U_C     (dòng 411)

U_R = u(success_rate)                                         (dòng 377)
U_S = 0.5·u(near_miss_rate) + 0.5·u(mean min_clearance)       (_safety)
U_E = 0.5·u(path_efficiency) + 0.5·u(time_efficiency)         (_efficiency)
U_C = β1·u(p99_latency) + β2·u(memory) + β3·u(cpu_time)
      + β4·u(engineering_cost)                                (_cost)

DEFAULT_BETA = (0.30, 0.20, 0.20, 0.30)                       (dòng 85)
```

Chiếu ngược từ 10 metric quan sát được sang cây này:

| Metric | Weight thật |
|---|---|
| Success rate | **`w_r`** — U_R là hàm của đúng một mình nó, ánh xạ 1:1 |
| Planner latency p99 | **`w_c × β1`** |
| Memory estimate | **`w_c × β2`** |
| Worst clearance | **không có.** U_S dùng **mean** min_clearance; worst là một đại lượng khác. Ghi `w_s` vào đây là nói dối về cái đã được chấm. |
| Collisions observed | **bằng 0 theo hợp đồng.** HĐ-6 loại va chạm khỏi U_S *có chủ đích*, để va chạm không thể đem đổi lấy tốc độ. Va chạm sống ở G2 và chỉ ở đó. |
| Collision bound 95% | 0 — thuộc tính của cỡ mẫu, không phải của stack |
| No route found | 0 — G1 quyết, không vào utility |
| Median episode duration | 0 — cái được chấm là `time_efficiency`, đại lượng khác |
| Distinct episodes | 0 — nền bằng chứng, không phải thành tích |
| Replans | 0 — [candidateMetrics.ts](../../../../apps/web/src/lib/candidateMetrics.ts) đã đặt `direction: "none"`: replan đã bị tính tiền hai lần ở travel time và latency; chấm thêm là định giá lần thứ ba theo một quy tắc không ai viết ra |

**Ba trên mười metric có weight.** Nếu ép một bảng phẳng phải mang cột
`weight`, bảy dòng trống sẽ đọc thành "chưa điền" thay vì "không được
chấm theo thiết kế" — đúng cái lỗi mà HĐ-12 chống, chỉ đổi chỗ.

### Cách xử lý: hai bảng thay vì một

- **`Detailed Comparison`** — 10 metric quan sát được. Giữ cột `weight`,
  ô trống ghi rõ lý do ở cột `note`. Trả lời: *"hai stack chạy khác nhau
  ở chỗ nào"*.
- **`Objective Breakdown`** — 4 trục có trọng số. Trả lời: *"quyết định
  được ra bằng gì"*, và cho phép người đọc **tự cộng lại ra
  `decision_utility`** ngay trong Excel.

Hai câu hỏi khác nhau. Nhồi vào một bảng thì cả hai đều mờ.

---

## 4. Bộ cột chốt

### 4.1 Sheet `Detailed Comparison` — 10 cột

```
Metric | Unit | <nhãn A> | <nhãn B> | Delta | Delta unit | Winner | Limit | Weight | Note
```

| Cột | Kiểu ô | Nguồn |
|---|---|---|
| `Metric` | text | `decisions.compare.<key>` — nhãn đã có sẵn tiếng Anh và tiếng Việt |
| `Unit` | text | `Format.unit` trong candidateMetrics.ts: `%`, `ms`, `s`, `m`, `MB`, rỗng cho count |
| `<nhãn A>` / `<nhãn B>` | **number** + `number_format` | giá trị thô; header là `stack_label` thật, không phải chữ "Algorithm A" |
| `Delta` | **number** | B − A trên **thang hiển thị** |
| `Delta unit` | text | `Format.deltaUnit ?? unit` — cột riêng vì hiệu của hai tỉ lệ là **pp**, không phải `%` |
| `Winner` | text | `A` / `B` / `tie` / `no direction` / `not measured` |
| `Limit` | number/rỗng | ngưỡng deployment khai: G3 `threshold`, G1 `threshold`, G4 `threshold_ms`, G5 `available_ram_mb`, G2 = 0 |
| `Weight` | number/rỗng | chỉ 3 dòng có; xem §3 |
| `Note` | text | `decisions.compare.why.<key>` — **đã viết sẵn đủ 10 câu**, không phải soạn mới |

Thêm hai cột so với gợi ý ban đầu (`Delta unit`, `Limit`) và đổi header
A/B thành tên stack thật. Lý do:

- `Delta unit` — bỏ nó là in `+2.0 %` cho một khoảng cách giữa 70.0 % và
  72.0 %, tức nói khoảng cách đó là tỉ lệ của một tỉ lệ. candidateMetrics
  đã tách `deltaUnit` đúng vì lý do này.
- `Limit` — với bài toán này, "7.35 ms" là vô nghĩa nếu không biết trần
  là 50 ms. Ngưỡng là thứ biến một con số thành một phán quyết, và
  deployment đã khai sẵn.
- Tên stack thật — file đi ra ngoài platform. "Algorithm A" bắt người
  đọc quay lại tra xem A là ai.

### 4.2 Mười dòng

| # | Metric | Unit | Hướng | Limit | Weight |
|---|---|---|---|---|---|
| 1 | Success rate | % | cao | G3 `threshold` | `w_r` |
| 2 | Collisions observed | count | thấp | 0 | — gate G2 |
| 3 | Collision probability, 95% upper bound | % | thấp | — | — cỡ mẫu |
| 4 | Episodes with no route found | % | thấp | G1 `threshold` | — gate G1 |
| 5 | Worst clearance in the whole run | m | cao | — | — U_S dùng mean |
| 6 | Median episode duration | s | thấp | — | — |
| 7 | Planner latency, pooled p99 | ms | thấp | G4 `threshold_ms` | `w_c × β1` |
| 8 | Memory estimate on the target board | MB | thấp | G5 `available_ram_mb` | `w_c × β2` |
| 9 | Distinct episodes | count | cao | — | — nền bằng chứng |
| 10 | Replans across the run | count | **không** | — | — |

Đây đúng bằng `comparisonRows()` — **cố ý**. Lưới trên UI và sheet trong
file phải là cùng một bảng, nếu không thì người xem màn hình và người mở
file đang đọc hai bài so sánh khác nhau về cùng một run.

**Hệ quả bắt buộc:** đừng viết lại logic này lần thứ hai trong Python.
`direction`, `unit`, `deltaUnit`, `TIE_TOLERANCE = 1e-3`, quy tắc
`leaders()` (một *tập* dẫn đầu, không phải một winner) — tất cả đã định
nghĩa trong [candidateMetrics.ts](../../../../apps/web/src/lib/candidateMetrics.ts).
Chép sang Python là bản định nghĩa thứ hai, và nó sẽ trôi ở lần sửa đầu
tiên. Chọn một trong hai:

- **(a)** Định nghĩa bảng metric một lần trong `decision_export.py`
  (Python là nguồn), rồi cho report mang nó ra để UI đọc.
- **(b)** Giữ nguyên bên TS, và Python import bảng đó dưới dạng dữ liệu.

Khuyến nghị **(a)** — export đã có `decision_export.py` tồn tại đúng vì
lý do "khai một lần, hai định dạng cùng có". Đây là chỗ thứ ba cùng loại.

### 4.3 Sheet `Objective Breakdown` — sheet mới, 7 cột

```
Objective | Weight | <nhãn A> | <nhãn B> | Delta | Contribution A | Contribution B
```

| Dòng | Weight | Ghi chú |
|---|---|---|
| U_R — Reliability | `w_r` | u(success_rate) so với sàn deployment khai |
| U_S — Safety | `w_s` | 0.5·near-miss + 0.5·mean clearance; **cả hai đầu vào đều không có trong report** |
| U_E — Efficiency | `w_e` | 0.5·path + 0.5·time efficiency; **cả hai đầu vào đều không có trong report** |
| U_C — Cost | `w_c` | β = (0.30, 0.20, 0.20, 0.30) trên latency / memory / CPU / engineering |
| **Decision utility** | **1.00** | `= Σ weight × U` |

`Contribution = weight × U`. Cột này tồn tại để cộng dọc lại đúng bằng
`decision_utility`. Người đọc **kiểm tra được phép tính bằng `SUM` ngay
trong Excel** — đó là điều một bảng số string không bao giờ cho phép, và
là lý do mạnh nhất cho việc chuyển sang ghi số thật.

Bốn dòng phụ của U_C (β1 latency · β2 memory · β3 CPU time · β4
engineering cost) nên hiện với đúng trọng số β, hai cột giá trị để rỗng
với β3 và β4 kèm note `"input not recorded in report"`. Trọng số có thật,
đầu vào thì không — nói đúng cả hai vế.

### 4.4 Lấy weight ra sao

```python
profile_label = (run.manifest or {}).get("preference_profile")
# "kho_ban_dem" | "benh_vien_gio_cao_diem" | "pilot_demo" | "measured_only"
# hoặc "<tên> (perturbed)" khi chạy sweep ổn định trọng số HĐ-11.5
```

Ba trường hợp, xử lý khác nhau:

| Trường hợp | Xử lý |
|---|---|
| Tên khớp `PREFERENCE_PROFILES` | Tra ra `w_r/w_s/w_e/w_c` + `beta`. Ghi cả tên profile lên sheet `Summary`. |
| Tên có hậu tố `(perturbed)` | `weights_override` **không được lưu ở đâu cả**. Không đoán. Cột `weight` để rỗng, note: `"weights perturbed for the HĐ-11.5 sweep and not recorded"`. |
| `manifest` là `None` | Run không có card ([selection.py:845](../../../../packages/benchmark/planbench_benchmark/selection.py#L845)). Không có xếp hạng thì cột weight rỗng là đúng — bỏ luôn sheet `Objective Breakdown`, giữ `Detailed Comparison`. |

Ràng buộc quan trọng: **trọng số phải đọc từ manifest của chính run đó,
không phải từ mặc định `"kho_ban_dem"`.** Một card tính dưới
`benh_vien_gio_cao_diem` (w_s = 0.50) mà export in trọng số của
`kho_ban_dem` (w_s = 0.10) thì mọi cột contribution đều sai, và sai một
cách không nhìn ra được vì tổng vẫn ra một con số hợp lý.

---

## 5. Quy tắc chọn winner — dùng lại, không viết mới

Từ `leaders()` / `standings()` trong candidateMetrics.ts:

- Chênh lệch ≤ `1e-3 × scale` của dòng thì gọi **tie**, không gọi winner.
- Dòng `direction: "none"` (Replans) **không có winner** — để `no direction`.
- Dưới hai candidate ghi được giá trị thì không so — để `not measured`.
- Mọi bên bằng nhau thì cũng không ai thắng.
- **"Không dẫn đầu" khác "thua".** Candidate không ghi được giá trị thì
  không thua — không có cuộc so nào diễn ra cả.

Điều cuối quyết định cách tô màu: conditional formatting chỉ được tô đỏ
ô **thật sự trail**, không tô ô rỗng và không tô dòng tie. Tô đỏ một ô
chưa đo là cùng một loại sai lầm với việc hiển thị null thành 0.

Với đúng hai candidate — trường hợp thường gặp của bài toán này — có thể
thêm một dòng tổng ở đầu sheet, đã có sẵn khoá i18n:
`decisions.compare.summary = "{a} leads on {aWins} of {total} scored metrics, {b} on {bWins}"`.

---

## 6. Tóm tắt thay đổi so với đề bài gốc

| Đề bài gốc | Chốt lại | Lý do |
|---|---|---|
| `metric` | giữ | |
| `unit` | giữ, **tách thêm `Delta unit`** | hiệu của hai tỉ lệ là pp |
| `Algorithm A` / `Algorithm B` | giữ, **header là `stack_label` thật** | file đi ra ngoài platform |
| `delta` | giữ, số thật, B − A trên thang hiển thị | |
| `winner` | giữ, thêm `tie` / `no direction` / `not measured` | ba trạng thái này khác "thua" |
| `weight` | giữ, **chỉ 3/10 dòng có số** | trọng số gắn vào objective, không gắn vào metric |
| `note` | giữ, **dùng lại `decisions.compare.why.*`** | 10 câu đã viết sẵn, có cả hai ngôn ngữ |
| — | **thêm `Limit`** | ngưỡng là thứ biến con số thành phán quyết |
| — | **thêm sheet `Objective Breakdown`** | chỗ duy nhất `weight` có nghĩa đầy đủ, và cho phép cộng lại ra `decision_utility` |

---

## 7. Acceptance criteria bổ sung

Thay cho E1.7–E1.8 trong ghi chú trước:

| # | Tiêu chí | Cách kiểm |
|---|---|---|
| E1.8a | `Detailed Comparison` có đúng 10 dòng, cùng thứ tự với lưới trên UI | Mở cạnh nhau, so từng dòng |
| E1.8b | Nhãn cột A/B là `stack_label` thật, không phải "Algorithm A/B" | Đọc header |
| E1.8c | Dòng Replans có `Winner = no direction`, không ai được tô màu | Xem dòng 10 |
| E1.8d | Chênh lệch dưới `1e-3 × scale` hiện `tie`, không hiện winner | Tìm run có hai giá trị gần nhau |
| E1.8e | Metric chỉ một bên đo được: `Winner = not measured`, **ô kia không bị tô đỏ** | Tìm run thiếu số |
| E1.8f | Cột `Limit` khớp ngưỡng deployment khai ở G1/G3/G4/G5 | So với task profile |
| E1.8g | Cột `Delta unit` là `pp` ở 3 dòng phần trăm, không phải `%` | Đọc dòng 1, 3, 4 |
| E1.8h | Chỉ 3 dòng có `Weight`; 7 dòng còn lại rỗng **và có lý do ở `Note`** | Đọc cột weight |
| E1.8i | `Weight` khớp `preference_profile` của **chính run đó**, không phải mặc định | Export hai run khác profile, so |
| E1.8j | Run chạy sweep (`(perturbed)`): weight rỗng + note nói rõ, **không đoán số** | Export một run sweep |
| E1.8k | **`SUM` cột Contribution trên `Objective Breakdown` = `decision_utility` trên `Summary`**, khớp tới 6 chữ số thập phân | Gõ `=SUM()` trong Excel |
| E1.8l | Run không có card: không có sheet `Objective Breakdown`, `Detailed Comparison` vẫn đầy đủ | Chọn run bị chặn gate |
| E1.8m | `Note` hiển thị đúng ngôn ngữ đang chọn | Export ở chế độ vi và en |

E1.8k là tiêu chí giá trị nhất trong cả bộ: nó bắt được cùng lúc bốn
thứ — số phải là số thật, trọng số phải đúng profile, ánh xạ objective
phải đúng, và không có đường chấm điểm thứ hai nào lẻn vào.

---

## 8. Việc còn nợ, không thuộc export

Ghi lại để không mất: `path_efficiency`, `time_efficiency`,
`near_miss_rate`, `cpu_time_per_mission_s`, `tuning_wall_clock_h` là
**đầu vào trực tiếp của U_S, U_E và U_C** nhưng không nằm trong report ở
bất kỳ cấp nào. Hệ quả: hai trong bốn trục quyết định — U_S và U_E — có
điểm số trong export mà **không có bất kỳ số đo nào giải thích điểm đó
từ đâu ra**. Người đọc thấy `U_E = 0.62` và không có cách nào truy ra.

Đây là lỗ hổng của `selection.py`, không phải của export, và nó lớn hơn
mọi thứ trong ghi chú này. Sửa ở đó thì `Objective Breakdown` tự đầy đủ
mà không phải đụng lại.
