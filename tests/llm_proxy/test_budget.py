"""BudgetManager disk-persistence tests (keys survive proxy restart)."""

import json
import os

from cybergym.llm_proxy.budget import BudgetManager


class TestBudgetPersistence:
    def test_save_and_reload_roundtrip(self, tmp_path):
        state = tmp_path / "budget_state.json"
        m1 = BudgetManager(default_max_budget=5.0, state_path=state)
        k1 = m1.generate_key(max_budget=10.0)
        k2 = m1.generate_key(
            max_budget=20.0, allowed_models=["deepseek-v4.1-flash"]
        )
        m1.record_usage(
            k1,
            "deepseek-v4.1-flash",
            {"input_tokens": 100, "output_tokens": 50},
            cost=0.5,
            duration=1.25,
        )

        # New manager (simulating proxy restart) must see the same keys.
        m2 = BudgetManager(default_max_budget=5.0, state_path=state)
        assert set(m2._keys) == {k1, k2}

        r1 = m2.validate_key(k1)
        assert r1 is not None
        assert r1.spend == 0.5
        assert r1.requests == 1
        assert r1.input_tokens == 100
        assert r1.output_tokens == 50
        assert r1.total_latency == 1.25
        assert r1.max_budget == 10.0

        r2 = m2.validate_key(k2)
        assert r2 is not None
        assert r2.allowed_models == frozenset({"deepseek-v4.1-flash"})

        # Per-model bucket survived too.
        usage = m2.get_usage(k1)
        assert usage["models"]["deepseek-v4.1-flash"]["requests"] == 1

    def test_delete_persists(self, tmp_path):
        state = tmp_path / "budget_state.json"
        m1 = BudgetManager(state_path=state)
        k = m1.generate_key()
        m1.delete_key(k)

        m2 = BudgetManager(state_path=state)
        assert m2.validate_key(k) is None
        assert m2.get_usage(k) is None

    def test_state_file_always_valid_json(self, tmp_path):
        state = tmp_path / "budget_state.json"
        m = BudgetManager(state_path=state)
        for i in range(5):
            m.generate_key()
            m.record_usage(f"cgym-{i}", "m", {"input_tokens": 1}, cost=0.1)
        # Atomic replace: file must parse at all times.
        with open(state) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_no_state_path_means_no_persistence(self, tmp_path):
        m = BudgetManager()
        k = m.generate_key()
        assert m.state_path is None
        assert not list(tmp_path.iterdir())
        assert k in m._keys

    def test_corrupt_state_starts_empty(self, tmp_path):
        state = tmp_path / "budget_state.json"
        state.write_text("{ not json !!")
        m = BudgetManager(state_path=state)
        assert m._keys == {}

    def test_os_env_not_required(self):
        # os is imported in budget.py for os.replace; sanity check attribute.
        from cybergym.llm_proxy import budget as mod

        assert hasattr(mod, "os")
        assert hasattr(mod.os, "replace")
