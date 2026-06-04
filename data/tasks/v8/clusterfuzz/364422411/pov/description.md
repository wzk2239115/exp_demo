# 364422411: DCHECK failure in source_map->map()->native_context() == *isolate->native_context() in ic.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6394334077190144

Fuzzer: mbarbella_js_mutation
Job Type: linux_asan_d8_v8_arm_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  source_map->map()->native_context() == *isolate->native_context() in ic.cc
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_v8_arm_dbg&range=95850:95851

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6394334077190144

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
