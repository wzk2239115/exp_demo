# 328483400: DCHECK failure in interpreter::Bytecodes::WritesAccumulator(iterator_.current_bytecode()) in magle

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6314308744445952

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  interpreter::Bytecodes::WritesAccumulator(iterator_.current_bytecode()) in magle
  v8::internal::maglev::MaglevGraphBuilder::GetDeoptFrameForLazyDeoptHelper
  void v8::internal::maglev::MaglevGraphBuilder::AttachLazyDeoptInfo<v8::internal:
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=89062:89063

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6314308744445952

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
