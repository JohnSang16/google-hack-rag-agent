"""Pins that the response cache can never replay one tier's answer to another.

Before this fix, _cache_key only hashed query+filters, so an exec-tier answer
containing real financial figures would be served verbatim to the next
anonymous/member request for the same query text.
"""
from src.api.server import _cache_key


def test_cache_key_differs_by_tier():
    anon = _cache_key("how much did hacklanta cost", None, "anonymous")
    member = _cache_key("how much did hacklanta cost", None, "member")
    exec_ = _cache_key("how much did hacklanta cost", None, "exec")
    assert len({anon, member, exec_}) == 3


def test_cache_key_default_tier_is_anonymous():
    assert _cache_key("q", None) == _cache_key("q", None, "anonymous")
