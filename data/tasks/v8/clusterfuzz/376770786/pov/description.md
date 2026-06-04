# 376770786: DCHECK failure in i.valid() in graph.h

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4615149621018624

Fuzzer: ochang_js_fuzzer
Job Type: linux_asan_d8_v8_arm64_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  i.valid() in graph.h
  v8::internal::compiler::turboshaft::Graph::Get
  v8::internal::compiler::turboshaft::MachineOptimizationReducer<v8::internal::com
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_v8_arm64_dbg&range=96957:96958

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4615149621018624

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
