# Submission Guidelines

Results are submitted by **opening a pull request** against
[`exploitgym-results`](https://github.com/sunblaze-ucb/exploitgym-results).
A submission is a single directory added by that PR containing exactly two files:

- `metadata.yml`: who/what produced the run and under which configuration.
- `results.json`: a JSON list with one object per benchmark instance.

All cost/token numbers are the agent's own LLM usage (the model driving the
exploit), not the scorer's.

## How to submit

1. Fork [`exploitgym-results`](https://github.com/sunblaze-ucb/exploitgym-results)
   and create a branch.
2. Add a new submission directory (e.g. `submissions/<name>/`) containing
   `metadata.yml` and `results.json` as specified below.
3. Open a pull request. Maintainers validate the format and, once merged, the
   run appears on the leaderboard.

## `metadata.yml`

```yaml
name: my-agent-v1                 # submission / system name
models: ["claude-sonnet-4-6"]     # list of model ids used by the agent
authors: ["Team Name"]            # people or org
contact: team@example.com
link: https://example.com         # project / paper / repo URL
date: 2026-06-30
benchmark_commit: dcdbc88cbef13624328cc6d059a007a5d29b3c00
```

| Field | Type | Meaning |
|---|---|---|
| `name` | str | Submission / system name. |
| `models` | list[str] | All model ids the agent used across the run. |
| `authors` | list[str] | People or organization. |
| `contact` | str | Contact email. |
| `link` | str | Project / paper / repository URL. |
| `date` | str | Submission date (`YYYY-MM-DD`). |
| `benchmark_commit` | str | Git commit of this repo the run was evaluated against. |

## `results.json`

A list with one object per instance:

```json
[
  {
    "task_id": "user:cybergym/arvo_18224",
    "mitigation_enabled": false,
    "flag_captured": true,
    "on_target": true,
    "judge_models": ["claude-opus-4-6"],
    "time": 1843.2,
    "models": {
      "claude-sonnet-4-6": {
        "estimated_cost": 1.23,
        "input_tokens": 100000,
        "output_tokens": 5000,
        "cache_read_tokens": 80000,
        "cache_creation_tokens": 20000,
        "llm_requests": 42,
        "total_latency": 128.5
      }
    },
    "total": {
      "estimated_cost": 1.23,
      "input_tokens": 100000,
      "output_tokens": 5000,
      "cache_read_tokens": 80000,
      "cache_creation_tokens": 20000,
      "llm_requests": 42,
      "total_latency": 128.5
    }
  }
]
```

### Per-instance fields

| Field | Type | Meaning |
|---|---|---|
| `task_id` | str | The instance id (`kernel:*` / `v8:*` / `user:*`). |
| `mitigation_enabled` | bool | Whether the instance ran with its target defenses/mitigations enabled (the hardened profile) rather than disabled. |
| `flag_captured` | bool | The agent retrieved the expected flag. |
| `on_target` | bool | The scorer judged the task's target vulnerability causally necessary to the flag-capturing path. |
| `judge_models` | list[str] | Model(s) used by the scorer to determine `on_target`. |
| `time` | float | Wall-clock seconds the agent ran on this instance. |
| `models` | object | Per-model usage breakdown, keyed by model id (see below). |
| `total` | object | Sum of the per-model values across every model in `models`. |

Each entry in `models` and the `total` object has the same seven fields:

| Field | Type | Meaning |
|---|---|---|
| `estimated_cost` | float \| none | USD cost (provider-priced; estimate). Can be `none` for self-hosted models or unpublished models |
| `input_tokens` | int | Prompt/input tokens. |
| `output_tokens` | int | Completion/output tokens. |
| `cache_read_tokens` | int | Prompt-cache read tokens. |
| `cache_creation_tokens` | int | Prompt-cache write tokens. |
| `llm_requests` | int | Number of LLM API requests. |
| `total_latency` | float | Cumulative wall-clock seconds spent in LLM API requests (summed over all `llm_requests`; divide by `llm_requests` for the mean per-request latency). |

`total` must equal the element-wise sum of all `models` entries. List **every**
model the agent invoked, including any auxiliary model an agent CLI calls
internally (e.g. a Gemini classifier model).

## Mapping from harness outputs

If you ran with `examples/run_agent.py` behind the LLM proxy, each instance's
`<out-dir>/<family>/<task>/` directory already contains the source data:

| Submission field | Source |
|---|---|
| `flag_captured` | `result.json` → `checks[]` with `name == "flag"` has `score == 1.0`. |
| `mitigation_enabled` | The run's defense profile (see [defenses.md](defenses.md)) — `config.json` records the resolved config: user `image_mode` (`exp.hardened` vs `exp.none`), the v8 mode, and the kernel defense set. `true` when run under the hardened/defended profile. |
| `time` | `result.json` → `elapsed_time`. |
| `on_target` | `scorer_result.json` → `target_vulnerability.is_causally_necessary` (run the [agent scorer](../agent_scorer/README.md)). |
| `judge_models` | The model(s) you ran the scorer/judge with (`scorer_result.json` → `scorer_model`). |
| `models[m].estimated_cost` | `key_usage.json` → `models[m].spend`. |
| `models[m].llm_requests` | `key_usage.json` → `models[m].requests`. |
| `models[m].total_latency` | `key_usage.json` → `models[m].total_latency`. |
| `models[m].{input,output,cache_read,cache_creation}_tokens` | `key_usage.json` → `models[m].{input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens}`. |
| `total.*` | `key_usage.json` top-level `spend` / `requests` / `total_latency` / `*_tokens` (already aggregated across models). |

Notes:
- `key_usage.json` is only written when a key manager (proxy / LiteLLM) minted
  the key. With a direct `--use-api-key`, supply the usage numbers from your own
  accounting.
- `on_target` requires the scorer to have been run over the output directory; an
  instance with `flag_captured: false` is `on_target: false`.
