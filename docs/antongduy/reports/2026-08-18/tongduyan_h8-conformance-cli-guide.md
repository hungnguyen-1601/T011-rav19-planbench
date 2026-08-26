# H8 — conformance suite, CLI cho operator, author guide

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §8 H8
**Trạng thái:** xong, 22 test mới xanh, **244 passed** lát cắt host
H1a→H8, **chưa commit**. Đây là pha cuối của plan.

---

## 1. Đã tạo

| File | Việc |
|---|---|
| `packages/plugin_sdk/.../conformance.py` | suite cho tác giả plugin — nằm trong SDK để họ chỉ phụ thuộc một package |
| `services/simulator/.../host/cli.py` | `list` / `check` — registration state + compatibility report |
| `docs/plugin_author_guide.md` | author guide cho cả ba role |
| `tests/test_conformance_and_cli.py` | **mới**, 22 test |

## 2. Conformance suite — bốn phép kiểm host *không* làm hộ được

Preflight trả lời *có được chạy không* từ lời khai. Suite này trả lời
*object có hành xử đúng như lời khai không* — cần chính plugin trong tay.

**(a) Determinism.** HĐ-4 đòi lệnh giống nhau cho đầu vào giống nhau, và
**mọi** phép so ghép cặp của nền tảng dựa vào đó. Không có gì ở runtime
phát hiện được: plugin đọc đồng hồ hoặc dùng generator chưa seed **không
hỏng** — nó làm thống kê đo nhiễu. Suite dựng **hai instance mới** rồi so
lệnh đầu tiên (không so tick 1 với tick 2, vì controller có state được
phép khác nhau — làm thế sẽ đánh trượt mọi tracker vì đúng việc của nó).

**(b) "Optional" phải thật sự optional.** Host tin nhãn: plugin khai
optional rồi hỏng khi thiếu sẽ được đem chạy trên deployment không có
kênh đó, và hỏng giữa episode. Suite **giữ lại từng optional một** và
bắt plugin vẫn phải trả lời.

**(c) Không đọc kênh chưa khai.** Chạy với đúng thứ đã khai; với tới thứ
khác thì lỗi **nêu tên capability** — bug của manifest, không phải của
runtime.

**(d) Không mutate payload.** Request model đã frozen nên gán lại field
vốn bất khả; thứ **không** ai chặn là ghi *vào* payload mutable. Host
trao cùng một envelope cho mọi consumer được cấp, nên một dict bị viết
lên là một thế giới khác cho người đọc kế tiếp.

## 3. CLI — vì "vắng mặt" là bốn buổi chiều khác nhau

```
python -m planbench_simulator.host.cli list --bundles <dir>
python -m planbench_simulator.host.cli check <plugin-id> [--research]
```

Không có nó, tín hiệu duy nhất rằng plugin không chạy là **nó không có
trong kết quả** — và một hàng thiếu trông y hệt nhau dù nguyên nhân là:
deployment thiếu provider, bundle bị quarantine, thiếu dependency, hay
chưa ai cài. Nên cả hai lệnh in **lý do**, và exit code dùng được trong
CI (0 chạy được, 1 không).

`check` in registration state, provider graph đã resolve, runtime lane,
evidence class, oracle providers, và `why` — **mọi** blocker một lượt.

## 4. Author guide

`docs/plugin_author_guide.md`, mười mục, viết cho người ngoài repo. Ba
chỗ đáng chú ý:

- **§5 Determinism** nói thẳng nó không optional và không detect được ở
  runtime — chỗ duy nhất tác giả sẽ đọc trước khi viết một controller
  dùng `time.time()`.
- **§9 "Nền tảng sẽ không làm gì hộ bạn"**: không đoán capability chưa
  khai, không chọn hộ giữa hai provider, không fallback lane, không coi
  crash là kết quả.
- **§10 Isolation nói thẳng**: in-process là trust policy; subprocess là
  crash/interpreter isolation và **không** phải security sandbox. Guide
  là đúng nơi tác giả sẽ tìm "cho phép chạy code lạ" — nên câu trả lời
  phải ở đó, không ở docstring.

Có test khoá guide không trôi: ba role được nói tới, hai lệnh CLI in ra
là lệnh thật, ba example bundle nó nêu đều tồn tại, và nó **không** hứa
security sandbox.

## 5. Hai lỗi trong phiên — cùng một lớp, và nó nằm trong chính suite

| # | Lỗi | Phán |
|---|---|---|
| 1 | Check immutability chụp `before` **sau khi** check determinism đã chạy `step` | check determinism mutate request trước ⇒ so một request đã bẩn với chính nó ⇒ **mọi plugin đều pass** |
| 2 | Sửa (1) bằng deep copy vẫn hỏng: `_check_optionals_are_optional` dùng `model_copy(update=...)` — **nông** — nên chia sẻ envelope và cũng làm bẩn bản gốc | cùng lớp lỗi, chỗ khác |

Sửa triệt để: **mỗi check nhận một bản sao sâu riêng** qua closure
`fresh()`. Ghi comment tại chỗ: *một check mà phán quyết phụ thuộc thứ
tự các check khác chạy thì không phải check*.

Đáng ghi vì đây là **suite kiểm tra tính đúng đắn của người khác mà tự
nó sai theo đúng kiểu nó đi bắt** — và nó chỉ lộ ra vì test được viết
với plugin **cố tình sai**. Một suite chỉ từng thấy đầu vào đúng chứng
minh nó không crash, không chứng minh nó bắt được gì.

## 6. Vòng rà của An — 9 điểm, **đúng cả 9**, đã sửa hết

Hai điểm nặng nhất không phải bug mà là **tuyên bố sai**, tệ hơn bug vì
người đọc tin nó:

- **#3:** report và docstring đều mô tả phép kiểm "không đọc kênh chưa
  khai" mà **code không có**. Tôi viết mô tả trước, viết code sau, không
  đối chiếu lại.
- **#1:** tôi viết test tên là *"lệnh trong guide là lệnh thật"* mà nó
  chỉ so chuỗi `"cli list" in text` — nên nó **pass trong khi guide dạy
  một lệnh argparse từ chối** (`--bundles` thuộc parser gốc nên phải
  đứng trước subcommand). Test có hình dạng test nhưng không kiểm gì.
  Cùng họ với "phép đo xanh đo ít hơn nó khai" của phiên P0–P6.

| # | Vấn đề | Bản sửa |
|---|---|---|
| 1 | Lệnh CLI trong guide không chạy được: repo chưa đóng gói, và sai thứ tự `--bundles` | Guide thêm bước `PYTHONPATH`, sửa thứ tự. Test giờ **thực thi** mọi lệnh trong guide (thay placeholder bằng bundle thật); `exit 2` = argparse từ chối = fail |
| 2 | Không có conformance cho **global** plugin — truyền vào suite local sẽ crash ở `step()` | `check_global_plugin()`: hai instance mới, cùng query, so path, kiểm non-finite waypoint, kiểm mutate |
| 3 | Tuyên bố có kiểm undeclared channel mà không có | `_check_only_declared_channels` — chạy với **đúng** tập đã khai; hỏng thì lỗi nêu tên thứ nó lén đọc |
| 4 | Optional chỉ bỏ từng cái ⇒ plugin "cần một trong hai" vẫn pass | Bỏ **từng cái một và tất cả cùng lúc** |
| 5 | Deep-copy chỉ áp cho step request; `reset_request` vẫn dùng chung | `fresh_reset()` riêng mỗi lần gọi + check plugin ghi vào reset request |
| 6 | "findings returned, never raised" nhưng `factory()`, `reset()`, `float(...)` nằm ngoài try | `_guard()` bọc mọi đường; constructor nổ thành Finding |
| 7 | Guide hứa "một dependency" nhưng ví dụ global trả `PlanResult` (thuộc `planbench_planning`) | Guide dùng `GlobalPlanResponse` của SDK; host convert phía nó. Path length **tính lại**, không tin plugin khai |
| 8 | Guide nói seed tới qua `reset` nhưng `LocalResetRequest` không có | `episode_seed` vào request thật; protocol **1.1.0 → 1.2.0**; facade truyền từ `build_planners` |
| 9 | CLI in `registered_and_runnable` cạnh `missing modules` rồi exit 1 | `missing_dependencies` vào thẳng `resolve_compatibility` ⇒ gộp vào `registered_but_missing_runtime`. Một verdict |

**Quyết định ở #7 và #8, ghi lại vì có phương án rẻ hơn mà tôi không
chọn.** Cả hai đều sửa được bằng cách hạ tài liệu xuống cho khớp code.
Tôi chọn ngược lại — **sửa contract cho khớp điều tài liệu nói** — vì cả
hai lời hứa đó đúng về thiết kế: plugin ngoài repo *nên* chỉ phụ thuộc
SDK, và plugin ngẫu nhiên *cần* seed để tái lập được theo HĐ-4. Hạ tài
liệu sẽ giữ nguyên hai thiếu sót thật của contract và làm chúng thành
chính thức.

## 7. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/test_conformance_and_cli.py` | **31 passed** (22 → 31 sau vòng rà) |
| Lát cắt host H1a→H8 **+ parity**, sau vòng rà | **236 passed**, 3:27 |
| `ruff check` toàn `packages/` + `services/` | sạch |
| **Parity sau khi thêm `episode_seed` vào contract** | **byte-identical** — protocol lên 1.2.0 và `build_planners` đổi chữ ký, nhưng không một byte quỹ đạo nào dịch |

## 7. Trạng thái plan

H0 → H8 **xong hết**. Còn lại theo lệnh An: **một lượt full suite sạch**
trên HEAD sau khi commit H8, và §11 DoD MVP nên được đối chiếu điểm một
lần cuối.
