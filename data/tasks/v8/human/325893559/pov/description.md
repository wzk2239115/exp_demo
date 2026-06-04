# 325893559: Debug check failed: index < length() (2 vs. 1)

## ClusterFuzz Report

```
## Title:
Debug check failed: index < length() (2 vs. 1)

## Component:
Blink>JavaScript>Runtime


## Description:
While auditing codes related to the newly shipped generic wasm-to-js wrapper, I found this vulnerability in the tier-up logic.

This is an OOB vulnerability during getting the ref of indirect function from `WasmDispatchTable` in `Runtime_TierUpWasmToJSWrapper`.

Crashed lines: both 'https://source.chromium.org/chromium/chromium/src/+/main:v8/src/runtime/runtime-wasm.cc;l=617' and 'https://source.chromium.org/chromium/chromium/src/+/main:v8/src/runtime/runtime-wasm.cc;l=688'. Like:

```cpp
  if (WasmApiFunctionRef::CallOriginIsImportIndex(origin)) {
    int func_index = WasmApiFunctionRef::CallOriginAsIndex(origin);
    ImportedFunctionEntry entry(instance_object, func_index);
    entry.set_target(wasm_code->instruction_start());
  } else {
    // Indirect function table index.
    int entry_index = WasmApiFunctionRef::CallOriginAsIndex(origin);
    int table_count = trusted_data->dispatch_tables()->length();
    // We have to find the table which contains the correct entry.
    for (int table_index = 0; table_index < table_count; ++table_index) {
      Tagged<WasmDispatchTable> table =
          trusted_data->dispatch_table(table_index);
      if (table->ref(entry_index) == *ref) { // ---> [1]
        table->SetTarget(entry_index, wasm_code->instruction_start());
        // {ref} is used in at most one table.
        break;
      }
    }
  }
```


The main root cause is that in [1], `Runtime_TierUpWasmToJSWrapper` wants to use the `entry_index` to directly get the function ref from **each**  WasmDispatchTable.

However, tables may have different sizes. If we use a large `entry_index` that exceeds the length of one WasmDispatchTable, the OOB will occur.

The `for` loop starts with the table that has a small index. So we may arrange two tables like that:

```js
  builder.addTable(kWasmFuncRef, 1, 1)
  builder.addTable(kWasmFuncRef, 3, 3)
```

And then tier-up the 3rd function in the 2nd table.

As a result, the `for` loop will first get the 3rd function ref of the 1st table, whose length is 1. Thus an OOB will occur.

I wrote a testcase to stably trigger this vulnerability.

build on latest commit: 

```6d26d2b5f88fbb3e3ea7020c2ec16e47ed1aceb6```

build command:

```python3 tools\dev\gm.py x64.debug```

run command (under `v8`, cause it needs the `test/mjsunit/wasm/wasm-module-builder.js`):

```out\x64.debug\d8.exe --wasm-wrapper-tiering-budget=1 poc.js```

Crash Log:
```log
#
# Fatal error in ..\..\src\wasm\wasm-objects-inl.h, line 335
# Debug check failed: index < length() (2 vs. 1).
#
#
#
#FailureMessage Object: 0000001B533FD160
==== C stack trace ===============================

        v8::base::debug::StackTrace::StackTrace [0x00007FF890FB5FF5+37]
        v8::platform::`anonymous namespace'::PrintStackTrace [0x00007FF8B4F6AD29+57]
        V8_Fatal [0x00007FF890F86ED7+295]
        v8::base::`anonymous namespace'::DefaultDcheckHandler [0x00007FF890F868AC+44]
        V8_Dcheck [0x00007FF890F86FC6+86]
        v8::internal::WasmDispatchTable::ref [0x00007FF8015DA06A+154]
        v8::internal::__RT_impl_Runtime_TierUpWasmToJSWrapper [0x00007FF803188A28+3624]
        v8::internal::Runtime_TierUpWasmToJSWrapper [0x00007FF8031878FF+383]
        Builtins_WasmCEntry [0x00007FF805C0EA75+181]
        Builtins_WasmToJsWrapperCSA [0x00007FF805BD95F8+696]
        (No symbol) [0x00000114643C18F4]
```

## VERSION
Chrome Version: Tested on v8 12.3.0

Operating System: Tested on Windows 11


## BISECT:
I think the commit that shipped the generic wasm-to-js wrapper is the latest bisect for this vulnerability.
Before this commit, we may need an experimental flag: `--wasm-to-js-generic-wrapper`.

https://chromium-review.googlesource.com/c/v8/v8/+/5259577
```
[wasm] Enable generic wasm-to-js wrapper by default

Bug: v8:14035, chromium:1489280
Change-Id: I6b45d6c1b88d76591be913a8798722ec0eadb4e2
Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/5259577
Commit-Queue: Andreas Haas <ahaas@chromium.org>
Reviewed-by: Clemens Backes <clemensb@chromium.org>
Cr-Commit-Position: refs/heads/main@{#92183
```

But the root commit that introduced this vulnerability should be:

https://chromium-review.googlesource.com/c/v8/v8/+/4738319
```
Reland "[wasm] Wrapper tierup for the generic wasm-to-js wrapper"

This is a reland of commit 20c285f21c83ac2b37617d772618657e20beb0f8

Fixes:
The CL got reverted because of a failing isolate test. Like other
tier-up tests the new test does not work for isolate tests, therefore
I skip the test now for isolate tests.

Other changes:
I added one more flag guard, and I removed CHECKs which were actually
not necessary. Maybe this is what caused the performance regression?

...

Bug: v8:14035
Change-Id: Ia2965e1e6f95fd098c614fb44bda0a3cfd7d782c
Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/4738319
Reviewed-by: Thibaud Michaud <thibaudm@chromium.org>
Commit-Queue: Andreas Haas <ahaas@chromium.org>
Cr-Commit-Position: refs/heads/main@{#89310}
```


## FIX PATCH:

Check the bound of the table first.

```patch
--- a/src/runtime/runtime-wasm.cc
+++ b/src/runtime/runtime-wasm.cc
@@ -614,7 +614,7 @@ RUNTIME_FUNCTION(Runtime_TierUpWasmToJSWrapper) {
     for (int table_index = 0; table_index < table_count; ++table_index) {
       Tagged<WasmDispatchTable> table =
           trusted_data->dispatch_table(table_index);
-      if (table->ref(entry_index) == *ref) {
+      if (entry_index < table->length() && table->ref(entry_index) == *ref) {
         canonical_sig_index = table->sig(entry_index);
         break;
       }
@@ -685,7 +685,7 @@ RUNTIME_FUNCTION(Runtime_TierUpWasmToJSWrapper) {
     for (int table_index = 0; table_index < table_count; ++table_index) {
       Tagged<WasmDispatchTable> table =
           trusted_data->dispatch_table(table_index);
-      if (table->ref(entry_index) == *ref) {
+      if (entry_index < table->length() && table->ref(entry_index) == *ref) {
         table->SetTarget(entry_index, wasm_code->instruction_start());
         // {ref} is used in at most one table.
         break;
```

## CREDIT:

5fceb6172bbf7e2c5a948183b53565b9
```

## Vulnerability Description

Self-contained version of the same tier-up crash PoC with the full wasm-module-builder.js inlined (~2300 lines). Same two kWasmFuncRef tables and iteration=1000 at the end. Identical logic to 53738825_poc.js.

## Capabilities

Crashes the process (CHECK failure: IsWasmExportedFunction). No memory read/write.
