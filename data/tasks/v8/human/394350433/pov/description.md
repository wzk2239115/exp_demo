# 394350433: Heap memory corruption due to overly large parameter count in WasmToJSWrapper tier-up

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

#### Summary

Heap memory corruption due to overly large JS parameter count of `0xfffa` and above in Wasm-to-JS wrapper tier-up compilation causing out-of-bounds memory access at `InstructionSelectorT::InitializeCallBuffer()`.


#### Details

When compiling a Wasm-to-JS wrapper where the imported JS function expects an arity of `0xfffa` or more, the total argument nodes required goes over the limit of `0xfffe` and above:

```cc
// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/wrappers.cc;drc=d18f1fb989fa3f6191bba17495c41cf06b6f4172;l=556

  void BuildWasmToJSWrapper(ImportCallKind kind, int expected_arity,
                            Suspend suspend) {
    // ...
    int pushed_count = std::max(expected_arity, wasm_count);
    // 5 extra arguments: receiver, new target, arg count, dispatch handle and
    // context.
    bool has_dispatch_handle =
        kind == ImportCallKind::kUseCallBuiltin
            ? false
            : V8_JS_LINKAGE_INCLUDES_DISPATCH_HANDLE_BOOL;
    base::SmallVector<OpIndex, 16> args(pushed_count + 4 +
                                        (has_dispatch_handle ? 1 : 0));
    // ...
```

This confuses the Turboshaft compiler, where the end result is an out-of-bounds heap memory access in `GetVirtualRegister()`:
```cc
// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/compiler/backend/instruction-selector.cc;drc=69de864028e8d11e8d05971253b98229365d4fb0;l=522

template <typename Adapter>
int InstructionSelectorT<Adapter>::GetVirtualRegister(node_t node) {
  DCHECK(this->valid(node));
  size_t const id = this->id(node);                   // [!] invalid id returned
  DCHECK_LT(id, virtual_registers_.size());
  int virtual_register = virtual_registers_[id];      // [!] oob read
  if (virtual_register == InstructionOperand::kInvalidVirtualRegister) {
    virtual_register = sequence()->NextVirtualRegister();
    virtual_registers_[id] = virtual_register;        // [!] potential oob write, and broken registers tracking
  }
  return virtual_register;
}
```

This is an immediate out-of-v8sbx memory corruption where an attacker can spray target data of `virtual_registers_[id] == InstructionOperand::kInvalidVirtualRegister` which this vulnerability allows to modify it to a different value. Not only is this the only problem, but the bug will also likely result in a broken compilation result which opens up other avenues of exploitation.


### Bisect

TBD


### VERSION

Chrome Version: Tested on Chrome M131 ~ M133 (latest stable), `d8` ToT  
Operating System: All


### REPRODUCTION CASE

Attached as `wasmtojs-tierup-isel-crash.js` which crashes due to OOB access. Also attached is a small wrapper `wrapper.html` that loads this script in Chrome to demonstrate reproducibility also in Chrome.

Full exploit is TBD.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Renderer

Crash State:
```
$ ./d8-asan-sandbox-testing-linux-release-v8-component-98499/d8 ./wasmtojs-tierup-isel-crash.js
=================================================================
==713021==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x79c88b272f34 at pc 0x5ce6f04cfac5 bp 0x7ffdc4a3e4d0 sp 0x7ffdc4a3e4c8
READ of size 4 at 0x79c88b272f34 thread T0
    #0 0x5ce6f04cfac4 in v8::internal::compiler::InstructionSelectorT::GetVirtualRegister(v8::internal::compiler::turboshaft::OpIndex) src/compiler/backend/instruction-selector.cc:543:26
    #1 0x5ce6f04d46f7 in v8::internal::compiler::OperandGeneratorT::UseLocation(v8::internal::compiler::turboshaft::OpIndex, v8::internal::LinkageLocation) src/compiler/backend/instruction-selector-impl.h:262:53
    #2 0x5ce6f04d396d in v8::internal::compiler::InstructionSelectorT::InitializeCallBuffer(v8::internal::compiler::turboshaft::OpIndex, v8::internal::compiler::CallBufferT*, v8::base::Flags<v8::internal::compiler::InstructionSelectorT::CallBufferFlag, int, int>, int) src/compiler/backend/instruction-selector.cc:1744:31
    #3 0x5ce6f04dbdef in v8::internal::compiler::InstructionSelectorT::VisitCall(v8::internal::compiler::turboshaft::OpIndex, v8::internal::compiler::turboshaft::Block*) src/compiler/backend/instruction-selector.cc:2846:3
    #4 0x5ce6f04d6374 in v8::internal::compiler::InstructionSelectorT::VisitNode(v8::internal::compiler::turboshaft::OpIndex) src/compiler/backend/instruction-selector.cc:5602:9
    #5 0x5ce6f04cdd76 in v8::internal::compiler::InstructionSelectorT::VisitBlock(v8::internal::compiler::turboshaft::Block*) src/compiler/backend/instruction-selector.cc:2031:7
    #6 0x5ce6f04cd366 in v8::internal::compiler::InstructionSelectorT::SelectInstructions() src/compiler/backend/instruction-selector.cc:157:5
    #7 0x5ce6f0f76b99 in v8::internal::compiler::turboshaft::InstructionSelectionPhase::Run(v8::internal::compiler::turboshaft::PipelineData*, v8::internal::Zone*, v8::internal::compiler::CallDescriptor const*, v8::internal::compiler::Linkage*, v8::internal::CodeTracer*) src/compiler/turboshaft/instruction-selection-phase.cc:359:55
    #8 0x5ce6f08eb1e1 in auto v8::internal::compiler::turboshaft::Pipeline::Run<v8::internal::compiler::turboshaft::InstructionSelectionPhase, v8::internal::compiler::CallDescriptor*&, v8::internal::compiler::Linkage*&, v8::internal::CodeTracer*&>(v8::internal::compiler::CallDescriptor*&, v8::internal::compiler::Linkage*&, v8::internal::CodeTracer*&) src/compiler/turboshaft/pipelines.h:88:27
    #9 0x5ce6f0880fe6 in v8::internal::compiler::turboshaft::Pipeline::SelectInstructions(v8::internal::compiler::Linkage*) src/compiler/turboshaft/pipelines.h:312:48
    #10 0x5ce6f0869beb in v8::internal::compiler::(anonymous namespace)::GenerateCodeFromTurboshaftGraph(v8::internal::compiler::Linkage*, v8::internal::compiler::turboshaft::Pipeline&, v8::internal::compiler::PipelineImpl*, std::__Cr::shared_ptr<v8::internal::compiler::OsrHelper>) src/compiler/pipeline.cc:504:28
    #11 0x5ce6f08738dc in v8::internal::compiler::Pipeline::GenerateCodeForWasmNativeStubFromTurboshaft(v8::internal::wasm::CanonicalSig const*, v8::internal::wasm::WrapperCompilationInfo, char const*, v8::internal::AssemblerOptions const&, v8::internal::compiler::SourcePositionTable*) src/compiler/pipeline.cc:3061:26
    #12 0x5ce6f19cb9ca in v8::internal::compiler::CompileWasmImportCallWrapper(v8::internal::wasm::ImportCallKind, v8::internal::wasm::CanonicalSig const*, bool, int, v8::internal::wasm::Suspend) src/compiler/wasm-compiler.cc:1729:17
    #13 0x5ce6eff41362 in v8::internal::wasm::WasmImportWrapperCache::CompileWasmImportCallWrapper(v8::internal::Isolate*, v8::internal::wasm::ImportCallKind, v8::internal::wasm::CanonicalSig const*, v8::internal::wasm::CanonicalTypeIndex, bool, int, v8::internal::wasm::Suspend) src/wasm/wasm-import-wrapper-cache.cc:158:34
    #14 0x5ce6efbc3ebe in __RT_impl_Runtime_TierUpWasmToJSWrapper src/runtime/runtime-wasm.cc:745:24
    #15 0x5ce6efbc3ebe in v8::internal::Runtime_TierUpWasmToJSWrapper(int, unsigned long*, v8::internal::Isolate*) src/runtime/runtime-wasm.cc:627:1
    #16 0x5ce6f1ba63c8 in Builtins_WasmCEntry setup-isolate-deserialize.cc
    #17 0x5ce6f1b9d20b in Builtins_WasmToJsWrapperCSA setup-isolate-deserialize.cc
    #18 0x7b788bed2996  (<unknown module>)
    #19 0x5ce6f1b9c814 in Builtins_JSToWasmWrapperAsm setup-isolate-deserialize.cc
    #20 0x5ce6f1c7e3fd in Builtins_JSToWasmWrapper setup-isolate-deserialize.cc
    #21 0x5ce6f1afec74 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #22 0x5ce6f1afc75b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #23 0x5ce6f1afc4aa in Builtins_JSEntry setup-isolate-deserialize.cc
    #24 0x5ce6ee6c5f25 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/execution.cc:437:22
    #25 0x5ce6ee6c68c8 in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:537:10
    #26 0x5ce6ee296fbc in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2146:7
    #27 0x5ce6ee210593 in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1018:44
    #28 0x5ce6ee23129f in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:4979:10
    #29 0x5ce6ee238db7 in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:5930:37
    #30 0x5ce6ee23884c in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5838:18
    #31 0x5ce6ee23ad8d in v8::Shell::Main(int, char**) src/d8/d8.cc:6696:18
    #32 0x7b788bc29d8f in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16

Address 0x79c88b272f34 is a wild pointer inside of access range of size 0x000000000004.
SUMMARY: AddressSanitizer: heap-buffer-overflow src/compiler/backend/instruction-selector.cc:543:26 in v8::internal::compiler::InstructionSelectorT::GetVirtualRegister(v8::internal::compiler::turboshaft::OpIndex)
Shadow bytes around the buggy address:
  0x79c88b272c80: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x79c88b272d00: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x79c88b272d80: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x79c88b272e00: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x79c88b272e80: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
=>0x79c88b272f00: fa fa fa fa fa fa[fa]fa fa fa fa fa fa fa fa fa
  0x79c88b272f80: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x79c88b273000: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x79c88b273080: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x79c88b273100: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x79c88b273180: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
Shadow byte legend (one shadow byte represents 8 application bytes):
  Addressable:           00
  Partially addressable: 01 02 03 04 05 06 07 
  Heap left redzone:       fa
  Freed heap region:       fd
  Stack left redzone:      f1
  Stack mid redzone:       f2
  Stack right redzone:     f3
  Stack after return:      f5
  Stack use after scope:   f8
  Global redzone:          f9
  Global init order:       f6
  Poisoned by user:        f7
  Container overflow:      fc
  Array cookie:            ac
  Intra object redzone:    bb
  ASan internal:           fe
  Left alloca redzone:     ca
  Right alloca redzone:    cb
==713021==ABORTING
```


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n) of CMU CyLab

-----

Initially discovered by a v8sbx fuzzer, which revealed not to be a v8sbx violation but a full-blown memory corruption bug.
```

## Vulnerability Description

Large self-contained PoC (wasm-module-builder inlined) for d8. Creates a JS function (jsFunc) with a complex signature (12 i32 params, 6 mixed returns), wraps it in a WasmTableObject, and calls instance.exports.main() 1000 times to trigger tier-up of the WasmToJS wrapper. Instruction selection for the tiered-up wrapper crashes due to an unsupported value type combination.

## Capabilities

Crashes during WasmToJS wrapper tier-up instruction selection. No memory read/write.
