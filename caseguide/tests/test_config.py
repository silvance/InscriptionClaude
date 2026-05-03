"""Config: SUITE_LLM_MODEL / SUITE_LLM_BASE_URL env vars feed defaults."""

from __future__ import annotations

import pytest

from caseguide.config import DEFAULT_LLM_BASE_URL, DEFAULT_LLM_MODEL, Config


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


# ---- SUITE_LLM_BASE_URL --------------------------------------------------


def test_suite_llm_base_url_env_overrides_default(tmp_path, monkeypatch) -> None:
    """Air-gapped launcher exports this so the apps target the bundled
    Ollama on port 11435 instead of the system Ollama on 11434."""
    monkeypatch.setenv("SUITE_LLM_BASE_URL", "http://127.0.0.1:11435/v1")
    cfg = Config(path=tmp_path / "c.ini")
    assert cfg.llm_base_url == "http://127.0.0.1:11435/v1"


def test_suite_llm_base_url_env_yields_to_user_choice(tmp_path, monkeypatch) -> None:
    """A user who pointed Settings at a remote endpoint shouldn't have
    that quietly overridden by the launcher's env var."""
    ini = tmp_path / "c.ini"
    cfg = Config(path=ini)
    cfg.llm_base_url = "https://my-server.local:8000/v1"
    cfg.sync()

    monkeypatch.setenv("SUITE_LLM_BASE_URL", "http://127.0.0.1:11435/v1")
    assert Config(path=ini).llm_base_url == "https://my-server.local:8000/v1"


@pytest.mark.parametrize("env_value", ["", "   "])
def test_suite_llm_base_url_empty_env_falls_back(tmp_path, monkeypatch, env_value) -> None:
    monkeypatch.setenv("SUITE_LLM_BASE_URL", env_value)
    cfg = Config(path=tmp_path / "c.ini")
    assert cfg.llm_base_url == DEFAULT_LLM_BASE_URL
