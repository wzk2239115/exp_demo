# 446124893: Wasm type confusion due to custom descriptors spec ambiguity in `ref.get_desc` exactness typing

## ClusterFuzz Report

```
## README

This is a Wasm spec-level unsoundness issue. Any runtime implementing the same spec faithfully will have the same bug. I am reporting this privately to Google Chrome/V8 as Google seems to be leading the spec work and implementation of custom descriptors the first and practically has the most affected users in the wild.

As this is a spec-level unsoundness which the Wasm community needs to know, I believe that the issue necessitates a quicker disclosure deadline than what is enforced by default by Chrome's disclosure policies. **It would be great if we can coordinate the disclosure within a week from the reported date** - please contact me through email or through the comments. Unless otherwise coordinated, **the spec unsoundness issue is subject to a 14-day disclosure deadline after which the issue, without any specific mentions of Chrome/V8, will be disclosed publicly** on https://github.com/WebAssembly/custom-descriptors/issues. The Chrome/V8 security team is allowed to responsibly disclose this to other vendors and personnel involved in WebAssembly work (at CG meetings or whatnot) under the conditions that 1. the reporter is credited, and 2. is given at least a day's advance notice.


### VULNERABILITY DETAILS

#### Summary

Wasm type confusion due to spec unsoundness around `ref.get_desc` exactness typing. [Spec](https://github.com/WebAssembly/custom-descriptors/blob/main/proposals/custom-descriptors/Overview.md#new-instructions) describes two different rules for `ref.get_desc`:
- (Rule #1) Rule in the codeblock indicates that `ref.get_desc` must type the result as exact only when the stack type is a subtype of the exact encoded type (thus only allowing the exact encoded type). This rule is sound.
- (Rule #2) Rule written in plain English indicates that *"If the provided reference is to an exact heap type, then the type of the custom descriptor is known precisely, so the result can be exact as well"*. In other words, the provided reference's exactness directly propagates to the result type. However, the result type in this case MUST be typed as the **provided reference's descriptor type**, not the **encoded immediate type's descriptor type**. This rule is also sound (if done right) but is different than the first rule.
- However, mixing the two up yields an **unsound rule**, e.g. by propagating the provided reference's exactness to the result type (Rule #2), but taking the base result type from the encoded immediate type's descriptor (Rule #1). The spec is unsound in that it describes two completely different rules as if it is the same `ref.get_desc`.

V8 also gets confused and implements the unsound rule, transferring the exactness of the stack type to the result type while using the encoded immediate type's descriptor. This allows typing the resulting descriptor as an exact supertype, leading to type confusion.

Custom descriptors feature is exposed in the wild by default through Origin Trials from M141, which is currently at Beta and very soon reaches (Early) Stable. This bug is not caused by a recent code change and has existed from the very first feature implementation (approx. 6 months) due to an inherent spec unsoundness.


#### Details

[Spec](https://github.com/WebAssembly/custom-descriptors/blob/main/proposals/custom-descriptors/Overview.md#new-instructions) indicates that `ref.get_desc` must type the result as exact only when the stack type is a subtype of the exact sourcetype:

```
ref.get_desc typeidx

C |- ref.get_desc x : (ref null (exact_1 x)) -> (ref (exact_1 y))
-- C.types[x] ~ descriptor y ct
```

For example, take `x' <: x` with `C.types[x'] ~ descriptor y' ct'` where `C |- ¬(C.types[x'] ~ C.types[x])` - that is, `x'` is a strict subtype of `x`. Due to subtyping rules on descriptors, `y' <: y` holds. If `ref exact x'` is passed to `ref.get_desc x`:

```
Stack: ref exact x'
Match: ref exact x' <: ref null x => exact_1 = inexact
=> ref.get_desc x (ref exact x') -> (ref y)
```

Since `¬(ref exact x' <: ref null exact x)`, `exact_1 = inexact` is the only suitable rule and the resulting descriptor type must be inexact.

However, the spec also describes this rule in plain English but with different typing rules:

> If the provided reference is to an exact heap type, then the type of the custom descriptor is known precisely, so the result can be exact as well. Otherwise, the subtyping rules described above ensure that there will be some custom descriptor value and that it will be a subtype of the custom descriptor type for `x`, so the result can be a non-null reference to the inexact descriptor type.

This may be interpreted as a weakened, unsound rule that translates to the below rule:

```
ref.get_desc? typeidx

C |- ref.get_desc? x : (ref null (exact_1 x')) -> (ref (exact_1 y))
-- C.types[x] ~ descriptor y ct
-- C.types[x'] ~ descriptor y' ct'
-- C |- x' <: x                                                                     // [!] (modified) subtype check
```

Note that we've subtly weakened the rule on the input type, effectively passing on the exactness of whatever was on the stack instead of typechecking `stacktype <: ref null exact x`. We also derive `y` from the encoded type `x`, not the provided type on the stack. This yields the results below:

```
Stack: ref exact x'
Match: (ref exact x' <: ref null exact x') ∧ (x' <: x) => exact_1 = exact
=> ref.get_desc? x (ref exact x') -> (ref exact y)
```

V8's implementation takes the weakened, unsound rule:

```cc
// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/function-body-decoder-impl.h;drc=43df3221d3b0c1ea8f7d54394a00cb8656204085;l=5994
      case kExprRefGetDesc: {
        // ...
        StructIndexImmediate imm(this, this->pc_ + opcode_length, validate);
        if (!this->Validate(this->pc_ + opcode_length, imm)) return 0;
        const TypeDefinition& type = this->module_->type(imm.index);
        if (!VALIDATE(type.has_descriptor())) {
          // ...
          return 0;
        }
        Value ref = Pop(ValueType::RefNull(imm.heap_type()));                       // [!] (modified) subtype check
        Value* desc =
            Push(ValueType::Ref(this->module_->heap_type(type.descriptor))
                     .AsExact(ref.type.exactness()));                               // [!] exactness directly from stack type (x')
        CALL_INTERFACE_IF_OK_AND_REACHABLE(RefGetDesc, ref, desc);
        return opcode_length + imm.length;
      }
```


Now we have `ref exact y'` typed as `ref exact y` where `y' <: y`. This pokes a hole in the type system exactly as described in the [proposal docs](https://github.com/WebAssembly/custom-descriptors/blob/main/proposals/custom-descriptors/Overview.md#exact-types), allowing attackers to invalidly type a descriptor `y'` into an exact supertype `y`, instantiate struct `x`, then invalidly cast down to `x'`. This leads to type confusion between arbitrary Wasm types.

This seems to be a very common misinterpretation of the spec. Development work on Binaryen [also shows](https://github.com/WebAssembly/binaryen/pull/7886) this misunderstanding: *"`ref.get_desc` inherits its input ref's exactness..."* which is only true when the reference type's descriptor is used as the return type (which from a cursory glance may be what Binaryen's doing). This leads me to wonder if the spec was initially designed to represent something like Rule #1, but happened to be written down in a different thing described as Rule #2, and then things got messy? [Slides](https://docs.google.com/presentation/d/1HtHw4WNEZ4DAt6ythWzhDiPHBc8_-GHT5qKAMlxfcYc/edit?slide=id.g35846d341e4_0_429#slide=id.g35846d341e4_0_429) from CG meeting for Phase 2 advancement of the proposal also mix up the two, stating the formal rule as Rule #1 but uses the phrase "propagates exactness of references" which applies on Rule #2.


#### Bisect

Bug introduced by WebAssembly Custom Descriptors, on Origin Trials from M141 and onwards. More specifically, it is introduced in commit [2f4c043d](https://crrev.com/c/6401033) which implements `ref.get_desc`.


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

Large self-contained JS exploit (wasm-module-builder inlined), no-import variant of the WasmGC implicit type refinement + decoder inconsistency bug. Constructs addrof, fakeobj, caged_read, caged_write, and caged_write_unsafe primitives. Ends with caged_write_unsafe(0x42424242, 0x43434343).

## Capabilities

addrof, fakeobj, caged_read, caged_write, caged_write_unsafe primitives via WasmGC type confusion (no-import variant). Demonstrated: caged_write_unsafe(0x42424242, 0x43434343).
