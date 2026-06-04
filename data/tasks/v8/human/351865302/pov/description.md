# 351865302: Fatal error in ../../src/compiler/simplified-lowering.cc, line 568

## ClusterFuzz Report

```
Security: Fatal error in ../../src/compiler/simplified-lowering.cc, line 568

Steps to reproduce the problem:
build flag:
gn gen out/fuzzbuild_new --args='is_debug=false dcheck_always_on=true v8_static_library=true v8_enable_slow_dchecks=true v8_enable_v8_checks=true v8_enable_verify_heap=true v8_enable_verify_csa=true v8_fuzzilli=true sanitizer_coverage_flags="trace-pc-guard" target_cpu="x64"'

environment:
Ubuntu 22.04.2 LTS 5.19.0-42-generic
v8 Version: commit 106f228ca86505edb70aa575c99fd2d636819d17

or download d8 binary with 
https://www.googleapis.com/download/storage/v1/b/v8-asan/o/linux-debug%2Fd8-arm-asan-linux-debug-v8-component-94899.zip?generation=1720486183963990&alt=media

run with:
./d8 --allow-natives-syntax --jit-fuzzing poc.js

result will be:

#
# Fatal error in ../../src/compiler/simplified-lowering.cc, line 568
# Debug check failed: current_type.Maybe(integer).
#
#
#
#FailureMessage Object: 0x78fd1452b860
==== C stack trace ===============================

    ./d8(__interceptor_backtrace+0x46) [0x5b66cb1ee616]
    /home/goushi/prebuild_v8/94899/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x78fd4b165963]
    /home/goushi/prebuild_v8/94899/libv8_libplatform.so(+0x3172a) [0x78fd4b0b772a]
    /home/goushi/prebuild_v8/94899/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x2a0) [0x78fd4b126d00]
    /home/goushi/prebuild_v8/94899/libv8_libbase.so(+0x50e0f) [0x78fd4b125e0f]
    /home/goushi/prebuild_v8/94899/libv8.so(v8::internal::compiler::RepresentationSelector::Weaken(v8::internal::compiler::Node*, v8::internal::compiler::Type, v8::internal::compiler::Type)+0x3e2) [0x78fd4890e6b2]
    /home/goushi/prebuild_v8/94899/libv8.so(v8::internal::compiler::RepresentationSelector::UpdateFeedbackType(v8::internal::compiler::Node*)+0x11e6) [0x78fd489041e6]
    /home/goushi/prebuild_v8/94899/libv8.so(v8::internal::compiler::RepresentationSelector::RetypeNode(v8::internal::compiler::Node*)+0x3d) [0x78fd48902abd]
    /home/goushi/prebuild_v8/94899/libv8.so(v8::internal::compiler::RepresentationSelector::RunRetypePhase()+0x459) [0x78fd488e1b89]
    /home/goushi/prebuild_v8/94899/libv8.so(v8::internal::compiler::SimplifiedLowering::LowerAllNodes()+0x477) [0x78fd488cf447]
    /home/goushi/prebuild_v8/94899/libv8.so(v8::internal::compiler::SimplifiedLoweringPhase::Run(v8::internal::compiler::TFPipelineData*, v8::internal::Zone*, v8::internal::compiler::Linkage*)+0x234) [0x78fd48843fe4]
    /home/goushi/prebuild_v8/94899/libv8.so(auto v8::internal::compiler::PipelineImpl::Run<v8::internal::compiler::SimplifiedLoweringPhase, v8::internal::compiler::Linkage*&>(v8::internal::compiler::Linkage*&)+0x17e) [0x78fd48791c3e]
    /home/goushi/prebuild_v8/94899/libv8.so(v8::internal::compiler::PipelineImpl::OptimizeTurbofanGraph(v8::internal::compiler::Linkage*)+0xaef) [0x78fd4878460f]
    /home/goushi/prebuild_v8/94899/libv8.so(v8::internal::compiler::PipelineCompilationJob::ExecuteJobImpl(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x319) [0x78fd487827a9]
    /home/goushi/prebuild_v8/94899/libv8.so(v8::internal::OptimizedCompilationJob::ExecuteJob(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x1a5) [0x78fd43de2e45]
    /home/goushi/prebuild_v8/94899/libv8.so(v8::internal::OptimizingCompileDispatcher::CompileNext(v8::internal::TurbofanCompilationJob*, v8::internal::LocalIsolate*)+0x4a) [0x78fd43fe33aa]
    /home/goushi/prebuild_v8/94899/libv8.so(v8::internal::OptimizingCompileDispatcher::CompileTask::Run(v8::JobDelegate*)+0x5f1) [0x78fd43fe9911]
    /home/goushi/prebuild_v8/94899/libv8_libplatform.so(v8::platform::DefaultJobWorker::Run()+0x2b9) [0x78fd4b0b4969]
    /home/goushi/prebuild_v8/94899/libv8_libplatform.so(v8::platform::DefaultWorkerThreadsTaskRunner::WorkerThread::Run()+0x1f1) [0x78fd4b0bb901]
    /home/goushi/prebuild_v8/94899/libv8_libbase.so(+0x8e413) [0x78fd4b163413]
    ./d8(+0x15ef27) [0x5b66cb242f27]
    /lib/x86_64-linux-gnu/libc.so.6(+0x94ac3) [0x78fd3da94ac3]
    /lib/x86_64-linux-gnu/libc.so.6(+0x126850) [0x78fd3db26850]
[1]    19319 trace trap  ./d8 --allow-natives-syntax --jit-fuzzing poc.js
```

## Vulnerability Description

Fuzzer-generated PoC with nested closures and complex loop structure. Function opt() contains a for-loop whose condition is an IIFE with an inner for-loop computing Object.is(~i8/i4, i8/-14615) and updating v0 via v26 = --v0. The outer loop's update is also an IIFE. The return value references undeclared v41. Uses --allow-natives-syntax implicitly (no %Optimize call visible, but likely triggered by fuzzer flags). Likely triggers a type inference or loop optimization bug.

## Capabilities

Crashes with a ReferenceError (v41 not defined) or a DCHECK in the optimizer. No memory read/write.
