# 458914193: Dcheck failure in fixed-array-inl.h

## ClusterFuzz Report

```
## Description

Compilation error occurs with nested classes having a specific structure. The error manifests as an array bounds check violation in fixed-array-inl.h.

The error happens when attempting to access a WeakFixedArray element at index 6, which is out of bounds.

## Reproduction Case

```javascript
class C1 {}

const v1 = {
    n() {
        try { 
            this.n();
        } catch (e) {}

        class C2 {
            constructor() {
                class C3 extends C1 {
                    constructor() {}
                    a;
                    static {};
                    b;
                    static {
                        let x = 0;
                    }
                }
            }
        };

        new C2();
    }
};
let res = v1.n();
```

Tested on debug build **without ASAN** on Linux x64

**Build flags:**
```
is_debug = true
target_cpu = "x64"
v8_enable_backtrace = true
v8_static_library = true  
is_component_build = false
dcheck_always_on = true
v8_enable_disassembler = true
v8_enable_debugging_features=true
v8_dcheck_always_on = true
```

```
./out/debug/d8 poc.js


#
# Fatal error in ../../src/objects/fixed-array-inl.h, line 116
# Debug check failed: IsInBounds(index).
#
#
#
#FailureMessage Object: 0x7ffec77d5720
==== C stack trace ===============================

    ./out/debug/d8(v8::base::debug::StackTrace::StackTrace()+0x13) [0x55980cf3cbb3]
    ./out/debug/d8(+0x2909abd) [0x55980cf3babd]
    ./out/debug/d8(V8_Fatal(char const*, int, char const*, ...)+0x194) [0x55980cf33774]
    ./out/debug/d8(+0x2901025) [0x55980cf33025]
    ./out/debug/d8(void v8::internal::DeclarationScope::AllocateScopeInfos<v8::internal::Isolate>(v8::internal::ParseInfo*, v8::internal::DirectHandle<v8::internal::Script>, v8::internal::Isolate*)+0x715) [0x55980d153d05]
    ./out/debug/d8(+0x2ac01bf) [0x55980d0f21bf]
    ./out/debug/d8(v8::internal::Compiler::Compile(v8::internal::Isolate*, v8::internal::Handle<v8::internal::SharedFunctionInfo>, v8::internal::Compiler::ClearExceptionFlag, v8::internal::IsCompiledScope*, v8::internal::CreateSourcePositions)+0x88f) [0x55980d0f16cf]
    ./out/debug/d8(v8::internal::Compiler::Compile(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::Compiler::ClearExceptionFlag, v8::internal::IsCompiledScope*)+0x259) [0x55980d0f2909]
    ./out/debug/d8(+0x397500d) [0x55980dfa700d]
    ./out/debug/d8(v8::internal::Runtime_CompileLazy(int, unsigned long*, v8::internal::Isolate*)+0x84) [0x55980dfa6b14]
    ./out/debug/d8(+0x62fb67d) [0x55981092d67d]
Trace/breakpoint trap
```

## Introduced

This vulnerability was introduced in: https://chromium.googlesource.com/v8/v8/+/a96a186d4d293bb9cc728eac23709b4e79dc358a (M141 Stable)


## Proposed Fix

Fixing this proved to be quite challenging for me, but for a local fix I discovered that limiting the loop in DeclarationScope::AllocateScopeInfos to infos->length() prevents the crash:

```diff
diff --git a/src/ast/scopes.cc b/src/ast/scopes.cc
index e406e916459..b2ba7218be0 100644
--- a/src/ast/scopes.cc
+++ b/src/ast/scopes.cc
@@ -2803,7 +2803,7 @@ void DeclarationScope::AllocateScopeInfos(ParseInfo* parse_info,
     // reuse. Also look at the compiled function itself, and reuse its function
     // scope info if it exists.
     for (int i = parse_info->literal()->function_literal_id();
-         i <= parse_info->max_info_id(); ++i) {
+         i <= parse_info->max_info_id() && i < infos->length(); ++i) {
       Tagged<MaybeObject> maybe_info = infos->get(i);
       if (maybe_info.IsWeak()) {
         Tagged<Object> info = maybe_info.GetHeapObjectAssumeWeak();
```

Additionally, reverting the changes made in commit a96a186d4d293bb9cc728eac23709b4e79dc358a also prevents the crash.

## CREDIT INFORMATION

Reporter credit: @p1nky4745
```

## Vulnerability Description

PoC triggering a crash via nested class constructor definitions under recursive method invocation. Defines a class C1, then an object with method n() that recurses (catching the stack overflow), and inside the catch block defines and instantiates nested classes C2 and C3 (C3 extends C1 with public fields and static blocks). The combination of recursive context and class field/static block initialization triggers a crash or DCHECK in V8.

## Capabilities

Triggers a crash or DCHECK in V8's class initializer/static block processing under a recursive call stack. No memory read/write or exploit primitives.
