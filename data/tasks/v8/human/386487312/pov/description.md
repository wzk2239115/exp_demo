# 386487312: Debug check failed: position() + n <= buffer_.length() in v8

## ClusterFuzz Report

```
VULNERABILITY DETAILS
## INTRODUCE
After bisect, it was determined that following commit caused this problem.

- Commit Info
    - Version: 97879
    - link: https://crrev.com/02c8d9c11009c3b9b510fdc599e7e2115fc88b00
- Commit Message

```
commit 02c8d9c11009c3b9b510fdc599e7e2115fc88b00
Author: pthier <pthier@chromium.org>
Date:   Thu Dec 19 13:00:10 2024 +0100

    [conversions] Return std::string_view from *ToCString methods
    
    Previously, DoubleToCString, IntToCString, DoubleToFixedCString,
    DoubleToExponentialCString, DoubleToPrecisionCString and
    DoubleToRadixCString returned a 0-terminated C-String.
    However most users of these methods copy the C-String again (e.g. into
    a V8 Heap object), thus requiring another strlen() call to retrieve the
    length, that is already known within these methods.
    
    Therefore this CL changes the following:
    - *ToCString methods return a std::string_view (not 0-terminated)
      instead of a 0-terminated C-String.
    - The caller provides the required buffer to store the result.
      Previously the methods created a malloced buffer and transferred
      ownership to the caller. By requiring the caller to provide the
      buffer (1) ownership is clear and (2) the buffer can be stack
      allocated.
    - Rename *ToCString to *ToStringView to reflect the changed semantics.
    
    Bug: 380044242, 377438310
    Change-Id: If7b44d0dc8ff8551d4aaeac01f5d20e1528a9c3f
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/6105411
    Commit-Queue: Patrick Thier <pthier@chromium.org>
    Reviewed-by: Leszek Swirski <leszeks@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#97879}
```

## CRASH LOG
- Debug output

```bash
# CMD: /tmp/d8-linux-debug-v8-component-97925/d8 poc.js
# OUTPUT ==============================================================


#
# Fatal error in ../../src/numbers/conversions.cc, line 96
# Debug check failed: position() + n <= buffer_.length() (108 vs. 107).
#
#
#
#FailureMessage Object: 0x7ffccf570d00
==== C stack trace ===============================

    /tmp/d8-linux-debug-v8-component-97925/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7f04ba7f53e3]
    /tmp/d8-linux-debug-v8-component-97925/libv8_libplatform.so(+0x1ae6d) [0x7f04ba79de6d]
    /tmp/d8-linux-debug-v8-component-97925/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x194) [0x7f04ba7d65c4]
    /tmp/d8-linux-debug-v8-component-97925/libv8_libbase.so(+0x2bfd5) [0x7f04ba7d5fd5]
    /tmp/d8-linux-debug-v8-component-97925/libv8.so(v8::internal::SimpleStringBuilder::AddSubstring(char const*, int)+0x200) [0x7f04bdd41530]
    /tmp/d8-linux-debug-v8-component-97925/libv8.so(v8::internal::DoubleToPrecisionStringView(double, int, v8::base::Vector<char>)+0x502) [0x7f04bdd42912]
    /tmp/d8-linux-debug-v8-component-97925/libv8.so(+0x2c1cd4f) [0x7f04bd41cd4f]
    /tmp/d8-linux-debug-v8-component-97925/libv8.so(v8::internal::Builtin_NumberPrototypeToPrecision(int, unsigned long*, v8::internal::Isolate*)+0x7d) [0x7f04bd41c2dd]
    /tmp/d8-linux-debug-v8-component-97925/libv8.so(+0x218647d) [0x7f04bc98647d]
```

VERSION
Tested on v8 version: 13.3.0 - 13.3.0

REPRODUCTION CASE
1. Download debug v8 from: gs://v8-asan/linux-debug/d8-linux-debug-v8-component-97925.zip
2. Run: d8  poc.js

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

CREDIT INFORMATION
Reporter credit: Zhenghang Xiao (@Kipreyyy) and Nan Wang (@eternalsakura13)
```

## Vulnerability Description

One-line PoC: '(-.0000012345).toPrecision(100)'. Calls Number.prototype.toPrecision with precision=100 on a small negative float. Triggers a buffer overflow or assertion failure in V8's double-to-string conversion (dtoa/toPrecision) when the precision exceeds a safe internal limit.

## Capabilities

Crashes the process (likely SIGSEGV or CHECK failure) in Number.toPrecision's string formatting path. No memory read/write.
