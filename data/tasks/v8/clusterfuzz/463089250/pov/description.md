# 463089250: DCHECK failure in Holder<To> v8::internal::TrustedCast(Holder<From>, SourceLocation) [To = v8::int

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6242414175911936

Fuzzer: ochang_js_fuzzer
Job Type: linux_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  Holder<To> v8::internal::TrustedCast(Holder<From>, SourceLocation) [To = v8::int
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_d8_dbg&range=103851:103852

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6242414175911936

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
