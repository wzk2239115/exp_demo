# 371659887: DCHECK failure in IsCurrentThreadOwner() in js-atomics-synchronization-inl.h

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5537852561489920

Fuzzer: ochang_js_fuzzer
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  IsCurrentThreadOwner() in js-atomics-synchronization-inl.h
  v8::internal::JSAtomicsMutex::Unlock
  v8::internal::JSAtomicsMutex::UnlockAsyncLockedMutex
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=93688:93689

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5537852561489920

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
