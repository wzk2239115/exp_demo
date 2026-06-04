# 423960608: DCHECK failure in iterator_.current_bytecode() == interpreter::Bytecode::kGetNamedProperty || iter

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5277013443018752

Fuzzer: ochang_js_fuzzer
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  iterator_.current_bytecode() == interpreter::Bytecode::kGetNamedProperty || iter
  v8::internal::maglev::MaglevGraphBuilder::FindContinuationForPolymorphicProperty
  v8::internal::maglev::MaybeReduceResult v8::internal::maglev::MaglevGraphBuilder
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=100752:100753

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5277013443018752

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
