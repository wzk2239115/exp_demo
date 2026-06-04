# 401732698: V8 sandbox violation in v8

## ClusterFuzz Report

```
## VULNERABILITY DETAILS

### CRASH LOG

```bash
$ /path/to/v8/v8/out/fuzzbuild-sandbox/d8  --sandbox-fuzzing ./poc.js 
Sandbox testing mode is enabled. Only sandbox violations will be reported, all other crashes will be ignored.
# Ignoring debug check failure in .....
# Ignoring debug check failure in .....
# Ignoring debug check failure in .....

## V8 sandbox violation detected!

Received signal 11 SEGV_MAPERR 08464d000848

==== C stack trace ===============================

/path/to/v8/v8/out/fuzzbuild-sandbox/d8(+0xaabe66)[0x55b346715e66]
/lib/x86_64-linux-gnu/libc.so.6(+0x42520)[0x7f8bbee42520]
/path/to/v8/v8/out/fuzzbuild-sandbox/d8(+0x2157e9b)[0x55b347dc1e9b]
/path/to/v8/v8/out/fuzzbuild-sandbox/d8(+0x21523d7)[0x55b347dbc3d7]
/path/to/v8/v8/out/fuzzbuild-sandbox/d8(+0x2146b1a)[0x55b347db0b1a]
/path/to/v8/v8/out/fuzzbuild-sandbox/d8(+0x21444ed)[0x55b347dae4ed]
/path/to/v8/v8/out/fuzzbuild-sandbox/d8(+0x2140ed0)[0x55b347daaed0]
/path/to/v8/v8/out/fuzzbuild-sandbox/d8(+0x2140dae)[0x55b347daadae]
/path/to/v8/v8/out/fuzzbuild-sandbox/d8(+0x260dfe9)[0x55b348277fe9]
/path/to/v8/v8/out/fuzzbuild-sandbox/d8(+0x260d742)[0x55b348277742]
/path/to/v8/v8/out/fuzzbuild-sandbox/d8(+0x55b84bd)[0x55b34b2224bd]
[end of stack trace]
[1]    3821081 segmentation fault  /path/to/v8/v8/out/fuzzbuild-sandbox/d8 --sandbox-fuzzing ./poc.js
```

### REPRODUCTION CASE

- build

```bash
# Mar 8 2025 
git checkout fec6c4c97ac26259c4633142dd6423de1592fbf0
gn gen ./out/sbx --args='v8_enable_partition_alloc=false treat_warnings_as_errors=false is_debug=false dcheck_always_on=true v8_static_library=true v8_enable_slow_dchecks=true v8_enable_v8_checks=true v8_enable_verify_heap=true v8_enable_verify_csa=true v8_enable_verify_predictable=true target_cpu="x64" v8_enable_sandbox=true v8_enable_memory_corruption_api=true'
ninja -C ./out/sbx d8
```

- trigger

```bash
./out/sbx/d8  --sandbox-fuzzing ./poc.js 
```


## FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

## CREDIT INFORMATION
Reporter credit: Zhenghang Xiao (@Kipreyyy) and Nan Wang (@eternalsakura13)
```

## Vulnerability Description

63598023_poc.js: Uses Sandbox.MemoryView to replace object v0's Map pointer with the tagged pointer to RangeError constructor, then calls Object.getOwnPropertyNames(v0) which invokes CollectKeysFromDictionary with the wrong Map type, triggering a crash. Uses --sandbox-fuzzing flag. 63598027_CollectKeysFromDictionary-disasm.asm: x86-64 disassembly of CollectKeysFromDictionary<NameDictionary> from a fuzzbuild binary. 63598931_CollectKeysFromDictionary-decompile.cpp: Decompiled C++ pseudocode of the same function. Both asm and cpp files are analysis artifacts identifying the vulnerable code path.

## Capabilities

Crashes in CollectKeysFromDictionary when passed an object with a mismatched Map type. No controlled arbitrary write.
