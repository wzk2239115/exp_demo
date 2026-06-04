function f1() {
    new ArrayBuffer(0x7fe00000);
    v0 = Math.sqrt(0);
    %DebugPrint(v0);
}

function f5(v0) {
    %OptimizeMaglevOnNextCall(f1);
    f1();
}

let v0 = 1;
f5();
f5();
