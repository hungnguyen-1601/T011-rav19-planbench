# D1 — hai hành động của con người, tách đôi

**Ngày:** 2026-08-12 · **Pha:** 6.3 (backlog 08-08) · **Lược đồ:** `0007` · **Điều khoản:** HĐ-14

---

## 1. Vì sao không phải một cột `approved`

Một cờ `approved` trên `decision_runs` ngắn hơn, và **sai**. Lý do y hệt cái đã lật bảng ở `0006`:
**phần lớn run không sinh ra khuyến nghị nào.**

Bốn trên năm phép so đầu tiên của dự án không ra card. Với một cột duy nhất, những dòng đó ép ta
chọn một trong hai, và cả hai đều hỏng:

- **Cho duyệt** — thế thì `approved` mang nghĩa *"có người đọc bảng cổng"* ở dòng này và *"đây là
  cấu hình đem triển khai"* ở dòng kia, mà không có gì trong cột nói đang là nghĩa nào.
- **Cấm hẳn** — thế thì một run loại được bốn candidate **không có chỗ nào ghi rằng đã có ai nhìn
  vào nó**, và đó đúng là cách nó trở thành artifact bị bỏ quên — điều bạn đã chốt phải tránh khi
  trả lời Q3 ngày 11-08.

Nên hai cột, trả lời hai câu hỏi khác nhau:

| cột | câu hỏi | áp cho |
|---|---|---|
| `review_state` | đã có người đọc bằng chứng của run này chưa? | **mọi** run |
| `config_state` | khuyến nghị của run này có phải cấu hình ta triển khai không? | chỉ run có card |

## 2. `not_applicable` làm việc chính

`config_state` của một run không card là `not_applicable`. Đó **không** phải một giá trị trang trí:
nó là lời từ chối, và đặt nó thành *trạng thái* thay vì một `if` trong endpoint có nghĩa là

- người viết endpoint thứ hai không thể quên nó, và
- **không tồn tại đường đi** từ `not_applicable` sang `approved`.

Duyệt một run không recommend ai sẽ biến *"cái này đã được đo"* thành *"cái này đã được chuẩn
thuận"*, và `approved_config.yaml` sinh ra sẽ **không nêu tên candidate nào**.

Cả hai cột đều `NOT NULL` với giá trị mặc định thận trọng, nên một dòng viết bởi đường code chưa
biết tới cột này rơi vào trạng thái *chưa đọc, chưa duyệt được* chứ không phải ngược lại.
`StoredDecisionRun.__post_init__` nâng lên `pending` khi có card — đặt ở dataclass chứ không ở
caller, để cột và đối tượng không thể bất đồng.

## 3. Ba lời từ chối khi duyệt cấu hình

1. **Không card thì không có gì để duyệt.** Đọc thẳng `config_state`, không suy lại từ `card is
   None` — một chỗ kiểm thì không lệch được với giá trị đã lưu.
2. **Không ai duyệt run của chính mình** (HĐ-14). Người chọn candidate, chọn deployment và chọn số
   episode không phải một bước kiểm độc lập với kết quả.
3. **Đã quyết là quyết.** `approved` và `rejected` đều là trạng thái cuối. Cho quyết lại nghĩa là
   một lần từ chối có thể bị lật lặng lẽ sau đó; câu trả lời hợp lệ cho *"chúng ta đã sai"* là
   **một run mới** — rẻ, có ngày tháng, và để lại cả hai bản ghi.

**Đọc thì khác.** Người chạy run **được** đọc run của mình: đọc là tuyên bố đã nhìn, không phải
tuyên bố tán thành. Bắt phải có người thứ hai mới được *đọc* sẽ khiến phần lớn run không ai đọc —
đó là chính cái hỏng cần tránh, không phải hàng rào.

## 4. Chạm vào đâu

| | |
|---|---|
| `decisions.py` | `ReviewState`, `ConfigState`, `ReviewAction`, `ReviewEvent`; sáu trường mới trên `StoredDecisionRun`; `review()`, `decide_config()`, `events()` |
| `db/models.py` | sáu cột trên `DecisionRunRow` + hai index; bảng `decision_run_reviews` |
| `alembic/0007` | thêm cột, backfill `config_state='pending'` cho dòng đã có card, bảng audit, downgrade đối xứng |
| `db/decision_repositories.py` | bản SQL của cùng ba phép, cùng thứ tự từ chối, cùng câu chữ |
| `decision_service.py` | ba phép trên + `approved_config()` sinh YAML |
| `routers/decisions.py` | `POST /decisions/{id}/review` · `POST /decisions/{id}/config-approval` · `GET /decisions/{id}/audit` · `GET /decisions/{id}/approved_config.yaml`; sáu trường mới trên `DecisionRunResource` |

**Bảng audit là bảng mới, không phải `approvals` nới ra.** `approvals.benchmark_id` là khoá ngoại
`NOT NULL` vào `benchmarks`; cho nó nullable để chứa cả hai loại sẽ khiến **mọi dòng audit cũ**
không nói được nó mô tả loại nào.

## 5. `approved_config.yaml` mang theo cái gì

HĐ-14 nói hệ ở chế độ **sim-only**: không có đường dẫn kỹ thuật nào từ UI tới robot thật, và
"triển khai" chỉ là xuất một file. File **tự nói điều đó về chính nó**, ở ngay đầu, chỗ người đọc
sau này nhìn thấy.

Ngoài candidate được chọn, file mang theo `task_profile_id`, `experiment_scope`, ΔU và khoảng tin
cậy, `manifest_ref`, `run_uri` và `run_checksum`. Một file chỉ nêu tên người thắng sẽ mời người ta
đem nó áp vào chỗ chưa bao giờ đo — khuyến nghị chỉ có nghĩa trên **một** deployment (HĐ-1.4), và
bỏ phạm vi đó đi là cách nó thôi đúng.

## 6. Test

`tests/test_decision_review.py` — **43 test, chạy cả hai backend qua cùng một bộ khẳng định**
(`@pytest.fixture(params=["memory", "sql"])`). Hai bản hiện thực là cái giá của việc có hub
in-memory và hub SQL; hai bản **bất đồng** mới là bug, và cách duy nhất để biết là hỏi cả hai cùng
một câu.

Phủ: trạng thái khởi đầu · đọc áp cho mọi run · đọc hai lần bị từ chối · duyệt cần có card · không
tự duyệt · không quyết lại (cả hai chiều) · hai cột không đụng nhau · audit đúng thứ tự kèm cả hai
đầu của thay đổi · **hành động bị từ chối không ghi dòng nào** · run không tồn tại.

`tests/api/test_api_decisions.py` — 4 test HTTP: run không card đọc được, duyệt cấu hình 409 kèm
câu chỉ ra việc làm được thay thế, audit đúng thứ tự, chưa duyệt thì không xuất được config.

`tests/api/test_migrations.py` — 5 test cho `0007`: cột có mặt, mặc định thận trọng và `NOT NULL`,
bảng audit riêng có khoá ngoại, hai cột được đánh index, downgrade chỉ gỡ cái nó thêm.

## 7. Chưa làm, cố ý

- **Chưa có test HTTP cho đường duyệt thành công**, vì nó cần một run **có card** qua API, tức
  ~30 episode mô phỏng thật trong một test. Luật đã được khoá đủ ở tầng repository (cả hai
  backend); phần HTTP còn thiếu đúng một nhánh happy-path. Sẽ có tự nhiên khi UI gọi thật.
- **Chưa có vai `approver` riêng.** HĐ-14 nói hai vai, và hệ hiện chỉ phân biệt "người chạy run"
  với "người khác". Đủ cho chống tự duyệt; chưa đủ nếu sau này cần hạn chế ai được duyệt.
