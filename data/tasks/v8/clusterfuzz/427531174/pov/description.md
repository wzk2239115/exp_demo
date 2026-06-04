# 427531174: DCHECK failure in !IsEmptyNodeType(GetType(other)) in maglev-graph-builder.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4650914585444352

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  !IsEmptyNodeType(GetType(other)) in maglev-graph-builder.cc
  bool v8::internal::maglev::MaglevGraphBuilder::TryReduceCompareEqualAgainstConst
  v8::internal::maglev::ReduceResult v8::internal::maglev::MaglevGraphBuilder::Vis
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=100999:101000

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4650914585444352

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
