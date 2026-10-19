"""Read-only direct-provider authentication/model checks; never run inference or infer billing tier."""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

if __package__:
    from .validate_repo import DIRECT_PROVIDER_MODELS
else:
    from validate_repo import DIRECT_PROVIDER_MODELS

ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/models",
    "google": "https://generativelanguage.googleapis.com/v1beta/models",
}
ENVIRONMENT_KEYS = {
    "groq": ("GROQ_API_KEY",),
    "google": ("GOOGLE_GENERATIVE_AI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"),
}


class AccessError(Exception):
    """A fixed, safe diagnostic without upstream bodies or credentials."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AccessError(
            "Provider redirected the credential request; stopped without forwarding credentials."
        )


def credential(provider, auth_path=None):
    """Use OpenCode's user credential store first; never accept an untrusted project path."""
    base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    path = Path(auth_path) if auth_path is not None else base / "opencode/auth.json"
    try:
        with path.open(encoding="utf-8") as stream:
            raw = stream.read(2_000_001)
        if len(raw) > 2_000_000:
            raise AccessError("User credential store is oversized; stopped.")
        auth = json.loads(raw)
        if not isinstance(auth, dict):
            raise ValueError
        entry = auth.get(provider, {})
        if not isinstance(entry, dict):
            raise ValueError
        key = entry.get("key") if entry.get("type") == "api" else None
    except FileNotFoundError:
        key = None
    except (OSError, ValueError):
        raise AccessError("User credential store could not be read safely.") from None
    if not key:
        key = next(
            (
                os.environ[name]
                for name in ENVIRONMENT_KEYS[provider]
                if os.environ.get(name)
            ),
            None,
        )
    if not isinstance(key, str) or not key.strip() or "\n" in key or "\r" in key:
        raise AccessError("No usable API key; connect the provider through OpenCode.")
    return key


def check(provider, key, opener=None):
    if provider not in ENDPOINTS:
        raise AccessError("Unreviewed provider rejected.")
    headers = {"User-Agent": "opencode/1.19.3", "Accept": "application/json"}
    headers.update(
        {"Authorization": "Bearer " + key}
        if provider == "groq"
        else {"x-goog-api-key": key}
    )
    request = Request(ENDPOINTS[provider], headers=headers, method="GET")
    opener = opener or build_opener(NoRedirects())
    try:
        with opener.open(request, timeout=20) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise AccessError("Provider model list is oversized; stopped.")
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise ValueError
        entries = body.get("data" if provider == "groq" else "models")
        if not isinstance(entries, list) or not all(
            isinstance(entry, dict) for entry in entries
        ):
            raise ValueError
        ids = {entry.get("id" if provider == "groq" else "name") for entry in entries}
        expected = DIRECT_PROVIDER_MODELS[provider]
        missing = [
            mid
            for mid in sorted(expected)
            if (mid if provider == "groq" else "models/" + mid) not in ids
        ]
        if missing:
            raise AccessError("Reviewed model unavailable: " + ", ".join(missing))
        return sorted(expected)
    except HTTPError as error:
        raise AccessError(
            f"Provider model-list HTTP {error.code}; no inference or fallback attempted."
        ) from None
    except (URLError, OSError, ValueError, TypeError):
        raise AccessError(
            "Provider model list could not be verified; raw errors withheld."
        ) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=sorted(ENDPOINTS))
    args = parser.parse_args()
    failed = False
    for provider in [args.provider] if args.provider else sorted(ENDPOINTS):
        try:
            models = check(provider, credential(provider))
            print(
                provider
                + ": authentication/model availability PASS: "
                + ", ".join(models)
            )
        except AccessError as error:
            failed = True
            print(provider + ": " + str(error), file=sys.stderr)
    print(
        "Read-only GETs only. Billing tier, remaining quota, tool calling and inference are not verified."
    )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
