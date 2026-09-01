# Kế hoạch: map custom trong panel khởi chạy, và kết quả từng episode hiện ra

> **Ngày lập:** 2026-08-12 (phiên lập kế hoạch thứ hai trong ngày — tách khỏi
> `viec-con-lai-sau-mvp-v1.md`, vì đó là plan đã làm xong, còn đây là phiên trao đổi riêng)
> **Người lập:** An (cùng Claude) · **Trạng thái:** dev đã chốt ba lựa chọn
> **Bối cảnh:** MVP v1 chốt sáng nay. Dev dùng thử và tìm ra hai lỗ hổng dùng-thật.

---

## 0. Hai lỗ hổng, nguyên văn

1. *"chọn runs để so sánh chưa cho phép tinh chỉnh maps, mà mới chỉ cho chọn 2 maps cố định.
   Tôi cần maps phải được thiết kế custom, vì sau này mô phỏng không phải chỗ nào cũng
   giống nhau."*
2. *"sau khi run xong và trả về kết quả, tôi chỉ nhìn thấy id của các lần chạy, chứ không
   thật sự biết được run nào fail run nào success. Chúng không được hiện trên UI."*

### Dev chốt phạm vi

| câu hỏi | chốt |
|---|---|
| "run fail/success" ở cấp nào | **cả hai**: từng episode trong một phép so, **và** từng run trong danh sách `/decisions` |
| map custom hình thức nào | **nối editor sẵn có** (`/maps`) vào task profile |
| chỗ chỉnh map nằm ở đâu | **trong panel khởi chạy `/decisions`** |

---

## 1. Vì sao hai lỗ hổng này có cùng một hình dạng

Cả hai đều là **dữ liệu đã có mà không đi ra được tới màn hình**.

- `EpisodeMetricSet` có `success: bool` và `failure_reason` cho **từng** episode
  ([definitions.py:97-98](../../../../../packages/metrics/planbench_metrics/definitions.py#L97-L98)).
  `run_comparison` tính đủ, dùng để ra `success_rate`, rồi **vứt** — report chỉ giữ tổng hợp
  theo candidate ([selection.py:637-670](../../../../../packages/benchmark/planbench_benchmark/selection.py#L637-L670)).
- Luồng cũ **đã có** map store + editor vẽ ô + versioning + checksum (`/maps`, `MapCanvas`,
  `POST /maps`). Luồng quyết định đọc map từ **đường dẫn file trên đĩa**
  (`environment.map: maps/open_hall.pgm`), nên hai thứ không gặp nhau.

Không việc nào cần thuật toán mới. Cả hai là nối dây.

---

## 2. Việc A — map custom

### A0. Ràng buộc không được vi phạm

**Đổi map là đổi thế giới, nên phải đổi `task_profile_id`.** `episode_context_id` băm
`(task_profile_id, mission_id, environment_variant, seed)` và HĐ-3.1 đóng băng payload đó —
map **không** nằm trong đó. Sửa map tại chỗ mà giữ id sẽ sinh ra context hash trùng với thế
giới cũ, và `--reuse-traces` sẽ phục vụ episode ghi trên bản đồ không còn tồn tại. Không có
gì cảnh báo; id khớp nhau.

Đây đúng cái bẫy `sensor_noise` đã sinh ra `open_hall_v2`. Nên panel khởi chạy **không sửa
deployment**, nó **dẫn xuất một deployment mới**.

### A1. Không đổi hợp đồng, không đổi lược đồ — vật chất hoá map ra đĩa

Cách rẻ nhất và ít rủi ro nhất: khi dẫn xuất, **ghi map trong store ra cặp `map_server` trên
đĩa** rồi trỏ `environment.map` / `map_yaml` vào đó. Toàn bộ tầng dưới (`task_map`, manifest,
endpoint trace) chạy nguyên không sửa một dòng.

- `planbench_schemas.map_io` thêm `dump_map_server(map_data) -> (pgm_bytes, yaml_text)` —
  **nghịch đảo đúng** của `load_map_server` đang có. Hàng rào: test round-trip
  `load_map_server(*dump_map_server(m)) == m`.
- Ghi vào `maps/custom/<map_id>__v<version>.pgm` + `.yaml`, đường dẫn **tương đối repo**.
  Không dùng đường dẫn tuyệt đối: một profile mang đường dẫn tuyệt đối là một profile chỉ
  đúng trên một cái máy, và HĐ-13 đòi người khác dựng lại được.
- **`maps/custom/` thì gitignore** — sửa lại so với ý ban đầu của bản plan này. Lý do đảo:
  những file đó là **dẫn xuất**, lưới người vẽ nằm trong `planbench.db`, mà DB **đã bị
  gitignore** (`*.db`). Commit đầu ra của một nguồn không nằm trong git là commit một bản sao
  sẽ cũ ngay lần đầu ai đó sửa map. Dựng lại bằng cách derive lại deployment.

### A2. Endpoint mới: `POST /task-profiles/derive`

```
{ base_task_profile_id, new_id, map_id, missions?: [{id, start:[x,y,theta], goal:[x,y,theta]}] }
```

Làm bốn việc, theo đúng thứ tự này:

1. nạp profile gốc,
2. ghi map trong store ra `maps/custom/`,
3. thay `environment.map` / `map_yaml` (và `missions` nếu có),
4. **`TaskProfile` validate + `validate_missions_on_map`** rồi mới lưu.

Bước 4 là bước đáng tiền. Một mission có goal nằm trong kệ cho **0% success với mọi
candidate**, và phép so khi đó báo hoà giữa các stack trên một câu hỏi không stack nào được
hỏi — mọi cột đều đọc ra một con số 0.00 hợp lý. `validate_missions_on_map` đã bắt được năm
kiểu lệch này ([task_map.py:184-258](../../../../../packages/benchmark/planbench_benchmark/task_map.py#L184-L258));
việc ở đây chỉ là gọi nó **trước khi** ai đó tốn hai tiếng máy.

Từ chối `new_id == base_id`: đó chính là hành vi A0 cấm.

### A3. UI trong panel khởi chạy

Mặc định **"map như deployment"** — luồng hiện tại không đổi một cú bấm nào. Chọn map khác
thì mở ra: ô `new_id`, xem trước `MapCanvas`, và bấm chuột lên bản đồ để đặt start/goal.

Bấm Chạy khi có map custom = derive trước, rồi mới xếp hàng trên id vừa dẫn xuất.

Link sang `/maps` để vẽ map mới — **không dựng editor thứ hai**. Editor đã có, và hai
editor là hai định nghĩa của cùng một thứ.

---

## 3. Việc B — kết quả từng episode và từng run

### B1. Report ghi thêm kết quả **từng** episode

Thêm `episodes` vào mỗi candidate trong report:

```
{ episode_context_id, success, failure_reason, collision_count, min_clearance,
  travel_time_s, p99_latency_ms }
```

Theo **từng candidate**, không phải một bảng chung: dừng sớm làm hai candidate chạy số
episode khác nhau, và một bảng chung sẽ phải bịa ra ô trống cho phần chênh.

**Danh sách `/decisions` cắt trường này đi.** 300 episode × 2 candidate × 10 run là gần một
megabyte cho một trang không vẽ lấy một dòng episode nào. Trang chi tiết giữ đủ.

**Report cũ không có trường này**, và UI phải đọc "vắng mặt" là *"chưa ghi"*, không phải
*"tất cả đều đạt"*. Cùng luật với `weight_stability_margin: null` đã có.

### B2. Trang chi tiết: bảng episode × candidate

Đặt **ngay trên trình xem trace**, trong cùng panel bằng chứng. Thứ tự lập luận:

```
bảng cổng   "G3: fail, 70% thành công"     <- tuyên bố về các episode
bảng episode "#7 ✗ collision, #12 ✗ stuck"  <- episode NÀO
trình xem    vẽ ra episode đó               <- bấm vào ô là mở
```

Bấm một ô = chọn luôn cặp (candidate, episode) cho trình xem. Đó là lý do bảng nằm **trong**
panel trace chứ không phải một panel riêng: tách ra thì phải nâng state lên trang, và người
đọc phải tự chép id sang dropdown.

Dropdown chọn episode cũng mang nhãn kết quả: `#3 · a1b2c3d4 · ✗ collision`, thay vì id trần.

### B3. Danh sách `/decisions`: cột kết quả đọc được

Hiện tại cột Outcome in `recommended_candidate_id` — một hash hex. Đổi thành nhãn người đọc
được: **stack + cấu hình** của bên thắng, kèm **mấy/mấy candidate qua cổng**. Cả hai có sẵn
trong `report.candidates[]`, không cần backend đổi gì.

Run không card giữ nguyên chip lý do (ba lý do, ba hành động tiếp theo khác nhau — không
được gộp), nhưng thêm số qua cổng bên cạnh.

---

## 4. Thứ tự làm

```
B1 report ghi episodes  (backend, độc lập)
B2 + B3 UI              (phụ thuộc B1, nhưng chịu được report cũ)
A1 dump_map_server      (schema, độc lập)
A2 endpoint derive      (phụ thuộc A1)
A3 UI panel khởi chạy   (phụ thuộc A2)
```

## 5. Hàng rào

- Round-trip `load_map_server(*dump_map_server(m)) == m`.
- Derive với mission không vừa map ⇒ **từ chối kèm lý do**, không lưu profile.
- Derive với `new_id == base_id` ⇒ từ chối.
- Report cũ (không có `episodes`) render ra *"chưa ghi"*, không phải *"đạt"*.
- Danh sách `/decisions` không mang mảng `episodes`.
- Suite backend và web phải xanh; nếu phải sửa assertion cũ thì đã đổi hành vi.

## 6. Cố ý không làm lần này

- **Editor map thứ hai trong panel khởi chạy.** Vẽ ô là việc của `/maps`.
- **Sinh map theo tham số** (nợ C2: map vừa khó vừa đối xứng). Đúng việc, khác phiên.
- **Upload PGM từ SLAM thật.** Cần khi có map hiện trường, chưa có.
- **Đổi `EnvironmentSpec` để trỏ thẳng vào map store.** Vật chất hoá ra đĩa cho cùng kết quả
  với không một dòng hợp đồng nào phải bump.
