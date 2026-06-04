# Changelog

Notable changes to the ExploitGym benchmark and tooling.

## 2026-06: 1.0 release

The released benchmark may differ from the snapshot evaluated in the
[paper](https://arxiv.org/abs/2605.11086) (arXiv:2605.11086). The canonical task
list for each version lives in `data/task_ids/` (e.g. `data/task_ids/v1.txt`).

### Benchmark

- Initial public release: **869 instances**, including kernel 186 (kernelctf 27, syzbot
  159), user 502 (cybergym 484, nofuzz 18), v8 181 (clusterfuzz 106, human 66,
  sbxbrk 9).
- Filtered non-exploitable cases from the paper snapshot
  (**898 → 869**).
