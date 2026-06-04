# 423955533: DCHECK failure in iterator_.current_offset() == continuation->last_continuation in maglev-graph-bu

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4795142472925184

Fuzzer: ochang_js_fuzzer_win
Job Type: windows_asan_d8_dbg
Platform Id: windows

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  iterator_.current_offset() == continuation->last_continuation in maglev-graph-bu
  v8::platform::PrintStackTrace
  v8::internal::maglev::MaglevGraphBuilder::VisitGetNamedProperty
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=windows_asan_d8_dbg&range=100752:100753

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4795142472925184

Issue filed automatically.
```
