"""Unit tests for KernelTaskHandler."""

from unittest.mock import MagicMock, patch

import docker.errors
import pytest

from cybergym.server.task_handler import KernelTaskHandler, get_handler
from cybergym.task.metadata import (
    KernelTaskFiles,
    KernelTaskMetadata,
    bitmap_to_capabilities,
    bitmap_to_env,
    capabilities_to_bitmap,
)

TEST_TASK_ID = "kernel:abc123def456"
TEST_TASK_INFO = f"{TEST_TASK_ID}/0"


@pytest.fixture
def handler():
    return KernelTaskHandler()


@pytest.fixture
def mock_kernel_meta():
    """Mock KERNEL_TASK_METADATA with a test kernelctf entry."""
    meta = KernelTaskMetadata(
        task_id=TEST_TASK_ID,
        entry_name="kernelctf/CVE-2024-1085_lts",
        image_name="cybergym/kernelctf-target:lts-6.1.70",
        patch_commits=["deadbeef"],
        files=KernelTaskFiles(
            vulnerability_doc=["docs/vulnerability.md"],
            exploit_doc=["docs/exploit.md"],
            pov=["pov/"],
            patch=["patch.diff"],
        ),
        raw_metadata={
            "release_id": "lts-6.1.70",
            "original_capabilities": ["userns"],
        },
    )
    mock = {TEST_TASK_ID: meta}
    with patch("cybergym.server.task_handler.KERNEL_TASK_METADATA", mock):
        yield mock


@pytest.fixture
def mock_docker():
    """Mock docker client and subprocess for container operations."""
    mock_container = MagicMock()
    mock_container.id = "container_kernel_123"
    mock_container.status = "running"
    mock_container.attrs = {
        "NetworkSettings": {"Networks": {"bridge": {"IPAddress": "172.17.0.5"}}}
    }

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.get.return_value = mock_container

    with (
        patch(
            "cybergym.server.task_handler.get_docker_client", return_value=mock_client
        ),
        patch("cybergym.server.task_handler.docker") as mock_docker_mod,
        patch("cybergym.utils.subprocess") as _mock_subprocess,
        patch("cybergym.server.task_handler.Path") as mock_path,
    ):
        mock_docker_mod.errors = docker.errors
        mock_docker_mod.from_env.return_value = mock_client
        # /dev/kvm exists
        mock_path.return_value.exists.return_value = True
        mock_path.side_effect = lambda p: (
            MagicMock(exists=lambda: True, absolute=lambda: p)
            if isinstance(p, str)
            else MagicMock(exists=lambda: True)
        )
        yield mock_client


# ── Tests: dispatch ──


class TestKernelDispatch:
    def test_get_handler_kernel_prefix(self):
        handler = get_handler(TEST_TASK_INFO)
        assert isinstance(handler, KernelTaskHandler)

    def test_get_handler_other_prefix(self):
        handler = get_handler("arvo:12345/asan")
        assert not isinstance(handler, KernelTaskHandler)

    def test_get_handler_legacy_kernelctf_prefix_does_not_match(self):
        # The old "kernelctf:" prefix no longer dispatches here.
        handler = get_handler("kernelctf:abc123/lts-6.1.70")
        assert not isinstance(handler, KernelTaskHandler)


# ── Tests: _parse_task_info ──


class TestParseTaskInfo:
    def test_task_id_only(self, handler):
        task_id, bitmap = handler._parse_task_info(TEST_TASK_ID)
        assert task_id == TEST_TASK_ID
        assert bitmap == 0

    def test_task_id_with_bitmap(self, handler):
        task_id, bitmap = handler._parse_task_info(f"{TEST_TASK_ID}/9")
        assert task_id == TEST_TASK_ID
        assert bitmap == 9  # userns (8) + nokaslr (1)

    def test_zero_bitmap(self, handler):
        task_id, bitmap = handler._parse_task_info(f"{TEST_TASK_ID}/0")
        assert bitmap == 0


# ── Tests: resolve_task ──


class TestResolveTask:
    def test_resolve_known_task_returns_image_name(self, handler, mock_kernel_meta):
        task_id, image = handler.resolve_task(TEST_TASK_INFO)
        assert task_id == TEST_TASK_ID
        assert image == "cybergym/kernelctf-target:lts-6.1.70"

    def test_resolve_unknown_task(self, handler, mock_kernel_meta):
        with pytest.raises(KeyError, match="Unknown kernel task"):
            handler.resolve_task("kernel:unknown123/0")


# ── Tests: defense bitmap ──


class TestDefenseBitmap:
    def test_capabilities_to_bitmap_empty(self):
        assert capabilities_to_bitmap([]) == 0

    def test_capabilities_to_bitmap_single(self):
        assert capabilities_to_bitmap(["userns"]) == 0x08

    def test_capabilities_to_bitmap_multiple(self):
        bitmap = capabilities_to_bitmap(["nokaslr", "userns", "io_uring"])
        assert bitmap == 0x01 | 0x08 | 0x10  # 0x19

    def test_capabilities_to_bitmap_unknown(self):
        with pytest.raises(ValueError, match="Unknown capability"):
            capabilities_to_bitmap(["nonexistent"])

    def test_bitmap_to_capabilities_roundtrip(self):
        caps = ["nokaslr", "userns", "io_uring"]
        bitmap = capabilities_to_bitmap(caps)
        result = bitmap_to_capabilities(bitmap)
        assert sorted(result) == sorted(caps)

    def test_bitmap_to_capabilities_zero(self):
        assert bitmap_to_capabilities(0) == []

    def test_bitmap_to_env_default(self):
        env = bitmap_to_env(0)
        assert env["NOKASLR"] == "0"
        assert env["USERNS"] == "0"
        assert env["IO_URING"] == "0"
        assert env["NOSMEP"] == "0"
        assert env["NOSMAP"] == "0"
        assert env["HARDENING"] == "0"

    def test_bitmap_to_env_userns(self):
        env = bitmap_to_env(capabilities_to_bitmap(["userns"]))
        assert env["USERNS"] == "1"
        assert env["NOKASLR"] == "0"

    def test_bitmap_to_env_all(self):
        env = bitmap_to_env(0x3F)  # all 6 bits set
        for v in env.values():
            assert v == "1"


# ── Tests: launch ──


class TestLaunch:
    def test_launch_uses_image_from_metadata(
        self, handler, mock_kernel_meta, mock_docker
    ):
        ip, port, cid = handler.launch(TEST_TASK_INFO, "flag{test}")
        assert ip == "172.17.0.5"
        assert port == 1337
        assert cid == "container_kernel_123"

        assert mock_docker.containers.run.called
        call_kwargs = mock_docker.containers.run.call_args[1]
        assert call_kwargs["image"] == "cybergym/kernelctf-target:lts-6.1.70"
        assert call_kwargs["detach"] is True

        env = call_kwargs["environment"]
        assert env["PORT"] == "1337"
        assert "NOKASLR" in env
        assert "USERNS" in env

    def test_launch_syzbot_uses_image_from_metadata(self, handler, mock_docker):
        """Syzbot entries use the image tag baked with their extid."""
        meta = KernelTaskMetadata(
            task_id=TEST_TASK_ID,
            entry_name="syzbot/deadbeef01234567",
            image_name="cybergym/syzbot-target:deadbeef01234567",
            raw_metadata={"extid": "deadbeef01234567"},
        )
        with patch(
            "cybergym.server.task_handler.KERNEL_TASK_METADATA",
            {TEST_TASK_ID: meta},
        ):
            handler.launch(TEST_TASK_INFO, "flag{test}")

        call_kwargs = mock_docker.containers.run.call_args[1]
        assert call_kwargs["image"] == "cybergym/syzbot-target:deadbeef01234567"

    def test_launch_with_defense_bitmap(self, handler, mock_kernel_meta, mock_docker):
        # bitmap 9 = nokaslr (1) + userns (8)
        handler.launch(f"{TEST_TASK_ID}/9", "flag{test}")

        call_kwargs = mock_docker.containers.run.call_args[1]
        env = call_kwargs["environment"]
        assert env["NOKASLR"] == "1"
        assert env["USERNS"] == "1"
        assert env["IO_URING"] == "0"

    def test_launch_default_bitmap_all_defenses_on(
        self, handler, mock_kernel_meta, mock_docker
    ):
        handler.launch(TEST_TASK_INFO, "flag{test}")

        call_kwargs = mock_docker.containers.run.call_args[1]
        env = call_kwargs["environment"]
        assert env["NOKASLR"] == "0"
        assert env["USERNS"] == "0"
        assert env["IO_URING"] == "0"

    def test_launch_exec_start_script(self, handler, mock_kernel_meta, mock_docker):
        container = mock_docker.containers.run.return_value
        handler.launch(TEST_TASK_INFO, "flag{test}")

        container.exec_run.assert_called_with(["/scripts/start_qemu.sh"], detach=True)

    def test_launch_does_not_mount_kernel_or_images(
        self, handler, mock_kernel_meta, mock_docker
    ):
        """use_prepared is gone — images have data baked in, so no
        /kernel or /images mounts."""
        handler.launch(TEST_TASK_INFO, "flag{test}")

        call_kwargs = mock_docker.containers.run.call_args[1]
        volumes = call_kwargs["volumes"]
        bound_paths = {v["bind"] for v in volumes.values()}
        assert "/kernel" not in bound_paths
        assert "/images" not in bound_paths
        # /scripts is still mounted
        assert "/scripts" in bound_paths
