"""Reviewed free-account guard and fixed runner-up selection. No inference or billing changes."""

import hashlib
import json
import os
from datetime import date
from pathlib import Path

if __package__:
    from .check_provider_access import AccessError, ENVIRONMENT_KEYS, credential
    from .validate_repo import ROLE_MODELS
else:
    from check_provider_access import AccessError, ENVIRONMENT_KEYS, credential
    from validate_repo import ROLE_MODELS


class RoutingError(Exception):
    """Safe routing error without credentials or upstream details."""


def confirmation_path():
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share")))
    return base / "EmdashAnswerTeam/free-tier-accounts.local.json"


def approved_environment(model, environment, path=None):
    """Bind owner free-tier confirmation to the exact key; fail closed after 30 days.

    This is an owner assertion, never a provider billing audit. The interactive
    OpenCode UI bypasses this controller and still needs owner billing controls.
    """
    provider = model.split("/", 1)[0]
    if provider == "openrouter":
        return environment
    if provider not in ENVIRONMENT_KEYS:
        raise RoutingError("Unreviewed inference provider rejected.")
    try:
        with (Path(path) if path is not None else confirmation_path()).open(
            encoding="utf-8"
        ) as stream:
            raw = stream.read(16001)
        if len(raw) > 16000:
            raise ValueError
        confirmation = json.loads(raw)[provider]
        if not isinstance(confirmation, dict):
            raise ValueError
        age = (date.today() - date.fromisoformat(confirmation["confirmed_on"])).days
        key = credential(provider)
        if (
            confirmation.get("free_tier") is not True
            or confirmation.get("paid_billing_disabled") is not True
            or not 0 <= age <= 30
            or confirmation.get("key_sha256")
            != hashlib.sha256(key.encode()).hexdigest()
        ):
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError, AccessError):
        raise RoutingError(
            "Direct-provider free-tier confirmation is missing, expired or does not match the current key; stop and reconfirm billing status."
        ) from None
    result = dict(environment)
    # Bind SDK environment aliases to the same checked credential. No key in args/logs.
    for name in ENVIRONMENT_KEYS[provider]:
        result[name] = key
    return result


def candidates(agent):
    if agent not in ROLE_MODELS:
        raise RoutingError("Unreviewed role rejected.")
    return ROLE_MODELS[agent]
