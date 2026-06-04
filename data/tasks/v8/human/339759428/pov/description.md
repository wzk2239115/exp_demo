# 339759428: Debug check failed: code.SafeEquals(topmost_) implies safe_to_deopt_.

## ClusterFuzz Report

```
Version: bac95ef1
OS: Linux
Architecture: x64

What steps will reproduce the problem?
1. v8/out/fuzzbuild/d8 --expose-gc --omit-quit --allow-natives-syntax --fuzzing --jit-fuzzing --future --harmony --js-staging ./deoptimizer.cc_L359_DCHECK_fail.js

The bug, detected by bac95ef1 and reproduced with some probability at this point based on 49272427, the latest commit, occurs in src/deoptimizer/deoptimizer.cc, line 359, with Debug check failed: program counter replacement fails due to code.SafeEquals(topmost_) implies safe_to_deopt_.

What is the expected output?

No crash.

What do you see instead?

// CRASH INFO
// ==========
// INSTANCE TAG: bac95ef1
// TERMSIG: 6
// STDERR:
// [COV] edge counters initialized. Shared memory: shm_id_3450327_14 with 1309323 edges
// 
// 
// #
// # Fatal error in ../../src/deoptimizer/deoptimizer.cc, line 359
// # Debug check failed: code.SafeEquals(topmost_) implies safe_to_deopt_.
// #
// #
// #
// #FailureMessage Object: 0x7f921b0c0060
// ==== C stack trace ===============================
// 
//     ../v8/out/fuzzbuild/d8(___interceptor_backtrace+0x46) [0x5f5a036428a6]
//     ../v8/out/fuzzbuild/d8(+0x1f61b02) [0x5f5a0393fb02]
//     ../v8/out/fuzzbuild/d8(+0x1f5f18f) [0x5f5a0393d18f]
//     ../v8/out/fuzzbuild/d8(+0x1f49477) [0x5f5a03927477]
//     ../v8/out/fuzzbuild/d8(+0x1f4879f) [0x5f5a0392679f]
//     ../v8/out/fuzzbuild/d8(+0x271c380) [0x5f5a040fa380]
//     ../v8/out/fuzzbuild/d8(+0x271b5d2) [0x5f5a040f95d2]
//     ../v8/out/fuzzbuild/d8(+0x271e14a) [0x5f5a040fc14a]
//     ../v8/out/fuzzbuild/d8(+0x2867c83) [0x5f5a04245c83]
//     ../v8/out/fuzzbuild/d8(+0x28b5bea) [0x5f5a04293bea]
//     ../v8/out/fuzzbuild/d8(+0x423e239) [0x5f5a05c1c239]
//     ../v8/out/fuzzbuild/d8(+0x423d969) [0x5f5a05c1b969]
//     ../v8/out/fuzzbuild/d8(+0x7f82008) [0x5f5a09960008]
// Received signal 6
// STDOUT:
// 
// FUZZER ARGS: .build/x86_64-unknown-linux-gnu/debug/FuzzilliCli --profile=v8 ../v8/out/fuzzbuild/d8 --jobs=24 --engine=multi --logLevel=verbose --timeout=1200 --storagePath=../v8_fuzzing_results --resume --exportStatistics --statisticsExportInterval=5 --diagnostics --tag=3ea85f9c
// TARGET ARGS: ../v8/out/fuzzbuild/d8 --expose-gc --omit-quit --allow-natives-syntax --fuzzing --jit-fuzzing --future --harmony --js-staging
// CONTRIBUTORS: TypedArrayGenerator, IntegerGenerator, ExplorationMutator, ArrayGenerator
// EXECUTION TIME: 171ms

Please use labels and text to provide additional information.

The bug is suspected to be caused by the same object being processed and the top-level optimisation code object, but there are no recent changes in the commit log for this file that could be related to this. I'm currently in the process of looking at the GCs involved in getting to DCHECK_IMPLIES.
```

## Vulnerability Description

Fuzzer-generated JS. Defines a constructor F0 containing an async inner function f2. f2 accesses a3.constructor, constructs a new instance passing 'this' twice plus f2, then awaits 'this' and calls a method on the result. A regex literal with complex syntax is also present. When called via 'new F0()', the async function deoptimizes in a state where DCHECK 'code.SafeEquals(topmost_) implies safe_to_deopt_' fails in deoptimizer.cc line 359.

## Capabilities

Crashes the process with SIGABRT (DCHECK failure in deoptimizer). No memory read/write primitive.
