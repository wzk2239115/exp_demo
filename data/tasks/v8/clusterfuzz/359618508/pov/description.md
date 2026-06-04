# 359618508: CHECK failure: IsRegExpDataWrapper(*field_value) in translated-state.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5813945325518848

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: CHECK failure
Crash Address: 
Crash State:
  IsRegExpDataWrapper(*field_value) in translated-state.cc
  v8::internal::TranslatedState::InitializeJSObjectAt
  v8::internal::TranslatedState::InitializeCapturedObjectAt
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=95464:95465

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5813945325518848

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
