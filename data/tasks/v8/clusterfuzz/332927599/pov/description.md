# 332927599: v8_script_parser_fuzzer: Use-after-poison in v8::internal::RegExpParserImpl<unsigned char>::GetCapture

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5333287586168832

Fuzzing Engine: libFuzzer
Fuzz Target: v8_script_parser_fuzzer
Job Type: v8_libfuzzer_asan_linux_arm_sim
Platform Id: linux

Crash Type: Use-after-poison READ 4
Crash Address: 0xe792b1e0
Crash State:
  v8::internal::RegExpParserImpl<unsigned char>::GetCapture
  v8::internal::RegExpParserImpl<unsigned char>::ParseDisjunction
  v8::internal::RegExpParserImpl<unsigned char>::Parse
  
Sanitizer: address (ASAN)

Recommended Security Severity: High

Regressed: https://clusterfuzz.com/revisions?job=v8_libfuzzer_asan_linux_arm_sim&range=1283024:1283029

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5333287586168832

Issue filed automatically.

See https://chromium.googlesource.com/chromium/src/+/master/testing/libfuzzer/reproducing.md for instructions on reproducing this bug locally.
```
