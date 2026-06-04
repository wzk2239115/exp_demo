# 461097476: V8 sandbox violation in Builtins_CallVarargs

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5934762917036032

Fuzzer: None
Job Type: linux_asan_d8_sandbox_testing
Platform Id: linux

Crash Type: V8 sandbox violation
Crash Address: 0x7ffde29ba000
Crash State:
  Builtins_CallVarargs
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_sandbox_testing&range=98073:98074

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5934762917036032

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
