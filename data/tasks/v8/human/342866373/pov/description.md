# 342866373: V8 Sandbox Bypass: JSToWasmWrapperAsm accessible and allows type confusion

## ClusterFuzz Report

```
Security Bug

Important: Please do not change the component of this bug manually.

Please READ THIS FAQ before filing a bug: https://chromium.googlesource.com/chromium/src/+/HEAD/docs/security/faq.md

Please see the following link for instructions on filing security bugs: https://www.chromium.org/Home/chromium-security/reporting-security-bugs

Reports may be eligible for reward payments under the Chrome VRP: https://g.co/chrome/vrp

NOTE: Security bugs are normally made public once a fix has been widely deployed.

-------------------------

VULNERABILITY DETAILS
By overwriting the code pointer on a function object, we can call JSToWasmWrapperAsm. The generated code (on x64) treats `rsi` (which contains the full JSFunction pointer) as a `WrapperBuffer` containing raw pointers, derefencing and calling sandbox-controllable pointers.

This happens as `JSToWasmWrapperAsm` uses the `kJSEntrypointTag` tag (i.e. untagged).

VERSION
V8 12.7.0, commit d4b2933dd0e9b51bd86227556062270384409c14

REPRODUCTION CASE
Please include a demonstration of the security bug, such as an attached HTML or binary file that reproduces the bug when loaded in Chrome. PLEASE make the file as small as possible and remove any content not required to demonstrate the bug, or any personal or confidential information.

Please attach files directly, not in zip or other archive formats, and if you've created a demonstration site please also attach the files needed to reproduce the demonstration locally.


CREDIT INFORMATION
Externally reported security bugs may appear in Chrome release notes. If this bug is included, how would you like to be credited?
Reporter credit: clubby789
```

## Vulnerability Description

Single-file sandbox escape exploit. Creates Sandbox.MemoryView over the full 4GB sandbox range for arbitrary in-sandbox read/write. Reads the builtin dispatch index at offset 0xc of Uint8Array.prototype.map (a JSFunction), increments it by 1 to redirect to JSToWasmWrapperAsm (the immediately following entry in builtins-definitions.h). Writes fake wasm wrapper metadata at offsets 0x10-0x28: RSP delta=0, callTarget=Sandbox.targetPage, paramStart=Sandbox.targetPage, paramEnd=Sandbox.targetPage. Calls f.apply({}, [0,0]) to bypass receiver checks and trigger JSToWasmWrapperAsm with the attacker-controlled call target.

## Capabilities

Arbitrary call to Sandbox.targetPage (attacker-controlled address outside the sandbox). Full V8 sandbox escape via builtin dispatch table index corruption. Requires --sandbox-testing and Sandbox.* API.
