# 433817201: DCHECK failure in !IsEmptyNodeType(GetType(index)) in maglev-graph-builder.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6331477306310656

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  !IsEmptyNodeType(GetType(index)) in maglev-graph-builder.cc
  v8::internal::maglev::MaglevGraphBuilder::BuildLoadFixedDoubleArrayElement
  v8::internal::maglev::MaglevGraphBuilder::TryReduceArrayPrototypeAt
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=101555:101556

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6331477306310656

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
