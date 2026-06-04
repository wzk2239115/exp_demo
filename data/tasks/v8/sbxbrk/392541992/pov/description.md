# V8 Sandbox Bypass: UAF in ValueSerializer::WriteRawBytes

#### VULNERABILITY DETAILS
Injecting faults in the `stack` property of a `URIError` object causes a UAF. The root cause seems to be in `ExpandBuffer` at `src/objects/value-serializer.cc:408`. If `base::Realloc` is called with `requested_capacity = 0`, `buffer_` is freed and `new_buffer` is set to null. Since `buffer_` is not updated to reflect that it was freed, it becomes a dangling pointer.
```
Maybe<bool> ValueSerializer::ExpandBuffer(size_t required_capacity) {
  DCHECK_GT(required_capacity, buffer_capacity_);
  size_t requested_capacity =
      std::max(required_capacity, buffer_capacity_ * 2) + 64;
  size_t provided_capacity = 0;
  void* new_buffer = nullptr;
  if (delegate_) {
    new_buffer = delegate_->ReallocateBufferMemory(buffer_, requested_capacity,
                                                   &provided_capacity);
  } else {
    new_buffer = base::Realloc(buffer_, requested_capacity);
    provided_capacity = requested_capacity;
  }
  if (new_buffer) {
    DCHECK(provided_capacity >= requested_capacity);
    buffer_ = reinterpret_cast<uint8_t*>(new_buffer);
    buffer_capacity_ = provided_capacity;
    return Just(true);
  } else {
    out_of_memory_ = true;
    return Nothing<bool>();
  }
}
```

#### VERSION
V8 commit: a4167ecedefcb215facaa9feca98eeb8c225bc15

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
==1391712==ERROR: AddressSanitizer: heap-use-after-free on address 0x7c6ff6ee0496 at pc 0x555557aa756e bp 0x7fffffff7570 sp 0x7fffffff6d30
WRITE of size 1 at 0x7c6ff6ee0496 thread T0
    #0 0x555557aa756d in __asan_memcpy /b/s/w/ir/cache/builder/src/third_party/llvm/compiler-rt/lib/asan/asan_interceptors_memintrinsics.cpp:63:3
    #1 0x55555bd52938 in v8::internal::ValueSerializer::WriteRawBytes(void const*, unsigned long) src/objects/value-serializer.cc:391:5
    #2 0x55555bd79114 in void v8::internal::ValueSerializer::WriteVarint<unsigned char>(unsigned char) src/objects/value-serializer.cc:343:3
    #3 0x55555bd746a8 in v8::internal::ValueSerializer::WriteJSError(v8::internal::DirectHandle<v8::internal::JSObject>) src/objects/value-serializer.cc:1111:3
    #4 0x55555bd5997e in v8::internal::ValueSerializer::WriteJSReceiver(v8::internal::Handle<v8::internal::JSReceiver>) src/objects/value-serializer.cc:646:14
    #5 0x55555bd568ac in v8::internal::ValueSerializer::WriteObject(v8::internal::Handle<v8::internal::Object>) src/objects/value-serializer.cc:509:16
    #6 0x555557f17d15 in v8::ValueSerializer::WriteValue(v8::Local<v8::Context>, v8::Local<v8::Value>) src/api/api.cc:3520:45
    #7 0x555557bf3943 in v8::Shell::SerializerSerialize(v8::FunctionCallbackInfo<v8::Value> const&) src/d8/d8.cc:2718:21
    #8 0x555562233a3f in Builtins_CallApiCallbackGeneric setup-isolate-deserialize.cc
    #9 0x555562231c74 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #10 0x55556222f75b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #11 0x55556222f4aa in Builtins_JSEntry setup-isolate-deserialize.cc
    #12 0x555558e0cda6 in v8::internal::GeneratedCode<unsigned long, unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**>::Call(unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**) src/execution/simulator.h:191:12
    #13 0x555558e02913 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/execution.cc:437:22
    #14 0x555558e03db6 in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:537:10
    #15 0x555557ed96d8 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2147:7
    #16 0x555557ed8426 in v8::Script::Run(v8::Local<v8::Context>) src/api/api.cc:2110:10
    #17 0x555557ba3e5c in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1014:44
    #18 0x555557c32312 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:4956:10
    #19 0x555557c47002 in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:5900:37
    #20 0x555557c459a6 in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5809:18
    #21 0x555557c4be99 in v8::Shell::Main(int, char**) src/d8/d8.cc:6676:18
    #22 0x555557c4d151 in main src/d8/d8.cc:6768:43
    #23 0x7ffff7c911c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #24 0x7ffff7c9128a in __libc_start_main csu/../csu/libc-start.c:360:3
    #25 0x555557a0a029 in _start (/work/v8-build/v8/out/Reproduction/d8+0x24b6029) (BuildId: 45d6774bc6969192)

0x7c6ff6ee0496 is located 22 bytes inside of 65-byte region [0x7c6ff6ee0480,0x7c6ff6ee04c1)
freed by thread T0 here:
    #0 0x555557aa9b0c in realloc /b/s/w/ir/cache/builder/src/third_party/llvm/compiler-rt/lib/asan/asan_malloc_linux.cpp:81:3
    #1 0x555557c9a09c in v8::base::Realloc(void*, unsigned long) src/base/platform/memory.h:56:10
    #2 0x55555bd539fd in v8::internal::ValueSerializer::ExpandBuffer(unsigned long) src/objects/value-serializer.cc:418:18
    #3 0x55555bd533e6 in v8::internal::ValueSerializer::ReserveRawBytes(unsigned long) src/objects/value-serializer.cc:400:10
    #4 0x55555bd527dd in v8::internal::ValueSerializer::WriteRawBytes(void const*, unsigned long) src/objects/value-serializer.cc:390:7
    #5 0x55555bd52dba in v8::internal::ValueSerializer::WriteTwoByteString(v8::base::Vector<unsigned short const>) src/objects/value-serializer.cc:375:3
    #6 0x55555bd5c63a in v8::internal::ValueSerializer::WriteString(v8::internal::Handle<v8::internal::String>) src/objects/value-serializer.cc:569:5
    #7 0x55555bd743d5 in v8::internal::ValueSerializer::WriteJSError(v8::internal::DirectHandle<v8::internal::JSObject>) src/objects/value-serializer.cc:1097:5
    #8 0x55555bd5997e in v8::internal::ValueSerializer::WriteJSReceiver(v8::internal::Handle<v8::internal::JSReceiver>) src/objects/value-serializer.cc:646:14
    #9 0x55555bd568ac in v8::internal::ValueSerializer::WriteObject(v8::internal::Handle<v8::internal::Object>) src/objects/value-serializer.cc:509:16
    #10 0x555557f17d15 in v8::ValueSerializer::WriteValue(v8::Local<v8::Context>, v8::Local<v8::Value>) src/api/api.cc:3520:45
    #11 0x555557bf3943 in v8::Shell::SerializerSerialize(v8::FunctionCallbackInfo<v8::Value> const&) src/d8/d8.cc:2718:21
    #12 0x555562233a3f in Builtins_CallApiCallbackGeneric setup-isolate-deserialize.cc
    #13 0x555562231c74 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #14 0x55556222f75b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #15 0x55556222f4aa in Builtins_JSEntry setup-isolate-deserialize.cc
    #16 0x555558e0cda6 in v8::internal::GeneratedCode<unsigned long, unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**>::Call(unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**) src/execution/simulator.h:191:12
    #17 0x555558e02913 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/execution.cc:437:22
    #18 0x555558e03db6 in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:537:10
    #19 0x555557ed96d8 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2147:7
    #20 0x555557ed8426 in v8::Script::Run(v8::Local<v8::Context>) src/api/api.cc:2110:10
    #21 0x555557ba3e5c in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1014:44
    #22 0x555557c32312 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:4956:10
    #23 0x555557c47002 in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:5900:37
    #24 0x555557c459a6 in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5809:18
    #25 0x555557c4be99 in v8::Shell::Main(int, char**) src/d8/d8.cc:6676:18
    #26 0x555557c4d151 in main src/d8/d8.cc:6768:43
    #27 0x7ffff7c911c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #28 0x7ffff7c9128a in __libc_start_main csu/../csu/libc-start.c:360:3
    #29 0x555557a0a029 in _start (/work/v8-build/v8/out/Reproduction/d8+0x24b6029) (BuildId: 45d6774bc6969192)

previously allocated by thread T0 here:
    #0 0x555557aa9b0c in realloc /b/s/w/ir/cache/builder/src/third_party/llvm/compiler-rt/lib/asan/asan_malloc_linux.cpp:81:3
    #1 0x555557c9a09c in v8::base::Realloc(void*, unsigned long) src/base/platform/memory.h:56:10
    #2 0x55555bd539fd in v8::internal::ValueSerializer::ExpandBuffer(unsigned long) src/objects/value-serializer.cc:418:18
    #3 0x55555bd533e6 in v8::internal::ValueSerializer::ReserveRawBytes(unsigned long) src/objects/value-serializer.cc:400:10
    #4 0x55555bd527dd in v8::internal::ValueSerializer::WriteRawBytes(void const*, unsigned long) src/objects/value-serializer.cc:390:7
    #5 0x55555bd52662 in v8::internal::ValueSerializer::WriteTag(v8::internal::SerializationTag) src/objects/value-serializer.cc:324:3
    #6 0x55555bd5255d in v8::internal::ValueSerializer::WriteHeader() src/objects/value-serializer.cc:314:3
    #7 0x555557f17709 in v8::ValueSerializer::WriteHeader() src/api/api.cc:3509:60
    #8 0x555557bf3491 in v8::Shell::SerializerSerialize(v8::FunctionCallbackInfo<v8::Value> const&) src/d8/d8.cc:2715:14
    #9 0x555562233a3f in Builtins_CallApiCallbackGeneric setup-isolate-deserialize.cc
    #10 0x555562231c74 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #11 0x55556222f75b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #12 0x55556222f4aa in Builtins_JSEntry setup-isolate-deserialize.cc
    #13 0x555558e0cda6 in v8::internal::GeneratedCode<unsigned long, unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**>::Call(unsigned long, unsigned long, unsigned long, unsigned long, long, unsigned long**) src/execution/simulator.h:191:12
    #14 0x555558e02913 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/execution.cc:437:22
    #15 0x555558e03db6 in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:537:10
    #16 0x555557ed96d8 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2147:7
    #17 0x555557ed8426 in v8::Script::Run(v8::Local<v8::Context>) src/api/api.cc:2110:10
    #18 0x555557ba3e5c in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1014:44
    #19 0x555557c32312 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:4956:10
    #20 0x555557c47002 in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:5900:37
    #21 0x555557c459a6 in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5809:18
    #22 0x555557c4be99 in v8::Shell::Main(int, char**) src/d8/d8.cc:6676:18
    #23 0x555557c4d151 in main src/d8/d8.cc:6768:43
    #24 0x7ffff7c911c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #25 0x7ffff7c9128a in __libc_start_main csu/../csu/libc-start.c:360:3
    #26 0x555557a0a029 in _start (/work/v8-build/v8/out/Reproduction/d8+0x24b6029) (BuildId: 45d6774bc6969192)

SUMMARY: AddressSanitizer: heap-use-after-free src/objects/value-serializer.cc:391:5 in v8::internal::ValueSerializer::WriteRawBytes(void const*, unsigned long)
Shadow bytes around the buggy address:
  0x7c6ff6ee0200: 00 00 00 00 00 fa fa fa fa fa 00 00 00 00 00 00
  0x7c6ff6ee0280: 00 00 00 00 fa fa fa fa 00 00 00 00 00 00 00 00
  0x7c6ff6ee0300: 00 00 fa fa fa fa 00 00 00 00 00 00 00 00 00 00
  0x7c6ff6ee0380: fa fa fa fa 00 00 00 00 00 00 00 00 00 fa fa fa
  0x7c6ff6ee0400: fa fa fd fd fd fd fd fd fd fd fd fa fa fa fa fa
=>0x7c6ff6ee0480: fd fd[fd]fd fd fd fd fd fd fa fa fa fa fa fa fa
  0x7c6ff6ee0500: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7c6ff6ee0580: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7c6ff6ee0600: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7c6ff6ee0680: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7c6ff6ee0700: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
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
==1391712==ABORTING

## V8 sandbox violation detected!
```
