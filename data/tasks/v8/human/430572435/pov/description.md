# 430572435: JIT type confusion via corrupted inlining metadata

## ClusterFuzz Report

```
```


#
# Fatal error in ../../src/base/bit-field.h, line 56
# Debug check failed: is_valid(value).
#
#
#
#FailureMessage Object: 0x7bc04a228c60
==== C stack trace ===============================

    ./out/test/d8(__interceptor_backtrace+0x46) [0x564f0c1e4c96]
    /home/user/v8-bisect/v8/out/test/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7fc077c80a23]
    /home/user/v8-bisect/v8/out/test/libv8_libplatform.so(+0x36a8a) [0x7fc077bd5a8a]
    /home/user/v8-bisect/v8/out/test/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x2a0) [0x7fc077c4b8e0]
    /home/user/v8-bisect/v8/out/test/libv8_libbase.so(+0x5699f) [0x7fc077c4a99f]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::SourcePosition::SetInliningId(int)+0x140) [0x7fc07c9bc9f0]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevGraphBuilder::MaglevGraphBuilder(v8::internal::LocalIsolate*, v8::internal::maglev::MaglevCompilationUnit*, v8::internal::maglev::Graph*, float, v8::internal::BytecodeOffset, bool, int, v8::internal::maglev::MaglevGraphBuilder*)+0x7b8) [0x7fc07f0758f8]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevGraphBuilder::TryBuildInlinedCall(v8::internal::maglev::ValueNode*, v8::internal::maglev::ValueNode*, v8::internal::maglev::ValueNode*, v8::internal::compiler::SharedFunctionInfoRef, v8::internal::compiler::OptionalRef<v8::internal::compiler::FeedbackVectorRef>, v8::internal::maglev::CallArguments&, v8::internal::compiler::FeedbackSource const&)+0xd9b) [0x7fc07f0f2e9b]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevGraphBuilder::TryBuildCallKnownJSFunction(v8::internal::maglev::ValueNode*, v8::internal::maglev::ValueNode*, v8::internal::maglev::ValueNode*, v8::internal::compiler::SharedFunctionInfoRef, v8::internal::compiler::OptionalRef<v8::internal::compiler::FeedbackVectorRef>, v8::internal::maglev::CallArguments&, v8::internal::compiler::FeedbackSource const&)+0x137) [0x7fc07f11c1d7]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevGraphBuilder::TryBuildCallKnownJSFunction(v8::internal::compiler::JSFunctionRef, v8::internal::maglev::ValueNode*, v8::internal::maglev::CallArguments&, v8::internal::compiler::FeedbackSource const&)+0x2ea) [0x7fc07f11be7a]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevGraphBuilder::ReduceCallForConstant(v8::internal::compiler::JSFunctionRef, v8::internal::maglev::CallArguments&, v8::internal::compiler::FeedbackSource const&)+0x3d2) [0x7fc07f0b66c2]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevGraphBuilder::ReduceCall(v8::internal::maglev::ValueNode*, v8::internal::maglev::CallArguments&, v8::internal::compiler::FeedbackSource const&)+0x305) [0x7fc07f0f9625]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevGraphBuilder::BuildCallWithFeedback(v8::internal::maglev::ValueNode*, v8::internal::maglev::CallArguments&, v8::internal::compiler::FeedbackSource const&)+0x395) [0x7fc07f11f965]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevGraphBuilder::BuildCallFromRegisters(int, v8::internal::ConvertReceiverMode)+0x28f) [0x7fc07f12317f]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevGraphBuilder::VisitSingleBytecode()+0x19df) [0x7fc07ef3db9f]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevGraphBuilder::BuildBody()+0x52b) [0x7fc07ef3584b]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevGraphBuilder::Build()+0x7df) [0x7fc07ef29aef]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevCompiler::Compile(v8::internal::LocalIsolate*, v8::internal::maglev::MaglevCompilationInfo*)+0x15ca) [0x7fc07ef2629a]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevCompilationJob::ExecuteJobImpl(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x10b) [0x7fc07f0688db]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::OptimizedCompilationJob::ExecuteJob(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x1a4) [0x7fc07c6b2414]
    /home/user/v8-bisect/v8/out/test/libv8.so(v8::internal::maglev::MaglevConcurrentDispatcher::JobTask::Run(v8::JobDelegate*)+0x85b) [0x7fc07f06d76b]
    /home/user/v8-bisect/v8/out/test/libv8_libplatform.so(v8::platform::DefaultJobWorker::Run()+0x2b9) [0x7fc077bd28a9]
    /home/user/v8-bisect/v8/out/test/libv8_libplatform.so(v8::platform::DefaultWorkerThreadsTaskRunner::WorkerThread::Run()+0x1e8) [0x7fc077bd97e8]
    /home/user/v8-bisect/v8/out/test/libv8_libbase.so(+0x8a33e) [0x7fc077c7e33e]
    ./out/test/d8(+0x163de7) [0x564f0c23ade7]
    /lib/x86_64-linux-gnu/libc.so.6(+0x9caa4) [0x7fc0762c3aa4]
    /lib/x86_64-linux-gnu/libc.so.6(+0x129c3c) [0x7fc076350c3c]
Trace/breakpoint trap
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

PoC for a JIT optimization bug in very large functions. Creates largeFuncUnrolled via new Function() with 70000 unrolled noop() calls. After 2001 warm-up calls (JIT compilation), a final call also deletes trigger_obj.initial_prop, triggering a bug in property invalidation or deoptimization within a very large JIT-compiled function.

## Capabilities

Triggers a DCHECK or crash in JIT deoptimization or property invalidation in a very large compiled function. No memory read/write.
