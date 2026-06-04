# 324747822: Debug check failed: !type.is_uninhabited(). in v8

## ClusterFuzz Report

```
VULNERABILITY DETAILS
## INTRODUCE
After bisect, it was determined that following commit caused this problem.

- Commit Info
    - Version: 92242
    - link: https://crrev.com/3f2471d0abe711c92ddb3d6fe17bc22d9955f2b8 
- Commit Message

```
commit 3f2471d0abe711c92ddb3d6fe17bc22d9955f2b8
Author: Matthias Liedtke <mliedtke@chromium.org>
Date:   Wed Feb 7 16:34:41 2024 +0100

    [turboshaft][wasm] WasmGCTypeReducer: Check for uninhabited, not bottom
    
    wasm::Type::AsNonNull() converts `ref null T` to `ref T`.
    For any T in {none, nofunc, noextern} this will result in types which
    do not have a valid value, i.e. cannot occur in reachable code.
    
    Therefore we should check for `type.is_uninhabited()` instead of
    `type == kWasmBottom` in all cases where we care about "invalid" types.
    
    Bug: v8:14108
    Change-Id: I2ab7c542527938535bcb6eb9ac29d7a8748209d5
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/5277240
    Auto-Submit: Matthias Liedtke <mliedtke@chromium.org>
    Commit-Queue: Jakob Kummerow <jkummerow@chromium.org>
    Reviewed-by: Jakob Kummerow <jkummerow@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#92242}

```

## CRASH LOG
- Debug output

```bash
# CMD: /tmp/d8-linux32-debug-v8-component-92272/d8 --allow-natives-syntax --expose-gc --future --fuzzing --jit-fuzzing --harmony --omit-quit --js-staging --wasm-staging --no-wasm-loop-unrolling --no-wasm-loop-peeling poc.js
# OUTPUT ==============================================================


#
# Fatal error in ../../src/compiler/turboshaft/wasm-gc-type-reducer.cc, line 396
# Debug check failed: !type.is_uninhabited().
#
#
#
#FailureMessage Object: 0xe17f9d90
==== C stack trace ===============================

    /tmp/d8-linux32-debug-v8-component-92272/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x1f) [0xf7ecb19f]
    /tmp/d8-linux32-debug-v8-component-92272/libv8_libplatform.so(+0x16274) [0xf7e77274]
    /tmp/d8-linux32-debug-v8-component-92272/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0xf7) [0xf7eaa5a7]
    /tmp/d8-linux32-debug-v8-component-92272/libv8_libbase.so(+0x26fa6) [0xf7ea9fa6]
    /tmp/d8-linux32-debug-v8-component-92272/libv8_libbase.so(V8_Dcheck(char const*, int, char const*)+0x31) [0xf7eaa5f1]
    /tmp/d8-linux32-debug-v8-component-92272/libv8.so(v8::internal::compiler::turboshaft::WasmGCTypeAnalyzer::CreateMergeSnapshot(v8::base::Vector<v8::internal::compiler::turboshaft::SnapshotTable<v8::internal::wasm::ValueType, v8::internal::compiler::turboshaft::NoKeyData>::Snapshot const>, v8::base::Vector<bool const>)+0x53a) [0xf730e0ca]
    /tmp/d8-linux32-debug-v8-component-92272/libv8.so(v8::internal::compiler::turboshaft::WasmGCTypeAnalyzer::Run()+0x3a5) [0xf730d585]
    /tmp/d8-linux32-debug-v8-component-92272/libv8.so(void v8::internal::compiler::turboshaft::GraphVisitor<v8::internal::compiler::turboshaft::ReducerStack<v8::internal::compiler::turboshaft::Assembler<v8::internal::compiler::turboshaft::reducer_list<v8::internal::compiler::turboshaft::TurboshaftAssemblerOpInterface, v8::internal::compiler::turboshaft::GraphVisitor, v8::internal::compiler::turboshaft::WasmLoadEliminationReducer, v8::internal::compiler::turboshaft::WasmGCTypeReducer, v8::internal::compiler::turboshaft::TSReducerBase>>, false, v8::internal::compiler::turboshaft::WasmLoadEliminationReducer, v8::internal::compiler::turboshaft::WasmGCTypeReducer, v8::internal::compiler::turboshaft::TSReducerBase>>::VisitGraph<false>()+0x4d) [0xf72d393d]
    /tmp/d8-linux32-debug-v8-component-92272/libv8.so(v8::internal::compiler::turboshaft::CopyingPhaseImpl<v8::internal::compiler::turboshaft::WasmLoadEliminationReducer, v8::internal::compiler::turboshaft::WasmGCTypeReducer>::Run(v8::internal::compiler::turboshaft::Graph&, v8::internal::Zone*, bool)+0xf4) [0xf72d37b4]
    /tmp/d8-linux32-debug-v8-component-92272/libv8.so(v8::internal::compiler::turboshaft::WasmGCOptimizePhase::Run(v8::internal::Zone*)+0xb4) [0xf72c1774]
    /tmp/d8-linux32-debug-v8-component-92272/libv8.so(auto v8::internal::compiler::PipelineImpl::Run<v8::internal::compiler::turboshaft::WasmGCOptimizePhase>()+0xd0) [0xf7116af0]
    /tmp/d8-linux32-debug-v8-component-92272/libv8.so(v8::internal::compiler::Pipeline::GenerateWasmCodeFromTurboshaftGraph(v8::internal::OptimizedCompilationInfo*, v8::internal::wasm::CompilationEnv*, v8::internal::compiler::WasmCompilationData&, v8::internal::compiler::MachineGraph*, v8::internal::wasm::WasmFeatures*, v8::internal::compiler::CallDescriptor*)+0x78d) [0xf711577d]
    /tmp/d8-linux32-debug-v8-component-92272/libv8.so(v8::internal::compiler::turboshaft::ExecuteTurboshaftWasmCompilation(v8::internal::wasm::CompilationEnv*, v8::internal::compiler::WasmCompilationData&, v8::internal::wasm::WasmFeatures*)+0x317) [0xf73dea27]
    /tmp/d8-linux32-debug-v8-component-92272/libv8.so(v8::internal::wasm::WasmCompilationUnit::ExecuteFunctionCompilation(v8::internal::wasm::CompilationEnv*, v8::internal::wasm::WireBytesStorage const*, v8::internal::Counters*, v8::internal::wasm::WasmFeatures*)+0x727) [0xf68effa7]
    /tmp/d8-linux32-debug-v8-component-92272/libv8.so(v8::internal::wasm::WasmCompilationUnit::ExecuteCompilation(v8::internal::wasm::CompilationEnv*, v8::internal::wasm::WireBytesStorage const*, v8::internal::Counters*, v8::internal::wasm::WasmFeatures*)+0x18a) [0xf68ef48a]
    /tmp/d8-linux32-debug-v8-component-92272/libv8.so(+0x334cc9c) [0xf694cc9c]
    /tmp/d8-linux32-debug-v8-component-92272/libv8.so(+0x334c599) [0xf694c599]
    /tmp/d8-linux32-debug-v8-component-92272/libv8_libplatform.so(v8::platform::DefaultJobWorker::Run()+0xcb) [0xf7e75e9b]
    /tmp/d8-linux32-debug-v8-component-92272/libv8_libplatform.so(v8::platform::DefaultWorkerThreadsTaskRunner::WorkerThread::Run()+0x9f) [0xf7e7862f]
    /tmp/d8-linux32-debug-v8-component-92272/libv8_libbase.so(+0x46dbe) [0xf7ec9dbe]
    /lib/i386-linux-gnu/libc.so.6(+0x86c01) [0xf2c86c01]
    /lib/i386-linux-gnu/libc.so.6(+0x12372c) [0xf2d2372c]
Received signal 6

```

## Other
Please note to include the flags `--allow-natives-syntax --expose-gc --future --fuzzing --jit-fuzzing --harmony --omit-quit --js-staging --wasm-staging --no-wasm-loop-unrolling --no-wasm-loop-peeling` for clusterfuzz classification.

VERSION
Tested on v8 version: 12.3.0 - 12.3.0

REPRODUCTION CASE
1. Download debug v8 from: gs://v8-asan/linux32-debug/d8-linux32-debug-v8-component-92272.zip
2. Run: `d8 --allow-natives-syntax --expose-gc --future --fuzzing --jit-fuzzing --harmony --omit-quit --js-staging --wasm-staging --no-wasm-loop-unrolling --no-wasm-loop-peeling poc.js`

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

CREDIT INFORMATION
Reporter credit: Jerry
```

## Vulnerability Description

53555016_poc.js contains the Wasm module bytecode inlined as a Uint8Array, instantiates it with wasm:js-string / wasm:text-decoder / wasm:text-encoder builtins, and calls exports.main(). 53601805_wasm.bin is the raw binary form of that same Wasm module. The JS file does not load the .bin at runtime; the .bin is the original binary from which the inline bytes were derived.

## Capabilities

Crashes the process with SIGTRAP (DCHECK !type.is_uninhabited()). No memory read/write. No controlled output.
