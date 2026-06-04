# 361124378: DCHECK failure in can_throw == CanThrow::kNo implies lazy_deopt_on_throw == LazyDeoptOnThrow::kNo 

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5118229047345152

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  can_throw == CanThrow::kNo implies lazy_deopt_on_throw == LazyDeoptOnThrow::kNo 
  v8::internal::compiler::turboshaft::TSCallDescriptor::Create
  std::__Cr::enable_if<v8::internal::compiler::turboshaft::BuiltinCallDescriptor::
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=95044:95045

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5118229047345152

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
