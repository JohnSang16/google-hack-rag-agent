"""
Pins the Discord auth token layer and the tier capability matrix.
No network calls; Discord API interaction is exercised only through
the pure role-mapping function.
"""
import time
from unittest.mock import patch

from src.access import (
    TIER_ADMIN,
    TIER_ANONYMOUS,
    TIER_EXEC,
    TIER_MEMBER,
    access_for_tier,
    legacy_default,
)
from src.api.auth import sign_token, tier_from_roles, verify_token

_SECRET = "test-secret"


# --- Signed tokens ---

def test_token_roundtrip():
    token = sign_token({"uid": "123", "name": "john"}, _SECRET)
    payload = verify_token(token, _SECRET)
    assert payload["uid"] == "123"
    assert payload["name"] == "john"


def test_tampered_token_rejected():
    token = sign_token({"uid": "123"}, _SECRET)
    body, sig = token.split(".")
    assert verify_token(f"{body}x.{sig}", _SECRET) is None
    assert verify_token(f"{body}.{sig}x", _SECRET) is None


def test_wrong_secret_rejected():
    token = sign_token({"uid": "123"}, _SECRET)
    assert verify_token(token, "other-secret") is None


def test_expired_token_rejected():
    token = sign_token({"uid": "123"}, _SECRET, ttl=-1)
    assert verify_token(token, _SECRET) is None


def test_garbage_token_rejected():
    assert verify_token("not-a-token", _SECRET) is None
    assert verify_token("", _SECRET) is None


# --- Role to tier mapping ---

_ENV = {
    "DISCORD_EXEC_ROLE_IDS": "111,222",
    "DISCORD_ADMIN_ROLE_IDS": "999",
    "DISCORD_ADMIN_USER_IDS": "42",
}


def test_admin_user_id_wins():
    with patch.dict("os.environ", _ENV):
        assert tier_from_roles([], "42") == TIER_ADMIN


def test_admin_role_maps_to_admin():
    with patch.dict("os.environ", _ENV):
        assert tier_from_roles(["999", "111"], "1") == TIER_ADMIN


def test_exec_role_maps_to_exec():
    with patch.dict("os.environ", _ENV):
        assert tier_from_roles(["222"], "1") == TIER_EXEC


def test_guild_member_without_special_roles_is_member():
    with patch.dict("os.environ", _ENV):
        assert tier_from_roles(["777"], "1") == TIER_MEMBER
        assert tier_from_roles([], "1") == TIER_MEMBER


# --- Capability matrix ---

def test_member_cannot_plan_or_see_financial():
    a = access_for_tier(TIER_MEMBER, user_id="1")
    assert not a.can_plan and not a.financial_access
    assert not a.can_calendar and not a.can_gmail_send
    assert a.guarded and not a.is_admin


def test_exec_gets_plan_and_financial_but_not_gmail():
    a = access_for_tier(TIER_EXEC, user_id="1")
    assert a.can_plan and a.can_calendar and a.financial_access
    assert not a.can_gmail_send and not a.is_admin
    assert not a.guarded


def test_only_admin_can_gmail_send():
    for tier in (TIER_ANONYMOUS, TIER_MEMBER, TIER_EXEC):
        assert not access_for_tier(tier).can_gmail_send
    a = access_for_tier(TIER_ADMIN, user_id="1")
    assert a.can_gmail_send and a.is_admin


def test_anonymous_is_fully_restricted():
    a = access_for_tier(TIER_ANONYMOUS)
    assert not a.can_plan and not a.financial_access and a.guarded


# --- Legacy fallback (auth not configured) preserves DEMO_MODE semantics ---

def test_legacy_demo_mode_restricts_financial_but_allows_plan_docs():
    a = legacy_default(demo_mode=True)
    assert a.can_plan and not a.can_calendar and not a.can_gmail_send
    assert not a.financial_access and a.guarded


def test_legacy_full_mode_is_unrestricted():
    a = legacy_default(demo_mode=False)
    assert a.can_plan and a.can_calendar and a.can_gmail_send
    assert a.financial_access and not a.guarded
    assert not a.is_admin  # admin endpoints still need real auth
