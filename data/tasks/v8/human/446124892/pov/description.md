# 446124892: Wasm type confusion due to missing exactness check on JS-Wasm boundary

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

#### Summary

Wasm type confusion due to missing exactness check on JS-to-Wasm boundary. `JSToWasmObject()` allows subtyping even for exact types, leading to type confusion when a descriptor is invalidly typed as an exact supertype and is used to instantiate a described struct.

Custom descriptors feature is exposed in the wild by default through Origin Trials from M141, which is currently at Beta and very soon reaches (Early) Stable. This bug is not caused by a recent code change and has existed from the very first feature implementation (approx. 6 months).


#### Details

WebAssembly Custom Descriptors proposal introduces exactness as part of heaptype. An object may only be typed as exact if it is exactly an instance of that type, but not for its subtypes. This is due to issues around descriptor subtyping and struct instantiation with upcasted descriptors, as traditional Wasm subtyping semantics will allow instantiating a described object with an upcasted descriptor (supertype struct), then downcasting it (subtype struct) which should be illegal. This issue is resolved by introducing exact types as part of heaptypes.

As exactness is now part of heaptype, this means that each and every type conversions must take exactness into account. However, at JS-to-Wasm boundary this is ignored and traditional subtyping rules are allowed even for exact types:

```cc
// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/wasm-objects.cc;drc=e75b1ba2a99aa352048745d44754c5de8be273d8;l=3656
MaybeDirectHandle<Object> JSToWasmObject(Isolate* isolate,
                                         DirectHandle<Object> value,
                                         CanonicalValueType expected,
                                         const char** error_message) {
  // ...
  switch (expected.heap_representation_non_shared()) {
    // ...
    default: {
      DCHECK(expected.has_index());
      CanonicalTypeIndex canonical_index = expected.ref_index();
      auto type_canonicalizer = GetWasmEngine()->type_canonicalizer();

      if (WasmExportedFunction::IsWasmExportedFunction(*value)) {
        // ...
      } else if (WasmJSFunction::IsWasmJSFunction(*value)) {
        // ...
      } else if (WasmCapiFunction::IsWasmCapiFunction(*value)) {
        // ...
      } else if (IsWasmStruct(*value) || IsWasmArray(*value)) {
        DirectHandle<WasmObject> wasm_obj = Cast<WasmObject>(value);
        Tagged<WasmTypeInfo> type_info = wasm_obj->map()->wasm_type_info();
        CanonicalTypeIndex actual_type = type_info->type_index();
        if (!type_canonicalizer->IsCanonicalSubtype(actual_type,                // [!] ignores exactness and allows any subtypes 
                                                    canonical_index)) {
          *error_message = "object is not a subtype of expected type";
          return {};
        }
        return value;
      } else {
        *error_message = "JS object does not match expected wasm type";
        return {};
      }
    }
  }
}
```

This pokes a hole in the type system exactly as described in the [proposal docs](https://github.com/WebAssembly/custom-descriptors/blob/main/proposals/custom-descriptors/Overview.md#exact-types), allowing attackers to invalidly type a descriptor `A` into an exact supertype `B`, instantiate a struct described by `B`, then invalidly cast it to another described struct that is described by `A`. This leads to type confusion between arbitrary Wasm types.


#### Bisect

Bug introduced by WebAssembly Custom Descriptors, on Origin Trials from M141 and onwards.


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

Large self-contained JS exploit (wasm-module-builder inlined), identity-import variant of the WasmGC implicit type refinement + decoder inconsistency bug. Constructs addrof, fakeobj, caged_read, caged_write, and caged_write_unsafe primitives. Ends with caged_write_unsafe(0x42424242, 0x43434343).

## Capabilities

addrof, fakeobj, caged_read, caged_write, caged_write_unsafe primitives via WasmGC type confusion (identity import variant). Demonstrated: caged_write_unsafe(0x42424242, 0x43434343).
