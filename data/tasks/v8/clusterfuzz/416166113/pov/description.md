# 416166113: DCHECK failure in AllowGarbageCollection::IsAllowed() in heap.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4582502903513088

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  AllowGarbageCollection::IsAllowed() in heap.cc
  v8::internal::Heap::CollectGarbage
  v8::internal::Heap::AllocateExternalBackingStore
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=100099:100100

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4582502903513088

Issue manually filed by: saelo

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
