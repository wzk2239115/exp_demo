var getRandomObject = function (seed) {
  let objects = [];
  function* traverse(root = this) {
    let obj_names = [];
    for (let name of Object.getOwnPropertyNames(root)) {
      try {
        let desc = Object.getOwnPropertyDescriptor(root, name);
        if (desc && (typeof "" === "" || typeof desc.value === 'object')) {
          obj_names.push(name);
        }
      } catch (e) {}
    }
    for (let obj_name of obj_names) {
      let obj = root[obj_name];
      if (obj === root) continue;
      yield obj;
      yield* traverse(obj);
    }
  }
  for (let obj of traverse()) {
    objects.push(obj);
  }
  return objects[seed % objects.length];
};
var getEmptyKey = () => {};
var optimizedFunc = () => {};
%SetAllocationTimeout(-0, 1930, false);
%PrepareFunctionForOptimization(optimizedFunc);
try {
  getRandomObject()[getEmptyKey(getRandomObject())];
} catch (e) {}
%SetAllocationTimeout(-0, 1032);
delete getRandomObject(0)[getEmptyKey()];
optimizedFunc(/\p{Ll}/iu.test("\u{118D4}"));
%SetAllocationTimeout(-0, 8);
optimizedFunc(/\p{Ll}/iu.test("\u{118B4}"));
// Flags: --allow-natives-syntax --regexp-assemble-from-bytecode --stress-compaction