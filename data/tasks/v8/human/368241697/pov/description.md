# 368241697: Type confusion due to improper WASM module size check in `AsyncStreamingDecoder`

## ClusterFuzz Report

```
### VULNERABILITY DETAILS

#### Summary

Type confusion due to WASM streaming decoder size overflow with overly large modules. `AsyncStreamingDecoder` does not properly check maximum module size, resulting in offset truncation into 30 bits for `ConstantExpression::kWireBytesRef` constant expressions. This eventually results in a primitive to confuse `undefined` as any WASM (reference) type, resulting in type confusion (and an instant arbitrary caged RW).


#### Details

WASM modules must hold an invariant that its size is less than `kV8MaxWasmModuleSize = 1024 * 1024 * 1024 (1 GiB)`:

```cpp
// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/wasm-limits.h;drc=f84fb630ee9aa58f7493db195d3ab6e0b254425e;l=49
constexpr size_t kV8MaxWasmModuleSize = 1024 * 1024 * 1024;  // = 1 GiB
```

However, `AsyncStreamingDecoder` only checks this limit on each section sizes and not the whole module:

```cpp
// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/streaming-decoder.cc;l=465
class AsyncStreamingDecoder::DecodeSectionLength : public DecodeVarInt32 {
 public:
  explicit DecodeSectionLength(uint8_t id, uint32_t module_offset)
      : DecodeVarInt32(max_module_size(), "section length"),    // [!] checks each section size, not the whole module
        section_id_(id),
        module_offset_(module_offset) {}

  std::unique_ptr<DecodingState> NextWithValue(
      AsyncStreamingDecoder* streaming) override;

 private:
  const uint8_t section_id_;
  // The start offset of this section in the module.
  const uint32_t module_offset_;
};
```

This allows a module to grow over 1 GiB, which results in offset truncation in `ConstantExpression::kWireBytesRef` constant expressions:

```cpp
// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/constant-expression.h;drc=247e36d85da39a66a1f68b46ef4aebf7dfdfdb03;l=31
// A representation of a constant expression. The most common expression types
// are hard-coded, while the rest are represented as a {WireBytesRef}.
class ConstantExpression {
 public:
  // ...
  static constexpr ConstantExpression WireBytes(uint32_t offset,
                                                uint32_t length) {
    return ConstantExpression(OffsetField::encode(offset) |
                              LengthField::encode(length) |
                              KindField::encode(kWireBytesRef));
  }
  // ...
  V8_EXPORT_PRIVATE WireBytesRef wire_bytes_ref() const;

 private:
  static constexpr int kValueBits = 32;
  static constexpr int kLengthBits = 30;   // [!] length limited to 30 bits (under 1 GiB)
  static constexpr int kOffsetBits = 30;
  static constexpr int kKindBits = 3;

  // There are two possible combinations of fields: offset + length + kind if
  // kind = kWireBytesRef, or value + kind for anything else.
  using ValueField = base::BitField<uint32_t, 0, kValueBits, uint64_t>;
  using OffsetField = base::BitField<uint32_t, 0, kOffsetBits, uint64_t>;
  using LengthField = OffsetField::Next<uint32_t, kLengthBits>;
  using KindField = LengthField::Next<Kind, kKindBits>;

  // ...
  uint64_t bit_field_ = 0;
};

// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/constant-expression.cc;drc=8cab41c0837d9b869abdb0e5ca6a929b302f0d6a;l=23
WireBytesRef ConstantExpression::wire_bytes_ref() const {
  DCHECK_EQ(kind(), kWireBytesRef);
  return WireBytesRef(OffsetField::decode(bit_field_),
                      LengthField::decode(bit_field_));
}
```

With a constant expression located in an offset over 1 GiB, `ConstantExpression::wire_bytes_ref()` uses a truncated offset to fetch the `WireBytesRef`. This function is notably used in `EvaluateConstantExpression()`:

```cpp
// https://source.chromium.org/chromium/chromium/src/+/main:v8/src/wasm/constant-expression.cc;drc=8cab41c0837d9b869abdb0e5ca6a929b302f0d6a;l=29
ValueOrError EvaluateConstantExpression(
    Zone* zone, ConstantExpression expr, ValueType expected, Isolate* isolate,
    Handle<WasmTrustedInstanceData> trusted_instance_data,
    Handle<WasmTrustedInstanceData> shared_trusted_instance_data) {
  switch (expr.kind()) {
    // ...
    case ConstantExpression::kWireBytesRef: {
      WireBytesRef ref = expr.wire_bytes_ref();

      base::Vector<const uint8_t> module_bytes =
          trusted_instance_data->native_module()->wire_bytes();

      const uint8_t* start = module_bytes.begin() + ref.offset();
      const uint8_t* end = module_bytes.begin() + ref.end_offset();

      auto sig = FixedSizeSignature<ValueType>::Returns(expected);
      // We have already validated the expression, so we might as well
      // revalidate it as non-shared, which is strictly more permissive.
      // TODO(14616): Rethink this.
      constexpr bool kIsShared = false;
      FunctionBody body(&sig, ref.offset(), start, end, kIsShared);
      WasmDetectedFeatures detected;
      const WasmModule* module = trusted_instance_data->module();
      ValueOrError result;
      {
        // We need a scope for the decoder because its destructor resets some
        // Zone elements, which has to be done before we reset the Zone
        // afterwards.
        // We use FullValidationTag so we do not have to create another template
        // instance of WasmFullDecoder, which would cost us >50Kb binary code
        // size.
        WasmFullDecoder<Decoder::FullValidationTag, ConstantExpressionInterface,
                        kConstantExpression>
            decoder(zone, module, WasmEnabledFeatures::All(), &detected, body,
                    module, isolate, trusted_instance_data,
                    shared_trusted_instance_data);

        decoder.DecodeFunctionBody();

        result = decoder.interface().has_error()
                     ? ValueOrError(decoder.interface().error())
                     : ValueOrError(decoder.interface().computed_value());
      }

      zone->Reset();

      return result;
    }
  }
}
```

This function is called on every cases that require constant expression evaluation (global init, data/table segment offset, element segment entry, etc). Unfortunately, `WasmFullDecoder<Decoder::FullValidationTag, ...>` is used which typechecks the expression result type with the expected type - only valid typechecked expression are allowed. (Note: failure cases still successfully result in a `kWasmVoid` typed `WasmValue`, but this is difficult to exploit.)

This can still be exploited by tricking `InstanceBuilder::InitGlobals()` into using a yet uninitialized reference typed global value, which initially has the placeholder value `undefined`.

`DecodeGlobalSection()` originally enforces initialization order of the globals by the decoding phase inside `consume_init_expr()`:

```cpp
  void DecodeGlobalSection() {
    uint32_t globals_count = consume_count("globals count", kV8MaxWasmGlobals);
    uint32_t imported_globals = static_cast<uint32_t>(module_->globals.size());
    // It is important to not resize the globals vector from the beginning,      // [!] this enforces initialization order
    // because we use its current size when decoding the initializer.
    module_->globals.reserve(imported_globals + globals_count);
    for (uint32_t i = 0; ok() && i < globals_count; ++i) {
      // ...
      ConstantExpression init = consume_init_expr(module_.get(), type, shared);
      module_->globals.push_back(
          WasmGlobal{.type = type,
                     .mutability = mutability,
                     .init = init,
                     .index = 0,  // set later in CalculateGlobalOffsets
                     .shared = shared});
      if (shared) module_->has_shared_part = true;
    }
  }
```

At `InstanceBuilder::InitGlobals()`, we have all the `module_->globals` entries ready but are initializing them in order starting from index 0. This allows us to use a global value that is yet uninitialized, which returns `undefined` but is typed to be the global's type. In the attached PoC, we set up the module so that `global[0]` is initialized with `global.get 0`, which uses its own placeholder value of `undefined`.

This finally results in a type confusion, where using the global value results in `undefined` being confused as the global's type. This interestingly also immediately leads to arbitrary caged read/write primitive, as `undefined` has the following memory layout:

```text
pwndbg> x/4wx 0x121300000068
0x121300000068: 0x000004f5      0x00000000      0x7ff80000      0x00005bb1
```

The entry at index 2, `0x7ff80000`, corresponds to the `length` field for `WasmArray` types. Thus we can confuse `undefined` to a `i32` array and obtain caged read/write primitive.

> Note: This bug also implies that `wasm_max_module_size` should never be allowed to be set higher than the current `kV8MaxWasmModuleSize` limit. However, there are no such invariants enforced.
>
> Note 2: This bug may also be exploitable by overflowing the module size outside of `int`/`uint32_t` range, but this has not been investigated further as overflowing 1 GiB is already enough.


#### Bisect

- Module size check bug introduced by commit [549692c](https://chromiumdash.appspot.com/commit/549692cbc0ab4e9929e6e5f13db879072b119fb0) in M63 that introduced WASM streaming compilation.
- 30-bit offset optimization introduced by commit [e557383](https://chromiumdash.appspot.com/commit/e557383c83d99a0b06168e87487018f94d29a467) in M99 that optimizes constant expression decoding.


### VERSION

See bisect commit release info in Chromium Dash for more info: [549692c](https://chromiumdash.appspot.com/commit/549692cbc0ab4e9929e6e5f13db879072b119fb0), [e557383](https://chromiumdash.appspot.com/commit/e557383c83d99a0b06168e87487018f94d29a467)

Current exploit uses WasmGC, but this may also be exploitable even before the introduction of WasmGC as the underlying bug is technically irrelevant with WasmGC.

This (at least) affects all Chrome builds with WasmGC available by default, which is M112 up to latest (M112 ~ M118 behind Origin Trials, later shipped in M119~). The root cause exists from M99~, any may even affect M63~ if `int`/`uint32_t` overflow is feasible.

Chrome Version: M112 (?) ~ latest (tested on latest canary, 131.0.6727.0)\
Operating System: All


### REPRODUCTION CASE

Attached `poc.html` which exploits the vulnerability to obtain arbitrary caged read/write, then writes into cage offset `0x4242424` a value of `0x13333337` to demonstrate a crash.

In my local environment the repro required ~5GB of resident memory, so I recommend running this on an environment with 8GB or more memory. Also, ClusterFuzz may have a hard time reproing due to 1 GiB module creation - locally it repros in 3 seconds, but I recommend giving CF up to 60 seconds.


### FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION

Type of crash: Renderer  
Crash State: Crashes within JIT code, while trying to `array.set` which results in writing `0x13333337` into cage offset `0x4242424`.


### CREDIT INFORMATION

Reporter credit: Seunghyun Lee (@0x10n) of CMU CyLab


-----

Full exploit coming soon... (again??)
```

## Vulnerability Description

d8 (JS) version of the same intermediate WasmNull type confusion exploit PoC. Identical exploit logic to 59486321_poc.html; runs in d8 standalone. Establishes caged_read and caged_write primitives, final call: caged_write(0x4242424, 0x13333337).

## Capabilities

addrof, caged_read (arbitrary 32-bit read within V8 sandbox), caged_write (arbitrary 32-bit write within V8 sandbox). Demonstrated: caged_write(0x4242424, 0x13333337). d8 environment.
