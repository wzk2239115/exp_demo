# 354408144: V8 Sandbox Bypass: AAR/W via WASM signature confusion in Wasm-to-JS wrapper through PodArrayOfWasmValueType overwrite

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

V8 sandbox bypass, arbitrary address read/write via WASM signature confusion in Wasm-to-JS (both generic & compiled) wrapper through PodArrayOfWasmValueType overwrite using in-sandbox primitives.

JS functions imported into Wasm are represented with `WasmApiFunctionRef`, which is a `TrustedObject` that uses `sig: PodArrayOfWasmValueType` to represent its signature. `PodArrayOfWasmValueType` is a small wrapper on top of a `ByteArray`, representing arrays of `wasm::ValueType` with return count accompanied for bookkeeping the number of return types and parameter types.

**Unfortunately, even when `TrustedObject` is used only the plain values written inside the trusted object can be trusted - any references back to the sandbox must not be trusted.** In this case, `WasmApiFunctionRef` itself is a `TrustedObject` and the handle `sig: PodArrayOfWasmValueType` cannot be overwritten. However, as this is a handle back to the sandbox the in-sandbox data can be freely modified by an attacker with in-sandbox primitives.

Currently, in-sandbox object held within `TrustedObject` is only "protected" by security-by-obscurity. Although we may not be able to directly obtain a handle pointing to `sig` within the sandbox, attackers with in-sandbox exploit primitives can search the sandbox region to find and modify matching objects. This is not only a problem with the `sig` field - all non-`ProtectedPointer` handles within the `TrustedObject` are subject to the same problem.


### VERSION

V8 Version: 9b9d02b07c231de5046a87ac80d4bbe24a737097


### REPRODUCTION CASE

Repro added as `wasm2js-sig-overwrite.js`.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Sandbox violation (likely P2 / S3)


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n)
```

## Vulnerability Description

Shorter version of the same Wasm serialized signature corruption exploit. Loads wasm-module-builder.js via d8.file.execute('test/mjsunit/wasm/wasm-module-builder.js'). Finds ByteArrayMap dynamically from a dummy WebAssembly.Tag object. Searches for the serialized signature ByteArray starting at the dummy_tag_ptr and overwrites its ref type field at offset 0xc from kRef to kI64. Calls boom(Sandbox.targetPage - 7n, 0x42n).

## Capabilities

Arbitrary 64-bit write to any address outside the sandbox via serialized signature corruption. Same technique as Group 1. Requires external wasm-module-builder.js and --sandbox-testing.
