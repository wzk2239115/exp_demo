# V8 Sandbox Bypass: UAF during LargeObjectSpace tear down

#### VERSION
V8 commit: 9a9a2b2d796da6e8b4ae1bb294aff41294b882fc

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
==1515577==ERROR: AddressSanitizer: heap-use-after-free on address 0x7dff2a8ef228 at pc 0x560b63b47ea5 bp 0x7fff5d8ee640 sp 0x7fff5d8ee638
READ of size 8 at 0x7dff2a8ef228 thread T0
    #0 0x560b63b47ea4 in get third_party/libc++/src/include/__memory/unique_ptr.h:268:94
    #1 0x560b63b47ea4 in IsLargePage src/heap/mutable-page-metadata.h:281:33
    #2 0x560b63b47ea4 in v8::internal::MemoryAllocator::DeleteMemoryChunk(v8::internal::MutablePageMetadata*) src/heap/memory-allocator.cc:663:17
    #3 0x560b63b8fadc in v8::internal::PagePool::ReleaseOnTearDown(v8::internal::Isolate*) src/heap/page-pool.cc:72:11
    #4 0x560b639a7149 in v8::internal::Heap::TearDown() src/heap/heap.cc:6223:31
    #5 0x560b637dfcc6 in v8::internal::Isolate::Deinit() src/execution/isolate.cc:4547:9
    #6 0x560b637deed0 in v8::internal::Isolate::Delete(v8::internal::Isolate*) src/execution/isolate.cc:4137:12
    #7 0x560b62f9d93e in v8::Shell::OnExit(v8::Isolate*, bool) src/d8/d8.cc:4471:14
    #8 0x560b62fb529c in v8::Shell::Main(int, char**) src/d8/d8.cc:6874:3
    #9 0x7faf2b6a61c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #10 0x7faf2b6a628a in __libc_start_main csu/../csu/libc-start.c:360:3
    #11 0x560b62e74029 in _start (/work/v8-build/v8/out/Reproduction/d8+0x1143029) (BuildId: 47bbc0a8c91a8f29)

0x7dff2a8ef228 is located 296 bytes inside of 8528-byte region [0x7dff2a8ef100,0x7dff2a8f1250)
freed by thread T0 here:
    #0 0x560b62f4e89d in operator delete(void*) /b/s/w/ir/cache/builder/src/third_party/llvm/compiler-rt/lib/asan/asan_new_delete.cpp:143:3
    #1 0x560b63a53015 in v8::internal::LargeObjectSpace::TearDown() src/heap/large-spaces.cc:73:33
    #2 0x560b63a56823 in v8::internal::LargeObjectSpace::~LargeObjectSpace() src/heap/large-spaces.h:38:34
    #3 0x560b63a5679d in v8::internal::OldLargeObjectSpace::~OldLargeObjectSpace() src/heap/large-spaces.h:144:7
    #4 0x560b639a6f70 in operator() third_party/libc++/src/include/__memory/unique_ptr.h:76:5
    #5 0x560b639a6f70 in reset third_party/libc++/src/include/__memory/unique_ptr.h:287:7
    #6 0x560b639a6f70 in v8::internal::Heap::TearDown() src/heap/heap.cc:6218:15
    #7 0x560b637dfcc6 in v8::internal::Isolate::Deinit() src/execution/isolate.cc:4547:9
    #8 0x560b637deed0 in v8::internal::Isolate::Delete(v8::internal::Isolate*) src/execution/isolate.cc:4137:12
    #9 0x560b62f9d93e in v8::Shell::OnExit(v8::Isolate*, bool) src/d8/d8.cc:4471:14
    #10 0x560b62fb529c in v8::Shell::Main(int, char**) src/d8/d8.cc:6874:3
    #11 0x7faf2b6a61c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #12 0x7faf2b6a628a in __libc_start_main csu/../csu/libc-start.c:360:3
    #13 0x560b62e74029 in _start (/work/v8-build/v8/out/Reproduction/d8+0x1143029) (BuildId: 47bbc0a8c91a8f29)

previously allocated by thread T0 here:
    #0 0x560b62f4e03d in operator new(unsigned long) /b/s/w/ir/cache/builder/src/third_party/llvm/compiler-rt/lib/asan/asan_new_delete.cpp:86:3
    #1 0x560b63b4873d in v8::internal::MemoryAllocator::AllocatePage(v8::internal::MemoryAllocator::AllocationMode, v8::internal::Space*, v8::internal::Executability) src/heap/memory-allocator.cc:393:16
    #2 0x560b63b993a6 in v8::internal::PagedSpaceBase::TryExpand(v8::internal::LocalHeap*, v8::internal::AllocationOrigin) src/heap/paged-spaces.cc:305:52
    #3 0x560b63a61edf in v8::internal::PagedSpaceAllocatorPolicy::TryExpandAndAllocate(unsigned long, v8::internal::AllocationOrigin) src/heap/main-allocator.cc:775:18
    #4 0x560b63a6138c in v8::internal::PagedSpaceAllocatorPolicy::RefillLab(int, v8::internal::AllocationOrigin) src/heap/main-allocator.cc:748:9
    #5 0x560b63a5ce9f in v8::internal::MainAllocator::EnsureAllocation(int, v8::internal::AllocationAlignment, v8::internal::AllocationOrigin) src/heap/main-allocator.cc:333:29
    #6 0x560b63a5c9a1 in v8::internal::MainAllocator::AllocateRawSlowUnaligned(int, v8::internal::AllocationOrigin) src/heap/main-allocator.cc:212:8
    #7 0x560b64a4a06a in AllocateRaw src/heap/main-allocator-inl.h:39:31
    #8 0x560b64a4a06a in AllocateRaw<(v8::internal::AllocationType)1> src/heap/heap-allocator-inl.h:130:35
    #9 0x560b64a4a06a in AllocateRawWith<(v8::internal::HeapAllocator::AllocationRetryMode)1> src/heap/heap-allocator-inl.h:227:14
    #10 0x560b64a4a06a in v8::internal::Heap::AllocateRawOrFail(int, v8::internal::AllocationType, v8::internal::AllocationOrigin, v8::internal::AllocationAlignment) src/heap/heap-inl.h:204:9
    #11 0x560b64a43460 in Allocate src/snapshot/deserializer.cc:1665:50
    #12 0x560b64a43460 in v8::internal::Deserializer<v8::internal::Isolate>::ReadObject(v8::internal::SnapshotSpace) src/snapshot/deserializer.cc:800:7
    #13 0x560b64a5c4ce in int v8::internal::Deserializer<v8::internal::Isolate>::ReadNewObject<v8::internal::SlotAccessorForRootSlots>(unsigned char, v8::internal::SlotAccessorForRootSlots) src/snapshot/deserializer.cc:1098:42
    #14 0x560b64a4502e in ReadData src/snapshot/deserializer.cc:975:16
    #15 0x560b64a4502e in v8::internal::Deserializer<v8::internal::Isolate>::VisitRootPointers(v8::internal::Root, char const*, v8::internal::FullObjectSlot, v8::internal::FullObjectSlot) src/snapshot/deserializer.cc:381:3
    #16 0x560b6399dc1e in v8::internal::Heap::IterateRoots(v8::internal::RootVisitor*, v8::base::EnumSet<v8::internal::SkipRoot, int>, v8::internal::Heap::IterateRootsMode) src/heap/heap.cc:4675:6
    #17 0x560b64ac7ef3 in v8::internal::StartupDeserializer::DeserializeIntoIsolate() src/snapshot/startup-deserializer.cc:42:24
    #18 0x560b637ed8f8 in v8::internal::Isolate::Init(v8::internal::SnapshotData*, v8::internal::SnapshotData*, v8::internal::SnapshotData*, bool) src/execution/isolate.cc:5791:26
    #19 0x560b637ef698 in v8::internal::Isolate::InitWithSnapshot(v8::internal::SnapshotData*, v8::internal::SnapshotData*, v8::internal::SnapshotData*, bool) src/execution/isolate.cc:5245:10
    #20 0x560b64a8e187 in v8::internal::Snapshot::Initialize(v8::internal::Isolate*) src/snapshot/snapshot.cc:198:19
    #21 0x560b6339f9b5 in v8::Isolate::Initialize(v8::Isolate*, v8::Isolate::CreateParams const&) src/api/api.cc:10088:8
    #22 0x560b6339ff84 in New src/api/api.cc:10127:3
    #23 0x560b6339ff84 in v8::Isolate::New(v8::Isolate::CreateParams const&) src/api/api.cc:10121:10
    #24 0x560b62fb465b in v8::Shell::Main(int, char**) src/d8/d8.cc:6684:22
    #25 0x7faf2b6a61c9 in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    #26 0x7faf2b6a628a in __libc_start_main csu/../csu/libc-start.c:360:3
    #27 0x560b62e74029 in _start (/work/v8-build/v8/out/Reproduction/d8+0x1143029) (BuildId: 47bbc0a8c91a8f29)

SUMMARY: AddressSanitizer: heap-use-after-free third_party/libc++/src/include/__memory/unique_ptr.h:268:94 in get
Shadow bytes around the buggy address:
  0x7dff2a8eef80: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7dff2a8ef000: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7dff2a8ef080: fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa fa
  0x7dff2a8ef100: fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd
  0x7dff2a8ef180: fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd
=>0x7dff2a8ef200: fd fd fd fd fd[fd]fd fd fd fd fd fd fd fd fd fd
  0x7dff2a8ef280: fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd
  0x7dff2a8ef300: fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd
  0x7dff2a8ef380: fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd
  0x7dff2a8ef400: fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd
  0x7dff2a8ef480: fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd fd
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
==1515577==ABORTING

## V8 sandbox violation detected!

```
