# 349529650: V8 Sandbox Bypass: AAR/W via function import signature check race

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

V8 sandbox bypass, arbitrary address read/write via function import signature check bypass through race condition using in-sandbox exploit primitives.

Imported functions are processed through `InstanceBuilder::ProcessImportedFunction()`, where various checks are performed in `WasmImportData::ComputeKind()`. Signature checks are performed in https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/module-instantiate.cc;l=698, where we access `WasmExportedFunction -> SharedFunctionInfo -> TrustedFunctionData`. However, we access this once again starting from the `WasmExportedFunction` at https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/module-instantiate.cc;l=1874 when we actually add the function call target to the imported entry dispatch table.

This opens up a race window where we can race two `TrustedFunctionData` values: one malicious with differing signature, and one benign with matching signature. Once we pass the first check with the benign `TrustedFunctionData` and then add the malicious one to the dispatch table (benign -> malicious case), we can cause a signature mismatch at `call` (NOT `call_ref` which is signature hash checked) and obtain AAR/W. If the race condition is not satisfied, we either instantiate the WASM module with the benign function (benign -> benign case) or simply throw a `LinkError` (malicious -> ? case) which we can catch from JS, thus we obtain a 100% success rate.


### VERSION

Chrome Version: ~latest (tested on v8 commit a832ff96bd41b40b9cfee90a314fa816802cf9ae)  
Operating System: all


### REPRODUCTION CASE

Repro added as `function_import_race.js`.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Sandbox violation


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n)
```

## Vulnerability Description

Self-contained sandbox escape exploit using a race condition (wasm-module-builder inlined). Module 0 exports 'writer' (struct field set, sig: i64+struct_ref) and 'dummy' (no-op, same sig). Module 1 imports 'writer' under sig i64+i64 (mismatched) and exports 'boom' which calls the import directly. Uses Sandbox.MemoryView to read writer's SharedFunctionInfo and its TrustedFunctionData pointer. Spawns a Worker that races continuously: alternating setField(writer_sfi, 4, dummy_tfd) and setField(writer_sfi, 4, writer_tfd). The main thread repeatedly instantiates module 1 and calls boom(). The race causes the signature check to pass with dummy_tfd (which has the i64+i64 signature) while the actual function body executes with writer's code (i64+struct_ref), resulting in type confusion. When the race wins, boom(ptr, val) causes writer to treat the i64 val as a struct pointer and write to ptr, achieving arbitrary 64-bit write to Sandbox.targetPage.

## Capabilities

Arbitrary 64-bit write to any address outside the sandbox via a race condition on function import signature validation. Demonstrated by writing 0xdeadbeefcafebabe to Sandbox.targetPage. Requires --sandbox-testing and Sandbox.* API. Probabilistic; loops until race is won.
