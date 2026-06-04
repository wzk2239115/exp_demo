# 346835902: Debug check failed: Object::FitsRepresentation(*object, representation). in v8

## ClusterFuzz Report

```
VULNERABILITY DETAILS
## INTRODUCE
After bisect, it was determined that following commit caused this problem.

- Commit Info
    - Version: 94239
    - link: https://crrev.com/d8bc0da831599b038cabab63b45b63cc28db2687 
- Commit Message

```
commit d8bc0da831599b038cabab63b45b63cc28db2687
Author: Olivier Flückiger <olivf@chromium.org>
Date:   Tue Jun 4 15:06:24 2024 +0200

    [ic] Ensure clone IC respects field type
    
    We can only use a clone IC if a field type change in the target map
    cannot produce a field type that is invalid with respect to entries that
    are created by the clone IC.
    
    Drive-By: Also exclude the int->double case that was accidentally
              allowed.
    
    Fixed: 344638604
    Fixed: 344669837
    Change-Id: Id92f57cf0eadb5d155e268ca2315b3a74644febc
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/5595017
    Commit-Queue: Olivier Flückiger <olivf@chromium.org>
    Reviewed-by: Igor Sheludko <ishell@chromium.org>
    Commit-Queue: Igor Sheludko <ishell@chromium.org>
    Auto-Submit: Olivier Flückiger <olivf@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#94239}

```

## CRASH LOG
- Debug output

```bash
# CMD: /tmp/d8-linux-debug-v8-component-94416/d8 --jit-fuzzing poc.js
# OUTPUT ==============================================================


#
# Fatal error in ../../src/objects/objects.cc, line 255
# Debug check failed: Object::FitsRepresentation(*object, representation).
#
#
#
#FailureMessage Object: 0x7fffb82bd4d0
==== C stack trace ===============================

    /tmp/d8-linux-debug-v8-component-94416/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7f8cc1bf4f03]
    /tmp/d8-linux-debug-v8-component-94416/libv8_libplatform.so(+0x18e3d) [0x7f8cc70d2e3d]
    /tmp/d8-linux-debug-v8-component-94416/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x194) [0x7f8cc1bd60e4]
    /tmp/d8-linux-debug-v8-component-94416/libv8_libbase.so(+0x2bb05) [0x7f8cc1bd5b05]
    /tmp/d8-linux-debug-v8-component-94416/libv8.so(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>> v8::internal::Object::WrapForRead<(v8::internal::AllocationType)0, v8::internal::Isolate>(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Representation)+0x24c) [0x7f8cc50149fc]
    /tmp/d8-linux-debug-v8-component-94416/libv8.so(v8::internal::JSObject::FastPropertyAt(v8::internal::Isolate*, v8::internal::Handle<v8::internal::JSObject>, v8::internal::Representation, v8::internal::FieldIndex)+0xa0) [0x7f8cc4e903b0]
    /tmp/d8-linux-debug-v8-component-94416/libv8.so(v8::internal::LookupIterator::FetchValue(v8::internal::AllocationPolicy) const+0x717) [0x7f8cc4fc4747]
    /tmp/d8-linux-debug-v8-component-94416/libv8.so(v8::internal::Object::GetProperty(v8::internal::LookupIterator*, bool)+0x8f) [0x7f8cc507742f]
    /tmp/d8-linux-debug-v8-component-94416/libv8.so(v8::internal::JSReceiver::GetOwnPropertyDescriptor(v8::internal::LookupIterator*, v8::internal::PropertyDescriptor*)+0xae8) [0x7f8cc4e85118]
    /tmp/d8-linux-debug-v8-component-94416/libv8.so(v8::internal::JSReceiver::OrdinaryDefineOwnProperty(v8::internal::Isolate*, v8::internal::Handle<v8::internal::JSObject>, v8::internal::PropertyKey const&, v8::internal::PropertyDescriptor*, v8::Maybe<v8::internal::ShouldThrow>)+0x146) [0x7f8cc4e843c6]
    /tmp/d8-linux-debug-v8-component-94416/libv8.so(v8::internal::JSReceiver::OrdinaryDefineOwnProperty(v8::internal::Isolate*, v8::internal::Handle<v8::internal::JSObject>, v8::internal::Handle<v8::internal::Object>, v8::internal::PropertyDescriptor*, v8::Maybe<v8::internal::ShouldThrow>)+0x1a5) [0x7f8cc4e84195]
    /tmp/d8-linux-debug-v8-component-94416/libv8.so(v8::internal::JSReceiver::DefineOwnProperty(v8::internal::Isolate*, v8::internal::Handle<v8::internal::JSReceiver>, v8::internal::Handle<v8::internal::Object>, v8::internal::PropertyDescriptor*, v8::Maybe<v8::internal::ShouldThrow>)+0x560) [0x7f8cc4e83210]
    /tmp/d8-linux-debug-v8-component-94416/libv8.so(v8::internal::JSReceiver::DefineProperty(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Object>, v8::internal::Handle<v8::internal::Object>, v8::internal::Handle<v8::internal::Object>)+0x16a) [0x7f8cc4e829fa]
    /tmp/d8-linux-debug-v8-component-94416/libv8.so(+0x277bc8d) [0x7f8cc437bc8d]
    /tmp/d8-linux-debug-v8-component-94416/libv8.so(v8::internal::Builtin_ObjectDefineProperty(int, unsigned long*, v8::internal::Isolate*)+0x7d) [0x7f8cc437b94d]
    /tmp/d8-linux-debug-v8-component-94416/libv8.so(+0x1dee3bd) [0x7f8cc39ee3bd]

```

## Other
Please note to include the flags `--jit-fuzzing` for clusterfuzz classification.

VERSION
Tested on v8 version: 12.7.0 - 12.8.0

REPRODUCTION CASE
1. Download debug v8 from: gs://v8-asan/linux-debug/d8-linux-debug-v8-component-94416.zip
2. Run: `d8 --jit-fuzzing poc.js`

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

CREDIT INFORMATION
Reporter credit: Zhenghang Xiao (@Kipreyyy)
```

## Vulnerability Description

Fuzzer-generated PoC. Uses helper functions (getp/get) to select object property names by modular index with magic numbers. Defines two spread-copying functions f4/f5, creates objects v10 and v11, runs them through Object.defineProperty calls that change field values from integer to Math.PI (float) and then to URIError (non-numeric). With --jit-fuzzing the JIT compiles f4/f5 assuming Smi/double field representation, which no longer matches when URIError is stored, triggering DCHECK 'Object::FitsRepresentation'.

## Capabilities

Crashes the process with DCHECK failure (Object::FitsRepresentation). No memory read/write.
