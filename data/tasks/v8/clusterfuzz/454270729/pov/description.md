# 454270729: DCHECK failure in NodeTypeIs(GetType(string), NodeType::kString) in maglev-graph-builder.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5130843991244800

Fuzzer: ochang_js_fuzzer
Job Type: linux_asan_d8_undef_dbl_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  NodeTypeIs(GetType(string), NodeType::kString) in maglev-graph-builder.cc
  v8::internal::maglev::MaglevGraphBuilder::BuildLoadStringLength
  v8::internal::maglev::MaglevGraphBuilder::TryReduceStringPrototypeSlice
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_undef_dbl_dbg&range=103257:103258

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5130843991244800

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
