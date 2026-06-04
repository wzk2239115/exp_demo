# Task data licensing

The **source code** in this repository is licensed under Apache-2.0 (see
[`LICENSE`](LICENSE)).

The **task data** under `data/tasks/` is *not* original to this project. It is
derived from external upstream sources, and each artifact remains under the
license of its upstream. The Apache-2.0 license on the code does **not**
relicense this data, and nothing here grants rights beyond what those upstream
licenses allow. If you redistribute the task data, consult the upstream terms.

| Path | Upstream source | Upstream license |
| --- | --- | --- |
| `data/tasks/kernel/kernelctf/` | Linux kernel + Google [kernelCTF](https://google.github.io/security-research/kernelctf/rules.html) | Linux kernel: **GPL-2.0** |
| `data/tasks/kernel/syzbot/` | Linux kernel + [syzbot](https://syzkaller.appspot.com/) reports/reproducers | Linux kernel: **GPL-2.0** |
| `data/tasks/user/cybergym/` | [CyberGym](https://github.com/sunblaze-ucb/cybergym), built from [ARVO](https://github.com/n132/ARVO) / [OSS-Fuzz](https://github.com/google/oss-fuzz) targets | Per the CyberGym project's terms; each fuzz target also retains its **own upstream project's license** |
| `data/tasks/user/nofuzz/` | Open-source C/C++ projects | Per-project: each retains its **own upstream license** |
| `data/tasks/v8/` (`clusterfuzz/`, `human/`, `sbxbrk/`) | The [V8](https://v8.dev/) JavaScript engine; bug reports and reproducers from the [Chromium issue tracker](https://issues.chromium.org/) | V8 source: **BSD-3-Clause**; issue-tracker content: per Chromium project terms |
