# 459883555: v8_wasm_module_fuzzer: DCHECK failure in module->num_imported_functions == statuses.size() in module-compiler.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5451234022457344

Fuzzing Engine: libFuzzer
Fuzz Target: v8_wasm_module_fuzzer
Job Type: libfuzzer_chrome_asan_debug_highend
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  module->num_imported_functions == statuses.size() in module-compiler.cc
  v8::internal::wasm::ValidateAndSetBuiltinImports
  v8::internal::wasm::WasmEngine::SyncCompile
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=libfuzzer_chrome_asan_debug_highend&range=1543263:1543270

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5451234022457344

Issue filed automatically.

See https://chromium.googlesource.com/chromium/src/+/master/testing/libfuzzer/reproducing.md for instructions on reproducing this bug locally.
```
