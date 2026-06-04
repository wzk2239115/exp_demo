# 419081101: DCHECK failure in !Is<ContextCell>(get(index, kRelaxedLoad)) in contexts-inl.h

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5020915985219584

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  !Is<ContextCell>(get(index, kRelaxedLoad)) in contexts-inl.h
  v8::internal::DeclareEvalHelper
  v8::internal::__RT_impl_Runtime_DeclareEvalFunction
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=100384:100385

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5020915985219584

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
