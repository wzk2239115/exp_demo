# 343069827: Trap in v8::internal::__RT_impl_Runtime_Abort

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5117022101766144

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: Trap
Crash Address: 0x000000000000
Crash State:
  v8::internal::__RT_impl_Runtime_Abort
  v8::internal::Runtime_Abort
  Builtins_CEntry_Return1_ArgvOnStack_NoBuiltinExit
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=94041:94042

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5117022101766144

Issue manually filed by: saelo

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
