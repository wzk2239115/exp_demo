# 410842388: CHECK failure: !input->op()->HasProperty(Operator::kNoThrow) in verifier.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5024172879052800

Fuzzer: ochang_js_fuzzer
Job Type: linux32_asan_d8_dbg
Platform Id: linux

Crash Type: CHECK failure
Crash Address: 
Crash State:
  !input->op()->HasProperty(Operator::kNoThrow) in verifier.cc
  v8::internal::compiler::Verifier::Visitor::Check
  v8::internal::compiler::Verifier::Run
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux32_asan_d8_dbg&range=99789:99790

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5024172879052800

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
