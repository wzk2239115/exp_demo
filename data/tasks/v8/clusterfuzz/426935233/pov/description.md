# 426935233: DCHECK failure in input.operand().IsStackSlot() in maglev-assembler-x64-inl.h

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6269351611006976

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  input.operand().IsStackSlot() in maglev-assembler-x64-inl.h
  v8::internal::maglev::MaglevAssembler::IsRootConstant
  v8::internal::maglev::LogicalNot::GenerateCode
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=99508:99509

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6269351611006976

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
