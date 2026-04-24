"""Config: LLM-related settings round-trip through QSettings."""

from __future__ import annotations

from inscription.config import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TIMEOUT_S,
    Config,
)


def test_llm_defaults(tmp_path) -> None:
    cfg = Config(path=tmp_path / "c.ini")
    assert cfg.llm_enabled is False
    assert cfg.llm_base_url == DEFAULT_LLM_BASE_URL
    assert cfg.llm_model == DEFAULT_LLM_MODEL
    assert cfg.llm_timeout_s == DEFAULT_LLM_TIMEOUT_S
    assert cfg.llm_api_key is None


def test_llm_values_round_trip(tmp_path) -> None:
    ini = tmp_path / "c.ini"
    cfg = Config(path=ini)
    cfg.llm_enabled = True
    cfg.llm_base_url = "http://localhost:1234/v1"
    cfg.llm_model = "gemma2:9b"
    cfg.llm_timeout_s = 60.0
    cfg.llm_api_key = "sk-test"
    cfg.sync()

    # New Config instance reads back from disk.
    reopened = Config(path=ini)
    assert reopened.llm_enabled is True
    assert reopened.llm_base_url == "http://localhost:1234/v1"
    assert reopened.llm_model == "gemma2:9b"
    assert reopened.llm_timeout_s == 60.0
    assert reopened.llm_api_key == "sk-test"


def test_llm_api_key_clears_to_none(tmp_path) -> None:
    cfg = Config(path=tmp_path / "c.ini")
    cfg.llm_api_key = "x"
    cfg.llm_api_key = None
    assert cfg.llm_api_key is None


def test_llm_timeout_coerces_bad_value(tmp_path) -> None:
    ini = tmp_path / "c.ini"
    ini.write_text("[llm]\ntimeout_s=not-a-number\n", encoding="utf-8")
    cfg = Config(path=ini)
    assert cfg.llm_timeout_s == DEFAULT_LLM_TIMEOUT_S
