# 374627491: DCHECK failure in Handle<To> v8::internal::Cast(Handle<From>, const v8::SourceLocation &) [To = v8

## ClusterFuzz Report

```
# Steps to reproduce the problem
1. download d8-asan-linux-debug-v8-component-96641
2. unzip that
3. run d8 ./poc.js

# Problem Description
```
#
# Fatal error in ../../src/objects/objects.cc, line 353
# Debug check failed: Handle<To> v8::internal::Cast(Handle<From>, const v8::SourceLocation &) [To = v8::internal::JSReceiver, From = v8::internal::Object].
#
#
#
#FailureMessage Object: 0x7bc62e2f9c60
==== C stack trace ===============================

    ./google-cloud-sdk/d8-asan-linux-debug-v8-component-96641/d8(__interceptor_backtrace+0x46) [0x55cbd91b17a6]
    /root/google-cloud-sdk/d8-asan-linux-debug-v8-component-96641/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7fc6317c8573]
    /root/google-cloud-sdk/d8-asan-linux-debug-v8-component-96641/libv8_libplatform.so(+0x3687a) [0x7fc63171c87a]
    /root/google-cloud-sdk/d8-asan-linux-debug-v8-component-96641/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x2a0) [0x7fc631792c80]
    /root/google-cloud-sdk/d8-asan-linux-debug-v8-component-96641/libv8_libbase.so(+0x56d3f) [0x7fc631791d3f]
    /root/google-cloud-sdk/d8-asan-linux-debug-v8-component-96641/libv8.so(v8::internal::Handle<v8::internal::JSReceiver> v8::internal::Cast<v8::internal::JSReceiver, v8::internal::Object>(v8::internal::Handle<v8::internal::Object>, v8::SourceLocation const&)+0x1b2) [0x7fc635ba53f2]
    /root/google-cloud-sdk/d8-asan-linux-debug-v8-component-96641/libv8.so(v8::internal::Object::ConvertToNumeric(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Object>)+0x1ba) [0x7fc637bd9dba]
    /root/google-cloud-sdk/d8-asan-linux-debug-v8-component-96641/libv8.so(v8::internal::Object::ToNumeric(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Object>)+0x3d1) [0x7fc635aacda1]
    /root/google-cloud-sdk/d8-asan-linux-debug-v8-component-96641/libv8.so(+0x6acfa0d) [0x7fc6382b3a0d]
    /root/google-cloud-sdk/d8-asan-linux-debug-v8-component-96641/libv8.so(v8::internal::Runtime_ToNumeric(int, unsigned long*, v8::internal::Isolate*)+0x1da) [0x7fc6382b315a]
    /root/google-cloud-sdk/d8-asan-linux-debug-v8-component-96641/libv8.so(+0x3a58afd) [0x7fc63523cafd]
AddressSanitizer:DEADLYSIGNAL
=================================================================
==1914346==ERROR: AddressSanitizer: TRAP on unknown address 0x000000000000 (pc 0x7fc6317c3690 bp 0x7ffe27e76810 sp 0x7ffe27e76810 T0)
SCARINESS: 10 (signal)
    #0 0x7fc6317c3690 in v8::base::OS::Abort() src/base/platform/platform-posix.cc:730:7
    #1 0x7fc631792c9b in V8_Fatal(char const*, int, char const*, ...) src/base/logging.cc:215:3
    #2 0x7fc631791d3e in v8::base::(anonymous namespace)::DefaultDcheckHandler(char const*, int, char const*) src/base/logging.cc:59:3
    #3 0x7fc635ba53f1 in v8::internal::Handle<v8::internal::JSReceiver> v8::internal::Cast<v8::internal::JSReceiver, v8::internal::Object>(v8::internal::Handle<v8::internal::Object>, v8::SourceLocation const&) src/handles/handles-inl.h:50:3
    #4 0x7fc637bd9db9 in v8::internal::Object::ConvertToNumeric(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Object>) src/objects/objects.cc:350:5
    #5 0x7fc635aacda0 in v8::internal::Object::ToNumeric(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Object>) src/objects/objects-inl.h:816:10
    #6 0x7fc6382b3a0c in v8::internal::__RT_impl_Runtime_ToNumeric(v8::internal::Arguments<(v8::internal::ArgumentsType)0>, v8::internal::Isolate*) src/runtime/runtime-object.cc:1231:3
    #7 0x7fc6382b3159 in v8::internal::Runtime_ToNumeric(int, unsigned long*, v8::internal::Isolate*) src/runtime/runtime-object.cc:1227:1
    #8 0x7fc63523cafc in Builtins_CEntry_Return1_ArgvOnStack_NoBuiltinExit setup-isolate-deserialize.cc
    #9 0x7fc635454701 in Builtins_NonNumberToNumeric setup-isolate-deserialize.cc
    #10 0x7fc6358490d4 in Builtins_ShiftRightLogicalHandler setup-isolate-deserialize.cc
    #11 0x7fc634e5754e in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #12 0x7fc634e58162 in Builtins_InterpreterPushArgsThenFastConstructFunction setup-isolate-deserialize.cc
    #13 0x7fc63587725c in Builtins_ConstructHandler setup-isolate-deserialize.cc
    #14 0x7fc634e5754e in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #15 0x7fc634e4e5db in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #16 0x7fc634e4e31e in Builtins_JSEntry setup-isolate-deserialize.cc
    #17 0x7fc63659536a in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/simulator.h:191:12
    #18 0x7fc63659903c in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::Handle<v8::internal::JSFunction>, v8::internal::Handle<v8::internal::Object>, v8::internal::Handle<v8::internal::Object>) src/execution/execution.cc:517:10
    #19 0x7fc635a5b263 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2140:7
    #20 0x55cbd927e335 in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) 
```

# Summary
Type Confusion in ConvertToNumeric

# Custom Questions
#### Type of crash: 
tab

# Additional Data
Category: Security \
Chrome Channel: Not sure \
Regression: N/A
```

## Vulnerability Description

Short PoC that accesses testRunner.toLocaleString (a d8 test runner property), then defines class C4 extending C3 whose constructor uses 'v1 >>>= this' (unsigned right shift assignment with 'this' as operand) inside a switch statement, and has 'case this:' as a case label. Using 'this' before super() in a derived class constructor triggers a TDZ (temporal dead zone) violation or type confusion in the parser/compiler.

## Capabilities

Triggers a crash or DCHECK in the parser or constructor-call path when 'this' is used before super() in a derived class. No memory read/write.
