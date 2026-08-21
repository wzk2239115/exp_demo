# Prior-run notes for v8_clusterfuzz_328280144_report.md

## Verified recon facts
- The challenge container ships a V8 12.4.0 d8 binary; `/src/v8` holds an un-gitted source snapshot (no `.git`).
- The bug is a DEBUG-only DCHECK failure in Maglev JIT deopt path; release builds behave correctly for all tested patterns.
- This d8 has had many built-in functions (e.g. `version`, `os`) stripped by a patch; alternatives like `node` in `/data` exist.
- A full debug build (`dcheck_always_on=true`) takes ~2 hours on this box (cgroup CPU quota = 4 cores). A separate `dcheck` build has ~4× targets and is not viable concurrently.
- The POV/minimized testcase from ClusterFuzz is downloadable via network; the challenge server also exposes a standard start script.
- Wasm is functional in the challenge d8.

## Anti-patterns to avoid
- **Repeatedly running release fuzzers that always print "all ok"**: this is a no-feedback loop. Stop and reconsider the hypothesis or the build configuration.
- **Reading the same Maglev compiler source paths over and over (regalloc, deopt, Phi-selector)**: when you say "I've been going around in circles", force a context switch — try a different build type, a different tool, or a different search.
- **Waiting idly for a long build while re-analyzing the same code**: instead, act on prior signals: check the downloaded testcase, inspect the challenge binaries, or query network resources.
- **Launching `ninja` without confirming its path and the correct `-j` value**: check CPU quota first; a bad job count silently destroys prior progress.
- **Ignoring a non-crashing debug build**: a clean pass is a major signal. Immediately verify the source commit/date and its relationship to the challenge before going deeper.
- **Repeatedly disassembling / re-checking the same binary or build flags**: if `--trace-maglev` output looks wrong, verify flags on the exact binary you're using, not on generic assumptions.

## Missed signals
- **If your debug build exits 0 on the POV**, that's a strong hint the source you have is post-fix. Check git history or the source date immediately—much wasted time came from ignoring this.
- **If a downloaded ClusterFuzz testcase runs without crashing**, read its flags and the harness configuration before assuming your binary is wrong; a missing prerequisite flag can explain everything.
- **If you can reach the network**, prioritize searching for the fix/history over local deep-dives. The prior run only found the root-cause CL after exhausting hours locally.

## Environment notes
- The machine reports 256 cores / huge RAM but cgroup limits to 4 CPUs (`400000/100000`). Use `-j 4` from the start for V8 builds.
- The server responds but the container needs time to start; a quick TCP connect may succeed before the service is ready, causing a stall.
- Source snapshot date and commit hash are accessible (e.g., via file dates or `REVISION` file); verify them to catch a patched checkout.
- The challenge d8's stripped binaries can be inspected with `file` and `readelf`; `node` from `/data` can act as a JS interpreter fallback.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
