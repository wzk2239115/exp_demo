# 400052777: Signal SIGTRAP in v8

## ClusterFuzz Report

```
VULNERABILITY DETAILS
## INTRODUCE
After bisect, it was determined that following commit caused this problem.

- Commit Info
    - Version: 97378
    - link: https://crrev.com/b8d3f7d0cf6461b59ec41379e49534eb7bebc210
- Commit Message

```
commit b8d3f7d0cf6461b59ec41379e49534eb7bebc210
Author: Marja Hölttä <marja@chromium.org>
Date:   Mon Nov 25 15:13:39 2024 +0100

    [turbofan] Reduce the amount of map loads during elements kind transitions
    
    Adopt the "TransitionElementsKindOrCheckMap" concept from Maglev. It
    allows us to do only one map load instead of one map load per transition.
    
    Change-Id: I1d9ea645fd5359bf72cf70c79e714676c73c6233
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/6035112
    Commit-Queue: Marja Hölttä <marja@chromium.org>
    Reviewed-by: Darius Mercadier <dmercadier@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#97378}

```

## CRASH LOG
- Debug output

```bash
# CMD: /tmp/d8-linux-debug-v8-component-99019/d8 --allow-natives-syntax poc.js
# OUTPUT ==============================================================


#
# Fatal error in ../../src/objects/object-type.cc, line 82
# Type cast failed in CAST(elements) at ../../src/builtins/builtins-array-gen.cc:1353
  Expected FixedDoubleArray but found 0x32ae00288a31: [FixedArray]
 - map: 0x32ae00000565 <Map(FIXED_ARRAY_TYPE)>
 - length: 1
           0: 0x32ae00288a3d <HeapNumber 0.1>

#
#
#
#FailureMessage Object: 0x7ffeb2544cf0
==== C stack trace ===============================

    /tmp/d8-linux-debug-v8-component-99019/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7f22bca27373]
    /tmp/d8-linux-debug-v8-component-99019/libv8_libplatform.so(+0x1b1bd) [0x7f22bc9d21bd]
    /tmp/d8-linux-debug-v8-component-99019/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x194) [0x7f22bca0a8a4]
    /tmp/d8-linux-debug-v8-component-99019/libv8.so(v8::internal::CheckObjectType(unsigned long, unsigned long, unsigned long)+0x3be1) [0x7f22ba40c441]
    /tmp/d8-linux-debug-v8-component-99019/libv8.so(+0x20410b5) [0x7f22b88410b5]

```

## Other
Please note to include the flags `--allow-natives-syntax` for clusterfuzz classification.

VERSION
Tested on v8 version: 13.3.0 - 13.5.0

REPRODUCTION CASE
1. Download debug v8 from: gs://v8-asan/linux-debug/d8-linux-debug-v8-component-99019.zip
2. Run: `d8 --allow-natives-syntax poc.js`

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

CREDIT INFORMATION
Reporter credit: Zhenghang Xiao (@Kipreyyy) and Nan Wang (@eternalsakura13)
```

## Vulnerability Description

Short crash PoC. Defines f0 that reads array elements v4=v3[0] and v5=v2[0], calls Array.prototype.indexOf.call(v3). After warm-up with mixed tagged/double arrays, %OptimizeFunctionOnNextCall(f0) compiles assuming tagged elements, but the final call passes double arrays (v1[0]=0.1), causing a type confusion or DCHECK.

## Capabilities

Triggers a DCHECK or crash in TurboFan's array element type specialization. No memory read/write.
