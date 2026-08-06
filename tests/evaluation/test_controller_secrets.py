"""Tests for resolving the controller secrets on the evaluator side.

The evaluators must derive the same task tokens and expected flag as the
controller, so the secrets have no hardcoded fallback: they come from the
arguments or the environment, or resolution fails.
"""

import pytest

from cybergym.evaluation.types import resolve_controller_secrets
from cybergym.server.types import API_KEY_ENV_VAR, FLAG_SEED_ENV_VAR, SALT_ENV_VAR

SECRET_ENV_VARS = (SALT_ENV_VAR, FLAG_SEED_ENV_VAR, API_KEY_ENV_VAR)


@pytest.fixture
def full_secret_env(monkeypatch):
    monkeypatch.setenv(SALT_ENV_VAR, "env_salt")
    monkeypatch.setenv(FLAG_SEED_ENV_VAR, "env_seed")
    monkeypatch.setenv(API_KEY_ENV_VAR, "env_key")


@pytest.fixture
def no_secret_env(monkeypatch):
    for var in SECRET_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestResolveControllerSecrets:
    def test_from_env(self, full_secret_env):
        secrets = resolve_controller_secrets()
        assert secrets.salt == "env_salt"
        assert secrets.flag_seed == "env_seed"
        assert secrets.api_key == "env_key"

    def test_arguments_win_over_env(self, full_secret_env):
        secrets = resolve_controller_secrets(
            token_salt="arg_salt",
            flag_seed="arg_seed",
            controller_api_key="arg_key",
        )
        assert secrets == ("arg_salt", "arg_seed", "arg_key")

    def test_arguments_alone_are_enough(self, no_secret_env):
        secrets = resolve_controller_secrets(
            token_salt="s", flag_seed="f", controller_api_key="k"
        )
        assert secrets == ("s", "f", "k")

    def test_rejects_when_unconfigured(self, no_secret_env):
        with pytest.raises(ValueError, match=SALT_ENV_VAR):
            resolve_controller_secrets()

    @pytest.mark.parametrize(
        ("omit", "env_var"),
        [
            ("token_salt", SALT_ENV_VAR),
            ("flag_seed", FLAG_SEED_ENV_VAR),
            ("controller_api_key", API_KEY_ENV_VAR),
        ],
    )
    def test_rejects_each_missing_secret(self, no_secret_env, omit, env_var):
        """Every secret is required — a partial configuration is not accepted."""
        kwargs = {"token_salt": "s", "flag_seed": "f", "controller_api_key": "k"}
        del kwargs[omit]
        with pytest.raises(ValueError, match=env_var):
            resolve_controller_secrets(**kwargs)
