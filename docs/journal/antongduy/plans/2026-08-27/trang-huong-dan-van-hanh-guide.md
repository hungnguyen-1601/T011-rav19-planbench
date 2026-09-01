# `/guide` — trang hướng dẫn vận hành dạng wiki

**Ngày:** 2026-08-27 · **Trạng thái: đã thi hành xong P0–P6** trên nhánh
`tongduyan_guide-page` (worktree `../P-011-guide`), 8 commit, chưa push chưa merge.
Báo cáo: [`reports/2026-08-27/tongduyan_trang-huong-dan-van-hanh-guide.md`](../../reports/2026-08-27/tongduyan_trang-huong-dan-van-hanh-guide.md).
**Đây là plan duy nhất.** Ba bản nháp trước (`…-ban-chot`, `…-wiki`,
`…-wiki-v2`) đã xoá; mọi thứ còn hiệu lực gộp vào đây.
**Khảo sát nền:** [`notes/2026-08-27/tongduyan_mang-kien-thuc-cho-trang-huong-dan-van-hanh.md`](../../notes/2026-08-27/tongduyan_mang-kien-thuc-cho-trang-huong-dan-van-hanh.md)

**An đã chốt:** kiến trúc lai (MDX nội dung · i18n giao diện · API dữ liệu
động, **không** cho API đọc tuỳ ý `docs/`) · wiki nhiều URL, `/guide` là
landing · độc giả là cả ban giám khảo lẫn người vận hành · tìm kiếm mức
tiêu đề · `operation` một mạch, không tab.

---

## 0. Một điểm chết phải sửa trước

An nêu bốn ưu điểm của nhiều URL: gửi link chính xác · refresh không mất
nội dung · back/forward tự nhiên · link được từ dấu `?` trên form.

**Ba trong bốn cái đó hôm nay không chạy trên bản desktop.**

```python
# tests/api/test_api_static_site.py
def test_an_exported_page_is_served_by_name(desktop_client):
    response = desktop_client.get("/login.html")      # ← kèm đuôi .html
...
    assert desktop_client.get("/nonsense").status_code == 404
```

Mount là `SpaStaticFiles(directory=web_root, html=True)`, và `_shell_for`
chỉ cứu **hai segment mà segment đầu nằm trong `DYNAMIC_ROUTES`**
(`decisions`, `maps`, `scenarios`). Đường dẫn tĩnh không đuôi — `/login`,
`/guide/operation` — rơi thẳng 404.

Hôm nay không ai va vì app mở ở `/` và mọi điều hướng là client-side.
Nhưng F5 trên một bài và dán link cho đồng nghiệp là đúng hai việc trang
này sinh ra để làm.

| | Cách | Được | Mất |
|---|---|---|---|
| **A — chọn** | `SpaStaticFiles` thử thêm `path + ".html"` khi miss và file đó có thật | không đổi URL nào; sửa luôn `/login` và mọi route tĩnh khác | đụng file đang phục vụ bản desktop **ban giám khảo đang chấm** |
| B | `trailingSlash: true` | không cần sửa Python | **đổi mọi URL toàn app**, ảnh hưởng cả build `standalone` |

**Chọn A.** B đổi một thứ toàn cục để giải một vấn đề cục bộ, trên bản
đang được chấm.

Ràng buộc kèm (memory `giam-khao-dung-admin-admin`): sau khi sửa, deep
link `/decisions/<id>` vẫn trả shell, `/nonsense` vẫn 404, `admin:admin`
dùng được toàn app.

---

## 1. Tải MDX theo locale — thiết kế khoá cứng

### 1.1. `DEFAULT_LOCALE = "en"` đổi câu trả lời

`lib/i18n/shared.ts:19`. Static export prerender **bằng tiếng Anh**.

Để MDX render lúc build rồi hydrate theo cookie thì người đọc tiếng Việt
thấy **một bài tiếng Anh dài đầy màn hình rồi mới lật**. Với chuỗi ngắn ở
trang khác app đã chấp nhận cái nháy đó; với bài 2000 chữ thì không còn là
nháy.

**Chốt: không prerender nội dung bài.** `ssr: false` + skeleton có chiều
cao. Mất nội dung trong HTML tĩnh — ở đây không mất gì thật: app sau đăng
nhập, bản desktop, không SEO.

### 1.2. `dynamic()` tạo **một lần ở module scope**, không tạo trong render

Gọi `dynamic()` trong thân render sinh **component type mới mỗi lần
render** → React thấy type khác → unmount/remount → skeleton nháy lại, và
Next khó gắn preload cho từng import.

```ts
// content/guide/modules.ts
const opts = { ssr: false, loading: ArticleSkeleton } as const;

export const GUIDE_MODULES = {
  vi: {
    operation: dynamic(() => import("./vi/operation.mdx"), opts),
    // …11 bài
  },
  en: {
    operation: dynamic(() => import("./en/operation.mdx"), opts),
  },
} satisfies Record<Locale, Record<Slug, ComponentType>>;
```

Dùng:

```tsx
const Article = GUIDE_MODULES[locale][slug];
return <Article />;
```

Đường dẫn **viết thẳng, không ghép chuỗi**
(`import(\`./${locale}/${slug}.mdx\`)`) — ghép chuỗi làm bundler gom cả
thư mục thành một chunk.

### 1.3. Sửa một lời hứa viết sai

Bản nháp trước viết *"một ngôn ngữ vào bundle — 22 chunk, tải đúng một"*.
Sai hai chỗ: **build output chứa cả hai locale**, và bundler không đảm bảo
đúng 22 chunk (nó được phép tách nhỏ hoặc dùng shared chunk).

Lời hứa đúng, và đây mới là thứ **T8** kiểm được:

> Cả hai locale có trong build output. **Runtime không tải module MDX của
> locale còn lại.**

### 1.4. Luồng

```
app/guide/[slug]/page.tsx            ← SERVER component
  · generateStaticParams() ← GUIDE.map(a => a.slug)
  · slug ∉ manifest → notFound()
  · <GuideArticle slug={slug} />
        ↓
components/guide/GuideArticle.tsx    ← CLIENT component
  · const { locale } = useTranslation()     ← KHÔNG có useLocale() trong repo
  · const Article = GUIDE_MODULES[locale][slug]
  · <Article />
  · đổi ngôn ngữ → chỉ `Article` đổi; KHÔNG router.push, KHÔNG đụng hash
```

`useTranslation()` (`lib/i18n/index.ts:68`) trả `{ locale, t }` — không
tạo hook mới chỉ để đọc locale. `Providers` cấp `LocaleContext` từ
`localeStore`, nên đổi ngôn ngữ cập nhật context client-side; `router.refresh()`
trong `LanguageSwitcher` là để build `standalone` đồng ý, và là no-op trên
static export.

| Câu hỏi | Chốt |
|---|---|
| `[slug]/page.tsx` server hay client | **server** — `generateStaticParams` là API server-only |
| Locale từ đâu | `useTranslation().locale` |
| Ánh xạ module | `GUIDE_MODULES[locale][slug]`, dynamic tạo ở module scope |
| Bundle | cả hai locale có trong output; runtime chỉ tải một |
| Đổi ngôn ngữ giữ slug/hash | **có** — slug trung lập ngôn ngữ, `id` do tác giả viết giống hệt hai bên |

---

## 2. `id` là thứ tác giả viết, không phải slug sinh ra

Slug hoá tiêu đề (`rehype-slug`) hỏng theo thiết kế:

```
vi:  Khai deployment        → #khai-deployment
en:  Declare a deployment   → #declare-a-deployment
```

Hai id cho một mục ⇒ link sâu chết khi người nhận đọc thứ tiếng khác.

Chốt: component `<Section id="…" title="…">`, `id` **giống hệt hai bên**,
chỉ `title` đổi. Không cần `rehype-slug` — giữ đúng 5 dep.

---

## 3. Cấu trúc thông tin — 11 bài

Tiêu chí (nguyên văn của An):

> **Bài riêng** khi nội dung đọc được, gửi link được và hiểu được độc lập.
> **Tab** khi các phần cùng trả lời một câu hỏi và ngang hàng.

Giữ một vế của luật cũ vì nó có lý do kỹ thuật: **không tab cho nội dung
đọc tuần tự** — panel không active render `hidden`, Ctrl+F không thấy, và
người đọc bước 2 không biết bước 5 tồn tại.

| Nhóm | Bài | Tab |
|---|---|---|
| Tổng quan | `overview` | Hệ thống làm gì · Luồng tổng thể · Thuật ngữ |
| | `getting-started` | — |
| Vận hành | `operation` | — (một mạch) |
| | `pages` | Workspace · Resources · Account |
| Hiểu kết quả | `concepts` | — |
| | `gates` | G1 · G2 · G3 · G4 · G5 · G6 |
| | `evidence` | Ghép cặp · Khoảng tin cậy · Thang bằng chứng |
| Nâng cao | `plugin-import` | — |
| | `ai` | Trợ lý · Cố vấn · Cấu hình · Offline |
| | `running` | Web · Cục bộ · Windows · Desktop · API |
| Tham khảo | `reference` | Quyền hạn · Xuất-chia sẻ-duyệt · Giới hạn |

**11 bài × 2 tiếng = 22 file MDX.** Không gộp xuống 8: `gates` và
`evidence` đều thoả tiêu chí "gửi link được, hiểu độc lập" —
`/guide/gates#g2` là đúng thứ người ta dán vào chat khi cãi nhau về một cổng.

---

## 4. Ranh giới `operation` ⇄ `pages`

| | Trả lời | Không được chứa |
|---|---|---|
| `operation` | *"tôi phải làm gì, theo thứ tự nào"* | mô tả từng trường nhập, từng tab của màn hình |
| `pages` | *"màn hình này có gì, trường này nghĩa là gì, lỗi này là gì"* | thứ tự các bước, "trước tiên / tiếp theo" |

Mỗi bước trong `operation` kết bằng **đúng một** link
`[Xem chi tiết màn hình →](/guide/pages#deployments)`. Không bảng ba cột —
bảng đó chính là chỗ `pages` rò ngược vào `operation`.

**Chống trùng: một nửa là răng, một nửa là review.** Id khác nhau **không**
chứng minh nội dung không trùng — hai bài viết cùng một đoạn với hai id
khác nhau vẫn trùng. Nên:

- **Răng (T10):** mỗi bước `operation` có đúng một link vào `pages#…`; và
  `pages` không chứa từ chỉ thứ tự quy trình (`trước tiên`, `tiếp theo`,
  `bước tiếp`, `first`, `next step`).
- **Acceptance review (không phải test):** `operation` không mô tả field
  hay tab cụ thể · `pages` không kể quy trình · không đoạn nào copy nguyên
  giữa hai bài.

---

## 5. `reference` — tách tĩnh khỏi động

| Tầng | Nội dung | Ở đâu |
|---|---|---|
| Tĩnh | capability là gì · vì sao thao tác cần quyền · thiếu quyền thì làm gì | MDX |
| Động | tài khoản đang đăng nhập **có / không có** | `<CapabilityNotice>` |

- MDX: *"Nhập thuật toán yêu cầu capability `plugin.import`."*
- Component: *"Tài khoản hiện tại của bạn: **có quyền** / **không có quyền**."*

**T4:** MDX **được** nhắc tên capability; **không được** chứa `is_admin`,
`"chỉ admin"`, `"admin only"`, hay tên role. Ánh xạ role→capability sống
đúng một chỗ: `guideContext.ts`.

---

## 6. `guideContext` — hợp đồng, và **fail-open**

```ts
export interface GuideContext {
  version: string;          // GET /health         → version
  aiReady: boolean;         // GET /settings/agent → ready && !active_deterministic
  aiModel: string;          // GET /settings/agent → active_model
  signedIn: boolean;        // GET /auth/session
  canImportPlugin: boolean; // hôm nay: session.is_admin
}
```

**Zero endpoint mới** — cả ba đã có.

`canImportPlugin` là điểm khớp với
[plan role](thiet-ke-role-engineer-reviewer-admin.md): hôm nay
`session.is_admin`, khi P0 role chạy thì đổi **một dòng** thành
`has("plugin.import")`. Comment trỏ sang plan đó nằm ngay trên dòng ấy.

**Fail-open, bắt buộc.** Trang hướng dẫn là nội dung tĩnh; API hỏng không
được chặn việc đọc:

```
guideContext đang tải hoặc lỗi
  → CapabilityNotice và status card ẩn (hoặc làm mờ)
  → sidebar, landing, nội dung MDX vẫn render đầy đủ
```

Ba lời gọi song song, hỏng độc lập. Chưa đăng nhập thì `/settings/agent`
và `/auth/session` trả 401 — đó là **câu trả lời**, không phải lỗi.
Quan trọng vì có link từ `/welcome`, nơi người dùng thường chưa có session.
**T11** canh: chặn cả ba lời gọi vẫn đọc được bài.

---

## 7. Tab — tái dùng, không viết mới

[`components/DecisionTabs.tsx`](../../../../../apps/web/src/components/DecisionTabs.tsx)
đã có đủ: `role="tablist"/"tab"/"tabpanel"`, `aria-selected`,
`aria-controls`, `aria-labelledby`, roving `tabIndex`, mũi tên +
`Home`/`End` qua `tabAfterKey`, `preventDefault` để mũi tên không cuộn
trang, selection-follows-focus. **Không viết `Tabs.tsx` thứ hai** — hai bộ
luật bàn phím cho một cử chỉ, và bộ mới sẽ là bộ kém hơn.

### 7.1. Nới kiểu — phải là discriminated union

`DecisionTabSpec.labelKey` hiện là `string` (dòng 37). `string | string`
không phân biệt được, nên component không biết `"G1"` là chữ đã dịch hay
key phải gọi `t("G1")`:

```ts
type TabLabel =
  | { labelKey: string; label?: never }
  | { label: string; labelKey?: never };

export type DecisionTabSpec = { id: string; content: ReactNode } & TabLabel;

type TabsLabel =
  | { ariaLabelKey: string; ariaLabel?: never }
  | { ariaLabel: string; ariaLabelKey?: never };
```

Tiêu đề tab của guide nằm trong `manifest.ts` (song ngữ, không phải key),
nên đi nhánh `label` / `ariaLabel`. Chỗ gọi hiện có không đổi.

### 7.2. Giao thức focus

| Tình huống | Hành vi |
|---|---|
| Hash trỏ tới tab (deep link, F5) | **chọn tab**, cuộn tới nó, **không cướp focus** |
| Kích hoạt kết quả tìm kiếm trong phiên | chọn tab **và** `panel.focus()` |
| Hash không khớp tab nào | tab đầu, không màn trắng |

Panel cần `tabIndex={-1}` để `.focus()` gọi được. Tín hiệu "đến từ
tìm kiếm" là state trong phiên (không phải query param) — deep link và F5
không được tự cướp focus.

Đổi tab thì `history.pushState`, để back/forward đi qua từng tab.

---

## 8. Tìm kiếm — mức tiêu đề, và nói thật trên nhãn

Tìm trên **tiêu đề bài + tiêu đề mục + tiêu đề tab**, mọi bài, đọc từ
manifest. Không dep, không index build-time.

Lọc **không dấu, không phân biệt hoa thường** (`normalize("NFD")` + bỏ dấu
tổ hợp, ~6 dòng) — gõ `khai` phải ra *Khai deployment*. Có unit test riêng
cho hành vi này vì đó là cách người Việt gõ thật.

**Nhãn nói đúng cái nó làm:** ô ghi **"Tìm bài và đề mục"**, không phải
"Tìm kiếm hướng dẫn" — người dùng thấy chữ sau sẽ mặc định nó tìm cả nội
dung. Kết quả rỗng nói thêm: *"Chưa tìm cả nội dung bài — mở bài rồi Ctrl+F."*

Key i18n đặt trung lập `guide.search.placeholder`: khi có full-text thì
đổi **chữ**, không đổi **key**.

Full-text là việc sau, khi nội dung đứng yên.

---

## 9. Cấu trúc file

```
apps/web/
├── content/guide/
│   ├── manifest.ts                 ← slug · group · order · title{vi,en} · sections · tabs
│   ├── modules.ts                  ← GUIDE_MODULES, dynamic ở module scope
│   ├── vi/{overview,getting-started,operation,pages,concepts,gates,
│   │        evidence,plugin-import,ai,running,reference}.mdx
│   └── en/{…11 file cùng tên…}
├── src/app/guide/
│   ├── layout.tsx                  ← shell: sidebar con · tìm kiếm · breadcrumb
│   ├── page.tsx                    ← landing
│   └── [slug]/page.tsx             ← server, generateStaticParams
└── src/components/guide/
    ├── GuideArticle.tsx · GuideSidebar.tsx · GuideSearch.tsx
    ├── ArticleToc.tsx · PrevNext.tsx · ArticleSkeleton.tsx
    ├── Section.tsx · Callout.tsx · AppLink.tsx · CapabilityNotice.tsx
    └── (dùng DecisionTabs đã nới, lib/guideContext.ts)
```

**`[slug]` một đoạn, không `[...slug]`** — IA phẳng, nhóm chỉ là nhãn trên
sidebar chứ không phải đoạn URL. Catch-all mở ra `/guide/a/b/c` mà
`generateStaticParams` không liệt kê.

### Manifest thay frontmatter — bớt hai dep

`@next/mdx` không đọc frontmatter; muốn YAML phải thêm `remark-frontmatter`
+ `remark-mdx-frontmatter`. Đặt trong `manifest.ts` thì không thêm dep, và
`generateStaticParams` · sidebar · tìm kiếm · prev/next đọc **cùng một
nguồn** — nếu mỗi bài tự khai frontmatter thì sidebar phải import cả 11
module (kéo toàn bộ nội dung vào landing) mới dựng được menu.

---

## 10. URL

| Thứ | Hình dạng |
|---|---|
| Landing | `/guide` |
| Bài | `/guide/operation` — slug **tiếng Anh, không đổi theo locale** |
| Mục | `/guide/operation#buoc-3-deployment` |
| Tab | `/guide/gates#g2` |

`/guide` là landing chứ không phải một bài dài: ô tìm kiếm · **Năm phút
đầu** nổi bật · sơ đồ bảy bước (mỗi bước là link vào
`/guide/operation#…`, không phải hình trang trí) · card theo nhóm ·
trạng thái động (phiên bản · AI online/offline · capability).

---

## 11. Entry — utility link cuối sidebar

"Hướng dẫn" không thuộc **Account**, và tạo `nav.section.help` cho một mục
là lặp lại lỗi `navigation.ts` vừa gỡ (*"A heading is a claim about a set"*).

```ts
export const NAV_UTILITY: readonly NavItem[] = [
  { href: "/guide", labelKey: "nav.guide", icon: "book",
    descriptionKey: "nav.desc.guide" },
];
export const ALL_ROUTES = [...NAV_SECTIONS.flatMap(s => s.items),
                           ...NAV_UTILITY, ...EXTRA_ROUTES];
```

`Sidebar.tsx` render `NAV_UTILITY` sau vòng `NAV_SECTIONS`, **trên** nút
gập, ngăn bằng một đường kẻ, không heading. Phải có trong `ALL_ROUTES`:
`shell.test.tsx` đọc nó để dựng title và breadcrumb. Cần icon `book` mới.

Hai lối vào phụ: tile trên `/`, link trên `/welcome`.

---

## 12. i18n — chỉ chữ của khung

```
nav.guide · nav.desc.guide
guide.title · guide.subtitle
guide.search.placeholder · guide.search.noMatch · guide.search.clear
guide.toc · guide.backToTop · guide.prev · guide.next
guide.openIn                       // "Xem trên trang {page}"
guide.version · guide.ai.on · guide.ai.offline
guide.capability.canImport · guide.capability.cannotImport
guide.signInToSee
dashboard.guide.title · welcome.guide.link
```

Tiêu đề bài/mục/tab nằm trong `manifest.ts`, không phải i18n. Phát sinh
key ngoài danh sách này là dấu hiệu văn đang rò từ MDX sang JSON — dừng
và hỏi.

---

## 13. Mười hai cái răng

| # | Ghim gì | Kiểu | Phase |
|---|---|---|---|
| T0 | Desktop trả 200 cho `/guide/operation` và `/login`; `/decisions/<id>` vẫn trả shell; `/nonsense` vẫn 404 | auto | P0 |
| T1 | Link trong MDX: slug ∈ manifest · hash ∈ sections∪tabs của **bài đích** · href ngoài ∈ `ALL_ROUTES` · vi/en cùng slug+id | auto | mọi phase MDX |
| T2 | `vi/` và `en/` cùng tập slug; mỗi bài cùng tập `section.id` | auto | mọi phase MDX |
| T3 | Key i18n có ở cả `en.json` và `vi.json` | auto | P1c |
| T4 | MDX không chứa `is_admin` / `"chỉ admin"` / `"admin only"` / tên role | auto | mọi phase MDX |
| T5 | Mọi `id` trong manifest có đúng một `<Section id=…>` ở **cả hai** file, và ngược lại | auto | mọi phase MDX |
| T6 | `generateStaticParams` trả đúng tập slug của manifest; export sinh đủ 11 trang | auto | P1a |
| T7a | Hash chọn đúng tab · bàn phím · focus panel chỉ khi đến từ tìm kiếm, deep link/F5 **không** cướp focus | auto | P3 |
| T7b | Tab active nhìn thấy được ở **light và dark**, đạt ngưỡng tương phản | **visual QA** | P3 |
| T8 | Runtime **không tải** module MDX của locale còn lại; không `import()` ghép chuỗi; không import `.mdx` tĩnh ngoài `modules.ts` | auto | P1a |
| T9 | Đổi locale giữa bài: nội dung sang đúng locale mới · không hiện lại locale cũ · `pathname` và `hash` không đổi · không remount lặp do `router.refresh()` | auto | P1a |
| T10 | Mỗi bước `operation` có đúng một link vào `pages#…`; `pages` không chứa từ chỉ thứ tự quy trình | auto | P2 |
| T11 | Chặn cả ba lời gọi của `guideContext` → bài vẫn đọc được, sidebar và landing vẫn render | auto | P1c |

**T1 · T2 · T4 · T5 chạy sau mọi phase thêm MDX**, không dồn về cuối — một
câu "chỉ admin" thêm ở P4 mà tới P6 mới biết là muộn ba phase.

Mỗi răng tiêm lỗi rồi đòi nó đỏ trước khi tính là xong.

---

## 14. Phase

| Phase | Nội dung | Xong nghĩa là |
|---|---|---|
| **P0** | `SpaStaticFiles` cách A | **T0** |
| **P1a** | 5 dep + `next.config` + `vitest.config` + `manifest.ts` + `modules.ts` + `[slug]/page.tsx` + `GuideArticle` + `ArticleSkeleton` | build xanh **cả hai output**; **T6 · T8 · T9**; một bài giả hiện đúng thứ tiếng |
| **P1b** | Shell wiki: sidebar con · breadcrumb · prev/next · `ArticleToc` · `Section` · `Callout` · `AppLink` · nới `DecisionTabs` (union) | shell chạy với nội dung giả; chỗ gọi `DecisionTabs` cũ không đổi |
| **P1c** | Landing · tìm bài-và-đề-mục · `guideContext` · `CapabilityNotice` · `NAV_UTILITY` + icon + tile + welcome · i18n | **T3 · T11**; landing dựng từ manifest |
| **P2** | `operation` · `pages` · `concepts` — vi+en cùng commit từng bài | **T1 T2 T4 T5 T10** |
| **P3** | `overview` · `getting-started` · `gates` · `evidence` | **T1 T2 T4 T5 · T7a**; **T7b** QA tay |
| **P4** | `plugin-import` · `ai` · `running` | **T1 T2 T4 T5** |
| **P5** | `reference` — **sau cùng**, sau khi đọc lại `OFFICIAL_GOLDEN_READY` ở cây chính | **T1 T2 T4 T5**; mọi câu có `file:line` hoặc commit đứng sau |
| **P6** | Chạy lại 12 răng; bản desktop thật: F5 trên một bài · dán link · đổi ngôn ngữ giữa bài · `admin:admin` dùng được toàn app | 12/12 cắn |

**Không full suite** trừ khi An bảo · **không tự commit** · report vào
`docs/antongduy/reports/2026-08-27/`.

---

## 15. Rủi ro

| Rủi ro | Dấu hiệu | Xử |
|---|---|---|
| `@next/mdx` xung khắc `output: export` | P1a build `PLANBENCH_DESKTOP=1` đỏ | **Dừng và báo An.** Rủi ro duy nhất giết cả phương án MDX — đặt ở phase đầu để biết sớm |
| Sửa `SpaStaticFiles` làm hỏng deep link đang chạy | T0 đỏ ở vế "không đổi" | revert P0, cân lại cách B |
| `reference` viết xong đã cũ | nhánh `tongduyan_ai-analyst-ban-8` merge giữa chừng | P5 xếp cuối chính vì vậy |

---

## 16. Đã thi hành

P0–P6 xong, 12/12 răng chứng minh cắn. Ba chỗ làm khác plan và lý do —
`pages` bỏ tab, `NAV_UTILITY` kéo lên P1b, ba bài dùng tab ngoài bảng IA
— ghi ở mục 7 của báo cáo. Bốn việc cần trình duyệt hoặc máy thật vẫn
chờ người kiểm, ghi ở mục 6 của báo cáo.
