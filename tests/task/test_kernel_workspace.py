"""Unit tests for the unified kernel workspace builder."""

from pathlib import Path

import pytest

from cybergym.task.metadata import KERNEL_TASK_METADATA
from cybergym.task.workspace import TaskType, prepare_workspace
from cybergym.task.workspace.kernel import prepare_workspace_kernel

KERNELCTF_ENTRY = "kernelctf/CVE-2023-3776_lts"
SYZBOT_ENTRY = "syzbot/01523a0ae5600aef5895"


@pytest.fixture
def kernelctf_task_id() -> str:
    return KERNEL_TASK_METADATA[f"kernel:{KERNELCTF_ENTRY}"].task_id


@pytest.fixture
def syzbot_task_id() -> str:
    return KERNEL_TASK_METADATA[f"kernel:{SYZBOT_ENTRY}"].task_id


def _prepare(tmp_path: Path, task_id: str, **overrides) -> str:
    kwargs = dict(
        task_id=task_id,
        workspace_dir=tmp_path,
        controller_url="http://ctrl",
        agent_id="aid",
        agent_token="tok",
    )
    kwargs.update(overrides)
    return prepare_workspace_kernel(**kwargs)


class TestKernelctfSubset:
    def test_creates_readme_and_run_vm(self, tmp_path, kernelctf_task_id):
        _prepare(tmp_path, kernelctf_task_id)
        assert (tmp_path / "README.md").is_file()
        assert (tmp_path / "run_vm.sh").is_file()
        assert (tmp_path / "run_vm.sh").stat().st_mode & 0o111  # executable

    def test_copies_vulnerability_by_default_without_patch(
        self, tmp_path, kernelctf_task_id
    ):
        # The vulnerability doc is exposed by default; the patch is opt-in
        # (include_patch defaults to False).
        _prepare(tmp_path, kernelctf_task_id)
        assert (tmp_path / "vulnerability.md").is_file()
        assert not (tmp_path / "patch.diff").exists()

    def test_includes_patch_when_flag_set(self, tmp_path, kernelctf_task_id):
        _prepare(tmp_path, kernelctf_task_id, include_patch=True)
        assert (tmp_path / "patch.diff").is_file()

    def test_skips_pov_unless_include_pov(self, tmp_path, kernelctf_task_id):
        _prepare(tmp_path, kernelctf_task_id, include_pov=False)
        assert not (tmp_path / "pov").exists()

    def test_includes_pov_when_flag_set(self, tmp_path, kernelctf_task_id):
        _prepare(tmp_path, kernelctf_task_id, include_pov=True)
        assert (tmp_path / "pov").is_dir()

    def test_includes_exploit_doc_when_flag_set(self, tmp_path, kernelctf_task_id):
        _prepare(tmp_path, kernelctf_task_id, include_exploit_doc=True)
        assert (tmp_path / "exploit.md").is_file()

    def test_skips_vulnerability_when_flag_false(self, tmp_path, kernelctf_task_id):
        _prepare(tmp_path, kernelctf_task_id, include_vulnerability_doc=False)
        assert not (tmp_path / "vulnerability.md").exists()

    def test_skips_patch_when_flag_false(self, tmp_path, kernelctf_task_id):
        _prepare(tmp_path, kernelctf_task_id, include_patch=False)
        assert not (tmp_path / "patch.diff").exists()

    def test_description_uses_patch_commit_title(self, tmp_path, kernelctf_task_id):
        readme = _prepare(tmp_path, kernelctf_task_id)
        # Known patch commit title for CVE-2023-3776_lts
        assert "net/sched: cls_fw" in readme
        # Release id and CVE must NOT leak into the README
        assert "lts-6.1.36" not in readme
        assert "CVE-2023-3776" not in readme

    def test_run_vm_has_hostname(self, tmp_path, kernelctf_task_id):
        _prepare(tmp_path, kernelctf_task_id)
        run_vm = (tmp_path / "run_vm.sh").read_text()
        assert "hostname=" in run_vm

    def test_default_capabilities_from_metadata(self, tmp_path, kernelctf_task_id):
        readme = _prepare(tmp_path, kernelctf_task_id)
        # CVE-2023-3776_lts has userns capability in raw_metadata
        assert "userns" in readme

    def test_defense_capabilities_override(self, tmp_path, kernelctf_task_id):
        _prepare(
            tmp_path,
            kernelctf_task_id,
            defense_capabilities=["nokaslr", "nosmep"],
        )
        run_vm = (tmp_path / "run_vm.sh").read_text()
        assert "NOKASLR=1" in run_vm
        assert "NOSMEP=1" in run_vm
        # userns wasn't requested, so USERNS=0
        assert "USERNS=0" in run_vm

    def test_empty_defense_capabilities(self, tmp_path, kernelctf_task_id):
        _prepare(tmp_path, kernelctf_task_id, defense_capabilities=[])
        run_vm = (tmp_path / "run_vm.sh").read_text()
        assert "NOKASLR=0" in run_vm
        assert "USERNS=0" in run_vm


class TestSyzbotSubset:
    def test_creates_readme_and_run_vm(self, tmp_path, syzbot_task_id):
        _prepare(tmp_path, syzbot_task_id)
        assert (tmp_path / "README.md").is_file()
        assert (tmp_path / "run_vm.sh").is_file()

    def test_includes_patch_when_flag_set(self, tmp_path, syzbot_task_id):
        # include_patch defaults to False, so request it explicitly.
        _prepare(tmp_path, syzbot_task_id, include_patch=True)
        # syzbot/01523a0ae5600aef5895 has a single fix-commit patch file;
        # it's copied by basename into the workspace root.
        patches = sorted(tmp_path.glob("*.patch"))
        assert patches, f"no .patch file copied into {tmp_path}"

    def test_skips_patch_by_default(self, tmp_path, syzbot_task_id):
        _prepare(tmp_path, syzbot_task_id)
        assert not sorted(tmp_path.glob("*.patch"))

    def test_copies_vulnerability_doc_in_syzbot(self, tmp_path, syzbot_task_id):
        # syzbot metadata historically has an empty files.vulnerability_doc
        # list, but docs/vulnerability.md is exposed when it exists on disk.
        _prepare(tmp_path, syzbot_task_id)
        assert (tmp_path / "vulnerability.md").is_file()

    def test_description_uses_patch_commit_title(self, tmp_path, syzbot_task_id):
        readme = _prepare(tmp_path, syzbot_task_id)
        # Known patch_commit_title for syzbot/01523a0ae5600aef5895;
        # the raw syzbot bug title must not leak into the README.
        assert "comedi: fix race between polling and detaching" in readme
        assert "io_poll_remove_entries" not in readme

    def test_run_vm_has_hostname(self, tmp_path, syzbot_task_id):
        _prepare(tmp_path, syzbot_task_id)
        run_vm = (tmp_path / "run_vm.sh").read_text()
        assert "hostname=" in run_vm

    def test_skips_pov_unless_include_pov(self, tmp_path, syzbot_task_id):
        _prepare(tmp_path, syzbot_task_id, include_pov=False)
        assert not (tmp_path / "pov").exists()

    def test_includes_pov_when_flag_set(self, tmp_path, syzbot_task_id):
        readme = _prepare(tmp_path, syzbot_task_id, include_pov=True)
        assert (tmp_path / "pov").is_dir()
        assert "vulnerability.md` is the vulnerability description" in readme
        assert "PoV/crash reproducer artifacts are under `pov/`" in readme


class TestDataDrivenCopy:
    def _with_files(self, monkeypatch, **file_overrides):
        """Register a synthetic kernel task derived from KERNELCTF_ENTRY with
        its ``files`` field overridden, and return its task_id. entry_name is
        preserved so the on-disk task data dir still resolves."""
        base = KERNEL_TASK_METADATA[f"kernel:{KERNELCTF_ENTRY}"]
        synthetic = base.model_copy(
            update={"files": base.files.model_copy(update=file_overrides)}
        )
        monkeypatch.setitem(KERNEL_TASK_METADATA, synthetic.task_id, synthetic)
        return synthetic.task_id

    def test_empty_files_list_copies_nothing(self, tmp_path, monkeypatch):
        """An entry whose files.pov is empty should not produce a pov/ dir
        even when include_pov=True."""
        task_id = self._with_files(monkeypatch, pov=[])
        _prepare(tmp_path, task_id, include_pov=True)
        assert not (tmp_path / "pov").exists()

    def test_missing_source_path_is_non_fatal(self, tmp_path, monkeypatch):
        """If a listed file doesn't exist on disk, the builder logs and
        continues without raising."""
        task_id = self._with_files(monkeypatch, exploit=["exploit/does_not_exist"])
        _prepare(tmp_path, task_id, include_exploit=True)
        assert (tmp_path / "README.md").is_file()
        assert not (tmp_path / "does_not_exist").exists()


class TestRegistryDispatch:
    def test_dispatch_via_task_type(self, tmp_path, kernelctf_task_id):
        prepare_workspace(
            TaskType.KERNEL_EXPLOITATION,
            task_id=kernelctf_task_id,
            workspace_dir=tmp_path,
            controller_url="http://ctrl",
            agent_id="aid",
            agent_token="tok",
        )
        assert (tmp_path / "README.md").is_file()
