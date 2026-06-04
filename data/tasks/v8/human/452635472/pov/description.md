# 452635472: Wasm type confusion due to increased kMaxCanonicalTypes limit colliding with abstract HeapType::Representation

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

> Disclaimer: The commit [3bd862a](https://crrev.com/c/7047048) landed a few hours ago, I just happened to come across it while submitting other reports. Filing this just in case fuzzers fail to pick it up, and since this is a known "things not to do".


#### Summary

Commit [3bd862a](https://crrev.com/c/7047048) that bumps `kMaxCanonicalTypes` to 2M revives CVE-2024-6100 (b/344608204) and allows Wasm type confusion.


#### Details

> TL;DR: Slide page 69 from POC2024 talk, [WebAssembly Is All You Need: Exploiting Chrome and the V8 Sandbox 10+ times with WASM](https://github.com/leesh3288/talks/blob/main/poc2024/%5BPOC2024%5D%20WebAssembly%20Is%20All%20You%20Need%20-%20Exploiting%20Chrome%20and%20the%20V8%20Sandbox%2010%2B%20times%20with%20WASM.pdf)

Bumping `kMaxCanonicalTypes` to 2M allows us to exceed canonical indices of `kV8MaxWasmTypes`. This colllides with abstract [`HeapType::Representation`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/value-type.h;drc=08d948d0d0ae9a2cd56f75ae138e54a9ea65e1a6;l=794) and leads to Wasm type confusion in e.g. [`JSToWasmObject()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/wasm-objects.cc;drc=f8449afd2a2736981d7851eb8fc6264a5bfa7c17;l=3427). 

A temporary fix can be to bump the start of `HeapType::Representation` to `kMaxCanonicalTypes` and add a `static_assert()` to guard against similar problems in the future, before it is refactored out completely.


### VERSION

V8: Tested on `d8-asan-linux-debug-v8-component-103172` which includes [3bd862a](https://crrev.com/c/7047048).


### REPRODUCTION CASE

Attached as `poc.js` which crashes on an arbitrary caged write of value 0x43434343 to caged offset 0x42424242.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Renderer


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n) of CMU CSD / CyLab
```

## Vulnerability Description

Exploit for a canonical type index collision bug in WasmGC. Inlines wasm-module-builder.js and creates a recgroup of kV8MaxWasmTypes (1,000,000) function signatures, causing the next allocated struct type to collide with a predefined canonical type index (kAny). Then a second module exploits this collision: a write() function that takes an $s0 struct (whose field has type nullref) but actually writes to an $s1 struct (whose field has type i32), achieving a type-confused write. Calls write(s1, 0x43434343) with s1 constructed as make_s1(0x42424242 - 7), writing 0x43434343 at address 0x42424242-7.

## Capabilities

Arbitrary 32-bit write within the V8 sandbox via WasmGC canonical type index collision. Writes an attacker-controlled value at an attacker-controlled sandbox address.
