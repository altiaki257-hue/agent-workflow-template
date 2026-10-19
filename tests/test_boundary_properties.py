"""Generated boundary cases complement the explicit protocol/privacy regressions."""

import unittest

from hypothesis import given, settings, strategies as st

from scripts import answer_telemetry as telemetry


class BoundaryProperties(unittest.TestCase):
    @settings(max_examples=100, derandomize=True, database=None, deadline=None)
    @given(st.one_of(st.booleans(), st.text(), st.none(), st.lists(st.integers())))
    def test_token_counts_never_accept_other_json_types(self, value):
        clean = telemetry.usage_metadata({"input_tokens": value})
        self.assertNotIn("input_tokens", clean)

    @settings(max_examples=100, derandomize=True, database=None, deadline=None)
    @given(st.floats(allow_nan=True, allow_infinity=True))
    def test_float_typed_token_counts_are_not_exported(self, value):
        clean = telemetry.usage_metadata({"input_tokens": value})
        self.assertNotIn("input_tokens", clean)

    @settings(max_examples=100, derandomize=True, database=None, deadline=None)
    @given(st.integers())
    def test_integer_counts_have_a_safe_export_range(self, value):
        clean = telemetry.usage_metadata({"input_tokens": value})
        self.assertEqual("input_tokens" in clean, 0 <= value <= 10**12)

    @settings(max_examples=100, derandomize=True, database=None, deadline=None)
    @given(st.text(max_size=300))
    def test_unknown_prose_does_not_enter_export_payload(self, prose):
        clean = telemetry.sanitize_metadata(
            {
                "route": "direct",
                "evidence_scope": "supplied",
                "question": prose,
                "answer": prose,
                "raw_error": prose,
                "unknown": prose,
            }
        )
        baseline = telemetry.sanitize_metadata(
            {"route": "direct", "evidence_scope": "supplied"}
        )
        self.assertEqual(clean, baseline)


if __name__ == "__main__":
    unittest.main()
