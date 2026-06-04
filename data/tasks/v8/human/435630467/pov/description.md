# 435630467: V8 Sandbox Bypass: In-sandbox corruption allows execution of DebugBreakTrampoline, leading to invalid tail call

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

> Another example of the meta-bug b/435630464 to show that these issues are prevalent, not only for the `v8_flags.*` gated ones. Feel free to dup this into the meta-bug if necessary, but keep in mind that every reachable code, not just ones that are "commonly used and fuzzed", need to be fixed as according to the v8 sandbox threat model.


#### Summary

As explained in b/435630464, an attacker may exploit in-sandbox corruption primitives to unlock a vast amount of dangerous or experimental code that is not fully verified or tested. This bypass uses `DebugBreakTrampoline` which is an example of a builtin that is irrelevant to feature flags (`v8_flags.*`), but is still obviously not intended under normal execution.


#### Details

`DebugBreakTrampoline` blindly trusts that the arguments supplied is sufficient for `sfi->code` and executes a [tail call](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/builtins/builtins-internal-gen.cc;drc=72c6f133031af8165bfb18b2c7cbcbca51bc6aaf;l=116) to this code. This violates Leaptiering CFI, and is also mentioned in the comments as a TODO. However, it seems that this issue has not been considered a threat due to being a debugging-only code. b/435630464 proves that this is not the case.

The bug allows the callee to pop more arguments than existing on the stack, leading to stack pointer popping above the current used stack and even the frame pointer. Execution from this state corrupts the stack which easily leads to v8sbx violations.

Attached exploit uses this bypass to tail call into a 0x100-arity function with no arguments, immediately followed by a Wasm stack spraying call that corrupts the stack. This allows the attacker to pivot the stack into fully controlled Wasm stack, resulting in PC + stack control. Both the calls are made within a wrapper function that is tiered up to avoid issues with InterpreterEntryTrampoline.



### VERSION

V8: Tested on `d8-sandbox-testing-linux-release-v8-component-101728`


### REPRODUCTION CASE

Attached as `v8sbx-unlock-debugbreaktrampoline.js`, run with `./d8 --sandbox-testing`.

> The repro already has `SharedFunctionInfo` matching that of the tested version hardcoded inside. This should work on most latest d8 builds.

The repro attempts a stack pivot into attacker-controlled Wasm stack sprayed with values 0x4242424200XX, resulting in PC + stack control.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Sandbox violation


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n) of CMU CyLab

-----

One-of-many variants of the fuzzer-found b/435630464.  
Marking any rewards for charity in advance.
```

## Vulnerability Description

Large self-contained exploit (~2500+ lines, wasm-module-builder inlined). Uses Sandbox.MemoryView, addrof, caged_read, caged_write to manipulate SharedFunctionInfo and dispatch table entries. Creates a fake SFI pointing to the DebugBreakTrampoline builtin (dispatch handle 0x87 << 1). Attaches this fake SFI to debug_fn. Tiers up target function fn (100 parameters, called 0x10000 times). Reassigns fn's SFI to debug_fn. In the exploit loop wrap_fn(debug_fn, 0x424242420000n), spray(0x424242420000n) fills the stack with the controlled value, then calling debug_fn triggers DebugBreakTrampoline which returns to the sprayed stack value, achieving PC control.

## Capabilities

Arbitrary call/PC control via DebugBreakTrampoline stack pivot. Demonstrated: return to 0x424242420000n >> 1. Requires --sandbox-testing and Sandbox.* API.
