# ExploitGym

[![Paper](https://img.shields.io/badge/arXiv-2605.11086-b31b1b?style=flat&logo=arxiv&logoColor=white)](https://arxiv.org/abs/2605.11086)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

ExploitGym is a large-scale, realistic benchmark built from real-world vulnerabilities across userspace programs, Google's V8 engine, and the Linux kernel, designed to evaluate AI agents' ability to develop exploits.

## Quick start

```bash
# 1. Python deps
uv sync --extra proxy

# 2. Build runtime artifacts (gdb, socat, nc, node + agent CLIs) and
#    extract task data
bash scripts/setup/setup_data.sh

# 3. Verify the install
bash scripts/setup/validate.sh

# 4. Pull the Firewall Squid image
docker pull ubuntu/squid:latest

# 5. Pull the Docker images for the tasks you want to run
uv run scripts/setup/pull_images.py data/task_ids/sample.txt

# 6. Start the controller, firewall, and LLM proxy. pre_run.py runs the
#    readiness checks and starts all three (auto-detecting any already
#    running), or start them by hand — see docs/eval.md
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
uv run scripts/setup/pre_run.py data/task_ids/sample.txt

# 7. Run the agent
export CYBERGYM_ADMIN_KEY=...
uv run examples/run_agent.py --help
```

Detailed setup steps (system dependencies, GDB, static node, agent
CLIs) live in [docs/setup.md](docs/setup.md).

## Documentation

- [Setup](docs/setup.md): Python deps, GDB, socat/nc, node + agent CLIs
- [Docker images](docs/docker_images.md): pulling target images per task family
- [Evaluation](docs/eval.md): controller / firewall / LLM proxy + `examples/run_agent.py`
- [Defenses](docs/defenses.md): disabling system defenses (ASLR, etc.)
- [Firewall](docs/firewall.md): outbound network isolation for agent containers

## Benchmark updates

The released benchmark is actively maintained. The current release is **v1.0** with
869 instances. See [CHANGELOG.md](CHANGELOG.md) for the full version history. The
canonical task list for the current release is `data/task_ids/v1.txt`.

## Citation

If you use ExploitGym in your research, please cite:

```bibtex
@article{wang2026exploitgym,
  title={ExploitGym: Can AI Agents Turn Security Vulnerabilities into Real Attacks?},
  author={Wang, Zhun and Schiller, Nico and Li, Hongwei and Sesha Narayana, Srijiith and Nasr, Milad and Carlini, Nicholas and Qi, Xiangyu and Wallace, Eric and Bursztein, Elie and Invernizzi, Luca and Thomas, Kurt and Shoshitaishvili, Yan and Guo, Wenbo and He, Jingxuan and Holz, Thorsten and Song, Dawn},
  journal={arXiv preprint arXiv:2605.11086},
  year={2026}
}
```

## License

The source code is licensed under [Apache-2.0](LICENSE). The bundled task data
under `data/tasks/` derives from external upstreams and retains their
respective licenses, see [DATA_LICENSE.md](DATA_LICENSE.md).
