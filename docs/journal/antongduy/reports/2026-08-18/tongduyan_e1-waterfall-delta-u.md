# E1 — waterfall ΔU: tháo con số trên card ra bốn thanh

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-18/tang-giai-thich-vi-sao.md` §5, đợt **E1**
**Thiết kế nguồn:** `notes/2026-08-18/tongduyan_giai-phap-giai-thich-vi-sao-thuat-toan-thang.md` §3
**Tiền đề:** E0 (commit `d28ff20`)
**Trạng thái:** xong, **đã qua năm vòng rà của An** (mục 6–10; tất cả đã sửa).
42 test mới xanh. **Chưa commit.** Full suite chưa chạy.

---

## 1. Giao cái gì

`packages/explanation/planbench_explanation/waterfall.py` — một module, bốn
object, một hàm dựng:

| Object | Vai |
|---|---|
| `WaterfallBar` | một objective: `weight`, `delta_objective_mean`, `contribution`, `ci95` marginal, cờ `crosses_zero` (**field**, không phải property) |
| `Waterfall` | tổng ΔU mean + median mô tả + CI tổng + bốn thanh + drill-down + **`WaterfallProfile`** + seed |
| `WaterfallProfile` | `kind` (canonical/perturbed) + `base_profile` + snapshot `PreferenceWeights` + `label` **suy ra** |
| `ObjectiveLevels` | một objective ở **cả hai mức** aggregation, cho một candidate |
| `UtilityDrillDown` | hai mức utility đặt cạnh nhau, kèm `diverging_objectives` (**field**) |
| `build_waterfall(a, b, *, settings, seed, n_resamples)` | dựng từ `CandidateEvidence` của tầng decision |

Module đọc `planbench_decision` (`CandidateEvidence`, `paired_bootstrap_ci`,
`require_shared_context_ids`, `DecisionSettings`) và **không sửa gì bên đó** —
chiều phụ thuộc một hướng: explanation đọc decision, không ngược lại.

## 2. Đẳng thức là toàn bộ lý do module tồn tại

`decision_utility = Σ w_j·u_j` mỗi episode, nên

```
mean(ΔU) = Σ_j w_j · mean(Δu_j)
```

`Waterfall` có `model_validator` **từ chối tồn tại** nếu tổng bốn thanh lệch
tổng quá `SUM_TOLERANCE = 1e-9`. Không phải cảnh báo in cạnh biểu đồ: một phân
rã không dựng lại được tổng của chính nó là bức tranh của một đại lượng khác.
Test sửa `contribution` của một thanh rồi `model_validate` lại — refusal, không
phải biểu đồ lệch.

Thanh cũng bắt buộc **đúng bốn objective, mỗi loại một lần** (so multiset, mục
6). Ba thanh cộng lại "gần đúng", hay bốn thanh trong đó một objective lặp lại
che mất một objective vắng mặt, đều là ca tệ hơn sai hẳn.

## 3. Hai cái bẫy số học, viết thành code chứ không thành lời khuyên

**Mean chứ không median.** Đẳng thức trên chỉ đi qua **mean**; `Σ w_j·median(Δu_j)`
không bằng `median(ΔU)` vì median không tuyến tính. HĐ-11.3 báo cáo median/IQR
nên median **có mặt** trên waterfall — ở trường riêng `delta_utility_median`,
mô tả phân phối, **không bao giờ là thanh**.

Test khóa điều này bằng một fixture ba nhánh **không cân** (6/12/12 episode):
- hai nhánh cân bằng nhau thì mọi median rơi vào trung điểm của cùng một cặp,
  phân rã median **tình cờ đúng**, và test lẽ ra bắt lỗi lại xanh nhờ số học
  không tổng quát. Đây là ca tôi vấp thật lúc viết, ghi lại vì nó là cái bẫy
  của chính test.
- 6/12/12 đẩy episode median của ΔU sang nhánh khác với episode median của từng
  objective, nên `median(ΔU) ≠ Σ w_j·median(Δu_j)` đo được, còn đẳng thức mean
  vẫn đúng trên cùng dữ liệu.

**Hai mức utility lệch nhau ở U_R.** Card in mức **set**; thanh dựng ở mức
**episode** (paired ΔU không tồn tại ở mức set). Chúng chia tay ở U_R vì `u`
affine *có clip* và ở U_R **mọi** episode chạm biên: `success` là 0/1 nên trung
bình episode chính là success rate, còn mức set chấm chính success rate đó với
sàn deployment khai. `UtilityDrillDown` in cả hai số cạnh nhau và
`diverging_objectives` **được suy ra rồi kiểm lại** chứ không khai cứng —
objective nào bắt đầu clip sau này sẽ tự hiện ra thay vì làm người đọc ngạc
nhiên (mục 6, MEDIUM-1: nó là field lưu thật, không phải property).

Test: một episode `success=False` trong 30 ⇒ `episode_mean(U_R) = 29/30`,
`set_level(U_R)` khác hẳn, `diverging_objectives == ("U_R",)`, và thanh vẫn cộng
đúng vào ΔU **mức episode**.

## 4. CI marginal — và test khóa đúng chỗ đó

Mỗi thanh mang CI bootstrap ghép cặp **của riêng contribution nó**. Đây là bốn
phát biểu riêng lẻ, **không phải** một dải đồng thời:

- cộng cận dưới/cận trên của bốn thanh **không** ra CI của tổng, và test khóa
  cả dấu: tổng bề rộng bốn CI **rộng hơn** CI tổng, vì các objective tương quan
  qua từng episode còn tổng được resample như **một** đại lượng;
- CI tổng lấy từ chính chuỗi ΔU — và test đối chiếu nó bằng `compare_pair()`
  cùng seed: waterfall và card phải ra **đúng một** con số, không phải hai con
  số gần nhau.

Mọi bootstrap dùng chung một `seed` **có chủ ý**: cùng seed ⇒ cùng chỉ số
resample ⇒ trong từng lần resample các thanh vẫn cộng đúng vào tổng. Bốn CI vẽ
rời nhau bằng bốn seed sẽ mất tính đồng bộ đó.

`crosses_zero` là field suy ra rồi kiểm lại, để UI làm mờ thanh vắt qua 0. Một
thanh vẽ đậm được đọc là một kết luận; thanh có CI chứa 0 chưa xác lập được
chiều nào.

## 5. Từ chối cái gì

- decompose một candidate với chính nó ⇒ refusal (mọi thanh bằng 0 theo cấu
  tạo, mà CI lại tuyên bố đã đo).
- `settings.profile_label` khác profile mà evidence đã được chấm ⇒ refusal.
  Trọng số không sinh ra utility thì không phân rã được utility đó — đây là ca
  im lặng nhất nếu không chặn: bốn thanh cộng ra tổng của **người khác**.
- context không ghép cặp ⇒ `PairingViolation` từ tầng decision, ném **trước**
  khi vẽ thanh nào.
- `preference_profile` nằm trên chính object: waterfall không nói mình vẽ dưới
  trọng số nào là đang trình bày một sở thích như một phép đo.

## 6. Vòng rà của An — bốn điểm, cùng một gốc

Cả bốn đúng, và cùng một chủ đề: **`build_waterfall()` tính đúng, nhưng model
không fail-closed khi bị deserialize hay bị sửa tay.** Artifact sẽ được ghi ra
đĩa rồi đọc lại ở E4, nên "builder không tạo ra thứ đó" không phải một bảo đảm.

**HIGH-1 — bốn thanh nhưng không đúng bốn objective.** Validator cũ chỉ đếm.
`U_R, U_S, U_E, U_E` đủ bốn, tổng vẫn khớp, còn U_C **biến mất** — và phần giải
thích quy công cho objective không hề được phân rã. Nay so **multiset**
(`Counter`) với `OBJECTIVE_NAMES`, dùng chung cho `bars`, `levels_a`, `levels_b`.
Test hồi quy dựng đúng payload đó: đổi nhãn thanh U_C thành U_E, giữ nguyên mọi
con số nên tổng vẫn đúng — chỉ multiset bắt được.

**HIGH-2 — thanh không tự kiểm phép nhân của chính nó.** `weight=0.25`,
`delta_objective_mean=999`, `contribution=0.1` từng hợp lệ miễn tổng khớp: chiều
cao thanh và các con số in cạnh nó kể hai câu chuyện khác nhau. Nay
`contribution == weight × delta_objective_mean` là invariant của `WaterfallBar`.

**HIGH-3 — drill-down không bị ràng gì.** Nhận `levels_a=()`, nhận candidate id
khác `Waterfall` bên ngoài, nhận `episode_mean_delta` khác `delta_utility_mean`.
Ba invariant mới: đủ bốn objective mỗi bên; candidate id khớp waterfall chứa nó;
`episode_mean_delta ≈ delta_utility_mean` trong `SUM_TOLERANCE`. Drill-down là
tấm panel giải thích **vì sao** thanh và card lệch nhau — nó trỏ sang cặp
candidate khác thì đang giải thích một phép so khác dưới tiêu đề của phép so này.

**MEDIUM-1 — hai trường UI cần lại không serialize.** `crosses_zero` và
`diverging_objectives` là `@property`, nên **không có** trong `model_dump()`.
Đúng như An chỉ ra, report của tôi nói đây là thứ giao cho UI, mà nó sẽ biến mất
đúng lúc E4 ghi artifact hoặc trả JSON. Nay là **field lưu thật**: validator
`mode="before"` điền khi vắng, validator `mode="after"` tính lại và **từ chối
nếu lệch** — cờ làm mờ không được phép mâu thuẫn với khoảng nó mô tả. Test
round-trip `dump → validate → dump` và `dump_json → validate_json`.

Chọn field-được-validator-tái-tính thay vì `@computed_field` vì `extra="forbid"`:
`computed_field` có trong dump nhưng không nhận lại được lúc validate, nên chính
artifact do mình ghi ra sẽ không đọc lại được.

**MEDIUM-2 — CI đảo cận.** `(2.0, -2.0)` từng hợp lệ, và khi đó `crosses_zero`
trả `True` (chứa mọi thứ) còn biểu đồ vẽ ngược. Một guard chung
`_check_interval()` cho cả `ci95` từng thanh lẫn `total_ci95`.

## 7. Vòng rà thứ hai — ba điểm

**HIGH — miền giá trị.** Vòng trước khóa *quan hệ* giữa các con số (tổng, tích,
khớp id) nhưng không khóa **giá trị nào là khả dĩ**. An dựng được artifact qua
sạch mọi validator với `delta_objective_mean = [100, -100, 0, 0]`,
`delta_utility_median = 999`, `total_ci95 = (-999, 999)`, `set_utility_a = 99`,
`set_utility_b = -99` — số bịa **chọn theo cặp triệt tiêu** nên mọi phép cộng
vẫn khớp. Đây là điểm hay nhất trong ba vòng rà: quan hệ đúng không suy ra được
giá trị đúng.

Utility nằm trên [0, 1] theo cấu tạo (anchor clip), nên:

| Đại lượng | Miền | Chỗ chặn |
|---|---|---|
| `set_level`, `episode_mean`, bốn utility trong drill-down | [0, 1] | `Field(ge=0, le=1)` |
| `delta_objective_mean`, `delta_utility_mean`, `delta_utility_median` | [-1, 1] | `Field(ge=-1, le=1)` |
| `contribution` và hai cận `ci95` của một thanh | [-weight, weight] | `_within()` trong validator |
| hai cận `total_ci95` | [-1, 1] | `_within()` |
| tổng bốn `weight` | ≈ 1 | `math.isclose` với `WEIGHT_SUM_TOLERANCE` **của tầng decision** (một nguồn, không đặt hằng số thứ hai) |

Thêm `candidate_a != candidate_b` ở **mức model** cho cả `Waterfall` lẫn
`UtilityDrillDown` — builder đã chặn, nhưng artifact được đọc lại bởi code chưa
bao giờ gọi builder. Test hồi quy dựng đúng payload "bất khả thi mà tổng vẫn
khớp" của An.

**MEDIUM — before-validator tính toán trên dữ liệu thô.** Đúng: `ci95=["x","y"]`
ném `TypeError` trần, và qua API thì đó là **500 thay vì 422**. Đã bỏ hẳn hai
before-validator; `crosses_zero` và `diverging_objectives` nay derive trong
**after-validator** từ field đã typed, gán qua `object.__setattr__` (model
frozen; trả về bản copy từ validator không được hỗ trợ khi dựng bằng `__init__`
— pydantic cảnh báo đúng chỗ đó).

Không dùng `@computed_field` như gợi ý thứ nhất vì đã thử và nó **phá round-trip**
dưới `extra="forbid"`: computed field có trong `model_dump()` nhưng
`model_validate()` từ chối nó là extra key, tức artifact do chính mình ghi ra
không đọc lại được. Giữ `extra="forbid"` quan trọng hơn — nên chọn đúng phương
án thứ hai của An (derive trong after-validator).

**LOW — report lỗi thời.** Đúng ở thời điểm An đọc. Số liệu hiện tại ở mục 8.

## 8. Vòng rà thứ ba — hai điểm, cùng một họ với hai chỗ tôi tự soát thêm

Hai điểm An chỉ ra đều là **cross-check giữa các object**: từng object tự nhất
quán, tổng cũng khớp, nhưng hai object cạnh nhau nói hai chuyện khác nhau.

**HIGH-1 — thanh chưa ràng với level trong drill-down.** An dựng được artifact
mà thanh khai `[+0,1, −0,1]` còn drill-down đo `[+0,2, −0,2]`: sai lệch triệt
tiêu nên tổng vẫn đúng, mà **công của phần thắng bị quy sai objective** — đúng
thứ duy nhất tấm panel này tồn tại để nói. Nay validator dựng map objective từ
`levels_a`/`levels_b` rồi đối chiếu từng thanh:
`bar.delta_objective_mean ≈ levels_a[obj].episode_mean − levels_b[obj].episode_mean`.

**HIGH-2 — `preference_profile` mới chỉ là nhãn.** Artifact khai
`kho_ban_dem` với weight `[0.5, 0.5, 0, 0]` vẫn hợp lệ vì chỉ có luật "tổng bằng
1". Nay `Waterfall` mang **snapshot `PreferenceWeights`** và từng `bar.weight`
phải khớp snapshot.

Chọn snapshot thay vì tra `PREFERENCE_PROFILES` theo nhãn — đúng lý do An nêu,
và nó còn quan trọng hơn thế: sweep ổn định HĐ-11.5 **cố ý** dịch trọng số, nên
tra bảng canonical sẽ làm ca hợp lệ đó **không biểu diễn được**; và artifact cũ
vẫn tái lập được khi bảng canonical bị sửa về sau. Có test cho ca perturbed:
`weights_override` dựng waterfall bình thường, `profile_label` khác nhãn gốc.

**Hai chỗ tôi tự soát ra khi đóng HIGH-1** (cùng hình dạng, chưa ai báo):

- `set_utility_a/b` phải bằng `Σ w_j · levels[j].set_level`;
- `episode_mean_utility_a/b` phải bằng `Σ w_j · levels[j].episode_mean`.

Không có hai luật này thì một objective trong drill-down bị dịch mà tổng utility
đứng yên — vẫn là "lỗi từng phần bị tổng che", chỉ thấp hơn một tầng.

**Một câu ở bản trước của mục này đã sai, sửa lại.** Tôi viết rằng phép kiểm
`drill_down.episode_mean_delta ≈ delta_utility_mean` trở thành "không thể kích
hoạt riêng lẻ". Không đúng — nó **vẫn kích hoạt được**, và lý do tôi thấy khác đi
là script sửa của vòng đó đã đẩy nhầm ba invariant toàn cục xuống cuối
`_check_side()`, làm chúng chạy **sau** phép kiểm fold. An bắt được chỗ đặt sai ở
vòng 5 (mục 10); sau khi trả về đúng chỗ, phép kiểm này chạy trước và test của nó
lại assert đúng thông điệp của chính nó.

## 9. Vòng rà thứ tư — nhãn profile

**Điểm cuối của cùng một mạch.** Vòng 3 đã ràng thanh với snapshot trọng số,
nhưng **nhãn** vẫn là chuỗi tự do: đổi `kho_ban_dem` thành `pilot_demo` trong
payload, giữ nguyên snapshot và mọi con số, artifact vẫn hợp lệ. Số học không
sai — nhưng panel nói nó mô tả một sở thích mà nó không mô tả, và một sweep độ
nhạy có thể được rửa thành kết quả chính thức.

Nay có `WaterfallProfile` typed:

```yaml
kind: canonical | perturbed
base_profile: <khóa của PREFERENCE_PROFILES>     # sweep vẫn phải khai nó rời từ đâu
weights:      <snapshot PreferenceWeights>
label:        <SUY RA, không nhận từ payload>
```

Luật: `base_profile` lạ ⇒ từ chối · `canonical` mà trọng số khác bảng ⇒ từ chối
(trọng số đã dịch là một sweep) · `perturbed` mà trọng số **đúng bằng** bảng ⇒
cũng từ chối (gắn nhãn sweep cho một kết quả không dịch là giấu kết quả chính
thức sau một caveat) · `label` suy ra từ hai trường trên và phải khớp đúng cách
viết của `DecisionSettings.profile_label` (`"<profile> (perturbed)"`), vì evidence
hai bên đã được lưu dưới chính chuỗi đó.

**Một hệ quả cố ý, nói trước:** `canonical` nghĩa là *đúng trọng số trong bảng*,
nên nếu `PREFERENCE_PROFILES` bị sửa sau này, artifact cũ khai canonical dưới cái
tên đó **sẽ thôi validate** — vì thanh của nó vẽ dưới trọng số mà cái tên ấy
không còn chỉ nữa. Snapshot vẫn giữ đủ số để đọc, và cách sửa là khai lại thành
`perturbed` với cùng snapshot. Đây là đánh đổi ngược chiều với ý "snapshot giúp
tái lập khi bảng đổi" của vòng 3: giữ đọc được, nhưng **không chứng nhận** một
cái nhãn đã đổi nghĩa. Nếu An muốn nới (canonical chỉ cảnh báo thay vì từ chối)
thì đây là chỗ sửa.

## 10. Vòng rà thứ năm — beta, và một chỗ đặt sai của chính tôi

**HIGH — canonical bỏ qua `beta`.** `matches_table` chỉ duyệt bốn trọng số cấp
cao, trong khi `PreferenceWeights.beta` quyết định **U_C được phân rã thế nào**.
Nên một artifact giữ nguyên `w_C` mà đổi beta từ `(0.3, 0.2, 0.2, 0.3)` sang
`(1, 0, 0, 0)` vẫn được **chứng nhận canonical** — và tệ hơn: nó **không thể**
khai perturbed cho trung thực, vì cùng phép kiểm đó bảo rằng nó "khớp bảng". Tức
lỗ này phá đúng ngữ nghĩa vừa chốt ở vòng 4 theo cả hai chiều.

Nay có `_same_weights()` so **toàn bộ** profile, beta theo từng phần tử. Ba test:
beta-only khai canonical ⇒ từ chối; khai perturbed ⇒ nhận, label
`"kho_ban_dem (perturbed)"`; `DecisionSettings(weights_override=…)` chỉ đổi beta
⇒ waterfall ra `kind="perturbed"`.

**LOW — invariant toàn cục nằm trong `_check_side()`.** An gọi đây là "chạy hai
lần"; thực tế nặng hơn thế, và nó là **lỗi của script sửa ở vòng 3**: ba phép
kiểm toàn cục (tổng thanh, khớp candidate, ΔU mức episode) bị đẩy xuống cuối
helper, nên chúng chạy **sau** phép kiểm fold — và đó chính là lý do tôi kết luận
sai ở mục 8 rằng phép kiểm ΔU mức episode "không kích hoạt được" (xem đoạn đã sửa
ở mục 8). Helper còn `return self` trong khi khai `-> None`. Đã trả ba phép kiểm
về validator chính, helper chỉ còn đúng một việc: `U = Σ w_j·u_j` cho **một**
candidate. Docstring của helper nói thẳng luật đó để lần sau không ai đặt nhầm
lại.

## 11. Kiểm chứng

- `tests/test_explanation_waterfall.py` — **42 test**.
- **136 passed**: `pytest tests/test_explanation_waterfall.py
  tests/test_explanation_contracts.py tests/test_explanation_promotion.py
  tests/test_stats.py tests/test_dev_stack_pythonpath.py`.
- `ruff check` + `ruff format` sạch.
- **Full suite chưa chạy.**

## 12. Chưa làm — nói rõ

- **Chưa có UI.** E1 giao số và bất biến; vẽ thanh, làm mờ thanh vắt 0, in tên
  profile lên panel là việc của E4.
- **Chưa nối vào Decision Card/manifest** — E4.
- **Chưa có CI cho từng metric vật lý** (drill-down mức 2 theo anchor) — E4.
- **`intervention`/detector chưa liên quan** — E2/E3.
- **Chưa kiểm `total_ci95` có chứa `delta_utility_mean` không.** Cố ý: CI
  percentile của bootstrap thường chứa trung bình mẫu nhưng **không bảo đảm** với
  phân phối lệch mạnh, nên đặt luật đó là biến một tính chất thống kê thành một
  ràng buộc sai.
