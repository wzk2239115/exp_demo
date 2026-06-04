# 348963663: Debug check failed: Handle<To> v8::internal::Cast(Handle<From>, const v8::SourceLocation &) [To = v8::internal::JSReceiver, From = v8::internal::Object].

## ClusterFuzz Report

```
VULNERABILITY DETAILS
## INTRODUCE
After bisect, it was determined that following commit caused this problem.

- Commit Info
    - Version: 94380
    - link: https://crrev.com/7aea96892a74f489f3e8d06a4b6d99ba4f9ea865 
- Commit Message

```
commit 7aea96892a74f489f3e8d06a4b6d99ba4f9ea865
Author: Thibaud Michaud <thibaudm@chromium.org>
Date:   Tue Jun 11 16:54:49 2024 +0200

    [wasm] Do not generate import-specific export wrappers
    
    The signature-specific export wrappers load the target and ref from the
    import dispatch table or from the function data depending on whether the
    target is a re-exported import or an internal function. But the target
    and ref from the function data is more generic and also works for
    re-exported imports.
    
    In fact wrapper tier-up may accidentally replace an export wrapper
    compiled for an import with an export wrapper compiled for an internal
    function, but we did not notice it because the latter still works.
    
    However the other way around does not work. The wrapper compiled for a
    re-exported import uses the dispatch table, which breaks if the target
    is not an import. This happens if we try to enable the generic wrapper
    for re-exported imports.
    
    Remove the import-specific path entirely since the other one is more
    generic, which allows us to use the generic wrapper for re-exported
    imports and will reduce the number of wrappers that we need to compile.
    
    R=jkummerow@chromium.org
    
    Bug: 343772336
    Change-Id: I54446f38971167a5128521027939707ac20d1a86
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/5604484
    Commit-Queue: Thibaud Michaud <thibaudm@chromium.org>
    Reviewed-by: Jakob Kummerow <jkummerow@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#94380}

```

## CRASH LOG
- Debug output

```bash
# CMD: /tmp/d8-linux-debug-v8-component-94592/d8 --allow-natives-syntax --jit-fuzzing poc.js
# OUTPUT ==============================================================


#
# Fatal error in ../../src/objects/object-type.cc, line 82
# Type cast failed in Parameter 1 at ../../src/builtins/builtins-constructor-gen.cc:292
  Expected JSReceiver but found 0xce900000069: [Oddball] in ReadOnlySpace: #undefined

#
#
#
#FailureMessage Object: 0x7ffd759b6170
==== C stack trace ===============================

    /tmp/d8-linux-debug-v8-component-94592/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7f3c5bdd8113]
    /tmp/d8-linux-debug-v8-component-94592/libv8_libplatform.so(+0x190ad) [0x7f3c5bd810ad]
    /tmp/d8-linux-debug-v8-component-94592/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x194) [0x7f3c5bdb9224]
    /tmp/d8-linux-debug-v8-component-94592/libv8.so(v8::internal::CheckObjectType(unsigned long, unsigned long, unsigned long)+0x3a79) [0x7f3c59aed0a9]
    /tmp/d8-linux-debug-v8-component-94592/libv8.so(+0x1ad2888) [0x7f3c580d2888]

```

## Other
Please note to include the flags `--allow-natives-syntax --jit-fuzzing` for clusterfuzz classification.

VERSION
Tested on v8 version: 12.8.0 - 12.8.0

REPRODUCTION CASE
1. Download debug v8 from: gs://v8-asan/linux-debug/d8-linux-debug-v8-component-94592.zip
2. Run: `d8 --allow-natives-syntax --jit-fuzzing poc.js`

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

CREDIT INFORMATION
Reporter credit: Zhenghang Xiao (@Kipreyyy)
```

## Vulnerability Description

Fuzzer-generated output. Tries to load wasm-module-builder.js via d8.file.execute inside try/catch (falls back silently if missing), then instantiates a Wasm module with kSig_v_v (no params) import satisfied by a JS class constructor c1 (extends c0, calls super() in body). Calling the exported function from Wasm while the JIT-compiled wrapper tries to invoke c1 as a constructor triggers DCHECK Cast<JSReceiver> failure because the Wasm-to-JS wrapper does not properly handle constructors.

## Capabilities

Crashes the process with DCHECK failure (Cast<JSReceiver>). No memory read/write.
