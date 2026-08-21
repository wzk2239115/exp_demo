# Prior-run notes for user_nofuzz_GHSA-44mr-8vmm-wjhg_report.md
## Verified recon facts
- The target binary `/out/instantiate` is a libFuzzer build; its version differs from both mainline and local v2.0.2 sources in expected ways (files moved, behavior changed).
- The fuzz input decodes via `wasm-smith` 0.11.6; local builds of a harness require pinning `arbitrary` to a compatible version (1.1.0 is not compatible).
- The bug triggers only under a pooling allocator config with `memory_pages = 0` AND `static_memory_bound` derived from a zero maximum. That combination makes the compiled guest code behave unexpectedly (traps or zero-size allocations).
- `/out/instantiate` panics at `cow.rs:583` on the provided PoC; it is a patched build for this specific crash. A non-patched build should exist elsewhere in the separator's sandbox — look for it before assuming you need to bypass the fix.
- `pahole` is NOT available; use `gdb` only if ptrace is permitted (it is not in this sandbox — `Operation not permitted`).

## Anti-patterns to avoid
- **Reading the same source file >2 times without new info** (e.g., `MemoryImageSlot::create`, `reset_with_anon_memory`, `MemoryStyle::for_memory`): switch to writing a small reproducer or grepping for call sites instead of re-reading prose.
- **Chasing mainline repo history** when the target version differs: the files moved and logic diverged; use `git log`/`git show` on the exact commit, not HEAD.
- **Re-verifying a fact already confirmed** (e.g., the panic frame): log it once, then move on. The prior run re-confirmed the same panic 3 times.
- **Using `xxd` when it's missing** — check availability early; switch to `od` or Python.
- **Deep-diving into a specific allocator path for 30+ steps** without formulating a testable hypothesis: if you've spent >20 steps on the same function and haven't produced a candidate input, step back and try to trigger it via fuzzing/harness instead.
- **Spinning up a 200k-input search without a precise filter** — the first filter produced candidates, then was proven wrong (nmem=0 instead of ≥1). Quarantine filter validation as its own mini-step.

## Missed signals
- Half of the generated candidates ran "OK" (no panic) — that split is valuable, but the run did not analyze WHY one half is OK and the other panics. If you see a clean binary split, investigate the differing characteristic first.
- The config has a `static_memory_bound` mapping that was discovered but never pushed further: check whether any generator config allows `bound > 0` while `pages = 0`.
- The `start` function's execution order relative to the crashing `drop` was never determined. If you can reach the drop with guest-controlled state, that is likely the intended path.

## Environment notes
- The container has huge resources (256 cores, 502 GB RAM, 10 TB disk) — use parallel fuzzing/compilation freely.
- The shell cwd resets to `/workspace` after some builds; `cd` into the harness directory explicitly before running.
- Network access appears unrestricted; the full git history is available locally.
- The crash occurs during instance teardown (`drop`), not during instantiation — timing of when the runtime cleans up memory is central.
- The handler is `instantiate(wasm, ...)`: it instantiates the module and then drops it; the bug fires after execution, not while running guest code.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
