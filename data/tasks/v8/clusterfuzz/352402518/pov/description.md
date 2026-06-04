# 352402518: v8_fully_instrumented_fuzzer: DCHECK failure in scope->UniqueIdInScript() > UniqueIdInScript() in scopes.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6198778442743808

Fuzzing Engine: libFuzzer
Fuzz Target: v8_fully_instrumented_fuzzer
Job Type: libfuzzer_chrome_asan_debug
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  scope->UniqueIdInScript() > UniqueIdInScript() in scopes.cc
  void v8::internal::Scope::AllocateScopeInfosRecursively<v8::internal::Isolate>
  void v8::internal::Scope::AllocateScopeInfosRecursively<v8::internal::Isolate>
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=libfuzzer_chrome_asan_debug&range=1326146:1326175

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6198778442743808

Issue filed automatically.

See https://chromium.googlesource.com/chromium/src/+/master/testing/libfuzzer/reproducing.md for instructions on reproducing this bug locally.
```
