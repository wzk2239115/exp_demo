# 454364323: DCHECK failure in !value->properties().is_conversion() in maglev-interpreter-frame-state.h

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5941768444903424

Fuzzer: ochang_js_fuzzer
Job Type: linux_asan_v8_inspector_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  !value->properties().is_conversion() in maglev-interpreter-frame-state.h
  void v8::internal::maglev::MaglevGraphBuilder::StoreRegister<v8::internal::magle
  v8::internal::maglev::MaglevGraphBuilder::BuildCallWithFeedback
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_v8_inspector_dbg&range=103292:103293

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5941768444903424

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
