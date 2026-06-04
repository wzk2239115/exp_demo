# 452681948: DCHECK failure in trace->cp_offset() == text_length in regexp-compiler.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4534649447448576

Fuzzer: ochang_js_fuzzer
Job Type: linux32_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  trace->cp_offset() == text_length in regexp-compiler.cc
  V8_Dcheck
  v8::internal::LoopChoiceNode::Emit
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux32_asan_d8_dbg&range=103101:103102

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4534649447448576

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
