"""Unit tests for IntermediateStatsLogger (mid-run progress / usage snapshots)."""

import json

from cybergym.evaluation.agents.helper import IntermediateStatsLogger


class _FakeKeyManager:
    def __init__(self):
        self.calls = 0

    def get_api_key_usage(self, api_key: str) -> dict:
        self.calls += 1
        return {"spend": 0.5, "requests": self.calls}


def _force_interval_crossing(log: IntermediateStatsLogger) -> None:
    # Pretend the agent has been running well past one interval, deterministically.
    log.start_time -= log.time_interval * 5


def test_snapshots_usage_on_interval_crossing(tmp_path):
    km = _FakeKeyManager()
    log = IntermediateStatsLogger(
        agent_name="Test",
        api_key="cgym-x",
        key_manager=km,
        usage_dir=tmp_path,
        time_interval=1.0,
    )
    _force_interval_crossing(log)

    log("first chunk")

    snapshots = list(tmp_path.glob("usage_*.json"))
    assert len(snapshots) == 1
    assert km.calls == 1
    assert json.loads(snapshots[0].read_text())["spend"] == 0.5


def test_no_key_manager_writes_nothing(tmp_path):
    # Elapsed-time logging still works, but no usage fetch / snapshot.
    log = IntermediateStatsLogger(
        agent_name="Test", usage_dir=tmp_path, time_interval=1.0
    )
    _force_interval_crossing(log)
    log("chunk")  # must not raise
    assert list(tmp_path.glob("usage_*.json")) == []


def test_usage_fetch_failure_is_non_fatal(tmp_path):
    class _Boom:
        def get_api_key_usage(self, api_key):
            raise RuntimeError("proxy down")

    log = IntermediateStatsLogger(
        agent_name="Test",
        api_key="cgym-x",
        key_manager=_Boom(),
        usage_dir=tmp_path,
        time_interval=1.0,
    )
    _force_interval_crossing(log)
    log("chunk")  # must swallow the error
    assert list(tmp_path.glob("usage_*.json")) == []


def test_no_snapshot_before_interval(tmp_path):
    km = _FakeKeyManager()
    log = IntermediateStatsLogger(
        agent_name="Test",
        api_key="cgym-x",
        key_manager=km,
        usage_dir=tmp_path,
        time_interval=1e9,  # never crosses within the test
    )
    log("chunk")
    assert km.calls == 0
    assert list(tmp_path.glob("usage_*.json")) == []
