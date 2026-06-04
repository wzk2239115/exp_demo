# 420746766: DCHECK failure in IndirectHandle<To> v8::internal::Cast(IndirectHandle<From>, const v8::SourceLoca

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6188188238282752

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  IndirectHandle<To> v8::internal::Cast(IndirectHandle<From>, const v8::SourceLoca
  v8::internal::__RT_impl_Runtime_ThrowConstructorNonCallableError
  v8::internal::Runtime_ThrowConstructorNonCallableError
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=100516:100517

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6188188238282752

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
