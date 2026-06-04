# 352414652: DCHECK failure in !is_hidden() in scopes.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4624238960902144

Fuzzer: mbarbella_js_mutation
Job Type: linux32_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  !is_hidden() in scopes.cc
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux32_d8_dbg&range=95014:95015

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4624238960902144

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
