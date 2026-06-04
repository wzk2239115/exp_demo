function isp(obj, name, type) {
  return typeof type === 'undefined' || typeof desc.value === type;
}
function getp(obj, type) {
  let properties = [];
  for (let name of Object.getOwnPropertyNames(obj)) {
    if (isp(obj, name, type)) properties.push(name);
  }
  return properties;
}
function get(obj, s) {
  let properties = getp(obj);
  return properties[s % properties.length];
}
function main() {
  try {
    (function () {
      function f4(v12) {
        return {
          ...v12
        };
      }
      function f5(v13) {
        return {
          ...v13
        };
      }
      const v10 = {
        x: "x",
        y: "y",
        z: "x"
      };
      const v11 = {
        a: 1,
        b: 2,
        c: 3,
        d: 4
      };
      try {
        Object.defineProperty(v11, 'c', {
          writable: false
        });
      } catch (e) {}
      for (const v14 of [v10, v11]) {
        for (const v15 of [f4, f5]) {
          const v16 = v15(v14);
          Object.defineProperty(v16, get(v16, 828586), {
            value: Math.PI
          });
        }
      }
      Object.defineProperty(v11, get(v11, 906838), {
        value: URIError
      });
    })();
  } catch (e) {}
}
main();
main();
//flags: --jit-fuzzing