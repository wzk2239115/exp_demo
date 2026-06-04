# 377829476: Debug check failed: string->IsFlat(). in v8

## ClusterFuzz Report

```
VULNERABILITY DETAILS
## INTRODUCE
After bisect, it was determined that following commit caused this problem.
                                                                                                                                                                                                                 - Commit Info                                                                                                                                                                                                        - Version: 96923
    - link: https://crrev.com/c07d8f220405f6c0cdf53c748e7c07fd7916f1d5
- Commit Message

```
commit c07d8f220405f6c0cdf53c748e7c07fd7916f1d5
Author: Jakob Linke <jgruber@chromium.org>
Date:   Thu Oct 31 13:07:57 2024 +0100

    [regexp] Implement the global Atom path
                                                                                                                                                                                                                     ExecInternal2 can now handle all regexp types (irregexp, atom,
    experimental). I also widen the existing replace/match global paths in
    this CL.

    Bug: 370804671, 372285209
    Change-Id: I4952ad969ed153651a356b97ee7f3c57c6930ffd
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/5979830
    Commit-Queue: Jakob Linke <jgruber@chromium.org>
    Commit-Queue: Patrick Thier <pthier@chromium.org>
    Reviewed-by: Patrick Thier <pthier@chromium.org>
    Auto-Submit: Jakob Linke <jgruber@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#96923}

```

## CRASH LOG
- Debug output

```bash
# CMD: /tmp/d8-linux-debug-v8-component-97038/d8 --allow-natives-syntax --jit-fuzzing --regexp-interpret-all poc.js                                                                                              # OUTPUT ==============================================================


#
# Fatal error in ../../src/objects/string-inl.h, line 326
# Debug check failed: string->IsFlat().
#
#
#
#FailureMessage Object: 0x7ffd09e0bd40
==== C stack trace ===============================

    /tmp/d8-linux-debug-v8-component-97038/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7f45e55dea73]                                                                                         /tmp/d8-linux-debug-v8-component-97038/libv8_libplatform.so(+0x1a05d) [0x7f45e558805d]
    /tmp/d8-linux-debug-v8-component-97038/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x194) [0x7f45e55c0274]                                                                                     /tmp/d8-linux-debug-v8-component-97038/libv8_libbase.so(+0x2bc85) [0x7f45e55bfc85]
    /tmp/d8-linux-debug-v8-component-97038/libv8.so(v8::internal::IrregexpInterpreter::Match(v8::internal::Isolate*, v8::internal::Tagged<v8::internal::IrRegExpData>, v8::internal::Tagged<v8::internal::String>, int*, int, int, v8::internal::RegExp::CallOrigin)+0x111) [0x7f45e33f1361]
    /tmp/d8-linux-debug-v8-component-97038/libv8.so(v8::internal::IrregexpInterpreter::MatchForCallFromJs(unsigned long, int, unsigned long, unsigned long, int*, int, v8::internal::RegExp::CallOrigin, v8::internal::Isolate*, unsigned long)+0x126) [0x7f45e3408c56]
    [0x7f455fba84e3]

```

## Other
Please note to include the flags `--allow-natives-syntax --jit-fuzzing --regexp-interpret-all` for clusterfuzz classification.                                                                                   
VERSION
Tested on v8 version: 13.2.0 - 13.2.0

REPRODUCTION CASE
1. Download debug v8 from: gs://v8-asan/linux-debug/d8-linux-debug-v8-component-97038.zip
2. Run: `d8 --allow-natives-syntax --jit-fuzzing --regexp-interpret-all poc.js`

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

CREDIT INFORMATION
Reporter credit: Zhenghang Xiao (@Kipreyyy)
```

## Vulnerability Description

Short TurboFan JIT optimization PoC. Defines two string-returning functions (f0 returns 14 'a's, f1 returns 14 'b's), f2 concatenates them, f3 concatenates its argument with f2(). After warm-up, %OptimizeFunctionOnNextCall(f3) triggers TurboFan compilation. The resulting string is then used in two regexp replace operations with a Unicode character class. Likely triggers a bug in JIT string concatenation or string representation optimization.

## Capabilities

Triggers a DCHECK or crash in TurboFan's string representation handling. No memory read/write.
