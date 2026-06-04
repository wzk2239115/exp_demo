# 373703277: DCHECK failure in Handle<To> v8::internal::Cast(Handle<From>, const v8::SourceLocation &) [To = v8

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

#### Summary

Simple variant of b/372285204 and b/332081797. For (null)exnref table types [`InstanceBuilder::Build()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/module-instantiate.cc;drc=c658efa26d8eef733fd77263802d57d4efcf3c04;l=1276) uses `WasmNull` as the default value instead of JS null, resulting in type confusion.


#### Details

[`InstanceBuilder::Build()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/module-instantiate.cc;drc=c658efa26d8eef733fd77263802d57d4efcf3c04;l=1276) does not handle exnref or nullexnref types, resulting in type confusion where `WasmNull` is set as the default element for exnref / nullexnref typed table. This can further be retrieved back to JS-side through `throw_ref` and may be exploited through Turboshaft optimization - see b/372285204 and b/372269618.


#### Bisect

Bug introduced by commit [2e357c4](https://chromiumdash.appspot.com/commit/2e357c4814954c6d83c336655209e14aa53911d4) in M112 that introduced wasm null, but `exnref` types are guarded behind a staged WASM feature.


#### Suggested Fix

Use `isolate_->factory()->null_value()` for `IsSubtypeOf(table.type, kWasmExnRef, module_)` too.


### VERSION

See bisect commit release info in Chromium Dash for more info: https://chromiumdash.appspot.com/commit/2e357c4814954c6d83c336655209e14aa53911d4

Chrome Version: 112.0.5579.0 ~ latest (requires exnref, a staged WASM feature)  
Operating System: All


### REPRODUCTION CASE

Attached as `poc.js` which exploits the type confusion to retrieve a `WasmNull` back to JS, then accesses a property on it to cause a crash. Run it with `--experimental-wasm-exnref --allow-natives-syntax`, which will yield the following:

```text
0x3a8d0000fffd <Other heap object (WASM_NULL_TYPE)>
Stacktrace:
    ptr1=0x3a8d0000fffd
    ptr2=(nil)
    ptr3=(nil)
    ptr4=(nil)
    ptr5=(nil)
    ptr6=(nil)
    failure_message_object=0x7fff8fca6e10

==== JS stack trace =========================================

    0: ExitFrame [pc: 0x5ee6dbabbaf6]
    1: StubFrame [pc: 0x5ee6dbbbdb53]
    2: /* anonymous */ [0x3a8d001a6781] [./poc.js:2391] [bytecode=0x1f7f00040c65 offset=8563](this=0x3a8d00181a25 <JSGlobalProxy>)
    3: InternalFrame [pc: 0x5ee6dba1561c]
    4: EntryFrame [pc: 0x5ee6dba1535f]

==== Details ================================================

[0]: ExitFrame [pc: 0x5ee6dbabbaf6]
[1]: StubFrame [pc: 0x5ee6dbbbdb53]
[2]: /* anonymous */ [0x3a8d001a6781] [./poc.js:2391] [bytecode=0x1f7f00040c65 offset=8563](this=0x3a8d00181a25 <JSGlobalProxy>) {
...
```


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Renderer  
Crash State: Crashes on invalid property access on a wasm null object


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n) of CMU CyLab
```

## Vulnerability Description

Self-contained PoC (wasm-module-builder inlined). Creates a 1-element Wasm table with kWasmNullExnRef as the table type. Exports function f which does TableGet at index 0 then ThrowRef, catching the exception and accessing property .a. Accessing .a on a caught null exception reference triggers a type confusion or DCHECK. Requires --experimental-wasm-exnref.

## Capabilities

Triggers a DCHECK or type confusion when accessing a property of a caught kWasmNullExnRef exception object. No memory read/write.
