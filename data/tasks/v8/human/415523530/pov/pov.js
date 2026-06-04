
let v0 = -2147483649;
function f0() {
  let v1 = 0;
  try {
    for (let v3 = 0; v3 < 25; v3++) {
      v0 = v3;
      [Uint8Array, Int8Array, Uint16Array, Int16Array, Uint32Array, Int32Array, Uint8ClampedArray, Float32Array, Float64Array].forEach(v3);
      v0 = v3;
    }
  } catch (v6) {}
}
try {
  %PrepareFunctionForOptimization(f0);
} catch (v7) {}
try {
  f0();
} catch (v9) {}
%OptimizeFunctionOnNextCall(f0);
try {
  f0();
} catch (v11) {}
//flags: --allow-natives-syntax --turbolev
