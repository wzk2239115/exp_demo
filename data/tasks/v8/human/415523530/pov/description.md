# 415523530: Debug check failed: CanElideWriteBarrier(object, value). in v8

## ClusterFuzz Report

```
VULNERABILITY DETAILS
## INTRODUCE
After bisect, it was determined that following commit caused this problem.

- Commit Info
    - Version: 99836
    - link: https://crrev.com/6953465cfa8d77c67f6cab42cfe3bf5204028a22
- Commit Message

```
commit 6953465cfa8d77c67f6cab42cfe3bf5204028a22
Author: Marja Hölttä <marja@chromium.org>
Date:   Tue Apr 22 08:44:55 2025 +0200

    [maglev] Type system refactoring: Fix write barriers in dead code
    
    Fixed: 412125812
    Change-Id: I7d5886dd3c00762ee650a60a3d6607e90929fd18
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/6478150
    Commit-Queue: Marja Hölttä <marja@chromium.org>
    Reviewed-by: Leszek Swirski <leszeks@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#99836}

```

## CRASH LOG
- Debug output

```bash
# CMD: /tmp/d8-linux-debug-v8-component-100039/d8 --allow-natives-syntax --future --turbolev poc.js
# OUTPUT ==============================================================


#
# Fatal error in ../../src/maglev/maglev-graph-builder.cc, line 5513
# Debug check failed: CanElideWriteBarrier(object, value).
#
#
#
#FailureMessage Object: 0x7ffc5f68faf0
==== C stack trace ===============================

    /tmp/d8-linux-debug-v8-component-100039/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7f29c1c163d3]
    /tmp/d8-linux-debug-v8-component-100039/libv8_libplatform.so(+0x1ba1d) [0x7f29c1bbfa1d]
    /tmp/d8-linux-debug-v8-component-100039/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x194) [0x7f29c1bf9504]
    /tmp/d8-linux-debug-v8-component-100039/libv8_libbase.so(+0x2bec5) [0x7f29c1bf8ec5]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::maglev::MaglevGraphBuilder::BuildStoreTaggedFieldNoWriteBarrier(v8::internal::maglev::ValueNode*, v8::internal::maglev::ValueNode*, int, v8::internal::maglev::StoreTaggedMode)+0x175) [0x7f29bfccb675]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::maglev::MaglevGraphBuilder::TrySpecializeStoreContextSlot(v8::internal::maglev::ValueNode*, int, v8::internal::maglev::ValueNode*, v8::internal::maglev::Node**)+0x3a6) [0x7f29bfccb046]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::maglev::MaglevGraphBuilder::StoreAndCacheContextSlot(v8::internal::maglev::ValueNode*, int, v8::internal::maglev::ValueNode*, v8::internal::ContextMode)+0x12e) [0x7f29bfccba5e]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::maglev::MaglevGraphBuilder::VisitSingleBytecode()+0x7fc) [0x7f29bfbbab7c]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::maglev::MaglevGraphBuilder::BuildLoopForPeeling()+0x18e) [0x7f29bfd2234e]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::maglev::MaglevGraphBuilder::PeelLoop()+0x12c) [0x7f29bfd2203c]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::maglev::MaglevGraphBuilder::BuildBody()+0x270) [0x7f29bfbb6490]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::maglev::MaglevGraphBuilder::Build()+0x37d) [0x7f29bfbb258d]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::compiler::turboshaft::MaglevGraphBuildingPhase::Run(v8::internal::compiler::turboshaft::PipelineData*, v8::internal::Zone*, v8::internal::compiler::Linkage*)+0x1cb) [0x7f29c139f36b]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(auto v8::internal::compiler::turboshaft::Pipeline::Run<v8::internal::compiler::turboshaft::MaglevGraphBuildingPhase, v8::internal::compiler::Linkage*&>(v8::internal::compiler::Linkage*&)+0xf7) [0x7f29c0b96057]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::compiler::turboshaft::Pipeline::CreateGraphWithMaglev(v8::internal::compiler::Linkage*)+0xbb) [0x7f29c0b82c0b]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::compiler::PipelineCompilationJob::ExecuteJobImpl(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x1d7) [0x7f29c0b829d7]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::OptimizedCompilationJob::ExecuteJob(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x92) [0x7f29be7e3ed2]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(+0x31fb07d) [0x7f29be7fb07d]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::Compiler::CompileOptimized(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::ConcurrencyMode, v8::internal::CodeKind)+0x3d7) [0x7f29be7feac7]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(+0x42d46a5) [0x7f29bf8d46a5]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(+0x42cbe33) [0x7f29bf8cbe33]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(v8::internal::Runtime_OptimizeTurbofanEager(int, unsigned long*, v8::internal::Isolate*)+0xa0) [0x7f29bf8cb9a0]
    /tmp/d8-linux-debug-v8-component-100039/libv8.so(+0x23f243d) [0x7f29bd9f243d]

```

## Other
Please note to include the flags `--allow-natives-syntax --future --turbolev` for clusterfuzz classification.

VERSION
Tested on v8 version: 13.7.0 - 13.8.0

REPRODUCTION CASE
1. Download debug v8 from: gs://v8-asan/linux-debug/d8-linux-debug-v8-component-100039.zip
2. Run: `d8 --allow-natives-syntax --future --turbolev poc.js`

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

CREDIT INFORMATION
Reporter credit: Zhenghang Xiao (@Kipreyyy) and Nan Wang (@eternalsakura13)
```

## Vulnerability Description

Short PoC for a --turbolev optimization bug. Defines f0 which calls forEach on an array of 9 TypedArray constructors using loop counter v3 as the callback. %PrepareFunctionForOptimization and %OptimizeFunctionOnNextCall trigger Turbolev compilation. Turbolev may mishandle the case where v3 (a number) is used as a forEach callback.

## Capabilities

Triggers a DCHECK or crash in the Turbolev compiler or runtime when a number is incorrectly treated as a callable in forEach. No memory read/write.
