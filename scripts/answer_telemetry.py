"""Optional isolated metadata-only Langfuse exporter; never receives answer prose."""

import argparse
import base64
import json
import logging
import math
import os
import re
import sys
import time
from urllib.parse import urlsplit

if __package__:
    from .validate_repo import ROLE_MODELS
else:
    from validate_repo import ROLE_MODELS

REQUEST_NAME = "answer-team.request"
STAGE_NAME = "answer-team.stage"
MAX_PAYLOAD = 64000
NETWORK_TIMEOUT = 5
TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)
ROUTES = {"auto", "direct", "review", "research", "consult"}
SCOPES = {"repository", "supplied"}
ROLES = {"answer-coordinator", "answer-critic", "researcher"}
STATUSES = {"completed", "availability_failure", "skipped_for_independence"}


def number(value, integer=False):
    return (
        (type(value) is int if integer else type(value) in (int, float))
        and 0 <= value <= 10**12
        and math.isfinite(value)
    )


def usage_metadata(source):
    """Keep observed subtotals and coverage; do not invent missing counts."""
    if not isinstance(source, dict):
        return {}
    result = {
        field: source[field]
        for field in (*TOKEN_FIELDS, "steps", "steps_with_token_counts")
        if number(source.get(field), integer=True)
    }
    for field in ("token_counts_observed",):
        if type(source.get(field)) is bool:
            result[field] = source[field]
    for field, integer in (
        ("token_field_steps", True),
        ("token_fields_observed", False),
    ):
        values = source.get(field)
        if isinstance(values, dict):
            result[field] = {
                key: values[key]
                for key in TOKEN_FIELDS
                if (
                    number(values.get(key), integer=True)
                    if integer
                    else type(values.get(key)) is bool
                )
            }
    return result


def stage_metadata(source):
    if (
        not isinstance(source, dict)
        or not isinstance(source.get("agent"), str)
        or source["agent"] not in ROLES
    ):
        return None
    role = source["agent"]
    if source.get("model") not in ROLE_MODELS[role]:
        return None
    result = {"agent": role, "model": source["model"]}
    for field in ("elapsed_seconds", "successful_attempt_seconds"):
        if number(source.get(field)):
            result[field] = source[field]
    if isinstance(source.get("usage"), dict):
        result["usage"] = usage_metadata(source["usage"])
    attempts = source.get("attempts")
    if isinstance(attempts, list):
        result["attempts"] = []
        for attempt in attempts[:2]:
            if (
                isinstance(attempt, dict)
                and attempt.get("model") in ROLE_MODELS[role]
                and isinstance(attempt.get("status"), str)
                and attempt["status"] in STATUSES
            ):
                clean = {key: attempt[key] for key in ("model", "status")}
                if type(attempt.get("usage_unknown")) is bool:
                    clean["usage_unknown"] = attempt["usage_unknown"]
                result["attempts"].append(clean)
    return result


def sanitize_metadata(source, route=None):
    """Copy selected typed values only; never serialize arbitrary answer fields."""
    if not isinstance(source, dict):
        raise ValueError("Invalid metadata.")
    route = source.get("route") if route is None else route
    if (
        not isinstance(route, str)
        or route not in ROUTES
        or not isinstance(source.get("evidence_scope"), str)
        or source["evidence_scope"] not in SCOPES
    ):
        raise ValueError("Invalid route or evidence scope.")
    result = {
        "schema_version": 1,
        "route": route,
        "evidence_scope": source["evidence_scope"],
    }
    if isinstance(source.get("status"), str) and source["status"] in {
        "completed",
        "failed",
    }:
        result["status"] = source["status"]
    for field in ("elapsed_seconds", "preflight_seconds"):
        if number(source.get(field)):
            result[field] = source[field]
    if number(source.get("model_stages"), integer=True) and source["model_stages"] <= 3:
        result["model_stages"] = source["model_stages"]
    for field in ("independent_critique_completed", "synthesis_required"):
        if type(source.get(field)) is bool:
            result[field] = source[field]
    if isinstance(source.get("usage"), dict):
        result["usage"] = usage_metadata(source["usage"])
    truncation = source.get("truncation")
    if isinstance(truncation, dict):
        result["truncation"] = {
            field: truncation[field]
            for field in ("draft", "critique")
            if type(truncation.get(field)) is bool
        }
    stages = source.get("stages")
    if isinstance(stages, list):
        result["stages"] = [
            clean
            for stage in stages[:3]
            if (clean := stage_metadata(stage)) is not None
        ]
    return result


def configured():
    if os.environ.get("ANSWER_TEAM_LANGFUSE") != "1":
        return False
    base = os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST", "")
    parsed = urlsplit(base)
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_SECRET_KEY")
        and parsed.scheme == "https"
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )


def field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def flattened_metadata(value, prefix=""):
    """The v2 observation API returns nested metadata as dotted leaf keys."""
    if isinstance(value, dict):
        entries = value.items()
    else:
        return {prefix: value}
    result = {}
    for key, item in entries:
        result.update(
            flattened_metadata(item, f"{prefix}.{key}" if prefix else str(key))
        )
    return result


def observations_match(response, trace_id, expected):
    """Delivery alone is insufficient: verify returned content and exact metadata."""
    observations = field(response, "data")
    if not isinstance(observations, list) or len(observations) != len(expected):
        return False
    seen = set()
    for observation in observations:
        identity = field(observation, "id")
        if identity not in expected or identity in seen:
            return False
        seen.add(identity)
        name, metadata = expected[identity]
        parent = field(observation, "parent_observation_id")
        root_id = next(key for key, item in expected.items() if item[0] == REQUEST_NAME)
        observed_metadata = field(observation, "metadata")
        if isinstance(observed_metadata, dict):
            observed_metadata = dict(observed_metadata)
            for key, value in (
                ("scope.name", "answer-team.metadata"),
                ("scope.version", "1"),
                ("attributes.langfuse.trace.name", REQUEST_NAME),
                ("attributes.langfuse.observation.type", "span"),
            ):
                if observed_metadata.get(key) == value:
                    observed_metadata.pop(key)
            if (
                type(observed_metadata.get("scope.version")) is int
                and observed_metadata["scope.version"] == 1
            ):
                observed_metadata.pop("scope.version")
        if (
            field(observation, "name") != name
            or field(observation, "trace_id") != trace_id
            or any(
                field(observation, key) not in (None, "")
                for key in ("input", "output", "user_id", "session_id")
            )
            or observed_metadata not in (metadata, flattened_metadata(metadata))
            or parent != (root_id if name == STAGE_NAME else None)
        ):
            return False
    return True


def isolated_exporter(
    delegate, span_type, resource_type, scope_type, exporter_base=object
):
    """Also remove SDK instrumentation identity: it can contain a public project key."""

    class Exporter(exporter_base):
        def export(self, spans):
            clean = [
                span_type(
                    name=span.name,
                    context=span.context,
                    parent=span.parent,
                    start_time=span.start_time,
                    end_time=span.end_time,
                    attributes={
                        key: value
                        for key, value in span.attributes.items()
                        if key
                        in {
                            "langfuse.observation.type",
                            "langfuse.observation.metadata",
                            "langfuse.trace.name",
                        }
                    },
                    resource=resource_type({}),
                    instrumentation_scope=scope_type(
                        "answer-team.metadata", "1", attributes={}
                    ),
                    events=(),
                    links=(),
                )
                for span in spans
                if span.name in {REQUEST_NAME, STAGE_NAME}
            ]
            return delegate.export(clean)

        def shutdown(self):
            return delegate.shutdown()

        def force_flush(self, timeout_millis=30000):
            return delegate.force_flush(timeout_millis)

    return Exporter()


def emit_metadata(payload, verify=False):
    """Run in an isolated child only. Fixed safe statuses never reveal upstream errors."""
    provider = None
    try:
        if not configured():
            return {"status": "disabled"}
        clean = sanitize_metadata(payload)
        # Optional SDK imports must never affect normal answer startup.
        from langfuse import Langfuse
        from langfuse.types import MaskOtelSpansResult, OtelSpanPatch
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
        from opentelemetry.sdk.trace.export import SpanExporter
        from opentelemetry.sdk.util.instrumentation import InstrumentationScope
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        expected = {}
        trace_id = None

        def should_export(span):
            context = span.context
            return bool(
                span.name in {REQUEST_NAME, STAGE_NAME}
                and f"{context.trace_id:032x}" == trace_id
                and f"{context.span_id:016x}" in expected
                and not dict(span.resource.attributes)
                and not span.events
                and not span.links
                and not span.status.description
            )

        def mask_spans(*, params):
            patches = {}
            for identity, span in params.spans.items():
                entry = expected.get(span.span_id)
                if (
                    entry is None
                    or span.trace_id != trace_id
                    or span.resource_attributes
                ):
                    patches[identity] = None
                    continue
                _, metadata = entry
                patches[identity] = OtelSpanPatch(
                    delete_attributes=tuple(span.attributes),
                    set_attributes={
                        "langfuse.observation.type": "span",
                        "langfuse.observation.metadata": json.dumps(
                            metadata, allow_nan=False
                        ),
                        "langfuse.trace.name": REQUEST_NAME,
                    },
                )
            return MaskOtelSpansResult(span_patches=patches)

        provider = TracerProvider(resource=Resource({}), shutdown_on_exit=False)
        base_url = os.environ.get("LANGFUSE_BASE_URL") or os.environ["LANGFUSE_HOST"]
        auth = base64.b64encode(
            (
                os.environ["LANGFUSE_PUBLIC_KEY"]
                + ":"
                + os.environ["LANGFUSE_SECRET_KEY"]
            ).encode()
        ).decode()
        exporter = isolated_exporter(
            OTLPSpanExporter(
                endpoint=base_url.rstrip("/") + "/api/public/otel/v1/traces",
                headers={
                    "Authorization": "Basic " + auth,
                    "x-langfuse-ingestion-version": "4",
                },
                timeout=NETWORK_TIMEOUT,
            ),
            ReadableSpan,
            Resource,
            InstrumentationScope,
            SpanExporter,
        )
        if not isinstance(exporter, SpanExporter):
            raise TypeError("Invalid telemetry exporter interface.")
        client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            base_url=os.environ.get("LANGFUSE_BASE_URL") or os.environ["LANGFUSE_HOST"],
            timeout=NETWORK_TIMEOUT,
            debug=False,
            tracing_enabled=True,
            sample_rate=1.0,
            environment="answer-team",
            release="metadata-v1",
            flush_at=100,
            flush_interval=60,
            tracer_provider=provider,
            span_exporter=exporter,
            should_export_span=should_export,
            mask_otel_spans=mask_spans,
        )
        root_metadata = {key: value for key, value in clean.items() if key != "stages"}
        root = client.start_observation(name=REQUEST_NAME, metadata=root_metadata)
        trace_id = root.trace_id
        expected[root.id] = (REQUEST_NAME, root_metadata)
        for metadata in clean.get("stages", []):
            span = client.start_observation(
                trace_context={"trace_id": trace_id, "parent_span_id": root.id},
                name=STAGE_NAME,
                metadata=metadata,
            )
            expected[span.id] = (STAGE_NAME, metadata)
            span.end()
        root.end()
        client.flush()
        if not isinstance(trace_id, str) or not re.fullmatch(r"[0-9a-f]{32}", trace_id):
            return {"status": "failed"}
        if verify:
            for attempt in range(8):
                try:
                    response = client.api.observations.get_many(
                        trace_id=trace_id,
                        fields="core,basic,io,metadata,trace_context",
                        expand_metadata=",".join(
                            sorted(
                                {
                                    key
                                    for _, metadata in expected.values()
                                    for key in metadata
                                }
                            )
                        ),
                        limit=10,
                    )
                    if observations_match(response, trace_id, expected):
                        return {"status": "verified", "trace_id": trace_id}
                except Exception:
                    pass
                if attempt < 7:
                    time.sleep(2)
            return {"status": "failed"}
        return {"status": "submitted", "trace_id": trace_id}
    except Exception:
        return {"status": "failed"}
    finally:
        if provider is not None:
            try:
                provider.shutdown()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit", action="store_true")
    mode.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    # The isolated worker must never expose SDK logs or upstream response bodies.
    logging.disable(logging.CRITICAL)
    try:
        if args.smoke:
            payload = {
                "route": "direct",
                "evidence_scope": "supplied",
                "model_stages": 1,
                "elapsed_seconds": 0,
                "stages": [
                    {
                        "agent": "answer-coordinator",
                        "model": ROLE_MODELS["answer-coordinator"][0],
                        "elapsed_seconds": 0,
                        "attempts": [
                            {
                                "model": ROLE_MODELS["answer-coordinator"][0],
                                "status": "completed",
                            }
                        ],
                        "usage": {"token_counts_observed": False},
                    }
                ],
            }
        else:
            raw = sys.stdin.read(MAX_PAYLOAD + 1)
            if len(raw) > MAX_PAYLOAD:
                return 0
            payload = json.loads(raw)
        result = emit_metadata(payload, verify=args.smoke)
    except Exception:
        result = {"status": "failed"}
    if args.smoke:
        print(json.dumps(result))
        return 0 if result["status"] == "verified" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
