# Agent Trajectory Scorer

Batch-scores AI agent trajectories from cybersecurity exploitation tasks. For
each task, a two-pass pipeline runs **inside the task's original target image**,
the same image the agent was evaluated against — so the scorer has first-hand
access to the target's source code and build artifacts (e.g. `/src/v8` and
`/challenge` for V8 tasks; the project source / vulnerable binary for userspace
tasks) to verify root-cause and target-vulnerability claims against real code.

The per-task image is resolved automatically from each task's `config.json` via
cybergym metadata, so **run the scorer with `uv run`** (it must import
`cybergym`). The agent CLI is not baked into any image: the statically-built
runtime under `data/runtime` (node + the claude/codex/gemini CLIs) is
bind-mounted at `/data`, exactly like the main evaluation harness.

1. **Scorer agent** — reads the trajectory logs (and the target source) and produces a structured `scorer_result.json`
2. **Judge agent** — reviews the scorer's output, validates evidence quotes (`grep -F`), checks logical consistency against the real source, and corrects errors

Both passes use the same model. The recommended models are:

- **Claude scorer**: `claude-opus-4-6` (via Claude Code CLI)
- **Codex scorer**: `gpt-5.5` (via Codex CLI)

The final `scorer_result.json` analyzes:

- What vulnerabilities the agent actually used in its final exploit
- Whether they match the task's target vulnerability
- Where vulnerability info came from (model knowledge, task description, web search, etc.)
- Whether the agent already knew the vulnerability was exploitable
- Any refusal behavior (hard/soft)
- All claims backed by exact verbatim quotes from the trajectory files

## Authentication

**Default: API keys** (from environment variables)

- Claude: `ANTHROPIC_API_KEY`
- Codex: `OPENAI_API_KEY`

**Alternative: credential files** (add `--use-credential`)

- Claude: `~/.claude/.credentials.json` (run `claude` to authenticate)
- Codex: `~/.codex/auth.json` (run `codex login` to authenticate)

## Prerequisites

- The static agent CLI runtime at `data/runtime` (built by
  `scripts/setup/static_build_node_and_agents.sh` — see [setup](../docs/setup.md)).
  Override its location with `--runtime-dir` if needed.
- The per-task target images available locally (or pullable) — the same images
  used for evaluation; see [docker_images.md](../docs/docker_images.md).

## Usage

### Basic

```bash
# Score all tasks under an experiment directory with Claude
uv run agent_scorer/run_scorer.py /path/to/experiment/batch \
    --scorer claude --model claude-opus-4-6 --output-dir out/scores

# Score with Codex
uv run agent_scorer/run_scorer.py /path/to/experiment/batch \
    --scorer codex --model gpt-5.5 --output-dir out/scores
```

### Common options

```bash
uv run agent_scorer/run_scorer.py /path/to/experiment/batch \
    --scorer claude \
    --model claude-opus-4-6 \
    --workers 6 \                # concurrent scorer containers (default: 4)
    --output-dir out/scores \    # results dir (flat: path/to/task → path__to__task/)
    --success-only \             # only score tasks where result.json has score > 0
    --overwrite                  # re-score tasks that already have scorer_result.json
```

### All options

| Option | Description |
|---|---|
| `root` | Root directory containing task result directories |
| `--scorer {claude,codex}` | Which agent CLI to use (default: `claude`) |
| `--model MODEL` | Model name (default: `claude-sonnet-4-6`; recommended: `claude-opus-4-6` for Claude, `gpt-5.5` for Codex) |
| `--workers N` | Concurrent scorer containers (default: 4) |
| `--timeout SECS` | Timeout per task in seconds (default: 600) |
| `--output-dir PATH` | Write results to this directory (flat layout: relative path joined with `__`) |
| `--success-only` | Only score tasks with successful results |
| `--use-credential` | Use credential files instead of API keys |
| `--overwrite` | Re-score already-scored tasks |
| `--task-list FILE` | File with explicit task directory paths (one per line) |
| `--api-base-url URL` | Custom API base URL |
| `--runtime-dir PATH` | Host dir with the static agent CLI runtime, mounted at `/data` (default: `data/runtime`) |
| `--task-image IMG` | Override the per-task image (otherwise resolved from each task's `config.json`) |
| `--dry-run` | List task directories without running |

## Validating results

`validate_results.py` checks that every evidence quote in `scorer_result.json` is an exact substring of the claimed source file:

```bash
python3 agent_scorer/validate_results.py out/scores
```

## Output format

Each scored task produces a directory (flat `__`-joined name under `--output-dir`) containing:

- `scorer_result.json` — structured analysis (vulnerabilities, refusals, evidence quotes, strategy summary), after judge correction. Includes `scorer_model` and `scorer_task_image` (the image the scorer ran in).
- `scorer.log` — raw scorer agent output (first pass)
- `judge.log` — raw judge agent output (second pass)
- `_task_dir.txt` — absolute path to the original task directory
