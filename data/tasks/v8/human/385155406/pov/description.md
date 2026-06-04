# 385155406: D8 SEGV wild read/write/negative-size-param / Check failed: func_info->parameter_count() == StateValuesAccess(state.parameters()).size() (0 vs. 65536)

## ClusterFuzz Report

```
VULNERABILITY DETAILS
# Fatal error in ../../src/compiler/verifier.cc, line 611
# Check failed: func_info->parameter_count() == StateValuesAccess(state.parameters()).size() (0 vs. 65536). (This is what happens in an ASAN build with dchecks enabled)

==908705==ERROR: UndefinedBehaviorSanitizer: SEGV on unknown address 0x1718ff846454 (pc 0x7ffff7d98ac3 bp 0x7fffffffb480 sp 0x7fffffffb408 T908705)
==908705==The signal is caused by a WRITE memory access. (To me this one looks like a wild write)

==909193==ERROR: AddressSanitizer: negative-size-param: (size=-7171516)
Address 0x7abe00a0b900 is a wild pointer inside of access range of size 0x000000000001.
SUMMARY: AddressSanitizer: negative-size-param src/utils/memcopy.h in MemCopy

==910208==ERROR: AddressSanitizer: SEGV on unknown address 0x00000008e67c (pc 0x7ffff1f77afe bp 0x7fffffffd3f0 sp 0x7fffffffd340 T0)
==910208==The signal is caused by a READ memory access.
SUMMARY: AddressSanitizer: SEGV third_party/libc++/src/include/__atomic/support/c11.h:75:10 in __cxx_atomic_load<int>

VERSION
V8 a770bc7cd104cce1d4ae8f6443d79fb9b3434a91
Operating System: Ubuntu 24.04

BISECT
I stopped bisecting when I got to 6 months old.  Its segfaulting in a release build of d46b1d8f105d674d9bdabff56cb6c3a18bd50095

2024-12-20T11:11:44.222126+00:00 dl360p10fuzz kernel: d8[924282]: segfault at 23e3ffe5e64c ip 00007ffff7d98ac3 sp 00007fffffffc278 error 6 in libc.so.6[7ffff7c28000+188000] likely on CPU 9 (core 10, socket 0)
2024-12-20T11:11:44.222155+00:00 dl360p10fuzz kernel: Code: 66 03 48 83 ee 80 62 e1 fd 28 7f 0f 62 e1 fd 28 7f 57 01 62 e1 fd 28 7f 5f 02 62 e1 fd 28 7f 67 03 48 83 ef 80 48 39 fa 77 bd <62> e1 fe 28 7f 6a 03 62 e1 fe 28 7f 72 02 62 e1 fe 28 7f 7a 01 62

MY ANALYSIS
I think this might be related to https://issues.chromium.org/issues/344664770 however I've ran out of skills trying to get to the bottom of it (surprise surprise).  In my fuzzer build (which is as close as I can get for an instrumented binary to a release build, running in a modified version of fuzzilli) I get what looks like a wild write.  So then I try in an ASAN build and get a 'harmless' Check failed.  If I remove that check from the code (since release builds dont run checks) then ASAN build tends to blow up with wild read or negative size param.  I believe something is going terribly wrong in garbage collection, a lot of the test cases are triggering OOM condition.  Checking with release builds the SEGV looks most like the wild write I am getting in my fuzzilli build.

REPRODUCTION CASE (Attached)
I've got a huge pile of crashers which all appear to be the same issue.  The attached one happens to be one of those fuzzilli testcases that appear to be placed into some kind of larger framework file which I honestly do not understand.  Therefore I've not tried to minimize it yet.  I will add a minimized repro if I can create one that makes sense to me.

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: SEGV read/write / Check Failed

./d8 --expose-gc --expose-externalize-string --omit-quit --allow-natives-syntax --fuzzing --jit-fuzzing --future --harmony --js-staging --wasm-staging --disable-in-process-stack-traces ~/fuzzilli_corpus/crashes/program_20241220024106_E23EB080-4FC2-4AF7-9394-F33E868748A2_flaky.js
[COV] no shared memory bitmap available, skipping
[COV] edge counters initialized. Shared memory: (null) with 878562 edges
UndefinedBehaviorSanitizer:DEADLYSIGNAL
==936268==ERROR: UndefinedBehaviorSanitizer: SEGV on unknown address 0x169aff84594c (pc 0x7ffff7d98ac3 bp 0x7fffffffb550 sp 0x7fffffffb4d8 T936268)
==936268==The signal is caused by a WRITE memory access.
    #0 0x7ffff7d98ac3 in __memcpy_evex_unaligned_erms string/../sysdeps/x86_64/multiarch/memmove-vec-unaligned-erms.S:496
    #1 0x555556e2670e in heap::base::SlotCallbackResult v8::internal::Scavenger::ScavengeObject<v8::internal::CompressedHeapObjectSlot>(v8::internal::CompressedHeapObjectSlot, v8::internal::Tagged<v8::internal::HeapObject>) (/home/alan/v8/v8/out/fuzzilli/d8+0x18d270e) (BuildId: 787711c61a56e1db)
    #2 0x555556dfdc2b in v8::internal::Scavenger::Process(v8::JobDelegate*) (/home/alan/v8/v8/out/fuzzilli/d8+0x18a9c2b) (BuildId: 787711c61a56e1db)
    #3 0x555556def28b in v8::internal::ScavengerCollector::JobTask::ProcessItems(v8::JobDelegate*, v8::internal::Scavenger*) (/home/alan/v8/v8/out/fuzzilli/d8+0x189b28b) (BuildId: 787711c61a56e1db)
    #4 0x555556deeaa9 in v8::internal::ScavengerCollector::JobTask::Run(v8::JobDelegate*) (/home/alan/v8/v8/out/fuzzilli/d8+0x189aaa9) (BuildId: 787711c61a56e1db)
    #5 0x555558e337bd in v8::platform::DefaultJobState::Join() (/home/alan/v8/v8/out/fuzzilli/d8+0x38df7bd) (BuildId: 787711c61a56e1db)
    #6 0x555558e33e4e in v8::platform::DefaultJobHandle::Join() (/home/alan/v8/v8/out/fuzzilli/d8+0x38dfe4e) (BuildId: 787711c61a56e1db)
    #7 0x555556e0217e in v8::internal::ScavengerCollector::CollectGarbage() (/home/alan/v8/v8/out/fuzzilli/d8+0x18ae17e) (BuildId: 787711c61a56e1db)
    #8 0x555556cf647b in v8::internal::Heap::Scavenge() (/home/alan/v8/v8/out/fuzzilli/d8+0x17a247b) (BuildId: 787711c61a56e1db)
    #9 0x555556cf493f in v8::internal::Heap::PerformGarbageCollection(v8::internal::GarbageCollector, v8::internal::GarbageCollectionReason, char const*) (/home/alan/v8/v8/out/fuzzilli/d8+0x17a093f) (BuildId: 787711c61a56e1db)
    #10 0x555556d1bf68 in v8::internal::Heap::CollectGarbage(v8::internal::AllocationSpace, v8::internal::GarbageCollectionReason, v8::GCCallbackFlags)::$_1::operator()() const heap.cc
    #11 0x555556d1b995 in void heap::base::Stack::SetMarkerAndCallbackImpl<v8::internal::Heap::CollectGarbage(v8::internal::AllocationSpace, v8::internal::GarbageCollectionReason, v8::GCCallbackFlags)::$_1>(heap::base::Stack*, void*, void const*) heap.cc
    #12 0x555557ce51a6 in PushAllRegistersAndIterateStack push_registers_asm.cc

==936268==Register values:
rax = 0x0000169b000aca18  rbx = 0x0000555559b51f90  rcx = 0x0000169b000aca18  rdx = 0x0000169aff8458ec  
rdi = 0x0000169b000acaa0  rsi = 0x0000169b00913b38  rbp = 0x00007fffffffb550  rsp = 0x00007fffffffb4d8  
 r8 = 0x0000169b000aca18   r9 = 0x0000000000000030  r10 = 0x0000000000000001  r11 = 0x00000000013c0000  
r12 = 0x0000169b00913aad  r13 = 0x00000000ff798f58  r14 = 0x0000000000000565  r15 = 0x0000169b00000565  
UndefinedBehaviorSanitizer can not provide additional info.
SUMMARY: UndefinedBehaviorSanitizer: SEGV string/../sysdeps/x86_64/multiarch/memmove-vec-unaligned-erms.S:496 in __memcpy_evex_unaligned_erms
==936268==ABORTING

RANDOM ADENDUM
To create my release mode binaries I ran what looked to be a helpful script: tools/dev/gm.py x64.release.  Glancing through the script it didnt look like it was going to break my v8 tree but after running it; all my other builds in ./out are 'cleaned' - eg wiped out.  This has really thrown a spanner in trying to complete this report.  Hopefully if I erase my v8 directory and check out a new copy this weirdness goes away but this is super frustrating +++ because its not clear from reading the script that its gonna do this and it doesnt anywhere mention running it could cause data loss in your output folder.

CREDIT INFORMATION
Externally reported security bugs may appear in Chrome release notes. If this bug is included, how would you like to be credited?
Reporter credit: Alan Goodman
```

## Vulnerability Description

Original flaky Fuzzilli Probe output for the JIT bug involving spreading a very long array into Function.prototype.bind. Creates array v0=['1'], sets length to 65521, calls f13.bind(null, ...v0, ..."setUint32", 1). The resulting bound function is optimized via %PrepareFunctionForOptimization and %OptimizeFunctionOnNextCall. Intermittently produces a controlled OOB read.

## Capabilities

Intermittently produces a controlled OOB read (SIGSEGV at 0x48) during TurboFan optimization of a function with a very long bound-argument list. No controlled write.
