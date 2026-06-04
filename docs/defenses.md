# Defenses and Mitigations


## Disable ASLR

Some evaluation tasks require disabling OS-level security features on the
host machine. These changes affect all processes on the host, so only apply
them on dedicated evaluation machines.

Address Space Layout Randomization (ASLR) must be disabled for deterministic
exploit reproduction.

```bash
sudo sysctl -w kernel.randomize_va_space=0
```

To re-enable:

```bash
sudo sysctl -w kernel.randomize_va_space=2
```

> This setting is not persistent across reboots. To make it permanent,
> add `kernel.randomize_va_space = 0` to `/etc/sysctl.conf` or a file
> under `/etc/sysctl.d/`.

## Mitigations

How much protection the target is given is selected per task family, because
the mechanism differs in each case: user tasks pick a hardened **binary
build**, V8 tasks pick a **sandbox build**, and kernel tasks pick a set of
**boot-time defenses / attacker capabilities**. `examples/run_agent.py`
therefore exposes one flag per family.

### User tasks: `--user-mode`

Selects which compiled image of the cybergym binary to attack (default
`exp.none`). The chosen image must be pulled first, see
[docker_images.md](docker_images.md).

| Mode | Binary hardening |
| --- | --- |
| `exp.none` (default) | none, baseline build, paired with ASLR disabled |
| `exp.canary` | stack canaries |
| `exp.pie` | position-independent executable, paired with ASLR enabled |
| `exp.relro` | full RELRO |
| `exp.hardened` | all of the above |

```bash
uv run examples/run_agent.py --agent claude_code --use-api-key \
    --task-family user --user-mode exp.canary

# With all mitigations (ASLR, canary, PIE, Full RELRO)
# output 2 (ASLR enabled)
sysctl kernel.randomize_va_space
uv run examples/run_agent.py ... \
    --task-family user --user-mode exp.hardened
```



### V8 tasks: `--v8-mode`

Selects which V8 build to evaluate against (default `sandbox`). Each task
ships a primary `image` and, for most, an `image_no_sandbox` variant.

Each mode can be paired with ASLR disabled or enabled.

| Mode | Image used | Skips |
| --- | --- | --- |
| `nodefense` (default) | nosandbox if present, else main | never, runs any task that has any image |
| `sandbox` | main image (V8 sandbox enabled) | pre-sandbox tasks that have no main image |
| `strict` | main if present, else nosandbox | never, runs any task that has any image |
| `nosandbox` | sandbox-disabled image | sandbox-escape tasks that have no nosandbox image |

```bash
uv run examples/run_agent.py --agent claude_code --use-api-key \
    --task-family v8 --v8-mode nosandbox

# With all mitigations (ASLR, sandbox)
# output 2 (ASLR enabled)
sysctl kernel.randomize_va_space
uv run examples/run_agent.py ... \
    --task-family v8 --v8-mode strict
```

### Kernel tasks: `--kernel-defense`

Selects the kernel mitigation profile for kernelctf/syzbot VMs (default
`default`). A profile is a set of capabilities, where each capability
weakens a defense or grants the attacker a kernel feature:

| Capability | Effect |
| --- | --- |
| `nokaslr` | KASLR disabled |
| `nosmep` | SMEP disabled |
| `nosmap` | SMAP disabled |
| `userns` | unprivileged user namespaces enabled |
| `io_uring` | io_uring enabled |
| `kernelctf_hardening` | kernelCTF hardening sysctls enabled |

Accepted values are a preset or a `+`-separated capability list:

| Spec | Capabilities |
| --- | --- |
| `default` (default) | `nokaslr` + `userns` |
| `original` | the CVE's original kernelctf capabilities (from task metadata) |
| `strict` | none, every defense on, no attacker capabilities |
| `nodefense` | every capability set |
| `<cap>+<cap>…` | exactly the listed capabilities, e.g. `nokaslr+nosmep+userns` |

```bash
# Use the task's original kernelctf profile
uv run examples/run_agent.py --agent claude_code --use-api-key \
    --task-family kernel --kernel-defense original

# Hand-pick capabilities
uv run examples/run_agent.py --agent claude_code --use-api-key \
    --task-family kernel --kernel-defense nokaslr+userns

# With all mitigations (KASLR, SMEP, SMAP, no userns)
uv run examples/run_agent.py --agent claude_code --use-api-key \
    --task-family kernel --kernel-defense strict
```
