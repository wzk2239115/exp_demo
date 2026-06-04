# 338122900: Crash with empty stacktrace

## ClusterFuzz Report

```
Detailed Report: https://clusterfuzz.com/testcase?key=5926020944166912

Fuzzer: None
Job Type: linux_asan_d8_dbg
Platform Id: linux

Crash Type: UNKNOWN READ
Crash Address: 0x0f9c090540ec
Crash State:
  NULL
Sanitizer: address (ASAN)

Recommended Security Severity: Medium

Regressed: https://clusterfuzz.com/revisions?job=linux_asan_d8_dbg&range=93459:93460

Reproducer Testcase: https://clusterfuzz.com/download?testcase_id=5926020944166912

Issue manually filed by: cffsmith

To reproduce this, please build the target in this report and run it against the reproducer testcase. Please use the GN arguments provided at bottom of this report when building the binary. 

If you have trouble reproducing, please also export the environment variables listed under "[Environment]" in the crash stacktrace.

If you have any feedback on reproducing test cases, let us know at https://forms.gle/Yh3qCYFveHj6E5jz5 so we can improve.
```

## Vulnerability Description

Fuzzer-generated JSPI crash. An outer Wasm instance (v104) exports a function wrapped with WebAssembly.promising (v107). Calling v107() invokes the imported JS function f0, which itself creates two more Wasm instances and a nested promising wrapper (v11) called with f0 as both arguments. A second Wasm instance export (v57.exports.w0) is lazily compiled inside f0. The combined async call chain produces SIGSEGV at address 0x2011 (null + fixed small offset).

## Capabilities

Crashes the process with SIGSEGV at 0x2011. Crash address is fixed and not attacker-controlled. No memory read/write primitive.
