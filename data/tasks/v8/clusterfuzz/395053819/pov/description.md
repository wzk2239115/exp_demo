# 395053819: DCHECK failure in index > 0 in string-hasher-inl.h

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5809197002194944

Fuzzer: decoder_langfuzz
Job Type: linux_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  index > 0 in string-hasher-inl.h
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_d8_dbg&range=98518:98519

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5809197002194944

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
