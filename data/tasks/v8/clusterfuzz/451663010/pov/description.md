# 451663010: DCHECK failure in visited_.insert(lit).second in ast-function-literal-id-reindexer.cc

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=4657471234703360

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: DCHECK failure
Crash Address: 
Crash State:
  visited_.insert(lit).second in ast-function-literal-id-reindexer.cc
  v8::internal::AstTraversalVisitor<v8::internal::AstFunctionLiteralIdReindexer>::
  v8::internal::AstFunctionLiteralIdReindexer::VisitClassLiteral
  
Sanitizer: address (ASAN)

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=95611:95612

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=4657471234703360

Issue filed automatically.

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary.

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```
