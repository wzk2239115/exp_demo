# 394327270: V8 correctness failure in sources: 18

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5812304713023488

Fuzzer: foozzie_js_fuzzer
Job Type: v8_foozzie_v2
Platform Id: linux

Crash Type: V8 correctness failure
Crash Address: 
Crash State:
  sources: 18
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=v8_foozzie_v2&range=98337:98338

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5812304713023488

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
