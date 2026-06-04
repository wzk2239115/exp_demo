# 366643711: DCHECK failure in count > 0 in waiter-queue-node.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4590870976200704

Fuzzer: ochang_js_fuzzer
Job Type: linux_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  count > 0 in waiter-queue-node.cc
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_d8_dbg&range=93688:93689

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4590870976200704

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
