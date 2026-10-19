"""Check the public OpenRouter catalog without authentication or model inference."""

import json
import sys
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOG_URL = "https://openrouter.ai/api/v1/models"


def model_errors(config, catalog, today=None, *, model_ids=None):
    today = today or date.today()
    if not isinstance(catalog, dict) or not isinstance(catalog.get("data"), list):
        raise ValueError("Invalid model catalog structure.")
    entries = {}
    for model in catalog["data"]:
        if (
            not isinstance(model, dict)
            or not isinstance(model.get("id"), str)
            or not model["id"]
            or model["id"] in entries
        ):
            raise ValueError("Invalid or duplicate model catalog identity.")
        entries[model["id"]] = model
    errors = []
    whitelist = config["provider"]["openrouter"]["whitelist"]
    for model_id in whitelist if model_ids is None else model_ids:
        if model_id not in whitelist:
            errors.append(f"{model_id}: not in the reviewed whitelist")
            continue
        model = entries.get(model_id)
        if not model:
            errors.append(
                f"{model_id}: unavailable; stop instead of selecting a paid replacement"
            )
            continue
        pricing = model.get("pricing", {})
        try:
            if (
                not isinstance(pricing, dict)
                or not {"prompt", "completion"} <= pricing.keys()
                or any(Decimal(str(value)) != 0 for value in pricing.values())
            ):
                errors.append(f"{model_id}: missing or nonzero pricing")
        except (InvalidOperation, TypeError, ValueError):
            errors.append(f"{model_id}: pricing cannot be verified")
        parameters = model.get("supported_parameters")
        if (
            not isinstance(parameters, list)
            or not all(isinstance(item, str) for item in parameters)
            or "tools" not in parameters
        ):
            errors.append(f"{model_id}: tool support unavailable")
        expires = model.get("expiration_date")
        if expires is not None:
            try:
                if not isinstance(expires, str):
                    raise ValueError
                if date.fromisoformat(expires) <= today + timedelta(days=14):
                    errors.append(
                        f"{model_id}: expires within 14 days; replace explicitly"
                    )
            except ValueError:
                errors.append(f"{model_id}: invalid expiry metadata")
    return errors


def main():
    config = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
    request = Request(
        CATALOG_URL, headers={"User-Agent": "repository-model-preflight/1.0"}
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read(20_000_001)
        if len(raw) > 20_000_000:
            raise ValueError("oversize catalog")
        errors = model_errors(config, json.loads(raw))
    except (URLError, OSError, ValueError, KeyError, TypeError):
        print(
            "Public catalog could not be verified. No inference was run; retry later.",
            file=sys.stderr,
        )
        return 1
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print(
            "Configured OpenRouter endpoints exist, support tools, and report zero pricing; no inference run."
        )
        if set(config.get("provider", {})) - {"openrouter"}:
            print(
                "Direct providers use owner-confirmed account free tiers, not zero-priced OpenRouter variants; "
                "run scripts/check_provider_access.py and verify account billing separately."
            )
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
