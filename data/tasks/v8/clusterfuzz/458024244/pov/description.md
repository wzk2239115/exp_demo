# 458024244: Use-after-poison in v8::internal::maglev::MaglevFrameTranslationBuilder::BuildDeoptFrameSingleValue

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4537964524666880

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: Use-after-poison READ 8
Crash Address: 0x7d75f2ff1190
Crash State:
  v8::internal::maglev::MaglevFrameTranslationBuilder::BuildDeoptFrameSingleValue
  v8::internal::maglev::MaglevFrameTranslationBuilder::BuildDeoptFrameValues
  v8::internal::maglev::MaglevFrameTranslationBuilder::RecursiveBuildDeoptFrame
  
Sanitizer: address (ASAN)

Recommended Security Severity: High

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=102885:102886

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4537964524666880

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
