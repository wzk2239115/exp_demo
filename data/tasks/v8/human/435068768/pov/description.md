# 435068768: Debug check failed: ValidationTag::validate

## ClusterFuzz Report

```
```


#
# Fatal error in ../../src/wasm/function-body-decoder-impl.h, line 204
# Debug check failed: ValidationTag::validate.
#
#
#
#FailureMessage Object: 0x7ffdcecc5098
==== C stack trace ===============================

    /home/user/v8/v8/out/x64.debug/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x1e) [0x7fb7c553149e]
    /home/user/v8/v8/out/x64.debug/libv8_libplatform.so(+0x4abbd) [0x7fb7c549cbbd]
    /home/user/v8/v8/out/x64.debug/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x205) [0x7fb7c5509e65]
    /home/user/v8/v8/out/x64.debug/libv8_libbase.so(+0x4e81c) [0x7fb7c550981c]
    /home/user/v8/v8/out/x64.debug/libv8_libbase.so(V8_Dcheck(char const*, int, char const*)+0x4d) [0x7fb7c5509f3d]
    /home/user/v8/v8/out/x64.debug/libv8.so(void v8::internal::wasm::DecodeError<v8::internal::wasm::Decoder::NoValidationTag, unsigned int, char const*, unsigned int>(v8::internal::wasm::Decoder*, char const*, unsigned int&&, char const*&&, unsigned int&&)+0x36) [0x7fb7cf1fa3d6]
    /home/user/v8/v8/out/x64.debug/libv8.so(void v8::internal::wasm::WasmDecoder<v8::internal::wasm::Decoder::NoValidationTag, (v8::internal::wasm::DecodingMode)0>::DecodeError<char const*, unsigned int, char const*, unsigned int>(char const*, unsigned int, char const*, unsigned int)+0x34) [0x7fb7cf1fa294]
    /home/user/v8/v8/out/x64.debug/libv8.so(bool v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::TypeCheckStackAgainstMerge_Slow<(v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::StackElementsCountMode)1, (v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::PushBranchValues)0, (v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::MergeType)2, (v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::RewriteStackTypes)0>(v8::internal::wasm::Merge<v8::internal::wasm::TurboshaftGraphBuildingInterface::Value>*)+0xc4) [0x7fb7cf3b3134]
    /home/user/v8/v8/out/x64.debug/libv8.so(bool v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::TypeCheckStackAgainstMerge<(v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::StackElementsCountMode)1, (v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::PushBranchValues)0, (v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::MergeType)2, (v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::RewriteStackTypes)0>(v8::internal::wasm::Merge<v8::internal::wasm::TurboshaftGraphBuildingInterface::Value>*)+0xbe) [0x7fb7cf3b2ffe]
    /home/user/v8/v8/out/x64.debug/libv8.so(bool v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::DoReturn<(v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::StackElementsCountMode)1, (v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::MergeType)2>()+0x30) [0x7fb7cf3b0810]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::DecodeEndImpl(v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::TraceLine*, v8::internal::wasm::WasmOpcode)+0x92d) [0x7fb7cf3af05d]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::DecodeEnd(v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>*, v8::internal::wasm::WasmOpcode)+0x6e) [0x7fb7cf38c48e]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::DecodeFunctionBody()+0x4a9) [0x7fb7cf37e769]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::wasm::WasmFullDecoder<v8::internal::wasm::Decoder::NoValidationTag, v8::internal::wasm::TurboshaftGraphBuildingInterface, (v8::internal::wasm::DecodingMode)0>::Decode()+0x276) [0x7fb7cf365f66]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::wasm::BuildTSGraph(v8::internal::compiler::turboshaft::PipelineData*, v8::internal::AccountingAllocator*, v8::internal::wasm::CompilationEnv*, v8::internal::wasm::WasmDetectedFeatures*, v8::internal::compiler::turboshaft::Graph&, v8::internal::wasm::FunctionBody const&, v8::internal::wasm::WireBytesStorage const*, std::__Cr::unique_ptr<v8::internal::wasm::AssumptionsJournal, std::__Cr::default_delete<v8::internal::wasm::AssumptionsJournal>>*, v8::internal::ZoneVector<v8::internal::WasmInliningPosition>*, int, v8::internal::wasm::WasmFunctionCoverageData*)+0x1f1) [0x7fb7cf363ef1]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::compiler::Pipeline::GenerateWasmCode(v8::internal::wasm::CompilationEnv*, v8::internal::compiler::WasmCompilationData&, v8::internal::wasm::WasmDetectedFeatures*, v8::internal::Counters*)+0xa59) [0x7fb7cff163f9]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::compiler::turboshaft::ExecuteTurboshaftWasmCompilation(v8::internal::wasm::CompilationEnv*, v8::internal::compiler::WasmCompilationData&, v8::internal::wasm::WasmDetectedFeatures*, v8::internal::Counters*)+0x53) [0x7fb7d164f0e3]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::wasm::WasmCompilationUnit::ExecuteCompilation(v8::internal::wasm::CompilationEnv*, v8::internal::wasm::WireBytesStorage const*, v8::internal::Counters*, v8::internal::wasm::WasmDetectedFeatures*)+0x96c) [0x7fb7cf2bef2c]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::wasm::CompileLazy(v8::internal::Isolate*, v8::internal::Tagged<v8::internal::WasmTrustedInstanceData>, int)+0x2f9) [0x7fb7cf2c5959]
    /home/user/v8/v8/out/x64.debug/libv8.so(+0x9bd8cce) [0x7fb7cf11bcce]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::Runtime_WasmCompileLazy(int, unsigned long*, v8::internal::Isolate*)+0x151) [0x7fb7cf11b791]
    /home/user/v8/v8/out/x64.debug/libv8.so(+0x71d2257) [0x7fb7cc715257]
Trace/breakpoint trap (core dumped)
```

#### VERSION

V8 version 13.9.0 (candidate)

#### REPRODUCTION CASE

Build: `python3 tools/dev/gm.py x64.debug`

Run: `./d8 poc.js`

---
Reporter credit: Shaheen Fazim
```

## Vulnerability Description

Short ASM.js PoC. Defines an ASM.js module with HEAP32 view and trigger(a, b) that does HEAP32[a >> (b >> 2)] = 42. Calls trigger(0x100, 0x100): in ASM.js, b >> 2 = 64, and a >> 64 should be 0x100 (shift by 0 mod 32), writing HEAP32[0x100] = byte 1024, within bounds. V8's ASM.js JIT may incorrectly compute the shift, leading to OOB write.

## Capabilities

Triggers incorrect HEAP32 write due to ASM.js shift amount computation bug. No controlled arbitrary write beyond ASM.js heap bounds.
