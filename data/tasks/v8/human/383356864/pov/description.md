# 383356864: WasmGCTypeAnalyzer improperly revisits single-block loops, leading to type confusion

## ClusterFuzz Report

```
`WasmGCTypeAnalyzer` is a Turboshaft analyzer responsible for inferring known type information for various operations, which can then be used by `WasmGCTypedOptimizationReducer` to potentially remove some type checks at compile time. To do this, it traverses the Turboshaft graph while keeping track of which types might be encountered at any particular point in the code. When encountering a loop, the analyzer keeps revisiting the loop body indefinitely until the type feedback stabilizes - this is intended to ensure that the loop backedge's type feedback is properly accounted for. The analyzer revisits the loop's body by calling `iterator.MarkLoopForRevisitSkipHeader()` - the loop header has already been revisited while trying to determine whether the type feedback stabilized, so it is skipped here, presumably as an optimization.

However, this assumption / optimization doesn't account for single-block loops, which can occur in the Turboshaft graph when compiling infinite loops without any branches. For these loops, the loop header contains the entire loop body, effectively turning `iterator.MarkLoopForRevisitSkipHeader()` into a No-Op, and preventing the loop from being revisited any additional times. This cuts the fixed-point analysis short after two iterations: one initial visit, and one additional visit as part of the check to determine whether the type feedback stabilized. As such, `WasmGCTypeAnalyzer` might report incorrect type feedback to `WasmGCTypedOptimizationReducer` when the loop's type information does not stabilize after two iterations (which can be the case because of, for example, a chain of Phis), which can lead to type checks being incorrectly removed, resulting in type confusion.

See attached two files:
 - `poc.js`: this contains a minimal POC which utilizes this bug to create and dereference a fake object, resulting in a crash. This POC has been reproduced with an D8 optdebug build (commit `86ffa19a533bdec3b9ce4a56106a2d9e8015e108`) on an x86-64 Linux machine.
 - `exploit.js`: this contains a full Chromium exploit chain, utilizing this bug + unprotected PartitionAlloc metadata to demonstrate an attacker controlled write outside of the sandbox. This exploit has been tested and confirmed to work on Chromium 131.0.6778.108 on an x86-64 Linux machine, using `--js-flags="--turboshaft-wasm"` to enable Turboshaft for Wasm. Note that this class of sandbox escape (namely manipulating exposed `SlotSpanMetadata` objects) has been used in other exploit chains to achieve full RCE; this exploit stops short of achieving RCE, only demonstrating attacker controlled writes, since further exploitation requires hardcoding offsets for specific Chromium builds, which reduces the general reproducibility and reliability of the exploit.

A potential fix for this bug would be to not use `MarkLoopForRevisitSkipHeader` for revisiting single block loops, and instead use `MarkLoopForRevisit` for this particular edge case. A sample patch of such a fix could look as follows:
```diff
@@ -61,8 +61,14 @@ void WasmGCTypeAnalyzer::Run() {
         if (needs_revisit) {
           block_to_snapshot_[loop_header.index()] = MaybeSnapshot(snapshot);
           // This will push the successors of the loop header to the iterator
-          // stack, so the loop body will be visited in the next iteration.
-          iterator.MarkLoopForRevisitSkipHeader();
+          // stack, so the loop body will be visited in the next iteration. If
+          // this is a single-block loop, then there are no successors - as such
+          // revisit the entire loop (consisting of just the header) in this
+          // case.
+          if (block.index() != header.index()) {
+            iterator.MarkLoopForRevisitSkipHeader();
+          } else {
+            iterator.MarkLoopForRevisit();
+          }
         }
       }
     }
```

Reporter Credit: if applicable, please credit my pseudonym Popax21 in regards to this report.
```

## Vulnerability Description

Exploit using the Turboshaft phi-chain type confusion. Establishes addrof, fakeobj, hread32, hwrite32 primitives via the confuse/pwn Wasm module. Builds proper primitives using an object holder. Demonstrates arbitrary write via PartitionDirectUnmap technique: constructs a fake SlotSpanMetadata and PartitionDirectMapExtent, then frees a sacrificial buffer to trigger write_unlink(0x133713371337n, 0x1234n).

## Capabilities

addrof, fakeobj, arbitrary 32-bit read/write (hread32/hwrite32), PartitionDirectUnmap-based arbitrary write. Demonstrated: write_unlink(0x133713371337n, 0x1234n).
