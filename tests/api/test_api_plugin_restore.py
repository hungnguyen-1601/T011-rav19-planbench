"""A bundle in the database with nothing on disk.

This is what an upgrade does. `install_root` keys a bundle's directory
on the archive's checksum; it used to key on the declared version, so
every bundle imported before that change sits under a path this build
never looks at. The row is intact, the archive is intact, and the two
have simply stopped agreeing about where the code lives.

Before this was handled, the catalogue offered such a bundle anyway —
the manifest is in the row, so building a stack from it succeeds — and
the failure waited for a sweep, where every episode died with
``ModuleNotFoundError`` naming a package the reader had never heard of.
Measured on a real machine, not imagined.

Two acceptable outcomes, and one that is not: unpack it again, or leave
it out of the catalogue and say so. Offering it is the one that is not.
"""

from __future__ import annotations

import shutil

from conftest import ADMIN, auth_headers
from fastapi.testclient import TestClient

# The bundle builder and the upload call already exist, and a second
# copy of either would be a second thing to keep in step with the
# manifest schema.
from test_api_plugin_import import import_bundle

from planbench_api.plugin_runtime import INSTALLED_MARKER, install_root
from planbench_api.plugin_service import sync_catalogue


def _import_plugin(client: TestClient) -> dict[str, str]:
    """Import the example bundle; returns the admin headers used."""
    admin = auth_headers(client, ADMIN)
    response = import_bundle(client, admin)
    assert response.status_code == 201, response.text
    return admin


class TestABundleWhoseDirectoryMoved:
    def test_it_is_unpacked_again_rather_than_offered_empty(
        self, client: TestClient, app, tmp_path
    ) -> None:
        """The self-healing half: the archive is still stored, so use it."""
        _import_plugin(client)
        bundles = app.state.repos.plugin_bundles
        root = app.state.plugin_install_root
        record = bundles.list()[0]
        directory = install_root(root, record)
        assert (directory / INSTALLED_MARKER).is_file()

        # Exactly what the upgrade left behind: a row pointing at a
        # directory that is not there.
        shutil.rmtree(directory)

        registered = sync_catalogue(bundles, root, app.state.model_storage)

        assert (directory / INSTALLED_MARKER).is_file(), "the bundle was not restored"
        assert registered, "a restored bundle should be offerable again"

    def test_without_storage_it_is_left_out_of_the_catalogue(self, client: TestClient, app) -> None:
        """The honest half. An algorithm missing from the picker sends
        somebody to look; one that fails per-episode sends them to a
        traceback."""
        _import_plugin(client)
        bundles = app.state.repos.plugin_bundles
        root = app.state.plugin_install_root
        shutil.rmtree(install_root(root, bundles.list()[0]))

        registered = sync_catalogue(bundles, root, None)

        assert registered == []

    def test_an_archive_that_no_longer_hashes_is_refused_not_unpacked(
        self, client: TestClient, app
    ) -> None:
        """`install_bundle` verifies before it writes, and the refusal has
        to leave the bundle unoffered rather than take the catalogue down
        with it."""
        _import_plugin(client)
        bundles = app.state.repos.plugin_bundles
        root = app.state.plugin_install_root
        record = bundles.list()[0]
        shutil.rmtree(install_root(root, record))

        class Tampered:
            def open(self, key: str) -> bytes:
                return b"not the archive that was imported"

        registered = sync_catalogue(bundles, root, Tampered())

        assert registered == []
        assert not (install_root(root, record) / INSTALLED_MARKER).exists()

    def test_a_bundle_already_on_disk_is_not_unpacked_again(self, client: TestClient, app) -> None:
        """Restoring is for the case that needs it. Re-extracting eighty
        megabytes on every startup would be a cost paid by every launch
        to fix a state almost none of them are in."""
        _import_plugin(client)
        bundles = app.state.repos.plugin_bundles
        root = app.state.plugin_install_root

        opened: list[str] = []

        class Counting:
            def __init__(self, inner) -> None:
                self._inner = inner

            def open(self, key: str) -> bytes:
                opened.append(key)
                return self._inner.open(key)

        sync_catalogue(bundles, root, Counting(app.state.model_storage))

        assert opened == [], "an installed bundle should not be read again"
