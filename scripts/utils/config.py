from pathlib import Path
from typing import Any

import yaml

from scripts.utils.paths import get_config_path


class BusinessRulesConfig:
    def __init__(self, filename: str = "business_rules.yaml") -> None:
        self.config_file_path: Path = get_config_path(filename)
        self._raw_config = self._load_yaml()

        self.project = self._raw_config.get("project", {})
        self.regions = self._raw_config.get("regions", [])
        self.fx = self._raw_config.get("fx", {})
        self.products = self._raw_config.get("products", [])
        self.product_skus = self._raw_config.get("product_skus", [])
        self.customer_segments = self._raw_config.get("customer_segments", {})
        self.customer_industries = self._raw_config.get("customer_industries", [])
        self.customer_cohorts = self._raw_config.get("customer_cohorts", {})
        self.revenue_concentration = self._raw_config.get("revenue_concentration", {})
        self.arr_growth_targets = self._raw_config.get("arr_growth_targets", {})
        self.sales_seasonality = self._raw_config.get("sales_seasonality", {})
        self.departments = self._raw_config.get("departments", [])
        self.headcount_targets = self._raw_config.get("headcount_targets", {})
        self.employee_levels = self._raw_config.get("employee_levels", {})
        self.sales_capacity = self._raw_config.get("sales_capacity", {})
        self.quota_attainment = self._raw_config.get("quota_attainment", {})
        self.acquisition = self._raw_config.get("acquisition", {})
        self.budget_rules = self._raw_config.get("budget_rules", {})
        self.forecast_rules = self._raw_config.get("forecast_rules", {})
        self.data_quality_defects = self._raw_config.get("data_quality_defects", {})
        self.target_volumes = self._raw_config.get("target_volumes", {})

    def _load_yaml(self) -> dict[str, Any]:
        if not self.config_file_path.exists():
            raise FileNotFoundError(
                f"business_rules.yaml not found at: {self.config_file_path}"
            )

        try:
            with open(self.config_file_path, "r", encoding="utf-8") as file:
                return yaml.safe_load(file) or {}
        except yaml.YAMLError as error:
            raise ValueError(f"Invalid YAML in {self.config_file_path}: {error}") from error

    def get_currency_assumption(self, currency_code: str) -> dict[str, Any]:
        assumptions = self.fx.get("trend_assumptions", {})

        if currency_code not in assumptions:
            raise KeyError(
                f"Currency '{currency_code}' missing from fx.trend_assumptions."
            )

        return assumptions[currency_code]

    def as_dict(self) -> dict[str, Any]:
        return self._raw_config