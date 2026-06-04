# 445966259: V8 Sandbox Bypass: AAW/PC control via DebugBreakTrampoline

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

#### Details

It's possible to tail call into any builtin from DebugBreakTrampoline regardless of linkage, allowing an attacker to escape the sandbox.

The crux of the issue can be seen in [DebugBreakTrampoline](https://source.chromium.org/chromium/chromium/src/+/main:v8/src/builtins/builtins-internal-gen.cc;l=111-118;drc=6749ee535fe656b4e0d47e6a5e7e62d93693dd02):
```cpp
TF_BUILTIN(DebugBreakTrampoline, CodeStubAssembler) {
  // ...snipped...
  CallRuntime(Runtime::kDebugBreakAtEntry, context, function);
  Goto(&tailcall_to_shared);

  BIND(&tailcall_to_shared);
  // Tail call into code object on the SharedFunctionInfo.
  TNode<Code> code = GetSharedFunctionInfoCode(shared);

  // [!!!] Linkage was not validated

  // TailCallJSCode will take care of parameter count validation between the
  // code and dispatch handle.
  TailCallJSCode(code, context, function, new_target, arg_count,
                 dispatch_handle);
}
```
There is no linkage validation after retrieving the code from the SharedFunctionInfo. Thus, one can store builtins such as `CEntry_Return1_ArgvOnStack_NoBuiltinExit` and/or `MemCopyUint8Uint8` within the SharedFunctionInfo to obtain PC control/AAW.

For the PoC, the `CEntry_Return1_ArgvOnStack_NoBuiltinExit` builtin was abused similar to crbug/445209324 to obtain PC control.

**Suggested Fix:** Validate linkage before tail-calling, as presumably this trampoline is meant to only be used for JS linkage functions.

### VERSION
V8 commit: 3d0f462a17ffa08869805874ac46726783512fef

#### REPRODUCTION CASE

**NOTE (for the shepherd):** To reproduce in CF, the `linux_d8_sandbox_testing` job type with the below shell args should hopefully do the trick.

**Shell args**: `--allow-natives-syntax --sandbox-testing`

**Build args**:
```
is_debug=false
is_asan=true
v8_enable_sandbox=true
v8_enable_memory_corruption_api=true
dcheck_always_on=false
target_cpu="x64"
```

**Sample output (`--disable-in-process-stack-traces` used to show PC)**:
```
Sandbox testing mode is enabled. Only sandbox violations will be reported, all other crashes will be ignored.
Sandbox bounds: [0x745500000000,0x755500000000)

## V8 sandbox violation detected!

Access type was read though which is technically not a sandbox violation. This requires manual investigation.
AddressSanitizer:DEADLYSIGNAL
=================================================================
==152308==ERROR: AddressSanitizer: SEGV on unknown address 0x424242424242 (pc 0x424242424242 bp 0x7ffd64b8e4f0 sp 0x7ffd64b8e4d8 T0)
==152308==The signal is caused by a READ memory access.
    #0 0x424242424242  (<unknown module>)
    #1 0x5b4cc710023e  (<unknown module>)
    #2 0x5b4c671287a9 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #3 0x5b4c6712555b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #4 0x5b4c671252aa in Builtins_JSEntry setup-isolate-deserialize.cc
    #5 0x5b4c62b7a3a2 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/simulator.h:212:12
    #6 0x5b4c62b7b928 in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:542:10
    #7 0x5b4c627071ad in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:1955:7
    #8 0x5b4c6242fad6 in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1036:44
    #9 0x5b4c6246794d in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:5487:10
    #10 0x5b4c62473743 in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:6443:37
    #11 0x5b4c62472b75 in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:6351:18
    #12 0x5b4c6247627c in v8::Shell::Main(int, char**) src/d8/d8.cc:7241:18
    #13 0x79964562a1c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #14 0x79964562a28a in __libc_start_main csu/../csu/libc-start.c:360:3
    #15 0x5b4c62322029 in _start (/home/krish/chrome/v8/v8/out/asan_no_dcheck/d8+0x1f92029) (BuildId: 4f9566aef8cd1e75)

==152308==Register values:
rax = 0x0000000000000001  rbx = 0x0000424242424242  rcx = 0x00005b4c671d3d40  rdx = 0x000078a644ae1000  
rdi = 0x0000000000000001  rsi = 0x00007ffd64b8e500  rbp = 0x00007ffd64b8e4f0  rsp = 0x00007ffd64b8e4d8  
 r8 = 0x00007455000c0671   r9 = 0x0000000000000000  r10 = 0x0000759600c64000  r11 = 0x0000000000000000  
r12 = 0x0000744bf0000000  r13 = 0x000078a644ae1080  r14 = 0x0000745500000000  r15 = 0x00007ffd64b8e500  
AddressSanitizer can not provide additional info.
SUMMARY: AddressSanitizer: SEGV (<unknown module>) 
==152308==ABORTING
```

### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Sandbox violation


### CREDIT INFORMATION

Reporter credit: Krishna Ravishankar (@krsh732)
```

## Vulnerability Description

Exploit using Sandbox.setFunctionCodeToBuiltin and Sandbox.getBuiltinNames to redirect a function's code to the DebugBreakTrampoline builtin. Then zeroes out the TrustedFunctionData field and sets the function_data to a CEntry stub index, so calling the function invokes call(0x424242424242n), achieving PC control at an arbitrary address.

## Capabilities

Full PC control: redirects a JS function to call an arbitrary address (0x424242424242n) via DebugBreakTrampoline builtin substitution and TrustedFunctionData corruption using Sandbox APIs.
