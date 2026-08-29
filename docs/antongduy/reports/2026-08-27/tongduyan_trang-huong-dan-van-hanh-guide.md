# Đã làm: trang hướng dẫn vận hành `/guide`

**Ngày:** 2026-08-27 · **Plan:** [`plans/2026-08-27/trang-huong-dan-van-hanh-guide.md`](../../plans/2026-08-27/trang-huong-dan-van-hanh-guide.md)
**Nhánh:** `tongduyan_guide-page`, worktree `../P-011-guide`, tách từ `main` `c0da14d`
**Trạng thái:** P0 → P6 xong. **Chưa push, chưa merge.** Cây `P-011` và
phần role đang dở **không bị đụng một dòng nào**.

| Phase | Commit | Nội dung |
|---|---|---|
| P0 | `d3c3b6a` | `SpaStaticFiles` phục vụ trang tĩnh theo URL không đuôi |
| P1a | `afb1e8e` | Hạ tầng MDX, registry module theo locale |
| P1b | `b48e815` | Shell wiki; `DecisionTabs` nới sang discriminated union |
| P1c | `16cea8f` | Landing, tìm kiếm, `guideContext` fail-open |
| P2 | `09e6d72` | `operation` · `pages` · `concepts` |
| P3 | `7889786` | `overview` · `getting-started` · `gates` · `evidence` |
| P4 | `680a36f` | `plugin-import` · `ai` · `running` |
| P5 | `fdb2474` | `reference` |

**11 bài × 2 thứ tiếng = 22 file MDX.** Dep thêm đúng 5 như đã hứa.

---

## 1. Một lỗi có sẵn, phát hiện khi làm P0

Ba trong bốn ưu điểm của phương án nhiều URL **không chạy trên bản
desktop**, và không phải vì guide — vì một lỗi có từ trước.

`tests/api/test_api_static_site.py` lấy `/login.html` **kèm đuôi**, và
khẳng định `/nonsense` trả 404. `SpaStaticFiles._shell_for` chỉ cứu hai
segment mà segment đầu nằm trong `DYNAMIC_ROUTES`. Mọi đường dẫn tĩnh
không đuôi — `/login`, `/decisions`, `/guide/operation` — rơi thẳng 404.

Không ai va vào vì app mở ở `/` và mọi điều hướng là client-side. Nhưng
**F5 trên một trang, hay dán link cho đồng nghiệp**, là đúng hai việc
trang hướng dẫn sinh ra để làm.

Sửa: thử thêm `path + ".html"` khi miss. Không đổi URL nào; sửa luôn
`/login` và mọi route tĩnh khác. Thứ tự hai luật được ghim bằng một test
mới: `/decisions/list` (trang thật dưới route động) phải thắng shell.

---

## 2. Ba thứ plan không lường được

**`next/dynamic` không nhận options dùng chung.** *"next/dynamic options
must be an object literal"* — trình biên dịch đọc options lúc build để
quyết định prerender, và không đi theo được một biến. Nên `ssr: false`
phải chép ở cả 22 lời gọi, và **T8 đếm** số lần xuất hiện, vì sót một cái
nghĩa là bài đó prerender bằng tiếng Anh cho người đọc tiếng Việt.

**`pages` không dùng được tab.** Neo `#deployments` sẽ nằm trong panel
`hidden` — trình duyệt không cuộn tới được, mà `pages` chính là bài các
bài khác link thẳng vào từng mục. Nên `pages` là mười mục cuộn thẳng. Tab
giữ cho `gates`, `evidence`, `ai`, `running`, `reference` — nơi **tab
chính là neo**, nên `#g2` mở tab G2 *là* trả lời xong cái link.

**Một cái răng có sẵn của repo bắt trúng trang mới.** `dashboard-page.test.tsx`
đòi mọi `page.tsx` phải dịch được. Trang `[slug]` là server component
không có chữ nào. Repo đã có sẵn lối đi cho hình dạng này — uỷ cho một
component **đặt cạnh route** — nên tôi chuyển `GuideArticle` sang cạnh
route thay vì nới test.

---

## 3. Hai lỗi tôi tự gây ra, ghi lại để không lặp

**Chạy `prettier --write "src/**/*"` trên cả cây.** Suite nhảy từ 8 lên
15 file đỏ / 46 test, vì nhiều test ở repo này đọc mã nguồn theo chuỗi và
prettier còn viết lại line-ending hàng loạt. Đã hoàn nguyên mọi file
ngoài phạm vi; suite về đúng baseline. Lệnh format phải nhắm đúng file
vừa sửa, như ở P0 (`ruff format --check` hai file).

**CSS đọc token không tồn tại.** `--surface-2`, `--text-muted`,
`--warning`, `--danger` — repo không có cái nào; tên thật là `--panel-2`,
`--muted`, `--warn`, `--err`. `tokens.test.ts` bắt được. Loại lỗi này
trôi qua mắt rất dễ vì trình duyệt im lặng.

---

## 4. Mười hai cái răng, tất cả đã chứng minh cắn

Mỗi cái tiêm một lỗi thật vào rồi đòi nó đỏ, sau đó khôi phục.

| # | Ghim gì | Tiêm gì | Kết quả |
|---|---|---|---|
| T0 | Desktop phục vụ URL không đuôi, không phá deep link cũ | đảo thứ tự page/shell; bỏ luật page | 1 đỏ · 3 đỏ |
| T1 | Link: slug · hash ∈ neo của bài đích · href ngoài ∈ `ALL_ROUTES` · vi/en cùng đích | `#maps` → `#map` | 2 đỏ |
| T2 | Hai thứ tiếng cùng tập slug và cùng tập `section.id` | đổi id ở một bản | 2 đỏ |
| T3 | Khoá i18n có ở cả `en.json` và `vi.json` | xoá một khoá khỏi `vi` | 2 đỏ |
| T4 | MDX không nêu tên role | thêm "Chỉ admin dùng được" | 1 đỏ |
| T5 | Manifest ⇄ `<Section>` khớp cả hai bản | (chung với T2) | 2 đỏ |
| T6 | `generateStaticParams` = đúng tập slug của manifest | bỏ một slug | 1 đỏ |
| T7a | Hash chọn tab · `hashchange` · không cướp focus · `pushState` | gỡ listener | 1 đỏ |
| T8 | Không import `.mdx` tĩnh ngoài registry; không `import()` ghép chuỗi; `ssr:false` đủ 22 | đổi một path thành template | 1 đỏ |
| T9 | Đổi ngôn ngữ không điều hướng | thêm `useRouter` vào `GuideArticle` | 1 đỏ |
| T10 | Mỗi bước `operation` bàn giao đúng một lần; `pages` không kể quy trình | xoá link của một bước | 2 đỏ |
| T11 | `guideContext` fail-open | `allSettled` → `all` | 1 đỏ |

**T7b không phải test.** Tab active có nhìn thấy được ở light/dark không
là phán đoán tương phản, cần trình duyệt. Ghi thẳng trong docstring của
`guide-tabs.test.tsx` rằng nó là việc review — không gộp vào để trông như
đã tự động.

**Một nửa T10 cũng vậy.** Chuyện `operation` có *lặp nội dung* `pages`
hay không là phán đoán; test chỉ ghim được hình dạng.

---

## 5. Bằng chứng

**Suite web:** 8 file / 19 test đỏ **trước và sau**, danh sách tên trùng
khít (`diff` rỗng). 2190 test xanh, tăng 45 so với baseline 2145.
Tất cả 19 cái đỏ là pre-existing, đúng thứ README §9.7 ghi.

**Typecheck:** 3 lỗi, cả ba ở `candidates-page.test.tsx` đòi khoá
`paper.*` chưa từng tồn tại. Không lỗi nào chạm file mới. Baseline cũng
đỏ đúng chỗ đó.

**Build:** `standalone` và `PLANBENCH_DESKTOP=1` đều exit 0. Export sinh
đủ 11 trang bài + `guide.html`.

**Kiểm bản export thật qua đúng đường bản desktop phục vụ**
(`SpaStaticFiles`, không phải fixture):

```
11 bài F5 trực tiếp     : all 200
/guide                  200      /decisions/abc123   200 (shell, như cũ)
/login                  200      /nonsense           404
/                       200      /guide/not-an-article 404
```

`/login` trước P0 là 404.

**Tách chunk theo ngôn ngữ, đo trên bản build thật:** prose bài
`operation` bản Việt nằm ở `chunks/9803…js`, bản Anh ở `chunks/9553…js`
— hai chunk khác nhau. Tiêu đề trong manifest thì nằm chung ở chunk
layout, và đó là **đúng thiết kế**: rail phải hiện được tên mọi bài mà
không tải nội dung bài nào.

**Guide suite:** 6 file / 63 test xanh. **T0 python:** 12 xanh.

---

## 6. Còn lại cho người kiểm

Bốn thứ cần trình duyệt hoặc máy thật, tôi **không** kiểm được và không
tuyên bố đã kiểm:

1. Bấm chuyển ngôn ngữ giữa một bài — nội dung đổi, URL và hash giữ
   nguyên, không remount lặp. (T9 chỉ ghim được cấu trúc: `GuideArticle`
   không có `useRouter`/`router.`/`window.location`.)
2. Bấm tab và bấm Back — lịch sử đi qua từng tab.
3. **T7b** — tab active nhìn thấy được ở light và dark.
4. Cài bản desktop, đăng nhập `admin`/`admin`, mở `/guide`, F5 giữa bài.

Mục 4 là ràng buộc cứng của memory `giam-khao-dung-admin-admin`. Tôi đã
kiểm phần server-side của nó (mục 5), phần còn lại là chạy trình cài đặt
thật.

---

## 7. Ba việc plan ghi mà tôi làm khác, có lý do

| Plan | Đã làm | Vì sao |
|---|---|---|
| `pages` có tab Workspace/Resources/Account | không tab, mười mục | neo trong panel ẩn không cuộn tới được |
| `NAV_UTILITY` + i18n ở P1c | kéo lên P1b | không có chúng thì breadcrumb và tiêu đề hiện slug thô, shell chưa gọi là chạy được |
| 5 nhóm tab như bảng IA | thêm `ai`, `running`, `reference` dùng tab | ba bài này đều là các mặt ngang hàng, và tab của chúng là neo |

---

## 8. Chưa làm

Không push (memory `push-hai-remote` chờ lệnh), không merge, không sửa
`README.md`. README §9 vẫn còn bốn chỗ cũ — bài `reference` nói đúng hiện
trạng, nhưng README thì chưa được sửa, và đó là việc riêng.
