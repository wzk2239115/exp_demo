# 350292240: V8 Sandbox Bypass: AAR/W via generic function table `call_indirect` rtt check bypass

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

V8 sandbox bypass, arbitrary address read/write via function signature confusion through rtt check bypass in `call_indirect` for generic function tables using in-sandbox exploit primitives.

Function signature confusion in tables are fixed by https://chromium-review.googlesource.com/c/v8/v8/+/5626414 and https://chromium-review.googlesource.com/5659606, with the former checking table updates and the latter checking table imports.

Notably, we're using `SBXCHECK(FunctionSigMatchesTable(...))` to check whether the function signature is in fact a canonical subtype of the actual table type. This check cannot be done statically with generic function typed tables and thus the checks are eventually [done in runtime via rtt subtype checks](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/baseline/liftoff-compiler.cc;drc=98618e309ba7ec15e3164651e26b5587a1d9cee2;l=8308). However, all the objects involved in the checks are within the v8 sandbox (rtt `Map`, `WasmTypeInfo`, `ManagedObjectMaps`, etc.) and are subject to corruption.

Thus, an attacker may corrupt in-sandbox memory such that `WasmTypeInfo.supertype[rtt_depth] = formal_rtt` to bypass rtt subtype check, causing function signature confusion and obtain AAR/W primitives outside of the sandbox.

Note that this can be used to force other runtime casts to succeed, such as `rtt.cast`.

Analysis of Liftoff JIT compilation for the rtt subtype checks:

```
pwndbg> nearpc 0x23525d93889c 0x8
 ► 0x23525d93889c    mov    ecx, dword ptr [rsi + 7]
   0x23525d93889f    or     rcx, qword ptr [r13 + 0x1e0]
   0x23525d9388a6    mov    ebx, dword ptr [rcx + 0x17]
   0x23525d9388a9    cmp    ebx, 5
   0x23525d9388ac    je     0x23525d9388f0                <0x23525d9388f0>
 
   // __ emit_i32_cond_jumpi(kEqual, sig_mismatch_label, real_sig_id.gp_reg(), -1, frozen);
   0x23525d9388b2    cmp    ebx, -1
   0x23525d9388b5    je     0x23525d938948                <0x23525d938948>
 
   // __ LoadFullPointer(real_rtt.gp_reg(), kRootRegister, IsolateData::root_slot_offset(RootIndex::kWasmCanonicalRtts));
   0x23525d9388bb    mov    rdi, qword ptr [r13 + 0x1cf8]
   // __ LoadTaggedPointer(real_rtt.gp_reg(), real_rtt.gp_reg(), real_sig_id.gp_reg(), ObjectAccess::ToTagged(WeakArrayList::kHeaderSize), nullptr, true);
   0x23525d9388c2    mov    edi, dword ptr [rdi + rbx*4 + 0xb]
   0x23525d9388c6    add    rdi, r14
   // __ emit_i64_andi(real_rtt.reg(), real_rtt.reg(), static_cast<int32_t>(~kWeakHeapObjectMask));
   0x23525d9388c9    and    rdi, 0xfffffffffffffffd
   // Step 1: load the WasmTypeInfo.
   // ScopedTempRegister type_info{std::move(real_rtt)};
   // __ LoadTaggedPointer(type_info.gp_reg(), type_info.gp_reg(), no_reg, kTypeInfoOffset);
   0x23525d9388cd    mov    edi, dword ptr [rdi + 0x13]
   0x23525d9388d0    add    rdi, r14
   // Step 2: check the list's length if needed. => omitted
   // Step 3: load the candidate list slot, and compare it.
   // ScopedTempRegister maybe_match{std::move(type_info)};
   // __ LoadTaggedPointer(maybe_match.gp_reg(), maybe_match.gp_reg(), no_reg, ObjectAccess::ToTagged(WasmTypeInfo::kSupertypesOffset + rtt_depth * kTaggedSize));
   0x23525d9388d3    mov    edi, dword ptr [rdi + 0x13]
   0x23525d9388d6    add    rdi, r14
   // LOAD_TAGGED_PTR_INSTANCE_FIELD(formal_rtt.gp_reg(), ManagedObjectMaps, kGpCacheRegList);
   0x23525d9388d9    mov    ebx, dword ptr [rsi + 0xb3]
   0x23525d9388df    add    rbx, r14
   // __ LoadTaggedPointer(formal_rtt.gp_reg(), formal_rtt.gp_reg(), no_reg, wasm::ObjectAccess::ElementOffsetInTaggedFixedArray(imm.sig_imm.index));
   0x23525d9388e2    mov    ebx, dword ptr [rbx + 0xf]
   0x23525d9388e5    add    rbx, r14
   // __ emit_cond_jump(kNotEqual, sig_mismatch_label, kRtt, formal_rtt.gp_reg(), maybe_match.gp_reg(), frozen);
   0x23525d9388e8    cmp    ebx, edi
   0x23525d9388ea    jne    0x23525d938948                <0x23525d938948>
```

### VERSION

V8 Version: a832ff96bd41b40b9cfee90a314fa816802cf9ae


### REPRODUCTION CASE

Repro added as `rtt_subtype_check_bypass.js`.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Sandbox violation


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n)
```

## Vulnerability Description

57566312_wasm-module-builder.js is the standard V8 test helper library loaded via d8.file.execute. 57566313_rtt_subtype_check_bypass.js is an exploit that builds two Wasm functions: 'writer' (sig: i64 + struct_ref -> void, does struct.set) and 'boom' (sig: i64 + i64 -> void, does call_indirect). Uses Sandbox.MemoryView and Sandbox.getAddressOf to read the WasmTypeInfo of writer's funcref map, then overwrites typeinfo_v_ls.supertypes[0] with map_v_ll (the map of boom's funcref type). This makes the RTT subtype check believe boom's signature is a subtype of writer's, so call_indirect succeeds with the wrong signature. Calls boom(Sandbox.targetPage - 7n, 0x42n) achieving arbitrary write.

## Capabilities

Arbitrary 64-bit write to any address outside the sandbox via RTT subtype check bypass. Demonstrated by writing 0x42 to Sandbox.targetPage. Requires --sandbox-testing and Sandbox.* API.
