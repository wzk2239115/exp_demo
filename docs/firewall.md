# Firewall Proxy

The firewall proxy restricts agent containers to a domain allowlist by
running a Squid forward proxy on an **internal** Docker network with no
default internet route. Even if a program inside the container ignores
`HTTP_PROXY`, direct connections fail because there is no route out.

```
Agent Container ──(cybergym-internal, no internet)──> Squid Proxy ──(bridge)──> Internet
                                                                    filtered by allowlist
```

## Quick start

```bash
# 0. Pull the Firewall Squid image
docker pull ubuntu/squid:latest

# 1. Start the proxy (creates network + Squid container)
python -m cybergym.firewall start

# 2. Run an evaluation with the proxy enabled
#    (the evaluator connects to the running proxy automatically)
python run_eval.py --use-proxy ...
```

## CLI reference

```bash
# Start proxy with defaults
python -m cybergym.firewall start

# Start with a custom allowlist and extra domains
python -m cybergym.firewall start \
    --allowlist my_domains.txt \
    --domain extra.example.com \
    --domain .another.org

# Add an IP allowlist
python -m cybergym.firewall start \
    --ip-allowlist my_ips.txt \
    --ip 10.0.0.0/8

# Restart proxy with fresh config (preserves network, keeps other containers connected)
python -m cybergym.firewall update

# Stop the proxy container (network is kept for reuse)
python -m cybergym.firewall stop

# Stop proxy and remove network (disconnects all containers)
python -m cybergym.firewall stop-all

# Show current infrastructure state
python -m cybergym.firewall status
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
includes domains for:

- **apt** -- `archive.ubuntu.com`, `security.ubuntu.com`, etc.
- **pip** -- `pypi.org`, `files.pythonhosted.org`, etc.
- **v8 deps** -- `chromium.googlesource.com`, `storage.googleapis.com`, etc.
- **LLM APIs** -- `api.openai.com`, `api.anthropic.com`, `generativelanguage.googleapis.com`, etc.

Pass `--allowlist` to replace the default, or `--domain` to add entries
on top of it.

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

1. Connects to the running proxy via `FirewallProxyManager().connect()`
2. Places the agent container on the `cybergym-internal` network
3. Injects `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` environment
   variables into the container

The proxy must be started **before** running the evaluation. The
evaluator does not manage the proxy lifecycle -- this lets a single proxy
instance be shared across multiple evaluation runs.

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
   reach the Squid proxy. Squid checks each request against the domain
   (and optionally IP) allowlist and either forwards it to the internet
   or returns a `403 Forbidden`.

4. **Cleanup** -- `stop()` removes the proxy container but keeps the
   network (for quick restarts). `stop_all()` disconnects all remaining
   containers and removes the network entirely.
