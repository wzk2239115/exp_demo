# 396192870: DCHECK failure in arg_repr == ValueRepresentation::kTagged in maglev-graph-builder.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5688393430138880

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  arg_repr == ValueRepresentation::kTagged in maglev-graph-builder.cc
  v8::internal::maglev::MaglevGraphBuilder::DoTryReduceMathRound
  v8::internal::maglev::MaglevGraphBuilder::TryReduceBuiltin
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=98604:98605

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5688393430138880

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
