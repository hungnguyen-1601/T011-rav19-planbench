# Chốt: giữ code và release ở repo public, repo org chỉ nhận bản nộp

**Ngày:** 2026-08-26

## Bối cảnh

Sau khi ship 0.1.14, An hỏi có cần đổi link tải khi chuyển sang repo mới
(`AI20K-Build-Phase-Cohort-3/P-011`) không. Câu hỏi kéo ra một chuỗi
khảo sát, cuối cùng chốt **không đổi gì cả**. Ghi lại vì kết luận
"không đổi gì" trông giống như chưa làm gì, trong khi đường đến nó loại
được ba phương án và tránh được một lỗi im lặng.

## Bốn phương án đã cân

| | Source private | Link tải | User dán token | CI |
|---|---|---|---|---|
| 1. Chuyển hẳn sang repo org | ✅ | đổi + **bị chặn** | mỗi máy | ok |
| 2. Repo phát hành mới, public | ✅ | đổi | không | ok |
| 3. Repo org build, public phát hành | ✅ | **không đổi** | không | **cần admin** |
| 4. Giữ nguyên, sao sang org để nộp | ❌ | **không đổi** | không | ok |

**Chốt phương án 4.**

## Vì sao ba phương án kia rụng

### Repo org là private, và điều đó giết đường CDN

Đo, không đoán:

```
=== private org repo, ẩn danh ===
api repo        : http 404
releases/latest : http 404

=== repo public, ẩn danh ===
releases/latest : http 200
```

Bản 0.1.14 vừa ship bỏ được yêu cầu token là nhờ repo public: manifest
đọc qua CDN không cần credential. Trên repo private, request không ký
trả 404, luôn rơi về API, và **mỗi máy** phải có PAT `contents:read` —
đúng thứ docstring của updater nói là đã bị loại vì "cũng như không có
updater".

### Link tải không di chuyển được

Link cố định **chính là** đường dẫn repo public, và đường dẫn đó nằm
cứng trong mọi bản app đã cài ở `updater.REPOSITORY` — hằng số cố tình
không cho cấu hình. Chuyển phát hành đi nơi khác thì link đã gửi cho
người khác chết, và mọi bản 0.1.12/0.1.13/0.1.14 đang chạy sẽ hỏi một
repo đã ngừng publish, **im lặng, vĩnh viễn**.

### Phương án 3 chết vì quyền, không vì kỹ thuật

Phương án 3 đã được **làm xong** rồi mới phát hiện tắc: workflow build ở
repo org, publish sang repo public bằng `secrets.PUBLISH_TOKEN`, có cổng
`if: github.repository == ...` để một tag đẩy nhầm ở repo public không
build đè lên bản thật.

Nhưng thêm Actions secret cần quyền admin:

```
hungnguyen-1601/T011-rav19-planbench   private=False  admin=False  push=True
AI20K-Build-Phase-Cohort-3/P-011       private=True   admin=False  push=True
```

Không ai bên này là admin của **cả hai** repo. An cũng không nhờ được
owner org. Nên phương án 3 hoàn tác toàn bộ.

Trên đường đi có hai phát hiện phụ đáng giữ:

- **Fine-grained PAT không chọn được repo của tài khoản cá nhân khác.**
  Repo public thuộc `hungnguyen-1601` (type: User), An là collaborator
  có quyền write, nhưng fine-grained token chỉ chạm được tài nguyên của
  *một* resource owner: chính tài khoản An, hoặc một organization An là
  thành viên. Repo đó **không bao giờ hiện** trong danh sách "Only
  select repositories" — cấp thêm quyền cũng không hiện.
- **Classic PAT scope `public_repo` là đủ và hẹp.** Ghi được repo
  public, và `http 404` trên repo private — đã kiểm. Token An tạo đúng
  loại này; giờ chưa dùng đến nhưng giữ lại không hại.

## Đã hoàn tác gì

`git checkout c0da14d -- .github/workflows/desktop-release.yml docs/DESKTOP-RELEASE.md`

Quan trọng nhất là **gỡ cổng `if: github.repository`**. Để lại thì nó
chặn build ở đúng nơi cần build, và release kế tiếp sẽ **không chạy mà
không báo gì** — CI xanh vì không có job nào fail, chỉ là không có job
nào chạy.

Kiểm sau khi hoàn tác:

```
guard removed : True
env removed   : True
token         : ${{ github.token }}
--repo gone   : True
```

## Đã ghi lại cho session sau

An yêu cầu ghi rõ để session khác biết phải push hai nơi. Ba chỗ:

**1. `docs/DESKTOP-RELEASE.md`** — mục mới "Two remotes, and every push
goes to both", đặt ngay sau "The short version" để đọc được trước lần
push đầu tiên. Gồm bảng tra hai remote, hai lệnh push, ràng buộc
"Create a merge commit" khi merge PR ở repo org, và **lý do** hai ràng
buộc gặp nhau (link không di chuyển được + không ai có admin) — kèm cả
số đo `admin=False`.

Có thêm một mục nhỏ "What this means when you are tempted to tidy it
up": session sau sẽ thấy trùng lặp và muốn gộp lại, nên ghi sẵn giá
phải trả.

**2. Memory dự án** `push-hai-remote.md` — để session mới nạp được
ngay, không phải đọc hết runbook mới biết.

**3. Remote cục bộ đặt đúng tên:**

```
origin  https://github.com/hungnguyen-1601/T011-rav19-planbench   (public)
org     https://github.com/AI20K-Build-Phase-Cohort-3/P-011       (private)
```

`origin` là nơi làm việc và phát hành, nên `git push` theo phản xạ đi
đúng chỗ. Trong lúc thử phương án 3 hai remote này từng bị đảo vai; đã
đặt lại.

## Trạng thái sau khi chốt

| Thứ | Trạng thái |
|---|---|
| Link tải cố định | không đổi |
| `updater.REPOSITORY` | không đổi |
| Workflow release | về nguyên bản, chạy ở repo public |
| Bản đã cài trên máy mọi người | không ảnh hưởng |
| 0.1.14 | đã publish, đã kiểm chạy |

## Còn treo

- Thu hồi token cũ `ghp_PAE3...` (đã rò qua chat, đã bị GitHub push
  protection chặn hai lần)
- Xoá token khỏi `GITHUB_CLIENT_SECRET` trong `.env` — ô đó dành cho
  OAuth app secret. `GITHUB_CLIENT_ID` đang rỗng nên chưa hỏng gì, nhưng
  đó không phải chỗ của nó.
- Branch `tongduyan_split-source-and-distribution` trên repo org mang
  phương án 3 đã bỏ — **đừng merge**, nên xoá.
