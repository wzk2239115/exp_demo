# 352402498: DCHECK failure in source_map->GetInObjectProperties() >= result_map->GetInObjectProperties() in ic

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5897343175950336

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  source_map->GetInObjectProperties() >= result_map->GetInObjectProperties() in ic
  v8::internal::__RT_impl_Runtime_CloneObjectIC_Miss
  v8::internal::Runtime_CloneObjectIC_Miss
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=94979:94980

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5897343175950336

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
