# 323698305: Crash in Builtins_InterpreterEntryTrampoline

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5103780250451968

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: UNKNOWN READ
Crash Address: 0x7edd000031e0
Crash State:
  Builtins_InterpreterEntryTrampoline
  Builtins_JSEntryTrampoline
  Builtins_JSEntry
  
Sanitizer: address (ASAN)

Recommended Security Severity: Medium

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=91868:91869

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5103780250451968

Issue manually filed by: saelo

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
