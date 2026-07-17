"""Org-specific configuration, loaded from org_config.json at the repo root.

The public codebase is a generic org-knowledge engine; everything specific to
one org (authoritative Drive file ids, sensitive phrase filters, event keyword
mappings, canned demo responses) lives in org_config.json, which is gitignored.
org_config.example.json documents the shape with placeholder values and is the
fallback when the private file is absent (fresh clones, CI).

Deployment note: .gcloudignore deliberately does NOT exclude org_config.json,
so `gcloud run deploy --source .` ships the private config even though git
never sees it. Set ORG_CONFIG_PATH to load from a different location.
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_cache: Optional[dict] = None


def load_org_config() -> dict:
    global _cache
    if _cache is None:
        configured = os.environ.get("ORG_CONFIG_PATH")
        candidates = [Path(configured)] if configured else []
        candidates += [_REPO_ROOT / "org_config.json", _REPO_ROOT / "org_config.example.json"]
        for path in candidates:
            if path.is_file():
                try:
                    _cache = json.loads(path.read_text())
                    logger.info("Org config loaded from %s", path.name)
                    break
                except Exception as e:
                    # A present-but-broken config file is a misconfiguration, not
                    # an absent one. Silently falling through to the next
                    # candidate (e.g. the generic example config) would quietly
                    # disable org-specific safety guards like sensitive_phrases —
                    # fail loud instead of guessing.
                    raise RuntimeError(f"{path} exists but failed to parse: {e}") from e
        if _cache is None:
            logger.warning("No org config found; running with empty config")
            _cache = {}
    return _cache


def cfg_list(key: str) -> list:
    return load_org_config().get(key, [])


def cfg_dict(key: str) -> dict:
    return load_org_config().get(key, {})
