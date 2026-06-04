# 416302802: Crash in v8::internal::Builtin_Impl_Uint8ArrayPrototypeSetFromHex

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5362316627345408

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: UNKNOWN WRITE
Crash Address: 0x7f9affffffff
Crash State:
  v8::internal::Builtin_Impl_Uint8ArrayPrototypeSetFromHex
  v8::internal::Builtin_Uint8ArrayPrototypeSetFromHex
  Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit
  
Sanitizer: address (ASAN)

Recommended Security Severity: High

Crash Revision: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&revision=100121

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5362316627345408

Issue manually filed by: saelo

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
