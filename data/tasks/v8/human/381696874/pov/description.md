# 381696874: Arbitrary Wasm type confusion due to improper fix of b/380397544

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

A bit unfortunate that even after a series of patches canonicalization is still broken, we really need a proactive approach rather than reactive bug discovery & patches.

#### Summary

Arbitrary Wasm type confusion due to improper fix of b/380397544 (which attempts to fix a broken patch for b/379009132, which in turn attempts to fix a broken patch for b/371565065 + b/354408144). `HeapType` checks are missing for generic Wasm heap types at [`CanonicalEquality::EqualValueType()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/canonical-types.h;drc=592f1915dbe12bf8d6abf680e2ba029e23eeed4b;l=303), allowing type confusion between arbitrary Wasm types.


#### Details

I've pointed out in b/380397544 that after https://crrev.com/c/6035175 v8 does not distinguish between (relative) recursion group based index vs. (absolute) canonical index, which leads to different recursion group to be mistakenly canonicalized into the same index and thus lead to arbitrary type confusion between Wasm types. https://crrev.com/c/6048961 attempts to fix this by checking for relative types on type index comparison. Equality checks for `CanonicalValueType`s go through the following code at [`CanonicalEquality::EqualValueType()`](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/canonical-types.h;drc=592f1915dbe12bf8d6abf680e2ba029e23eeed4b;l=303):

```cpp
    bool EqualValueType(CanonicalValueType type1,
                        CanonicalValueType type2) const {
      if (type1.kind() != type2.kind()) return false;
      if (type1.has_index() &&
          !EqualTypeIndex(type1.ref_index(), type2.ref_index())) {
        return false;
      }
      return true;
    }
```

We see that if `!type1.has_index()`, that is, if the left-hand side of the equality comparison has a generic heap type, then the comparison always returns true no matter what the heap type of `type2` is. This results in the equality comparator of `Canonical(Singleton)Group` to consider different reference types to be the same under the aformentioned case and thus may lead to arbitrary Wasm type confusion again.

However, this issue is not immediately evident as we use `std::unordered_set<Canonical(Singleton)Group>` to find pre-existing canonicalization results. This uses `CanonicalHashing` as a hashing function for the hashmap. Thus, to trigger this issue we must find two different recursion group that is considered equal by `CanonicalEquality`, but which **at the same time also has a hash collision** when hashed via `CanonicalHashing`.

`CanonicalHashing` uses `base::Hasher` which is based on MurmurHash64A and thus returns a 64bit hash value. **Birthday attack allows us to find a collision in ~50% chance with 2^32 samples** which is very feasible (in minutes, if not seconds). By precomputing offline the hash values for struct types that either has `ref null any` or `ref null none` as its fields and iterating this selection for >32 fields we can easily create >2^32 different inputs that are all considerered equal by `CanonicalEquality`, but which has random-ish hash values in which we are likely to find at least a single duplicate hash value. By using such precomputed colliding struct types we can canonicalize two different struct types into the same canonical index and cause arbitrary Wasm type confusion.

The attached PoC/exploit has a precomputed hash-colliding struct type that uses either `ref null any` or `ref null none` for its 40 field types. It tries two colliding pairs, one that works before https://crrev.com/c/6055121 and one that works after that as the patch affects hashing results.


#### Bisect

Bug introduced by https://crrev.com/c/6048961 in M133 that attempts to fix b/380397544 by accounting for relative type indices. Note that the commit is already backported to [M132](https://crrev.com/c/6054730) and [M131](https://crrev.com/c/6054989).


### VERSION

- M133: https://crrev.com/c/6048961
- M132: https://crrev.com/c/6054730
- M131: https://crrev.com/c/6054989

Chrome Version: 133.0.6862.0 ~ latest / M131 head / M132 head  
Operating System: All


### REPRODUCTION CASE

Attached as `poc.js` which exploits the hash collision + type confusion to obtain in-sandbox exploit primitives, and then crashes on arbitrary caged write attempt.

Also attached is yet another full exploit `exp.html` that pops `calc` on Windows x64 Chrome, tested against Canary 133.0.6871.0.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Renderer  
Crash State: Crashes on arbitrary caged write attempt from JIT-compiled Wasm function (on d8, `poc.js`), arbitrary code execution (on Chrome, `exp.html`)


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n) of CMU CyLab
```

## Vulnerability Description

Large self-contained exploit (wasm-module-builder inlined). Exploits a canonical type index hash collision to achieve type confusion between two WasmGC structs ($s_dst with all ref null none fields and $s_src with all ref null any fields). The exploit tries two known pre/post-592f191 collision pairs. When the collision is found, struct field access via $s_src's type info on an $s_dst object treats a null reference as a live JS reference, establishing addrof, caged_read, and caged_write primitives. Final call: caged_write(0x42424242, 0x13371447).

## Capabilities

addrof, caged_read (arbitrary 32-bit read within V8 sandbox), caged_write (arbitrary 32-bit write within V8 sandbox). Demonstrated: caged_write(0x42424242, 0x13371447).
