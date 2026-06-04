# 392180065: V8 sandbox violation in v8::bigint::CopyAndZeroExtend

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6342353035919360

Fuzzer: None
Job Type: linux_asan_d8_sandbox_testing
Platform Id: linux

Crash Type: V8 sandbox violation
Crash Address: 0x79d72ebd34a8
Crash State:
  v8::bigint::CopyAndZeroExtend
  v8::bigint::FFTContainer::Start
  v8::bigint::ProcessorImpl::MultiplyFFT
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_sandbox_testing&range=94746:94747

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6342353035919360

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
