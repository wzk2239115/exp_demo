# V8 Sandbox Bypass: OOB write in icu_74::CharString::append

#### VULNERABILITY DETAILS
NOTE: This bug is flaky and may require multiple tries!

The Intl.NumberFormat.formatRangeToParts function causes the `IntlMathematicalValue::ToFormattable` function to be executed. Apparently the to-be-formatted type must be a Number to pass some previous checks, thus the reproducer starts out with a Number and transmutes it to a string during execution:

```c++
Maybe<icu::Formattable> IntlMathematicalValue::ToFormattable(
    Isolate* isolate) const {
  if (IsNumber(*value_)) { //<----- this check must be false,
                           //       thus we change the map of value to string before here.
    return Just(icu::Formattable(approx_));
  }
  DirectHandle<String> string;
  ASSIGN_RETURN_ON_EXCEPTION_VALUE(isolate, string, ToString(isolate),
                                   Nothing<icu::Formattable>());
  UErrorCode status = U_ZERO_ERROR;
  {
    DisallowGarbageCollection no_gc;
    const String::FlatContent& flat = string->GetFlatContent(no_gc);
    int32_t length = static_cast<int32_t>(string->length());
    if (flat.IsOneByte()) {
      icu::Formattable result(
          {reinterpret_cast<const char*>(flat.ToOneByteVector().begin()),
           length}, // <---- this will create a `StringPiece` with length 0x7fffffff,
                    // i.e., length+1 results in a negative value
          status);
      if (U_SUCCESS(status)) return Just(result);
    } else {
      icu::Formattable result({string->ToCString().get(), length}, status);
      if (U_SUCCESS(status)) return Just(result);
    }
  }
  THROW_NEW_ERROR_RETURN_VALUE(isolate,
                               NewTypeError(MessageTemplate::kIcuError),
                               Nothing<icu::Formattable>());
}
```

The constructor `icu::Formattable result()` from above will eventually call `CharString &CharString::append` (`icu/source/common/charstr.cpp:112`) which contains the following code that contains an integer overflow when passing a `sLength` of 0x7fffffff:
```c++
CharString &CharString::append(const char *s, int32_t sLength, UErrorCode &errorCode) {
    if(U_FAILURE(errorCode)) {
        return *this;
    }
    if(sLength<-1 || (s==nullptr && sLength!=0)) {
        errorCode=U_ILLEGAL_ARGUMENT_ERROR;
        return *this;
    }
    if(sLength<0) {
        sLength= static_cast<int32_t>(uprv_strlen(s));
    }
    if(sLength>0) {
        if(s==(buffer.getAlias()+len)) {
            // The caller wrote into the getAppendBuffer().
            if(sLength>=(buffer.getCapacity()-len)) {
                // The caller wrote too much.
                errorCode=U_INTERNAL_PROGRAM_ERROR;
            } else {
                buffer[len+=sLength]=0;
            }
        } else if(buffer.getAlias()<=s && s<(buffer.getAlias()+len) &&
                  sLength>=(buffer.getCapacity()-len)
        ) {
            // (Part of) this string is appended to itself which requires reallocation,
            // so we have to make a copy of the substring and append that.
            return append(CharString(s, sLength, errorCode), errorCode);
        // <----------- The check below will pass because sLength+1 will overflow,
        // <----------- and the memcpy will then write OOB.
        } else if(ensureCapacity(len+sLength+1, 0, errorCode)) {
            uprv_memcpy(buffer.getAlias()+len, s, sLength);
            buffer[len+=sLength]=0;
        }
    }
    return *this;
}
```

So this is apparently a bug in third_party/icu.


#### VERSION
V8 commit: b16b7d4801081446f2eba527c581d468a688453c (Fri Mar 14 11:36:32 2025 +0100)

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
==2737101==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7baa280928e0 at pc 0x56200ac0dd2e bp 0x7ffca4a69910 sp 0x7ffca4a690d0
WRITE of size 2147483647 at 0x7baa280928e0 thread T0
    #0 0x56200ac0dd2d in __asan_memcpy /b/s/w/ir/cache/builder/src/third_party/llvm/compiler-rt/lib/asan/asan_interceptors_memintrinsics.cpp:63:3
    #1 0x56200d70a036 in icu_74::CharString::append(char const*, int, UErrorCode&) third_party/icu/source/common/charstr.cpp:139:13
    #2 0x56200d59e980 in append third_party/icu/source/common/charstr.h:124:16
    #3 0x56200d59e980 in CharString third_party/icu/source/common/charstr.h:46:9
    #4 0x56200d59e980 in icu_74::number::impl::DecNum::setTo(icu_74::StringPiece, UErrorCode&) third_party/icu/source/i18n/number_utils.cpp:122:16
    #5 0x56200d530684 in icu_74::number::impl::DecimalQuantity::setToDecNumber(icu_74::StringPiece, UErrorCode&) third_party/icu/source/i18n/number_decimalquantity.cpp:531:12
    #6 0x56200d501037 in icu_74::Formattable::setDecimalNumber(icu_74::StringPiece, UErrorCode&) third_party/icu/source/i18n/fmtable.cpp:811:9
    #7 0x56200c013578 in v8::internal::IntlMathematicalValue::ToFormattable(v8::internal::Isolate*) const src/objects/js-number-format.cc:1787:24
    #8 0x56200c012637 in v8::internal::IntlMathematicalValue::FormatRange(v8::internal::Isolate*, icu_74::number::LocalizedNumberRangeFormatter const&, v8::internal::IntlMathematicalValue const&, v8::internal::IntlMathematicalValue const&) src/objects/js-number-format.cc:1608:3
    #9 0x56200c019a5e in PartitionNumberRangePattern<v8::internal::JSArray, &v8::internal::(anonymous namespace)::FormatRangeToJSArray> src/objects/js-number-format.cc:2048:7
    #10 0x56200c019a5e in v8::internal::JSNumberFormat::FormatNumericRangeToParts(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSNumberFormat>, v8::internal::Handle<v8::internal::Object>, v8::internal::Handle<v8::internal::Object>) src/objects/js-number-format.cc:2186:10
    #11 0x56200b29c8b3 in v8::internal::Tagged<v8::internal::Object> v8::internal::NumberFormatRange<v8::internal::JSArray, &v8::internal::JSNumberFormat::FormatNumericRangeToParts(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSNumberFormat>, v8::internal::Handle<v8::internal::Object>, v8::internal::Handle<v8::internal::Object>)>(v8::internal::BuiltinArguments, v8::internal::Isolate*, char const*) src/builtins/builtins-intl.cc:561:3
    #12 0x56200b269be3 in Builtin_Impl_NumberFormatPrototypeFormatRangeToParts src/builtins/builtins-intl.cc:575:10
    #13 0x56200b269be3 in v8::internal::Builtin_NumberFormatPrototypeFormatRangeToParts(int, unsigned long*, v8::internal::Isolate*) src/builtins/builtins-intl.cc:571:1
    #14 0x56200f7062f5 in Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit setup-isolate-deserialize.cc
    #15 0x56200f65ec34 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #16 0x56200f65c71b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #17 0x56200f65c46a in Builtins_JSEntry setup-isolate-deserialize.cc
    #18 0x56200b47c5f4 in Call src/execution/simulator.h:205:12
    #19 0x56200b47c5f4 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/execution.cc:437:22
    #20 0x56200b47db98 in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:537:10
    #21 0x56200b0200c7 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:1968:7
    #22 0x56200ac76bd7 in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1027:44
    #23 0x56200aca2833 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:5053:10
    #24 0x56200acad70e in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:6007:37
    #25 0x56200acacde6 in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5915:18
    #26 0x56200acafdd8 in v8::Shell::Main(int, char**) src/d8/d8.cc:6780:18
    #27 0x7faa29f701c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #28 0x7faa29f7028a in __libc_start_main csu/../csu/libc-start.c:360:3
    #29 0x56200ab70029 in _start (/work/v8-build/v8/out/Reproduction/d8+0x1113029) (BuildId: c99095fa2d6782c0)

Address 0x7baa280928e0 is located in stack of thread T0 at offset 96 in frame
    #0 0x56200d59e87f in icu_74::number::impl::DecNum::setTo(icu_74::StringPiece, UErrorCode&) third_party/icu/source/i18n/number_utils.cpp:120

  This frame has 1 object(s):
    [32, 96) 'cstr' (line 122) <== Memory access at offset 96 overflows this variable
HINT: this may be a false positive if your program uses some custom stack unwind mechanism, swapcontext or vfork
      (longjmp and C++ exceptions *are* supported)
SUMMARY: AddressSanitizer: stack-buffer-overflow third_party/icu/source/common/charstr.cpp:139:13 in icu_74::CharString::append(char const*, int, UErrorCode&)
Shadow bytes around the buggy address:
  0x7baa28092600: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7baa28092680: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7baa28092700: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7baa28092780: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7baa28092800: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
=>0x7baa28092880: f1 f1 f1 f1 00 00 00 00 00 00 00 00[f3]f3 f3 f3
  0x7baa28092900: f1 f1 f1 f1 f8 f8 f8 f8 f8 f8 f8 f8 f3 f3 f3 f3
  0x7baa28092980: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7baa28092a00: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7baa28092a80: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7baa28092b00: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
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
==2737101==ABORTING

## V8 sandbox violation detected!
```
