# 329693878: DCHECK failure in (var) != nullptr in scopes.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5177826856075264

Fuzzer: mbarbella_js_mutation
Job Type: linux32_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  (var) != nullptr in scopes.cc
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux32_d8_dbg&range=89088:89089

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5177826856075264

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
