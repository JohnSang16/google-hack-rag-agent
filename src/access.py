"""Access tiers and per-tier capabilities.

Tier model (roadmap Section 7):
  anonymous  public visitor, no login. Demo experience: RECALL/ANALYZE with
             financial data restricted, no artifact creation.
  member     verified club member (in the Discord server). RECALL/ANALYZE only,
             financial data excluded, standard guards apply.
  exec       exec board Discord role. Adds PLAN mode (Doc + Calendar creation)
             and financial data with an internal-figures caveat.
  admin      top-level role or allowlisted user id. Adds Gmail send and the
             /admin endpoints.

Identity comes from Discord OAuth (src/api/auth.py). This module stays free of
FastAPI and Discord imports so the agent layer can depend on it cleanly.

TODO (permission overrides): normal members sometimes need admin-level access
for specific work (e.g. running a re-sync while owning an event). Planned as an
`access_overrides` collection in Atlas keyed by Discord user id with an expiry,
checked after role mapping in auth.resolve_tier, plus an admin endpoint to
grant/revoke. Not built yet; tiers come only from roles for now.
"""
import os
from dataclasses import dataclass
from typing import Optional

TIER_ANONYMOUS = "anonymous"
TIER_MEMBER = "member"
TIER_EXEC = "exec"
TIER_ADMIN = "admin"

_DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"


@dataclass(frozen=True)
class Access:
    tier: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    can_plan: bool = False
    can_calendar: bool = False
    can_gmail_send: bool = False
    financial_access: bool = False
    guarded: bool = True  # rate limiting and the query blocklist apply
    is_admin: bool = False

    def as_dict(self) -> dict:
        return {
            "tier": self.tier,
            "username": self.username,
            "can_plan": self.can_plan,
            "can_calendar": self.can_calendar,
            "can_gmail_send": self.can_gmail_send,
            "financial_access": self.financial_access,
        }


def access_for_tier(tier: str, user_id: Optional[str] = None, username: Optional[str] = None) -> Access:
    """Capability matrix for authenticated deployments."""
    if tier == TIER_ADMIN:
        return Access(tier, user_id, username, can_plan=True, can_calendar=True,
                      can_gmail_send=True, financial_access=True, guarded=False, is_admin=True)
    if tier == TIER_EXEC:
        return Access(tier, user_id, username, can_plan=True, can_calendar=True,
                      can_gmail_send=False, financial_access=True, guarded=False)
    if tier == TIER_MEMBER:
        return Access(tier, user_id, username)
    return Access(TIER_ANONYMOUS)


def legacy_default(demo_mode: Optional[bool] = None) -> Access:
    """Behavior when Discord auth is not configured: preserve the original
    deployment-wide DEMO_MODE semantics so nothing changes until auth env
    vars are set. Demo keeps PLAN doc creation on (the recorded demo relies
    on it); the authenticated anonymous tier is stricter."""
    demo = _DEMO_MODE if demo_mode is None else demo_mode
    if demo:
        return Access(TIER_ANONYMOUS, can_plan=True)
    return Access(TIER_ANONYMOUS, can_plan=True, can_calendar=True,
                  can_gmail_send=True, financial_access=True, guarded=False)
