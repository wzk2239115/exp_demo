# 376818204: Security: Fatal error in src/compiler/js-native-context-specialization.cc, line 2980

## ClusterFuzz Report

```
# VULNERABILITY DETAILS

Violation in `DCHECK_EQ(receiver, lookup_start_object);` in `src/compiler/js-native-context-specialisation.cc on line 2980` has been detected.

`receiver` is the value of this that is assigned to the actual object when the property is called (referencing the `this` of the object being accessed), and `lookup_start_object` is the object to start exploring when searching for the property.

If the two values are not the same, optimizations can go in the wrong direction, and in particular, we suspect that memory conformance can be adversely affected.

  
# VERSION
Chrome Version: Main branch HEAD commit (a48e4a13)

Operating System: Ubuntu 22.04 LTS

# REPRODUCTION CASE

`./d8 --allow-natives-syntax ./poc.js`

---

# 1. Crash log
```
#
# Fatal error in ../../src/compiler/js-native-context-specialization.cc, line 2980
# Debug check failed: receiver == lookup_start_object (0x7e8ff71247b8 vs. 0x7ecff72492b0).
#
#
#
#FailureMessage Object: 0x7bfff6256860
==== C stack trace ===============================

    /root/v8/out/fuzzbuild/d8(___interceptor_backtrace+0x46) [0x55555897d536]
    /root/v8/out/fuzzbuild/d8(v8::base::debug::StackTrace::StackTrace()+0x22) [0x555558c727d2]
    /root/v8/out/fuzzbuild/d8(+0x371c3bf) [0x555558c703bf]
    /root/v8/out/fuzzbuild/d8(V8_Fatal(char const*, int, char const*, ...)+0x2fa) [0x555558c57e3a]
    /root/v8/out/fuzzbuild/d8(+0x3702c1f) [0x555558c56c1f]
    /root/v8/out/fuzzbuild/d8(v8::internal::compiler::JSNativeContextSpecialization::BuildPropertyLoad(v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::NameRef, v8::internal::ZoneVector<v8::internal::compiler::Node*>*, v8::internal::compiler::PropertyAccessInfo const&)+0x62b) [0x55555e1dda8b]
    /root/v8/out/fuzzbuild/d8(v8::internal::compiler::JSNativeContextSpecialization::BuildPropertyAccess(v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::NameRef, v8::internal::ZoneVector<v8::internal::compiler::Node*>*, v8::internal::compiler::PropertyAccessInfo const&, v8::internal::compiler::AccessMode)+0x95) [0x55555e1ce7e5]
    /root/v8/out/fuzzbuild/d8(v8::internal::compiler::JSNativeContextSpecialization::ReduceNamedAccess(v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::NamedAccessFeedback const&, v8::internal::compiler::AccessMode, v8::internal::compiler::Node*)+0x340c) [0x55555e1cb2fc]
    /root/v8/out/fuzzbuild/d8(v8::internal::compiler::JSNativeContextSpecialization::ReducePropertyAccess(v8::internal::compiler::Node*, v8::internal::compiler::Node*, v8::internal::compiler::OptionalRef<v8::internal::compiler::NameRef>, v8::internal::compiler::Node*, v8::internal::compiler::FeedbackSource const&, v8::internal::compiler::AccessMode)+0x649) [0x55555e1cf4f9]
    /root/v8/out/fuzzbuild/d8(v8::internal::compiler::JSNativeContextSpecialization::ReduceJSLoadNamedFromSuper(v8::internal::compiler::Node*)+0x289) [0x55555e1b98d9]
    /root/v8/out/fuzzbuild/d8(v8::internal::compiler::GraphReducer::Reduce(v8::internal::compiler::Node*)+0x3c1) [0x55555e074f91]
    /root/v8/out/fuzzbuild/d8(v8::internal::compiler::GraphReducer::ReduceTop()+0x6ed) [0x55555e0742bd]
    /root/v8/out/fuzzbuild/d8(v8::internal::compiler::GraphReducer::ReduceNode(v8::internal::compiler::Node*)+0x124) [0x55555e073624]
    /root/v8/out/fuzzbuild/d8(v8::internal::compiler::InliningPhase::Run(v8::internal::compiler::TFPipelineData*, v8::internal::Zone*)+0xb27) [0x55555d9e6a77]
    /root/v8/out/fuzzbuild/d8(auto v8::internal::compiler::PipelineImpl::Run<v8::internal::compiler::InliningPhase>()+0x186) [0x55555d7fb896]
    /root/v8/out/fuzzbuild/d8(v8::internal::compiler::PipelineImpl::CreateGraph()+0x38e) [0x55555d7eedae]
    /root/v8/out/fuzzbuild/d8(v8::internal::compiler::PipelineCompilationJob::ExecuteJobImpl(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x32e) [0x55555d7edd6e]
    /root/v8/out/fuzzbuild/d8(v8::internal::OptimizedCompilationJob::ExecuteJob(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x2e6) [0x555559244576]
    /root/v8/out/fuzzbuild/d8(v8::internal::OptimizingCompileDispatcher::CompileTask::Run(v8::JobDelegate*)+0x709) [0x5555594b2eb9]
    /root/v8/out/fuzzbuild/d8(v8::platform::DefaultJobState::Join()+0x599) [0x555558c76439]
    /root/v8/out/fuzzbuild/d8(v8::platform::DefaultJobHandle::Join()+0x3a) [0x555558c77b4a]
    /root/v8/out/fuzzbuild/d8(+0x3f5e65b) [0x5555594b265b]
    /root/v8/out/fuzzbuild/d8(+0x7811103) [0x55555cd65103]
```

# 2. Stacktrace with symbols

```
#0  0x0000555558c6785c in v8::base::OS::Abort()::$_0::operator()() const (this=<optimized out>) at ../../src/base/platform/platform-posix.cc:730
#1  v8::base::OS::Abort () at ../../src/base/platform/platform-posix.cc:730
#2  0x0000555558c57e56 in V8_Fatal (file=<optimized out>, line=<optimized out>, format=0x5555576cb9a0 <str> "Debug check failed: %s.") at ../../src/base/logging.cc:215
#3  0x0000555558c56c1f in v8::base::(anonymous namespace)::DefaultDcheckHandler (file=0x55555819b000 <str> "../../src/compiler/js-native-context-specialization.cc", line=2980, message=0x7c6ff70e1590 "receiver == lookup_start_object (0x7e8ff71247b8 vs. 0x7ecff72492b0)") at ../../src/base/logging.cc:59
#4  0x000055555e1dda8b in v8::internal::compiler::JSNativeContextSpecialization::BuildPropertyLoad (this=<optimized out>, lookup_start_object=<optimized out>, receiver=<optimized out>, context=<optimized out>, frame_state=<optimized out>, effect=0x7ecff72493b8, control=0x7e8ff7124e78, name=..., if_exceptions=<optimized out>, access_info=...) at ../../src/compiler/js-native-context-specialization.cc:2980
#5  0x000055555e1ce7e5 in v8::internal::compiler::JSNativeContextSpecialization::BuildPropertyAccess (this=0x7bfff63da340, lookup_start_object=lookup_start_object@entry=0x7ecff72492b0, receiver=0x7e8ff71247b8, value=value@entry=0x7e4ff728aaa0, context=context@entry=0x7e4ff7289f80, frame_state=0x7ecff7248628, effect=0x7ecff72493b8, control=0x7e8ff7124e78, name=..., if_exceptions=0x0, access_info=..., access_mode=v8::internal::compiler::AccessMode::kLoad) at ../../src/compiler/js-native-context-specialization.cc:3028
#6  0x000055555e1cb2fc in v8::internal::compiler::JSNativeContextSpecialization::ReduceNamedAccess (this=<optimized out>, node=0x7ecff72484c0, value=<optimized out>, feedback=..., access_mode=<optimized out>, key=<optimized out>) at ../../src/compiler/js-native-context-specialization.cc:1654
#7  0x000055555e1cf4f9 in v8::internal::compiler::JSNativeContextSpecialization::ReducePropertyAccess (this=<optimized out>, node=<optimized out>, key=0x0, static_name=..., value=<optimized out>, source=..., access_mode=<optimized out>) at ../../src/compiler/js-native-context-specialization.cc:2566
#8  0x000055555e1b98d9 in v8::internal::compiler::JSNativeContextSpecialization::ReduceJSLoadNamedFromSuper (this=<optimized out>, node=0x7ecff72484c0) at ../../src/compiler/js-native-context-specialization.cc:1894
#9  0x000055555e074f91 in v8::internal::compiler::Reducer::Reduce (this=0x7bfff63da340, node=0x7ecff72484c0, observe_node_manager=0x0) at ../../src/compiler/graph-reducer.cc:34
#10 v8::internal::compiler::GraphReducer::Reduce (this=0x7bfff63da020, node=<optimized out>) at ../../src/compiler/graph-reducer.cc:105
#11 0x000055555e0742bd in v8::internal::compiler::GraphReducer::ReduceTop (this=0x7bfff63da020) at ../../src/compiler/graph-reducer.cc:178
#12 0x000055555e073624 in v8::internal::compiler::GraphReducer::ReduceNode (this=0x7bfff63da020, node=<optimized out>) at ../../src/compiler/graph-reducer.cc:75
#13 0x000055555d9e6a77 in v8::internal::compiler::InliningPhase::Run (this=<optimized out>, data=0x7daff70e2518, temp_zone=<optimized out>) at ../../src/compiler/pipeline.cc:1003
#14 0x000055555d7fb896 in _ZN2v88internal8compiler12PipelineImpl3RunITkNS1_10turboshaft13TurbofanPhaseENS1_13InliningPhaseEJEEEDaDpOT0_ (this=0x7daff70e2940) at ../../src/compiler/pipeline.cc:916
#15 0x000055555d7eedae in v8::internal::compiler::PipelineImpl::CreateGraph (this=<optimized out>) at ../../src/compiler/pipeline.cc:2538
#16 0x000055555d7edd6e in v8::internal::compiler::PipelineCompilationJob::ExecuteJobImpl (this=0x7daff70e2380, stats=<optimized out>, local_isolate=<optimized out>) at ../../src/compiler/pipeline.cc:817
#17 0x0000555559244576 in v8::internal::OptimizedCompilationJob::ExecuteJob (this=<optimized out>, stats=<optimized out>, local_isolate=0x7bfff643b060) at ../../src/codegen/compiler.cc:486
#18 0x00005555594b2eb9 in v8::internal::OptimizingCompileDispatcher::CompileNext (this=0x7cfff70e0940, job=0x7daff70e2380, local_isolate=0x7bfff643b060) at ../../src/compiler-dispatcher/optimizing-compile-dispatcher.cc:96
#19 v8::internal::OptimizingCompileDispatcher::CompileTask::Run (this=<optimized out>, delegate=<optimized out>) at ../../src/compiler-dispatcher/optimizing-compile-dispatcher.cc:56
#20 0x0000555558c76439 in v8::platform::DefaultJobState::Join (this=0x7d0ff70e4018) at ../../src/libplatform/default-job.cc:141
#21 0x0000555558c77b4a in v8::platform::DefaultJobHandle::Join (this=0x7c2ff713cbc0) at ../../src/libplatform/default-job.cc:238
#22 0x00005555594b265b in v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0::operator()() const (this=<optimized out>) at ../../src/compiler-dispatcher/optimizing-compile-dispatcher.cc:143
#23 v8::internal::LocalHeap::ParkAndExecuteCallback<v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0>(v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0) (this=0x7dcff70e1e90, callback=...) at ../../src/heap/local-heap-inl.h:65
#24 v8::internal::LocalHeap::ExecuteMainThreadWhileParked<v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0>(v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0)::{lambda()#1}::operator()() const (this=<optimized out>) at ../../src/heap/local-heap-inl.h:89
#25 heap::base::Stack::SetMarkerAndCallbackImpl<v8::internal::LocalHeap::ExecuteMainThreadWhileParked<v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0>(v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0)::{lambda()#1}>(heap::base::Stack*, void*, void const*) (stack=0x7dcff70e2618, argument=<optimized out>, stack_end=<optimized out>) at ../../src/heap/base/stack.h:170
#26 0x000055555cd65103 in PushAllRegistersAndIterateStack ()
#27 0x00005555594ac6f1 in heap::base::Stack::SetMarkerAndCallback<v8::internal::LocalHeap::ExecuteMainThreadWhileParked<v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0>(v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0)::{lambda()#1}>(v8::internal::LocalHeap::ExecuteMainThreadWhileParked<v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0>(v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0)::{lambda()#1}) (this=0x7bfff53006a4, callback=...) at ../../src/heap/base/stack.h:69
debug2: channel 0: window 998852 sent adjust 49724
#28 v8::internal::LocalHeap::ExecuteMainThreadWhileParked<v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0>(v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0) (this=0x7dcff70e1e90, callback=...) at ../../src/heap/local-heap-inl.h:88
#29 v8::internal::LocalIsolate::ExecuteMainThreadWhileParked<v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0>(v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks()::$_0) (this=<optimized out>, callback=...) at ../../src/execution/local-isolate-inl.h:37
#30 v8::internal::OptimizingCompileDispatcher::AwaitCompileTasks (this=0x7cfff70e0940) at ../../src/compiler-dispatcher/optimizing-compile-dispatcher.cc:142
#31 0x000055555b63be03 in v8::internal::(anonymous namespace)::FinalizeOptimization (isolate=isolate@entry=0x7f0ff70e1000) at ../../src/runtime/runtime-test.cc:625
#32 0x000055555b5ced7a in v8::internal::__RT_impl_Runtime_OptimizeOsr (args=..., isolate=0x7f0ff70e1000) at ../../src/runtime/runtime-test.cc:803
#33 0x000055555b5cce5b in v8::internal::Runtime_OptimizeOsr (args_length=<optimized out>, args_object=<optimized out>, isolate=0x7f0ff70e1000) at ../../src/runtime/runtime-test.cc:668
#34 0x00005555605029f6 in Builtins_CEntry_Return1_ArgvOnStack_NoBuiltinExit ()
```

Reporter credit: Changheon Lee (@2rr0r4o3)
```

## Vulnerability Description

Short PoC that defines class C1 extending String. C1's constructor contains a for-loop that calls %OptimizeOsr() (on-stack replacement optimization trigger) 5 times, then calls super() and accesses super.length. The OSR happens while inside the loop before super() is called, resulting in an inconsistent object state (the derived class instance is not fully initialized when OSR'd code runs).

## Capabilities

Triggers a DCHECK or crash in OSR optimization of a derived class constructor before super() is called. No memory read/write.
