# `openai` đi cùng bản cài — ô dán API key giờ mới dùng được

**Ngày:** 2026-09-01 · **Nhánh:** `tongduyan_ship-openai-sdk`
**Chưa release.** An giữ lại để ra `0.1.17` cùng vài phần khác.

## Triệu chứng

Dock trợ lý trong **bản app đã cài** trả về:

> the 'openai' package is not installed; install it (`pip install
> openai`) or use the deterministic mock provider

Máy An có `openai` 3.3.1 trong `.venv`, nên chạy từ source thì không
gặp. Hai interpreter khác nhau.

## Chẩn đoán

[`build_desktop.ps1:258`](../../../../../scripts/build_desktop.ps1) cài vào
runtime đóng gói bằng đúng một file:

```powershell
pip install --target $SitePackages -r requirements.txt pywebview
```

`openai` **không có** trong `requirements.txt`. Nó chỉ nằm ở
`requirements-optional.txt` (đang comment) và `docker/requirements-analyst.txt`.

**Lượt đầu tôi kết luận đây là thiết kế cố ý** — `requirements-optional.txt`
ghi rõ "LLM thật là opt-in". An phản bác: trong Cài đặt có ô dán key.
An đúng, và tôi sai vì đã đọc chữ "opt-in" mà không hỏi **ai** opt-in
được.

Đây là **lỗi sản phẩm**:

- `AgentSettings.ready` — *"True when the provider is configured **and**
  its SDK is installed"*
- `provider_status()` đặt `sdk_installed=_can_import("openai")`
- Trên bản cài, runtime là embeddable Python đọc `._pth`, không phải
  venv ⇒ **người dùng không có cách nào thêm gói**

Luồng thật của người dùng: dán key → lưu được → `key_present: true` →
`ready` vẫn `false` → hết cách. Một ô nhập nhận dữ liệu rồi không bao
giờ dùng được dữ liệu đó, trên chính artifact được phát hành.

## Đã sửa

`requirements.txt` thêm `openai==3.3.1`, kèm giải thích tại chỗ vì sao
nó không còn optional. `requirements-optional.txt` mục 4 viết lại — để
nguyên thì hai file nói ngược nhau về cùng một dependency, mà đó chính
là cách nó lọt khỏi bản build.

`anthropic` **vẫn** optional, và ghi rõ lý do: trang Cài đặt chưa có
đường dán key cho nó. Khi nào có thì phải chuyển theo, cùng một lý do.

## Vì sao ghim 3.3.1

Đo bằng cách giải phụ thuộc hai lần với `--ignore-installed`, không đoán:

| ghim | gói mới | cỡ | ghi chú |
|---|---|---|---|
| `openai==3.3.1` | 6 | **11.2 MB** | kéo thêm `httpx2`/`httpcore2` — stack HTTP thứ hai bên cạnh `httpx==0.28.1` |
| `openai==2.50.0` | 5 | 10.4 MB | dùng lại `httpx` sẵn có, thêm `distro` + `tqdm` |

Chênh **0.8 MB** trên installer hiện tại **91.6 MB** — không đủ để làm
lý do. Chọn 3.3.1 vì đó là bản `.venv` của An đang chạy và là bản **mọi
lượt thí nghiệm analyst ngày 30–31/08 đi qua**. Ship một bản khác bản đã
thử chính là loại lỗi vừa gặp: dev và bản cài chạy hai thứ khác nhau.

## Kiểm chứng

`provider_status()` sau khi sửa, cố tình bỏ key khỏi môi trường:

```
openai     sdk_installed=True   key_present=False  ready=False
           missing: set OPENAI_API_KEY
```

`missing` rút còn đúng thứ ô dán key cung cấp được. Trước đó nó còn đòi
`pip install openai` — thứ người dùng bản cài không làm được.

## Test

`tests/test_agent_sdk_is_shipped.py` — 6 test mới. Suite agent + settings
đầy đủ: **240 pass**.

Cắn ba hướng:

| tiêm | đỏ |
|---|---|
| gỡ `openai` khỏi `requirements.txt` | 2 |
| đổi ghim chính xác thành khoảng `>=` | 2 |
| để hai file lại bất đồng về `openai` | 1 |

Test ghim cả **mắt xích** giữa pin và build — `build_desktop.ps1` phải
đọc đúng `requirements.txt` và runtime phải là `._pth` chứ không phải
venv. Đó là một dòng PowerShell mà không gì khác sẽ báo nếu ai đổi.

## Còn lại

- **Chưa bump VERSION, chưa đẩy tag.** An gộp vào `0.1.17` sau.
- Khi release: smoke gate (`scripts/desktop/smoke_stage.py`) kiểm mọi
  source root import được **trên interpreter đã đóng gói** — nó sẽ bắt
  nếu `openai` không vào được runtime.
- Người dùng bản cài vẫn phải tự dán key. Bản cài đọc `.env` ở thư mục
  dữ liệu riêng (`paths.py`), không phải `.env` trong repo.
