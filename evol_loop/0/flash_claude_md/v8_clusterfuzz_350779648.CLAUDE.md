# Prior-run notes for v8_clusterfuzz_350779648_report.md
## Verified recon facts
- The provided PoV targets a `deferred_counters_`-related path that is compiled out in this build (release); the server runs a release d8 with no extra flags and behaves like the local binary.
- The server binary exposes `%`-syntax only with `--allow-natives-syntax`; `--expose-gc` is ignored. File-internal `// Flags:` comments are not parsed.
- The container lacks ninja, gn, clang (only gcc), and depot_tools; building V8 locally is infeasible. `ptrace` is blocked.
- Web access works (gitiles/Chrome logs) but is rate-limited and pagination of large commit ranges is error-prone; prefer small, explicit ranges.
- The V8 source and binary are approximately revision 48ff05d0, mid-2024; the branch is nearly identical to the 12.8 release line.

## Anti-patterns to avoid
- **Spending many steps re-verifying that a DEBUG-only code path is absent in a release binary**: after confirming via disassembly that a symbol is gone, stop and pivot to a new hypothesis.
- **Repeatedly querying the same external API endpoint that already returned an error or empty result (403, pagination loop)**: reformulate the query (e.g., use a narrower date/commit range) before retrying, or switch to reading the already-fetched data.
- **Continuing to mutate a single PoC after 10+ crashes (or lack thereof) without a new structural insight**: instead, dump the optimization graph or bytecode trace to understand *why* the trigger isn't firing, then reformulate the JS shape, not just its parameters.
- **Diving deep into a compiler pass (e.g., phi typing, write barriers) without a step-by-step trace of the generated graph**: if `--trace-opt`/graph-building flags show no compilation or an unexpected node type, fix that mismatch before adjusting the exploit trigger further.
- **Retrying a command that timed out in the background**: check if the process/output is actually available before spawning another identical run.

## Missed signals
- If a trace flag (e.g., `--trace-opt`) shows the target function is *not* being optimized, treat that as a definitive "this trigger won't work" signal and switch approach, rather than testing more variants.
- If an OSR phi remains a tagged Number instead of being untagged to Int32, this type mismatch is the crux of the trigger; act on that specific observation to reshape the loop, not just lengthen it.
- If a `--print-code` flag crashes the binary, consider it a tooling defect and move on; do not retry with similar printing flags.

## Environment notes
- The server is reachable and runs d8 on a temp file with no flags; small scripts execute normally. Benchmark timing is ~similar to local, confirming a release build.
- Physical memory/CPU is limited — large loop benchmarks (20M iterations) work slowly; keep test cases small and bounded to avoid timeouts.
- Background commands (`&`) can lose output; prefer foreground execution with explicit timeouts for reliable tracing.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
