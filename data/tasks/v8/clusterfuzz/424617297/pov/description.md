# 424617297: DCHECK failure in IsTyped(node) in node-properties.h

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5843070234853376

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  IsTyped(node) in node-properties.h
  v8::internal::compiler::RedundancyElimination::ReduceSpeculativeNumberComparison
  v8::internal::compiler::GraphReducer::Reduce
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=100800:100801

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5843070234853376

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
