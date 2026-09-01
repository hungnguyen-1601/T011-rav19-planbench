# Đẩy lịch sử main của repo team sang một nhánh trong repo ban tổ chức

Ngày 2026-08-26.

## Việc cần làm

Phần lớn công việc được commit vào repo riêng của team
(`hungnguyen-1601/T011-rav19-planbench`) trong khi nơi cần nộp là repo
của ban tổ chức (`AI20K-Build-Phase-Cohort-3/P-011`). Yêu cầu: chuyển
toàn bộ nội dung nhánh `main` của repo team sang một nhánh mới trong
repo ban tổ chức, giữ nguyên mọi chỉ số đóng góp mà GitHub Insights
đếm được, và giữ nguyên từng byte của `.ai-log/` vì đó cũng là minh
chứng công việc.

## Khảo sát trước khi làm

Hai repo không phải hai lịch sử xa lạ. Chúng có tổ tiên chung
`d3328ca` — chính là đầu nhánh `hungnguyen-1601` trong repo ban tổ
chức.

| Đại lượng | Giá trị |
|---|---|
| `main` repo team | 523 commit, HEAD `c0da14d` |
| `main` repo ban tổ chức | 289 commit, HEAD `9e367cb` |
| Merge-base | `d3328ca` |
| Org main có mà team main thiếu | 1 commit (`9e367cb`, merge PR #1) |
| Team main có mà org main thiếu | 235 commit |
| Xung đột dự kiến khi merge | 0 (`git merge-tree` trả tree sạch `8bef199`) |

`9e367cb` có hai cha là `9bedac4` và `d3328ca`, cả hai đều đã nằm
trong team main. Nên khoảng cách giữa hai repo thực chất là "repo ban
tổ chức tụt lại phía sau", không phải phân nhánh thật.

Tác giả của 235 commit chênh lệch: An Tong 186, Phạm Thái Sơn 41, Hung
Nguyen 7, tungnhoc 1. Trong đó 9 merge commit và 78 commit mang trailer
`Co-Authored-By: Claude`.

Quyền ghi vào repo ban tổ chức được xác nhận bằng một lần
`git push --dry-run` (không tạo ref nào trên máy chủ).

## Vì sao chỉ số không mất

GitHub Contributors graph đếm commit reachable trên **default branch**,
quy chủ theo email của author cộng thêm trailer `Co-Authored-By`. Push
không đổi author, email hay ngày; merge bằng merge commit thậm chí
không đổi cả SHA. Con số 404 / 102 / 53 / 41 đang thấy ở repo team sẽ
tái lập ở repo ban tổ chức sau khi nhánh này vào `main`.

Chênh lệch giữa 404 (Insights) và 413 (`git shortlog`) là do Insights
cắt theo cửa sổ "Last 3 months"; và mục "claude 102 commits" không
phải một contributor riêng mà là 105 commit mang trailer Claude.

Điều kiện bắt buộc khi merge PR: **chọn "Create a merge commit", tuyệt
đối không "Squash and merge"**. Squash gộp 235 commit thành 1 và xoá
sạch minh chứng. "Rebase and merge" giữ được số đếm nhưng đổi SHA và
bỏ 9 merge commit — kém hơn.

## Đã làm gì

Không rewrite history, không `filter-repo`, không force-push. Chỉ hai
thao tác:

```bash
git remote add upstream https://github.com/AI20K-Build-Phase-Cohort-3/P-011.git
git push upstream main:refs/heads/tongduyan_import-from-team-repo
```

Kết quả push: `* [new branch] main -> tongduyan_import-from-team-repo`,
exit 0. Chỉ 22.78 MiB được truyền chứ không phải 390 MB, vì repo ban tổ
chức đã có sẵn phần lịch sử chung — 3645 object gửi đi, 183 object phía
máy chủ dùng lại.

## Kiểm chứng sau khi push

| Kiểm | Kết quả |
|---|---|
| SHA nhánh trên máy chủ | `c0da14d…` |
| SHA `main` cục bộ | `c0da14d…` — trùng khớp |
| `.ai-log/` trong commit đã push | 27 file, 103.39 MiB |
| Nhánh `probe-write-access*` còn sót | không có |

`.ai-log/` nguyên vẹn vì lịch sử không hề bị viết lại — cùng một object
SHA, không phải bản sao.

## Còn lại chưa nằm trong nhánh đã đẩy

Đây là các thay đổi chưa commit ở cây làm việc, nên không có trong
`main` và không được push:

- `.ai-log/archive/2026-08-26.jsonl` — thêm 545 dòng
- `.ai-log/session.jsonl` — sửa 7 dòng
- `.gitignore` — thêm `vfh_plus_iterated/`
- Chưa track: `docs/antongduy/notes/2026-08-26/` (5 file),
  `docs/antongduy/plans/2026-08-26/`,
  `docs/antongduy/reports/2026-08-24/` và `2026-08-26/` (4 file),
  `artifacts/runs/2026-08-25/`, `mppi_import/`,
  `presentation/thumbnail/`, hai file `planbench.db.bak-before-00*`

Nếu muốn phần log ngày 2026-08-26 cũng là minh chứng thì phải commit
rồi push bổ sung lên chính nhánh đó trước khi mở PR.

## Bước tiếp theo (người làm)

Mở PR `tongduyan_import-from-team-repo` → `main` tại
https://github.com/AI20K-Build-Phase-Cohort-3/P-011/pull/new/tongduyan_import-from-team-repo
và merge bằng **Create a merge commit**.

Lưu ý: 235 commit này gồm cả công của Sơn, Hưng và tungnhoc, không
riêng một người — nên báo team trước khi merge.

## Kiểm chứng độc lập bằng bản clone mới từ máy chủ

Sau khi push, một bản clone blobless mới (`--filter=blob:none
--no-checkout --single-branch`) được kéo về thư mục tạm để đọc lịch sử
trực tiếp từ máy chủ chứ không dùng object cục bộ. Kết quả trùng khớp
hoàn toàn: 523 commit, 500 commit không phải merge, An Tong 413, Hung
Nguyen 65, Phạm Thái Sơn 41, hungnguyen-1601 2, phoenix-mentor[bot] 1,
tungnhoc 1, 105 commit mang trailer Claude, `.ai-log/` 27 file /
103.39 MiB. Tree SHA `8bef199d…` giống hệt `main` cục bộ. Bản clone đã
được xoá sau khi kiểm.

## Sau khi merge vào main của ban tổ chức

PR #2 được merge bằng merge commit `e382e5d`, hai cha là `9e367cb`
(main cũ) và `c0da14d` (đỉnh nhánh đã đẩy) — đúng kiểu "Create a merge
commit", không squash, nên toàn bộ SHA gốc giữ nguyên.

| Đại lượng | Org main trước merge | Sau merge |
|---|---|---|
| Tổng commit | 289 | **525** |
| Không tính merge commit | — | **500** |
| An Tong `antongduy@gmail.com` | — | **415** (413 + 2 merge commit) |
| Hung Nguyen | — | 65 |
| Phạm Thái Sơn | — | 41 |
| hungnguyen-1601 (noreply) | — | 2 |
| phoenix-mentor[bot] | — | 1 |
| tungnhoc | — | 1 |
| Trailer `Co-Authored-By: Claude` | — | 105 |
| `.ai-log/` | — | 27 file, 103.39 MiB |

`git diff upstream/main main` trả về rỗng và tree SHA hai bên đều là
`8bef199d…`, tức nội dung cây file của main ban tổ chức bây giờ trùng
khít với main repo team. Commit đầu lịch sử vẫn là `9bedac4`
(2026-07-23), không đứt đoạn.
