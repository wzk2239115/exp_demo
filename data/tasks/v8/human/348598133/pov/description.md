# 348598133: DCHECK failure in size() > index in small-vector.h

## ClusterFuzz Report

```
VULNERABILITY DETAILS
## INTRODUCE
After bisect, it was determined that following commit caused this problem.

- Commit Info
    - Version: 92983
    - link: https://crrev.com/0c2b15100d997a8f1b74fcc448da319c75f2e045 
- Commit Message

```
commit 0c2b15100d997a8f1b74fcc448da319c75f2e045
Author: Adam Klein <adamk@chromium.org>
Date:   Thu Mar 21 13:36:59 2024 -0700

    [wasm][jspi][d8] Add ability to test runtime-enabling of JSPI
    
    This adds an `enableJSPI` function to the d8 test runner which
    allows simulating the way the JSPI Origin Trial in Chrome enables JSPI.
    
    Then it makes a copy of the JSPI mjsunit test to use this approach,
    rather than using a commandline flag.
    
    Bug: v8:14576
    Change-Id: I637972dcf7de288d42b1325355b08c6b1b86d9ef
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/5385244
    Reviewed-by: Francis McCabe <fgm@chromium.org>
    Commit-Queue: Adam Klein <adamk@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#92983}

```

## CRASH LOG
- Debug output

```bash
# CMD: /tmp/d8-linux-debug-v8-component-94592/d8 --allow-natives-syntax poc.js
# OUTPUT ==============================================================


#
# Fatal error in ../../src/base/small-vector.h, line 140
# Debug check failed: size() > index (7 vs. 7).
#
#
#
#FailureMessage Object: 0x7fff325f4130
==== C stack trace ===============================

    /tmp/d8-linux-debug-v8-component-94592/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7f6eb1b19113]
    /tmp/d8-linux-debug-v8-component-94592/libv8_libplatform.so(+0x190ad) [0x7f6eb1ac20ad]
    /tmp/d8-linux-debug-v8-component-94592/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x194) [0x7f6eb1afa224]
    /tmp/d8-linux-debug-v8-component-94592/libv8_libbase.so(+0x2bc45) [0x7f6eb1af9c45]
    /tmp/d8-linux-debug-v8-component-94592/libv8.so(+0x4b5e304) [0x7f6eb0f5e304]
    /tmp/d8-linux-debug-v8-component-94592/libv8.so(v8::internal::compiler::CompileWasmToJSWrapper(v8::internal::Isolate*, v8::internal::wasm::WasmModule const*, v8::internal::Signature<v8::internal::wasm::ValueType> const*, v8::internal::wasm::ImportCallKind, int, v8::internal::wasm::Suspend)+0x33c) [0x7f6eb0f5816c]
    /tmp/d8-linux-debug-v8-component-94592/libv8.so(v8::internal::WasmJSFunction::New(v8::internal::Isolate*, v8::internal::Signature<v8::internal::wasm::ValueType> const*, v8::internal::Handle<v8::internal::JSReceiver>, v8::internal::wasm::Suspend)+0x9a2) [0x7f6eb06158d2]
    /tmp/d8-linux-debug-v8-component-94592/libv8.so(+0x41d579a) [0x7f6eb05d579a]
    /tmp/d8-linux-debug-v8-component-94592/libv8.so(v8::internal::FunctionCallbackArguments::CallOrConstruct(v8::internal::Tagged<v8::internal::FunctionTemplateInfo>, bool)+0x191) [0x7f6eaeb8c841]
    /tmp/d8-linux-debug-v8-component-94592/libv8.so(+0x278ae6c) [0x7f6eaeb8ae6c]
    /tmp/d8-linux-debug-v8-component-94592/libv8.so(+0x2788b84) [0x7f6eaeb88b84]
    /tmp/d8-linux-debug-v8-component-94592/libv8.so(v8::internal::Builtin_HandleApiConstruct(int, unsigned long*, v8::internal::Isolate*)+0x7d) [0x7f6eaeb881ad]
    /tmp/d8-linux-debug-v8-component-94592/libv8.so(+0x1eac77d) [0x7f6eae2ac77d]

```

## Other
Please note to include the flags `--allow-natives-syntax` for clusterfuzz classification.

VERSION
Tested on v8 version: 12.5.0 - 12.8.0

REPRODUCTION CASE
1. Download debug v8 from: gs://v8-asan/linux-debug/d8-linux-debug-v8-component-94592.zip
2. Run: `d8 --allow-natives-syntax poc.js`

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

CREDIT INFORMATION
Reporter credit: Zhenghang Xiao (@Kipreyyy)
```

## Vulnerability Description

Fuzzer-generated output. Enables JSPI via d8.test.enableJSPI() and d8.test.installConditionalFeatures(), then inside an IIFE creates a WebAssembly.Function with {parameters:[], results:['i32']} wrapping a Promise-returning arrow function with {suspending:'first'} option. Triggers DCHECK failure in small-vector.h (size() > index) during JSPI suspending function setup.

## Capabilities

Crashes the process with DCHECK failure. No memory read/write.
