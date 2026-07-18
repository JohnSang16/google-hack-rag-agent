"""
Pins the org config loader: private file wins, example is the fallback,
and the config-driven constants are populated in whichever environment
the suite runs (private config locally, example config in CI).
"""
import json

import pytest

from src import org_config
from src.agent.agent import _EVENT_KEYWORD_MAP, _SENSITIVE_PHRASES
from src.retrieval.reranker import _AUTHORITATIVE_FILE_IDS


def test_loader_prefers_explicit_path(tmp_path, monkeypatch):
    custom = tmp_path / "custom.json"
    custom.write_text(json.dumps({"sensitive_phrases": ["from custom"]}))
    monkeypatch.setenv("ORG_CONFIG_PATH", str(custom))
    monkeypatch.setattr(org_config, "_cache", None)
    assert org_config.cfg_list("sensitive_phrases") == ["from custom"]
    monkeypatch.setattr(org_config, "_cache", None)


def test_loader_falls_back_to_example_when_path_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ORG_CONFIG_PATH", str(tmp_path / "does-not-exist.json"))
    monkeypatch.setattr(org_config, "_cache", None)
    cfg = org_config.load_org_config()
    assert cfg, "should fall back to org_config.json or the example, not empty"
    monkeypatch.setattr(org_config, "_cache", None)


def test_config_driven_constants_are_populated():
    assert len(_AUTHORITATIVE_FILE_IDS) >= 1
    assert len(_SENSITIVE_PHRASES) >= 1
    assert len(_EVENT_KEYWORD_MAP) >= 1


def test_example_config_has_all_expected_keys():
    example = json.loads(open("org_config.example.json").read())
    for key in ("authoritative_file_ids", "sensitive_phrases", "event_keyword_map", "demo_seeds"):
        assert key in example


def test_broken_org_config_fails_loud_instead_of_falling_back(tmp_path, monkeypatch):
    # A present-but-unparseable org_config.json must not silently fall through
    # to the generic example config — that would quietly disable org-specific
    # safety guards like sensitive_phrases without anyone noticing.
    broken = tmp_path / "custom.json"
    broken.write_text("{not valid json")
    monkeypatch.setenv("ORG_CONFIG_PATH", str(broken))
    monkeypatch.setattr(org_config, "_cache", None)
    with pytest.raises(RuntimeError):
        org_config.load_org_config()
    monkeypatch.setattr(org_config, "_cache", None)
