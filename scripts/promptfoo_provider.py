"""Synthetic evaluation adapter; offline fixtures are the default, never model results."""

import os
from pathlib import Path

if __package__:
    from .answer_team import TeamError, answer_team, validate_request
else:
    from answer_team import TeamError, answer_team, validate_request

ROOT = Path(__file__).resolve().parents[1]


def call_api(prompt, options, context):
    config = options.get("config", {})
    route = config.get("route", "direct")
    if route not in {"direct", "review"}:
        return {
            "error": "Only direct and fully synthesized review routes are supported."
        }
    variables = context.get("vars", {})
    evidence = variables.get("evidence", "")
    try:
        validate_request(prompt, evidence, route, "supplied")
        if os.environ.get("ANSWER_EVAL_LIVE") != "1":
            fixture = variables.get("fixture_output")
            if not isinstance(fixture, str) or not fixture:
                return {
                    "error": "Offline evaluation requires a synthetic fixture output."
                }
            return {
                "output": fixture,
                "metadata": {"execution": "offline_fixture", "route": route},
            }
        result = answer_team(prompt, evidence, route, ROOT, evidence_scope="supplied")
        if result.get("synthesis_required"):
            return {"error": "Unsynthesized drafts cannot be scored as final answers."}
        return {
            "output": result["answer"],
            "metadata": {
                "execution": "live",
                "route": route,
                "elapsed_seconds": result.get("elapsed_seconds"),
                "preflight_seconds": result.get("preflight_seconds"),
                "usage": result.get("usage"),
                "usage_scope": result.get("usage_scope"),
                "stages": result.get("stages", []),
                "truncation": result.get("truncation"),
                "independent_critique_completed": result.get(
                    "independent_critique_completed", False
                ),
            },
        }
    except TeamError:
        return {
            "error": "Guarded answer controller rejected or failed this evaluation."
        }
    except OSError:
        return {"error": "Local evaluation execution failed."}
