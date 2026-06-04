# 379418918: V8 sandbox violation in Builtins_ContinueToJavaScriptBuiltinWithResult

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6708773523488768

Fuzzer: None
Job Type: linux_asan_d8_sandbox_fuzzing
Platform Id: linux

Crash Type: V8 sandbox violation
Crash Address: 0x7ffe456f2750
Crash State:
  Builtins_ContinueToJavaScriptBuiltinWithResult
  Builtins_InterpreterEntryTrampoline
  Builtins_JSEntryTrampoline
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_sandbox_fuzzing&range=96867:96868

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6708773523488768

Issue manually filed by: saelo

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
