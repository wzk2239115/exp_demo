# 349864879: Type representation error: node BranchIfSmi (input @0 = Int32SubtractWithOverflow) type Int32 is not

## ClusterFuzz Report

```
# Steps to reproduce the problem
1. download d8: wget "https://www.googleapis.com/download/storage/v1/b/v8-asan/o/linux-debug%2Fd8-asan-linux-debug-v8-component-94695.zip?generation=1719508565330862&alt=media"
2. run ./d8  --expose-gc --omit-quit --allow-natives-syntax --fuzzing --jit-fuzzing --future --harmony --js-staging poc.js

# Problem Description
Type representation error: node BranchIfSmi (input @0 = Int32SubtractWithOverflow) type Int32 is not Tagged

# Summary
Type representation error: node BranchIfSmi (input @0 = Int32SubtractWithOverflow) type Int32 is not

# Custom Questions
#### Type of crash: 
tab

#### Crash state: 
```
#
# Fatal error in ../../src/maglev/maglev-ir.cc, line 601
# Type representation error: node BranchIfSmi (input @0 = Int32SubtractWithOverflow) type Int32 is not Tagged
#
#
#
#FailureMessage Object: 0x7f43fdea5460
==== C stack trace ===============================

    ./d8(__interceptor_backtrace+0x46) [0x557933f422d6]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7f4401296903]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8_libplatform.so(+0x3172a) [0x7f44011e772a]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x2a0) [0x7f4401257310]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8.so(v8::internal::maglev::CheckValueInputIs(v8::internal::maglev::NodeBase const*, int, v8::internal::maglev::ValueRepresentation, v8::internal::maglev::MaglevGraphLabeller*)+0x4b3) [0x7f4408647263]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8.so(v8::internal::maglev::GraphProcessor<v8::internal::maglev::MaglevGraphVerifier, false>::ProcessNodeBase(v8::internal::maglev::NodeBase*, v8::internal::maglev::ProcessingState const&)+0x3d1f) [0x7f44080d822f]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8.so(v8::internal::maglev::GraphProcessor<v8::internal::maglev::MaglevGraphVerifier, false>::ProcessGraph(v8::internal::maglev::Graph*)+0x535) [0x7f4407ff33e5]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8.so(v8::internal::maglev::MaglevCompiler::Compile(v8::internal::LocalIsolate*, v8::internal::maglev::MaglevCompilationInfo*)+0x1989) [0x7f4407fef379]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8.so(v8::internal::maglev::MaglevCompilationJob::ExecuteJobImpl(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x10b) [0x7f4408212ceb]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8.so(v8::internal::OptimizedCompilationJob::ExecuteJob(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x1a5) [0x7f440580f625]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8.so(+0x45bb449) [0x7f440586c449]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8.so(+0x45879a9) [0x7f44058389a9]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8.so(v8::internal::Compiler::CompileOptimized(v8::internal::Isolate*, v8::internal::Handle<v8::internal::JSFunction>, v8::internal::ConcurrencyMode, v8::internal::CodeKind)+0x24b) [0x7f440583dd0b]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8.so(+0x6701a6b) [0x7f44079b2a6b]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8.so(v8::internal::Runtime_CompileOptimized(int, unsigned long*, v8::internal::Isolate*)+0x131) [0x7f44079b1c51]
    /root/target/fjsoutput/v8d/d8-asan-linux-debug-v8-component-94695/libv8.so(+0x37003fd) [0x7f44049b13fd]
Received signal 6
Aborted
```

#### Reporter credit: 
chainsec.ai

# Additional Data
Category: Security \
Chrome Channel: Not sure \
Regression: N/A
```

## Vulnerability Description

Short Maglev optimization PoC. Defines f0 which calls charCodeAt with a function reference argument (producing NaN), computes NaN - NaN (v5=0), then passes both NaN and an array into f6 which calls a7.reduce() in a try/catch. After warm-up via recursive f0() calls, uses %OptimizeMaglevOnNextCall(f0) and calls f0() again to trigger Maglev compilation with the confused numeric type.

## Capabilities

Likely crashes with a DCHECK or assertion in Maglev's type inference or arithmetic optimization. No memory read/write. No controlled output.
