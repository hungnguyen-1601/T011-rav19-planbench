# Phase 1 — đồng bộ types TS và khai i18n cho traffic editor

> Plan: `docs/antongduy/plans/2026-08-15/config-vat-the-dong-tren-form-deployment.md` (bản v5).
> Ngày làm: 2026-08-15. Nhánh: `tongduyan_plannerselector`. **Chưa commit.**

## Làm gì

Phase 1 là phần nền, cố ý **không đổi một hành vi nào**: chỉ mở rộng
lớp kiểu TypeScript cho khớp schema backend, và khai sẵn từ điển i18n mà
Phase 2b sẽ dùng.

### 1. `apps/web/src/lib/types.ts`

| Thêm | Vì sao |
|---|---|
| `RandomWalkMotion`, `SuddenStopMotion` | TS mới mirror 2/4 motion kind; hai kind kia backend đã nhận từ lâu (`dynamic.py:70-90`) nhưng UI không gọi tên được |
| `Motion` mở thành union 4 kind | Trước: `WaypointMotion \| PeriodicMotion` |
| `SensorNoise` | Adapter preview của Phase 2b cần truyền nhiễu xuống scenario; trước đây TS không có kiểu này |
| `Scenario.sensor_noise?`, `.clearance_preference?`, `.stuck_time_window?` | Ba field `scenario_for` (`episode.py:97-117`) luôn điền mà TS chưa mirror |
| `ScenarioPreviewRequest` | `previewRequestOf` của Phase 2b hứa trả kiểu này; trước đây kiểu không tồn tại (điểm review vòng 4) |

Hai chi tiết ghi thẳng vào comment vì đọc code không thấy được, và đã
đối chiếu với `position_at` trước khi viết để không mô tả sai cơ chế:

- **Hai `seed_offset` là hai thứ khác nhau.**
  `RandomWalkMotion.seed_offset` vào `_hashed_angle(seed, offset, index)`
  (`dynamic.py:254, 284`) — nó chọn **chuỗi hướng đi**; hai walker cùng
  giá trị đi đúng một hình dạng. `DynamicObstacle.seed_offset` vào
  `_seed_time_shift` cùng `len(name)` (`dynamic.py:197`) — nó chọn **độ
  lệch pha đồng hồ**. Hai trục độc lập, không gộp được.
- **`sudden_stop` không có điểm cuối**: chỉ `start + heading + speed +
  stop_time`. Cú nhấp thứ hai trên canvas (Phase 2b) chỉ dùng để suy ra
  hướng, không lưu thành điểm.

`sensor_noise` để tất cả field optional vì lý do đơn giản: **mọi biên độ
mặc định 0 ở server** (`sensor.py`, `Field(default_factory=SensorNoise)`),
nên mirror optional là đúng. Bản đầu của comment này nói thêm rằng "bỏ
trống block" khác với "khai bằng 0" — sai ở tầng runtime: sau khi
normalize hai payload cho cùng một thế giới. Khác biệt đó chỉ có ở tầng
trình bày (`deployments.noiseUndeclared` trên trang danh sách), không
phải ở hành vi, nên đã gỡ khỏi comment kiểu.

### 2. i18n — `locales/en.json` + `vi.json`

Khai **60 key mới mỗi ngôn ngữ** (60 cặp, 120 entry), chèn ngay sau khối
`deployments.form.obstacleSpeed*` vì traffic và biên phanh đọc cùng nhau:

- `deployments.form.traffic.*` — tiêu đề khối, thêm/xoá, `name`,
  `radius`, picker 4 kind, tham số riêng từng kind (`speed`, `loop`,
  `ping_pong`, `period`, `phase`, `origin`, `change_interval`,
  `max_radius`, `heading`, `stop_time`), hai `seed_offset` với nhãn
  phân biệt rõ, gợi ý `seed_time_offset` (kèm nhánh "lộ trình một lần
  không có chu kỳ"), 6 nhãn nút + 6 câu caption cho placement mode,
  ghi chú chỉ sửa được trên khung phẳng.
- `deployments.form.validate*` — nút "Kiểm tra với server" và **câu nói
  rõ giới hạn**: dry-run chỉ đọc nội dung tài liệu, trùng id vẫn chỉ lộ
  lúc nộp (đúng phạm vi đã chốt ở plan v3).
- `deployments.form.preview*` — thời điểm, seed, và câu giải thích vị
  trí do server tính.
- `deployments.form.obstacleSpeedL18Note` — cảnh báo L18 đặt cạnh
  checkbox `v_obstacle_max`, để không ai bật nó một cách ngây thơ.

Chưa có consumer nào — đúng chủ ý: Phase 2b chỉ việc gắn dây, không
phải vừa viết UI vừa nghĩ câu chữ.

## Bằng chứng

| Kiểm | Kết quả |
|---|---|
| `npm run typecheck` (tsc --noEmit) | sạch |
| `npm run test` (web) | **670 passed / 32 file**, 0 fail |
| `pytest tests/test_form_covers_the_contract.py` | **14 passed** |

Guard `TestTrafficIsCarriedButNotYetAuthored` vẫn xanh, và đó là điều
**đúng** ở Phase 1: nó grep `DeploymentForm.tsx`, file này chưa bị đụng.
Nó sẽ đỏ ở Phase 2b và lúc đó mới được thay — không phải bây giờ.

## Cố ý chưa làm

- **Không đụng `DeploymentForm.tsx`** — mọi thứ về author traffic là
  Phase 2b.
- **Không sửa `deployments.form.noiseNote`** (đang nói "This form writes
  no moving traffic yet ... Add traffic on the YAML tab"). Hôm nay câu
  đó vẫn đúng; sửa sớm sẽ làm test `deployments-page.test.tsx:143` đỏ
  vì một lời nói dối ngược chiều.
- **Không sửa** `deployments.mode.note`, comment `DeploymentForm.tsx:560-562`.

## Phát hiện thêm (đã ghi vào plan)

**1. `nav.desc.scenarios`** = *"Kept until the deployment form can draw
obstacles"* — một chuỗi locale nữa sẽ sai sau Phase 2b, plan v5 chưa
liệt kê. Đã bổ sung vào danh sách "comment/locale hết hạn" của Phase 2b.

**2. Đồng hồ vật cản băm theo *độ dài* tên — một defect runtime, chặn
Phase 2b.** Phát hiện khi An soi lại copy tôi viết. `_seed_time_shift`
(`dynamic.py:192-200`) dùng `obstacle.seed_offset + len(obstacle.name)`,
nên hai vật cản khác tên nhưng cùng độ dài và cùng `seed_offset` chạy
**đồng pha** — đúng thất bại mà validator tên-duy-nhất tuyên bố ngăn
được. Đo thật (`cart` vs `rack`, `seed_time_offset = 20`):

| seed | cart | rack | forklift |
|---|---|---|---|
| 0 | 4.983802 | 4.983802 | 13.171391 |
| 7 | 19.384681 | 19.384681 | 15.519864 |
| 42 | 12.660475 | 12.660475 | 4.894837 |

`position_at` trùng nhau ở mọi thời điểm lấy mẫu. Backend cũng đang tự
mô tả sai: docstring `dynamic.py:115` nói "a hash of (seed, name)", và
thông điệp từ chối ở `task_profile.py:276-277` nói tên được trộn vào
hash. Chi tiết, hai phương án và cái giá của mỗi phương án nằm ở mục
**0c** của plan; đã thành **điểm quyết #4**, chặn Phase 2b.

Không profile đang ship trúng bẫy (mỗi profile một vật cản), nhưng đó là
may chứ không phải thiết kế — nó thành bẫy thật đúng lúc form cho khai
nhiều vật cản.

## Sửa sau review (cùng ngày)

An soi lại Phase 1 và bắt bốn chỗ; cả bốn đều đúng, đã sửa:

| Chỗ sai | Sự thật | Đã làm |
|---|---|---|
| Copy nói tên obstacle được băm vào hash | Chỉ `len(name)` được băm | Gỡ mọi tuyên bố về cơ chế băm khỏi `nameNote`, `obstacleSeedNote`, comment `seed_offset` — copy giờ đúng dưới **cả hai** phương án của điểm quyết #4 |
| `seedTimeOffsetNote` nói server luôn từ chối 0 và luôn đòi một chu kỳ | Chỉ waypoint/periodic/sudden_stop cần > 0; **chỉ periodic** đòi ≥ period; **random_walk được miễn** (`task_profile.py:279-309`) | Viết lại theo từng nhóm luật, en + vi; sửa luôn comment `seed_time_offset` trong `types.ts` (câu này có **từ trước** Phase 1, cũng sai theo cách đó) |
| Comment `SensorNoise` nói bỏ trống ≠ khai 0 | Runtime như nhau sau normalize | Rút lý do về đúng mức "mirror default của backend" |
| Report ghi 62 key / 31 cặp | 60 key mỗi ngôn ngữ | Sửa thành 60 cặp / 120 entry |

Chạy lại sau khi sửa: `tsc --noEmit` sạch, `npm run test` **670 passed**.

## Ngoài lề

Việc tiến hành Phase 1 mặc nhiên chốt **điểm quyết #1: đủ 4 motion kind
ngay từ đầu** — types và i18n đã khai cả bốn. Hai điểm quyết còn lại
(#2 nghỉ hưu `/scenarios`, #3 thời điểm gọi dry-run) chưa cần trả lời
trước Phase 2a.
