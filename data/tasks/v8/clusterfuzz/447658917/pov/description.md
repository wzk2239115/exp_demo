# 447658917: V8 correctness failure in sources: ee

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5916725849554944

Fuzzer: foozzie_js_fuzzer
Job Type: v8_foozzie_v2
Platform Id: linux

Crash Type: V8 correctness failure
Crash Address: 
Crash State:
  sources: ee
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=v8_foozzie_v2&range=102408:102409

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5916725849554944

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
