# Docker images

Every evaluation runs two containers: an **agent container** (the CLI running
your chosen model) and a **target container** (the vulnerable program or
kernel under attack). The agent image is built from the local
`docker/` tree; the target images need to be pulled from the CyberGym
registry before you can run any task.

This doc covers pulling the target images. Run everything from the project
root.

## Where image names come from

Each task family stores its image in metadata:

| Family | Metadata file | Field | Notes |
| --- | --- | --- | --- |
| `user:` (cybergym binary exploit) | `src/cybergym/task/metadata.json` | `images[<mode>]` | Multiple build variants per task |
| `kernel:` (kernelctf + syzbot) | `src/cybergym/task/kernel_metadata.json` | `image_name` | Single image per task |
| `v8:` | `src/cybergym/task/v8_metadata.json` | `image` + `image_no_sandbox` | Optional sandbox-disabled variant |

User tasks have several image modes (`vul`, `fix`, `exp.none`, `exp.canary`,
`exp.pie`, ...) corresponding to different compilation flags; you typically
only need one mode per evaluation campaign.

V8 tasks ship a primary `image` and, for most tasks, an `image_no_sandbox`
variant built with the V8 sandbox disabled. Sandbox-escape tasks only have
the primary image (no nosandbox variant).

## Pull images for a task list

Use `scripts/setup/pull_images.py`. It reads a text file (one task_id per
line), dispatches on the prefix, and pulls in parallel. Duplicate images
(common across kernel tasks) are deduplicated automatically.

```bash
# Default: pull `exp.none` for any user: tasks, plus the single image for kernel: / v8: tasks
uv run scripts/setup/pull_images.py data/task_ids/sample.txt

# Multiple cybergym modes in one pass
uv run scripts/setup/pull_images.py data/task_ids/sample.txt \
    --user-modes exp.none exp.canary exp.pie

# Pull both main and sandbox-disabled v8 builds
uv run scripts/setup/pull_images.py data/task_ids/sample.txt \
    --v8-variants main nosandbox

# One image per v8 task, preferring nosandbox where available
uv run scripts/setup/pull_images.py data/task_ids/sample.txt \
    --v8-variants nodefense

# Bigger worker pool on fast networks
uv run scripts/setup/pull_images.py data/task_ids/sample.txt --workers 16

# Force a registry pull even for images already present locally
uv run scripts/setup/pull_images.py data/task_ids/sample.txt --no-skip-local
```

Images already present locally are **skipped by default** — re-runs only
pull what's missing and don't spend Docker Hub rate-limit budget
re-validating tags you already have. Pass `--no-skip-local` to force a
`docker pull` for every resolved image (e.g. to refresh a tag).

The `--user-modes` flag is only consulted for `user:` entries;
`--v8-variants` is only consulted for `v8:` entries (choices: `main`,
`nosandbox`, `nodefense`; default: `main`). For `main` and `nosandbox`,
tasks that don't define the requested variant are skipped with a
warning. `nodefense` picks `image_no_sandbox` if available else `image`,
so it skips a task only when both are missing.

The task-id files in `data/task_ids/` use the alias form (e.g.
`user:cybergym/arvo_18224`, `kernel:kernelctf/CVE-2024-1085_lts`,
`v8:clusterfuzz/343069827`). Hashed forms (`user:<hex>`, `kernel:<hex>`,
`v8:<hex>`) also resolve.
