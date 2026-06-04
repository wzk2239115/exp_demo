function main() {
  function f0(v2, v3) {
    var v4 = v3[0];
    var v5 = v2[0];
    Array.prototype.indexOf.call(v3);
  }
  %PrepareFunctionForOptimization(f0);
  var v0 = new Array(1);
  v0[0] = 'tagged';
  f0(v0, [1]);
  var v1 = new Array(1);
  v1[0] = 0.1;
  %OptimizeFunctionOnNextCall(f0);
  f0(v1, v1);
}
main();
main();
//flags: --allow-natives-syntax