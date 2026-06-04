# 359729268: Signal SIGSEGV in v

## ClusterFuzz Report

```
VULNERABILITY DETAILS
## INTRODUCE
After bisect, it was determined that following commit caused this problem.

- Commit Info
    - Version: 95402
    - link: https://crrev.com/17d7d98b92926852a3e3ba90aba17b80ef869512 
- Commit Message

```
commit 17d7d98b92926852a3e3ba90aba17b80ef869512
Author: Hao Xu <hao.a.xu@intel.com>
Date:   Fri Jul 19 16:54:03 2024 +0800

    Reland "Support GetEnumeratedKeyedProperty bytecode in Maglev/Turbofan"
    
    This is a reland of commit 19cf1a317f65f0b94eba7082400cfd2608e0df29
    
    We should reset current_for_in_state.enum_cache_indices on resumable
    loop headers. Because it is not stored in any local register, we will
    lose this value in the loop body.
    
    Original change's description:
    > Support GetEnumeratedKeyedProperty bytecode in Maglev/Turbofan
    >
    > Bug: v8:14245
    > Change-Id: I1e84623b45969b9efee02e5469b7a3ecf747972a
    > Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/5634288
    > Reviewed-by: Leszek Swirski <leszeks@chromium.org>
    > Commit-Queue: Hao A Xu <hao.a.xu@intel.com>
    > Cr-Commit-Position: refs/heads/main@{#94956}
    
    Bug: v8:14245
    Change-Id: Iaf98f657056d925367b11bc53be249f7eadff31a
    Reviewed-on: https://chromium-review.googlesource.com/c/v8/v8/+/5723307
    Commit-Queue: Hao A Xu <hao.a.xu@intel.com>
    Reviewed-by: Leszek Swirski <leszeks@chromium.org>
    Cr-Commit-Position: refs/heads/main@{#95402}

```

## CRASH LOG
- Debug output

```bash
# CMD: /tmp/d8-linux-debug-v8-component-95637/d8 --allow-natives-syntax --fuzzing --always-turbofan poc.js
# OUTPUT ==============================================================
Received signal 11 SEGV_MAPERR ffffffffffffffff

```

## Other
Please note to include the flags `--allow-natives-syntax --fuzzing --always-turbofan` for clusterfuzz classification.

VERSION
Tested on v8 version: 12.9.0 - 12.9.0

REPRODUCTION CASE
1. Download debug v8 from: gs://v8-asan/linux-debug/d8-linux-debug-v8-component-95637.zip
2. Run: `d8 --allow-natives-syntax --fuzzing --always-turbofan poc.js`

FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: tab

CREDIT INFORMATION
Reporter credit: Zhenghang Xiao (@Kipreyyy)
```

## Vulnerability Description

Short TurboFan optimization PoC. Defines func(args) which iterates object properties with for-in and inside the loop accesses i[arg] where i is the numeric loop counter (0 or 1). Uses %PrepareFunctionForOptimization and then calls func twice with {x:20,y:11} before running under --always-turbofan. The JIT attempts to optimize i[arg] treating i as a number, which may trigger a DCHECK in property load elimination or type narrowing.

## Capabilities

Crashes with a DCHECK or assertion in TurboFan's type system. No memory read/write.
