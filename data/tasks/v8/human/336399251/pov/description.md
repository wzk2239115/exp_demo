# 336399251: Check failed: !v8::internal::v8_flags.enable_slow_asserts.value() || (IsWasmExportedFunction(*this))

## ClusterFuzz Report

```
# Steps to reproduce the problem
1. Download debug v8 from: gs://v8-asan/linux-debug/d8-linux-debug-v8-component-93481.zip
2. Run: `d8 --allow-natives-syntax --fuzzing poc.js`

# Problem Description
## INTRODUCE
After bisect, it was determined that following commit caused this problem.

- Commit Info
    - Version: 93460
    - link: https://crrev.com/63a58875aea33190ef982d254d10f5700463f49a
- Commit Message

```
commit 63a58875aea33190ef982d254d10f5700463f49a
Author: Thibaud Michaud <thibaudm@chromium.org>
Date:   Thu Apr 18 15:56:35 2024 +0200

    [wasm][jspi] Introduce WA.promising and WA.Suspending

    In the revised API, WebAssembly.promising and WebAssembly.Suspending
    replace WebAssembly.Function(..., {promising: 'first'}) and
    WebAssembly.Function(..., {suspending: 'first'}) respectively.

    WebAssembly.Suspending is a constructor. It returns a new object type
    which is not callable but can be imported into module.

    WebAssembly.promising returns a regular WasmExportedFunction.

    R=ahaas@chromium.org

    Bug: v8:14722
    Change-Id: I572b8d4bf0597a68dd31ac39241066156c6185ef
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/5454695
    Reviewed-by: Andreas Haas <ahaas@chromium.org>
    Commit-Queue: Thibaud Michaud <thibaudm@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#93460}

```

## CRASH LOG
- Debug output

```bash
# CMD: /tmp/d8-linux-debug-v8-component-93481/d8 --allow-natives-syntax --fuzzing poc.js
# OUTPUT ==============================================================

#
# Fatal error in ../../src/wasm/wasm-objects-inl.h, line 356
# Check failed: !v8::internal::v8_flags.enable_slow_asserts.value() || (IsWasmExportedFunction(*this)).
#
#
#
#FailureMessage Object: 0x7ffd9193e960
==== C stack trace ===============================

    /tmp/d8-linux-debug-v8-component-93481/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7feb959f4d93]
    /tmp/d8-linux-debug-v8-component-93481/libv8_libplatform.so(+0x193cd) [0x7feb9599d3cd]
    /tmp/d8-linux-debug-v8-component-93481/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x17d) [0x7feb959d5f8d]
    /tmp/d8-linux-debug-v8-component-93481/libv8.so(+0x40e96b5) [0x7feb99ae96b5]
    /tmp/d8-linux-debug-v8-component-93481/libv8.so(+0x19a23de) [0x7feb973a23de]
Received signal 6

```

## Other
Please note to include the flags `--allow-natives-syntax --fuzzing` for clusterfuzz classification.

VERSION
Tested on v8 version: 12.6.0 - 12.6.0

# Summary
Check failed: !v8::internal::v8_flags.enable_slow_asserts.value() || (IsWasmExportedFunction(*this))

# Custom Questions
#### Type of crash: 
tab

#### Reporter credit: 
Zhenghang Xiao (@Kipreyyy)

# Additional Data
Category: Security \
Chrome Channel: Not sure \
Regression: N/A
```

## Vulnerability Description

Three-line PoC: enables JSPI via d8.test.enableJSPI() and d8.test.installConditionalFeatures(), then calls WebAssembly.promising(Int32Array), passing a TypedArray constructor instead of a WebAssembly.Function. The JSPI implementation does not validate the argument type, crashing immediately.

## Capabilities

Crashes the process. No memory read/write. The only attacker-controlled input is the choice of non-Function object passed to promising().
