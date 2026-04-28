"""Config: SUITE_LLM_MODEL env var feeds the default model."""

from __future__ import annotations

import pytest

from caseguide.config import DEFAULT_LLM_MODEL, Config


def test_suite_llm_model_env_overrides_default(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SUITE_LLM_MODEL", "granite4:tiny-h")
    cfg = Config(path=tmp_path / "c.ini")
    assert cfg.llm_model == "granite4:tiny-h"


def test_suite_llm_model_env_yields_to_user_choice(tmp_path, monkeypatch) -> None:
    ini = tmp_path / "c.ini"
    cfg = Config(path=ini)
    cfg.llm_model = "qwen2.5:7b-instruct"
    cfg.sync()

    monkeypatch.setenv("SUITE_LLM_MODEL", "granite4:tiny-h")
    assert Config(path=ini).llm_model == "qwen2.5:7b-instruct"


@pytest.mark.parametrize("env_value", ["", "   "])
def test_suite_llm_model_empty_env_falls_back(tmp_path, monkeypatch, env_value) -> None:
    monkeypatch.setenv("SUITE_LLM_MODEL", env_value)
    cfg = Config(path=tmp_path / "c.ini")
    assert cfg.llm_model == DEFAULT_LLM_MODEL
