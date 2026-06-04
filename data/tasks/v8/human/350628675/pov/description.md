# 350628675: V8 Sandbox Bypass: AAR/W via WASM dispatch table index OOB from `WasmTableObject.uses`

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

V8 sandbox bypass, arbitrary address read/write via WASM dispatch table index OOB where the index is fetched from `WasmTableObject.uses`. This index value can be modified with in-sandbox exploit primitives.

`WasmTableObject` holds `uses`, which is a even-sized FixedArray holding pairs of `<WasmInstanceObject, table_index smi>`. This is used to update the dispatch table linked to this table object. Both the values are modifiable with in-sandbox exploit but the index is not checked to be within bounds of the `ProtectedFixedArray<WasmDispatchTable>` (ex: [`WasmTableObject::Grow()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/wasm-objects.cc;l=249;drc=2fdefb5683cd3e7f7734fb22c9a1cea3d06ece67) -> [`WasmTrustedInstanceData::EnsureMinimumDispatchTableSize()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/wasm-objects.cc;l=1136;drc=2fdefb5683cd3e7f7734fb22c9a1cea3d06ece67)). This allows OOB access within the trusted region. With controlled data sprays on the trusted region, this can be exploited to obtain arbitrary address read/write.


### VERSION

V8 Version: 2fdefb5683cd3e7f7734fb22c9a1cea3d06ece67


### REPRODUCTION CASE

To be uploaded - the problem seems clear, but the PoC is currently WIP :)


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Sandbox violation


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n)
```

## Vulnerability Description

Full sandbox escape exploit leveraging the WasmTableObject uses-array index bug. Creates thousands of spray WasmDispatchTable objects (DT_SPRAY range) and target dispatch tables (DT_TARGET range) at known offsets using a large number of kWasmFuncRef tables. Carefully positions canonical type indices to fabricate a fake WasmDispatchTable in the trusted heap. Corrupts the table_fa uses-array index to point into the fake dispatch table's signature field, then calls table_exp0.grow(1) to trigger the OOB write. This overwrites the saved signature (sig field) of entry 0xf in a real dispatch table from $sig_v_ls to $sig_v_ll. Then calls boom_i(Sandbox.targetPage - 7n, 0x42n) which executes writer via call_indirect with the wrong signature, writing 0x42 to Sandbox.targetPage. Requires wasm-module-builder.js from Group 1.

## Capabilities

Arbitrary 64-bit write to any address outside the sandbox via WasmDispatchTable signature corruption. Demonstrated by writing 0x42 to Sandbox.targetPage. Requires --sandbox-testing and Sandbox.* API.
