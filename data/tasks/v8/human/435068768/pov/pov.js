function AsmModule(stdlib, foreign, heap) {
    "use asm";
    var HEAP32 = new stdlib.Int32Array(heap);

    function trigger(a, b) {
        a = a | 0;
        b = b | 0;
        HEAP32[a >> (b >> 2)] = 42;
    }
    return { trigger: trigger };
}

var heap = new ArrayBuffer(0x10000);
var module = AsmModule({ "Int32Array": Int32Array }, {}, heap);

module.trigger(0x100, 0x100);