"""Unit tests for V8TaskHandler and V8 metadata."""

from unittest.mock import MagicMock, patch

import docker.errors
import pytest

from cybergym.server.task_handler import V8TaskHandler, get_handler
from cybergym.task.metadata import V8_TASK_METADATA, V8TaskMetadata

# ── Fixtures ──


@pytest.fixture
def handler():
    return V8TaskHandler()


@pytest.fixture
def mock_v8_meta():
    """Mock V8_TASK_METADATA with test entries.

    - pwn_meta: non-escape task with a no-sandbox variant.
    - sbx_meta: sandbox-escape task, no no-sandbox variant.
    """
    pwn_meta = V8TaskMetadata(
        task_id="v8:abc123pwncol",
        entry_name="pwncollege/cve-2020-6418-real",
        image="cybergym/v8:cve-2020-6418-real",
        image_no_sandbox="cybergym/v8:cve-2020-6418-real-nosandbox",
        revision="abc123",
        has_allow_natives_syntax=False,
        v8_sandbox_enabled=False,
        maglev_enabled=False,
        is_sandbox_escape=False,
    )
    sbx_meta = V8TaskMetadata(
        task_id="v8:def456sbxbrk",
        entry_name="sbxbrk/385775375",
        image="cybergym/v8:sbxbrk-385775375",
        image_no_sandbox=None,
        revision="def456",
        has_allow_natives_syntax=False,
        v8_sandbox_enabled=True,
        maglev_enabled=False,
        is_sandbox_escape=True,
    )
    mock = {
        "v8:abc123pwncol": pwn_meta,
        "v8:pwncollege/cve-2020-6418-real": pwn_meta,
        "v8:def456sbxbrk": sbx_meta,
        "v8:sbxbrk/385775375": sbx_meta,
    }
    with patch("cybergym.server.task_handler.V8_TASK_METADATA", mock):
        yield mock


@pytest.fixture
def mock_docker():
    """Mock docker client and subprocess for container operations."""
    mock_container = MagicMock()
    mock_container.id = "container_v8_123"
    mock_container.status = "running"
    mock_container.attrs = {
        "NetworkSettings": {"Networks": {"bridge": {"IPAddress": "172.17.0.3"}}}
    }

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.get.return_value = mock_container

    with (
        patch(
            "cybergym.server.task_handler.get_docker_client", return_value=mock_client
        ),
        patch("cybergym.server.task_handler.docker") as mock_docker_mod,
        patch("cybergym.utils.subprocess"),
    ):
        mock_docker_mod.errors = docker.errors
        mock_docker_mod.from_env.return_value = mock_client
        yield mock_client


# ── Tests: dispatch ──


class TestV8Dispatch:
    def test_get_handler_v8_prefix(self):
        handler = get_handler("v8:abc123")
        assert isinstance(handler, V8TaskHandler)

    def test_get_handler_non_v8_prefix(self):
        handler = get_handler("arvo:12345/asan")
        assert not isinstance(handler, V8TaskHandler)


# ── Tests: resolve_task ──


class TestResolveTask:
    def test_resolve_pwncollege_task(self, handler, mock_v8_meta):
        task_id, image = handler.resolve_task("v8:abc123pwncol")
        assert task_id == "v8:abc123pwncol"
        assert image == "cybergym/v8:cve-2020-6418-real"

    def test_resolve_sbxbrk_task(self, handler, mock_v8_meta):
        task_id, image = handler.resolve_task("v8:def456sbxbrk")
        assert task_id == "v8:def456sbxbrk"
        assert image == "cybergym/v8:sbxbrk-385775375"

    def test_resolve_by_alias(self, handler, mock_v8_meta):
        task_id, image = handler.resolve_task("v8:pwncollege/cve-2020-6418-real")
        assert task_id == "v8:pwncollege/cve-2020-6418-real"
        assert image == "cybergym/v8:cve-2020-6418-real"

    def test_resolve_unknown_task(self, handler, mock_v8_meta):
        with pytest.raises(KeyError):
            handler.resolve_task("v8:nonexistent")


# ── Tests: launch ──


class TestLaunch:
    def test_launch_pwncollege(self, handler, mock_v8_meta, mock_docker):
        ip, port, cid = handler.launch("v8:abc123pwncol", "flag{test}")
        assert ip == "172.17.0.3"
        assert port == 1337
        assert cid == "container_v8_123"

        call_kwargs = mock_docker.containers.run.call_args[1]
        assert call_kwargs["image"] == "cybergym/v8:cve-2020-6418-real"
        assert call_kwargs["detach"] is True

    def test_launch_sbxbrk(self, handler, mock_v8_meta, mock_docker):
        ip, port, cid = handler.launch("v8:def456sbxbrk", "flag{test}")
        assert ip == "172.17.0.3"
        assert port == 1337

        call_kwargs = mock_docker.containers.run.call_args[1]
        assert call_kwargs["image"] == "cybergym/v8:sbxbrk-385775375"

    def test_launch_exec_start_script(self, handler, mock_v8_meta, mock_docker):
        container = mock_docker.containers.run.return_value
        handler.launch("v8:abc123pwncol", "flag{test}")
        container.exec_run.assert_called_with(["/data/v8/start.sh"], detach=True)

    def test_launch_mounts_server_dir(self, handler, mock_v8_meta, mock_docker):
        handler.launch("v8:abc123pwncol", "flag{test}")
        call_kwargs = mock_docker.containers.run.call_args[1]
        volumes = call_kwargs["volumes"]
        binds = [v["bind"] for v in volumes.values()]
        assert "/data" in binds


# ── Tests: no-sandbox variant ──


class TestNoSandbox:
    def test_parse_no_sandbox_suffix(self, handler):
        assert handler._parse_task_info("v8:abc123pwncol") == (
            "v8:abc123pwncol",
            False,
        )
        assert handler._parse_task_info("v8:abc123pwncol/nosandbox") == (
            "v8:abc123pwncol",
            True,
        )

    def test_parse_alias_no_sandbox_suffix(self, handler):
        # entry_name aliases contain a /, so only the trailing /nosandbox
        # segment should be stripped.
        assert handler._parse_task_info(
            "v8:pwncollege/cve-2020-6418-real/nosandbox"
        ) == ("v8:pwncollege/cve-2020-6418-real", True)

    def test_resolve_no_sandbox_variant(self, handler, mock_v8_meta):
        task_id, image = handler.resolve_task("v8:abc123pwncol/nosandbox")
        assert task_id == "v8:abc123pwncol"
        assert image == "cybergym/v8:cve-2020-6418-real-nosandbox"

    def test_resolve_no_sandbox_missing_variant(self, handler, mock_v8_meta):
        # sbxbrk task has image_no_sandbox=None (sandbox-escape task).
        with pytest.raises(ValueError, match="no-sandbox"):
            handler.resolve_task("v8:def456sbxbrk/nosandbox")

    def test_launch_no_sandbox_variant(self, handler, mock_v8_meta, mock_docker):
        handler.launch("v8:abc123pwncol/nosandbox", "flag{test}")
        call_kwargs = mock_docker.containers.run.call_args[1]
        assert call_kwargs["image"] == "cybergym/v8:cve-2020-6418-real-nosandbox"


# ── Tests: metadata ──


class TestV8Metadata:
    def test_real_metadata_loads(self):
        """Verify actual v8_metadata.json loads correctly."""
        assert len(V8_TASK_METADATA) > 0

    def test_entry_name_format(self):
        """All entries should have source/name format."""
        seen = set()
        for meta in V8_TASK_METADATA.values():
            if id(meta) in seen:
                continue
            seen.add(id(meta))
            assert "/" in meta.entry_name, f"{meta.task_id} has no / in entry_name"
            source = meta.entry_name.split("/")[0]
            assert source in (
                "pwncollege",
                "sbxbrk",
                "clusterfuzz",
                "human",
            ), f"{meta.task_id} has unknown source: {source}"

    def test_hashed_task_id(self):
        """Task IDs should be hashed (no CVE or issue IDs visible)."""
        seen = set()
        for meta in V8_TASK_METADATA.values():
            if id(meta) in seen:
                continue
            seen.add(id(meta))
            assert meta.task_id.startswith("v8:")
            suffix = meta.task_id.removeprefix("v8:")
            assert len(suffix) == 12, f"{meta.task_id} hash is not 12 chars"
            assert all(c in "0123456789abcdef" for c in suffix), (
                f"{meta.task_id} has non-hex chars"
            )

    def test_dual_indexing(self):
        """Each task should be reachable by both hashed ID and alias."""
        seen = set()
        for meta in V8_TASK_METADATA.values():
            if id(meta) in seen:
                continue
            seen.add(id(meta))
            assert meta.task_id in V8_TASK_METADATA
            alias = f"v8:{meta.entry_name}"
            assert alias in V8_TASK_METADATA
            assert V8_TASK_METADATA[meta.task_id] is V8_TASK_METADATA[alias]

    def test_sbxbrk_has_sandbox_enabled(self):
        """All sbxbrk tasks should have v8_sandbox_enabled=True."""
        seen = set()
        for meta in V8_TASK_METADATA.values():
            if id(meta) in seen:
                continue
            seen.add(id(meta))
            if meta.entry_name.startswith("sbxbrk/"):
                assert meta.v8_sandbox_enabled, (
                    f"{meta.entry_name} should have sandbox enabled"
                )

    def test_image_no_sandbox_matches_is_sandbox_escape(self):
        """image_no_sandbox must be populated iff the task is not a
        sandbox-escape challenge.

        For tasks whose V8 build predates the sandbox, ``image`` is None and
        ``image_no_sandbox`` is the only build — those tasks are exempt from
        the ``image_no_sandbox == f"{image}-nosandbox"`` URL convention.
        """
        seen = set()
        for meta in V8_TASK_METADATA.values():
            if id(meta) in seen:
                continue
            seen.add(id(meta))
            if meta.is_sandbox_escape:
                assert meta.image_no_sandbox is None, (
                    f"{meta.task_id} is_sandbox_escape=True but has "
                    f"image_no_sandbox={meta.image_no_sandbox!r}"
                )
                continue
            assert meta.image_no_sandbox is not None, (
                f"{meta.task_id} is not a sandbox-escape task but has "
                f"image_no_sandbox=None"
            )
            if meta.image is None:
                # Pre-sandbox V8 build: only image_no_sandbox is populated.
                continue
            # Convention: the nosandbox variant inserts "-nosandbox" before the
            # trailing "-buildable" tag, e.g.
            #   cybergym/v8:clusterfuzz-323698305-buildable
            #   cybergym/v8:clusterfuzz-323698305-nosandbox-buildable
            assert meta.image.endswith("-buildable"), (
                f"{meta.task_id} image={meta.image!r} does not end with "
                f"'-buildable'"
            )
            expected = meta.image[: -len("-buildable")] + "-nosandbox-buildable"
            assert meta.image_no_sandbox == expected, (
                f"{meta.task_id} image_no_sandbox={meta.image_no_sandbox!r} "
                f"does not match {expected}"
            )
