"""Serving the exported web UI from the API process.

Only the desktop build uses this. Every other deployment runs the web UI
as its own container, and `web_dir` is empty there.

The whole of the problem is deep links. A static export writes one HTML
file per route it knows the name of, and three routes here are named
after a record — `/decisions/<id>`, `/maps/<id>`, `/scenarios/<id>` —
whose ids do not exist at build time and never will, because they are
created by the person using the app. Client-side navigation into those
pages works regardless: the router already has the bundle. Reloading
while standing on one does not, and neither does a link somebody pasted,
because the browser asks the server for a file that was never written.

The export therefore writes one shell per dynamic route under the
sentinel id `_`, and this class serves that shell for any id. The page
reads the real id from the URL once it hydrates. What is deliberately
*not* here is a catch-all that returns `index.html` for every miss: that
turns a page missing from the export — a real build failure — into a
blank screen that looks like a routing quirk, and the first person to
hit it would be a user rather than the build.

There is a second, plainer half to the same problem, and it went unseen
for longer because nothing in the app depended on it. A static export
writes `login.html`; the URL a person types, bookmarks or reloads is
`/login`. No file is named `login`, so every static page in the app was
reachable only by client-side navigation — the desktop app opens at `/`
and the router never asks the server again, so nobody hit it. A reload
or a pasted link did, and got the not-found page. `_page_for` answers
that: an extensionless path is tried as `<path>.html` before anything
else. It is the general fix, not a guide-shaped one — `/login` and
`/decisions` were already broken the same way.
"""

from __future__ import annotations

from collections.abc import Iterable

# Starlette's, not FastAPI's. `StaticFiles` raises the Starlette
# exception, and FastAPI's is a *subclass* of it — catching the
# subclass here compiles, reads correctly, and never fires.
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

#: Routes whose second segment is a record id rather than a page name.
#: Adding a dynamic route to the web app means adding it here too —
#: pinned by test_a_deep_link_into_a_dynamic_route_serves_its_shell.
DYNAMIC_ROUTES: tuple[str, ...] = ("decisions", "maps", "scenarios")

#: The id the export builds each shell under. Matches the value
#: `generateStaticParams` returns in the three pages.
SENTINEL = "_"


class SpaStaticFiles(StaticFiles):
    """Static files, plus the two things a static export cannot answer.

    A page by the name it is reached under (`/login` for `login.html`),
    and the shell for a deep link into a record (`/decisions/<id>`).
    """

    def __init__(self, *args, dynamic_routes: Iterable[str] = DYNAMIC_ROUTES, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._dynamic = frozenset(dynamic_routes)

    def _shell_for(self, path: str) -> str | None:
        """The shell that answers ``path``, or None to let the 404 stand.

        Two segments, the first a known dynamic route, and the second
        without a file extension. The extension check is what keeps a
        missing image under `/maps/` from being answered with a page:
        an `<img>` that renders HTML is a harder thing to diagnose than
        one that reports 404.
        """
        segments = [part for part in path.replace("\\", "/").split("/") if part]
        if len(segments) != 2:
            return None
        route, tail = segments
        if route not in self._dynamic or "." in tail:
            return None
        return f"{route}/{SENTINEL}.html"

    def _page_for(self, path: str) -> str | None:
        """The exported page ``path`` names, or None.

        Only the *last* segment is inspected: a path whose tail carries
        an extension is asking for a file, and answering a missing
        `.png` with a page is the same diagnosis problem `_shell_for`
        avoids. The empty path is the root, which `html=True` already
        answers with `index.html`.
        """
        if not path or path.endswith("/"):
            return None
        tail = path.replace("\\", "/").rsplit("/", 1)[-1]
        if not tail or "." in tail:
            return None
        return f"{path}.html"

    async def _serve(self, path: str, scope: Scope):
        """The response for ``path``, or None when the export lacks it.

        A miss arrives in **two** shapes, and handling only one is how
        this was wrong the first time. Without a `404.html` in the
        export, `StaticFiles` raises. With one — and `next export`
        writes one — it *returns* that page with status 404 instead, so
        an exception-only branch never fires and every deep link is
        answered with the not-found page. Both shapes collapse to None
        here, so each caller states its fallback once.

        Anything that is not a 404 is re-raised: a 405 on a page is a
        different fact and must not be read as "no such file".
        """
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return None
        return None if response.status_code == 404 else response

    async def get_response(self, path: str, scope: Scope):
        """Serve the file, the page it names, or the shell for a record.

        **Order matters, and this is the only place it is stated.** The
        page rule runs before the shell rule, so a real exported page
        always wins over a shell. The reverse order would answer
        `/decisions/<id>` correctly by luck and hide a missing page
        behind a shell that renders blank.

        A path that reaches neither is a 404 on purpose — the last call
        re-runs the original miss so the not-found page, not a guess,
        is what a wrong URL gets.
        """
        response = await self._serve(path, scope)
        if response is not None:
            return response

        for candidate in (self._page_for(path), self._shell_for(path)):
            if candidate is None:
                continue
            found = await self._serve(candidate, scope)
            if found is not None:
                return found

        return await super().get_response(path, scope)


__all__ = ["DYNAMIC_ROUTES", "SENTINEL", "SpaStaticFiles"]
