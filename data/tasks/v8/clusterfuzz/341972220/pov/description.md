# 341972220: DCHECK failure in IsNull(value) || IsJSProxy(value) || IsWasmObject(value) || (IsJSObject(value) &

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5166551975002112

Fuzzer: ochang_js_fuzzer
Job Type: linux_asan_d8_v8_arm_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  IsNull(value) || IsJSProxy(value) || IsWasmObject(value) || (IsJSObject(value) &
  V8_Dcheck
  v8::internal::Map::set_prototype
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_v8_arm_dbg&range=93996:93997

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5166551975002112

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
