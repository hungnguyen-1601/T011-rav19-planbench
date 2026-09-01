# 500 trên panel episode, và cái log câm khiến nó khó tìm

**Ngày:** 2026-09-01 · **Nhánh:** `tongduyan_route-points-and-desktop-logging`

Hai lỗi, một triệu chứng. Cái thứ hai là lý do cái thứ nhất mất một buổi
mới tìm ra.

## Triệu chứng

Mở tab *Watch an episode* trên run `sudden_stop_v0`, chọn episode #3
(`3ffbf2aba563`), dock hiện:

```
THIS EPISODE
internal server error
```

Trên **bản đã cài 0.1.17**, không phải dev server.

## Lỗi 1 — đọc sai hình dạng đỉnh route

`episode_builder._first_route` giải nén đỉnh route thành **cặp**:

```python
return [(float(x), float(y)) for x, y in points]
```

Nhưng chúng được ghi thành **dict**. Cùng một repo, ba chỗ liên quan:

| chỗ | làm gì |
|---|---|
| `decision_service.py:2035` | **sinh ra**: `"points": [{"x": x, "y": y} for x, y in record.output_path]` |
| `decision_service.py:1945` | **đọc đúng**: `[(float(point["x"]), float(point["y"])) for point in points]` |
| `episode_builder.py:155` | **đọc sai**: giải nén như cặp |

Lặp một `dict` thì ra **khoá**, nên đỉnh đầu tiên gọi `float("x")`:

```
ValueError: could not convert string to float: 'x'
```

**Vì sao lọt tới bản phát hành:** chỉ nổ khi sidecar E4.5 có ghi
polyline. Episode không có thì `planned_routes` rỗng, `_first_route` trả
`None`, mọi thứ chạy tiếp — và đó là **mọi fixture trong suite**.

Sửa: `_vertex()` đọc được cả hai hình dạng. Nhận cả dạng cặp chứ không
thay hẳn bằng dạng dict — một reader chỉ hiểu đúng hình dạng nó tình cờ
được thấy chính là lỗi này, đảo vai.

## Lỗi 2 — API bịt miệng chính tiến trình chứa nó

`logging_config.configure_logging`:

```python
root = logging.getLogger("planbench")   # không phải root thật
root.handlers = [handler]               # StreamHandler -> sys.stderr
root.propagate = False                  # cắt đường lên root thật
```

Đúng khi API sở hữu tiến trình. **Sai khi không.** Desktop chạy API
trong một thread của chính nó, sau khi đã trỏ root thật vào
`RotatingFileHandler`. Rồi dòng trên chạy lúc
`from planbench_api.main import app`, và cắt mọi logger `planbench.*`
khỏi file đó.

Hai hệ quả, cái sau che cái trước: app chạy bằng `pythonw.exe` nên
`sys.stderr` là `None` — handler vừa cài **không có chỗ ghi**; và
`propagate = False` nên cũng chẳng tới được file. **Một 500 trên bản
phát hành ghi traceback vào một luồng không tồn tại.**

Chính launcher đã biết điều này và có phòng vệ:

```python
if sys.stderr is not None:
    handlers.append(logging.StreamHandler(sys.stderr))
```

API thì không.

**Bằng chứng:** tôi gọi endpoint đó trên app đang chạy của An, nhận
**HTTP 500**, và `planbench.log` không ghi một dòng nào — kể cả dòng
`api ready on …` của `server.py`, vốn log **sau** lúc import. Chính chỗ
vắng đó chỉ ra thủ phạm. Traceback chỉ lấy được khi chạy cùng app đó qua
`TestClient` trong tiến trình **có** `stderr`.

Sửa: khi root đã có handler thì để nguyên cây, cho record propagate lên
đó. Khi không có thì API sở hữu tiến trình và hành xử **y như cũ**.

## Kiểm chứng trên dữ liệu thật

Gọi lại đúng endpoint đó trên chính DB của app đã cài:

```
truoc:  verdict HTTP 500  {"code":"internal_error"}
sau:    verdict HTTP 200  basis=outcome_only  winner=e1251e42a20b
```

`outcome_only` là đúng: episode #3 có astar+dwa `pass`, rrtstar+dwa
`timeout`.

## Test

`tests/test_episode_route_and_desktop_logging.py` — 9 test.

Một trong số đó ghim **sự đồng thuận** chứ không ghim hình dạng: nó đọc
dòng sinh ra trong `decision_service.py`. Hai reader bất đồng là toàn bộ
lỗi này; một test chép lại hình dạng của một bên sẽ không bắt được.

**Cổng cắn, bốn hướng:**

| tiêm | đỏ |
|---|---|
| quay lại `for x, y in points` | 3 |
| bỏ nhánh dict, chỉ còn cặp | 3 |
| API lại cướp cây logger | 1 |
| API độc lập mà vẫn propagate | 1 |

## Không sửa

**"Agent luôn đọc episode đang mở"** — An chốt để nguyên. Đó là hai
quyết định cố ý trong code, không phải bug:

- `setEpisodeSelection` chỉ gọi từ `chooseEpisode`; docstring ghi
  *"Never called with the episode the replay opened on"*
- `useEffect(() => clearEpisodeSelection, [])` xoá lựa chọn khi rời trang

Nên mở lần đầu thì dock đòi chọn episode, và rời trang rồi quay lại thì
mất lựa chọn.
