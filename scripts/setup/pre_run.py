"""Pre-run readiness check + service startup for cybergym evaluations.

Given a task list, verifies the host is ready to launch agents:
  - ASLR disabled (kernel.randomize_va_space == 0), or, with --hardened,
    ASLR enabled (kernel.randomize_va_space != 0)
  - Coredump pattern configured
  - Docker reachable + bridge IP resolvable
  - KVM available + accessible (only when kernel tasks are selected)
  - ubuntu/squid:latest image present
  - All required target images pulled
  - PoC data extracted to data/tasks/ for each task

If checks pass, starts the three supporting services in the background:
  - Firewall (cybergym.firewall) — the API-only run proxy, plus the allow-all
    install proxy when a selected task family has a non-empty install script
    (it installs deps during the pre-agent install phase behind that proxy)
  - Controller (cybergym.server)
  - LLM proxy (cybergym.llm_proxy)

Each service is started only if it is not already running — pre_run auto-detects
a live instance and reuses it instead of launching a duplicate. Pass the
matching --no-<service> flag to disable a service entirely.

Does NOT start the agent.

Usage:
  uv run scripts/setup/pre_run.py data/task_ids/ready.txt
  uv run scripts/setup/pre_run.py data/task_ids/ready.txt --no-llm-proxy
  uv run scripts/setup/pre_run.py data/task_ids/ready.txt --budget 10
  uv run scripts/setup/pre_run.py data/task_ids/ready.txt --hardened

--hardened switches to the strict/hardened profile: it requires ASLR enabled,
checks the hardened image variants (user exp.hardened, v8 strict), and prints
the matching run_agent.py flags (--user-mode exp.hardened --v8-mode strict
--kernel-defense strict).
"""

import argparse
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

import docker

from cybergym.evaluation.agents.helper import task_needs_install
from cybergym.firewall.proxy import INSTALL_PROXY_CONTAINER_NAME, PROXY_CONTAINER_NAME
from cybergym.task.metadata import KERNEL_TASK_METADATA, TASK_METADATA, V8_TASK_METADATA
from cybergym.task.workspace import TaskType

# Map task-id prefixes to their TaskType (for deciding which install scripts
# apply to the selected tasks).
_PREFIX_TO_TASK_TYPE = {
    "kernel:": TaskType.KERNEL_EXPLOITATION,
    "v8:": TaskType.V8_EXPLOITATION,
    "user:": TaskType.USER_EXPLOITATION,
}

COLOR_OK = "\033[32m"
COLOR_WARN = "\033[33m"
COLOR_ERR = "\033[31m"
COLOR_RESET = "\033[0m"


def ok(msg):
    print(f"  {COLOR_OK}OK{COLOR_RESET}   {msg}")


def warn(msg):
    print(f"  {COLOR_WARN}WARN{COLOR_RESET} {msg}")


def fail(msg):
    print(f"  {COLOR_ERR}FAIL{COLOR_RESET} {msg}")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_aslr(hardened: bool = False) -> bool:
    # Hardened profile expects defenses ON (ASLR enabled); the default profile
    # expects ASLR disabled for deterministic exploitation.
    print(f"[1/6] ASLR {'enabled' if hardened else 'disabled'}")
    try:
        val = subprocess.check_output(
            ["sysctl", "-n", "kernel.randomize_va_space"], text=True
        ).strip()
    except Exception as e:
        fail(f"could not read sysctl: {e}")
        return False
    if hardened:
        if val != "0":
            ok(f"kernel.randomize_va_space={val}")
            return True
        fail(
            "kernel.randomize_va_space=0 — hardened mode needs ASLR enabled; "
            "run: sudo sysctl -w kernel.randomize_va_space=2"
        )
        return False
    if val == "0":
        ok("kernel.randomize_va_space=0")
        return True
    fail(
        f"kernel.randomize_va_space={val} — run: sudo sysctl -w kernel.randomize_va_space=0"
    )
    return False


def check_coredump() -> bool:
    print("[2/6] Coredump pattern")
    try:
        pattern = subprocess.check_output(
            ["sysctl", "-n", "kernel.core_pattern"], text=True
        ).strip()
    except Exception as e:
        warn(f"could not read core_pattern: {e}")
        return True
    if pattern.startswith("|"):
        warn(
            f"core_pattern is a pipe ({pattern}); "
            "coredumps won't be captured. Recommend: "
            "sudo sysctl -w kernel.core_pattern=core.%e.%p.%t"
        )
        return True
    ok(f"core_pattern={pattern}")
    return True


def check_docker() -> tuple[bool, str | None]:
    print("[3/6] Docker")
    try:
        client = docker.from_env()
        client.ping()
    except Exception as e:
        fail(f"docker daemon unreachable: {e}")
        return False, None
    ok("docker daemon reachable")
    try:
        out = subprocess.check_output(
            ["ip", "-4", "addr", "show", "docker0"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                bridge_ip = line.split()[1].split("/")[0]
                ok(f"docker bridge IP: {bridge_ip}")
                return True, bridge_ip
    except Exception:
        pass
    warn("could not derive DOCKER_BRIDGE_IP from docker0 — pass --bridge-ip manually")
    return True, None


def check_kvm(needed: bool) -> bool:
    """Check KVM acceleration for kernel-task QEMU VMs. Non-fatal."""
    print("[4/6] KVM acceleration")
    if not needed:
        ok("no kernel tasks selected; KVM not required")
        return True
    dev = Path("/dev/kvm")
    if not dev.exists():
        warn(
            "/dev/kvm not present — kernel-task QEMU VMs will fall back to "
            "software emulation (TCG), which is extremely slow. Enable hardware "
            "virtualization (VT-x/AMD-V) in BIOS/firmware and load the kvm "
            "module (e.g. modprobe kvm_intel / kvm_amd)."
        )
        return True
    if not os.access(dev, os.R_OK | os.W_OK):
        warn(
            "/dev/kvm exists but is not read/writable by the current user — the "
            "QEMU containers need it. Add your user to the 'kvm' group "
            "(sudo usermod -aG kvm $USER, then re-login) or adjust its permissions."
        )
        return True
    ok("/dev/kvm present and accessible")
    return True


def check_squid(needed: bool) -> bool:
    if not needed:
        return True
    print("[5/6] Firewall proxy image")
    client = docker.from_env()
    try:
        client.images.get("ubuntu/squid:latest")
        ok("ubuntu/squid:latest present")
        return True
    except Exception:
        fail("ubuntu/squid:latest missing — run: docker pull ubuntu/squid:latest")
        return False


def _images_for_task(task_id, user_modes, v8_variants, hardened=False):
    if task_id.startswith("user:"):
        meta = TASK_METADATA.get(task_id)
        if meta is None:
            return []
        return [meta.images[m] for m in user_modes if meta.images.get(m)]
    if task_id.startswith("kernel:"):
        # Kernel defense (incl. --kernel-defense strict) is a runtime bitmap,
        # not a separate image, so the image is the same in either profile.
        meta = KERNEL_TASK_METADATA.get(task_id)
        return [meta.image_name] if meta else []
    if task_id.startswith("v8:"):
        meta = V8_TASK_METADATA.get(task_id)
        if meta is None:
            return []
        if hardened:
            # --v8-mode strict: prefer the sandbox (main) image, fall back to
            # the nosandbox image.
            img = meta.image or meta.image_no_sandbox
            return [img] if img else []
        # Variant resolution mirrors pull_images.py.
        images = []
        for v in v8_variants:
            if v == "main":
                if meta.image:
                    images.append(meta.image)
            elif v == "nosandbox":
                if meta.image_no_sandbox:
                    images.append(meta.image_no_sandbox)
            elif v == "nodefense":
                # Prefer the nosandbox image, fall back to the sandbox image.
                img = meta.image_no_sandbox or meta.image
                if img:
                    images.append(img)
        return images
    meta = TASK_METADATA.get(task_id)
    if meta is None:
        return []
    return [meta.images[m] for m in user_modes if meta.images.get(m)]


def check_images(task_ids, user_modes, v8_variants, hardened=False) -> bool:
    print("[6/6] Target images")
    client = docker.from_env()
    local = {t for img in client.images.list() for t in img.tags}
    missing = {}
    unknown_tasks = []
    for tid in task_ids:
        imgs = _images_for_task(tid, user_modes, v8_variants, hardened)
        if not imgs:
            unknown_tasks.append(tid)
            continue
        absent = [i for i in imgs if i not in local]
        if absent:
            missing[tid] = absent
    if unknown_tasks:
        warn(f"{len(unknown_tasks)} task(s) not in metadata: {unknown_tasks[:3]}...")
    if not missing:
        ok(f"all images present for {len(task_ids) - len(unknown_tasks)} task(s)")
        return True
    warn(f"{len(missing)} task(s) missing images (will be pulled lazily)")
    for tid, imgs in list(missing.items())[:5]:
        for img in imgs:
            print(f"       {tid}: {img}")
    if len(missing) > 5:
        print(f"       ... and {len(missing) - 5} more")
    # Under --hardened the v8 image is strict-resolved (main or nosandbox);
    # pull both to cover it, since pull_images has no 'strict' variant.
    v8_hint = "main nosandbox" if hardened else " ".join(v8_variants)
    print(
        "       To pre-pull: uv run scripts/setup/pull_images.py <tasks> "
        f"--user-modes {' '.join(user_modes)} --v8-variants {v8_hint}"
    )
    return True


# ---------------------------------------------------------------------------
# Service detection (auto-skip already-running services)
# ---------------------------------------------------------------------------


def _http_alive(url: str, timeout: float = 1.0) -> bool:
    """True if *url* answers with any HTTP response — even a 4xx/5xx.

    A FastAPI service returns 404 on an unknown path, which still proves
    something is listening on the port.
    """
    import urllib.error
    import urllib.request

    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def detect_firewall_running() -> bool:
    """True if the (API-only) run proxy container is already up."""
    try:
        client = docker.from_env()
        c = client.containers.get(PROXY_CONTAINER_NAME)
        c.reload()
        return c.status == "running"
    except Exception:
        return False


def detect_install_proxy_running() -> bool:
    """True if the allow-all install proxy container is already up."""
    try:
        client = docker.from_env()
        c = client.containers.get(INSTALL_PROXY_CONTAINER_NAME)
        c.reload()
        return c.status == "running"
    except Exception:
        return False


def detect_controller_running(bridge_ip: str, port: int) -> bool:
    """True if a controller is already serving on bridge_ip:port."""
    return bool(bridge_ip) and _http_alive(f"http://{bridge_ip}:{port}/")


def detect_llm_proxy_running(bridge_ip: str, port: int) -> bool:
    """True if an LLM proxy is already serving on bridge_ip:port."""
    if not bridge_ip:
        return False
    return _http_alive(f"http://{bridge_ip}:{port}/health/liveliness") or _http_alive(
        f"http://{bridge_ip}:{port}/"
    )


def extract_admin_key_from_log(log_path: Path) -> str | None:
    """Recover the LLM proxy admin key from a prior run's log.

    The proxy logs ``Admin key for /budget endpoints: <key>`` at startup
    (cybergym.llm_proxy.server). When we reuse an already-running proxy we
    didn't generate its key, so read it back from the log. The log is opened
    in append mode across runs, so return the most recent match.
    """
    try:
        text = log_path.read_text(errors="replace")
    except OSError:
        return None
    keys = re.findall(r"Admin key for /budget endpoints:\s*(\S+)", text)
    return keys[-1] if keys else None


# ---------------------------------------------------------------------------
# Service startup
# ---------------------------------------------------------------------------


def _start_background(cmd, log_path: Path, env=None):
    """Launch a command detached, writing stdout+stderr to log_path. Return Popen."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = log_path.open("ab")
    return subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=env,
        start_new_session=True,
    )


def start_firewall(bridge_ip, log_dir: Path, with_install: bool) -> bool:
    # Kernel tasks run an install phase behind the allow-all install proxy, so
    # bring up both proxies ('both') when kernel tasks are present; otherwise
    # just the API-only run proxy ('run').
    which = "both" if with_install else "run"
    print(f"\n→ Firewall (ip={bridge_ip}, which={which})")
    # firewall start is not long-running — it creates containers and exits.
    r = subprocess.run(
        [
            "uv",
            "run",
            "-m",
            "cybergym.firewall",
            "start",
            "--which",
            which,
            "--ip",
            bridge_ip,
        ],
        capture_output=True,
        text=True,
    )
    (log_dir / "firewall-start.log").write_text(r.stdout + r.stderr)
    if r.returncode != 0:
        fail(f"firewall start failed (see {log_dir}/firewall-start.log)")
        return False
    if with_install:
        ok(
            "firewall running (run proxy: cybergym-internal + cybergym-proxy; "
            "install proxy: cybergym-install + cybergym-install-proxy)"
        )
    else:
        ok("firewall running (cybergym-internal network + cybergym-proxy container)")
    return True


def start_controller(bridge_ip, port, log_dir: Path) -> subprocess.Popen | None:
    print(f"\n→ Controller (host={bridge_ip}, port={port})")
    log_path = log_dir / "controller.log"
    proc = _start_background(
        [
            "uv",
            "run",
            "-m",
            "cybergym.server",
            "--host",
            bridge_ip,
            "--port",
            str(port),
            "--log_dir",
            str(log_dir / "controller"),
            "--network",
            "cybergym-internal",
        ],
        log_path,
    )
    # Poll briefly — FastAPI 404 on / means up
    import urllib.request

    for _ in range(20):
        time.sleep(0.5)
        if proc.poll() is not None:
            fail(f"controller exited (code {proc.returncode}); see {log_path}")
            return None
        try:
            urllib.request.urlopen(f"http://{bridge_ip}:{port}/", timeout=1)
            break
        except Exception:
            pass
    if proc.poll() is not None:
        fail(f"controller exited (code {proc.returncode}); see {log_path}")
        return None
    ok(f"controller running (pid={proc.pid}, log={log_path})")
    return proc


def start_llm_proxy(
    bridge_ip, port, admin_key, budget, log_dir: Path
) -> subprocess.Popen | None:
    print(f"\n→ LLM proxy (host={bridge_ip}, port={port})")
    log_path = log_dir / "llm_proxy.log"
    env = os.environ.copy()
    proc = _start_background(
        [
            "uv",
            "run",
            "-m",
            "cybergym.llm_proxy",
            "--host",
            bridge_ip,
            "--port",
            str(port),
            "--admin-key",
            admin_key,
            "--default-budget",
            str(budget),
        ],
        log_path,
        env=env,
    )
    import urllib.request

    for _ in range(20):
        time.sleep(0.5)
        if proc.poll() is not None:
            fail(f"llm_proxy exited (code {proc.returncode}); see {log_path}")
            return None
        try:
            urllib.request.urlopen(
                f"http://{bridge_ip}:{port}/health/liveliness", timeout=1
            )
            break
        except Exception:
            try:
                urllib.request.urlopen(f"http://{bridge_ip}:{port}/", timeout=1)
                break
            except Exception:
                pass
    if proc.poll() is not None:
        fail(f"llm_proxy exited (code {proc.returncode}); see {log_path}")
        return None
    ok(f"llm_proxy running (pid={proc.pid}, log={log_path})")
    return proc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Pre-run readiness check + service startup for cybergym agents."
    )
    parser.add_argument(
        "tasks_file", type=Path, help="File with task IDs (one per line)"
    )
    parser.add_argument(
        "--no-firewall", action="store_true", help="Skip firewall startup"
    )
    parser.add_argument(
        "--no-controller", action="store_true", help="Skip controller startup"
    )
    parser.add_argument(
        "--no-llm-proxy", action="store_true", help="Skip LLM proxy startup"
    )
    parser.add_argument(
        "--hardened",
        action="store_true",
        help=(
            "Strict/hardened profile: require ASLR enabled, check the hardened "
            "image variants (user exp.hardened, v8 strict), and print the "
            "matching run_agent.py flags (--user-mode exp.hardened --v8-mode "
            "strict --kernel-defense strict). Sets the --user-modes/--v8-variants "
            "defaults unless you pass them explicitly."
        ),
    )
    parser.add_argument(
        "--user-modes",
        nargs="+",
        default=None,
        help=(
            "Image modes required for user/cybergym tasks "
            "(default: exp.none, or exp.hardened with --hardened)"
        ),
    )
    parser.add_argument(
        "--v8-variants",
        nargs="+",
        default=None,
        choices=["main", "nosandbox", "nodefense"],
        help=(
            "V8 image variants required (default: nodefense; ignored with "
            "--hardened, which uses v8 strict). 'nodefense' prefers the "
            "nosandbox image, falling back to the sandbox image."
        ),
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/tasks"),
        help="Extracted PoC root (default: data/tasks)",
    )
    parser.add_argument(
        "--bridge-ip",
        default=None,
        help="Override docker bridge IP (default: autodetect from docker0)",
    )
    parser.add_argument("--controller-port", type=int, default=8666)
    parser.add_argument("--proxy-port", type=int, default=4000)
    parser.add_argument(
        "--admin-key", default=None, help="LLM proxy admin key (default: auto-generate)"
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=20.0,
        help="Default per-task budget in USD (default: 20)",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs/pre_run"),
        help="Where service logs are written",
    )
    args = parser.parse_args()

    # The --hardened preset sets the image-check defaults unless overridden.
    # v8 image resolution under --hardened uses strict semantics directly, so
    # --v8-variants is ignored in that case (it only feeds the default profile).
    if args.user_modes is None:
        args.user_modes = ["exp.hardened"] if args.hardened else ["exp.none"]
    if args.v8_variants is None:
        args.v8_variants = ["nodefense"]

    if not args.tasks_file.exists():
        print(f"Task file not found: {args.tasks_file}", file=sys.stderr)
        sys.exit(2)

    task_ids = [
        line.strip()
        for line in args.tasks_file.read_text().splitlines()
        if line.strip()
    ]
    print(f"Checking {len(task_ids)} task(s) from {args.tasks_file}\n")

    enabled_firewall = not args.no_firewall
    enabled_controller = not args.no_controller
    enabled_proxy = not args.no_llm_proxy

    results = [
        check_aslr(hardened=args.hardened),
        check_coredump(),
    ]
    docker_ok, bridge_ip = check_docker()
    results.append(docker_ok)
    if args.bridge_ip:
        bridge_ip = args.bridge_ip
        ok(f"using --bridge-ip {bridge_ip}")
    has_kernel_tasks = any(t.startswith("kernel:") for t in task_ids)
    results.append(check_kvm(needed=has_kernel_tasks))
    results.append(check_squid(needed=enabled_firewall))
    results.append(
        check_images(task_ids, args.user_modes, args.v8_variants, args.hardened)
    )

    print()
    if not all(results):
        print(
            f"{COLOR_ERR}Pre-run check FAILED — resolve issues above before running.{COLOR_RESET}"
        )
        sys.exit(1)
    print(f"{COLOR_OK}Pre-run check PASSED.{COLOR_RESET}")

    # For each enabled service, auto-detect whether it is already running and,
    # if so, skip launching a duplicate. A `--no-*` flag disables the service
    # entirely (neither detected nor started).
    print("\nService status:")
    # Task families with a non-empty install script need the allow-all install
    # proxy up. Treat the firewall as "running" only when every proxy it needs
    # is up, so a missing install proxy triggers a (idempotent) start of both.
    present_task_types = {
        tt
        for prefix, tt in _PREFIX_TO_TASK_TYPE.items()
        if any(t.startswith(prefix) for t in task_ids)
    }
    need_install_proxy = enabled_firewall and any(
        task_needs_install(tt) for tt in present_task_types
    )
    firewall_running = (
        enabled_firewall
        and detect_firewall_running()
        and (not need_install_proxy or detect_install_proxy_running())
    )
    controller_running = enabled_controller and detect_controller_running(
        bridge_ip, args.controller_port
    )
    proxy_running = enabled_proxy and detect_llm_proxy_running(
        bridge_ip, args.proxy_port
    )
    for name, enabled, running in (
        ("firewall", enabled_firewall, firewall_running),
        ("controller", enabled_controller, controller_running),
        ("llm_proxy", enabled_proxy, proxy_running),
    ):
        if not enabled:
            ok(f"{name}: disabled (--no-... flag)")
        elif running:
            ok(f"{name}: already running — reusing it (no new instance started)")
        else:
            ok(f"{name}: not running — will start")

    need_start_firewall = enabled_firewall and not firewall_running
    need_start_controller = enabled_controller and not controller_running
    need_start_proxy = enabled_proxy and not proxy_running

    if not bridge_ip and (
        need_start_firewall or need_start_controller or need_start_proxy
    ):
        fail("bridge IP unknown; cannot start services. Pass --bridge-ip manually.")
        sys.exit(1)

    log_dir = args.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    if need_start_firewall:
        if not start_firewall(bridge_ip, log_dir, with_install=need_install_proxy):
            sys.exit(1)

    controller_proc = None
    if need_start_controller:
        controller_proc = start_controller(bridge_ip, args.controller_port, log_dir)
        if controller_proc is None:
            sys.exit(1)

    proxy_proc = None
    admin_key = args.admin_key or f"cgym-admin-{secrets.token_hex(12)}"
    if need_start_proxy:
        proxy_proc = start_llm_proxy(
            bridge_ip, args.proxy_port, admin_key, args.budget, log_dir
        )
        if proxy_proc is None:
            sys.exit(1)

    # Summary
    print("\n" + "=" * 60)
    print("Services ready. Relevant env for the agent runner:")
    print(f"export DOCKER_BRIDGE_IP={bridge_ip}")
    if enabled_proxy:
        if proxy_proc is not None:
            print(f"export CYBERGYM_ADMIN_KEY={admin_key}")
        else:
            # Reused an already-running proxy — recover its admin key from the
            # log it wrote at startup rather than asking the user for it.
            log_path = log_dir / "llm_proxy.log"
            recovered = extract_admin_key_from_log(log_path)
            if recovered:
                admin_key = recovered
                print(
                    f"export CYBERGYM_ADMIN_KEY={admin_key}  # recovered from {log_path}"
                )
            else:
                print(
                    "# llm_proxy was already running but its admin key was not "
                    f"found in {log_path}; set CYBERGYM_ADMIN_KEY yourself"
                )
        print(f"  --proxy-url http://{bridge_ip}:{args.proxy_port} \\")
        print("  --proxy-admin-key $CYBERGYM_ADMIN_KEY \\")
    if enabled_controller:
        print(f"  --controller-url http://{bridge_ip}:{args.controller_port} \\")
    if enabled_firewall:
        print("  --use-firewall \\")
    if args.hardened:
        # Hardened profile: pass the matching defense flags to run_agent.py.
        print("  --user-mode exp.hardened \\")
        print("  --v8-mode strict \\")
        print("  --kernel-defense strict \\")
    pids = []
    if controller_proc:
        pids.append(f"controller={controller_proc.pid}")
    if proxy_proc:
        pids.append(f"llm_proxy={proxy_proc.pid}")
    if pids:
        print(f"\nBackground PIDs: {' '.join(pids)}")
        print(f"Logs: {log_dir}/")
        print(
            "Stop with: kill <pid>  "
            "(firewall: uv run -m cybergym.firewall stop --which both)"
        )
    print("=" * 60)


if __name__ == "__main__":
    main()
