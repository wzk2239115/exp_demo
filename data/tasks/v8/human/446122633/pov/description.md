# 446122633: Wasm type confusion due to wrong reachability analysis in `WasmGCTypeAnalyzer::ProcessBranchOnTarget()` with custom descriptor casts

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

#### Summary

Wasm type confusion due to wrong reachability analysis on `WasmGCTypeAnalyzer::ProcessBranchOnTarget()` with descriptor checks. Analyzer wrongly assumes that same-type casts always succeed, although with custom descriptors exactly matching casts might still fail. This can be pivoted into arbitary Wasm type confusion.

Custom descriptors feature is exposed in the wild by default through Origin Trials from M141, which is currently at Beta and very soon reaches (Early) Stable. This bug is not caused by a recent code change and has existed from the very first feature implementation (approx. 6 months).


#### Details

WebAssembly Custom Descriptors proposal introduces descriptors, and [descriptor-based type checks](https://github.com/WebAssembly/custom-descriptors/blob/main/proposals/custom-descriptors/Overview.md#new-instructions). These casts/checks require that the described struct has a descriptor that matches the given descriptor at runtime, regardless of whether the types match or not. However, `WasmGCTypeAnalyzer::ProcessBranchOnTarget()` fails to acknowledge this and assumes that any "upcasts", based purely on static types, always succeed:

```cc
void WasmGCTypeAnalyzer::ProcessBranchOnTarget(const BranchOp& branch,
                                               const Block& target) {
  DCHECK_EQ(current_block_, &target);
  const Operation& condition = graph_.Get(branch.condition());
  switch (condition.opcode) {
    case Opcode::kWasmTypeCheck: {
      const WasmTypeCheckOp& check = condition.Cast<WasmTypeCheckOp>();
      if (branch.if_true == &target) {
        // It is known from now on that the type is at least the checked one.
        RefineTypeKnowledge(check.object(), check.config.to, branch);
      } else {
        DCHECK_EQ(branch.if_false, &target);
        if (wasm::IsSubtypeOf(GetResolvedType(check.object()), check.config.to,
                              module_)) {
          // The type check always succeeds, the target is impossible to be            // [!] this is not true with custom descriptors.
          // reached.
          DCHECK_EQ(target.PredecessorCount(), 1);
          block_is_unreachable_.Add(target.index().id());                              // [!] this might actually be reachable at runtime.
          TRACE(
              "[b%uu] Block unreachable as #%u(%s) used in #%u(%s) is always "
              "true\n",
              target.index().id(), branch.condition().id(),
              OpcodeName(condition.opcode), graph_.Index(branch).id(),
              OpcodeName(branch.opcode));
        }
      }
    } break;
    case Opcode::kIsNull: {
      // ...
    } break;
    default:
      break;
  }
}
```

Interestingly, `WasmGCTypedOptimizationReducer` does acknowledge this and avoids statically eliding the type check, fixed at commit [e8bdb12b](https://crrev.com/c/6722276):

```cc
  V<Word32> REDUCE_INPUT_GRAPH(WasmTypeCheck)(
      V<Word32> op_idx, const WasmTypeCheckOp& type_check) {
    // ...
    if (type != wasm::ValueType()) {
      // ...
      bool to_nullable = type_check.config.to.is_nullable();
      if (wasm::IsHeapSubtypeOf(type.heap_type(),
                                type_check.config.to.heap_type(), module_) &&
          // When checking for a particular custom descriptor, static types
          // cannot guarantee success.
          !(IsCastToCustomDescriptor(type_check.config))) {                            // [!] acknowledges custom descriptor casts
        if (to_nullable || type.is_non_nullable()) {
          // The inferred type is guaranteed to be a subtype of the checked
          // type.
          return __ Word32Constant(1);
        } else {
          // The inferred type is guaranteed to be a subtype of the checked
          // type if it is not null.
          return __ Word32Equal(
              __ IsNull(__ MapToNewGraph(type_check.object()), type), 0);
        }
      }
      // ...
    }
    // ...
  }
```

This leads to yet another bug where reachability analysis mistakenly marks a reachable code (false-side branch of the typecheck) as statically unreachable when the branch depends on an exact descriptor check.

Exploiting such reachability analysis bug has been shown to be possible in prior reports via loop reprocessing bypass, and thus is omitted. (b/372269618, b/373703277, b/374790906, b/377620832, ...)



#### Bisect

Bug introduced by WebAssembly Custom Descriptors, on Origin Trials from M141 and onwards. More specifically, it existed from commit [26b78962](https://crrev.com/c/6402494) which implements `br_on_cast_desc`, but likely has only been exposed after commit [e8bdb12b](https://crrev.com/c/6722276) which fixes the broken cast always succeeds/fails optimization on descriptor type cast/check (which itself would have been an exploitable bug).


### VERSION

Chrome Version: M141~  
Operating System: All


### REPRODUCTION CASE

Attached as `poc.js` which exploits this issue to alias two unrelated struct types, then uses this type confusion to trigger an arbitrary caged write within the sandbox.

Also attached is `rce.html` which exploits this issue, together with the `wrapper-wasmcpt-uaf` v8sbx bypass, to gain RCE and print out `/flag/flag` to stdout.

You might want to pass `--experimental-wasm-custom-descriptors` on d8 or `--enable-blink-features=WebAssemblyCustomDescriptors` on Chrome to simulate Origin Trials behavior.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Renderer  
Crash State: Crashes on arbitrary caged write attempt from JIT-compiled Wasm function with `poc.js` / RCE with `rce.html`


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n) of CMU CSD / CyLab
```

## Vulnerability Description

Large self-contained JS exploit (wasm-module-builder inlined), variant of issue 446113731. Exploits WasmGC implicit type refinement + decoder inconsistency to construct addrof, fakeobj, caged_read, caged_write, and caged_write_unsafe primitives. Ends with caged_write_unsafe(0x42424242, 0x43434343).

## Capabilities

addrof, fakeobj, caged_read, caged_write, caged_write_unsafe primitives via WasmGC type confusion. Demonstrated: caged_write_unsafe(0x42424242, 0x43434343).
