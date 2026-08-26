# Tách nơi viết code khỏi nơi phát hành

**Ngày:** 2026-08-26

## Việc cần làm

Từ giờ code viết ở repo **private** của ban tổ chức
(`AI20K-Build-Phase-Cohort-3/P-011`). Repo **public**
(`hungnguyen-1601/T011-rav19-planbench`) không nhận code nữa, chỉ còn
làm nơi phát hành bản cài.

## Vì sao phát hành không được phép chuyển theo

Link tải cố định **chính là đường dẫn repo public**:

```
https://github.com/hungnguyen-1601/T011-rav19-planbench/releases/latest/download/PlanBench-Setup.exe
```

Và cùng đường dẫn đó nằm cứng trong mọi bản app đã cài, ở
`updater.REPOSITORY` — một hằng số **cố tình không cho cấu hình**, vì
updater trỏ được sang repo khác là một đường cài bất cứ thứ gì.

Nên nếu phát hành chuyển đi:

- link đã gửi cho đồng nghiệp tháng trước chết;
- mọi bản 0.1.12 / 0.1.13 / 0.1.14 đang chạy sẽ hỏi một repo đã ngừng
  publish, **im lặng, vĩnh viễn** — check thất bại chỉ ghi một dòng
  WARNING, UI không nói gì.

Đo trước khi quyết, không đoán:

```
=== private org repo, ẩn danh ===
api repo        : http 404
releases/latest : http 404

=== repo public, ẩn danh ===
releases/latest : http 200
```

Repo private còn giết luôn đường CDN vừa làm ở 0.1.14: manifest gửi
không ký sẽ 404, luôn rơi về API, và **mỗi máy** phải có PAT
`contents:read`. Đó đúng thứ docstring của updater nói là đã bị loại.

Kết luận: source chuyển được, phát hành thì không.

## Đã làm

### 1. Workflow build ở repo có source, publish sang repo public

`.github/workflows/desktop-release.yml`:

```yaml
env:
  PUBLISH_REPOSITORY: hungnguyen-1601/T011-rav19-planbench
  SOURCE_REPOSITORY: AI20K-Build-Phase-Cohort-3/P-011

jobs:
  build:
    if: github.repository == 'AI20K-Build-Phase-Cohort-3/P-011'
```

```yaml
        env:
          GH_TOKEN: ${{ secrets.PUBLISH_TOKEN }}
        run: |
          gh release create $tag dist/PlanBench-Setup.exe dist/latest.json `
            --repo $env:PUBLISH_REPOSITORY `
            --target main `
            --title "PlanBench $version" `
            --notes "..."
```

Bốn quyết định, đều ghi lý do trong file:

**`if: github.repository == ...`** — file workflow này **cũng nằm trong
repo public**, nó đi theo lịch sử được sao sang. Không có cổng chặn thì
một tag `desktop-v*` đẩy nhầm ở repo public sẽ build một installer thứ
hai từ cây đã đóng băng rồi **publish đè lên bản thật**. Dùng một file
kèm cổng thay vì hai bản file khác nhau: hai bản sẽ trôi lệch, và chỗ
phát hiện ra trôi lệch là lúc release.

**`GH_TOKEN: secrets.PUBLISH_TOKEN`, không phải `github.token`** —
token tự động chỉ có quyền trên chính repo nó chạy, mà release phải tạo
ở repo khác.

**`--target main`** — tag chưa tồn tại ở repo public (commit tương ứng
nằm ở repo private), nên `gh` phải được bảo tạo tag trên nhánh nào.

**Bỏ `--generate-notes`** — nó tóm tắt commit của repo *chạy build*, tức
repo private. Đăng tiêu đề commit của repo private lên trang release
public là rò rỉ không đổi lại được gì. Body giờ là một câu cố định nói
bản gì và tải ở đâu.

### 2. Remote cục bộ đổi vai

```
origin  -> https://github.com/AI20K-Build-Phase-Cohort-3/P-011.git   (private, nơi code)
publish -> https://github.com/hungnguyen-1601/T011-rav19-planbench   (public, nơi phát hành)
```

`origin` giờ là nơi làm việc, nên `git push` theo phản xạ đi đúng chỗ và
không còn đẩy nhầm code lên repo public.

### 3. Runbook

`docs/DESKTOP-RELEASE.md` thêm mục "Two repositories: where you tag, and
where the release appears", kèm bảng tra và hai hệ quả cần biết trước
khi đi tìm:

1. Tag ở repo public trỏ vào `main` đã đóng băng, **không** phải commit
   build ra installer. Provenance thật là tag cùng tên ở repo private,
   cộng SHA mà installer đóng dấu vào trang System — SHA đó sẽ không
   tra được ở repo public.
2. Body release là câu cố định, lý do ở mục trên.

Mục "The short version" thêm một dòng: chạy ở repo **private**.

## Cái không phải đổi

| Thứ | Đổi không |
|---|---|
| Link tải cố định | Không |
| `updater.REPOSITORY` | Không |
| Bản bắc cầu cho máy đang chạy | Không cần |
| Người dùng cài lại / dán token | Không |
| Đường CDN của 0.1.14 | Chạy nguyên |

Đây là lý do phương án này thắng ba phương án còn lại đã cân nhắc
(chuyển hẳn sang private; tạo repo phát hành mới; giữ code public).

## Cần người làm — chưa xong cho tới khi có

Trong repo **private**, tạo Actions secret tên `PUBLISH_TOKEN`:

1. github.com/settings/personal-access-tokens → **Fine-grained token**
2. Repository access: **chỉ** `hungnguyen-1601/T011-rav19-planbench`
3. Permissions → Repository permissions → **Contents: Read and write**
4. Copy, rồi vào `AI20K-Build-Phase-Cohort-3/P-011` → Settings → Secrets
   and variables → Actions → New repository secret, tên `PUBLISH_TOKEN`

**Dán thẳng vào ô secret của GitHub, không dán vào chat.** Phiên này đã
có một lần token đi qua chat, bị `.ai-log` ghi lại, và GitHub push
protection chặn push — không nên lặp lại.

Release kế tiếp sẽ hỏng ở bước cuối nếu secret chưa tồn tại: build và
smoke gate vẫn chạy, chỉ `gh release create` báo 401.

## Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| YAML parse | ok |
| Cổng repo | `github.repository == 'AI20K-Build-Phase-Cohort-3/P-011'` |
| Token dùng ở bước release | `${{ secrets.PUBLISH_TOKEN }}` |
| `--repo` trỏ biến `PUBLISH_REPOSITORY` | có |
| Hai repo lệch nội dung | 0 commit (org main chứa toàn bộ `main` public) |

Cảnh báo `Context access might be invalid: PUBLISH_TOKEN` từ linter IDE
là đúng và sẽ tự hết khi secret được tạo — nó chỉ đang nói secret chưa
tồn tại.
