# 351418008: DCHECK failure in HasBytecodeArray() in shared-function-info-inl.h

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4841099786911744

Fuzzer: ochang_js_fuzzer
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  HasBytecodeArray() in shared-function-info-inl.h
  v8::internal::Tagged<v8::internal::BytecodeArray> v8::internal::SharedFunctionIn
  v8::internal::Deoptimizer::DoComputeUnoptimizedFrame
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=94686:94687

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4841099786911744

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
