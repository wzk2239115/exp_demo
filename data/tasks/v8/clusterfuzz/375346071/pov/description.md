# 375346071: DCHECK failure in Tagged<To> v8::internal::Cast(Tagged<From>, const v8::SourceLocation &) [To = v8

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5587461900009472

Fuzzer: ochang_js_fuzzer
Job Type: linux32_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  Tagged<To> v8::internal::Cast(Tagged<From>, const v8::SourceLocation &) [To = v8
  V8_Dcheck
  v8::internal::__RT_impl_Runtime_TierUpWasmToJSWrapper
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux32_asan_d8_dbg&range=96808:96809

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5587461900009472

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
