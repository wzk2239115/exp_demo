# V8 sandbox violation due to concurrent ArrayBuffer modifications during std::sort

#### VULNERABILITY DETAILS
Changing the element type of an array before it is sorted may cause an out-of-bound write. I suspect this to be a double fetch bug since it required a background worker to be triggered.

**Please note that this causes an OOB read before it causes an OOB write. Please reach out if you need the LLVM patches I used to disable the instrumentation of reads.**

#### VERSION
V8 commit: 4715559d4fe2ce6e2c0f6de3c966347b6da6a489

#### REPRODUCTION CASE
The test case is mostly one shot but sometimes requires multiple runs.

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
Sandbox testing mode is enabled. Only sandbox violations will be reported, all other crashes will be ignored.
Sandbox.base: 0x7ea100000000
ar: 0x4a540
ar map: 0x1848ed
bit_field2_addr: 0x1848f7
bit_field2_addr value: 0x5d
=================================================================
==683885==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x7fffbefff880 at pc 0x5555580788be bp 0x7fffffffd610 sp 0x7fffffffd608
WRITE of size 8 at 0x7fffbefff880 thread T0
    #0 0x5555580788bd in void v8::base::WriteUnalignedValue<double>(unsigned long, double) src/base/memory.h:43:3
    #1 0x5555580788bd in v8::internal::UnalignedSlot<double>::Reference::operator=(v8::internal::UnalignedSlot<double>::Reference const&) src/objects/slots.h:240:7
    #2 0x5555580788bd in void std::__Cr::__sift_down<std::__Cr::_ClassicAlgPolicy, bool (*&)(double, double), v8::internal::UnalignedSlot<double>>(v8::internal::UnalignedSlot<double>, bool (*&)(double, double), std::__Cr::iterator_traits<v8::internal::UnalignedSlot<double>>::difference_type, v8::internal::UnalignedSlot<double>) third_party/libc++/src/include/__algorithm/sift_down.h:61:14
    #3 0x5555580780b0 in void std::__Cr::__make_heap<std::__Cr::_ClassicAlgPolicy, bool (*&)(double, double), v8::internal::UnalignedSlot<double>>(v8::internal::UnalignedSlot<double>, v8::internal::UnalignedSlot<double>, bool (*&)(double, double)) third_party/libc++/src/include/__algorithm/make_heap.h:39:7
    #4 0x5555580780b0 in v8::internal::UnalignedSlot<double> std::__Cr::__partial_sort_impl<std::__Cr::_ClassicAlgPolicy, bool (*&)(double, double), v8::internal::UnalignedSlot<double>, v8::internal::UnalignedSlot<double>>(v8::internal::UnalignedSlot<double>, v8::internal::UnalignedSlot<double>, v8::internal::UnalignedSlot<double>, bool (*&)(double, double)) third_party/libc++/src/include/__algorithm/partial_sort.h:41:3
    #5 0x555558075971 in v8::internal::UnalignedSlot<double> std::__Cr::__partial_sort<std::__Cr::_ClassicAlgPolicy, bool (*&)(double, double), v8::internal::UnalignedSlot<double>, v8::internal::UnalignedSlot<double>>(v8::internal::UnalignedSlot<double>, v8::internal::UnalignedSlot<double>, v8::internal::UnalignedSlot<double>, bool (*&)(double, double)) third_party/libc++/src/include/__algorithm/partial_sort.h:65:7
    #6 0x555558075971 in void std::__Cr::__introsort<std::__Cr::_ClassicAlgPolicy, bool (*&)(double, double), v8::internal::UnalignedSlot<double>, false>(v8::internal::UnalignedSlot<double>, v8::internal::UnalignedSlot<double>, bool (*&)(double, double), std::__Cr::iterator_traits<v8::internal::UnalignedSlot<double>>::difference_type, bool) third_party/libc++/src/include/__algorithm/sort.h:767:7
    #7 0x55555805b67b in void std::__Cr::__sort_dispatch<std::__Cr::_ClassicAlgPolicy, v8::internal::UnalignedSlot<double>, bool (*)(double, double)>(v8::internal::UnalignedSlot<double>, v8::internal::UnalignedSlot<double>, bool (*&)(double, double)) third_party/libc++/src/include/__algorithm/sort.h:888:3
    #8 0x55555805b67b in void std::__Cr::__sort_impl<std::__Cr::_ClassicAlgPolicy, v8::internal::UnalignedSlot<double>, bool (*)(double, double)>(v8::internal::UnalignedSlot<double>, v8::internal::UnalignedSlot<double>, bool (*&)(double, double)) third_party/libc++/src/include/__algorithm/sort.h:953:5
    #9 0x55555805b67b in void std::__Cr::sort<v8::internal::UnalignedSlot<double>, bool (*)(double, double)>(v8::internal::UnalignedSlot<double>, v8::internal::UnalignedSlot<double>, bool (*)(double, double)) third_party/libc++/src/include/__algorithm/sort.h:961:3
    #10 0x55555805b67b in v8::internal::__RT_impl_Runtime_TypedArraySortFast(v8::internal::Arguments<(v8::internal::ArgumentsType)0>, v8::internal::Isolate*) src/runtime/runtime-typedarray.cc:185:5
    #11 0x55555805b67b in v8::internal::Runtime_TypedArraySortFast(int, unsigned long*, v8::internal::Isolate*) src/runtime/runtime-typedarray.cc:110:1
    #12 0x55555afea375 in Builtins_CEntry_Return1_ArgvOnStack_NoBuiltinExit setup-isolate-deserialize.cc
    #13 0x55555b0b3409 in Builtins_TypedArrayPrototypeSort setup-isolate-deserialize.cc
    #14 0x55555af3ea80 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #15 0x55555af3c69b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #16 0x55555af3c3ea in Builtins_JSEntry setup-isolate-deserialize.cc
    #17 0x555556e0b572 in v8::internal::GeneratedCode<unsigned long, unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**>::Call(unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**) src/execution/simulator.h:191:12
    #18 0x555556e0b572 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/execution.cc:436:22
    #19 0x555556e0d44c in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:536:10
    #20 0x5555569b79e5 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2155:7
    #21 0x555556774dba in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1013:44
    #22 0x5555567ac9c8 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:4942:10
    #23 0x5555567b934e in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:5886:37
    #24 0x5555567b87dd in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5795:18
    #25 0x5555567bd25c in v8::Shell::Main(int, char**) src/d8/d8.cc:6649:18
    #26 0x7fffbfb911c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #27 0x7fffbfb9128a in __libc_start_main csu/../csu/libc-start.c:360:3
    #28 0x555556613029 in _start (/work/v8-build/v8/out/ReproductionSuppressReads/d8+0x10bf029) (BuildId: 313280bf0dd9443d)

0x7fffbefff880 is located 128 bytes after 524288-byte region [0x7fffbef7f800,0x7fffbefff800)
allocated by thread T0 here:
    #0 0x55555673ef08 in operator new(unsigned long) /work/llvm-project/compiler-rt/lib/asan/asan_new_delete.cpp:86:3
    #1 0x55555805ffff in void* std::__Cr::__libcpp_operator_new<unsigned long>(unsigned long) third_party/libc++/src/include/__new/allocate.h:35:10
    #2 0x55555805ffff in std::__Cr::__libcpp_allocate(unsigned long, unsigned long) third_party/libc++/src/include/__new/allocate.h:59:10
    #3 0x55555805ffff in std::__Cr::allocator<unsigned char>::allocate(unsigned long) third_party/libc++/src/include/__memory/allocator.h:105:32
    #4 0x55555805ffff in std::__Cr::__allocation_result<std::__Cr::allocator_traits<std::__Cr::allocator<unsigned char>>::pointer> std::__Cr::__allocate_at_least<std::__Cr::allocator<unsigned char>>(std::__Cr::allocator<unsigned char>&, unsigned long) third_party/libc++/src/include/__memory/allocate_at_least.h:41:19
    #5 0x55555805ffff in std::__Cr::__split_buffer<unsigned char, std::__Cr::allocator<unsigned char>&>::__split_buffer(unsigned long, unsigned long, std::__Cr::allocator<unsigned char>&) third_party/libc++/src/include/__split_buffer:325:25
    #6 0x55555805ffff in std::__Cr::vector<unsigned char, std::__Cr::allocator<unsigned char>>::__append(unsigned long) third_party/libc++/src/include/__vector/vector.h:921:49
    #7 0x55555805a40f in std::__Cr::vector<unsigned char, std::__Cr::allocator<unsigned char>>::resize(unsigned long) third_party/libc++/src/include/__vector/vector.h:1316:11
    #8 0x55555805a40f in v8::internal::__RT_impl_Runtime_TypedArraySortFast(v8::internal::Arguments<(v8::internal::ArgumentsType)0>, v8::internal::Isolate*) src/runtime/runtime-typedarray.cc:149:20
    #9 0x55555805a40f in v8::internal::Runtime_TypedArraySortFast(int, unsigned long*, v8::internal::Isolate*) src/runtime/runtime-typedarray.cc:110:1
    #10 0x55555afea375 in Builtins_CEntry_Return1_ArgvOnStack_NoBuiltinExit setup-isolate-deserialize.cc
    #11 0x55555b0b3409 in Builtins_TypedArrayPrototypeSort setup-isolate-deserialize.cc
    #12 0x55555af3ea80 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #13 0x55555af3c69b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #14 0x55555af3c3ea in Builtins_JSEntry setup-isolate-deserialize.cc
    #15 0x555556e0b572 in v8::internal::GeneratedCode<unsigned long, unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**>::Call(unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**) src/execution/simulator.h:191:12
    #16 0x555556e0b572 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/execution.cc:436:22
    #17 0x555556e0d44c in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:536:10
    #18 0x5555569b79e5 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2155:7
    #19 0x555556774dba in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1013:44
    #20 0x5555567ac9c8 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:4942:10
    #21 0x5555567b934e in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:5886:37
    #22 0x5555567b87dd in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5795:18
    #23 0x5555567bd25c in v8::Shell::Main(int, char**) src/d8/d8.cc:6649:18
    #24 0x7fffbfb911c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #25 0x7fffbfb9128a in __libc_start_main csu/../csu/libc-start.c:360:3
    #26 0x555556613029 in _start (/work/v8-build/v8/out/ReproductionSuppressReads/d8+0x10bf029) (BuildId: 313280bf0dd9443d)

SUMMARY: AddressSanitizer: heap-buffer-overflow src/base/memory.h:43:3 in void v8::base::WriteUnalignedValue<double>(unsigned long, double)
Shadow bytes around the buggy address:
  0x7fffbefff600: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  0x7fffbefff680: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  0x7fffbefff700: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  0x7fffbefff780: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  0x7fffbefff800: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
=>0x7fffbefff880:[fa]fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7fffbefff900: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7fffbefff980: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7fffbefffa00: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7fffbefffa80: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7fffbefffb00: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
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
==683885==ABORTING
```
