# 435225527: DCHECK failure in use_count_ > 0 in maglev-ir.h

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6350755669671936

Fuzzer: ochang_js_fuzzer
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  use_count_ > 0 in maglev-ir.h
  v8::internal::maglev::ValueNode::remove_use
  void v8::internal::maglev::DeoptInfoVisitor<v8::internal::maglev::EagerDeoptInfo
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=101661:101662

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6350755669671936

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
