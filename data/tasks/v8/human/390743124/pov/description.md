# 390743124: SIGSEGV in v8 regexp

## ClusterFuzz Report

```
VULNERABILITY DETAILS
## INTRODUCE
After bisect, it was determined that following commit caused this problem.

- Commit Info
    - Version: 97957
    - link: https://crrev.com/d1e497387a953db6daa37792e73150e397fbf7e3
- Commit Message

```
commit d1e497387a953db6daa37792e73150e397fbf7e3
Author: Samuel Groß <saelo@chromium.org>
Date:   Fri Jan 3 17:27:02 2025 +0000

    [sandbox] Reserve some pages at the start of trusted space
    
    This CL adds a simple mitigation for compressed nullptr dereference bugs
    in trusted space. Since we use zero as empty/missing value for protected
    pointer fields (pointers between objects in trusted space), we can have
    the equivalent of nullptr dereference bugs, but instead of accessing
    address zero, they will access the start of trusted space (because they
    are just offsets from the start of trusted space). With this CL, we now
    simply place a PROT_NONE mapping at the start of trusted space which
    should render most of these bugs unexploitable.
    
    Bug: 387491279
    Change-Id: Ic00e8bfa5f2373bc0d43bb6730a07b183e862c1f
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/6141634
    Reviewed-by: Michael Lippautz <mlippautz@chromium.org>
    Commit-Queue: Samuel Groß <saelo@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#97957}

```

## CRASH LOG
- Debug output

```bash
# CMD: /tmp/d8-linux-debug-v8-component-98188/d8 --allow-natives-syntax poc.js
# OUTPUT ==============================================================
Received signal 11 SEGV_ACCERR 3e8700140000

==== C stack trace ===============================

/tmp/d8-linux-debug-v8-component-98188/libv8_libbase.so(_ZN2v84base5debug10StackTraceC2Ev+0x13)[0x7f71e6a88a13]
/tmp/d8-linux-debug-v8-component-98188/libv8_libbase.so(+0x4b962)[0x7f71e6a88962]
/lib/x86_64-linux-gnu/libc.so.6(+0x42520)[0x7f71e0442520]
/tmp/d8-linux-debug-v8-component-98188/libv8.so(_ZNK2v88internal10HandleBase20IsDereferenceAllowedEv+0x44)[0x7f71e3be5de4]
/tmp/d8-linux-debug-v8-component-98188/libv8.so(_ZNK2v88internal15TranslatedValue11GetRawValueEv+0x41)[0x7f71e3a71ab1]
/tmp/d8-linux-debug-v8-component-98188/libv8.so(_ZN2v88internal15TranslatedValue8GetValueEv+0x17)[0x7f71e3a724e7]
/tmp/d8-linux-debug-v8-component-98188/libv8.so(_ZN2v88internal15TranslatedState23EnsureChildrenAllocatedEiPNS0_15TranslatedFrameEPiPNSt4__Cr5stackIiNS5_5dequeIiNS5_9allocatorIiEEEEEE+0x158)[0x7f71e3a7efc8]
/tmp/d8-linux-debug-v8-component-98188/libv8.so(_ZN2v88internal15TranslatedState31EnsureCapturedObjectAllocatedAtEiPNSt4__Cr5stackIiNS2_5dequeIiNS2_9allocatorIiEEEEEE+0x765)[0x7f71e3a7db45]
/tmp/d8-linux-debug-v8-component-98188/libv8.so(_ZN2v88internal15TranslatedState23EnsureObjectAllocatedAtEPNS0_15TranslatedValueE+0xfe)[0x7f71e3a72cee]
/tmp/d8-linux-debug-v8-component-98188/libv8.so(_ZN2v88internal15TranslatedValue8GetValueEv+0x337)[0x7f71e3a72807]
/tmp/d8-linux-debug-v8-component-98188/libv8.so(_ZN2v88internal11Deoptimizer22MaterializeHeapObjectsEv+0xb0)[0x7f71e3a607a0]
/tmp/d8-linux-debug-v8-component-98188/libv8.so(+0x3cf7084)[0x7f71e48f7084]
/tmp/d8-linux-debug-v8-component-98188/libv8.so(_ZN2v88internal25Runtime_NotifyDeoptimizedEiPmPNS0_7IsolateE+0x89)[0x7f71e48f6989]
[0x7f715f73babd]
[end of stack trace]

```

## Other
Please note to include the flags `--allow-natives-syntax` for clusterfuzz classification.

VERSION
Tested on v8 version: 13.4.0 - 13.4.0

REPRODUCTION CASE
1. Download debug v8 from: gs://v8-asan/linux-debug/d8-linux-debug-v8-component-98188.zip
2. Run: `d8 --allow-natives-syntax poc.js`

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

CREDIT INFORMATION
Reporter credit: Zhenghang Xiao (@Kipreyyy) and Nan Wang (@eternalsakura13)
```

## Vulnerability Description

Short JIT optimization PoC. Installs Array.prototype.__defineSetter__ for index 0, then runs f0 (sets v1.f = v2 where v2 is a regexp) through %PrepareFunctionForOptimization and %OptimizeFunctionOnNextCall. Likely triggers a bug in TurboFan's handling of indexed property setters during type specialization.

## Capabilities

Triggers a DCHECK or crash in JIT optimization when an indexed setter interferes with type-specialized property stores. No memory read/write.
