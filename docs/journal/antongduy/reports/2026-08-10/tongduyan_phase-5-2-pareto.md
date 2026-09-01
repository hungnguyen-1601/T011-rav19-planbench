# Báo cáo — Phase 5.2: Phân tích Pareto non-inferiority (HĐ-10)

> **Ngày:** 2026-08-10 · **Nhánh:** `plannerselector_p2`
> **Plan nguồn:** `plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **Phase 5.2**
> **Contract:** `4.1.0` → **`4.2.0`** (MINOR — HĐ-10.2 viết đủ, không thêm trường nào)
> **Vì sao làm được trước 5.1:** Pareto là hàm thuần trên objective theo từng episode. Cái cần
> 300 episode là **độ tin cậy của kết luận**, không phải khả năng viết code — và bài kiểm tra
> quan trọng nhất của HĐ-10.2 lại chạy tốt nhất trên bộ nhỏ.

---

## 1. Kết quả trên kho tham chiếu

```
pareto:         PARETO_FRONTIER
  2baaad3628e1: PARETO_FRONTIER
alternative:    2baaad3628e1
```

Cả hai candidate lên biên, và đó là câu trả lời đúng: A\*+DWA hơn về chi phí (p99 5,5 ms so với
12,0 ms), RRT\*+DWA hơn về an toàn (clearance 0,070 so với 0,041). Không bên nào lấn át bên nào,
nên **không bộ trọng số không âm nào loại được bên nào** — cả hai đều là lựa chọn hợp lệ, và
việc A\* thắng là chuyện của trọng số cụ thể mà kho này khai.

Đây cũng là lần đầu **`alternative` trên Decision Card có giá trị**. Trước phase này nó luôn
`null` vì HĐ-12 chỉ cho lấy từ candidate mang nhãn `PARETO_FRONTIER`, mà nhãn đó chưa tồn tại.

Sáu tiêu chí HĐ-15.1 vẫn xanh, `decision_utility = 0.820518` không đổi — Pareto **gắn nhãn,
không chọn người thắng**.

---

## 2. Phát hiện lớn nhất: quy tắc kết luận được từ **một** episode

Bài kiểm tra bắt buộc của HĐ-10.2 là *"nếu không có dữ liệu thì quy tắc làm gì?"* — đáp án đúng
luôn là "không làm gì". Tôi viết test đó trước, chạy, và **nó đỏ**: với `n = 1`, quy tắc tuyên
bố lấn át.

**Vì sao.** Bootstrap phân vị trên `n` điểm chỉ sinh được `n` giá trị khác nhau. Với `n = 1`,
mọi lần lấy mẫu lại đều rút đúng điểm đó, phân bố bootstrap là một điểm, "CI 95%" rộng bằng 0,
và `LCB` bằng chính hiệu số quan sát được. Quy tắc đọc `LCB` rất dương và kết luận lấn át **với
độ tin cậy tối đa từ một episode**.

Đây đúng chiều sai mà cả HĐ-10.2 tồn tại để chặn — và trớ trêu là nó len vào qua chính công cụ
được chọn để chặn nó. Khoảng tin cậy được chọn thay cho quy tắc "CI không nằm hoàn toàn dưới 0"
vì nó *phải* thận trọng khi thiếu dữ liệu. Nhưng máy móc khoảng tin cậy **không phân biệt được
"không có phương sai" với "không có dữ liệu"** — đúng điểm mù mà `DEGENERATE_SPREAD` của HĐ-11
phải chặn ở effect size, xuất hiện lại ở một tầng khác.

**Cách chữa: khai báo sàn, không suy ra.** `MIN_EPISODES_FOR_DOMINANCE = 10`. Dưới sàn, một cặp
**không** lấn át nhau **và cũng không** được kết luận là không lấn át — nó rơi vào
`UNCERTAIN_DOMINANCE`, đúng nghĩa của nhãn.

Có test khẳng định tính chất then chốt: cùng một cặp candidate thật sự bị lấn át, chạy `n = 2`
**không** kết luận, chạy `n = 30` mới kết luận. *Ít dữ liệu không bao giờ được kết luận nhiều
hơn nhiều dữ liệu.*

> Ghi lại vì nó lặp lại một bài học: **viết bài kiểm tra của contract trước, rồi chạy.** Nếu tôi
> viết test sau khi hiện thực xong, nhiều khả năng tôi đã dựng fixture 30 episode cho tiện và
> lỗ hổng `n = 1` sống sót tới lúc có người chạy thử một run nhỏ.

---

## 3. Ba nhãn cần hai phép kiểm, không phải một

Chỗ dễ làm sai thứ hai, và contract để ngỏ. HĐ-10.1 cho ba nhãn nhưng HĐ-10.2 chỉ định nghĩa
**một** điều kiện — lấn át. Câu hỏi còn lại: trong số những candidate *không* bị lấn át, cái nào
là `PARETO_FRONTIER` và cái nào là `UNCERTAIN_DOMINANCE`?

Câu trả lời sai là gộp cả hai: *"không bị ai lấn át ⇒ lên biên"*. Sai vì **"chưa ai chứng minh
được nó bị lấn át" không đồng nghĩa với "không ai lấn át nó"** — một candidate chưa đo đủ cũng
thỏa vế đầu. Gộp lại thì `n = 1` cho cả trường lên biên, và card in `PARETO_FRONTIER` như một
phát hiện.

Nên `PARETO_FRONTIER` đòi **bằng chứng dương**, đọc từ **cận trên** đúng cách lấn át đọc từ cận
dưới. Lấn át cần hai vế cùng đúng, nên nó bị bác khi chứng minh được **một trong hai** vế hỏng:

```
A KHÔNG THỂ lấn át B  ⟸  ∃j: UCB₉₅(ΔU_j) < −ε_j      (B hơn hẳn ở đâu đó)
                       ∨  ∀k: UCB₉₅(ΔU_k) ≤ +ε_k      (A không hơn hẳn ở đâu cả)
```

Vế thứ hai là thứ tôi suýt bỏ sót, và nó cần thiết: **hai candidate thật sự tương đương, đo
kỹ** — khoảng tin cậy ôm lấy 0, không bên nào hơn quá ε — phải cùng lên biên. Chỉ có vế đầu thì
chúng rơi vào `UNCERTAIN_DOMINANCE` mãi mãi, dù dữ liệu có nhiều đến đâu. Đó là một **kết luận**
bị dán nhãn "chưa đủ dữ liệu".

Còn lại — không lấn át được ai, cũng chưa loại trừ được ai lấn át mình — mới là
`UNCERTAIN_DOMINANCE`.

**Candidate đơn độc luôn `UNCERTAIN_DOMINANCE`,** không phải `PARETO_FRONTIER`. "Không ai lấn át
nó" đúng một cách tầm thường khi không có đối thủ, mà trên card thì câu đó đọc như một phát hiện.

---

## 4. Hai quy tắc sai mà đề tài đã ghi lại, viết thành test

Tài liệu mẹ (N10) ghi rằng hai bản trước của chính nó đều sai, theo hai kiểu ngược nhau. Cả hai
giờ là test thường trực, vì một quy tắc chỉ đúng trong văn bản thì lần refactor sau sẽ mất.

**Sai kiểu 1 — quá chặt:** *"A phải hơn B ≥ ε ở mọi objective"*. Chỉ cần hòa đúng một objective
là quy tắc tắt, dù A hơn 0,10 ở tất cả chỗ còn lại.

`test_one_tied_objective_does_not_switch_the_rule_off` dựng đúng ca đó: hai candidate có `U_R`
**hòa tuyệt đối** (mọi episode đều thành công, `ΔU_R = 0` tới 1e-12) trong khi một bên tệ hơn ở
cả ba objective còn lại. Test khẳng định nó **vẫn bị lấn át**, và assert luôn cả việc `U_R` thật
sự hòa — nếu không thì test xanh mà không kiểm cái nó nói đang kiểm.

**Sai kiểu 2 — quá lỏng, và sai về bản chất logic:** *"với mọi j, CI không nằm hoàn toàn dưới
0"*. Lẫn **không có bằng chứng A tệ hơn** với **có bằng chứng A không tệ hơn**. Ít dữ liệu ⇒ CI
rộng ⇒ dễ tuyên bố lấn át hơn.

`test_thin_data_never_concludes_more_than_thick_data` khẳng định tính chất ngược lại — và chính
nó là test đã bắt lỗi ở mục 2.

---

## 5. Chỗ phải sửa ở tầng dưới: `CandidateEvidence` chỉ giữ utility vô hướng

HĐ-10.2 so **theo từng objective**, mà `CandidateEvidence.episode_utilities` chỉ lưu
`decision_utility` cho mỗi episode. Bốn thành phần đã bị gộp lại và không dựng ngược được.

Sửa: trường đổi thành `episode_objectives: dict[str, ObjectiveBreakdown]`, và
`episode_utilities` thành **property dẫn xuất**. Cân nhắc phương án lưu cả hai và bỏ: hai bản
sao của cùng một con số sẽ có ngày lệch nhau, mà bên nào lệch thì cũng không ai biết.

Kèm theo, tách `paired_bootstrap_ci` thành hàm dùng chung của `stats.py`. Trước đó phép bootstrap
nằm lọt trong `compare_pair`; Pareto cần đúng phép đó nên hoặc dùng chung, hoặc có bản sao thứ
hai. Hai bản sao ở đây đặc biệt tệ: một candidate có thể là `CLEAR_RECOMMENDATION` so với đối thủ
dưới bootstrap này và bất phân thắng bại so với **cùng đối thủ đó** dưới bootstrap kia.

Chi tiết nhỏ nhưng có chủ ý: mỗi objective bootstrap bằng `seed + index` chứ không cùng một seed.
Dùng chung một ma trận chỉ số sẽ làm bốn khoảng tin cậy tương quan với nhau theo cách dữ liệu
không hề nói.

---

## 6. Hai chốt chặn mới trên card

**Candidate bị lấn át không bao giờ được khuyến nghị.** Nếu tổng có trọng số vẫn đẩy một
`LIKELY_DOMINATED` lên đầu thì bất đồng đó không phải chuyện làm tròn: có đối thủ không tệ hơn ở
**cả bốn** objective và hơn ở ít nhất một, nên khuyến nghị là **sản phẩm của bộ trọng số**, không
phải của dữ liệu. `build_decision_card` từ chối, nêu tên người lấn át.

**Mọi candidate được chấm đều phải mang nhãn.** HĐ-10.1: không ai biến mất khỏi báo cáo. Thiếu
một nhãn là từ chối, không phải bỏ qua.

Cộng với dedupe: `ParetoLabel` từng được khai hai lần — một ở `card.py`, một ở `pareto.py`. Giờ
`pareto.py` sở hữu, `card.py` import và re-export. Hai bản Literal giống nhau sẽ trôi ngay lần
đầu HĐ-10.1 có nhãn thứ tư.

---

## 7. Test

`tests/test_pareto.py`: **25 test**, cộng 5 test card.

- **Bài kiểm tra của contract (3):** một episode không kết luận gì · và gắn nhãn tất cả là
  `UNCERTAIN_DOMINANCE` · ít dữ liệu không kết luận nhiều hơn nhiều dữ liệu.
- **Lấn át (9):** tệ hơn mọi mặt thì bị lấn át · không đối xứng · đánh đổi không phải lấn át ·
  hòa mọi mặt không phải lấn át · **một objective hòa không tắt quy tắc** · không tự lấn át mình ·
  ε = 0 bị từ chối · tập context lệch bị từ chối trước khi tính · tái lập.
- **Gắn nhãn (6):** đánh đổi đưa cả hai lên biên · bị lấn át thì **gắn nhãn chứ không xóa** ·
  người lấn át giữ biên · candidate đơn độc là `UNCERTAIN` · ba candidate ra đủ ba nhãn · gắn
  nhãn cho người ngoài field bị từ chối · mọi cặp có thứ tự đều được so.
- **`alternative` (4):** lấy từ biên · **hạng nhì bị lấn át không bao giờ được đề xuất** · không
  có ai trên biên thì không có alternative · theo đúng thứ tự ranking.
- **ε (2):** mặc định đúng contract · nới ε thì kết luận **ít** đi, không nhiều lên.
- **Card (5):** chưa chạy phân tích thì không khẳng định gì · nhãn đến từ phân tích · alternative
  là candidate trên biên · **leader bị lấn át bị từ chối** · thiếu nhãn bị từ chối.

---

## 8. Chưa làm — cố ý

- **ε riêng cho từng objective.** HĐ-10.2 viết `ε_j` nhưng mặc định cả bốn bằng 0,02, và chưa có
  lý do nào để chúng khác nhau. Chữ ký hàm nhận một `epsilon`; đổi thành bốn là MINOR khi cần.
- **Sàn 10 episode chưa được hiệu chỉnh.** Nó là một sàn hợp lý, không phải một ngưỡng dẫn xuất
  từ độ phủ của bootstrap. Với Phase 5.1 chạy 300 episode thì nó không bao giờ chạm tới; nó tồn
  tại để chặn ca thoái hóa.
- **`robustness_margin`** — vẫn `null`, cần Task Neighborhood.

## 9. Trạng thái

| Phase | Trạng thái |
|---|---|
| 1–4 | ✅ |
| 5.2 Pareto | ✅ — `alternative` và `pareto_label` lần đầu có giá trị thật |
| 5.3 Sensitivity | ✅ |
| **5.1 Evaluation distribution N=300** | chưa — cần ~2,8 giờ **máy rảnh** (HĐ-7.4) |

Phase 5 giờ chỉ còn 5.1, và nó là việc chạy chứ không phải việc viết. Khi chạy xong, cả Pareto
lẫn sensitivity **tự có số chặt hơn mà không phải sửa dòng nào** — sàn 10 episode và mọi khoảng
tin cậy đều tính lại từ cùng bộ trace.
