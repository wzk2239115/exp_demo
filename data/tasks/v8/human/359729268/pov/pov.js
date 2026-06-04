let nop = function () { };
function func(args) {
  var bar = 0;
  for (var arg in args) {
    try {
      for (var i = 0; i < 2; i++) {
        nop();
        bar += i[arg];
      }
    } catch (e) { }
  }
}
%PrepareFunctionForOptimization(func);
func({x: 20, y: 11});
//flags: --allow-natives-syntax --fuzzing --always-turbofan
