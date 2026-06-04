# 416913840: v8_json_parse_valid_json_p_fuzztest: CHECK failure: CheckTag(content, tag_range)

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=6333815043588096

Fuzzing Engine: centipede
Fuzz Target: v8_json_parse_valid_json_p_fuzztest
Job Type: centipede_v8_asan
Platform Id: linux

Crash Type: CHECK failure
Crash Address: 
Crash State:
  CheckTag(content, tag_range)
  v8::internal::ExternalString::resource_as_address
  v8::internal::JsonParser<unsigned char>::ParseJsonObject
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=centipede_v8_asan&range=100114:100115

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=6333815043588096

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
