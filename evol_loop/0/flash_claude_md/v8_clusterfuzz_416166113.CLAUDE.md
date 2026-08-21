# Prior-run notes for v8_clusterfuzz_416166113_report.md

## Verified recon facts
- Release build (`is_debug=false`), pointer compression enabled; DCHECKs are no-ops.
- Low-level dynamic tracing (GDB) is unavailable: ptrace is blocked in this environment.
- `%DebugPrint` and `--trace-gc` work in d8; `gc()` and `--allow-natives-syntax` are not available.
- New space is small (2MB default); `Uint8Array` >64 bytes is allocated off-heap, ≤64 bytes on-heap.
- With a fixed script, object compressed-pointer offsets are deterministic across processes; cage base varies, but the gap between two sprayed objects can be stable (e.g., ~0xe0488 for one pair).
- Allocation sizes measured: `new Uint8Array(0x100)` adds ~0xc0 between allocations; a 1020-char string adds ~0x188.

## Anti-patterns to avoid
- **Repeatedly checking `--trace-gc` after tweaking allocation sizes and seeing "No GC"**: time-box this investigation; if the expected GC doesn't fire within ~20 steps, reformulate the trigger assumption instead of tuning numbers.
- **Fine-tuning a padding byte-by-byte across many runs (PADN 6500→6664)**: stop when changes don't produce a clean signal after a few iterations; switch to a coarser parameter sweep or a different placement strategy.
- **Sustained source-diving into internal GC accounting (external backing store thresholds, semi-space sizing)**: recognize this as a rabbit hole; step back to the observable behavior.
- **Scaling a placement strategy that only works under `%DebugPrint` without first testing it in a clean run**: early, verify whether your model holds without debug output; don't defer this check to the end.

## Missed signals
- When a fake object lands exactly at the target address but a subsequent read returns the target's own data, don't assume only a layout offset is wrong — consider that the receiver pointer itself wasn't relocated as expected. Test this hypothesis with a deliberately bogus pointer value in the fake to isolate the failure layer.
- If a corrected field offset still fails, question the underlying assumption about the pointer/field layout rather than re-measuring the same structure again.
- If a script depends on `%DebugPrint` having altered allocation order, check this dependency before spending many steps perfecting a layout that won't transfer to the clean environment.

## Environment notes
- The run harness (`run`) executes d8 via `su -s`, some hardening is applied; keep that in mind for how flags are passed.
- No `node` binary; use `python3` or bash for generating test files.
- Use `--format=json` for any measurement output to avoid parse bugs (stdout/stderr separation matters).
- Prefer `console.log` or stdout markers over `%DebugPrint` for final exploit verification, since debug output itself perturbs the heap and changes the layout.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
