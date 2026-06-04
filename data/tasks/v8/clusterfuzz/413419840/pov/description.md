# 413419840: DCHECK failure in CanElideWriteBarrier(object, value) in maglev-graph-builder.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4567079206191104

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  CanElideWriteBarrier(object, value) in maglev-graph-builder.cc
  v8::internal::maglev::MaglevGraphBuilder::BuildStoreTaggedFieldNoWriteBarrier
  v8::internal::maglev::MaglevGraphBuilder::TryBuildStoreField
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=99835:99836

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4567079206191104

Issue manually filed by: saelo

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
