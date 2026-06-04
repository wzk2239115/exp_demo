# V8 Sandbox Bypass: OOB write in JsonStringifier::TrySerializeSimplePropertyKey

#### VULNERABILITY DETAILS
During the serialization of an internalized string, an out-of-bounds write may occur due to an integer overflow in the buffer length check.

```c++
template <typename DestChar>
bool JsonStringifier::TrySerializeSimplePropertyKey(
    Tagged<String> key, const DisallowGarbageCollection& no_gc) {
  ReadOnlyRoots roots(isolate_);
  if (key->map() != roots.internalized_one_byte_string_map()) {
    return false;
  }
  if (!key_cache_.Contains(key)) {
    return false;
  }
  uint32_t length = key->length();  <---- length is read here from the heap. In the POC,
                                    <---- this is set to 0xfffffffd
  uint32_t copy_length = length;
  if constexpr (sizeof(DestChar) == 1) {
    // CopyChars has fast paths for small integer lengths, and is generally a
    // little faster if we round the length up to the nearest 4. This is still
    // within the bounds of the object on the heap, because object alignment is
    // never less than 4 for any build configuration.
    constexpr int kRounding = 4;
    static_assert(kRounding <= kObjectAlignment);
    copy_length = RoundUp(length, kRounding);
  }
  // Add three for the quote marks and colon, to determine how much output space
  // is needed. We might actually require a little less output space than this,
  // depending on how much rounding happened above, but it's more important to
  // compute the requirement quickly than to be precise.
  uint32_t required_length = copy_length + 3; <---- 0xfffffffd + 0x3 = 0
  if (!CurrentPartCanFit(required_length)) {  <---- check will pass
    return false;
  }
  NoExtendBuilder<DestChar> no_extend(
      reinterpret_cast<DestChar*>(part_ptr_) + current_index_, &current_index_);
  no_extend.Append('"');
  base::Vector<const uint8_t> chars(
      Cast<SeqOneByteString>(key)->GetChars(no_gc), copy_length); <------- copy_length is 0xfffffffd, causing OOB writes below
  DCHECK_LE(reinterpret_cast<Address>(chars.end()),
            key.address() + key->Size());
#if DEBUG
  for (uint32_t i = 0; i < length; ++i) {
    DCHECK(DoNotEscape(chars[i]));
  }
#endif  // DEBUG
  no_extend.AppendChars(chars, length);
  no_extend.Append('"');
  no_extend.Append(':');
  return true;
}
```



#### VERSION
V8 commit: 19d1cde7ffe6c6e5c6908496f5b575407c9b49e5

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
## V8 sandbox violation detected!

AddressSanitizer:DEADLYSIGNAL
=================================================================
==4076225==ERROR: AddressSanitizer: SEGV on unknown address 0x7f2a93c01472 (pc 0x556690d6b738 bp 0x7ffdaf21e9d0 sp 0x7ffdaf21e980 T0)
==4076225==The signal is caused by a WRITE memory access.
    #0 0x556690d6b738 in bool v8::internal::JsonStringifier::TrySerializeSimplePropertyKey<unsigned char>(v8::internal::Tagged<v8::internal::String>, v8::internal::PerThreadAssertScopeEmpty<false, (v8::internal::PerThreadAssertType)1, (v8::internal::PerThreadAssertType)2> const&) src/json/json-stringifier.cc:282:54
    #1 0x556690d57dd4 in v8::internal::JsonStringifier::Result v8::internal::JsonStringifier::Serialize_<true>(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, bool, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:1672:15
    #2 0x556690d491ba in v8::internal::JsonStringifier::Result v8::internal::JsonStringifier::Serialize_<false>(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, bool, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:76:12
    #3 0x556690d42c64 in v8::internal::JsonStringifier::Result v8::internal::JsonStringifier::Serialize_<false>(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, bool, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:66:12
    #4 0x556690d19c80 in v8::internal::JsonStringifier::Stringify(v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:59:12
    #5 0x556690d37cd9 in v8::internal::JsonStringify(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Handle<v8::internal::Union<v8::internal::Smi, v8::internal::HeapNumber, v8::internal::BigInt, v8::internal::String, v8::internal::Symbol, v8::internal::Boolean, v8::internal::Null, v8::internal::Undefined, v8::internal::JSReceiver>>, v8::internal::Handle<v8::internal::Object>) src/json/json-stringifier.cc:3179:24
    #6 0x55668fe0149a in v8::internal::Builtin_Impl_JsonStringify(v8::internal::BuiltinArguments, v8::internal::Isolate*) src/builtins/builtins-json.cc:37:3
    #7 0x556696cdd475 in Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit setup-isolate-deserialize.cc
    #8 0x556696c25922 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #9 0x556696c2305b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #10 0x556696c22daa in Builtins_JSEntry setup-isolate-deserialize.cc
    #11 0x5566902f87d9 in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/simulator.h:191:12
    #12 0x5566902fb1ca in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:537:10
    #13 0x55668fbfbd55 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:2030:7
    #14 0x55668f6eed24 in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1026:44
    #15 0x55668f733c86 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:5016:10
    #16 0x55668f74539c in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:5970:37
    #17 0x55668f7447e7 in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:5878:18
    #18 0x55668f74921d in v8::Shell::Main(int, char**) src/d8/d8.cc:6779:18
    #19 0x7f29955781c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16

==4076225==Register values:
rax = 0x0000000000000000  rbx = 0x00007f2993c01310  rcx = 0x0000000000036b1a  rdx = 0x000055668ed718a8
rdi = 0x00007f2a93c01473  rsi = 0x00007f2993c01310  rbp = 0x00007ffdaf21e9d0  rsp = 0x00007ffdaf21e980
 r8 = 0x00000000fffffffd   r9 = 0x0000015993c01310  r10 = 0x000000000000000c  r11 = 0x0000000000004000
r12 = 0x00007f2993c01474  r13 = 0x00007dd000000000  r14 = 0x00007f2a93c01472  r15 = 0x00007f2993c01475
AddressSanitizer can not provide additional info.
SUMMARY: AddressSanitizer: SEGV src/json/json-stringifier.cc:282:54 in bool v8::internal::JsonStringifier::TrySerializeSimplePropertyKey<unsigned char>(v8::internal::Tagged<v8::internal::String>, v8::internal::PerThreadAssertScopeEmpty<false, (v8::internal::PerThreadAssertType)1, (v8::internal::PerThreadAssertType)2> const&)
==4076225==ABORTING
```
