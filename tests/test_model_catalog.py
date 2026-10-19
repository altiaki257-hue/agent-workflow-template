import copy
import unittest
from datetime import date
from scripts.check_models import model_errors


class ModelCatalogTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "provider": {"openrouter": {"whitelist": ["example/model:free"]}}
        }
        self.catalog = {
            "data": [
                {
                    "id": "example/model:free",
                    "pricing": {"prompt": "0", "completion": "0"},
                    "supported_parameters": ["tools"],
                }
            ]
        }

    def test_free_tool_endpoint_passes(self):
        self.assertEqual([], model_errors(self.config, self.catalog))

    def test_selected_checks_ignore_unrelated_models_but_enforce_whitelist(self):
        self.config["provider"]["openrouter"]["whitelist"].append("unused/model:free")
        self.assertTrue(model_errors(self.config, self.catalog))
        self.assertFalse(
            model_errors(self.config, self.catalog, model_ids=["example/model:free"])
        )
        self.assertTrue(
            model_errors(self.config, self.catalog, model_ids=["unreviewed/model:free"])
        )

    def test_missing_endpoint_does_not_fall_back(self):
        self.assertTrue(model_errors(self.config, {"data": []}))

    def test_paid_or_missing_pricing_is_rejected(self):
        for pricing in (
            {"prompt": "0", "completion": "0.0001"},
            {"prompt": "0", "completion": "0", "request": "0.01"},
            {},
        ):
            catalog = copy.deepcopy(self.catalog)
            catalog["data"][0]["pricing"] = pricing
            self.assertTrue(model_errors(self.config, catalog))

    def test_missing_tools_and_imminent_expiry_are_rejected(self):
        catalog = copy.deepcopy(self.catalog)
        catalog["data"][0]["supported_parameters"] = []
        self.assertTrue(model_errors(self.config, catalog))
        catalog = copy.deepcopy(self.catalog)
        catalog["data"][0]["expiration_date"] = "2026-10-31"
        self.assertTrue(model_errors(self.config, catalog, today=date(2026, 10, 17)))


if __name__ == "__main__":
    unittest.main()
