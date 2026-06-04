# 346411877: DCHECK failure in IsClass(*old_field_type) implies old_representation.IsHeapObject() in map-update

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6237159332708352

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  IsClass(*old_field_type) implies old_representation.IsHeapObject() in map-update
  v8::internal::MapUpdater::GeneralizeField
  v8::internal::MapUpdater::GeneralizeField
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=94106:94107

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6237159332708352

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
