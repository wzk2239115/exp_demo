# 378701682: v8_wasm_compile_fuzzer: Crash in Builtins_JSToWasmWrapperAsm

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6542232324603904

Fuzzing Engine: libFuzzer
Fuzz Target: v8_wasm_compile_fuzzer
Job Type: libfuzzer_chrome_ubsan
Platform Id: linux

Crash Type: UNKNOWN WRITE
Crash Address: 0x2bf2ddcd3b8a
Crash State:
  Builtins_JSToWasmWrapperAsm
  Builtins_JSToWasmWrapper
  Builtins_JSEntryTrampoline
  
Sanitizer: undefined (UBSAN)

Recommended Security Severity: High

Regressed: https://clusterfuzz.com/revisions?job=libfuzzer_chrome_ubsan&range=1380623:1380645

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6542232324603904

Issue manually filed by: clemensb

See https://chromium.googlesource.com/chromium/src/+/master/testing/libfuzzer/reproducing.md for instructions on reproducing this bug locally.
```
