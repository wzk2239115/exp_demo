# Changelog

Notable changes to the ExploitGym benchmark and tooling.

## 2026-08-05

### Tooling

- **Breaking:** the controller's token salt, flag seed, and private API key are
  no longer hardcoded constants (`DEFAULT_SALT`, `DEFAULT_FLAG_SEED`,
  `DEFAULT_API_KEY` are gone). The controller generates them per startup unless
  `CYBERGYM_SERVER_SALT` / `CYBERGYM_SERVER_FLAG_SEED` /
  `CYBERGYM_SERVER_API_KEY` are set, and logs the values to export. Shipping
  them let anything inside an agent container forge a task token or derive the
  expected flag.
- `generate_token`, `verify_token`, and `generate_flag` now require the salt /
  seed as keyword arguments and reject an empty value; the evaluators take
  `token_salt`, `flag_seed`, and `controller_api_key` (default: the matching env
  var) and raise if unset. `run_agent.py` fails fast with the missing variable
  names. See [Controller secrets](docs/eval.md#controller-secrets).
- `pre_run.py` propagates the controller secrets: exported values win, else it
  recovers them from a reused controller's log, else it mints them — and prints
  the `export` lines. It refuses to run against a reused controller whose
  secrets it cannot determine.

## 2026-06-18: 1.1 release

### Tooling

- Firewall split into an API-only **run proxy** and an allow-all **install
  proxy** on its own network, selected with `--which {run,install,both}`; the
  default allowlist is now LLM API endpoints only.
- Added a pre-agent **install phase**: agents (`DefaultInstallAgent`) install
  per-task-type deps (`INSTALL_SCRIPTS`) via the install proxy, then the
  container is locked to the API-only run network before the agent runs.
- `pre_run.py`: added `--hardened` (ASLR-on, hardened images, prints the
  matching `run_agent.py` flags) and defaulted the v8 image variant to
  `nodefense`.
- LLM proxy now blocks **provider-side external retrieval** by default (HTTP
  403): web search/fetch, MCP tools/connectors, remote `file_url` / `image_url`
  / Gemini `file_uri` / URL sources, hosted code execution, file search,
  network-enabled hosted shells (`network_policy`), Gemini grounding / URL
  context, and web-search / deep-research models. Inline `data:` images and
  client-side agent tools are unaffected; pass `--allow-web-search` to disable.
- LLM proxy keys can be scoped to specific models via `allowed_models`; other
  models are rejected with HTTP 403 (`model_not_allowed`).
- Agents (Claude Code, Codex, Gemini CLI) now log intermediate progress while
  running: every ~20 min they record elapsed time and, with a key manager, a
  snapshot of API-key usage to `usage/usage_<elapsed>.json`.
- Update judge prompt and format of scorer results.

## 2026-06: 1.0 release

The released benchmark may differ from the snapshot evaluated in the
[paper](https://arxiv.org/abs/2605.11086) (arXiv:2605.11086). The canonical task
list for each version lives in `data/task_ids/` (e.g. `data/task_ids/v1.txt`).

### Benchmark

- Initial public release: **869 instances**, including kernel 186 (kernelctf 27, syzbot
  159), user 502 (cybergym 484, nofuzz 18), v8 181 (clusterfuzz 106, human 66,
  sbxbrk 9).
- Filtered non-exploitable cases from the paper snapshot
  (**898 → 869**).
- Extend vulnerability description for syzbot targets.
- Fix command line flags for several v8 instances.
