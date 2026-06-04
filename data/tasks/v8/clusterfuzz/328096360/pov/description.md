# 328096360: CHECK failure: !translated_values->IsMaterializedObject()

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4724932054810624

Fuzzer: mbarbella_js_mutation
Job Type: windows_asan_d8
Platform Id: windows

Crash Type: CHECK failure
Crash Address: 
Crash State:
  !translated_values->IsMaterializedObject()
  v8::platform::PrintStackTrace
  v8::internal::OptimizedFrame::Summarize
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=windows_asan_d8&range=92666:92667

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4724932054810624

Issue filed automatically.
```
