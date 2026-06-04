# 385326426: Stack-buffer-overflow in v8::internal::CreateExponentialRepresentation

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6159700861059072

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: Stack-buffer-overflow WRITE 1
Crash Address: 0x74667c07facb
Crash State:
  v8::internal::CreateExponentialRepresentation
  v8::internal::DoubleToExponentialStringView
  v8::internal::Builtin_Impl_NumberPrototypeToExponential
  
Sanitizer: address (ASAN)

Recommended Security Severity: High

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=97878:97879

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6159700861059072

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
