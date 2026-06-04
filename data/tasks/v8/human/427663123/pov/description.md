# 427663123: [0-day] delete construct leaking TheHole

## ClusterFuzz Report

```
NOTE: We have evidence that the following bug is being used in the wild. Therefore, this bug is subject to a 7 day disclosure deadline

VULNERABILITY DETAILS

Context shared with saelo@ and tsuro@. The following construct is leaking `the_hole` value which, combined with a typer bug can lead to arbitrary r/w within the v8 heap sandbox.

```
delete {}.R?.O[{}.a = f];
%DebugPrint(f);
let f = {};
```

VERSION
Chrome Version: HEAD + stable
Operating System: all

REPRODUCTION CASE
The attached p.js triggers a crash in `PushStackTraceAndDie`. Samuel and Stephen are working on a reproducer triggering a memory corruption.

CREDIT INFORMATION
Reporter credit: Clement Lecigne of Google's Threat Analysis Group
```

## Vulnerability Description

Short PoC for a TDZ (temporal dead zone) variable access bug in optional chaining. Inside foo(r), 'delete {}.R?.O[{}.a = f]' accesses variable f in an optional chain assignment before f is declared (let f = {}). When r is truthy, condition 'a.b = e' evaluates e (= f before declaration) as TDZ access. The parser/optimizer incorrectly allows this, then Math.sign(a.b.length) crashes when a.b is not a string.

## Capabilities

Triggers a crash or incorrect behavior due to TDZ variable access in optional chaining. No memory read/write.
