- Use `od` and `hexdump` for binary inspection; `xxd` is not installed in this environment.
- The target binary is non-PIE with partial RELRO, so GOT addresses are fixed; `.got.plt` starts near `0xf`.
- `ptrace` is fully blocked; interactive debuggers (gdb, strace) and core dumps are unusable. Do not waste steps retrying.
- ASLR cannot be disabled; heap addresses vary between runs.
- The input file uses CR-only line terminators, which alters line-parsing behavior compared to LF.
- The crash occurs inside `ScenePreprocessor` before post-processing steps run; post-processing is never reached.
- A fuzzer found a new crash input; analyzing it was less productive than expected.

## Anti-patterns to avoid
- **Debugger attempts failing with ptrace errors**: switch immediately to source analysis and runtime instrumentation (e.g., custom tracers).
- **Reading many post-processing source files sequentially without testing**: run a ground-truth comparison of normal vs. malformed inputs early to confirm which code paths are reachable.
- **Fixing a crashing malloc interposer for many steps**: prefer simpler runtime hooks or environment variables to capture allocation info.
- **Spawning subagents to read the same source files already analyzed**: give subagents a specific, testable question (e.g., "find OOB read/write primitives in this step") and require a concrete output.

## Missed signals
- If the primary crash occurs before post-processing, that does not mean exploitation is impossible—look for inputs that avoid the early crash while still reaching later write primitives.
- If a fuzzer yields a new crash sample, analyze it immediately instead of continuing static analysis.

## Environment notes
- The container lacks `xxd` and `coredumpctl`; `/proc/sys/kernel/core_pattern` is read-only.
- `gcc` and `clang` are available; building custom test binaries and interposers works.
- Python 3.8 is present; useful for generating test inputs.
- No network access or external resources assumed.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
