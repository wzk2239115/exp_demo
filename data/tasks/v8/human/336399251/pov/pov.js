d8.test.enableJSPI();
d8.test.installConditionalFeatures();
WebAssembly.promising(Int32Array);
//flags: --allow-natives-syntax --fuzzing