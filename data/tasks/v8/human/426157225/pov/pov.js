function f0(v7) {
    var v8 = v7();
    if (v8 && v8.next) {
      v8.next();
    }
}
  var v0 = {
    a() {},
    b: () => {},
    async c() {},
    *d() {},
    async ['f']() {},
    *['g']() {},
  };
for (var v1 of Object.keys(v0)) {
  f0(v0[v1]);
  %OptimizeFunctionOnNextCall(f0);
}
//flags: --allow-natives-syntax --maglev-poly-calls --turbolev