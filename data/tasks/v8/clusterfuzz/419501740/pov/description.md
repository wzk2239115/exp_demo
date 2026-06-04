# 419501740: DCHECK failure in IsFastKey(obj, no_gc) in json-stringifier.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4890040781963264

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  IsFastKey(obj, no_gc) in json-stringifier.cc
  v8::internal::FastJsonStringifierObjectKeyResult v8::internal::FastJsonStringifi
  v8::internal::FastJsonStringifierResult v8::internal::FastJsonStringifier<unsign
  
Sanitizer: address (ASAN)

Crash Revision: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&revision=100439

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4890040781963264

Issue manually filed by: saelo

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
