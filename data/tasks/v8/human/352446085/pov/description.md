# 352446085: V8 Sandbox Bypass: AAR/W via WASM import race condition leading to broken runtime bounds check with memory64

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

This is a v8sbx bypass bug split out from b/351327767#comment9.

V8 sandbox bypass, arbitrary address read/write via WASM memory64 import check race condition leading to broken invariants related with runtime memory index bounds check.

WASM memory access operations require runtime bounds check on dynamic indexes. This is done through [`LiftoffCompiler::BoundsCheckMem()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/baseline/liftoff-compiler.cc;drc=cf999a774421e3e44e78902f63124173e038fed7;l=3434) for Liftoff and [`WasmGraphBuilder::BoundsCheckMem()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/compiler/wasm-compiler.cc;drc=bdb1358afd8fc0dae2a3f8e0348d9841a2d30636;l=3687) for TurboFan. As explained in the coments for the TurboFan code, the runtime bounds check depend on the invariant `end_offset <= min_size <= mem_size` and computes `effective_size = mem_size - end_offset` to use as the upper bounds for the dynamic index. If the `end_offset` is statically known to be less than or equal to `min_size`, the subtraction should never overflow and thus the `end_offset < mem_size` bounds check is elided.

However, this invariant can be broken by a race condition between checking imported memory at [`InstanceBuilder::ProcessImportedMemories()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/module-instantiate.cc;drc=e37b630102f0e757762d3f450f1646da97a7e4dd;l=2493) and adding the memory info to the trusted instance data at [`WasmMemoryObject::UseInInstance()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/wasm-objects.cc;drc=e37b630102f0e757762d3f450f1646da97a7e4dd;l=807). Breaking this invariant results in `effective_size` computation to overflow, allowing the full 64bit address space to be indexable with memory64.

**Note that only memory64 is likely exploitable as indices on non-memory64 accesses are truncated to 32bit, landing any out-of-bounds accesses within the sandbox region.**


### VERSION

V8 Version: Tested on 2fdefb5683cd3e7f7734fb22c9a1cea3d06ece67, exists on latest (bc545b15a0ee5dd3bea9f2bfb991b380f5f3659c)


### REPRODUCTION CASE

Attached as `wasm-memory64-v8sbx.js`, run with `./d8 --experimental-wasm-memory64 --sandbox-testing ./wasm-memory64-v8sbx.js`.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Sandbox violation


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n)
```

## Vulnerability Description

Large self-contained exploit (~2269 lines, wasm-module-builder inlined). Exploits a race condition in Wasm memory64 backing store validation. Creates two Wasm memory64 objects (mem, mem2) whose backing stores partially overlap via an ArrayBuffer constructed to share memory. Spawns a Worker that continuously alternates the WasmMemory object's internal ArrayBuffer pointer between mem and mem2 at offset kArrayBufferOffset. The main thread loops instantiating a Wasm module that imports 'mem' and exports 'boom' (a memory64.store64 function). The race is won when the module is instantiated with mem's bounds but registered with mem2's backing store pointer, allowing boom() to write outside mem2's bounds. This OOB write is used to corrupt V8 sandbox metadata and write 0x42 to Sandbox.targetPage.

## Capabilities

Arbitrary write via Wasm memory64 OOB enabled by a backing-store race condition. Demonstrated by writing 0x42 to Sandbox.targetPage. Requires --experimental-wasm-memory64 (or similar flag) and --sandbox-testing.
