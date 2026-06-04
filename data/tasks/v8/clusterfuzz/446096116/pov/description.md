# 446096116: CHECK failure: ValueRepresentationIs(input->properties().value_representation(), NodeT::kInputT

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4937520047390720

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: CHECK failure
Crash Address: 
Crash State:
  ValueRepresentationIs(input->properties().value_representation(), NodeT::kInputT
  void v8::internal::maglev::MaglevReducer<v8::internal::maglev::MaglevPhiRepresen
  v8::internal::maglev::ChangeInt32ToFloat64* v8::internal::maglev::MaglevReducer<
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=102472:102473

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4937520047390720

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
