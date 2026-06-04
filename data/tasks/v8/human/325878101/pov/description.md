# 325878101: Debug check failed: IsWasmDispatchTable(table)

## ClusterFuzz Report

```
## Title:
Debug check failed: IsWasmDispatchTable(table)

## VULNERABILITY DETAILS
see comment #2.
```

## Vulnerability Description

Minimal PoC (requires external wasm-module-builder.js). Creates two Wasm tables: table[0]=kWasmArrayRef (1 element), table[1]=kWasmFuncRef (1 element, initialized with ref.func 0). A loop calls CallIndirect on table[1] index 0 with --wasm-wrapper-tiering-budget=1 to force immediate tier-up. Triggers DCHECK (IsWasmDispatchTable) at tier-up because kWasmArrayRef tables are not dispatch tables.

## Capabilities

Crashes the process with DCHECK (IsWasmDispatchTable or index < length). No memory read/write.
