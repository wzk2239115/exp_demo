# 328680228: CHECK failure: length == previously_materialized_objects->length()

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4809590910156800

Fuzzer: mbarbella_js_mutation
Job Type: windows_asan_d8
Platform Id: windows

Crash Type: CHECK failure
Crash Address: 
Crash State:
  length == previously_materialized_objects->length()
  v8::platform::PrintStackTrace
  v8::internal::TranslatedState::UpdateFromPreviouslyMaterializedObjects
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=windows_asan_d8&range=92700:92701

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4809590910156800

Issue filed automatically.
```
