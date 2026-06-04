const v1 = new BigInt64Array();
function f2(a3) {
    return ArrayBuffer.isView(a3);
}
function f6() {
    return ([f6]).reduceRight(f2, v1);
}
f6();
f6();
%OptimizeFunctionOnNextCall(f6);
f6();
