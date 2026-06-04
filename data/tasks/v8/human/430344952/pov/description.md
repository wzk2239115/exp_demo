# 430344952: Debug check failed: IsInBounds(index)

## ClusterFuzz Report

```
```


#
# Fatal error in ../../src/objects/fixed-array-inl.h, line 116
# Debug check failed: IsInBounds(index).
#
#
#
#FailureMessage Object: 0x7ffdb6786b58
==== C stack trace ===============================

    /home/user/v8/v8/out/x64.debug/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x1e) [0x7f64fec3792e]
    /home/user/v8/v8/out/x64.debug/libv8_libplatform.so(+0x4b60d) [0x7f64feba460d]
    /home/user/v8/v8/out/x64.debug/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x205) [0x7f64fec10ce5]
    /home/user/v8/v8/out/x64.debug/libv8_libbase.so(+0x4d69c) [0x7f64fec1069c]
    /home/user/v8/v8/out/x64.debug/libv8_libbase.so(V8_Dcheck(char const*, int, char const*)+0x4d) [0x7f64fec10dbd]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::TaggedArrayBase<v8::internal::WeakFixedArray, v8::internal::WeakFixedArrayShape, v8::internal::HeapObjectLayout>::get(int) const+0x47) [0x7f650670c1b7]
    /home/user/v8/v8/out/x64.debug/libv8.so(void v8::internal::DeclarationScope::AllocateScopeInfos<v8::internal::Isolate>(v8::internal::ParseInfo*, v8::internal::DirectHandle<v8::internal::Script>, v8::internal::Isolate*)+0x2ec) [0x7f650670ab0c]
    /home/user/v8/v8/out/x64.debug/libv8.so(+0x7c0ac9b) [0x7f6506853c9b]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::Compiler::Compile(v8::internal::Isolate*, v8::internal::Handle<v8::internal::SharedFunctionInfo>, v8::internal::Compiler::ClearExceptionFlag, v8::internal::IsCompiledScope*, v8::internal::CreateSourcePositions)+0x9f0) [0x7f65068537a0]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::Compiler::Compile(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::Compiler::ClearExceptionFlag, v8::internal::IsCompiledScope*)+0x4f0) [0x7f6506854730]
    /home/user/v8/v8/out/x64.debug/libv8.so(+0x8e5a176) [0x7f6507aa3176]
    /home/user/v8/v8/out/x64.debug/libv8.so(v8::internal::Runtime_CompileLazy(int, unsigned long*, v8::internal::Isolate*)+0x151) [0x7f6507aa2bb1]
    /home/user/v8/v8/out/x64.debug/libv8.so(+0x6fca53d) [0x7f6505c1353d]
Trace/breakpoint trap (core dumped)
```

#### VERSION

V8 version 13.9.0 (candidate)

#### REPRODUCTION CASE

Build: `python3 tools/dev/gm.py x64.debug`

Run: `./d8 poc.js`

---
Reporter credit: Shaheen Fazim
```

## Vulnerability Description

Short PoC for a scope confusion bug with unicode-escaped eval. outer() has default parameters; inside a block, 'ev\u0061l("var z = 3;")' (eval with escaped identifier) creates a var-scoped binding. inner() closes over obj. The unicode escape may cause the scope analyzer to misidentify the eval call, resulting in an incorrect scope chain.

## Capabilities

Triggers a DCHECK or incorrect scope resolution when unicode-escaped eval creates a var binding. No memory read/write.
