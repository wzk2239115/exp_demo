# 458608439: DCHECK failure in checked_value() == nullptr || (!IsConstantNode(checked_value()->opcode()) && IsC

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5491739322155008

Fuzzer: None
Job Type: linux_asan_d8_v8_arm64_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  checked_value() == nullptr || (!IsConstantNode(checked_value()->opcode()) && IsC
  v8::internal::maglev::NodeInfo::AlternativeNodes::set_checked_value
  v8::internal::maglev::MaglevGraphBuilder::SetKnownValue
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_v8_arm64_dbg&range=103501:103502

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5491739322155008

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
