# Báo cáo — Phase 3.4: Paired bootstrap ΔU + nhãn (HĐ-11)

> **Ngày:** 2026-08-10
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **3.4**
> **Nhánh:** `plannerselector_p2`
> **Điều kiện vào:** 3.4 phụ thuộc 3.3 (objectives) ✓ và 1.3 (EpisodeContext) ✓
> **Contract:** giữ nguyên **`2.1.0`** — HĐ-11 đủ, không phát sinh giả định thiếu.

---

## 1. Đã làm

| File | Vai |
|---|---|
| `packages/decision/planbench_decision/stats.py` (mới) | `CandidateEvidence`, bootstrap ghép cặp, nhãn, tie-break 4 bậc |
| `packages/decision/planbench_decision/pairing.py` | tách `require_shared_context_ids` để tầng thống kê dùng chung một luật |
| `tests/test_stats.py` (mới) | 30 test |

Ba hàm vào:

```python
build_evidence(candidate, metrics, contexts, anchors, settings) -> CandidateEvidence
compare_pair(a, b, seed=..., n_resamples=1000)                  -> PairedComparison
recommend(evidence, seed=...)                                   -> Recommendation
```

## 2. Vì sao ghép cặp, và vì sao từ chối trước khi tính

Hai candidate chạy **cùng tập episode context** (HĐ-3.2), nên hiệu số được lấy **bên
trong từng context** rồi mới trung bình. Bản đồ, mission, lần hiện thực vật cản và seed
lúc đó giống hệt ở hai vế phép trừ và triệt tiêu; cái còn lại đúng là candidate. So hai
trung bình độc lập trên cùng bộ dữ liệu sẽ vứt bỏ điều đó và bơm vào phương sai thứ
nhiễu mà **cả hai đều chịu như nhau**.

Nếu tập context lệch dù chỉ một phần tử, `require_shared_context_ids` ném lỗi và
**không con số nào được sinh ra**. ΔU trên tập lệch không phải câu trả lời nhiễu, nó là
câu trả lời cho một câu hỏi khác — và tới lúc nó nằm trên card thì lời cảnh báo đã rơi
mất.

`require_shared_context_ids` là bản tách ra từ `require_shared_contexts` chứ không phải
bản sao: tầng thống kê chỉ cầm id (id là hash, không đảo ngược được thành context), và
hai bản sao của luật "có chạy cùng episode không" sẽ trôi khỏi nhau — bản trôi sẽ là
bản thôi từ chối.

## 3. Nhãn đọc CI của **hiệu số**, không đọc chồng lấn

§17 cấm 5. Có test dựng đúng tình huống bẫy: hai candidate cùng dao động mạnh qua các
episode (CI riêng của từng cái chồng lấn nhau rất nhiều), nhưng một cái tốt hơn ở
**mọi** episode với biên đều — CI ghép cặp loại 0 và nhãn là `CLEAR_RECOMMENDATION`.
Nếu đọc chồng lấn thì kết luận ngược lại và sai.

Chiều ngược lại cũng có test: một lợi thế nhỏ đổi dấu qua các episode ⇒ CI chứa 0 ⇒
`NEAR_EQUIVALENT`. Đúng tính chất HĐ-10.2 đòi ở mọi quy tắc loại bỏ: **dữ liệu yếu thì
không kết luận gì**.

## 4. Tie-break: hòa vẫn ra đúng một khuyến nghị

`NEAR_EQUIVALENT` **không** nghĩa là "chọn cái nào cũng được". `TIE_BREAK_ORDER` khai
sẵn 4 bậc HĐ-11.3 dưới dạng dữ liệu — để card in được cái thang nó đã leo, và để không
ai đảo thứ tự sau khi thấy bậc nào có lợi cho candidate nào:

1. `U_C` cao hơn · 2. IQR của `decision_utility` nhỏ hơn · 3. `n_tunable_params` ít hơn ·
4. `modular` hơn `monolithic`.

Mỗi bậc có một test riêng. Hai điểm đáng ghi:

- **Tie-break được phép lật thứ hạng thô.** Có test: candidate dẫn đầu về
  `decision_utility` nhưng thua ở bậc 1, và khuyến nghị đi sang candidate kia. Nếu
  không lật được thì cái thang chỉ là trang trí.
- **Hòa cả bốn bậc thì giữ thứ hạng**, và **nói ra lý do đó** thay vì im lặng — giữ
  tính tái lập thay vì để kết quả tùy tiện.
- Candidate **không khai** `n_tunable_params` **thua** bậc 3 (`+∞`). Bậc đó thưởng cho
  "ít núm vặn phải bảo trì"; ai không nói mình có bao nhiêu thì chưa xứng nhận phần
  thưởng đó.

Một điều học được khi viết test, đáng ghi lại: **lợi thế chi phí đơn thuần không tạo ra
thế hòa.** `tuning_wall_clock_h` là hằng số theo candidate nên nó dịch ΔU của **mọi**
episode đi cùng một lượng ⇒ phương sai bằng 0 ⇒ CI loại 0 ⇒ `CLEAR_RECOMMENDATION`. Muốn
có thế hòa thật phải có **dao động thật giữa các episode**. Hai test tie-break đầu được
dựng lại theo đúng nhận xét này (fixture ban đầu của tôi sai, không phải code sai).

## 5. Một lỗi thật do test bắt được

`effect_size` (Cohen's `d_z` ghép cặp) trả `None` khi mọi episode cho cùng một hiệu số —
thang chuẩn hóa chia cho độ tán bằng 0 nên không xác định. Nhưng kiểm `spread == 0.0`
**không bao giờ đúng**: trừ hai float giống hệt nhau 30 lần để lại nhiễu cỡ `1e-17`, nên
`std` ra `4e-17` chứ không ra 0, và effect size được báo là **2.0e+15** — một con số
trông như bằng chứng áp đảo mà thực chất là phép chia cho sai số làm tròn.

Sửa bằng `DEGENERATE_SPREAD = 1e-12`, có lý do viết ngay tại chỗ: utility nằm trong
[0, 1] nên độ tán dưới `1e-12` không phải biến thiên đo được.

## 6. Tái lập

Bootstrap nhận `seed` (mặc định 0) và **ghi seed cùng `n_resamples` lên kết quả**.
HĐ-15.1 tiêu chí 2 đòi dựng lại từ manifest ra đúng cùng một card tới 6 chữ số — một
bootstrap gieo từ đồng hồ không làm được. Có test: cùng seed ⇒ cùng CI, khác seed ⇒
khác CI.

Lấy mẫu lại **theo episode context** (HĐ-11.2), không theo từng metric rời: episode mới
là đơn vị được rút, và resample metric rời sẽ phá đúng cái ghép cặp làm cho hiệu số có
nghĩa.

## 7. Ba thứ từ chối thay vì đoán

| Tình huống | Vì sao từ chối |
|---|---|
| Chỉ có 1 candidate | Nhãn của card định nghĩa theo CI của ΔU **so với hạng nhì**; một mình thì không có bằng chứng nó hơn cái gì |
| So một candidate với chính nó | ΔU = 0 do cấu tạo, mà CI lại tuyên bố đó là kết quả đo |
| `set_objectives` mức episode | Mức episode bỏ qua ngưỡng `success_rate_min` của khách (HĐ-9.1); xếp hạng bằng nó là xếp hạng theo một U_R khác |

## 8. Báo cáo tối thiểu HĐ-11.3

`PairedComparison` mang `delta_median`, `delta_iqr`, `ci95`, `effect_size`,
`n_episodes` — đúng danh sách tối thiểu. **Không có p-value nào được tính**, nên lệnh
cấm "p-value trần trụi" không thể vi phạm được; có test khẳng định không trường nào tên
`p_value`.

## 9. Chưa làm — cố ý

- **Pareto (HĐ-10)** — Phase 5.2. `recommend()` chỉ so **hai** candidate đầu bảng, đúng
  phạm vi HĐ-11.3 định nghĩa nhãn; gắn nhãn cả trường (không xóa ai) là việc của Pareto.
- **`alternative` trên card** — HĐ-12 nói `alternative` chỉ được lấy từ candidate mang
  nhãn `PARETO_FRONTIER`, nên trường đó chờ 5.2. Hiện `Recommendation` trả
  `runner_up_id` — hạng nhì theo thống kê, không phải "phương án thay thế" theo nghĩa
  contract. Hai khái niệm khác nhau, cố ý không gọi trùng tên.
- **Sensitivity (HĐ-11.5)** — Phase 5.3.

## 10. Test

`tests/test_stats.py`: **30 test** — `build_evidence` (5) · ghép cặp/từ chối (2) ·
bootstrap: dấu, hòa, nhiễu, tái lập theo seed, effect size, không p-value, đủ trường báo
cáo (9) · khuyến nghị: 1 candidate, trùng candidate, thắng rõ, hòa vẫn ra 1 tên, chỉ so
top-2, nhãn không đọc chồng lấn (6) · tie-break 4 bậc + không khai + hòa toàn tập + lật
thứ hạng (8).

Full suite: `pytest tests/ -q` → **1804 passed, 6 skipped** (9 phút 02). Baseline sau
Phase 3.3 là 1774 — thêm đúng 30 test, **không vỡ test nào** (gồm cả `test_pairing`
sau khi tách `require_shared_context_ids`). Ruff sạch. Vòng import kiểm cả hai thứ tự.

## 11. Trạng thái Phase 3

| Mục | Trạng thái | Phụ thuộc |
|---|---|---|
| 3.1 Anchors + `u()` | ✅ | 1.1 ✓ |
| 3.2 Gates G1–G6 | ✅ | 1.1 ✓, 2.3 ✓ |
| 3.3 Objectives + Decision Utility | ✅ | 3.1 ✓ |
| 3.4 Paired bootstrap ΔU + nhãn | ✅ | 3.3 ✓, 1.3 ✓ |
| 3.5 Decision Card + Manifest | chưa — **làm được ngay**, là mục cuối của Phase 3 | 3.2 ✓, 3.3 ✓, 3.4 ✓ |

Sau 3.5, Phase 3 đóng và mở khóa **Phase 4 — lát cắt dọc**, van chặn phương pháp luận.
