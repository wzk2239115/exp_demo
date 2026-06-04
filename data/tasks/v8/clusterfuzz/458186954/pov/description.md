# 458186954: Stack-buffer-overflow in uloc_toUnicodeLocaleType_77

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4526757210161152

Fuzzer: None
Job Type: linux_asan_d8_v8_arm64_dbg
Platform Id: linux

Crash Type: Stack-buffer-overflow READ {*}
Crash Address: 0x7b3edc85213d
Crash State:
  uloc_toUnicodeLocaleType_77
  v8::internal::Intl::ResolveLocale
  v8::internal::JSDateTimeFormat::CreateDateTimeFormat
  
Sanitizer: address (ASAN)

Recommended Security Severity: Medium

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_v8_arm64_dbg&range=102921:102922

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4526757210161152

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
