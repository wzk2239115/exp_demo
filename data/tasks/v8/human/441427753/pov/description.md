# 441427753: Debug check failed: isolate()->CurrentLocalHeap()->IsRunning()

## ClusterFuzz Report

```
```
#
# Fatal error in ../../src/heap/heap.cc, line 7095
# Debug check failed: isolate()->CurrentLocalHeap()->IsRunning().
#
#
#
#FailureMessage Object: 0x7b8393119c60
==== C stack trace ===============================

    ../v8/v8/out/x64.build/d8(__interceptor_backtrace+0x46) [0x55665cbdb286]
    /home/user/v8/v8/out/x64.build/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x13) [0x7f83c02460b3]
    /home/user/v8/v8/out/x64.build/libv8_libplatform.so(+0x392ea) [0x7f83c01912ea]
    /home/user/v8/v8/out/x64.build/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x2a0) [0x7f83c020c7f0]
    /home/user/v8/v8/out/x64.build/libv8_libbase.so(+0x5a7ef) [0x7f83c020b7ef]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::Heap::UnregisterStrongRoots(v8::internal::StrongRootsEntry*)+0x14f) [0x7f83c65779cf]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::IdentityMapBase::Clear()+0xac) [0x7f83c822374c]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::IdentityMap<unsigned long*, v8::internal::ZoneAllocationPolicy>::~IdentityMap()+0x2f) [0x7f83c5b5798f]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MaglevCompilationInfo::~MaglevCompilationInfo()+0xb9) [0x7f83c86b74f9]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MaglevCompilationJob::~MaglevCompilationJob()+0x74) [0x7f83c8843a84]
    /home/user/v8/v8/out/x64.build/libv8.so(v8::internal::maglev::MaglevConcurrentDispatcher::JobTask::Run(v8::JobDelegate*)+0xd2e) [0x7f83c884964e]
    /home/user/v8/v8/out/x64.build/libv8_libplatform.so(v8::platform::DefaultJobWorker::Run()+0x2e6) [0x7f83c018e746]
    /home/user/v8/v8/out/x64.build/libv8_libplatform.so(v8::platform::DefaultWorkerThreadsTaskRunner::WorkerThread::Run()+0x1f1) [0x7f83c0195941]
    /home/user/v8/v8/out/x64.build/libv8_libbase.so(+0x91b2e) [0x7f83c0242b2e]
    ../v8/v8/out/x64.build/d8(+0x1999b7) [0x55665cc329b7]
    /lib/x86_64-linux-gnu/libc.so.6(+0x9caa4) [0x7f83be84aaa4]
    /lib/x86_64-linux-gnu/libc.so.6(+0x129c3c) [0x7f83be8d7c3c]
Received signal 6
Aborted
```

#### VERSION

V8 version 14.1.0 (candidate)

#### REPRODUCTION CASE

Build: `python3 tools/dev/gm.py x64.release`

Run: `./d8 poc.js`

---
Reporter credit: Shaheen Fazim
```

## Vulnerability Description

PoC identical in logic to issue 430572435. Creates a large function with 70000 unrolled noop() calls via new Function(), warms it up 2001 times, then on the final call deletes trigger_obj.initial_prop. Triggers a DCHECK or crash in JIT property invalidation in a very large JIT-compiled function.

## Capabilities

Triggers a DCHECK or crash in JIT property invalidation/deoptimization in a very large compiled function. No memory read/write.
