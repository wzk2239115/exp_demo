# 418478214: Fatal error in Bytecode mismatch at offset 26 in interpreter.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6548838286295040

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: Fatal error
Crash Address: 
Crash State:
  Bytecode mismatch at offset 26 in interpreter.cc
  void v8::internal::interpreter::InterpreterCompilationJob::CheckAndPrintBytecode
  v8::internal::CompilationJob::Status v8::internal::interpreter::InterpreterCompi
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=100220:100221

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6548838286295040

Issue manually filed by: saelo

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
