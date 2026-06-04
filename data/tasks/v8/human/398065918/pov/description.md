# 398065918: V8 Maglev improper folded allocation handling (leading to memory safety issues)

## ClusterFuzz Report

```
VULNERABILITY DETAILS

### Intro
The vulnerability uses two V8 concepts:
- Folded allocation - is an optimization where multiple allocation operations are combined into a single allocation.
- Memory is divided into two main regions Young Generation (Young Space) and Old Generation (Old Space). When an object in the Young Space survives multiple garbage collections, it is promoted or reallocated to the Old Space. One of the moment when GC is called is during `Builtins_AllocateInYoungGeneration`, which is called when need to allocate more memory.

The issue gets triggered when reallocation is performed in the middle of folded allocation. 

### The bug
Let's consider a simplified code

```js
function triggerFunction(...a) {
    ...
}
function __f_0() {
    ...
    triggerFunction(v, pi, r);
    ...
}
```

When Maglev creates folded allocation and GC/reallocation is performed in the middle of such allocation, the variable "V" will be overlapped by array "A".

The process looks as follow:
1. Allocate memory for "V" and create "V"
2. Allocate memory for both "PI" and "A" (folded allocation) and create "PI". 
3. Allocate memory for "R" and create "R". As not enough memory in current block - extend it. During extention the garbage collection and reallocation (from Young to Old space) is done.
4. Reallocate "PI" from Young to Old space. Reallocate "V" from Young to Old space. "V" is put right after "PI".
5. Create array "A". As space after "PI" is reserved for "A" (in step 2) it is put right after "PI". But variable "V" now uses this space (becuase of step 4). "V" is overwritten by "A".

So, the "PI" is reallocated to the new place. The "V" varialbe is also, and it got placed right after "PI". However, due to the folded allocation, the place after "PI" is reserved for "A".

Variable "V" before overwritten by array "A"
```
0x33920064002d: [HeapNumber]
 - map: 0x339200000515 <Map[12](HEAP_NUMBER_TYPE)>
 - value: 1073751774.0
```

Variable "V" after overwritten by array "A"
```
0x33920064002d: [FixedArray]
 - map: 0x339200000565 <Map(FIXED_ARRAY_TYPE)>
 - length: 10
           0: 0x33920064002d <FixedArray[10]>
           1: 0x339200640021 <HeapNumber 3.14159>
           2: 0x339200000011 <undefined>
           3: 0x3392006400ad <HeapNumber 107375179900.0>
           4: 0x339200000011 <undefined>
           5: 0x339200640011 <Number map = 0x339200509f0d value = 0>
         6-9: 0x339200000011 <undefined>
```

### Restrictions/requirements for triggering the bug
Small modification in script result in triggering GC/reallocation in other functions, breaking the process. To trigger the issue this is a must:
- Folded allocation of "PI" and "A" (we always have it with our code)
- The quota to reallocate from Young to Old space for both "V" and "PI" should be reached right before step 3 (sensitive to side-effects)
- Should not be enough space to allocate new variable "R" at step 3, so `Builtins_AllocateInYoungGeneration` would be called and trigger reallocation (sensitive to side-effects)

To accommodate the different memory layouts (between various source commits, different run flags, build arguments), we had to introduce additional allocations by adding stub variable declarations. We've made a script `search_allocations.py` to do this automatically.

### How it probably should work
Non-vulnerable, intended behavior probably is one of the following:
- Reallocator should be aware of folded allocation and keep track reserved memory
- Reallocation shouldn't happen in the middle of folded allocation (between step 2 and 5). All objects from folded allocation should be created before reallocation. Currently, "A" is created after reallocation.

### Root cause
Rest arguments create such sequence "V", "PI", "R", "A", where "PI" and "A" are folded-allocated.

### Proof of concept
#### PoC 1
Branch: main, commit: `f30c2930794e1347a85909c0272964692e4311f6`

args.gn (release build)
```
is_component_build = false
is_debug = false
target_cpu = "x64"
v8_enable_sandbox = true
v8_enable_backtrace = true
v8_enable_disassembler = true
v8_enable_object_print = true
v8_enable_verify_heap = true
dcheck_always_on = false
```

Command: `d8 --allow-natives-syntax --no-js-atomics-pause --no-script-context-mutable-heap-number --predictable --wasm-staging --isolate poc1.js`

Error:
```
Stacktrace:
    ptr1=0x9b1001c002d
    ptr2=(nil)
    ptr3=(nil)
    ptr4=(nil)
    ptr5=(nil)
    ptr6=(nil)
    failure_message_object=0x75c7c3df7130

==== JS stack trace =========================================

    0: ExitFrame [pc: 0x5f92730281b6]
    1: StubFrame [pc: 0x5f927307ce95]
    2: StubFrame [pc: 0x5f9273070a45]
    3: toString [0x9b1003431d1](this=10000000,0x09b1001c002d <FixedArray[10]>,0x09b1001c0021 <HeapNumber 3.14159>,0x09b100000011 <undefined>,0x09b1001c00ad <HeapNumber 78383880524.0>,0x09b100000011 <undefined>,0x09b1001c0011 <Number map = 0x9b10034308d value = 0>,0x09b100000011 <undefined>,0x09b100000011 <undefined>,0x09b100000011 <undefined>,0x09b100000011 <undefined>)
    4: __f_0 [0x9b10035bc81] [poc1.js:~170] [pc=0x5f92d2f4a95e](this=0x09b100341a85 <JSGlobalProxy>)
    5: __f_1 [0x9b10035bcb5] [poc1.js:190] [bytecode=0x31a0018013d offset=40](this=0x09b100341a85 <JSGlobalProxy>)
    6: /* anonymous */ [0x9b10035b3a1] [poc1.js:193] [bytecode=0x31a001800d1 offset=43](this=0x09b100341a85 <JSGlobalProxy>)
    7: InternalFrame [pc: 0x5f9272f7e71c]
    8: EntryFrame [pc: 0x5f9272f7e46b]

==== Details ================================================

[0]: ExitFrame [pc: 0x5f92730281b6]
[1]: StubFrame [pc: 0x5f927307ce95]
[2]: StubFrame [pc: 0x5f9273070a45]
[3]: toString [0x9b1003431d1](this=10000000,0x09b1001c002d <FixedArray[10]>,0x09b1001c0021 <HeapNumber 3.14159>,0x09b100000011 <undefined>,0x09b1001c00ad <HeapNumber 78383880524.0>,0x09b100000011 <undefined>,0x09b1001c0011 <Number map = 0x9b10034308d value = 0>,0x09b100000011 <undefined>,0x09b100000011 <undefined>,0x09b100000011 <undefined>,0x09b100000011 <undefined>) {
// optimized frame
--------- s o u r c e   c o d e ---------
<No Source>
-----------------------------------------
}
[4]: __f_0 [0x9b10035bc81] [poc1.js:~170] [pc=0x5f92d2f4a95e](this=0x09b100341a85 <JSGlobalProxy>) {
// optimized frame
--------- s o u r c e   c o d e ---------
function __f_0() {\x0a  let __v_2 = __v_1;\x0a\x0a  for (var i = 0; i < 100; i++) { \x0a    --__v_1;\x0a    __v_2 += __v_1;\x0a    console.log(i);\x0a    console.log(__v_1);\x0a    triggerFunction(10000000, 456109613, __v_1,   Math.PI, __getRandomObject(5161),__v_2, __getRandomObject(639756),new Number(), undefined,undefined, undefined,...

-----------------------------------------
}
[5]: __f_1 [0x9b10035bcb5] [poc1.js:190] [bytecode=0x31a0018013d offset=40](this=0x09b100341a85 <JSGlobalProxy>) {
  // expression stack (top to bottom)
  [01] : 0x09b100341a85 <JSGlobalProxy>
  [00] : 0x09b10035bc81 <JSFunction __f_0 (sfi = 0x9b10035b259)>
--------- s o u r c e   c o d e ---------
function __f_1() {\x0a  %PrepareFunctionForOptimization(__f_0);  \x0a  __f_0();\x0a  %OptimizeMaglevOnNextCall(__f_0);\x0a  __v_1 = 1073751824;\x0a  __f_0();\x0a}
-----------------------------------------
}

[6]: /* anonymous */ [0x9b10035b3a1] [poc1.js:193] [bytecode=0x31a001800d1 offset=43](this=0x09b100341a85 <JSGlobalProxy>) {
  // heap-allocated locals
  var __v_1 = 0x09b10035eb35 <FixedArray[1]>
  // expression stack (top to bottom)
  [04] : 0x09b100341a85 <JSGlobalProxy>
  [03] : 0x09b10035d63d <Object map = 0x9b10034281d>
  [02] : 0x09b10035d659 <Object map = 0x9b10034281d>
  [01] : 0x09b10035bcb5 <JSFunction __f_1 (sfi = 0x9b10035b289)>
  [00] : 0x09b100000011 <undefined>
--------- s o u r c e   c o d e ---------
var my_simple_var_0;\x0avar my_simple_var_1;\x0avar my_simple_var_2;\x0avar my_simple_var_3;\x0avar my_simple_var_4;\x0avar my_simple_var_5;\x0avar my_simple_var_6;\x0avar my_simple_var_7;\x0avar my_simple_var_8;\x0avar my_simple_var_9;\x0avar my_simple_var_10;\x0avar my_simple_var_11;\x0avar my_simple_var_12;\x0avar my_simple_var_13;\x0ava...

-----------------------------------------
}

[7]: InternalFrame [pc: 0x5f9272f7e71c]
[8]: EntryFrame [pc: 0x5f9272f7e46b]
=====================

Trace/breakpoint trap (core dumped)
```

The crash itself happens in `toString` (`NumberPrototypeToString` in `number.tq`), where the first argument is considered as radix. But as number value is overlapped by array the crash will happen during the convertion.

#### PoC 2
Branch: main, commit: `f30c2930794e1347a85909c0272964692e4311f6`

args.gn (build with dchecks)
```
symbol_level = 2
is_debug = false
v8_optimized_debug = false
dcheck_always_on = true
v8_win64_unwinding_info = true
v8_enable_verify_csa = true
v8_enable_object_print = true
v8_enable_maglev_graph_printer = true
v8_enable_disassembler = true
v8_enable_slow_dchecks = true
v8_enable_verify_heap = true
v8_enable_sandbox = true

target_cpu = "x64"
v8_enable_backtrace = true
v8_enable_gdbjit = true
```

Command: `d8 --allow-natives-syntax --no-js-atomics-pause --no-script-context-mutable-heap-number --predictable --wasm-staging --isolate poc2.js`

Error:
```
#
# Fatal error in ../../src/objects/object-type.cc, line 82
# Type cast failed in CAST(LoadFromObject(machine_type, object, raw_offset)) at ../../src/codegen/code-stub-assembler.h:1166
  Expected Map but found Smi: 0x2a22168c (706877068)

#
#
#
#FailureMessage Object: 0x7ce5a47fee00Trace/breakpoint trap (core dumped)
```

Here we trigger a crash in different place, which may be more useful for the exploitation.

#### PoC 3
Issue is also present in older versions. This is the earliest commit for which we made a PoC, but the issue may have existed even earlier.

Branch: main, commit: `4bfcab00943b1e35f4fb2326aafea5a64752f75e`

args.gn (release)
```
is_component_build = false
is_debug = false
target_cpu = "x64"
v8_enable_sandbox = true

v8_enable_backtrace = true
v8_enable_disassembler = true
v8_enable_object_print = true
v8_enable_verify_heap = true
dcheck_always_on = false
```

Command: `d8 --allow-natives-syntax --predictable --isolate poc3.js`

Error:
```
Stacktrace:
    ptr1=0x9b0001c002d
    ptr2=(nil)
    ptr3=(nil)
    ptr4=(nil)
    ptr5=(nil)
    ptr6=(nil)
    failure_message_object=0x7d52007f7150

==== JS stack trace =========================================

    0: ExitFrame [pc: 0x6452ba4f81b6]
    1: StubFrame [pc: 0x6452ba54cf94]
    2: StubFrame [pc: 0x6452ba5410c5]
    3: toString [0x9b000349b09](this=10000000,0x09b0001c002d <FixedArray[10]>,0x09b0001c0021 <HeapNumber 3.14159>,0x09b000000069 <undefined>,0x09b0001c00ad <HeapNumber 13958773634.0>,0x09b000000069 <undefined>,0x09b0001c0011 <Number map = 0x9b0003499c5 value = 0>,0x09b000000069 <undefined>,0x09b000000069 <undefined>,0x09b000000069 <undefined>,0x09b000000069 <undefined>)
    4: __f_0 [0x9b00035c99d] [../../poc3_4bfcab00943b1e35f4fb2326aafea5a64752f75e.js:~360] [pc=0x6452e000a190](this=0x09b0003416c9 <JSGlobalProxy>)
    5: __f_1 [0x9b00035c9d1] [../../poc3_4bfcab00943b1e35f4fb2326aafea5a64752f75e.js:380] [bytecode=0x31a000800b5 offset=40](this=0x09b0003416c9 <JSGlobalProxy>)
    6: /* anonymous */ [0x9b00035b209] [../../poc3_4bfcab00943b1e35f4fb2326aafea5a64752f75e.js:383] [bytecode=0x31a00080035 offset=61](this=0x09b0003416c9 <JSGlobalProxy>)
    7: InternalFrame [pc: 0x6452ba45671c]
    8: EntryFrame [pc: 0x6452ba45645f]

==== Details ================================================

[0]: ExitFrame [pc: 0x6452ba4f81b6]
[1]: StubFrame [pc: 0x6452ba54cf94]
[2]: StubFrame [pc: 0x6452ba5410c5]
[3]: toString [0x9b000349b09](this=10000000,0x09b0001c002d <FixedArray[10]>,0x09b0001c0021 <HeapNumber 3.14159>,0x09b000000069 <undefined>,0x09b0001c00ad <HeapNumber 13958773634.0>,0x09b000000069 <undefined>,0x09b0001c0011 <Number map = 0x9b0003499c5 value = 0>,0x09b000000069 <undefined>,0x09b000000069 <undefined>,0x09b000000069 <undefined>,0x09b000000069 <undefined>) {
// optimized frame
--------- s o u r c e   c o d e ---------
<No Source>
-----------------------------------------
}
[4]: __f_0 [0x9b00035c99d] [../../poc3_4bfcab00943b1e35f4fb2326aafea5a64752f75e.js:~360] [pc=0x6452e000a190](this=0x09b0003416c9 <JSGlobalProxy>) {
// optimized frame
--------- s o u r c e   c o d e ---------
function __f_0() {\x0a  let __v_2 = __v_1;\x0a\x0a  for (var i = 0; i < 100; i++) { \x0a    --__v_1;\x0a    __v_2 += __v_1;\x0a    console.log(i);\x0a    console.log(__v_1);\x0a    triggerFunction(10000000, 456109613, __v_1,   Math.PI, __getRandomObject(5161),__v_2, __getRandomObject(639756),new Number(), undefined,undefined, undefined,...

-----------------------------------------
}
[5]: __f_1 [0x9b00035c9d1] [../../poc3_4bfcab00943b1e35f4fb2326aafea5a64752f75e.js:380] [bytecode=0x31a000800b5 offset=40](this=0x09b0003416c9 <JSGlobalProxy>) {
  // expression stack (top to bottom)
  [01] : 0x09b0003416c9 <JSGlobalProxy>
  [00] : 0x09b00035c99d <JSFunction __f_0 (sfi = 0x9b00035b0a9)>
--------- s o u r c e   c o d e ---------
function __f_1() {\x0a  %PrepareFunctionForOptimization(__f_0);  \x0a  __f_0();\x0a  %OptimizeMaglevOnNextCall(__f_0);\x0a  __v_1 = 1073751824;\x0a  __f_0();\x0a}
-----------------------------------------
}

[6]: /* anonymous */ [0x9b00035b209] [../../poc3_4bfcab00943b1e35f4fb2326aafea5a64752f75e.js:383] [bytecode=0x31a00080035 offset=61](this=0x09b0003416c9 <JSGlobalProxy>) {
  // heap-allocated locals
  var __v_1 = 0x09b000360995 <FixedArray[1]>
  // expression stack (top to bottom)
  [04] : 0x09b0003416c9 <JSGlobalProxy>
  [03] : 0x09b00035e391 <Object map = 0x9b000342445>
  [02] : 0x09b00035e3ad <Object map = 0x9b000342445>
  [01] : 0x09b00035c9d1 <JSFunction __f_1 (sfi = 0x9b00035b0e9)>
  [00] : 0x09b000000069 <undefined>
--------- s o u r c e   c o d e ---------
var my_simple_var_0;\x0avar my_simple_var_1;\x0avar my_simple_var_2;\x0avar my_simple_var_3;\x0avar my_simple_var_4;\x0avar my_simple_var_5;\x0avar my_simple_var_6;\x0avar my_simple_var_7;\x0avar my_simple_var_8;\x0avar my_simple_var_9;\x0avar my_simple_var_10;\x0avar my_simple_var_11;\x0avar my_simple_var_12;\x0avar my_simple_var_13;\x0ava...

-----------------------------------------
}

[7]: InternalFrame [pc: 0x6452ba45671c]
[8]: EntryFrame [pc: 0x6452ba45645f]
=====================

Trace/breakpoint trap (core dumped)
```

### Fix
The fix should reset/split folded allocation done in rest arguments.

```patch
diff --git a/src/maglev/maglev-graph-builder.cc b/src/maglev/maglev-graph-builder.cc
index 7c7c1c36c95..b36b64df4eb 100644
--- a/src/maglev/maglev-graph-builder.cc
+++ b/src/maglev/maglev-graph-builder.cc
@@ -12900,6 +12900,7 @@ ValueNode* MaglevGraphBuilder::BuildInlinedAllocation(
       SmallZoneVector<ValueNode*, 8> values(zone());
       vobject->ForEachDeoptInputLocation(
           [&](ValueNode* node, ValueNode*& input) {
+            ClearCurrentAllocationBlock();
             if (node->Is<VirtualObject>()) {
               VirtualObject* nested = node->Cast<VirtualObject>();
               node = BuildInlinedAllocation(nested, allocation_type);
```

### Reproduction
See the attached files and the "Restrictions/requirements for triggering the bug" section

### CREDIT INFORMATION
Externally reported security bugs may appear in Chrome release notes. If this bug is included, how would you like to be credited?
Reporter credit: Excello s.r.o.
```

## Vulnerability Description

Maglev optimization PoC variant 2. Same structure as poc1 — loop decrementing a large integer with Maglev optimization trigger. Variation in variable counts or loop structure compared to poc1.

## Capabilities

Crashes with a DCHECK or SIGSEGV in Maglev's integer arithmetic optimization. No memory read/write.
