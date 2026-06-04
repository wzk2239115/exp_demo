# 350779648: Heap-use-after-free in v8::internal::Heap::GarbageCollectionEpilogue

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6236059144749056

Fuzzer: None
Job Type: linux_asan_d8_v8_arm64_dbg
Platform Id: linux

Crash Type: Heap-use-after-free READ {*}
Crash Address: 0x50c0000098c0
Crash State:
  v8::internal::Heap::GarbageCollectionEpilogue
  v8::internal::Heap::CollectGarbage
  void heap::base::Stack::SetMarkerAndCallbackImpl<v8::internal::Heap::CollectGarb
  
Sanitizer: address (ASAN)

Recommended Security Severity: High

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_v8_arm64_dbg&range=90417:90418

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6236059144749056

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
