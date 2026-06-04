# 451663011: DCHECK failure in base::IsInRange(cp_offset, kMinCPOffset, kMaxCPOffset) in regexp-macro-assembler

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4901493207400448

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  base::IsInRange(cp_offset, kMinCPOffset, kMaxCPOffset) in regexp-macro-assembler
  v8::internal::NativeRegExpMacroAssembler::LoadCurrentCharacterImpl
  v8::internal::AssertionNode::Emit
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=101929:101930

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4901493207400448

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
