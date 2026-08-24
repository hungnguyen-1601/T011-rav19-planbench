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
    """Static files, plus the shell for a deep link into a dynamic route."""

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

    async def get_response(self, path: str, scope: Scope):
        """Serve the file, or the shell for a deep link into a record.

        A miss arrives here in **two** shapes, and handling only one is
        how this was wrong the first time. Without a `404.html` in the
        export, `StaticFiles` raises. With one — and `next export`
        writes one — it *returns* that page with status 404 instead, so
        the exception branch never fires and every deep link answered
        with the not-found page. Both shapes get the same treatment.
        """
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            shell = self._shell_for(path)
            if shell is None:
                raise
            return await super().get_response(shell, scope)

        if response.status_code == 404:
            shell = self._shell_for(path)
            if shell is not None:
                return await super().get_response(shell, scope)
        return response


__all__ = ["DYNAMIC_ROUTES", "SENTINEL", "SpaStaticFiles"]
