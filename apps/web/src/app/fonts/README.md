# Fonts, and where they came from

Seven `.woff2` files live in this directory rather than being fetched at
build time. Two reasons, and only the second is about speed.

**`next/font/google` downloads at build.** It self-hosts afterwards, so
the *runtime* is offline-safe either way — but `next build` itself needs
the network, and a CSS fallback cannot rescue a build that never
produced any CSS. Runtime-offline and build-offline are different
problems, and only committing the binaries solves the second. A demo
build has to be reproducible on a machine with no network.

**A binary with no provenance is a file nobody dares touch.** Six months
from now there is no way to tell which release this is, whether it
carries the Vietnamese glyphs, or whether somebody swapped one. Hence
the manifest below: pinned commit, upstream path, SHA-256, licence.

Pinned to a **commit**, not a branch or a tag — a branch moves under you
and a tag can be repointed.

## Be Vietnam Pro

Chosen because it is drawn for Vietnamese: stacked diacritics (`ế ồ ữ`)
do not collide at 12px, which is the size most of this UI runs at.

    Source:  https://github.com/bettergui/BeVietnamPro
    Commit:  804e62d81abbbcdcce5686069c69b41b8c245192
    Path:    fonts/webfonts/
    Licence: OFL-1.1 — see OFL-BeVietnamPro.txt

| Local file | Weight | SHA-256 |
|---|---|---|
| `BeVietnamPro-Regular.woff2`  | 400 | `907ebfa4a4bd967cdcb313b2889655ff9fb90d5fd4f193723aa99142d14a1652` |
| `BeVietnamPro-Medium.woff2`   | 500 | `15a399b6a57023c665fa8aca7f4691d36c512b17cc36f74bd9dc077487ac9ffc` |
| `BeVietnamPro-SemiBold.woff2` | 600 | `91329e727900425300269d9402c32e9e020943783fc0b9457f0b7419bef90dbf` |
| `BeVietnamPro-Bold.woff2`     | 700 | `32eb3a183490d280351f9676cc0b8e1725d95090988db57503dc83879b5fe602` |

## JetBrains Mono

    Source:  https://github.com/JetBrains/JetBrainsMono
    Release: v2.304
    Commit:  cd5227bd1f61dff3bbd6c814ceaf7ffd95e947d9
    Path:    fonts/webfonts/
    Licence: OFL-1.1 — see OFL-JetBrainsMono.txt

| Local file | Weight | SHA-256 |
|---|---|---|
| `JetBrainsMono-Regular.woff2`  | 400 | `a9cb1cd82332b23a47e3a1239d25d13c86d16c4220695e34b243effa999f45f2` |
| `JetBrainsMono-Medium.woff2`   | 500 | `086c48dfbea9ddaff1320f7e09399b8e2924e88ce67453721255db3bdbb5a353` |
| `JetBrainsMono-SemiBold.woff2` | 600 | `918edad542a1da608fd2ba8daebaff9ac802309103fe760eed465b8b4e47faf1` |

## Checking them

    python -c "import hashlib,pathlib;[print(f'{p.name:32}{hashlib.sha256(p.read_bytes()).hexdigest()}') for p in sorted(pathlib.Path('.').glob('*.woff2'))]"

Coverage was read from each file's `cmap` when they landed, not assumed:
all seven carry `ế ồ ữ ự ẫ ằ ợ ỗ ộ đ Đ` and `± ≤`. A `latin`-only subset
would build green, render, and drop every Vietnamese diacritic back to
the system font mid-sentence — which is why the check is on the glyph
table and not on the file name.

Only the weights the stylesheet asks for are here. Italics and the other
five weights are not, because an unused 40 KB is 40 KB nobody notices is
unused.
