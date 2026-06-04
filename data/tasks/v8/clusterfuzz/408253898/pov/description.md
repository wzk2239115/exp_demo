# 408253898: CHECK failure: IsSmi(value) || IsTheHole(value, isolate) in objects-debug.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4693303832281088

Fuzzer: ochang_wasm_fuzzer
Job Type: linux_d8_dbg
Platform Id: linux

Crash Type: CHECK failure
Crash Address: 
Crash State:
  IsSmi(value) || IsTheHole(value, isolate) in objects-debug.cc
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_d8_dbg&range=99028:99029

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4693303832281088

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
