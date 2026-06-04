# 449341185: SEGV_ACCERR in V8

## ClusterFuzz Report

```
## Bisect
- Commit: 05f2468756c718612b00908e10885fa2599fef34

```
Commit: 05f2468756c718612b00908e10885fa2599fef34
Commit Message:
commit 05f2468756c718612b00908e10885fa2599fef34
Author: pthier <pthier@chromium.org>
Date:   Fri Aug 29 11:51:13 2025 +0200

    [regexp] Assemble from BC: Implement Visit for special bytecodes
    
    Implement Visit methods for all RegExp bytecodes in the special bytecode
    list (bytecodes that don't have a 1:1 mapping to a method in the
    RegExpMacroAssembler).
    
    Bug: 437003349
    Change-Id: I5959b1f06ad5a3b297e3189ab9d65b798d31e791
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/6889011
    Reviewed-by: Jakob Linke <jgruber@chromium.org>
    Commit-Queue: Patrick Thier <pthier@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#102124}
```

## Reproduction

1. Download: `gs://v8-asan/linux-debug/d8-linux-debug-v8-component-102927.zip`
2. Run: `d8 --allow-natives-syntax --regexp-assemble-from-bytecode --stress-compaction poc.js`

## Crash Output
```
----------------------------------------
--------------------------------------------------------------------------------
Received signal 11 SEGV_ACCERR 39b900841c50

==== C stack trace ===============================

/home/sakura/v8/v8/out/fuzzbuild/d8(+0xc0b976)[0x55bdb06eb976]
/lib/x86_64-linux-gnu/libc.so.6(+0x42520)[0x7f9d8c642520]
/home/sakura/v8/v8/out/fuzzbuild/d8(+0x2644cc8)[0x55bdb2124cc8]
/home/sakura/v8/v8/out/fuzzbuild/d8(+0x2644b41)[0x55bdb2124b41]
/home/sakura/v8/v8/out/fuzzbuild/d8(+0x26436a0)[0x55bdb21236a0]
/home/sakura/v8/v8/out/fuzzbuild/d8(+0x264321d)[0x55bdb212321d]
/home/sakura/v8/v8/out/fuzzbuild/d8(+0x2619b7b)[0x55bdb20f9b7b]
/home/sakura/v8/v8/out/fuzzbuild/d8(+0x261afaa)[0x55bdb20fafaa]
/home/sakura/v8/v8/out/fuzzbuild/d8(+0x2610645)[0x55bdb20f0645]
/home/sakura/v8/v8/out/fuzzbuild/d8(+0x2611be4)[0x55bdb20f1be4]
/home/sakura/v8/v8/out/fuzzbuild/d8(+0x261140b)[0x55bdb20f140b]
/home/sakura/v8/v8/out/fuzzbuild/d8(+0x284fffb)[0x55bdb232fffb]
/home/sakura/v8/v8/out/fuzzbuild/d8(+0x284f661)[0x55bdb232f661]
/home/sakura/v8/v8/out/fuzzbuild/d8(+0x5ec28bd)[0x55bdb59a28bd]
[end of stack trace]
Segmentation fault



================================================================================
```
```

## Vulnerability Description

Fuzzer-generated PoC using %SetAllocationTimeout, %PrepareFunctionForOptimization, %OptimizeFunctionOnNextCall, and a Unicode regex with named capture groups inside a loop. Triggers a crash or DCHECK in V8's compiler or regex engine via GC-triggered allocation failure.

## Capabilities

Triggers a crash or DCHECK in V8 via GC allocation timeout combined with regex compilation. No memory read/write or exploit primitives.
