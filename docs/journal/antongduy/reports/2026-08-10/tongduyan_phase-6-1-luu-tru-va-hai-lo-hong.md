# Báo cáo — Phase 6.1: Lưu trữ tầng quyết định, và hai lỗ hổng của chính hợp đồng

> **Ngày:** 2026-08-10 · **Nhánh:** `plannerselector_p2`
> **Plan nguồn:** `plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **Phase 6.1**
> **Contract:** `4.2.0` → **`5.0.0`** (MAJOR, hai đổi ngữ nghĩa)
> **Vì sao làm được mà không cần 5.1:** migration và schema không phụ thuộc số episode. Mũi
> tên `P6 ◄─ P5` trong backlog là danh nghĩa.

---

## 1. Đã làm

| # | Việc | Kết quả |
|---|---|---|
| 1 | Sửa phép quét anchor (nợ từ Phase 5.3) | Hỏng theo **hai** cách ngược nhau — mục 2 |
| 2 | Manifest HĐ-13 lưu bản ghi context đầy đủ | Nghĩa vụ tái lập **chưa từng đúng** từ 1.0.0 — mục 3 |
| 3 | Migration `0005` + ORM ba bảng | mục 4 |

Full suite: **1970 passed, 6 skipped**. Baseline 1959 — thêm 11 test, không vỡ test nào. Ruff sạch.
Lát cắt dọc chạy lại dưới `5.0.0` (nghĩa vụ MAJOR của §0 luật 3): **6/6 tiêu chí xanh**,
`decision_utility = 0.820518` không đổi.

---

## 2. Phép quét anchor hỏng theo hai cách ngược nhau

Phase 5.3 đã nêu cách hỏng thứ nhất và để lại cho dev quyết. Sửa nó thì lộ ra cách thứ hai,
tệ hơn nhiều vì nó **im lặng hoàn toàn**.

### 2.1. Cách hỏng thứ nhất — nhân cả hai đầu giết metric bị chặn trên

`scaled(1.1)` nhân cả `good` lẫn `bad` với 1,1. Phép đó vừa **giãn** vừa **tịnh tiến** thang.
Với metric bị chặn trên theo định nghĩa, tịnh tiến đẩy cả thang ra khỏi miền: `success_rate` từ
`{good: 1.00, bad: 0.95}` thành `{1.10, 1.045}` — không tỷ lệ thành công thật nào chạm tới đầu
nào, mọi candidate clip về 0, `U_R` chết cho cả trường. Phép quét báo *"khuyến nghị không đổi"*.

**Sửa: xê dịch bề rộng.** Giữ `good` — điểm ta đang nhắm tới — và dời `bad` sao cho khoảng cách
giữa hai đầu thành `f` lần. Câu hỏi "thang có được chọn khéo không" chính là "khoảng cách từ
điểm ăn 1 tới điểm ăn 0 có đúng không". Sau khi sửa, mọi metric ở lại trong miền:

| | khai báo | +10% | −10% |
|---|---:|---:|---:|
| `success_rate` | 1 / 0,95 | 1 / 0,945 | 1 / 0,955 |
| `p99_latency_ms` | 10 / 50 | 10 / 54 | 10 / 46 |
| `min_clearance` | 0,26 / 0 | 0,26 / −0,026 | 0,26 / 0,026 |

### 2.2. Cách hỏng thứ hai — quét đồng loạt **chứng minh được** là vô nghĩa

Sửa xong, tôi chạy lại fixture knife-edge của Phase 5.3 để xác nhận nó vẫn lật. **Nó không lật
nữa.** Quét mọi biên độ tới ±50% cũng không.

Truy ra thì không phải fixture yếu, mà là phép kiểm bất khả thi. Với `bad' = good + (bad−good)·f`:

```
u' = (m − bad') / (good − bad')
   = (m − good − (bad−good)·f) / ((good − bad)·f)
   = 1 − (1 − u)/f
```

Mọi `u` đi qua **đúng một** phép affine, **giống hệt nhau cho mọi metric**. `decision_utility`
là tổ hợp lồi của các `u` với trọng số tổng bằng 1, nên `U' = 1 − (1−U)/f` — và đó là một phép
**tăng nghiêm ngặt** áp cho **mọi candidate như nhau**. Thứ hạng bất biến.

Kiểm bằng số, khớp tới chữ số cuối:

```
8ee649 f=1.1: U=0.782754 -> 0.802503   predicted=0.802503
829ae0 f=1.1: U=0.786754 -> 0.806140   predicted=0.806140
```

**Nghĩa là phép quét viết đúng theo chữ của HĐ-8.3 luật 3 trả về "không đổi" trên _mọi_ đầu
vào.** Đó là số học, không phải bằng chứng. Và nó là loại lỗi tệ nhất trong cả dự án này: một
tấm card in `anchor_stability: unchanged_at_±10%` như một sự trấn an đã được kiểm chứng, trong
khi phép kiểm không có khả năng nói điều gì khác.

Trớ trêu: cách hỏng thứ nhất **che** cách hỏng thứ hai. Bản cũ có lật, nhưng lật vì nó giết
`success_rate` chứ không vì thang quyết định gì. Lần lật duy nhất dự án từng quan sát được là
một sản phẩm phụ của lỗi.

### 2.3. Sửa: quét từng metric một

Cùng hình dạng với phép quét trọng số của HĐ-11.5, và cùng lý do — **mỗi lần một giả định dịch
chuyển thì một lần lật quy được trách nhiệm**. 10 metric × 2 chiều = 20 lần chạy lại tầng
quyết định, vài giây.

Kết quả không chỉ nói *có phải thang của ta quyết định hay không* mà nói **thang nào**:

```
changed_at_min_clearance+10%_and_p99_latency_ms-10%
```

Người đọc cãi lại được câu *"khuyến nghị này phụ thuộc vào chỗ ta vạch ranh giới cho latency"*.
Không ai cãi lại được câu *"đổi ở −10%"*.

Trên kho tham chiếu vẫn là `unchanged_at_±10%` — nhưng giờ câu đó **có nghĩa**: nó sống sót qua
20 phép nhiễu độc lập, thay vì qua một phép nhiễu chứng minh được là trung tính.

### 2.4. Cảnh báo "thang chết" bị gỡ, có chủ ý

Phase 5.3 thêm `degenerate_metrics` để liệt kê metric bị đẩy khỏi miền. Với luật mới, thang
nhiễu **luôn** chung một đầu với thang khai báo, nên tình huống đó không thể xảy ra — trường đó
sẽ vĩnh viễn rỗng. Một cơ chế an toàn không bao giờ kích hoạt được thì đọc như đang bảo vệ mà
thực ra không; gỡ đi, thay bằng test khẳng định **bất biến**: không metric nào bị quét ra khỏi
miền, kiểm trên chính file anchor đang ship.

---

## 3. HĐ-13 chưa từng tái lập được — suốt từ bản 1.0.0

Tiêu chí nghiệm thu của mục này, viết từ bản đầu: *"đưa manifest cho người khác, họ dựng lại
đúng tấm card"*. Nó chưa bao giờ đúng.

Manifest lưu `episode_context_ids`. Mà `episode_context_id` là **hash** của điều kiện (HĐ-3.1),
và hash không đảo ngược được. Người cầm manifest biết *những episode nào* đã chạy nhưng không có
`mission_id`, không có `seed` — mà `compute_metrics` cần cả hai để tính lại một metric.

**Vì sao suốt bốn phase không ai thấy.** Mọi lần chạy của dự án đều dựng manifest và tính metric
**trong cùng một tiến trình**, nơi object `EpisodeContext` vẫn nằm trong bộ nhớ và được truyền
thẳng vào `compute_metrics`. Đường đi qua file — đường mà HĐ-5 và HĐ-13 tồn tại để bảo đảm —
chưa từng có ai đi. Nó sẽ gãy đúng lúc Phase 6.2 đẩy run qua worker, và khi đó **mọi manifest đã
ghi đều mồ côi**.

Docstring của `compute_metrics` đã ghi lại đúng điều này từ Phase 2.3, như một việc phải quyết ở
6.1. Đây là lúc quyết.

**Sửa:** `episode_contexts` mang nguyên bản ghi. `episode_context_id` là computed field của
`EpisodeContext`, nên danh sách id vẫn còn — **dẫn xuất**, không lưu hai lần. Kèm một chốt chặn:
`build_manifest` từ chối nếu thiếu bản ghi cho bất kỳ episode nào các candidate đã được chấm
trên đó.

**Và nghĩa vụ giờ được _chạy_ chứ không được _khẳng định_.** Test mới trong
`tests/test_vertical_slice.py` đọc `manifest.json` và trace **từ đĩa**, dựng lại `EpisodeContext`
từ JSON, rồi gọi `compute_metrics` — vứt bỏ mọi object trong bộ nhớ, đúng như một người lạ sẽ
làm. Đây là loại test lẽ ra phải có từ Phase 2.3: một tiêu chí nghiệm thu chỉ được viết ra mà
không được chạy thì không phải tiêu chí.

Đổi trường ⇒ **MAJOR**. Schema JSON trong `contracts/schemas/manifest.schema.json` cũng đổi theo,
vì đó mới là hợp đồng máy kiểm được.

---

## 4. Migration `0005` — ba bảng

| Bảng | Khóa chính | Ghi chú |
|---|---|---|
| `task_profiles` | `id` | Cả profile lưu JSON; chỉ `environment` và `owner_user_id` lên cột |
| `candidates` | **`candidate_id`** | Không dùng khóa thay thế — xem dưới |
| `decision_cards` | `id` | `card` + `manifest` lưu trong hàng; trace nằm ngoài, trỏ bằng `run_uri` + `run_checksum` |

**Ba quyết định đáng ghi:**

**Thân hợp đồng lưu JSON, không băm thành cột.** `TaskProfile`, `Candidate` và card đều là model
Pydantic frozen mà tầng decision validate ở đầu vào. Băm chúng thành cột sẽ tạo **định nghĩa thứ
hai** của mỗi hợp đồng, viết bằng DDL, rồi trôi khỏi định nghĩa thứ nhất — đúng thứ §16 đặt một
chủ sở hữu cho mỗi schema để chặn. Chỉ trường nào truy vấn cần mới lên cột.

**`candidate_id` là khóa chính, không phải khóa thay thế.** HĐ-1.3 làm nó thành hash của
planner + controller + tham số + version + yêu cầu quan sát, nên hai hàng cùng id **là** cùng
một cấu hình. Khóa tự tăng sẽ cho phép cùng một stack đăng ký hai lần dưới hai tên và tự chia
đôi lịch sử của chính nó.

**`decision_cards` → `task_profiles` là `RESTRICT`, không phải `CASCADE`.** Card là một phát biểu
**về** một deployment profile. Xóa profile mà giữ card thì còn lại một khuyến nghị không ai diễn
giải được; xóa luôn card thì phá hồ sơ kiểm toán. Cả hai đều tệ hơn việc từ chối lệnh xóa.

Test có sẵn `test_migration_matches_the_models` đã so từng cột giữa migration và ORM, nên 5 test
mới chỉ kiểm những quyết định mà phép so đó không nhìn thấy: khóa nào được chọn, lệnh xóa được
làm gì, và cái gì **không** được vào database (`assert not {name for name in columns if "trace"
in name}`).

---

## 5. Một ghi chú về cách hai lỗi này lộ ra

Cả hai đều **không** lộ ra khi đọc code. Cái thứ nhất lộ khi Phase 5.3 in ra một dòng cảnh báo
mà tôi phải giải thích. Cái thứ hai lộ khi tôi chạy lại một fixture cũ sau khi sửa và thấy nó
**hết lật** — nếu tôi tin phép sửa và không chạy lại, phép kiểm vô nghĩa đó đã sống sót tới UI.
Cái thứ ba (HĐ-13) lộ vì Phase 2.3 ghi nó vào docstring thay vì để trong đầu.

Ba lần, cùng một cơ chế: **viết cái mình định làm ra chỗ người khác đọc được, rồi chạy lại thứ
lẽ ra không được đổi.**

---

## 6. Chưa làm — cố ý

- **Repository + router (6.2)** — bảng đã có, đường đọc/ghi chưa. Đó là lượt tiếp theo.
- **`run_checksum` chưa có ai ghi.** Cột tồn tại và có nghĩa; hàm tính checksum trên thư mục
  trace thuộc 6.2, nơi có thứ để ghi.
- **`robustness_margin`** — vẫn `null`, cần Task Neighborhood.

## 7. Trạng thái

| Phase | Trạng thái |
|---|---|
| 1–4 | ✅ |
| 5.2 Pareto · 5.3 Sensitivity | ✅ |
| **6.1 Lưu trữ** | ✅ |
| 5.1 Evaluation distribution | chưa — cần máy rảnh, xem dưới |
| 6.2 Router · 6.3 Approval | chưa |

**Nhắc lại về 5.1, vì nó rẻ hơn tưởng:** `N_min = ceil(3 / collision_probability_max)`, và ngưỡng
đó **do deployment khai**. Profile kho hiện khai 0,1 ⇒ `N_min = 30` ⇒ bộ 30 episode đang có
**đã thỏa G2 một cách thành thật**. Con số 2,8 giờ là cái giá để **nâng tuyên bố** lên 1%, không
phải cái giá để 5.1 hợp lệ. Mức trung gian 0,03 ⇒ 100 episode ⇒ khoảng 57 phút.
