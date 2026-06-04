# 434513380: Missing Write Barrier via Math.sqrt in Maglev

## ClusterFuzz Report

```
This vulnerability in the V8 engine's Maglev optimization layer occurs when a Smi is converted to a HeapNumber via Math.sqrt(0) after a major GC cycle. In this case, the write barrier—a mechanism that informs the garbage collector about changes to heap object references—fails to trigger due to a bug in the optimized Maglev path. The write barrier is critical for generational and incremental garbage collection in V8, as it records cross-generational references and prevents the creation of dangling pointers. While a write barrier is not needed for Smi values, after conversion to a HeapNumber, skipping the barrier leaves the garbage collector unaware of the new reference. This result a classic use-after-free vulnerability.

Attached files:
- poc.js: contains a minimal proof-of-concept which exploits this bug to create a dangling pointer, resulting in a crash. This POC has been reproduced with an D8 debug build (commit f83f5f03864363683eacfb374da9de287a624913) on an x86-64 Linux machine.
```
#
# Fatal error in ../../src/runtime/runtime-test.cc, line 2324
# Check failed: !WriteBarrier::IsRequired(heap_object, value).
#
#
```
- oob-read.js: Contains a script that allows reading data from the heap. This has been reproduced on a release build (non-debug) in the same environment.
```
oobArray:
0x3c4200080045 <JSObject>
[+] oobArray[100]:  981467136
```

This vulnerability was introduced in:
https://chromium.googlesource.com/v8/v8/+/30f71750eac22aa5a941b719a81874c0720a2256

A sample patch of such a fix could look as follows:
```
diff --git a/src/maglev/maglev-ir.h b/src/maglev/maglev-ir.h
index 6635b0a6369..86dc124040e 100644
--- a/src/maglev/maglev-ir.h
+++ b/src/maglev/maglev-ir.h
@@ -3951,7 +3951,7 @@ class Float64Sqrt : public FixedInputValueNodeT<1, Float64Sqrt> {
  public:
   explicit Float64Sqrt(uint64_t bitfield) : Base(bitfield) {}
 
-  static constexpr OpProperties kProperties = OpProperties::HoleyFloat64();
+  static constexpr OpProperties kProperties = OpProperties::Float64();
   static constexpr
       typename Base::InputTypes kInputTypes{ValueRepresentation::kHoleyFloat64};
```

CREDIT INFORMATION

Reporter credit: Pavel Kuzmin of Yandex Security Team
```

## Vulnerability Description

Initial PoC stage for the Maglev/GC interaction bug. Defines f1 that triggers a major GC then assigns v0 = Math.sqrt(0). After %OptimizeMaglevOnNextCall(f1), f1() is called again. Maglev incorrectly handles the GC interaction, causing v0 to become a type-confused array-like object. Demonstrates the type confusion exists.

## Capabilities

Type confusion: after Maglev-optimized f1 + GC, v0 is incorrectly treated as a holey double array. Demonstrates the confusion but does not access out-of-bounds memory.
