# V8 sandbox violation in icu_74::UnicodeString::doAppend

#### VULNERABILITY DETAILS
Converting a long string to local encoding via `"<...>".localeCompare` causes an OOB write.

#### VERSION
V8 commit: 69b47d88cb8f3bff0966000cd039b50786bbd891

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
==180411==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x7a72fffff7f0 at pc 0x5645f9e49ac6 bp 0x7fff70df8510 sp 0x7fff70df7cd0
WRITE of size 4294967286 at 0x7a72fffff7f0 thread T0
    #0 0x5645f9e49ac5 in __asan_memmove /b/s/w/ir/cache/builder/src/third_party/llvm/compiler-rt/lib/asan/asan_interceptors_memintrinsics.cpp:71:3
    #1 0x564600fdec1b in us_arrayCopy third_party/icu/source/common/unistr.cpp:87:5
    #2 0x564600fdec1b in icu_74::UnicodeString::doAppend(char16_t const*, int, int) third_party/icu/source/common/unistr.cpp:1641:7
    #3 0x5645fd89268d in v8::internal::Intl::ToICUUnicodeString(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::String>, int) src/objects/intl-objects.cc:240:10
    #4 0x5645fd8ad712 in v8::internal::Intl::CompareStrings(v8::internal::Isolate*, icu_74::Collator const&, v8::internal::DirectHandle<v8::internal::String>, v8::internal::DirectHandle<v8::internal::String>, v8::internal::Intl::CompareStringsOptions) src/objects/intl-objects.cc:1483:7
    #5 0x5645fd8aa9b1 in v8::internal::Intl::StringLocaleCompare(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::String>, v8::internal::DirectHandle<v8::internal::String>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>, char const*) src/objects/intl-objects.cc:1037:10
    #6 0x5645fb14f0ad in v8::internal::Builtin_Impl_StringPrototypeLocaleCompareIntl(v8::internal::BuiltinArguments, v8::internal::Isolate*) src/builtins/builtins-intl.cc:74:31
    #7 0x5645fb14ca6f in v8::internal::Builtin_StringPrototypeLocaleCompareIntl(int, unsigned long*, v8::internal::Isolate*) src/builtins/builtins-intl.cc:64:1
    #8 0x564604c878b5 in Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit setup-isolate-deserialize.cc
    #9 0x564604be0c74 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #10 0x564604bde75b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #11 0x564604bde4aa in Builtins_JSEntry setup-isolate-deserialize.cc
    #12 0x5645fb7af3e6 in v8::internal::GeneratedCode<unsigned long, unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**>::Call(unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**) src/execution/simulator.h:191:12
    #13 0x5645fb7a4b78 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/execution.cc:437:22
    #14 0x5645fb7a6026 in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:537:10
    #15 0x5645fa854468 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2147:7
    #16 0x5645fa8531b6 in v8::Script::Run(v8::Local<v8::Context>) src/api/api.cc:2110:10
    #17 0x5645f9f464dc in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1017:44
    #18 0x5645f9fd4a72 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:4959:10
    #19 0x5645f9fe9772 in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:5904:37
    #20 0x5645f9fe8106 in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5812:18
    #21 0x5645f9fee603 in v8::Shell::Main(int, char**) src/d8/d8.cc:6680:18
    #22 0x5645f9fef8f1 in main src/d8/d8.cc:6772:43
    #23 0x7fbe476111c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #24 0x7fbe4761128a in __libc_start_main csu/../csu/libc-start.c:360:3
    #25 0x5645f9dac029 in _start (/work/v8-build/v8/out/Reproduction/d8+0x24e6029) (BuildId: 9691a3447490edc9)

0x7a72fffff7f0 is located 0 bytes after 4294967280-byte region [0x7a71fffff800,0x7a72fffff7f0)
allocated by thread T0 here:
    #0 0x5645f9e4b714 in malloc /b/s/w/ir/cache/builder/src/third_party/llvm/compiler-rt/lib/asan/asan_malloc_linux.cpp:67:3
    #1 0x564600fdfe1d in allocate third_party/icu/source/common/unistr.cpp:382:34
    #2 0x564600fdfe1d in icu_74::UnicodeString::cloneArrayIfNeeded(int, int, signed char, int**, signed char) third_party/icu/source/common/unistr.cpp:1892:8
    #3 0x564600fdebb2 in icu_74::UnicodeString::doAppend(char16_t const*, int, int) third_party/icu/source/common/unistr.cpp:1631:7
    #4 0x5645fd89268d in v8::internal::Intl::ToICUUnicodeString(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::String>, int) src/objects/intl-objects.cc:240:10
    #5 0x5645fd8ad712 in v8::internal::Intl::CompareStrings(v8::internal::Isolate*, icu_74::Collator const&, v8::internal::DirectHandle<v8::internal::String>, v8::internal::DirectHandle<v8::internal::String>, v8::internal::Intl::CompareStringsOptions) src/objects/intl-objects.cc:1483:7
    #6 0x5645fd8aa9b1 in v8::internal::Intl::StringLocaleCompare(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::String>, v8::internal::DirectHandle<v8::internal::String>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>, char const*) src/objects/intl-objects.cc:1037:10
    #7 0x5645fb14f0ad in v8::internal::Builtin_Impl_StringPrototypeLocaleCompareIntl(v8::internal::BuiltinArguments, v8::internal::Isolate*) src/builtins/builtins-intl.cc:74:31
    #8 0x5645fb14ca6f in v8::internal::Builtin_StringPrototypeLocaleCompareIntl(int, unsigned long*, v8::internal::Isolate*) src/builtins/builtins-intl.cc:64:1
    #9 0x564604c878b5 in Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit setup-isolate-deserialize.cc
    #10 0x564604be0c74 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #11 0x564604bde75b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #12 0x564604bde4aa in Builtins_JSEntry setup-isolate-deserialize.cc
    #13 0x5645fb7af3e6 in v8::internal::GeneratedCode<unsigned long, unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**>::Call(unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**) src/execution/simulator.h:191:12
    #14 0x5645fb7a4b78 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/execution.cc:437:22
    #15 0x5645fb7a6026 in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:537:10
    #16 0x5645fa854468 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2147:7
    #17 0x5645fa8531b6 in v8::Script::Run(v8::Local<v8::Context>) src/api/api.cc:2110:10
    #18 0x5645f9f464dc in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1017:44
    #19 0x5645f9fd4a72 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:4959:10
    #20 0x5645f9fe9772 in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:5904:37
    #21 0x5645f9fe8106 in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5812:18
    #22 0x5645f9fee603 in v8::Shell::Main(int, char**) src/d8/d8.cc:6680:18
    #23 0x5645f9fef8f1 in main src/d8/d8.cc:6772:43
    #24 0x7fbe476111c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #25 0x7fbe4761128a in __libc_start_main csu/../csu/libc-start.c:360:3
    #26 0x5645f9dac029 in _start (/work/v8-build/v8/out/Reproduction/d8+0x24e6029) (BuildId: 9691a3447490edc9)

SUMMARY: AddressSanitizer: heap-buffer-overflow third_party/icu/source/common/unistr.cpp:87:5 in us_arrayCopy
Shadow bytes around the buggy address:
  0x7a72fffff500: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  0x7a72fffff580: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  0x7a72fffff600: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  0x7a72fffff680: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  0x7a72fffff700: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
=>0x7a72fffff780: 00 00 00 00 00 00 00 00 00 00 00 00 00 00[fa]fa
  0x7a72fffff800: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7a72fffff880: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7a72fffff900: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7a72fffff980: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7a72fffffa00: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
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
==180411==ABORTING

## V8 sandbox violation detected!

```
