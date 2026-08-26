# PlanBench (P-011) — luật cho agent làm việc trên repo này

Đọc file này trước khi sửa hoặc push bất cứ thứ gì.

Sản phẩm: **Planner Selector** — chọn cấu hình điều hướng tối ưu cho một
deployment cụ thể, chỉ mô phỏng, không điều khiển robot thật. Web app
(FastAPI + Next.js) và một desktop app Windows đóng gói từ cùng cây mã.

**`contracts/CONTRACTS.md` là luật.** Khi nó mâu thuẫn với bất kỳ tài
liệu nào khác — kể cả `docs/antongduy/de-tai-moi-planner-selector.md` —
contract thắng. Các điều khoản được trích dẫn khắp code dưới dạng
`HĐ-x.y`; sửa code chạm vào một điều khoản thì đọc điều khoản đó trước.

---

## 1. Hai remote — mọi lần push đi cả hai

`git push` một lần là **chưa đủ**, và chỗ nó thiếu thì không báo lỗi.

```
origin  https://github.com/hungnguyen-1601/T011-rav19-planbench   (public)
org     https://github.com/AI20K-Build-Phase-Cohort-3/P-011       (private)
```

| Remote | Vai | Release chạy ở đây? |
|---|---|---|
| `origin` | nơi code sống, nơi CI build | **có, và chỉ ở đây** |
| `org` | repo ban tổ chức, nơi nộp bài | không |

```powershell
git push origin main                     # repo làm việc
git push org main:refs/heads/<nhánh>     # bản nộp, rồi báo An mở PR
```

PR ở `org` merge bằng **"Create a merge commit"** — "Squash and merge"
gộp hàng trăm commit thành một và xoá sạch số đếm đóng góp, vốn là lý do
nộp sang đó.

**Đừng đề xuất gộp hai repo lại.** Link tải cố định chính là đường dẫn
repo public và được biên dịch cứng vào mọi bản app đã cài ở
`updater.REPOSITORY` — chuyển phát hành đi nơi khác thì link đã gửi cho
người khác chết và mọi bản đã cài mất cập nhật, im lặng. Chuyển CI sang
`org` thì cần quyền admin để thêm Actions secret, mà không ai bên này có
(`admin=False` trên cả hai repo, đo 2026-08-26). Chi tiết:
`docs/DESKTOP-RELEASE.md` mục "Two remotes".

---

## 2. Commit

- Tiền tố `TongDuyAn - `, **đúng một dòng**, **tiếng Anh**. Chi tiết để
  trong report, không nhồi vào commit message.
- **Không tự ý commit.** Chỉ commit khi An bảo. Xong việc thì dừng và
  báo cáo.
- Khi được bảo commit: làm trên **nhánh riêng**, và tách theo từng việc
  thay vì gom một cục.
- **Chỉ stage đúng file thuộc việc đang làm.** An thường làm song song
  một mảng khác trong cùng cây; quét `git add -A` là cách chắc chắn nhất
  để cuốn nhầm việc của An vào commit của mình.

**Không bao giờ commit:** `vfh_plus_import/`, `vfh_plus_iterated/`,
`mppi_import/`, `planbench.db.bak-*`, `artifacts/runs/`,
`presentation/thumbnail/`, và bất kỳ file nào An đang để untracked mà
mình không tạo ra.

`.ai-log/` **thì commit mỗi phiên** — đó là minh chứng công việc.

---

## 3. Secret

Hook `.ai-log` ghi lại **tool call nguyên văn**, nên mọi credential xuất
hiện trong phiên đều rơi vào đó và đi thẳng vào commit. GitHub push
protection đã chặn push vì lý do này hai lần trong một buổi.

- Trước khi commit `.ai-log/`, quét và thay mọi chuỗi khớp
  `gh[pousr]_[A-Za-z0-9]{36}` và `github_pat_…` bằng placeholder.
- Quét **bằng regex**, đừng viết chuỗi token thật vào script — chính
  script đó lại bị log và secret quay lại.
- Đừng bảo An dán secret vào chat. Bảo An ghi thẳng vào `.env` hoặc vào
  ô Actions secret của GitHub, rồi chỉ nói "đã ghi xong".
- Nếu push bị chặn: **đừng bấm link "allow the secret"** GitHub đưa ra.
  Đó là tự tay công bố credential. Redact rồi `--amend`.

---

## 4. Docs — `docs/antongduy/`

Thư mục này **được commit** (ngoại lệ so với thói quen gitignore), vì cả
team đọc.

| Folder | Chứa gì | Khi nào ghi |
|---|---|---|
| `reports/` | **đã thay đổi gì với code** | ngay sau khi xong một phần việc |
| `notes/` | **đã nhìn thấy gì** — khảo sát, đánh giá, research | sau khi khảo sát xong, kể cả khi không đổi dòng code nào |
| `plans/` | kế hoạch **chờ An duyệt** trước khi làm | sau khi chốt plan cùng An |

Đường dẫn: `<folder>/<YYYY-MM-DD>/tongduyan_<mô-tả-không-dấu>.md`
(riêng `plans/` không bắt buộc tiền tố).

Cuối một loạt việc phải có report **phủ hết** mọi task đã làm — kể cả
việc đã làm rồi bị yêu cầu hoàn tác: ghi lại cái đã khảo sát được, để
lần sau khỏi dò lại từ đầu.

Hai phiên lập kế hoạch khác nhau ⇒ **hai file plan riêng**, dù cùng ngày.

---

## 5. Test

- **Không chạy full suite** trừ khi An bảo. Chỉ chạy phần vừa sửa.
- Test ở repo này chủ yếu **đọc source và pin quyết định**, kèm văn xuôi
  giải thích *vì sao* quyết định đó tồn tại. Giữ nguyên lối đó.
- **Đừng pin thứ không phải hành vi.** Assertion bám vào thụt đầu dòng,
  ký tự xuống dòng hay thứ tự chuỗi sẽ đỏ khi CRLF/LF đổi, và nó không
  bảo vệ được gì. Pin tính chất, không pin hình dạng.
- Sửa `.py` xong chạy `ruff check` và `ruff format`; sửa web chạy
  `npx tsc --noEmit` và vitest cho suite liên quan.
- i18n: thêm key thì phải thêm vào **cả** `en.json` và `vi.json`. Thiếu
  một bên thì `translate()` fallback `?? key` và tên key hiện thẳng lên
  màn hình.

---

## 6. Chạy và deploy

- **Không tự restart server.** An tự chạy; đừng bật `next dev` thứ hai,
  nó xoá `.next` của An.
- Trước khi release desktop: đọc `docs/DESKTOP-RELEASE.md`. Deploy ở dự
  án này = bump `apps/desktop/planbench_desktop/VERSION`, commit, push,
  đẩy tag `desktop-v<X.Y.Z>`. Tag và VERSION lệch nhau thì CI từ chối.
- **Cổng release là smoke gate** trong `scripts/desktop/smoke_stage.py`,
  chạy trên interpreter đã đóng gói giữa lúc lắp stage và lúc đóng gói.
  Nó bắt được thứ pytest không thể thấy. Gate đỏ thì đọc nó nói gì trước
  khi sửa bất cứ thứ gì — nó nêu cơ chế, không nêu triệu chứng.
- Theo dõi CI thì poll **≥ 60 giây** hoặc gọi có xác thực. Hạn mức API
  ẩn danh là 60/giờ **theo IP, dùng chung với app của An đang chạy** —
  poll dày làm chính app của An hỏng cập nhật.

---

## 7. Bất biến nghiệp vụ dễ phá

Những thứ này đã bị phá ít nhất một lần và mỗi lần đều tốn một buổi:

- **Replanning là thuộc tính của stack**, cắm ở
  `services/simulator/planbench_simulator/nav_stack.py::run_stack()` —
  nơi mọi stack đều đi qua. Tuyệt đối không cắm vào file của một thuật
  toán.
- **Không vặn thí nghiệm cho khớp kết quả.** Khi một cổng không qua,
  bốn thứ tuyệt đối không được sửa để nó qua: map, mission,
  `collision_probability_max`, và tham số thuật toán tại chỗ.
- **Dưới 2 candidate qua cổng ⇒ không có Decision Card.** Không có
  ngoại lệ.
- **Bằng chứng không được nghe mạnh hơn dữ liệu cho phép.** Bảng cổng
  mang `n_episodes` theo từng candidate; đừng xếp một số từ 30 episode
  cạnh một số từ 300 như thể chúng cùng đơn vị tin cậy.
- **`resolve_git_sha` (`packages/decision/planbench_decision/card.py`)
  từ chối ghi manifest `unknown` — đừng nới lỏng nó.** Card không nêu
  được commit nghĩa là stamp thiếu; sửa stamp.
- Scope thí nghiệm: `global_planner_selection` đòi local layer giống
  hệt nhau, và ngược lại. Đây là HĐ-1.4, không phải tuỳ chọn UI.

---

## 8. Công cụ

CodeGraph MCP (`codegraph_*`) đã index sẵn toàn bộ symbol và edge. Dùng
nó cho câu hỏi **cấu trúc** (ai gọi gì, sửa cái này vỡ cái nào, X định
nghĩa ở đâu); dùng grep cho câu hỏi **văn bản** (nội dung chuỗi, comment,
log message).
