# Firewall Proxy

The firewall proxy restricts agent containers to a domain allowlist by
running a Squid forward proxy on an **internal** Docker network with no
default internet route. Even if a program inside the container ignores
`HTTP_PROXY`, direct connections fail because there is no route out.

There are **two** proxies:

- **Run proxy** (`cybergym-proxy` on `cybergym-internal`) — the default. Its
  allowlist permits **only the LLM API endpoints**. This is what the agent
  sees while it runs.
- **Install proxy** (`cybergym-install-proxy` on `cybergym-install`) — an
  **allow-all** proxy used only during the pre-agent install phase, where the
  container needs unrestricted network access to fetch packages. The evaluator
  disconnects the container from this network before the agent runs, so the
  agent has no route to it.

```
Install phase:  Container ─(cybergym-install, no internet)─> Install proxy ─(bridge)─> Internet  (allow-all)
                                                  │  evaluator switches network
Agent phase:    Container ─(cybergym-internal, no internet)─> Run proxy ─(bridge)─> Internet  (API endpoints only)
```

## Quick start

```bash
# 0. Pull the Firewall Squid image (used by both proxies)
docker pull ubuntu/squid:latest

# 1. Start the run proxy (creates network + Squid container)
python -m cybergym.firewall start

#    The agents' install phase needs the allow-all install proxy too —
#    `--which both` brings up both:
python -m cybergym.firewall start --which both

# 2. Run an evaluation with the firewall enabled
#    (the evaluator connects to the running proxy/proxies automatically)
python run_eval.py --use-firewall ...
```

## CLI reference

Every subcommand takes `--which {run,install,both}` to pick the target proxy
(default `run`). The allowlist flags below apply to the run proxy only — the
install proxy is always allow-all.

```bash
# Start the run proxy with defaults
python -m cybergym.firewall start

# Start the allow-all install proxy, or both at once
python -m cybergym.firewall start --which install
python -m cybergym.firewall start --which both

# Start the run proxy with a custom allowlist and extra domains
python -m cybergym.firewall start \
    --allowlist my_domains.txt \
    --domain extra.example.com \
    --domain .another.org

# Add an IP allowlist (run proxy)
python -m cybergym.firewall start \
    --ip-allowlist my_ips.txt \
    --ip 10.0.0.0/8

# Restart proxy with fresh config (preserves network, keeps other containers connected)
python -m cybergym.firewall update --which both

# Stop the proxy container(s) (network is kept for reuse)
python -m cybergym.firewall stop --which both

# Stop proxy and remove network (disconnects all containers)
python -m cybergym.firewall stop-all --which both

# Show current infrastructure state
python -m cybergym.firewall status --which both
```

## Domain allowlist

The allowlist file uses Squid `dstdomain` format: one domain per line,
with a leading dot matching the domain and all subdomains.

```text
# Comments start with #
.example.com          # matches example.com AND *.example.com
plain.org             # exact match only
```

The built-in default allowlist (`src/cybergym/firewall/default_allowlist.txt`)
is the **run-proxy** allowlist and contains **only the LLM API endpoints**:

- **LLM APIs** -- `api.openai.com`, `api.anthropic.com`,
  `generativelanguage.googleapis.com`, `api.together.xyz`.

Package repositories (apt, pip) are intentionally **not** here — package
installation happens in the install phase, which goes through the allow-all
install proxy (see [Install phase](#install-phase) below).

Pass `--allowlist` to replace the default, or `--domain` to add entries
on top of it.

## Install phase

Some tasks need build tooling and packages installed before the agent runs.
Because the run proxy only allows API endpoints, that work happens in a
separate **install phase**:

1. The evaluator starts the container on the **install network**
   (`cybergym-install`), attached to the allow-all install proxy.
2. It runs the agent's `install()` step, which fetches packages with full
   network access.
3. It disconnects the container from the install network and connects it to
   the API-only run network, then runs the agent. The agent has no route back
   to the install proxy.

Whether a task has an install phase is decided per agent and per task by
`Agent.has_install_phase(task_type)`. The bundled agents
(`ClaudeCodeAgent`, `CodexAgent`, `GeminiCliAgent`) inherit
`DefaultInstallAgent`, which runs a per-task-type script from `INSTALL_SCRIPTS`
in `src/cybergym/evaluation/agents/helper.py` — `KERNEL_INSTALL_SCRIPT`,
`V8_INSTALL_SCRIPT`, and `USER_INSTALL_SCRIPT`, each installing that family's
build / exploit tooling.

A script that is empty or contains only comments counts as "nothing to
install", so the install phase — and the install proxy — are skipped for that
task type. To customize, edit a script or override `install()` /
`has_install_phase()` in a subclass.

Because of this, running a task whose agent has an install phase behind the
firewall requires the install proxy to be up:

```bash
python -m cybergym.firewall start --which both
```

`scripts/setup/pre_run.py` does this automatically when a selected task family
has a non-empty install script.

## IP allowlist

For destinations that don't resolve to a fixed domain (e.g. internal
services), you can allowlist by IP address or CIDR block:

```bash
python -m cybergym.firewall start --ip 10.0.0.5 --ip 192.168.1.0/24
```

Or provide a file with `--ip-allowlist` (same format as the domain file,
one entry per line). When an IP allowlist is present, all ports (1-65535)
are opened for IP-matched destinations.

The host gateway IP on the internal network is automatically added to
both the IP allowlist and `NO_PROXY` so containers can reach the host
directly (e.g. for the challenge controller).

## Evaluator integration

Set `use_firewall=True` in `EvalConfig` to place agent containers behind
the proxy:

```python
from cybergym.evaluation.types import EvalConfig

config = EvalConfig(
    task_id="kernelctf:CVE-2024-1085_lts",
    use_firewall=True,
    # ...
)
```

When `use_firewall` is enabled the evaluator:

1. Connects to the running run proxy via `FirewallProxyManager().connect()`.
2. If the agent has an install phase for this task, connects to the install
   proxy (`FirewallProxyManager.for_install().connect()`), starts the
   container on `cybergym-install`, runs the install step with the install
   proxy's env, then switches the container to `cybergym-internal`. Otherwise
   the container starts directly on `cybergym-internal`.
3. Injects `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` environment variables
   into the container (install-proxy env during the install phase, run-proxy
   env for the agent).

The proxy/proxies must be started **before** running the evaluation. The
evaluator does not manage the proxy lifecycle -- this lets a single proxy
instance be shared across multiple evaluation runs. Tasks with an install
phase additionally require the install proxy (`--which both`).

## Python API

```python
from cybergym.firewall import FirewallProxyManager, load_allowlist

# Start with defaults
proxy = FirewallProxyManager()
proxy.start()

# Or customize
proxy = FirewallProxyManager(
    allowlist_path="my_domains.txt",      # domain allowlist file
    extra_domains=[".custom.example.com"],  # additional domains
    ip_allowlist_path="my_ips.txt",        # IP allowlist file
    extra_ips=["10.0.0.0/8"],             # additional IPs/CIDRs
)
proxy.start()

# Get env vars for a container
proxy.env_vars()
# {'HTTP_PROXY': 'http://cybergym-proxy:3128',
#  'HTTPS_PROXY': 'http://cybergym-proxy:3128',
#  'NO_PROXY': '172.18.0.1,localhost,127.0.0.1', ...}

# Other properties
proxy.proxy_url       # http://cybergym-proxy:3128
proxy.network_name    # cybergym-internal
proxy.host_gateway    # 172.18.0.1 (varies)

# Connect to an already-running proxy (does not start anything)
proxy2 = FirewallProxyManager()
proxy2.connect()

# The allow-all install proxy (own container + internal network)
install_proxy = FirewallProxyManager.for_install()
install_proxy.start()
install_proxy.proxy_url      # http://cybergym-install-proxy:3128
install_proxy.network_name   # cybergym-install

# Lifecycle
proxy.update()     # restart with fresh config, keep network
proxy.stop()       # remove proxy container, keep network
proxy.stop_all()   # remove proxy + network
proxy.status()     # {'network': {...}, 'proxy': {...}}
```

## How it works

1. **Network creation** -- `FirewallProxyManager.start()` creates a Docker
   bridge network with `internal=True`, which removes the default
   internet route. If the network already exists, it validates that it
   is internal (rejects external networks to prevent accidental bypass).

2. **Squid container** -- A `ubuntu/squid:latest` container is created
   on the default bridge (internet access). Configuration files are
   copied in via `put_archive()` (no bind-mounts). The container is
   then connected to the internal network so agents can reach it.

3. **Request flow** -- Agent containers on the internal network can only
   reach the Squid proxy. The run proxy checks each request against the
   domain (and optionally IP) allowlist and either forwards it to the
   internet or returns a `403 Forbidden`. The install proxy forwards to any
   destination.

4. **Two-phase isolation** -- The install and run proxies sit on separate
   internal networks. The evaluator moves the container off the install
   network before the agent runs, so revoking the broad access is enforced
   at the network layer (no route), not just by the proxy config.

5. **Cleanup** -- `stop()` removes the proxy container but keeps the
   network (for quick restarts). `stop_all()` disconnects all remaining
   containers and removes the network entirely. Use `--which both` to target
   both proxies.
