# Preregistration thống kê và phân vùng dữ liệu — chốt trước B1

**Plan:** `plans/2026-08-26/de-xuat-cai-thien-hieu-qua-ai-analyst.md` bản 6,
mục W0.8 (preregistration) và W0.9 (phân vùng).
**Mã:** `services/analyst_service/planbench_analyst/preregistration.py`,
`eval_spec.py`; nhãn `fixtures/golden/labels/visible.json`.
**Checksum preregistration:**
`17354118e80a864b8d52fd2603342058389366e8a0c81fc7f2d0fc02353f510a`
— pinned trong `tests/test_analyst_eval_spec.py::test_the_preregistration_is_pinned`.
**Checksum eval spec (development):**
`cd06d54aff18934ea0b013f0a58d542885b42905b830535a5017148546c029cc`.

## Ý nghĩa của việc pin checksum

Preregistration là dataclass frozen, hash canonical content. Test pin
checksum nghĩa là: **muốn đổi δ, α, primary endpoint, trọng số router hay số
họ staged thì phải sửa test**, và diff đó là thứ reviewer nhìn thấy. Không có
đường đổi ngầm.

Ngày chốt: 2026-08-26, **trước** B1 (baseline real-host). Mọi số từ B1 trở
đi được đọc theo bản này.

## Nội dung đã chốt

### Hard constraints (veto trước khi so)

| Ràng buộc | Giá trị |
|---|---|
| `structural_violations` | 0 |
| `budget_and_protocol_pass` | 1 (mọi case) |
| `menu_recall_when_filtering` | 1 — nếu W3 lọc menu, tool đúng phải còn trong menu ở mọi case |

Một cấu hình vi phạm hard constraint là **fail**, không có bảng so sánh.

### Primary endpoint — một số, một phép thử

- **Endpoint:** `case_level_mechanism_correctness` — tỷ lệ case mà mechanism
  đề xuất khớp mechanism trồng; mỗi case tính **một** lần, lấy lượt tệ nhất
  trong 3 repeats.
- **Phép thử:** McNemar exact, ghép cặp (cùng packet), analyst vs sàn
  model-free (`reference_analyst`).
- **Non-inferiority:** δ = 0.10 tuyệt đối. Analyst non-inferior khi cận dưới
  CI của (analyst − sàn) > −δ. Một phía, α = 0.05.
- **Superiority:** chỉ tuyên bố khi cận dưới CI > 0. Hai phía, α = 0.05.
- Non-inferior **≠** tương đương: nói "không tệ hơn quá 10 điểm", không nói
  "bằng".

### Secondary endpoints — đọc theo thứ tự, chỉ khi primary đạt

1. `component_attribution_accuracy`
2. `abstention_correctness`
3. `evidence_relevance`
4. `checker_selection_model_chosen`
5. `verified_rate_case_level`
6. `cost_median_tokens_itt`

Hierarchical: dừng đọc ở endpoint đầu tiên không đạt. Không thêm endpoint
sau khi thấy số.

### Tin cậy

- `repeats = 3`, mỗi lượt là một call model độc lập; harness **từ chối** báo
  cáo nếu `cache_hits > 0` (`compare_with_floor(..., cache=)` raise).
- `pass^k` chỉ là tỷ lệ khi **≥ 12 case**; dưới đó là counts + Wilson CI.
  Hiện có 3 case ⟹ mọi `pass^k` từ giờ đến khi đủ case là `(held, cases)`,
  không phải số phần trăm.

### Router oracle (cho E10)

`U = 1.0·quality − 0.02·cost_k_tokens − 0.005·latency_s`. Chốt để chọn oracle
cho router ở W3/E10; đổi trọng số sau khi thấy số là chọn oracle hậu nghiệm.

### Họ staged

3/6: `inflation_gap_closure`, `rrt_sample_starvation`, `dwa_local_minimum`.
Mọi macro average phải in `3/6` bên cạnh.

## Phân vùng dữ liệu

| Tập | Gồm | Dùng cho | Không dùng cho |
|---|---|---|---|
| **Development** | `VISIBLE_SUITE` (12 case spec, 3 có fixture) + mọi packet đội AI đã nhìn | E1–E10, sửa prompt, chọn model/feature/router | Kết luận deployment |
| **Confirmatory** | Hidden suite `preregistered`, mở qua `run_gate` | Một lượt duy nhất sau freeze `bundle_identity` + `runtime_config_checksum` + `eval_spec_checksum` + `router_rule_checksum` | Chọn bất cứ thứ gì |

Cơ chế đã có trong platform và W0 **không đi vòng**:

- `run_gate` fail-closed: đòi hidden + preregistered + packet `recorded`.
- `DryGateRun` không mang decision — rehearsal không bật được feature.
- `load_eval_spec` **từ chối** file nhãn có `partition != development`. Nhãn
  cho confirmatory không tồn tại dưới dạng file ai cũng đọc được.

### Trạng thái hiện tại

`OFFICIAL_GOLDEN_READY = False`, 3/6 họ, chưa tách được holdout ⟹ **mọi kết
quả E1–E10 là exploratory**. Đây không phải lỗi của plan, là sự thật của dữ
liệu, và báo cáo nào không ghi chữ `exploratory` là báo cáo sai.

Case đã xuất hiện trong bất kỳ lượt phát triển nào không được tái dùng trong
confirmatory, kể cả dưới tên khác.

## Biên nhãn — nhãn không tới analyst

- Nhãn ở `fixtures/golden/labels/`, **không** ở trong `packet.json`.
  `assert_no_label_in(view, spec)` chạy trên view của mọi fixture trong test.
- `docker/Dockerfile.analyst` không `COPY fixtures/`, và `RUN rm
  …/golden_fixtures.py` gỡ `VISIBLE_SUITE` (là code, mang expected findings)
  khỏi image. `planbench_explanation` import `VISIBLE_SUITE` lazy qua
  `__getattr__` để package không vỡ khi file vắng.
- Predicate nhãn là **any-of** (`subject` / `ref_prefix` / `scope_prefix`),
  không phải chuỗi ref đúng-từng-ký-tự — một citation khác mà đúng vẫn tính.

## Stratum chốt trước khi chạy

`expected_check_required` nằm trong nhãn, không suy từ nhánh model đi:

- `check_required`: `inflation-001`, `rrt-001`
- `no_check_required`: `dwa-001`

Chi phí W4.7 và E6 báo theo stratum này. Chọn stratum sau khi thấy model gọi
tool hay không là so sánh post-treatment.
