# V8 sandbox violation in v8::base::GenerateCountedDigits

#### VULNERABILITY DETAILS
During the execution of the `Number.prototype.toPrecision` builtin a heap Number is converted to a double without checking whether it is NaN. This double is then used to check some stack buffer bounds, which pass because comparing to NaN is false. Eventually, the value is cast to int, resulting in -1 being used as size value during a copy later during execution.

```c++
BUILTIN(NumberPrototypeToPrecision) {
  HandleScope scope(isolate);
  DirectHandle<Object> value = args.at(0);
  Handle<Object> precision = args.atOrUndefined(isolate, 1);

  // Unwrap the receiver {value}.
  if (IsJSPrimitiveWrapper(*value)) {
    value = direct_handle(Cast<JSPrimitiveWrapper>(value)->value(), isolate);
  }
  if (!IsNumber(*value)) {
    THROW_NEW_ERROR_RETURN_FAILURE(
        isolate, NewTypeError(MessageTemplate::kNotGeneric,
                              isolate->factory()->NewStringFromAsciiChecked(
                                  "Number.prototype.toPrecision"),
                              isolate->factory()->Number_string()));
  }
  double const value_number = Object::NumberValue(*value);

  // If no {precision} was specified, just return ToString of {value}.
  if (IsUndefined(*precision, isolate)) {
    return *isolate->factory()->NumberToString(value);
  }

  // Convert the {precision} to an integer first.
  // <<<<<<<<<<< precision is a Number. If precision can not be stored in an SMI,
  // <<<<<<<<<<< this will allocate a new Number heap object.
  ASSIGN_RETURN_FAILURE_ON_EXCEPTION(isolate, precision,
                                     Object::ToInteger(isolate, precision));
  // <<<<<<<<<<< Here, we store NaN through a background thread
  // <<<<<<<<<<< into the heap object from above.
  double const precision_number = Object::NumberValue(*precision);
  // <<<<<<<<<<< precision_number is NaN

  if (std::isnan(value_number)) return ReadOnlyRoots(isolate).NaN_string();
  if (std::isinf(value_number)) {
    return (value_number < 0.0) ? ReadOnlyRoots(isolate).minus_Infinity_string()
                                : ReadOnlyRoots(isolate).Infinity_string();
  }

  // <<<<<<<<<<< This check will not trigger for NaN
  if (precision_number < 1.0 || precision_number > kMaxFractionDigits) {
    THROW_NEW_ERROR_RETURN_FAILURE(
        isolate, NewRangeError(MessageTemplate::kToPrecisionFormatRange));
  }
  char chars[kDoubleToPrecisionMaxChars];
  base::Vector<char> buffer = base::ArrayVector(chars);
  // <<<<<<<<<<< NaN is cast to int, resulting in -1
  std::string_view str = DoubleToPrecisionStringView(
      value_number, static_cast<int>(precision_number), buffer);
  DirectHandle<String> result =
      isolate->factory()->NewStringFromAsciiChecked(str);
  return *result;
}

```

#### VERSION
V8 commit: 932fab3dab1483a16dc10bd0e036df6af564bcab

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
==827218==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7b8a0bd60ca5 at pc 0x55e5e4c5f82c bp 0x7ffe479e00b0 sp 0x7ffe479e00a8
WRITE of size 1 at 0x7b8a0bd60ca5 thread T0
    #0 0x55e5e4c5f82b in v8::base::GenerateCountedDigits(int, int*, v8::base::Bignum*, v8::base::Bignum*, v8::base::Vector<char>, int*) src/base/numbers/bignum-dtoa.cc:242:15
    #1 0x55e5e4c5f45c in v8::base::BignumDtoa(double, v8::base::BignumDtoaMode, int, v8::base::Vector<char>, int*, int*) src/base/numbers/bignum-dtoa.cc
    #2 0x55e5e4c5b892 in v8::base::DoubleToAscii(double, v8::base::DtoaMode, int, v8::base::Vector<char>, int*, int*, int*) src/base/numbers/dtoa.cc:76:3
    #3 0x55e5e4c48869 in v8::internal::DoubleToPrecisionStringView(double, int, v8::base::Vector<char>) src/numbers/conversions.cc:1182:3
    #4 0x55e5e427745c in v8::internal::Builtin_Impl_NumberPrototypeToPrecision(v8::internal::BuiltinArguments, v8::internal::Isolate*) src/builtins/builtins-number.cc:188:26
    #5 0x55e5e84c7cf5 in Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit setup-isolate-deserialize.cc
    #6 0x55e5e8420c74 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #7 0x55e5e841e75b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #8 0x55e5e841e4aa in Builtins_JSEntry setup-isolate-deserialize.cc
    #9 0x55e5e457269a in Call src/execution/simulator.h:191:12
    #10 0x55e5e457269a in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/execution.cc:437:22
    #11 0x55e5e4574b48 in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:537:10
    #12 0x55e5e4154b5b in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2146:7
    #13 0x55e5e3e0de64 in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1017:44
    #14 0x55e5e3e38576 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:4959:10
    #15 0x55e5e3e43456 in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:5904:37
    #16 0x55e5e3e42b26 in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5812:18
    #17 0x55e5e3e45b3d in v8::Shell::Main(int, char**) src/d8/d8.cc:6680:18
    #18 0x7f8a0db7c1c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #19 0x7f8a0db7c28a in __libc_start_main csu/../csu/libc-start.c:360:3
    #20 0x55e5e3d09029 in _start (/work/v8-build/v8/out/Reproduction/d8+0x10e5029) (BuildId: bd5d3ccb721c4315)

Address 0x7b8a0bd60ca5 is located in stack of thread T0 at offset 165 in frame
    #0 0x55e5e4c4872f in v8::internal::DoubleToPrecisionStringView(double, int, v8::base::Vector<char>) src/numbers/conversions.cc:1163

  This frame has 4 object(s):
    [32, 36) 'decimal_point' (line 1175)
    [48, 52) 'sign' (line 1176)
    [64, 165) 'decimal_rep' (line 1179) <== Memory access at offset 165 overflows this variable
    [208, 212) 'decimal_rep_length' (line 1180)
HINT: this may be a false positive if your program uses some custom stack unwind mechanism, swapcontext or vfork
      (longjmp and C++ exceptions *are* supported)
SUMMARY: AddressSanitizer: stack-buffer-overflow src/base/numbers/bignum-dtoa.cc:242:15 in v8::base::GenerateCountedDigits(int, int*, v8::base::Bignum*, v8::base::Bignum*, v8::base::Vector<char>, int*)
Shadow bytes around the buggy address:
  0x7b8a0bd60a00: f1 f1 f1 f1 f8 f8 f2 f2 00 00 00 00 00 00 00 00
  0x7b8a0bd60a80: 00 00 00 00 00 04 f3 f3 f3 f3 f3 f3 00 00 00 00
  0x7b8a0bd60b00: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7b8a0bd60b80: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7b8a0bd60c00: f1 f1 f1 f1 04 f2 04 f2 00 00 00 00 00 00 00 00
=>0x7b8a0bd60c80: 00 00 00 00[05]f2 f2 f2 f2 f2 04 f3 00 00 00 00
  0x7b8a0bd60d00: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7b8a0bd60d80: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7b8a0bd60e00: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7b8a0bd60e80: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
  0x7b8a0bd60f00: f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5 f5
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
==827218==ABORTING

## V8 sandbox violation detected!

```
