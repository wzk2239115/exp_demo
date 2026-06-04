# 440585463: DCHECK failure in Holder<To> v8::internal::TrustedCast(Holder<From>, const v8::SourceLocation &) [

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6597436592029696

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  Holder<To> v8::internal::TrustedCast(Holder<From>, const v8::SourceLocation &) [
  v8::internal::Builtin_Impl_AsyncDisposeFromSyncDispose
  v8::internal::Builtin_AsyncDisposeFromSyncDispose
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=101904:101905

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6597436592029696

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
