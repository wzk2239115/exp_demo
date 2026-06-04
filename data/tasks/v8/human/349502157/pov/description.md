# 349502157: V8 Sandbox Bypass: AAR/W via table set OOB SBXCHECK_LT() bypass

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

V8 sandbox bypass, arbitrary address read/write via table set OOB check bypass using in-sandbox exploit primitives.

As `WasmTableObject`'s `current_length` and `maximum_length` fields can be overwritten, `WasmDispatchTable::Set()` employs a [`SBXCHECK_LT(index, length());`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/wasm-objects.cc;l=1883) to guard against OOB writes in the dispatch table.

However, **both `index` and `length()` are `int`**, and all code paths in:
```
WebAssemblyTableSetImpl()
-> WasmTableObject::Set()
-> WasmTableObject::SetFunctionTableEntry()
-> WasmTableObject::UpdateDispatchTables()
```
...uses a very specific mix of `int` and `uint32_t` which results in negative indices to pass all the checks when `current_length` and `maximum_length` is modified to `0xfffffffe` (`-1` in `smi`). This causes out-of-bounds write with a negative index. This allows us to overwrite another table's dispatch table and cause function type confusion, leading to AAR/W outside of the sandbox.


### VERSION

Chrome Version: ~latest (tested on v8 commit a832ff96bd41b40b9cfee90a314fa816802cf9ae)  
Operating System: all


### REPRODUCTION CASE

Repro added as `table_set_oob.js`.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Sandbox violation


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n)
```

## Vulnerability Description

Self-contained sandbox escape exploit (wasm-module-builder inlined). Builds two Wasm tables: table_v_ls (sig: i64+struct_ref, 1 element, holds 'writer') and table_v_ll (sig: i64+i64, target for corruption), plus padding tables for alignment. writer() does a struct field set; boom() does CallIndirect on table_v_ll[0]. Uses Sandbox.MemoryView to corrupt table_v_ls->current_length to (smi)-1 at offsets 0x10 and 0x14, bypassing SBXCHECK_LT. Then calls table_v_ls.set(0xfffffff9, writer) which writes at index -7 OOB, overwriting table_v_ll's dispatch table entry with writer's reference. Calling boom(ptr, val) now dispatches through table_v_ll but executes writer with mismatched types, treating the i64 address as a struct pointer and performing a controlled 64-bit write. Final call writes 0xdeadbeefcafebabe to Sandbox.targetPage.

## Capabilities

Arbitrary 64-bit write to any address outside the sandbox. Demonstrated by writing 0xdeadbeefcafebabe to Sandbox.targetPage. Full sandbox escape. Requires --sandbox-testing and Sandbox.* API.
