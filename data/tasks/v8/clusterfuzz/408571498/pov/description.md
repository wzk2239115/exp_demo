# 408571498: DCHECK failure in IsString(instance_type) in instance-type-inl.h

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6455727891611648

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  IsString(instance_type) in instance-type-inl.h
  v8::internal::compiler::MapRef::IsTwoByteStringMap
  v8::internal::maglev::MaglevGraphBuilder::BuildNewConsStringMap
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=99629:99630

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6455727891611648

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
