# 369652654: CHECK failure: has_exception() in isolate-inl.h

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4753976603901952

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: CHECK failure
Crash Address: 
Crash State:
  has_exception() in isolate-inl.h
  v8::internal::JSAsyncDisposableStack::NextDisposeAsyncIteration
  v8::internal::Builtin_Impl_AsyncDisposableStackPrototypeDisposeAsync
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=96287:96288

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4753976603901952

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
