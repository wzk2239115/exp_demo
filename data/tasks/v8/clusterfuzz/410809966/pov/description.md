# 410809966: CHECK failure: index < node->op()->ControlInputCount()

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5236870195642368

Fuzzer: ochang_js_fuzzer
Job Type: linux_tsan_concurrent_inlining_d8
Platform Id: linux

Crash Type: CHECK failure
Crash Address: 
Crash State:
  index < node->op()->ControlInputCount()
  v8::internal::compiler::CFGBuilder::FindPredecessorBlock
  v8::internal::compiler::CFGBuilder::ConnectThrow
  
Sanitizer: thread (TSAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_tsan_concurrent_inlining_d8&range=99789:99790

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5236870195642368

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
