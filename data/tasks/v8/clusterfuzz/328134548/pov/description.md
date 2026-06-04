# 328134548: DCHECK failure in IsHeapNumber(value) in objects-debug.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4761386730586112

Fuzzer: ochang_js_fuzzer_win
Job Type: windows_asan_d8_dbg
Platform Id: windows

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  IsHeapNumber(value) in objects-debug.cc
  v8::platform::PrintStackTrace
  v8::internal::JSObject::JSObjectVerify
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=windows_asan_d8_dbg&range=92666:92667

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4761386730586112

Issue filed automatically.
```
