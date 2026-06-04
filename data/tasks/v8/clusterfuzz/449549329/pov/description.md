# 449549329: DCHECK failure in exception_handler_liveness->RegisterIsLive(i) implies liveness->RegisterIsLive(i

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6066073942032384

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  exception_handler_liveness->RegisterIsLive(i) implies liveness->RegisterIsLive(i
  v8::internal::maglev::MaglevGraphBuilder::GetDeoptFrameForLazyDeoptHelper
  void v8::internal::maglev::MaglevReducer<v8::internal::maglev::MaglevGraphBuilde
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=102579:102580

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6066073942032384

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
