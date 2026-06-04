# 390639820: V8 Sandbox Bypass: Control flow hijack via Torque function type corruption

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

#### Summary

V8 sandbox bypass, control flow hijack (arbitrary call) by corrupting in-sandbox Torque function types. These are conceptually equivalent to `smi`s representing its index within the builtins table used in a completely unguarded manner, which results in arbitrary builtins call as well as fully arbitrary call when using an out-of-bounds index to dereference function pointers within a controlled heap spray region.


#### Details

`Array.prototype.sort()` uses `SortState` to represent the current sorting state. Interestingly, it includes several function types used for comparison, load, store, delete and accessor check:
```torque
// https://source.chromium.org/chromium/chromium/src/+/main:v8/third_party/v8/builtins/array-sort.tq;drc=c87310a1337d106d75500a8c9793a54ba4daa69a;l=17
class SortState extends HeapObject {
  // ...
  // Function pointer to the comparison function. This can either be a builtin
  // that calls the user-provided comparison function or "SortDefault", which
  // uses ToString and a lexicographical compare.
  sortComparePtr: CompareBuiltinFn;

  // The following four function pointer represent an Accessor/Path.
  // These are used to Load/Store/Delete elements and to check whether
  // to bail to the baseline GenericElementsAccessor.
  loadFn: LoadFn;
  storeFn: StoreFn;
  deleteFn: DeleteFn;
  canUseSameAccessorFn: CanUseSameAccessorFn;
  // ...
}

// https://source.chromium.org/chromium/chromium/src/+/main:v8/third_party/v8/builtins/array-sort.tq;drc=c87310a1337d106d75500a8c9793a54ba4daa69a;l=235
type LoadFn = builtin(Context, SortState, Smi) => (JSAny|TheHole);
type StoreFn = builtin(Context, SortState, Smi, JSAny) => Smi;
type DeleteFn = builtin(Context, SortState, Smi) => Smi;
type CanUseSameAccessorFn = builtin(Context, JSReceiver, Map, Number) =>
    Boolean;
type CompareBuiltinFn = builtin(Context, JSAny, JSAny, JSAny) => Number;
```

This is in fact represented as an `smi`:
```torque
// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/builtins/base.tq;drc=c87310a1337d106d75500a8c9793a54ba4daa69a;l=294
type BuiltinPtr extends Smi generates 'TNode<BuiltinPtr>';
```

Torque code that fetches and calls such function is transpiled into CSA code using `{Load,Store}Reference<BuiltinPtr>`, which will emit a memory indirect call dereferencing the target builtin function pointer using the given `smi` index. Below is an example of such call in `Builtins_ArrayTimSort()`:
```
0x55555ba77602 <Builtins_ArrayTimSort+1026>    mov    r8d, dword ptr [rdi + r8*4 + 7]
0x55555ba77607 <Builtins_ArrayTimSort+1031>    add    r8, r14
0x55555ba7760a <Builtins_ArrayTimSort+1034>    mov    r11d, dword ptr [rax + 0x13]      ; rax = SortArray object, r11 = sortComparePtr
0x55555ba7760e <Builtins_ArrayTimSort+1038>    mov    r12d, dword ptr [rax + 0xf]
0x55555ba77612 <Builtins_ArrayTimSort+1042>    add    r12, r14
0x55555ba77615 <Builtins_ArrayTimSort+1045>    mov    qword ptr [rbp - 0x10], rcx
0x55555ba77619 <Builtins_ArrayTimSort+1049>    mov    qword ptr [rbp - 0x30], rdi
0x55555ba7761d <Builtins_ArrayTimSort+1053>    mov    qword ptr [rbp - 0x48], r9
0x55555ba77621 <Builtins_ArrayTimSort+1057>    mov    rax, r12
0x55555ba77624 <Builtins_ArrayTimSort+1060>    mov    rbx, r9
0x55555ba77627 <Builtins_ArrayTimSort+1063>    mov    rcx, r8
0x55555ba7762a <Builtins_ArrayTimSort+1066>    call   qword ptr [r13 + r11*4 + 0x51e8]  ; r13+0x51e8 = builtins table
```

We see that there are no checks whatsoever on what the index can be. This results in arbitrary (incompatible) builtin function calls, and even a complete control flow hijack by calling out-of-bounds index pointing to attacker-controlled heap spray.

The attached exploit works as follows:
1. Spray `TARGET` address to call on the native heap using Wasm
2. Create an object with a getter defined on index 0 in which we:
   1. Search the sandbox region for the constructed `SortState` object
   2. Corrupt `sortComparePtr` index to point to heap spray
3. Call `Array.prototype.sort()` on the object
   1. Index 0 getter called, `sortComparePtr` corrupted
   2. Comparator called to compare values at index 0 and 1, resulting in control flow hijack to `TARGET`

> The bypass does not fundamentally require Wasm. In the repro, Wasm is used simply as a means of heap spraying on the native heap - any other sprayable allocations on the native heap suffices.


### VERSION

V8: Tested on CF **no-asan** sandbox-testing d8 @ revision 98142 (commit [3ea3463](https://chromium-review.googlesource.com/c/v8/v8/+/6175894)) & custom **no-asan** Chrome build with sandbox testing enabled


### REPRODUCTION CASE

Attached as `array-sort-sortstate-corruption.js`, run with `./d8 --sandbox-testing` **on a no-asan build.**

The repro attempts a control flow hijack to address `0x42424242c0d3`.

> This bypass grants equivalent ~ stronger primitive than arbitrary writes, as this allows an attacker to immediately execute arbitrary code by e.g. running `Array.prototype.sort()` within a normal Wasm function as an imported function with stack sprayed with nop-sledded ropchain, triggered by calling into pivot gadget `add rsp, X; ...; ret`.

#### Triaging

For ClusterFuzz triage, I recommend the `linux_d8_sandbox_testing` job type.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Sandbox violation


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n) of CMU CyLab

-----

This was discovered during a test run of a WIP v8 sandbox fuzzer.  
Marking any potential VRP reward for this bug in advance to be processed for charity.
```

## Vulnerability Description

Full sandbox escape exploit leveraging Array.prototype.sort's SortState object. Sprays 128MB of Wasm modules (each containing target address 0x42424242c0d3 repeated at 8-byte intervals) to fill trusted heap space. Creates an object with getter-trapped indexed properties. When Array.prototype.sort.apply(obj) is called, the getter for [0] uses Sandbox.MemoryView to find the SortState by its map (0x1a8d) and overwrites SortState.sort_compare_ptr (offset 0x14) with a spray index pointing to 0x42424242c0d3. The sort's compare call then transfers execution to that address. Getters return controlled Smi values (0x13370000 >> 1 and 0x14470000 >> 1) for in-sandbox registers.

## Capabilities

Arbitrary call to attacker-controlled address 0x42424242c0d3 via SortState sort_compare_ptr corruption. Controlled register values at the call site. Requires --sandbox-testing and Sandbox.* API.
