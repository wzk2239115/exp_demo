# 374790906: Wasm type nullability confusion due to non-nullable exnref in catch(_all)_ref

## ClusterFuzz Report

```
Another round of subtle nullability issues in opaque types exploitable through Turboshaft. The commit that introduces this issue is less than seven days old, but I've decided not to hold on to it for a week as it seems that **the exception handling spec itself might have a soundness issue** that could also affect any other engines that depend on it as ground truth.

-----

### VULNERABILITY DETAILS

#### Summary

Wasm type nullability confusion due to allowing non-nullable exn in `catch_ref` / `catch_all_ref`. These operations can catch any non-trap exceptions, including `null` that could be thrown from JS. However, the catch type is allowed to be non-nullable, resulting in type nullability confusion issue that is exploitable through Turboshaft optimization (as also demonstrated in b/372269618#comment7 and b/373703277#comment13).

Triggering this bug requires a staged Wasm feature, `--experimental-wasm-exnref`.


#### Details

From commit [7cb6188](https://chromiumdash.appspot.com/commit/7cb6188cf9132d43e6c631befb0584a47a0e7d69), it is now possible to have a non-nullable exnref catch type in `catch_ref` / `catch_all_ref` as the pushed exception is assumed to have type `ref exn`:

```cpp
      if (catch_case.kind == kCatchRef || catch_case.kind == kCatchAllRef) {
        stack_.EnsureMoreCapacity(1, this->zone_);
        Push(ValueType::Ref(HeapType::kExn));         // [!] non-nullable ref exn type
        push_count += 1;
      }
```

However, an imported JS function can throw anything including `null` which can be caught by such operations, leading to a type nullability confusion issue - "null value in non-null type" case, exploitable as per b/373703277#comment13.



Note that this change is likely based on the spec discussion in https://github.com/WebAssembly/exception-handling/issues/336, which indicates that there might be either a spec unsoundness issue or a broken exception catching mechanism in Chrome.


#### Bisect

Bug introduced by commit [7cb6188](https://chromiumdash.appspot.com/commit/7cb6188cf9132d43e6c631befb0584a47a0e7d69) that allows non-nullable exn catch type.


#### Suggested Fix

Revisit the spec discussion in https://github.com/WebAssembly/exception-handling/issues/336, and decide on one of the following:
- Commit [7cb6188](https://chromiumdash.appspot.com/commit/7cb6188cf9132d43e6c631befb0584a47a0e7d69) should be reverted, i.e. `null` exceptions can be catched in Wasm
- `null` exceptions should be considered as a type of trap that cannot be caught in Wasm
- Add an implicit `AssertNotNull` after catching the exception to trap on `null` exceptions, effectively preventing null exceptions from being propagated into Wasm code


### VERSION

See bisect commit release info in Chromium Dash for more info: https://chromiumdash.appspot.com/commit/7cb6188cf9132d43e6c631befb0584a47a0e7d69

Chrome Version: 132.0.6785.0 (V8 commit [7cb6188](https://chromiumdash.appspot.com/commit/7cb6188cf9132d43e6c631befb0584a47a0e7d69)) ~ latest  
Operating System: All


### REPRODUCTION CASE

Attached as `poc.js` which exploits the type confusion via Turboshaft to obtain in-sandbox exploit primitives, and crashes on arbitrary caged write attempt. Run d8 with `--turboshaft-wasm --experimental-wasm-exnref` flags.

Also attached is yet another full exploit `exp.html` that pops `calc` on Windows x64 Chrome releases on canary versions 132.0.6785.0 ~ latest. Run Chrome with `--enable-features=WebAssemblyTurboshaft --js-flags=--experimental-wasm-exnref --no-sandbox` flags.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Renderer  
Crash State: Crashes on arbitrary caged write attempt from JIT-compiled Wasm function (on d8), arbitrary code execution (on Chrome)


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n) of CMU CyLab
```

## Vulnerability Description

Large self-contained exploit (wasm-module-builder inlined). Uses the same WasmNull/ExnRef type confusion as issues 373703277. Establishes addrof, caged_read, and caged_write via the 'confuser' Wasm function. Final call: caged_write(0x42424242, 0x13371337). Functionally identical to 60216636_exp.js but submitted as a separate issue. Comments note 'still exploitable via WasmTypeCheck (ref null ToNullSentinel(T)) + Branch'.

## Capabilities

addrof, caged_read (arbitrary 32-bit read within V8 sandbox), caged_write (arbitrary 32-bit write within V8 sandbox). Demonstrated: caged_write(0x42424242, 0x13371337).
