# V8 Sandbox Bypass: OOB write in JsonStringifier::SerializeString

#### VULNERABILITY DETAILS
Changing a string value that has been embedded into a `FixedArray` causes an out-of-bounds write during JSON serialization.

#### VERSION
V8 commit: 4715559d4fe2ce6e2c0f6de3c966347b6da6a489

#### REPRODUCTION CASE

Build args:
```
is_debug=false
is_asan=true
v8_enable_sandbox=true
v8_enable_memory_corruption_api=true
dcheck_always_on=false
v8_static_library=true
v8_fuzzilli=false
target_cpu="x64"
```

Shell args: `d8 --single-threaded --sandbox-fuzzing --allow-natives-syntax --expose-gc bug.js`

##### ASAN Report:

```
==1363666==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x521000049900 at pc 0x555556dbcbdc bp 0x7fffffffb9c0 sp 0x7fffffffb9b8
WRITE of size 2 at 0x521000049900 thread T0
    #0 0x555556dbcbdb in std::__Cr::pair<unsigned char const*, unsigned short*> std::__Cr::__copy_impl::operator()<unsigned char const*, unsigned char const*, unsigned short*>(unsigned char const*, unsigned char const*, unsigned short*) const third_party/libc++/src/include/__algorithm/copy.h:40:17
    #1 0x555556dbcbdb in std::__Cr::pair<unsigned char const*, unsigned short*> std::__Cr::__copy_move_unwrap_iters<std::__Cr::__copy_impl, unsigned char const*, unsigned char const*, unsigned short*, 0>(unsigned char const*, unsigned char const*, unsigned short*) third_party/libc++/src/include/__algorithm/copy_move_common.h:94:19
    #2 0x555556dbcbdb in std::__Cr::pair<unsigned char const*, unsigned short*> std::__Cr::__copy<unsigned char const*, unsigned char const*, unsigned short*>(unsigned char const*, unsigned char const*, unsigned short*) third_party/libc++/src/include/__algorithm/copy.h:109:10
    #3 0x555556dbcbdb in unsigned short* std::__Cr::copy<unsigned char const*, unsigned short*>(unsigned char const*, unsigned char const*, unsigned short*) third_party/libc++/src/include/__algorithm/copy.h:115:10
    #4 0x555556dbcbdb in unsigned short* std::__Cr::copy_n<unsigned char const*, unsigned long, unsigned short*, 0>(unsigned char const*, unsigned long, unsigned short*) third_party/libc++/src/include/__algorithm/copy_n.h:55:10
    #5 0x555556dbcbdb in void v8::internal::CopyChars<unsigned char, unsigned short>(unsigned short*, unsigned char const*, unsigned long) src/utils/memcopy.h:398:7
    #6 0x555557dc14b0 in void v8::internal::JsonStringifier::AppendSubstringByCopy<unsigned char>(unsigned char const*, int) src/json/json-stringifier.cc:212:7
    #7 0x555557d96674 in bool v8::internal::JsonStringifier::SerializeString_<unsigned char, unsigned short, false>(v8::internal::Tagged<v8::internal::String>, v8::internal::PerThreadAssertScopeEmpty<false, (v8::internal::PerThreadAssertType)1, (v8::internal::PerThreadAssertType)2> const&) src/json/json-stringifier.cc:1588:5
    #8 0x555557d96674 in bool v8::internal::JsonStringifier::SerializeString<false>(v8::internal::Handle<v8::internal::String>) src/json/json-stringifier.cc:1694:12
    #9 0x555557da9d5d in v8::internal::JsonStringifier::Result v8::internal::JsonStringifier::Serialize_<false>(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, bool, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:1006:9
    #10 0x555557dae7e5 in v8::internal::JsonStringifier::SerializeElement(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, int) src/json/json-stringifier.cc:66:12
    #11 0x555557dae7e5 in v8::internal::JsonStringifier::Result v8::internal::JsonStringifier::SerializeFixedArrayWithPossibleTransitions<(v8::internal::ElementsKind)2>(v8::internal::DirectHandle<v8::internal::JSArray>, unsigned int, unsigned int*) src/json/json-stringifier.cc:1212:23
    #12 0x555557dae7e5 in v8::internal::JsonStringifier::SerializeJSArray(v8::internal::Handle<v8::internal::JSArray>, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:1115:7
    #13 0x555557dae7e5 in v8::internal::JsonStringifier::Result v8::internal::JsonStringifier::Serialize_<false>(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, bool, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:961:14
    #14 0x555557d826e1 in v8::internal::JsonStringifier::SerializeObject(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>) src/json/json-stringifier.cc:59:12
    #15 0x555557d826e1 in v8::internal::JsonStringifier::Stringify(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:558:19
    #16 0x555557da4a42 in v8::internal::JsonStringify(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:2798:24
    #17 0x555556d7ba48 in v8::internal::Builtin_Impl_JsonStringify(v8::internal::BuiltinArguments, v8::internal::Isolate*) src/builtins/builtins-json.cc:37:3
    #18 0x55555e3dc475 in Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit setup-isolate-deserialize.cc
    #19 0x55555e330c40 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #20 0x55555e32e85b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #21 0x55555e32e5aa in Builtins_JSEntry setup-isolate-deserialize.cc
    #22 0x5555572dc132 in v8::internal::GeneratedCode<unsigned long, unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**>::Call(unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**) src/execution/simulator.h:191:12
    #23 0x5555572dc132 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/execution.cc:436:22
    #24 0x5555572df229 in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:536:10
    #25 0x555556bac947 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2155:7
    #26 0x555556801cba in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1017:44
    #27 0x555556850679 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:4962:10
    #28 0x555556864382 in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:5906:37
    #29 0x5555568632e3 in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5815:18
    #30 0x5555568691fd in v8::Shell::Main(int, char**) src/d8/d8.cc:6700:18
    #31 0x7fffbf91f1c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #32 0x7fffbf91f28a in __libc_start_main csu/../csu/libc-start.c:360:3
    #33 0x555556687029 in _start (/work/v8-build/v8/out/FuzzingSuppressReadsO1/d8+0x1133029) (BuildId: b464b5e14fdd1c7f)

0x521000049900 is located 0 bytes after 4096-byte region [0x521000048900,0x521000049900)
allocated by thread T0 here:
    #0 0x5555567b3068 in operator new[](unsigned long) /work/llvm-project/compiler-rt/lib/asan/asan_new_delete.cpp:89:3
    #1 0x555557d86425 in v8::internal::JsonStringifier::ChangeEncoding() src/json/json-stringifier.cc:1727:19
    #2 0x555557d93a25 in bool v8::internal::JsonStringifier::SerializeString<false>(v8::internal::Handle<v8::internal::String>) src/json/json-stringifier.cc:1689:7
    #3 0x555557da9d5d in v8::internal::JsonStringifier::Result v8::internal::JsonStringifier::Serialize_<false>(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, bool, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:1006:9
    #4 0x555557dae7e5 in v8::internal::JsonStringifier::SerializeElement(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, int) src/json/json-stringifier.cc:66:12
    #5 0x555557dae7e5 in v8::internal::JsonStringifier::Result v8::internal::JsonStringifier::SerializeFixedArrayWithPossibleTransitions<(v8::internal::ElementsKind)2>(v8::internal::DirectHandle<v8::internal::JSArray>, unsigned int, unsigned int*) src/json/json-stringifier.cc:1212:23
    #6 0x555557dae7e5 in v8::internal::JsonStringifier::SerializeJSArray(v8::internal::Handle<v8::internal::JSArray>, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:1115:7
    #7 0x555557dae7e5 in v8::internal::JsonStringifier::Result v8::internal::JsonStringifier::Serialize_<false>(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, bool, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:961:14
    #8 0x555557d826e1 in v8::internal::JsonStringifier::SerializeObject(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>) src/json/json-stringifier.cc:59:12
    #9 0x555557d826e1 in v8::internal::JsonStringifier::Stringify(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:558:19
    #10 0x555557da4a42 in v8::internal::JsonStringify(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:2798:24
    #11 0x555556d7ba48 in v8::internal::Builtin_Impl_JsonStringify(v8::internal::BuiltinArguments, v8::internal::Isolate*) src/builtins/builtins-json.cc:37:3
    #12 0x55555e3dc475 in Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit setup-isolate-deserialize.cc
    #13 0x55555e330c40 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #14 0x55555e32e85b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #15 0x55555e32e5aa in Builtins_JSEntry setup-isolate-deserialize.cc
    #16 0x5555572dc132 in v8::internal::GeneratedCode<unsigned long, unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**>::Call(unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**) src/execution/simulator.h:191:12
    #17 0x5555572dc132 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/execution.cc:436:22
    #18 0x5555572df229 in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:536:10
    #19 0x555556bac947 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2155:7
    #20 0x555556801cba in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1017:44
    #21 0x555556850679 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:4962:10
    #22 0x555556864382 in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:5906:37
    #23 0x5555568632e3 in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5815:18
    #24 0x5555568691fd in v8::Shell::Main(int, char**) src/d8/d8.cc:6700:18
    #25 0x7fffbf91f1c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #26 0x7fffbf91f28a in __libc_start_main csu/../csu/libc-start.c:360:3
    #27 0x555556687029 in _start (/work/v8-build/v8/out/FuzzingSuppressReadsO1/d8+0x1133029) (BuildId: b464b5e14fdd1c7f)

SUMMARY: AddressSanitizer: heap-buffer-overflow third_party/libc++/src/include/__algorithm/copy.h:40:17 in std::__Cr::pair<unsigned char const*, unsigned short*> std::__Cr::__copy_impl::operator()<unsigned char const*, unsigned char const*, unsigned short*>(unsigned char const*, unsigned char const*, unsigned short*) const
Shadow bytes around the buggy address:
  0x521000049680: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  0x521000049700: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  0x521000049780: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  0x521000049800: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  0x521000049880: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
=>0x521000049900:[fa]fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x521000049980: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x521000049a00: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x521000049a80: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x521000049b00: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x521000049b80: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
Shadow byte legend (one shadow byte represents 8 application bytes):
  Addressable:           00
  Partially addressable: 01 02 03 04 05 06 07
  Heap left redzone:       fa
  Freed heap region:       fd
  Stack left redzone:      f1
  Stack mid redzone:       f2
  Stack right redzone:     f3
  Stack after return:      f5
  Stack use after scope:   f8
  Global redzone:          f9
  Global init order:       f6
  Poisoned by user:        f7
  Container overflow:      fc
  Array cookie:            ac
  Intra object redzone:    bb
  ASan internal:           fe
  Left alloca redzone:     ca
  Right alloca redzone:    cb
==1363666==ABORTING

## V8 sandbox violation detected!

```
