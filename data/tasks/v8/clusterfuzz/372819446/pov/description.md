# 372819446: DCHECK failure in Tagged<To> v8::internal::Cast(Tagged<From>, const v8::SourceLocation &) [To = v8

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4967479746953216

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  Tagged<To> v8::internal::Cast(Tagged<From>, const v8::SourceLocation &) [To = v8
  v8::internal::RegExpResultsCache_MatchGlobalAtom::TryGet
  v8::internal::__RT_impl_Runtime_RegExpMatchGlobalAtom
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=96270:96271

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4967479746953216

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
