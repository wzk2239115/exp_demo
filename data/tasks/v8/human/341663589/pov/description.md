# 341663589: Security: [0-day] V8 Incorrect parsing leads to type confusions

## ClusterFuzz Report

```
#### VULNERABILITY DETAILS
NOTE: TAG has evidence that the following bug is being used in the wild. Therefore, this bug is subject to TAG's 7 day disclosure deadline.

There is a bug in V8's scope analysis that can result in type confusions. The following pocs were reconstructed from an exploit chain delivered to Chrome 124 and the bug also triggers on head.

```javascript
(function() {
    ((XXX = class {
      static {
        this;
      }
      constructor() {}
    }) => {})();
})();
```

#### VERSION
Chrome Version: 125.0.6422.60 + head

#### REPRODUCTION CASE
Minimal poc that triggers a dcheck in dcheck.js

Arbitrary read/write primitive can be found in rw.js

#### CREDIT INFORMATION
Externally reported security bugs may appear in Chrome release notes. If this bug is included, how would you like to be credited?

Reporter credit: Clément Lecigne of Google's Threat Analysis Group and Brendon Tiszka
```

## Vulnerability Description

56512351_dcheck.js is the minimal trigger for the underlying parser scope bug: a class expression with a static block referencing 'this' inside an arrow function inside an IIFE causes the parser to mark a parameter as forced-context-allocated without being used, hitting DCHECK '!var->has_forced_context_allocation() || var->is_used()' in scopes.cc:2450. 56512352_dcheck.txt is the crash log showing the full V8 DCHECK stack trace for this JS file.

## Capabilities

Crashes the process with DCHECK failure in scopes.cc. No memory read/write.
