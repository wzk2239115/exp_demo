# 355256380: Type Confusion between WasmObject and JSObject in V8 MaglevGraphBuilder::TryBuildFastOrdinaryHasInstance

## ClusterFuzz Report

```
VULNERABILITY DETAILS
## INTRODUCE
Without a doubt, the true introduction of this vulnerability, like most previous confusions between wasm and js objects, can be traced back to the point where wasm arrays and wasm structs were introduced.

## CRASH LOG
- Debug output

```bash
#
# Fatal error in ../../src/compiler/heap-refs.cc, line 1127
# Debug check failed: IsJSObject().
#
#
#
#FailureMessage Object: 0x7f6ebeffb250
==== C stack trace ===============================

    d8-linux-debug-v8-component-95248/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7f6ef59f4aa3]
    d8-linux-debug-v8-component-95248/libv8_libplatform.so(+0x19add) [0x7f6efb1ddadd]
    d8-linux-debug-v8-component-95248/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x194) [0x7f6ef59d6234]
    d8-linux-debug-v8-component-95248/libv8_libbase.so(+0x2bc55) [0x7f6ef59d5c55]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::compiler::ObjectRef::AsJSObject() const+0x65) [0x7f6efa1bf575]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevGraphBuilder::InferHasInPrototypeChain(v8::internal::maglev::ValueNode*, v8::internal::compiler::HeapObjectRef)+0x13a) [0x7f6ef963038a]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevGraphBuilder::BuildHasInPrototypeChain(v8::internal::maglev::ValueNode*, v8::internal::compiler::HeapObjectRef)+0x1c) [0x7f6ef963071c]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevGraphBuilder::TryBuildFastOrdinaryHasInstance(v8::internal::maglev::ValueNode*, v8::internal::compiler::JSObjectRef, v8::internal::maglev::ValueNode*)+0x278) [0x7f6ef9630aa8]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevGraphBuilder::BuildOrdinaryHasInstance(v8::internal::maglev::ValueNode*, v8::internal::compiler::JSObjectRef, v8::internal::maglev::ValueNode*)+0x22) [0x7f6ef961d892]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevGraphBuilder::TryBuildFastInstanceOf(v8::internal::maglev::ValueNode*, v8::internal::compiler::JSObjectRef, v8::internal::maglev::ValueNode*)+0x438) [0x7f6ef9630f48]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevGraphBuilder::TryBuildFastInstanceOfWithFeedback(v8::internal::maglev::ValueNode*, v8::internal::maglev::ValueNode*, v8::internal::compiler::FeedbackSource)+0x163) [0x7f6ef9631943]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevGraphBuilder::VisitTestInstanceOf()+0xa0) [0x7f6ef9631a00]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevGraphBuilder::VisitSingleBytecode()+0xd7a) [0x7f6ef951dcaa]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevGraphBuilder::BuildBody()+0x12a) [0x7f6ef951907a]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevGraphBuilder::Build()+0x3bb) [0x7f6ef9515eab]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevCompiler::Compile(v8::internal::LocalIsolate*, v8::internal::maglev::MaglevCompilationInfo*)+0x6d0) [0x7f6ef9514910]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevCompilationJob::ExecuteJobImpl(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x66) [0x7f6ef95de6c6]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::OptimizedCompilationJob::ExecuteJob(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x8d) [0x7f6ef83b5f1d]
    d8-linux-debug-v8-component-95248/libv8.so(v8::internal::maglev::MaglevConcurrentDispatcher::JobTask::Run(v8::JobDelegate*)+0x39b) [0x7f6ef95e041b]
    d8-linux-debug-v8-component-95248/libv8_libplatform.so(v8::platform::DefaultJobWorker::Run()+0xd3) [0x7f6efb1dc883]
    d8-linux-debug-v8-component-95248/libv8_libplatform.so(v8::platform::DefaultWorkerThreadsTaskRunner::WorkerThread::Run()+0xcc) [0x7f6efb1decbc]
    d8-linux-debug-v8-component-95248/libv8_libbase.so(+0x497f8) [0x7f6ef59f37f8]
    /lib/x86_64-linux-gnu/libc.so.6(+0x94ac3) [0x7f6ef5294ac3]
    /lib/x86_64-linux-gnu/libc.so.6(+0x126850) [0x7f6ef5326850]
[6]    1307572 trace trap  d8-linux-debug-v8-component-95248/d8 poc.js

```

VERSION
Tested on v8 version: 11.9.0 - 12.0.0

REPRODUCTION CASE
1. Download debug v8 from: gs://v8-asan/linux-debug/d8-linux-debug-v8-component-95248.zip
2. Run: `d8  poc.js`

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

CREDIT INFORMATION
Reporter credit: Zhenghang Xiao (@Kipreyyy)
```

## Vulnerability Description

Short PoC that loads wasm-module-builder.js, creates a WasmGC struct type (kWasmI32 field), exports MakeStruct() which returns the struct as externref, stores it as globalThis.struct. Then calls foo(function(){}) which sets arg.prototype = globalThis.struct (a WasmGC struct) and runs 'new arg() instanceof arg' 5000 times. The IC handler for hasInstance does not expect a WasmGC struct as the prototype, triggering a type confusion or DCHECK.

## Capabilities

Likely triggers a DCHECK or crash in the IC or instanceof handler when a WasmGC struct is used as a constructor prototype. No memory read/write.
