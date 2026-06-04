# 420697404: Debug check failed: escapes >= 0 (-2005397586 vs. 0)

## ClusterFuzz Report

```
#### VULNERABILITY DETAILS
```
#
# Fatal error in ..\..\src\objects\js-regexp.cc, line 234
# Debug check failed: escapes >= 0 (-2005397586 vs. 0).
#
#
#
#FailureMessage Object: 00000012179FD550
==== C stack trace ===============================

	v8::base::debug::StackTrace::StackTrace [0x0x7fff2bb5b685+37] (D:\Browser\v8\v8\src\base\debug\stack_trace_win.cc:173)
	v8::platform::`anonymous namespace'::PrintStackTrace [0x0x7fff2bcdab89+57] (D:\Browser\v8\v8\src\libplatform\default-platform.cc:28)
	V8_Fatal [0x0x7fff2bb35463+323] (D:\Browser\v8\v8\src\base\logging.cc:214)
	v8::base::`anonymous namespace'::DefaultDcheckHandler [0x0x7fff2bb34e8c+44] (D:\Browser\v8\v8\src\base\logging.cc:59)
	V8_Dcheck [0x0x7fff2bb35571+81] (D:\Browser\v8\v8\src\base\logging.cc:228)
	v8::internal::`anonymous namespace'::CountAdditionalEscapeChars<unsigned short> [0x0x7ffeaae0b824+740] (D:\Browser\v8\v8\src\objects\js-regexp.cc:234)
	v8::internal::`anonymous namespace'::EscapeRegExpSource [0x0x7ffeaae08824+420] (D:\Browser\v8\v8\src\objects\js-regexp.cc:306)
	v8::internal::JSRegExp::Initialize [0x0x7ffeaae07dfa+618] (D:\Browser\v8\v8\src\objects\js-regexp.cc:344)
	v8::internal::JSRegExp::Initialize [0x0x7ffeaae08581+529] (D:\Browser\v8\v8\src\objects\js-regexp.cc:179)
	v8::internal::__RT_impl_Runtime_RegExpInitializeAndCompile [0x0x7ffeab3fe615+549] (D:\Browser\v8\v8\src\runtime\runtime-regexp.cc:2147)
	v8::internal::Runtime_RegExpInitializeAndCompile [0x0x7ffeab3fe10d+413] (D:\Browser\v8\v8\src\runtime\runtime-regexp.cc:2137)
	Builtins_CEntry_Return1_ArgvOnStack_NoBuiltinExit [0x0x7ffeaf6b5b41+65]
	Builtins_RegExpConstructor [0x0x7ffeaf5f40db+7579]
	Builtins_InterpreterPushArgsThenFastConstructFunction [0x0x7ffeaf247501+1089]
	Builtins_ConstructHandler [0x0x7ffeafe522c5+8261]
	Builtins_InterpreterEntryTrampoline [0x0x7ffeaf2467f2+370]
	Builtins_InterpreterEntryTrampoline [0x0x7ffeaf2467f2+370]
	Builtins_JSEntryTrampoline [0x0x7ffeaf239ce7+103]
	Builtins_JSEntry [0x0x7ffeaf23983f+255]
	v8::internal::GeneratedCode<unsigned long long,unsigned long long,unsigned long long,unsigned long long,unsigned long long,long long,unsigned long long **>::Call [0x0x7ffea9f5438c+108] (D:\Browser\v8\v8\src\execution\simulator.h:212)
	v8::internal::`anonymous namespace'::Invoke [0x0x7ffea9f503cd+5469] (D:\Browser\v8\v8\src\execution\execution.cc:441)
	v8::internal::Execution::CallScript [0x0x7ffea9f50c61+513] (D:\Browser\v8\v8\src\execution\execution.cc:542)
	v8::Script::Run [0x0x7ffea978b5cf+1135] (D:\Browser\v8\v8\src\api\api.cc:1964)
	v8::Script::Run [0x0x7ffea978b148+120] (D:\Browser\v8\v8\src\api\api.cc:1929)
	v8::Shell::ExecuteString [0x0x7ff6ae1d21b6+3142] (D:\Browser\v8\v8\src\d8\d8.cc:1030)
	v8::SourceGroup::Execute [0x0x7ff6ae1f7e26+1174] (D:\Browser\v8\v8\src\d8\d8.cc:5073)
	v8::Shell::RunMainIsolate [0x0x7ff6ae1ff287+631] (D:\Browser\v8\v8\src\d8\d8.cc:6027)
	v8::Shell::RunMain [0x0x7ff6ae1feced+205] (D:\Browser\v8\v8\src\d8\d8.cc:5935)
	v8::Shell::Main [0x0x7ff6ae201901+3873] (D:\Browser\v8\v8\src\d8\d8.cc:6801)
	main [0x0x7ff6ae202333+35] (D:\Browser\v8\v8\src\d8\d8.cc:6893)
	invoke_main [0x0x7ff6ae368489+57] (D:\a\_work\1\s\src\vctools\crt\vcstartup\src\startup\exe_common.inl:79)
	__scrt_common_main_seh [0x0x7ff6ae3685c2+306] (D:\a\_work\1\s\src\vctools\crt\vcstartup\src\startup\exe_common.inl:288)
	__scrt_common_main [0x0x7ff6ae36864e+14] (D:\a\_work\1\s\src\vctools\crt\vcstartup\src\startup\exe_common.inl:331)
	mainCRTStartup [0x0x7ff6ae36866e+14] (D:\a\_work\1\s\src\vctools\crt\vcstartup\src\startup\exe_main.cpp:17)
	BaseThreadInitThunk [0x0x7fff6adfe8d7+23]
	RtlUserThreadStart [0x0x7fff6cafc5dc+44]
```
#### VERSION

V8 version 13.9.0 (candidate)

#### REPRODUCTION CASE

Build: `python3 tools/dev/gm.py x64.debug`

Run: `./d8 poc.js`

---
Reporter credit: Shaheen Fazim
```

## Vulnerability Description

PoC for an integer overflow in RegExp compilation. Constructs a string of ~357 million repetitions of U+2028 (Unicode line separator, 6x expansion when escaped). The total escaped length overflows a 32-bit integer. Passes this to 'new RegExp(pattern)', triggering an integer overflow in the regexp compiler's length calculation or buffer allocation.

## Capabilities

Crashes with a CHECK failure or SIGSEGV during RegExp compilation due to 32-bit integer overflow. No controlled memory write.
