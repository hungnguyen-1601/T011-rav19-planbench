# Báo cáo — Phase 3.5: Decision Card + Manifest (HĐ-12/13)

> **Ngày:** 2026-08-10
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **3.5**
> **Nhánh:** `plannerselector_p2`
> **Điều kiện vào:** 3.5 phụ thuộc 3.2 ✓, 3.3 ✓, 3.4 ✓ — cả ba đã xong hôm nay.
> **Contract:** `2.1.0` → **`2.2.0`** (MINOR, xem mục 2)
> **Ý nghĩa:** mục cuối của Phase 3. Xong mục này thì **Phase 3 đóng** và Phase 4 (lát cắt dọc) hết bị chặn.

---

## 1. Đã làm

| File | Vai |
|---|---|
| `contracts/schemas/decision_card.schema.json` (mới) | Dạng kiểm được bằng máy của HĐ-12 |
| `contracts/schemas/manifest.schema.json` (mới) | Dạng kiểm được bằng máy của HĐ-13 |
| `packages/decision/planbench_decision/card.py` (mới) | `DecisionCard`, `Manifest`, hai builder, `resolve_git_sha` |
| `contracts/CONTRACTS.md` | `decision_mode_label` (HĐ-12), khối `bootstrap` (HĐ-13), bảng giá trị chờ Phase 5, §18 |
| `packages/schemas/planbench_schemas/contracts.py` | `CONTRACTS_VERSION = "2.2.0"` |
| `requirements.txt` | `jsonschema==4.26.0` (chỉ dùng cho test) |
| `tests/test_decision_card.py` (mới) | 29 test |

```python
build_decision_card(recommendation, evidence, gate_reports, profile, settings,
                    experiment_scope, manifest_ref) -> DecisionCard
build_manifest(recommendation, evidence, gate_reports, profile, settings,
               anchors, provenance) -> Manifest
```

## 2. Contract 2.1.0 → 2.2.0 (MINOR) — hai lỗ hổng lộ ra khi viết file thật

**① HĐ-13 thiếu seed, và vì thế tiêu chí nghiệm thu của chính HĐ-13 không đạt được.**
HĐ-13 nói: đưa manifest cho người khác, họ dựng lại **cùng một Decision Card**, sai khác
chỉ ở thời gian tường. Nhưng `evidence.ci95` đến từ bootstrap ngẫu nhiên (HĐ-11.2) —
hai người chạy cùng manifest với hai seed khác nhau ra hai khoảng tin cậy khác nhau, và
khác biệt đó **không phải** thời gian tường. Bản 2.1.x không có chỗ nào ghi seed.

Thêm khối `bootstrap: {seed, n_resamples}`. `n_resamples` đi cùng vì đổi số lần lấy mẫu
cũng đổi khoảng.

**② HĐ-9.3 bắt in một câu nhãn, HĐ-12 không có trường cho nó.** Từ bản 1.0.0, HĐ-9.3
yêu cầu card in *"Khuyến nghị kỹ thuật — chỉ dựa trên số liệu đo được"* (hoặc câu tương
ứng của chế độ business). Nhưng ví dụ JSON của HĐ-12 không có chỗ, nên yêu cầu đó chỉ
tồn tại dưới dạng lời dặn — và một lời dặn thì tầng render nào quên cũng không ai biết.
Thêm `decision_mode_label` bắt buộc, để thiếu nhãn thành **lỗi validate** thay vì một
tấm card trông bình thường. Có test xóa trường này khỏi payload và khẳng định schema
bắt được.

Cả hai đều là trường thêm ⇒ MINOR. Không đụng ba định danh đóng băng, không đổi công
thức nào.

## 3. Điều khó nhất của phase: card chỉ được nói điều đã kiểm

Ba nhóm trường thuộc về phân tích mà Phase 3 **không chạy**. Giá trị đúng của chúng lúc
này đã ghi thành bảng trong HĐ-12:

| Trường | Giá trị | Vì sao không bịa, cũng không bỏ trống |
|---|---|---|
| `pareto_label` | `UNCERTAIN_DOMINANCE` | Đây đúng là tên HĐ-10.1 đặt cho "chưa đủ dữ liệu để kết luận". In `PARETO_FRONTIER` khi chưa chạy phân tích là tuyên bố một điều chưa kiểm |
| `alternative` | `null` | HĐ-12: chỉ được lấy từ candidate mang nhãn `PARETO_FRONTIER`. Chưa có nhãn đó thì không có nguồn hợp lệ |
| `evidence.weight_stability_margin` / `anchor_stability` / `robustness_margin` | `null` | `null` đọc được là "chưa đo". Một con số mặc định đọc được là "đã đo và ổn", và không ai ở hạ nguồn phân biệt được hai thứ đó |

**Hạng nhì theo thống kê KHÔNG phải `alternative`.** `recommend()` trả `runner_up_id` vì
đó là thứ nhãn được định nghĩa so với (HĐ-11.3). `alternative` trên card là một tuyên bố
khác — *"bạn cũng có thể ship cái này"* — và nó cần phân tích Pareto đỡ lưng. Hai thứ cố
ý **không** nối vào nhau, có test khẳng định.

## 4. Cổng chạy trước chấm điểm — và card cưỡng chế điều đó

`build_decision_card` **từ chối** khi candidate được khuyến nghị trượt bất kỳ cổng nào.
Cổng không phải điểm thấp có thể bù bằng điểm cao chỗ khác: candidate trượt cổng không
phải lựa chọn tệ hơn, nó **không phải một lựa chọn**.

Nhưng candidate bị loại **vẫn có dòng trên card** (HĐ-10.1: không ai biến mất khỏi báo
cáo). Có test dựng đúng cảnh demo của đề tài: một candidate nhanh nhất bảng (9 ms) bị
loại ở G6, vẫn hiện đủ trong bảng cổng với `G6: fail`.

Viết test này làm lộ một chỗ tôi dựng harness sai: ban đầu tôi chấm điểm **mọi**
candidate rồi mới xếp hạng, nên cái trượt cổng leo lên đầu bảng và card từ chối — code
đúng, harness sai. Pipeline đúng là: cổng trước, chỉ candidate qua cổng mới được chấm và
xếp hạng, còn bảng cổng thì gồm tất cả.

## 5. Schema là hợp đồng, model là hiện thực

Test validate JSON sinh ra bằng `contracts/schemas/*.json` chứ **không** bằng chính model
Pydantic đã sinh ra nó — kiểm output bằng cái đã tạo ra output thì không chứng minh gì.
Có thêm test khẳng định hai file schema tự nó là JSON Schema hợp lệ: một schema sai cú
pháp thì validate cái gì cũng qua và không bắt được gì.

DoD của phase ("card JSON validate được bằng schema trong `contracts/schemas/`") vì vậy
là một test chạy thật, không phải một câu khẳng định.

## 6. Tái lập

- `Provenance` (git_sha, docker digest, benchmark host, created_at) **truyền vào**, không
  tự dò. Tầng decision là hàm thuần của input (§16); một module vừa gọi `git` vừa đọc
  đồng hồ trong lúc dựng card thì không kiểm được tính tái lập — đúng thứ duy nhất mà
  manifest tồn tại để bảo đảm. `resolve_git_sha()` tách riêng cho runner gọi, và **ném
  lỗi** thay vì trả `"unknown"`: một manifest ghi `git_sha: unknown` trông đầy đủ mà dựng
  lại được không gì.
- Bảng cổng sắp theo `candidate_id`, không theo thứ hạng — hai candidate hòa điểm không
  được phép đổi chỗ giữa hai lần dựng cùng một run.
- Có test: hai lần dựng manifest từ cùng input ra JSON **bằng nhau**, và khi dời
  `created_at` thì mọi trường khác vẫn y nguyên — đúng phát biểu "sai khác chỉ ở thời
  gian tường".

## 7. Ba thứ từ chối

| Tình huống | Vì sao |
|---|---|
| Candidate được khuyến nghị trượt cổng | Mục 4 |
| Candidate được chấm điểm nhưng không có dòng cổng | Cổng chạy trước chấm điểm; thứ tự ngược nghĩa là có bug ở đâu đó, mà card sinh ra vẫn trông hợp lý |
| Các candidate được chấm trên tập context khác nhau | Manifest sẽ ghi một tập `evaluation` mà không phải ai cũng chạy |

## 8. Test

`tests/test_decision_card.py`: **29 test** — schema tự nó hợp lệ (3) · card/manifest thật
validate qua schema + round-trip JSON + schema bắt được thiếu nhãn (4) · card được phép
nói gì (9: nhãn chế độ, Pareto, alternative, null vs 0, evidence, PENDING, caveat G4,
ngôn ngữ cấm, candidate bị loại vẫn hiện, scope tính từ dữ liệu) · card từ chối gì (3) ·
manifest (7) · tái lập (2).

Full suite: `pytest tests/ -q` → **1833 passed, 6 skipped** (9 phút 14). Baseline sau
Phase 3.4 là 1804 — thêm đúng 29 test, **không vỡ test nào**, gồm cả 4 test
`test_contract_version` sau khi bump 2.2.0. Ruff sạch. Vòng import kiểm cả hai thứ tự.

## 9. Chưa làm — cố ý

- **`alternative` và `pareto_label` thật** — Phase 5.2. Chỗ nối đã sẵn, chỉ chờ nhãn.
- **Ba trường stability** — Phase 5.3 (weight/anchor) và 5.1 (robustness).
- **Ghi file xuống `artifacts/runs/`** — Phase 4 (lát cắt dọc) là nơi đầu tiên có một
  lần chạy thật để ghi; module này trả object và dict, không chạm đĩa.
- **`params_ref`** mặc định `null`: hiện bộ tham số chỉ nằm trong bản ghi candidate, và
  trỏ tới một bản sao thứ hai có thể trôi thì tệ hơn là không trỏ đâu cả.

## 10. Trạng thái Phase 3 — **đóng**

| Mục | Trạng thái |
|---|---|
| 3.1 Anchors + `u()` | ✅ |
| 3.2 Gates G1–G6 | ✅ |
| 3.3 Objectives + Decision Utility | ✅ |
| 3.4 Paired bootstrap ΔU + nhãn | ✅ |
| 3.5 Decision Card + Manifest | ✅ |

**DoD Phase 3** ("unit test từng module với trace giả lập; card JSON validate được bằng
schema trong `contracts/schemas/`") — đạt.

Kế tiếp là **Phase 4 — lát cắt dọc** (`scripts/vertical_slice.py`), van chặn phương pháp
luận. Lưu ý một nghĩa vụ đang treo: §16 ghi bản 2.0.0 là MAJOR nên đòi chạy lại lát cắt
dọc, mà lát cắt dọc chưa tồn tại — nghĩa vụ đó rơi vào lần đầu chạy Phase 4. Contract
hiện đã là 2.2.0 và vẫn **chưa đủ chữ ký** (cần Dev A và Dev C).
