# 426157225: Debug check failed: predecessors_so_far_ < predecessor_count_ (2 vs. 2). in v8

## ClusterFuzz Report

```
VULNERABILITY DETAILS
## INTRODUCE
After bisect, it was determined that following commit caused this problem.

- Commit Info
    - Version: 100753
    - link: https://crrev.com/1af713dbe9344e057c55ee3a45d2f3045cf36f67
- Commit Message

```
commit 1af713dbe9344e057c55ee3a45d2f3045cf36f67
Author: Marja Hölttä <marja@chromium.org>
Date:   Tue Jun 10 14:21:22 2025 +0200

    [maglev] Support (inlining) polymorphic calls
    
    Bug:411351177
    
    Change-Id: I086f47cb03214afec404c6d56cc9e2e364526e53
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/6607688
    Commit-Queue: Marja Hölttä <marja@chromium.org>
    Reviewed-by: Leszek Swirski <leszeks@chromium.org>
    Reviewed-by: Victor Gomes <victorgomes@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#100753}

```

## CRASH LOG
- Debug output

```bash
# CMD: /tmp/d8-linux-debug-v8-component-100914/d8 --allow-natives-syntax --maglev-poly-calls --turbolev poc.js
# OUTPUT ==============================================================


#
# Fatal error in ../../src/maglev/maglev-interpreter-frame-state.cc, line 738
# Debug check failed: predecessors_so_far_ < predecessor_count_ (2 vs. 2).
#
#
#
#FailureMessage Object: 0x7ffd026d4bd0
==== C stack trace ===============================

    /tmp/d8-linux-debug-v8-component-100914/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7f58f024d943]
    /tmp/d8-linux-debug-v8-component-100914/libv8_libplatform.so(+0x1bb1d) [0x7f58f01f4b1d]
    /tmp/d8-linux-debug-v8-component-100914/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x194) [0x7f58f022f244]
    /tmp/d8-linux-debug-v8-component-100914/libv8_libbase.so(+0x2cc05) [0x7f58f022ec05]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(v8::internal::maglev::MergePointInterpreterFrameState::Merge(v8::internal::maglev::MaglevGraphBuilder*, v8::internal::maglev::MaglevCompilationUnit&, v8::internal::maglev::InterpreterFrameState&, v8::internal::maglev::BasicBlock*)+0x240) [0x7f58edec4fe0]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(v8::internal::maglev::MaglevGraphBuilder::VisitSingleBytecode()+0x11c4) [0x7f58edc14df4]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(v8::internal::maglev::MaglevGraphBuilder::BuildBody()+0x1c4) [0x7f58edc0f804]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(v8::internal::maglev::MaglevGraphBuilder::Build()+0x3b3) [0x7f58edc0b493]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(v8::internal::compiler::turboshaft::TurbolevGraphBuildingPhase::Run(v8::internal::compiler::turboshaft::PipelineData*, v8::internal::Zone*, v8::internal::compiler::Linkage*)+0x4ad) [0x7f58ef505e7d]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(auto v8::internal::compiler::turboshaft::Pipeline::Run<v8::internal::compiler::turboshaft::TurbolevGraphBuildingPhase, v8::internal::compiler::Linkage*&>(v8::internal::compiler::Linkage*&)+0xf5) [0x7f58eec49045]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(v8::internal::compiler::turboshaft::Pipeline::CreateGraphWithMaglev(v8::internal::compiler::Linkage*)+0xbb) [0x7f58eec35bcb]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(v8::internal::compiler::PipelineCompilationJob::ExecuteJobImpl(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x1d7) [0x7f58eec35997]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(v8::internal::OptimizedCompilationJob::ExecuteJob(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x92) [0x7f58ec83bac2]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(+0x346bbe6) [0x7f58ec86bbe6]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(+0x3451fd4) [0x7f58ec851fd4]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(v8::internal::Compiler::CompileOptimized(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::ConcurrencyMode, v8::internal::CodeKind)+0x3fa) [0x7f58ec8544ba]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(+0x4470385) [0x7f58ed870385]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(+0x4467bbd) [0x7f58ed867bbd]
    /tmp/d8-linux-debug-v8-component-100914/libv8.so(v8::internal::Runtime_OptimizeTurbofanEager(int, unsigned long*, v8::internal::Isolate*)+0xa0) [0x7f58ed867700]
    [0x7f586f4e84fd]

```

## Other
Please note to include the flags `--allow-natives-syntax --maglev-poly-calls --turbolev` for clusterfuzz classification.

VERSION
Tested on v8 version: 13.9.0 - 13.9.0

REPRODUCTION CASE
1. Download debug v8 from: gs://v8-asan/linux-debug/d8-linux-debug-v8-component-100914.zip
2. Run: `d8 --allow-natives-syntax --maglev-poly-calls --turbolev poc.js`

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

CREDIT INFORMATION
Reporter credit: Zhenghang Xiao (@Kipreyyy) and Nan Wang (@eternalsakura13)
```

## Vulnerability Description

Short PoC for a Maglev/Turbolev polymorphic call optimization bug. Object v0 has six method properties (regular, arrow, async, generator, async computed, generator computed). Iterates keys, calls f0(v0[v1]) and then %OptimizeFunctionOnNextCall(f0) inside the loop. f0 calls v8.next() if truthy and has .next. The mixed function types at the call site cause a polymorphic call that --maglev-poly-calls and --turbolev mis-optimize.

## Capabilities

Triggers a DCHECK or crash in Maglev/Turbolev polymorphic call optimization. No memory read/write.
