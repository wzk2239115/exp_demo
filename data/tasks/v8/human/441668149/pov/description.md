# 441668149: Maglev type confusion via corrupted Phi node metadata

## ClusterFuzz Report

```
```

#
# Fatal error in ../../src/base/bit-field.h, line 56
# Debug check failed: is_valid(value).
#
#
#
#FailureMessage Object: 0x7bbc00ca1460
==== C stack trace ===============================

    ../v8/v8/out/x64.build/d8(__interceptor_backtrace+0x46) [0x56156e9e8286]
    /home/user/v8/v8/out/x64.build/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7fbc2899b0b3]
    /home/user/v8/v8/out/x64.build/libv8_libplatform.so(+0x392ea) [0x7fbc288e62ea]
    /home/user/v8/v8/out/x64.build/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x2a0) [0x7fbc289617f0]
    /home/user/v8/v8/out/x64.build/libv8_libbase.so(+0x5a7ef) [0x7fbc289607ef]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MergePointInterpreterFrameState::MergeValue(v8::internal::maglev::MaglevGraphBuilder const*, v8::internal::interpreter::Register, v8::internal::maglev::KnownNodeAspects const&, v8::internal::maglev::ValueNode*, v8::internal::maglev::ValueNode*, v8::base::ThreadedListBase<v8::internal::maglev::MergePointInterpreterFrameState::Alternatives, v8::base::EmptyBase, v8::base::ThreadedListTraits<v8::internal::maglev::MergePointInterpreterFrameState::Alternatives>, false>*, bool)+0x1bde) [0x7fbc3140678e]
    /home/user/v8/v8/out/x64.build/libv8.so(+0x8a5e1ba) [0x7fbc314161ba]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MergePointInterpreterFrameState::MergePhis(v8::internal::maglev::MaglevGraphBuilder*, v8::internal::maglev::MaglevCompilationUnit&, v8::internal::maglev::InterpreterFrameState&, v8::internal::maglev::BasicBlock*, bool)+0x20a) [0x7fbc313fc6fa]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MergePointInterpreterFrameState::Merge(v8::internal::maglev::MaglevGraphBuilder*, v8::internal::maglev::MaglevCompilationUnit&, v8::internal::maglev::InterpreterFrameState&, v8::internal::maglev::BasicBlock*)+0x204) [0x7fbc313fc054]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MaglevGraphBuilder::VisitJump()+0x12c) [0x7fbc310a6d9c]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MaglevGraphBuilder::VisitSingleBytecode()+0xbfa) [0x7fbc30ffc9fa]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MaglevGraphBuilder::BuildBody()+0x537) [0x7fbc31025697]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MaglevGraphBuilder::Build()+0xac2) [0x7fbc310bf2c2]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MaglevCompiler::Compile(v8::internal::LocalIsolate*, v8::internal::maglev::MaglevCompilationInfo*)+0x798) [0x7fbc30e12728]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MaglevCompilationJob::ExecuteJobImpl(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x113) [0x7fbc30f98f43]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::OptimizedCompilationJob::ExecuteJob(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x1ad) [0x7fbc2e110cbd]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MaglevConcurrentDispatcher::JobTask::Run(v8::JobDelegate*)+0x8a9) [0x7fbc30f9e1c9]
    /home/user/v8/v8/out/x64.build/libv8_libplatform.so(v8::platform::DefaultJobWorker::Run()+0x2e6) [0x7fbc288e3746]
    /home/user/v8/v8/out/x64.build/libv8_libplatform.so(v8::platform::DefaultWorkerThreadsTaskRunner::WorkerThread::Run()+0x1f1) [0x7fbc288ea941]
    /home/user/v8/v8/out/x64.build/libv8_libbase.so(+0x91b2e) [0x7fbc28997b2e]
    ../v8/v8/out/x64.build/d8(+0x1999b7) [0x56156ea3f9b7]
    /lib/x86_64-linux-gnu/libc.so.6(+0x9caa4) [0x7fbc26f9faa4]
    /lib/x86_64-linux-gnu/libc.so.6(+0x129c3c) [0x7fbc2702cc3c]
Received signal 6
Aborted
```

#### VERSION

V8 version 14.1.0 (candidate)

#### REPRODUCTION CASE

Build: `python3 tools/dev/gm.py x64.debug`

Run: `./d8 poc.js`

---
Reporter credit: Shaheen Fazim
```

## Vulnerability Description

PoC for a CoverageInfo integer overflow. Generates a switch function with 65536 (0x10000) cases via new Function(), calls it 10000 times (triggering JIT compilation of a function with 65536 basic blocks), then sets Error.prepareStackTrace and triggers stack trace collection. The extremely large number of switch cases causes an integer overflow in V8's CoverageInfo or BlockCounters structure.

## Capabilities

Triggers a DCHECK or integer overflow crash in CoverageInfo/block-counter allocation for a function with 65536 switch cases. No memory read/write.
