# 398431403: Security: Fatal error in src/compiler/turbofan-typer.cc, line 451

## ClusterFuzz Report

```
# VULNERABILITY DETAILS

A type inconsistency was identified in `src/compiler/turbofan-typer.cc, line 451`.

More specifically, the previous type and current type of PhiNode in `UpdateType` appear to be inconsistent.

# VERSION

Chrome Version: V8 main branch commit `e3b5497f`

Operating System: Ubuntu 22.04 LTS

# REPRODUCTION CASE

`./d8 --allow-natives-syntax --jit-fuzzing ./poc.js`

# Type of crash:

UpdateType error

# Crash State:

```
1. Crash log

#
# Fatal error in ../../src/compiler/turbofan-typer.cc, line 451
# UpdateType error for node 133: ObjectIsArrayBufferView(88)
  88: Phi[kRepTagged](65, 133, 84)

#
#
#
#FailureMessage Object: 0x7fffffffb7b0
==== C stack trace ===============================

    /home/error403/v8/out/fuzzbuild/d8(v8::base::debug::StackTrace::StackTrace()+0x13) [0x5555571f51e3]
    /home/error403/v8/out/fuzzbuild/d8(+0x1ca09eb) [0x5555571f49eb]
    /home/error403/v8/out/fuzzbuild/d8(V8_Fatal(char const*, int, char const*, ...)+0x183) [0x5555571ed543]
    /home/error403/v8/out/fuzzbuild/d8(v8::internal::compiler::Typer::Visitor::UpdateType(v8::internal::compiler::Node*, v8::internal::compiler::Type)+0x202) [0x555559126d12]
    /home/error403/v8/out/fuzzbuild/d8(v8::internal::compiler::GraphReducer::Reduce(v8::internal::compiler::Node*)+0xb8) [0x555558e8b888]
    /home/error403/v8/out/fuzzbuild/d8(v8::internal::compiler::GraphReducer::ReduceTop()+0x3de) [0x555558e8b21e]
    /home/error403/v8/out/fuzzbuild/d8(v8::internal::compiler::GraphReducer::ReduceNode(v8::internal::compiler::Node*)+0x80) [0x555558e8a830]
    /home/error403/v8/out/fuzzbuild/d8(v8::internal::compiler::Typer::Run(v8::internal::ZoneVector<v8::internal::compiler::Node*> const&, v8::internal::compiler::LoopVariableOptimizer*)+0x127) [0x555559117347]
    /home/error403/v8/out/fuzzbuild/d8(v8::internal::compiler::TyperPhase::Run(v8::internal::compiler::TFPipelineData*, v8::internal::Zone*, v8::internal::compiler::Typer*)+0x1af) [0x555558be975f]
    /home/error403/v8/out/fuzzbuild/d8(auto v8::internal::compiler::PipelineImpl::Run<v8::internal::compiler::TyperPhase, v8::internal::compiler::Typer*>(v8::internal::compiler::Typer*&&)+0x8d) [0x555558aff5dd]
    /home/error403/v8/out/fuzzbuild/d8(v8::internal::compiler::PipelineImpl::OptimizeTurbofanGraph(v8::internal::compiler::Linkage*)+0x187) [0x555558af9db7]
    /home/error403/v8/out/fuzzbuild/d8(v8::internal::compiler::PipelineCompilationJob::ExecuteJobImpl(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x144) [0x555558af9044]
    /home/error403/v8/out/fuzzbuild/d8(v8::internal::OptimizedCompilationJob::ExecuteJob(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x7f) [0x5555573ecb1f]
    /home/error403/v8/out/fuzzbuild/d8(+0x1ea7ce7) [0x5555573fbce7]
    /home/error403/v8/out/fuzzbuild/d8(v8::internal::Compiler::CompileOptimized(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::ConcurrencyMode, v8::internal::CodeKind)+0x28c) [0x5555573fe06c]
    /home/error403/v8/out/fuzzbuild/d8(+0x2a3df3e) [0x555557f91f3e]
    /home/error403/v8/out/fuzzbuild/d8(+0x2a37ae5) [0x555557f8bae5]
    /home/error403/v8/out/fuzzbuild/d8(v8::internal::Runtime_OptimizeTurbofanEager(int, unsigned long*, v8::internal::Isolate*)+0x90) [0x555557f8b730]
    /home/error403/v8/out/fuzzbuild/d8(+0x4d75b3d) [0x55555a2c9b3d
```

```
2. Backtrace with symbols

#0  0x00005555571f2182 in v8::base::OS::Abort()::$_0::operator()() const (this=<optimized out>) at ../../src/base/platform/platform-posix.cc:731
#1  v8::base::OS::Abort () at ../../src/base/platform/platform-posix.cc:731
#2  0x00005555571ed551 in V8_Fatal (file=0x555556aeefd0 "../../src/compiler/turbofan-typer.cc", line=line@entry=451, format=0x555556b1d01c "UpdateType error for node %s") at ../../src/base/logging.cc:215
#3  0x0000555559126d12 in v8::internal::compiler::Typer::Visitor::UpdateType (this=0x7fffffffbf80, node=<optimized out>, current=...) at ../../src/compiler/turbofan-typer.cc:451
#4  0x0000555558e8b888 in v8::internal::compiler::Reducer::Reduce (this=0x7fffffffbf80, node=0x55555a8ed870, observe_node_manager=0x0) at
 ../../src/compiler/graph-reducer.cc:34
#5  v8::internal::compiler::GraphReducer::Reduce (this=this@entry=0x7fffffffbe88, node=node@entry=0x55555a8ed870) at ../../src/compiler/graph-reducer.cc:105
#6  0x0000555558e8b21e in v8::internal::compiler::GraphReducer::ReduceTop (this=this@entry=0x7fffffffbe88) at ../../src/compiler/graph-reducer.cc:178
#7  0x0000555558e8a830 in v8::internal::compiler::GraphReducer::ReduceNode (this=0x7fffffffbe88, node=<optimized out>) at ../../src/compiler/graph-reducer.cc:75
#8  0x0000555559117347 in v8::internal::compiler::Typer::Run (this=<optimized out>, roots=..., induction_vars=0x7fffffffc018) at ../../src/compiler/turbofan-typer.cc:479
#9  0x0000555558be975f in v8::internal::compiler::TyperPhase::Run (this=this@entry=0x7fffffffc187, data=data@entry=0x55555a8a3bd0, temp_zone=temp_zone@entry=0x55555a8c00f0, typer=0x55555a8a5010) at ../../src/compiler/pipeline.cc:1044
#10 0x0000555558aff5dd in _ZN2v88internal8compiler12PipelineImpl3RunITkNS1_10turboshaft13TurbofanPhaseENS1_10TyperPhaseEJPNS1_5TyperEEEEDaDpOT0_ (this=this@entry=0x55555a8a4000, args=@0x7fffffffc1d0: 0x55555a8a5010) at ../../src/compiler/pipeline.cc:839
#11 0x0000555558af9db7 in v8::internal::compiler::PipelineImpl::OptimizeTurbofanGraph (this=this@entry=0x55555a8a4000, linkage=0x55555a89dc58) at ../../src/compiler/pipeline.cc:1978
#12 0x0000555558af9044 in v8::internal::compiler::PipelineCompilationJob::ExecuteJobImpl (this=0x55555a8a3a30, stats=<optimized out>, local_isolate=<optimized out>) at ../../src/compiler/pipeline.cc:778
#13 0x00005555573ecb1f in v8::internal::OptimizedCompilationJob::ExecuteJob (this=this@entry=0x55555a8a3a30, stats=0x55555a83e568, local_isolate=0x55555a864b30) at ../../src/codegen/compiler.cc:470
#14 0x00005555573fbce7 in v8::internal::(anonymous namespace)::CompileTurbofan_NotConcurrent (isolate=0x55555a82a000, job=0x55555a8a3a30) at ../../src/codegen/compiler.cc:1103
#15 v8::internal::(anonymous namespace)::CompileTurbofan (isolate=0x55555a82a000, function=..., shared=..., mode=v8::internal::ConcurrencyMode::kSynchronous, osr_offset=..., result_behavior=v8::internal::(anonymous namespace)::CompileResultBehavior::kDefault) at ../../src/codegen/compiler.cc:1248
#16 v8::internal::(anonymous namespace)::GetOrCompileOptimized (isolate=isolate@entry=0x55555a82a000, function=function@entry=..., mode=v8::internal::ConcurrencyMode::kSynchronous, code_kind=code_kind@entry=v8::internal::CodeKind::TURBOFAN_JS, osr_offset=osr_offset@entry=..., result_behavior=result_behavior@entry=v8::internal::(anonymous namespace)::CompileResultBehavior::kDefault) at ../../src/codegen/compiler.cc:1416
#17 0x00005555573fe06c in v8::internal::Compiler::CompileOptimized (isolate=0x55555a82a000, function=..., mode=v8::internal::ConcurrencyMode::kSynchronous, code_kind=<optimized out>) at ../../src/codegen/compiler.cc:3197
#18 0x0000555557f91f3e in v8::internal::(anonymous namespace)::CompileOptimized (function=function@entry=..., mode=mode@entry=v8::internal::ConcurrencyMode::kSynchronous, target_kind=target_kind@entry=v8::internal::CodeKind::TURBOFAN_JS, isolate=isolate@entry=0x55555a82a000) at ../../src/runtime/runtime-compiler.cc:185
#19 0x0000555557f8bae5 in v8::internal::__RT_impl_Runtime_OptimizeTurbofanEager (args=..., isolate=isolate@entry=0x55555a82a000) at ../../src/runtime/runtime-compiler.cc:227
#20 0x0000555557f8b730 in v8::internal::Runtime_OptimizeTurbofanEager (args_length=<optimized out>, args_object=0x7fffffffc5f8, isolate=0x55555a82a000) at ../../src/runtime/runtime-compiler.cc:222
#21 0x000055555a2c9b3d in Builtins_CEntry_Return1_ArgvOnStack_NoBuiltinExit ()
#22 0x000055555a1925f3 in Builtins_OptimizeTurbofanEager ()
#23 0x000055555a190863 in Builtins_InterpreterEntryTrampoline ()
```

Reporter credit: Changheon Lee (@2rr0r4o3)
```

## Vulnerability Description

Short TurboFan optimization PoC. Creates an empty BigInt64Array v1, defines f2 that returns ArrayBuffer.isView(a3), defines f6 that returns ([f6]).reduceRight(f2, v1). After two warm-up calls and %OptimizeFunctionOnNextCall(f6), TurboFan compiles f6 with type feedback that v1 is a BigInt64Array accumulator, but the array element [f6] is a function — type mismatch in reduceRight's callback.

## Capabilities

Triggers a DCHECK or crash in TurboFan's array reduceRight optimization with inconsistent accumulator type. No memory read/write.
