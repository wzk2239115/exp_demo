# 339043696: CHECK failure: (location_) != nullptr in maybe-handles.h

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5165972617887744

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: CHECK failure
Crash Address: 
Crash State:
  (location_) != nullptr in maybe-handles.h
  v8::internal::PerformPromiseThen
  v8::internal::JSAtomicsMutex::LockOrEnqueuePromise
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=93688:93689

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5165972617887744

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
