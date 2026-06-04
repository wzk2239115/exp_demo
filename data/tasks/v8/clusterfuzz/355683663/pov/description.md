# 355683663: DCHECK failure in V8_ENABLE_SANDBOX_BOOL implies !IsTrustedSpaceObject(target) in assembler-x64-in

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5197955420061696

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  V8_ENABLE_SANDBOX_BOOL implies !IsTrustedSpaceObject(target) in assembler-x64-in
  v8::internal::WritableRelocInfo::set_target_object
  v8::internal::InstructionStream::RelocateFromDesc
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=95295:95296

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5197955420061696

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
