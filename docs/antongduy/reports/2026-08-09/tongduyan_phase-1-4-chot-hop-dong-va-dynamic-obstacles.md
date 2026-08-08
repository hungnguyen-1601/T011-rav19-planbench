# Báo cáo — Phase 1.4: Chốt hợp đồng + `dynamic_obstacles` (contracts 1.1.0)

> **Ngày:** 2026-08-09 *(phiên làm việc liên tục từ 2026-08-08 — Phase 1.1–1.3 nằm ở `reports/2026-08-08/`)*
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **1.4**
> **Nhánh:** `integrate-tongduyan`
> **Phạm vi:** 1.4 + một thay đổi hợp đồng do user chốt (`dynamic_obstacles`).
> **Kết quả:** Phase 1 **xong toàn bộ**. `contracts_version` 1.0.0 → **1.1.0**.

---

## 1. Quyết định của user được thực hiện

Báo cáo 1.3 nêu một lỗ hổng hợp đồng: `TaskProfile` (HĐ-2) không có vật cản
động, nhưng HĐ-3.3 định nghĩa bộ `evaluation` là "mission × **lần hiện thực vật
cản** × seed". Hai hướng được đưa ra; **user chọn hướng 1** — thêm khối
`dynamic_obstacles` vào `TaskProfile.environment`.

### 1.1. Đã làm

`EnvironmentRef` → **`EnvironmentSpec`** (đổi tên vì giờ nó *đặc tả* môi trường,
không chỉ *trỏ* tới bản đồ — chỉ 3 chỗ tham chiếu, đổi rẻ), thêm:

```python
dynamic_obstacles: tuple[DynamicObstacle, ...] = ()
```

Tái dùng nguyên `DynamicObstacle` sẵn có (4 motion kind: waypoint, periodic,
random_walk, sudden_stop) — không thêm schema mới.

**Vì sao ở environment chứ không ở candidate:** mật độ traffic là thuộc tính của
hiện trường. Để nó trên candidate thì một stack được đánh giá trong kho trống
còn stack khác gặp giờ đổi ca, và bảng xếp hạng báo "thuật toán tốt hơn" cho một
bài toán dễ hơn — đúng lỗi mà cả đề tài này tồn tại để chống.

### 1.2. Bẫy thống kê phát hiện khi đọc `DynamicObstacle` — và luật cứng để chặn

`DynamicObstacle.seed_time_offset` mặc định **0.0**. Docstring của nó (viết từ
trước) đã cảnh báo: `waypoint`, `periodic`, `sudden_stop` là hàm thuần của thời
gian, nên với offset 0 chúng **bỏ qua seed hoàn toàn**.

Hệ quả trong thế giới mới nghiêm trọng hơn nhiều so với thế giới cũ. Một
`TaskProfile` khai traffic với offset mặc định sẽ làm 300 seed phát lại **một
episode 300 lần**. Khi đó G2 nhận một cận trên rule-of-three có **số mẫu hiệu
dụng là 1** chứ không phải 300, và Decision Card in "cận trên 95%: 1,0%" trong
khi bằng chứng không đỡ được gì cả. Đúng chiều sai mà một phát biểu an toàn
không bao giờ được phép mắc, và **hoàn toàn vô hình** khi review: mọi con số
trông hợp lý.

Nên thêm luật cứng vào validator của `EnvironmentSpec`:

```
motion.kind ∈ {waypoint, periodic, sudden_stop}  ⇒  seed_time_offset > 0
```

`random_walk` lấy hướng từ seed episode sẵn nên miễn. Danh sách để dạng
`frozenset` chứ không dùng `isinstance`, để một motion kind mới **buộc** phải
được phân loại có ý thức — quên thêm vào là tái sinh đúng lỗi này trong im lặng.

Thêm luật tên obstacle duy nhất: tên được trộn vào hash seed của từng obstacle,
nên hai obstacle cùng tên sẽ di chuyển đồng bộ.

**Environment không có vật cản động vẫn hợp lệ** (hiện trường tĩnh, hoặc chỉ
nghiên cứu chất lượng đường toàn cục). Nhưng cùng vấn đề số mẫu hiệu dụng tồn
tại ở đó: planner tất định + không traffic ⇒ mọi seed cho cùng một episode.
Không chặn ở schema vì đó là một cách dùng chính đáng; **ghi vào docstring và
vào contract rằng bảng cổng (3.2) là nơi phải nói thẳng điều đó**. Đây là việc
phải làm khi hiện thực G2, đã ghi lại để không rơi.

## 2. Chốt hợp đồng (1.4)

### 2.1. Move

`git mv docs/antongduy/CONTRACTS_1.md contracts/CONTRACTS.md` — giữ history.
Contract giờ ở gốc repo, ngang hàng với code, không nằm trong thư mục ghi chú cá
nhân của một người. Cập nhật `docs/antongduy/README.md`: bảng ba file nền tảng
(đề tài mới / contract / đề bài gốc) + mục "Đã đóng băng" giải thích số phận
plan-report hướng cũ.

### 2.2. Bốn thay đổi nội dung, version 1.0.0 → 1.1.0

| # | Mục | Loại | Nội dung |
|---|---|---|---|
| 1 | **HĐ-2.3 mới** | MINOR (thêm trường có mặc định) | `environment.dynamic_obstacles` + luật `seed_time_offset > 0` + luật tên duy nhất. Kèm YAML ví dụ ở 2.1 |
| 2 | **HĐ-7.0 mới** | thu hẹp ngữ nghĩa | Từ vựng quan sát là tập đóng. Ghi rõ đây là phép **thu hẹp**: input trước đây parse được giờ có thể bị từ chối |
| 3 | **HĐ-7.2** | bảo lưu | Sim-only: không có bo mạch đích ⇒ `realtime_gate.status` **luôn** `screened_on_host`, `verified_on_target` không xuất hiện, Target Verifier ngoài phạm vi |
| 4 | **§16** | PATCH | Bảng ánh xạ bố cục logic → vật lý, thay cây thư mục của 1.0.0 |

Thêm **§18 Lịch sử phiên bản** (bảng + chi tiết từng thay đổi) và 2 dòng vào
danh sách cấm §17:

> 11. Khai vật cản động tất định với `seed_time_offset = 0` rồi đếm N lần chạy như N mẫu độc lập.
> 12. In `verified_on_target` khi dự án không có bo mạch đích.

**Ba thứ frozen không đổi** đúng như §0 yêu cầu: định danh candidate (HĐ-1.3),
payload hash của episode context (HĐ-3.1), schema trace (HĐ-5).

Về mục 2 — thu hẹp ngữ nghĩa nghiêm ngặt mà nói là MAJOR. Xếp vào MINOR vì:
contract 1.0.0 chưa bao giờ *tuyên bố* trường này là chuỗi tự do (mọi ví dụ đều
là `lidar_2d`), mọi ví dụ trong contract vẫn parse được, và chưa có bản ghi nào
được lưu dưới schema này (schema ra đời cùng ngày). Vẫn ghi thẳng vào §18 thay
vì để lặng lẽ, để người review tự phán quyết lại nếu không đồng ý.

### 2.3. §16 — một ngoại lệ có lý do được ghi vào hợp đồng

Bảng ánh xạ ghi rõ `EpisodeContext` nằm ở `packages/schemas/`, không ở `runner/`
như §16 bản 1.0.0 vẽ, kèm lý do (ba nơi cần nó; đặt trong runner thì decision
phải import runner, ngược chiều bridge candidate ⇒ vòng import). Phần *sinh*
context vẫn ở `runner/contexts.py` đúng bảng. Ghi vào contract chứ không chỉ
trong report vì đây là thứ người đọc §16 sẽ thắc mắc.

### 2.4. Ký

Đã ký 1 chữ (Dev B, 2026-08-09) kèm bảo lưu sim-only. **Chưa đủ** — quy trình
mục 0 cần ≥2 approve. Đã thêm ghi chú trỏ Dev A và Dev C đọc §18 trước, vì nó
liệt kê đúng 4 chỗ khác so với bản mọi người đã xem.

## 3. Khóa version giữa doc và code

`packages/schemas/planbench_schemas/contracts.py` (mới):
`CONTRACTS_VERSION = "1.1.0"`, một nguồn duy nhất cho mọi Decision Card (HĐ-12)
và manifest (HĐ-13).

`tests/test_contract_version.py` (mới) — 4 test đọc thẳng
`contracts/CONTRACTS.md`:

1. version trong code là semver hợp lệ;
2. **khớp** header của contract — lệch thì fail kèm câu "bump both in one PR";
3. version hiện tại **có một dòng trong bảng §18** — bump mà không ghi lý do thì
   không review được (HĐ-0);
4. **mọi** ví dụ JSON trong contract quote đúng version hiện tại — chống việc ai
   đó copy ví dụ Decision Card rồi dán một version cũ vào code mới.

Test 2 và 4 chặn đúng cái lỗi tầm thường nhất và khó thấy nhất: sửa doc quên sửa
code (hoặc ngược lại), rồi một card đã lưu tự khai là được sinh ra dưới bộ luật
không phải bộ luật đã sinh ra nó — và tiêu chí nghiệm thu HĐ-13 (đưa manifest
cho người khác, họ dựng lại đúng card đó) âm thầm ngừng đúng.

## 4. Test

- `tests/test_task_profile.py`: **+6 test** cho traffic (`TestEnvironmentTraffic`) —
  traffic do deployment khai, environment tĩnh hợp lệ, offset 0 bị từ chối,
  parametrize cả `waypoint` và `sudden_stop` (khẳng định luật phủ **mọi** motion
  tất định, không chỉ cái trong fixture), `random_walk` miễn offset, tên trùng
  bị từ chối.
- `tests/test_contract_version.py` (mới): **4 test**.
- `tests/task_profile_fakes.py`: thêm `TRAFFIC` (một xe nâng `periodic`,
  `seed_time_offset=6.0`) và helper `environment()`.
- 5 file test của Phase 1 → **128 passed**.
- `ruff check packages tests/` sạch; đã format.
- Full suite: xem mục 6.

## 5. Dọn dẹp trong lượt này

| Việc | Loại |
|---|---|
| `CONTRACTS_1.md` ra khỏi `docs/antongduy/` vào `contracts/` (git mv, giữ history) | contract là luật của cả nhóm, không phải ghi chú cá nhân |
| `EnvironmentRef` → `EnvironmentSpec` | tên cũ sai nghĩa sau khi thêm traffic |
| `docs/antongduy/README.md` viết lại: bảng ba file nền tảng + mục "Đã đóng băng" | README còn trỏ `plans/2026-08-04` là "plan chính chờ approve" — sai từ lúc chuyển hướng. Ghi rõ số phận P05 (giữ code, không port) |
| Cây thư mục §16 của contract | thay bằng bảng ánh xạ — cây cũ mô tả một repo không tồn tại |

## 6. Kết quả full suite

*(cập nhật khi lệnh chạy nền xong)*

## 7. Phase 1 đóng — trạng thái và việc tiếp theo

| Mục | Trạng thái |
|---|---|
| 1.1 TaskProfile (HĐ-2) | ✅ + `dynamic_obstacles` |
| 1.2 Candidate + `candidate_id` (HĐ-1) | ✅ |
| 1.3 EpisodeContext + ghép cặp (HĐ-3) | ✅ |
| 1.4 Chốt hợp đồng | ✅ code + doc; **chờ 2 chữ ký còn lại** |

Ba định danh/schema mà §0 cấm đổi sau tuần 1: hai cái đầu (HĐ-1.3, HĐ-3.1) đã
đóng băng và có test khóa. Cái thứ ba (HĐ-5 trace schema) là việc đầu tiên của
Phase 2.

**Phase 2 — đường dữ liệu**, theo bảng tra của backlog:

- **2.1 TraceRecorder Parquet** (khóa cứng #3) — cần `pyarrow`; metadata đã có
  đủ (`episode_context_id`, `candidate_id`, `task_profile_id`, `sample_set`);
- **2.2 Map loader PGM/YAML** — song song được, không phụ thuộc 2.1;
- **2.3 `metrics/definitions.py`** — cần 2.1 xong trước (input duy nhất là trace).

Một việc phát sinh phải nhớ, đã ghi ở mục 1.2: khi hiện thực **G2 (phase 3.2)**,
gate phải phát hiện và nói thẳng trường hợp số mẫu hiệu dụng thấp — environment
không có traffic, hoặc traffic không đổi theo seed. Schema đã chặn trường hợp
thứ hai; trường hợp thứ nhất là việc của gate.
