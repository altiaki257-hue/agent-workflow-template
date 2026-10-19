"""Metadata privacy boundaries without an installed SDK or external requests."""

import copy
import io
import json
import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import answer_telemetry as telemetry


MODEL = telemetry.ROLE_MODELS["researcher"][0]
PAYLOAD = {
    "route": "consult",
    "evidence_scope": "supplied",
    "elapsed_seconds": 2.5,
    "model_stages": 2,
    "independent_critique_completed": True,
    "synthesis_required": True,
    "usage": {
        "input_tokens": 12,
        "output_tokens": 3,
        "token_counts_observed": False,
        "token_fields_observed": {"input_tokens": True, "output_tokens": True},
        "token_field_steps": {"input_tokens": 1},
    },
    "stages": [
        {
            "agent": "researcher",
            "model": MODEL,
            "elapsed_seconds": 1.5,
            "attempts": [{"model": MODEL, "status": "completed"}],
            "usage": {"input_tokens": 12, "token_counts_observed": False},
        }
    ],
}
ENV = {
    "ANSWER_TEAM_LANGFUSE": "1",
    "LANGFUSE_PUBLIC_KEY": "synthetic-public",
    "LANGFUSE_SECRET_KEY": "synthetic-secret",
    "LANGFUSE_BASE_URL": "https://example.invalid",
}


class FakeSdk:
    def __init__(self):
        self.options = None
        self.calls = []
        self.ended = []
        self.patches = None
        self.closed = False
        self.reads = 0
        self.failure = None
        self.mutate_trace = lambda trace: trace
        owner = self

        class Resource:
            def __init__(self, attributes):
                self.attributes = attributes

        class TracerProvider:
            def __init__(self, **kwargs):
                self.resource = kwargs["resource"]
                owner.provider_options = kwargs

            def shutdown(self):
                owner.closed = True

        class Span:
            trace_id = "a" * 32

            def __init__(self, kwargs):
                self.id = f"{len(owner.calls) + 1:016x}"
                self.kwargs = kwargs

            def end(self):
                owner.ended.append(self)

        class Langfuse:
            def __init__(self, **kwargs):
                owner.options = kwargs
                self.api = SimpleNamespace(
                    observations=SimpleNamespace(get_many=self.get_many)
                )

            def start_observation(self, **kwargs):
                if owner.failure == "start":
                    raise RuntimeError("private upstream error")
                span = Span(kwargs)
                owner.calls.append(span)
                return span

            def flush(self):
                if owner.failure == "flush":
                    raise RuntimeError("private upstream error")
                spans = {}
                for span in owner.ended:
                    context = SimpleNamespace(
                        trace_id=int(span.trace_id, 16), span_id=int(span.id, 16)
                    )
                    readable = SimpleNamespace(
                        name=span.kwargs["name"],
                        context=context,
                        resource=owner.options["tracer_provider"].resource,
                        events=(),
                        links=(),
                        status=SimpleNamespace(description=None),
                    )
                    if owner.options["should_export_span"](readable):
                        spans[span.id] = SimpleNamespace(
                            trace_id=span.trace_id,
                            span_id=span.id,
                            name=span.kwargs["name"],
                            resource_attributes={},
                            attributes={
                                "langfuse.observation.metadata": "UNTRUSTED",
                                "langfuse.observation.input": "PRIVATE INPUT",
                                "langfuse.observation.output": "PRIVATE OUTPUT",
                                "langfuse.release": "PRIVATE PATH",
                                "unknown": "PRIVATE UNKNOWN",
                            },
                        )
                owner.patches = owner.options["mask_otel_spans"](
                    params=SimpleNamespace(spans=spans)
                )

            def get_many(self, **kwargs):
                owner.read_options = kwargs
                owner.reads += 1
                if owner.failure == "read" or (
                    owner.failure == "delayed" and owner.reads == 1
                ):
                    raise RuntimeError("private upstream error")
                observations = [
                    {
                        "id": span.id,
                        "trace_id": span.trace_id,
                        "name": span.kwargs["name"],
                        "input": None,
                        "output": None,
                        "metadata": json.loads(
                            owner.patches.span_patches[span.id].set_attributes[
                                "langfuse.observation.metadata"
                            ]
                        ),
                        "parent_observation_id": span.kwargs.get(
                            "trace_context", {}
                        ).get("parent_span_id"),
                    }
                    for span in owner.calls
                ]
                trace = owner.mutate_trace(
                    {
                        "name": telemetry.REQUEST_NAME,
                        "metadata": {},
                        "input": None,
                        "output": None,
                        "observations": observations,
                    }
                )
                return {"data": trace["observations"]}

        modules = {
            "langfuse": {"Langfuse": Langfuse},
            "langfuse.types": {
                "MaskOtelSpansResult": SimpleNamespace,
                "OtelSpanPatch": SimpleNamespace,
            },
            "opentelemetry.sdk.resources": {"Resource": Resource},
            "opentelemetry.sdk.trace": {
                "TracerProvider": TracerProvider,
                "ReadableSpan": SimpleNamespace,
            },
            "opentelemetry.sdk.trace.export": {"SpanExporter": object},
            "opentelemetry.sdk.util.instrumentation": {
                "InstrumentationScope": lambda *args, **kwargs: SimpleNamespace(
                    name=args[0], version=args[1], **kwargs
                )
            },
            "opentelemetry.exporter.otlp.proto.http.trace_exporter": {
                "OTLPSpanExporter": lambda **kwargs: SimpleNamespace(**kwargs)
            },
        }
        self.modules = {}
        for name, values in modules.items():
            module = types.ModuleType(name)
            module.__dict__.update(values)
            self.modules[name] = module


class AnswerTelemetryTests(unittest.TestCase):
    def test_v2_flat_metadata_and_fixed_enrichment_are_verified_but_credentials_are_not(
        self,
    ):
        def v2_shape(trace):
            for row in trace["observations"]:
                metadata = row["metadata"]
                flattened = {}
                pending = list(metadata.items())
                while pending:
                    key, value = pending.pop()
                    if isinstance(value, dict):
                        pending.extend(
                            (key + "." + child, item) for child, item in value.items()
                        )
                    else:
                        flattened[key] = value
                row["metadata"] = {
                    **flattened,
                    "scope.name": "answer-team.metadata",
                    "scope.version": 1,
                    "attributes.langfuse.trace.name": telemetry.REQUEST_NAME,
                    "attributes.langfuse.observation.type": "span",
                }
                row["user_id"] = row["session_id"] = ""
            return trace

        sdk = FakeSdk()
        sdk.mutate_trace = v2_shape
        self.assertEqual("verified", self.emit(sdk, verify=True)["status"])

        def with_key(trace):
            trace = v2_shape(trace)
            trace["observations"][0]["metadata"]["scope.attributes.public_key"] = (
                "PRIVATE"
            )
            return trace

        sdk = FakeSdk()
        sdk.mutate_trace = with_key
        self.assertEqual("failed", self.emit(sdk, verify=True)["status"])

    def test_wire_export_removes_scope_credentials_resources_events_and_links(self):
        from unittest.mock import Mock

        delegate = Mock()

        def scope(name, version, **kwargs):
            return SimpleNamespace(name=name, version=version, **kwargs)

        exporter = telemetry.isolated_exporter(
            delegate,
            SimpleNamespace,
            lambda attrs: SimpleNamespace(attributes=attrs),
            scope,
        )
        exporter.export(
            [
                SimpleNamespace(
                    name=telemetry.REQUEST_NAME,
                    context="context",
                    parent=None,
                    start_time=1,
                    end_time=2,
                    attributes={
                        "langfuse.observation.type": "span",
                        "unexpected": "PRIVATE",
                    },
                    instrumentation_scope=SimpleNamespace(
                        attributes={"public_key": "PRIVATE"}
                    ),
                    resource=SimpleNamespace(attributes={"host": "PRIVATE"}),
                    events=["PRIVATE"],
                    links=["PRIVATE"],
                )
            ]
        )
        span = delegate.export.call_args.args[0][0]
        self.assertNotIn("PRIVATE", str(vars(span)))
        self.assertEqual({}, span.instrumentation_scope.attributes)
        self.assertEqual({}, span.resource.attributes)
        self.assertEqual((), span.events)
        self.assertEqual((), span.links)

    def emit(self, sdk, verify=False, payload=None):
        with (
            patch.dict(os.environ, ENV, clear=True),
            patch.dict(sys.modules, sdk.modules),
            patch.object(telemetry.time, "sleep"),
        ):
            return telemetry.emit_metadata(payload or PAYLOAD, verify=verify)

    def test_disabled_and_missing_configuration_never_import_sdk(self):
        for environment in (
            {},
            {**ENV, "ANSWER_TEAM_LANGFUSE": "0"},
            {**ENV, "LANGFUSE_SECRET_KEY": ""},
        ):
            with (
                patch.dict(os.environ, environment, clear=True),
                patch.dict(sys.modules, {"langfuse": None}),
            ):
                self.assertEqual(
                    {"status": "disabled"}, telemetry.emit_metadata(PAYLOAD)
                )

    def test_sanitizer_excludes_prose_paths_credentials_unknown_nested_values(self):
        source = copy.deepcopy(PAYLOAD)
        source.update(
            question="PRIVATE",
            context="PRIVATE",
            answer="PRIVATE",
            draft="PRIVATE",
            critique="PRIVATE",
            error="PRIVATE",
            path="PRIVATE",
        )
        source["usage"].update(secret="PRIVATE", reported_cost_usd=99)
        source["stages"][0].update(error="PRIVATE", prompt="PRIVATE")
        source["stages"][0]["attempts"][0]["raw_error"] = "PRIVATE"
        clean = telemetry.sanitize_metadata(source)
        self.assertNotIn("PRIVATE", json.dumps(clean))
        self.assertNotIn("reported_cost_usd", clean["usage"])
        self.assertEqual(clean, telemetry.sanitize_metadata(clean))
        self.assertNotIn("reasoning_tokens", clean["usage"])
        self.assertFalse(clean["usage"]["token_counts_observed"])

    def test_unknown_identifiers_and_invalid_numeric_values_cannot_escape(self):
        for value in ([], None, "PRIVATE", True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    telemetry.sanitize_metadata(
                        {"route": value, "evidence_scope": "supplied"}
                    )
        source = copy.deepcopy(PAYLOAD)
        source["stages"] += [
            {"agent": "PRIVATE", "model": "PRIVATE"},
            {"agent": [], "model": "PRIVATE"},
        ]
        source["usage"].update(
            input_tokens=True,
            output_tokens=-1,
            reasoning_tokens=float("inf"),
            cache_read_tokens=10**400,
        )
        clean = telemetry.sanitize_metadata(source)
        self.assertEqual(1, len(clean["stages"]))
        self.assertFalse(any(key in clean["usage"] for key in telemetry.TOKEN_FIELDS))

    def test_failure_status_retains_no_error_prose_or_invented_usage(self):
        for status in ("completed", "failed", "PRIVATE ERROR", [], None):
            source = {
                "route": "consult",
                "evidence_scope": "supplied",
                "status": status,
                "error": "PRIVATE ERROR",
                "question": "PRIVATE QUESTION",
            }
            clean = telemetry.sanitize_metadata(source)
            self.assertNotIn("PRIVATE", json.dumps(clean))
            self.assertNotIn("usage", clean)
            self.assertNotIn("stages", clean)
            self.assertNotIn("model_stages", clean)
            if status in ("completed", "failed"):
                self.assertEqual(status, clean["status"])
            else:
                self.assertNotIn("status", clean)

    def test_private_provider_filter_and_export_mask_remove_all_unknown_attributes(
        self,
    ):
        sdk = FakeSdk()
        result = self.emit(sdk)
        self.assertEqual("submitted", result["status"])
        self.assertEqual(telemetry.NETWORK_TIMEOUT, sdk.options["timeout"])
        self.assertEqual({}, sdk.provider_options["resource"].attributes)
        self.assertFalse(sdk.provider_options["shutdown_on_exit"])
        self.assertEqual(
            [telemetry.REQUEST_NAME, telemetry.STAGE_NAME],
            [span.kwargs["name"] for span in sdk.calls],
        )
        self.assertEqual(
            sdk.calls[0].id, sdk.calls[1].kwargs["trace_context"]["parent_span_id"]
        )
        for patch_value in sdk.patches.span_patches.values():
            self.assertEqual(
                {
                    "langfuse.observation.type",
                    "langfuse.observation.metadata",
                    "langfuse.trace.name",
                },
                set(patch_value.set_attributes),
            )
            self.assertIn("langfuse.observation.input", patch_value.delete_attributes)
            self.assertIn("langfuse.release", patch_value.delete_attributes)
            self.assertNotIn("PRIVATE", json.dumps(patch_value.set_attributes))
        allowed = sdk.options["should_export_span"]
        for name, identity, resource in (
            ("third-party", "1", {}),
            (telemetry.REQUEST_NAME, "ff", {}),
            (telemetry.REQUEST_NAME, "1", {"host.name": "PRIVATE"}),
        ):
            self.assertFalse(
                allowed(
                    SimpleNamespace(
                        name=name,
                        context=SimpleNamespace(
                            trace_id=int("a" * 32, 16), span_id=int(identity, 16)
                        ),
                        resource=SimpleNamespace(attributes=resource),
                        events=(),
                        links=(),
                        status=SimpleNamespace(description=None),
                    )
                )
            )
        self.assertTrue(sdk.closed)

    def test_sdk_absence_and_export_failures_are_safe_fixed_statuses(self):
        with (
            patch.dict(os.environ, ENV, clear=True),
            patch.dict(sys.modules, {"langfuse": None}),
        ):
            self.assertEqual({"status": "failed"}, telemetry.emit_metadata(PAYLOAD))
        for failure in ("start", "flush", "read"):
            sdk = FakeSdk()
            sdk.failure = failure
            self.assertEqual({"status": "failed"}, self.emit(sdk, verify=True))
            self.assertTrue(sdk.closed)
            self.assertLessEqual(sdk.reads, 8)

    def test_smoke_verifies_delivery_metadata_and_parentage_after_bounded_retry(self):
        sdk = FakeSdk()
        sdk.failure = "delayed"
        result = self.emit(sdk, verify=True)
        self.assertEqual("verified", result["status"])
        self.assertEqual(2, sdk.reads)
        self.assertEqual("a" * 32, sdk.read_options["trace_id"])
        self.assertIn("metadata", sdk.read_options["fields"])
        self.assertIn("usage", sdk.read_options["expand_metadata"])
        for field, value in (
            ("input", "PRIVATE"),
            ("output", "PRIVATE"),
            ("metadata", {"unknown": "PRIVATE"}),
            ("parent_observation_id", "wrong"),
            ("trace_id", "wrong"),
            ("user_id", "PRIVATE"),
        ):
            sdk = FakeSdk()

            def mutate(trace, field=field, value=value):
                trace["observations"][-1][field] = value
                return trace

            sdk.mutate_trace = mutate
            self.assertEqual({"status": "failed"}, self.emit(sdk, verify=True))
            self.assertEqual(8, sdk.reads)

    def test_emit_cli_is_quiet_and_always_successful_on_invalid_payloads(self):
        for raw in ("{invalid", "x" * (telemetry.MAX_PAYLOAD + 1)):
            with (
                patch.object(sys, "argv", ["answer_telemetry", "--emit"]),
                patch.object(sys, "stdin", io.StringIO(raw)),
                patch.object(sys, "stdout", io.StringIO()) as output,
            ):
                self.assertEqual(0, telemetry.main())
                self.assertEqual("", output.getvalue())


if __name__ == "__main__":
    unittest.main()
