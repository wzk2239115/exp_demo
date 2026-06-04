# 368503280: DCHECK failure in CanSubclassHaveInobjectProperties(instance_type) in js-function.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5499730616320000

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  CanSubclassHaveInobjectProperties(instance_type) in js-function.cc
  v8::internal::JSFunction::GetDerivedMap
  v8::internal::Builtin_Impl_AsyncDisposableStackConstructor
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=96211:96212

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5499730616320000

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
