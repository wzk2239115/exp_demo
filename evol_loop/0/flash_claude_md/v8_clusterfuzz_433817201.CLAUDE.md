# Prior-run notes for v8_clusterfuzz_433817201_report.md
## Verified recon facts
- V8 checkout at `/src/v8`; building a debug binary takes ~75 minutes even with 256 cores; release binary is fast to build and suitable for graphs.
- The bug is in the Maglev compiler's handling of a specific array method when the index has an "empty" type (no bits set), leading to a DCHECK failure in debug builds.
- `--print-maglev-code`, `--print-maglev-graph`, and `--trace-maglev-graph-building` work on the release build; `--print-code`/`--print-opt-code` are locked out.
- The upstream fix for this exact issue is reachable from the container's network via GitHub's V8 mirror; googlesource APIs may need multiple attempts to yield diffs.
## Anti-patterns to avoid
- **Repeatedly polling the build status (10+ times)**: each check returns "still building"—use the wait to digest already-collected graph dumps or write a targeted probe, not to re-read the same source.
- **Re-fetching the same fix commit via different APIs**: when one URL format works, stick to it; stop after the diff is saved locally.
- **Reading the same function's source more than twice**: save key code snippets to a file; re-open only if the surrounding behavior changes.
- **Testing a call pattern that the source already shows is polymorphic**: if a reduction requires a direct call, a `.call()` wrapper likely bypasses it—skip that path early.
- **Long source-auditing sessions during build waits**: if you haven't formed a novel testable hypothesis after ~10 pages, switch to running a new probe on the release build.
## Missed signals
- **`IsEmptyNodeType` checks inside check-folding paths (e.g., `BuildCheckMaps`)**: if you notice this, probe whether an empty-typed constant can skip a type check and access the wrong object's property—this was noted but never empirically followed up.
- **Graph dumps showing shared constant nodes across receiver and index**: act on that finding by tweaking the test input, not by re-reading the builder code.
## Environment notes
- `ninja` may not be on PATH; use the full path or invoke the build tool explicitly.
- The container has internet access, 256 cores, and 502GB RAM; no local git history of V8 exists, so fetch patches externally.
- The release d8 binary runs reproducers without crashing even when the DCHECK would fire in debug; use graph tracing to verify whether a code path actually triggers.
> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
