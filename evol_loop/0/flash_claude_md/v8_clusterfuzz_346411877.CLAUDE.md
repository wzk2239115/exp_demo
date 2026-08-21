# Prior-run notes for v8_clusterfuzz_346411877_report.md
## Verified recon facts
- The challenge binary `/challenge/d8` is a **release** build supporting `--allow-natives-syntax` and `%DebugPrint` summarization, but NOT traces like `--trace-generalization` or `--trace-maps`. A local debug build lacks `OBJECT_PRINT`, so `%DebugPrint` and `--print-all` produce no output.
- All four object literals `{c: 3.0}`, `{c: 1}`, `{c: "x"}` tested share the same Map, confirming map-sharing behavior for these constants.
- A field created with `h{Class}` always generalizes to `h{Any}` when a double is stored; `t{Class}` generalization proceeds via `Tagged` representation when a double is involved.
- `CanStayConst` returns true only when the field currently contains a hole (`kTheHole`); `undefined` is not treated as uninitialized for this purpose.
- `CheckFieldType` performs **no** check when the field representation is `Tagged` (`all_fine` path).
- The header of `JSAPIObjectWithEmbedderSlots` was calculated to plan object layouts; raw field copies during map migration do not re-verify field types.
- The bug's high-level trigger is a typo in `UpdateFieldType` under a sidestep transition, causing the wrong generalized `FieldType` to be written. The fix specifically corrects this typo.
- Toolchain `gn`, `ninja`, and `clang` are present on the VM; `gdb`, `lldb`, `ptrace`, and core dumps are **not** permitted, so runtime debugging requires source instrumentation.
- Network access to external V8 bug trackers works but may return response with a `)]}'` JSON prefix that must be stripped before parsing.

## Anti-patterns to avoid
- **"still building" grep loops (10+ times)**: Poll the build status once using a richer command (compiled file count, elapsed time), then immediately prep the instrumentation code for after-build execution instead of parallel source reading.
- **Deep static audit of JIT consumers (TurboFan/Maglev) ~20 steps to confirm "Tagged rep doesn't narrow type"**: If a source dive yields a likely negative result, confirm it with a quick behavioral probe on the challenge binary (e.g., `--trace-generalization`) before reading more callers.
- **Retrying a command after syntax errors without inspecting the raw output**: When fetching a commit/JSON via network, `cat`/`grep` the raw response body first to see prefixes or formatting issues before re-parsing.
- **Re-testing the same debug build flag after an empty output**: If `%DebugPrint` prints nothing, verify whether the build configured `OBJECT_PRINT` (via `args.gn` or `nm`) **before** trying alternate flag spellings for a success signal.
- **Reasoning about a failed POV in the dark**: When a conceptual test fails (e.g., constness not preserved), instrument the relevant runtime function to print ground truth **before** trying to diagnose the failure by reading more call chains.
- **Long stretches of low-yield parallel reading while a build runs**: If a build takes >100 steps, use the wait to write the next experiment script, not to re-read already-understood code.

## Missed signals
- If you discover the challenge binary is a **release** build enabling `--trace-generalization`, use it immediately to observe field-type state transitions *before* deep source analysis; delaying this costs ~25 steps.
- If you find `%DebugPrint` works on the release binary, act on it right away to probe object layouts (Map, in-object offsets) rather than pivoting to a new static analysis thread; the layout data is needed for any allocation plan.
- If a debug build finishes while you're mid-theory, run the planned instrumented experiment immediately — the report shows the session reaching that point but being cut off.

## Environment notes
- The challenge binary is already readable and runnable in the challenge dir; `cp` of `pov.js` into it failed on permissions, so adapted by running in place.
- The VM has 256 cores but the build load was high (33-61); a full debug build took ~180 steps. Pre-prepare instrumentation diffs before the build completes.
- The local V8 source tree has **no** git history, so blame/diff for the fix is unavailable locally; only online search reveals the fix.
- Only Python 3 is available as a generic scripting tool; editing source and rebuilding via `ninja` is the only sanctioned debug path.
> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
