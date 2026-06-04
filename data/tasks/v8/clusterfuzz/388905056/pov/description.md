# 388905056: CHECK failure: argument_count_with_receiver <= kMaxUInt16 in js-inlining.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6001104496033792

Fuzzer: ochang_js_fuzzer
Job Type: linux_d8_dbg
Platform Id: linux

Crash Type: CHECK failure
Crash Address: 
Crash State:
  argument_count_with_receiver <= kMaxUInt16 in js-inlining.cc
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_d8_dbg&range=97966:97967

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6001104496033792

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
