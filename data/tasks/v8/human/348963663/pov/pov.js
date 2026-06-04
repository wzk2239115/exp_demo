function main() {
  try {
    d8.file.execute("test/mjsunit/wasm/wasm-module-builder.js");
  } catch (v2) {}
  (function f15() {
    let v38 = new WasmModuleBuilder();
    let v39 = v38.addType(kSig_v_v);
    let v40 = v38.addImport('', 'func', v39);
    v38.addExport('exp', v40);
    class c0 {}
    class c1 extends c0 {
      constructor() {
        super();
      }
    }
    let v41 = v38.instantiate({
      '': {
        func: c1
      }
    }).exports;
    try {
      v41['exp']({});
    } catch (e) {}
    try {
      v41['exp']({});
    } catch (e) {}
  })();
}
main();
//flags: --allow-natives-syntax --jit-fuzzing