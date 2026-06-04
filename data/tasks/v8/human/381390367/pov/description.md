# 381390367: Fatal error in src/codegen/assembler.cc, line 237

## ClusterFuzz Report

```
# VULNERABILITY DETAILS

Detected the failure of `DCHECK(position.IsKnown());` of `src/codegen/assembler.cc, line 237`.

There seems to be something wrong with the delivery process of `v8::internal::compiler::CodeGenerator::AssembleCode` or the source map.


# VERSION

Chrome Version: V8 main branch, commit 6ac2d3ad

Operating System: Ubuntu 22.04

# REPRODUCTION CASE

`node ./execute.js`

# Type of crash:

DCHECK fail

# Crash status 

```
#
# Fatal error in src/codegen/assembler.cc, line 237
# Debug check failed: position.IsKnown().
#
#FailureMessage Object: 0x7f022fffdbb0
==== C stack trace ===============================

    ./d8(v8::base::debug::StackTrace::StackTrace()+0x22) [0x562cc0ef86c2]
    ./d8(+0x1c2f387) [0x562cc0ef7387]
    ./d8(V8_Fatal(char const*, int, char const*, ...)+0x1e6) [0x562cc0ee8d66]
    ./d8(+0x1c20575) [0x562cc0ee8575]
    ./d8(v8::internal::Assembler::RecordDeoptReason(v8::internal::DeoptimizeReason, unsigned int, v8::internal::SourcePosition, int)+0x1e0) [0x562cc12336c0]
    ./d8(v8::internal::compiler::CodeGenerator::AssembleDeoptimizerCall(v8::internal::compiler::DeoptimizationExit*)+0xa2) [0x562cc3ef1162]
    ./d8(v8::internal::compiler::CodeGenerator::AssembleCode()+0xf2f) [0x562cc3ef218f]
    ./d8(auto v8::internal::compiler::turboshaft::Pipeline::Run<v8::internal::compiler::turboshaft::AssembleCodePhase>()+0x14b) [0x562cc3bf0c0b]
    ./d8(v8::internal::compiler::turboshaft::Pipeline::AssembleCode(v8::internal::compiler::Linkage*)+0xfa) [0x562cc3b33b2a]
    ./d8(+0x4843ef3) [0x562cc3b0bef3]
    ./d8(v8::internal::compiler::PipelineCompilationJob::ExecuteJobImpl(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x21b) [0x562cc3b09e2b]
    ./d8(v8::internal::OptimizedCompilationJob::ExecuteJob(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x184) [0x562cc123d2f4]
    ./d8(v8::internal::OptimizingCompileDispatcher::CompileNext(v8::internal::TurbofanCompilationJob*, v8::internal::LocalIsolate*)+0x37) [0x562cc1392287]
    ./d8(v8::internal::OptimizingCompileDispatcher::CompileTask::Run(v8::JobDelegate*)+0x30f) [0x562cc1398c9f]
    ./d8(v8::platform::DefaultJobWorker::Run()+0x12f) [0x562cc0efb55f]
    ./d8(v8::platform::DefaultWorkerThreadsTaskRunner::WorkerThread::Run()+0xa5) [0x562cc0f06ee5]
    ./d8(+0x1c2ca69) [0x562cc0ef4a69]
    /lib/x86_64-linux-gnu/libc.so.6(+0x94ac3) [0x7f025a5eaac3]
    /lib/x86_64-linux-gnu/libc.so.6(+0x126850) [0x7f025a67c850]
Trace/breakpoint trap (core dumped)
```

```
0x000055555717f08e in v8::base::OS::Abort()::$_0::operator()() const (this=<optimized out>) at ../../src/base/platform/platform-posix.cc:730, IMMEDIATE_CRASH();
#0  0x000055555717f08e in v8::base::OS::Abort()::$_0::operator()() const (this=<optimized out>) at ../../src/base/platform/platform-posix.cc:730
#1  v8::base::OS::Abort () at src/base/platform/platform-posix.cc:730
#2  0x0000555557174d74 in V8_Fatal (file=0x555556878990 "src/codegen/assembler.cc", line=237, format=<optimized out>) at src/base/logging.cc:215
#3  0x0000555557174575 in v8::base::(anonymous namespace)::DefaultDcheckHandler (file=0x55555b7b7d80 "", line=0, message=0x7ffff7b35010 "\\200\\272\\032") at src/base/logging.cc:59
#4  0x00005555574bf6c0 in v8::internal::Assembler::RecordDeoptReason (this=0x7fff1c00bc00, reason=v8::internal::DeoptimizeReason::kNotASmi, node_id=32, position=..., id=0) at src/codegen/assembler.cc:237
#5  0x000055555a17d162 in v8::internal::compiler::CodeGenerator::AssembleDeoptimizerCall (this=this@entry=0x7fff1c00bb30, exit=exit@entry=0x7fff1c017368) at src/compiler/backend/code-generator.cc:176
#6  0x000055555a17e18f in v8::internal::compiler::CodeGenerator::AssembleCode (this=0x7fff1c00bb30) at src/compiler/backend/code-generator.cc:405
#7  0x0000555559e7cc0b in v8::internal::compiler::turboshaft::AssembleCodePhase::Run (data=<optimized out>, temp_zone=0x55555c551170, this=<optimized out>) at src/compiler/turboshaft/register-allocation-phase.h:201
#8 _ZN2v88internal8compiler10turboshaft8Pipeline3RunITkNS2_15TurboshaftPhaseENS2_17AssembleCodePhaseEJEEEDaDpOT0_ (this=this@entry=0x7fffc1ffa270) at src/compiler/turboshaft/pipelines.h:76
#9  0x0000555559dbfb2a in v8::internal::compiler::turboshaft::Pipeline::AssembleCode (this=this@entry=0x7fffc1ffa270, linkage=linkage@entry=0x55555c556130) at src/compiler/turboshaft/pipelines.h:489
#10 0x0000555559d97ef3 in v8::internal::compiler::(anonymous namespace)::GenerateCodeFromTurboshaftGraph (use_turboshaft_instruction_selection=<optimized out>, linkage=linkage@entry=0x55555c556130, turboshaft_pipeline=..., turbofan_pipeline=turbofan_pipeline@entry=0x55555c551100, osr_helper=...) at src/compiler/pipeline.cc:531
#11 0x0000555559d95e2b in v8::internal::compiler::PipelineCompilationJob::ExecuteJobImpl (this=<optimized out>, stats=<optimized out>, local_isolate=<optimized out>) at src/compiler/pipeline.cc:846
#12 0x00005555574c92f4 in v8::internal::OptimizedCompilationJob::ExecuteJob (this=0x55555c550b40, stats=0x0, local_isolate=0x7fffc1ffa368) at src/codegen/compiler.cc:469
#13 0x000055555761e287 in v8::internal::OptimizingCompileDispatcher::CompileNext (this=0x55555c4e3a20, job=job@entry=0x55555c550b40, local_isolate=local_isolate@entry=0x7fffc1ffa368) at src/compiler-dispatcher/optimizing-compile-dispatcher.cc:96
#14 0x0000555557624c9f in v8::internal::OptimizingCompileDispatcher::CompileTask::Run (this=0x55555c4e3b40, delegate=0x7fffc1ffac78) at ../../src/compiler-dispatcher/optimizing-compile-dispatcher.cc:56
#15 0x000055555718755f in v8::platform::DefaultJobWorker::Run (this=0x55555c5500e0) at src/libplatform/default-job.h:147\n' +
#16 0x0000555557192ee5 in v8::platform::DefaultWorkerThreadsTaskRunner::WorkerThread::Run (this=0x55555c469e50) at src/libplatform/default-worker-threads-task-runner.cc:95
#17 0x0000555557180a69 in v8::base::Thread::NotifyStartedAndRun (this=0x55555c469e50) at src/base/platform/platform.h:626
#18 v8::base::ThreadEntry (arg=0x55555c469e50) at src/base/platform/platform-posix.cc:1231
#19 0x00007ffff7cedac3 in start_thread (arg=<optimized out>) at nptl/pthread_create.c:44
#20 0x00007ffff7d7f850 in clone3 () at sysdeps/unix/sysv/linux/x86_64/clone3.S:81
```

##### CREDIT INFORMATION

Reporter credit: Changheon Lee (@2rr0r4o3)
```

## Vulnerability Description

Short PoC. Defines f0 which recursively calls itself inside a try/catch to exhaust the stack. After catching the stack overflow, it evals a template string containing code that calls console.profile() and runs a short for-loop. The eval inside a deeply recursive scope introduces a context allocation bug or incorrect scope chain traversal.

## Capabilities

Triggers a DCHECK or incorrect behavior related to scope context allocation inside eval in a recursive try/catch. No memory read/write.
