# 344963941: V8 Sandbox Bypass: Irregexp engine bytecode modification leads to arbitrary read/write outside the sandbox

## ClusterFuzz Report

```
# V8 Sandbox Bypass: Irregexp engine bytecode modification leads to arbitrary read/write outside the sandbox

**VULNERABILITY DETAILS**

Since the bytecode used by the Irregexp engine resides on the V8 heap, it can be arbitrarily modified by an attacker.
In `IrregexpInterpreter::Result RawMatch` the `backtrack_stack` is not guarded against an attacker controlling this bytecode.
By performing a pop on an empty `backtrack_stack`, data in front of the original stack data can be accessed OOB.
This can be achieved by using any of the following bytecodes: `POP_CP, POP_BT, POP_REGISTER and CHECK_GREEDY` [1].

The `backtrack_stack` data is initially allocated on the OS stack.
Therefore, this OOB can be used to modify OS stack data directly.
Concretely, I target the corresponding `backtrack_stack.data_` structure that is directly accessible with the OOB.
I exploit this with the following steps to write to an arbitrary address (here the Sandbox.targetPage):

- Underflow `backtrack_stack` by using the `POP_REGISTER` bytecode.
- Overwrite `backtrack_stack.data_.end_of_storage_` with a random unaligned value. This effectively allows for OOB access in both directions now since the check that could potentially reallocate `backtrack_stack.data_` will always fail even once the stack becomes full [2].
- Overwrite `backtrack_stack.data_.end_` to point to the location on the stack where the data pointer of `InterpreterRegisters` is stored [3]. Without first modifying `backtrack_stack.data_.end_of_storage_`, this would fail because this pointer is stored directly after the original end of `backtrack_stack.data_`.
- Use the `PUSH_BT` bytecode to write an arbitrary pointer (here Sandbox.targetPage) to the data pointer of `InterpreterRegisters`.
- Using the `SET_REGISTER` bytecode will now write to our given pointer.

The corresponding bytecode, which illustrates this better, looks like this:
```
POP_REGISTER | 0x000,
PUSH_BT, 0x1, // overwrite backtrack_stack.data_.end_of_storage_
POP_REGISTER | 0x000, POP_REGISTER | 0x000, POP_REGISTER | 0x000,
POP_REGISTER | 0x100, ADVANCE_REGISTER | 0x100, BACKTRACK_END_TO_REGS_OFF, // BACKTRACK_END_TO_REGS_OFF = 0x10c
PUSH_REGISTER | 0x100, // overwrite backtrack_stack.data_.end => &registers.begin_
PUSH_BT, sbxLower,   // overwrite registers.begin_ with Sandbox.targetPage
PUSH_BT, sbxUpper,
SET_REGISTER | 0x000, 0x41414141, // write 0x41414141 to targetPage
```

To reproduce this, use the attached expl.js below. This relies on stack offsets, so you might need to replicate my setup or adjust those offsets to make it work on other distros. However, in my tests this was consistent and did not need to be adjusted.
I developed the repro on commit V8 `2106d9c81a1fb9d758ebda1560e2251b0f05150c` and used the following docker image `archlinux:base-20240101.0.204074
`.

[1] https://source.chromium.org/chromium/chromium/src/+/main:v8/src/regexp/regexp-interpreter.cc;l=552

[2] https://source.chromium.org/chromium/chromium/src/+/main:v8/src/base/small-vector.h;l=153

[3] https://source.chromium.org/chromium/chromium/src/+/main:v8/src/regexp/regexp-interpreter.cc;l=454

**VERSION**

Tested on d8 stable (12.5.227.13)

Operating system: Arch Linux



**FIX**

Turn the DCHECK in BacktrackStack::peek() into a SBXCHECK (see fix.patch)
```

## Vulnerability Description

Full sandbox escape exploit via Irregexp bytecode modification. Uses Sandbox.MemoryView for arbitrary in-sandbox read/write and Sandbox.getAddressOf for object location. Reads the regexp's RegExpData pointer and bytecode ByteArray pointer from the heap. Sets capture count to 0xfffffffe to force interpreter mode. Overwrites bytecode with crafted Irregexp opcodes (POP_REGISTER, PUSH_BT, ADVANCE_REGISTER, PUSH_REGISTER, SET_REGISTER) that underflow the backtrack stack, overwrite data_.end_of_storage_, pivot data_.end to point at the registers array, overwrite registers.begin_ with Sandbox.targetPage (via two PUSH_BT opcodes for lower/upper 32-bit halves). The final SET_REGISTER writes 0x41414141 to Sandbox.targetPage.

## Capabilities

Arbitrary 32-bit write to any address outside the sandbox (demonstrated: 0x41414141 to Sandbox.targetPage). Full sandbox escape via regexp bytecode manipulation. Requires --sandbox-testing and Sandbox.* API.
