# 382291459: Arbitrary Wasm type confusion due to missing struct field mutability check on canonicalization

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

#### Summary

Arbitrary Wasm type confusion due to missing struct field mutability check on canonicalization. Mutability checks are missing for struct fields at [`CanonicalEquality::EqualStructType()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/canonical-types.h;drc=a4d354fa54ba3e6a0f061c6b959be408ead5db95;l=326), allowing type confusion between arbitrary Wasm types.

This is a variant of b/381696874.


#### Details

I've pointed out in b/381696874 that if we have a broken `CanonicalEquality` check that may be exploitable, we can use the birthday attack to cause a hash collision and trigger the bug. [`CanonicalEquality::EqualStructType()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/canonical-types.h;drc=a4d354fa54ba3e6a0f061c6b959be408ead5db95;l=326) is missing mutability checks for its fields:

```cpp
    bool EqualStructType(const CanonicalStructType& type1,
                         const CanonicalStructType& type2) const {
      return std::equal(
          type1.fields().begin(), type1.fields().end(), type2.fields().begin(),
          type2.fields().end(),
          std::bind_front(&CanonicalEquality::EqualValueType, this));
    }
```

This can be exploited by a casting chain of `struct {const ref null none} -> struct {const ref null any} -> struct {mut ref null any}` where the last cast is due to broken canonicalization, and the first cast is through legal subtype relationship. This allows us to overwrite `ref null none` with a value of `ref null any` type, resulting in arbitrary Wasm type confusion.

The attached PoC/exploit has a precomputed hash-colliding struct type that uses either `const ref null any` or `mut ref null any` for its 40 field types.


#### Bisect

Bug likely introduced by https://crrev.com/c/6049646 in M133 that attempts to fix b/379009132 by removing relative type indexs from canonical types. Note that the commit is already backported to [M132](https://crrev.com/c/6049645) and [M131](https://crrev.com/c/6049646).


### VERSION

- M133: https://crrev.com/c/6049646
- M132: https://crrev.com/c/6049645
- M131: https://crrev.com/c/6049646

Chrome Version: 131.0.6778.108, 132.0.6834.32, 133.0.6848.0 ~ latest  
Operating System: All


### REPRODUCTION CASE

Attached as `poc.js` which exploits the hash collision + type confusion to obtain in-sandbox exploit primitives, and then crashes on arbitrary caged write attempt.

Also attached is yet another full exploit `exp.html` that pops `calc` on Windows x64 Chrome, tested against Canary 133.0.6877.0.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Renderer  
Crash State: Crashes on arbitrary caged write attempt from JIT-compiled Wasm function (on d8, `poc.js`), arbitrary code execution (on Chrome, `exp.html`)


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n) of CMU CyLab
```

## Vulnerability Description

Large self-contained exploit (wasm-module-builder inlined). Uses the same canonical type index hash collision technique as issue 381696874, but with a different struct layout ($s_src_none and $s_src variants). Establishes addrof, caged_read, and caged_write via WasmGC struct type confusion. Final call: caged_write(0x42424242, 0x13371447).

## Capabilities

addrof, caged_read (arbitrary 32-bit read within V8 sandbox), caged_write (arbitrary 32-bit write within V8 sandbox). Demonstrated: caged_write(0x42424242, 0x13371447).
