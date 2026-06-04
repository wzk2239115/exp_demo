# 428226995: CHECK failure: is_loadable()

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4958207650758656

Fuzzer: ochang_js_fuzzer_mac
Job Type: mac_asan_d8
Platform Id: mac

Crash Type: CHECK failure
Crash Address: 
Crash State:
  is_loadable()
  libsystem_c.dylib
  v8::internal::maglev::StraightForwardRegisterAllocator::AssignFixedInput
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=mac_asan_d8&range=101091:101092

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4958207650758656

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
