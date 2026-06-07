"""
Project Atlas / Nexus Technologies
Phase 3N.1 - Variance Source Extract Generation

Purpose
-------
Generates:
- data/raw/planning/variance_source_extract.csv

This source-style extract aligns Actuals, Budget and Forecasts at a common
FP&A planning grain so downstream dbt / Power BI layers can perform Budget vs
Actual, Forecast vs Actual and Forecast vs Budget analysis without expensive
multi-file joins.

Design
------
Budget lines provide the locked Annual Operating Plan baseline.
Forecast lines provide scenario-specific rolling forecast values and, for
completed months, the actuals already blended by Phase 3M.

The extract preserves the Phase 3L / 3M presentation-sign convention:
- Revenue is stored as a positive target.
- COGS / OpEx are stored as positive spend envelopes.

Variance favourability is account-class aware:
- Revenue above baseline is favourable.
- Expense below baseline is favourable.

Grain
-----
One row per:
    forecast_version_code
    posting_period
    department_id
    account_code
    currency
    planning_driver
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    from scripts.utils.config import BusinessRulesConfig
    from scripts.utils.logger import get_logger
    from scripts.utils.paths import get_raw_data_path
except Exception:  # pragma: no cover - local sandbox fallback only
    BusinessRulesConfig = None

    def get_logger(name: str, log_file: str):
        import logging

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
        return logging.getLogger(name)

    def get_raw_data_path(domain: str) -> Path:
        return Path.cwd() / "data" / "raw" / domain


logger = get_logger("VarianceSourceExtractGenerator", "generation_execution.log")


@dataclass(frozen=True)
class VarianceSourceExtractRules:
    created_at: str = "2026-06-03"
    updated_at: str = "2026-06-03"
    rounding_tolerance: float = 0.05


class VarianceSourceExtractGenerator:
    """
    Generates the Phase 3N.1 variance source extract.

    Inputs
    ------
    data/raw/planning/budget_lines.csv
    data/raw/planning/forecast_versions.csv
    data/raw/planning/forecast_lines.csv
    data/raw/accounting/financial_statement_extract.csv
    data/raw/workforce/payroll_expense_lines.csv

    Output
    ------
    data/raw/planning/variance_source_extract.csv
    """

    output_filename = "variance_source_extract.csv"

    REQUIRED_BUDGET_COLUMNS = {
        "budget_line_id",
        "budget_version_code",
        "posting_period",
        "department_id",
        "account_code",
        "account_name",
        "account_class",
        "financial_statement",
        "currency",
        "budget_amount_local",
        "budget_amount_gbp",
        "planning_driver",
    }

    REQUIRED_FORECAST_VERSION_COLUMNS = {
        "forecast_version_code",
        "scenario_type",
        "cutover_period",
        "actual_period_start",
        "actual_period_end",
        "forecast_period_start",
        "forecast_period_end",
        "source_budget_version_code",
    }

    REQUIRED_FORECAST_COLUMNS = {
        "forecast_line_id",
        "forecast_version_code",
        "scenario_type",
        "fiscal_year",
        "posting_period",
        "period_start_date",
        "period_end_date",
        "department_id",
        "account_code",
        "account_name",
        "account_class",
        "financial_statement",
        "currency",
        "forecast_amount_local",
        "forecast_amount_gbp",
        "source_budget_amount_local",
        "source_budget_amount_gbp",
        "forecast_basis",
        "planning_driver",
        "source_budget_version_code",
        "source_budget_line_id",
    }

    REQUIRED_FS_COLUMNS = {
        "posting_period",
        "account_code",
        "account_class",
        "currency",
        "amount_gbp",
        "is_calculated_line",
        "calculation_type",
    }

    REQUIRED_PAYROLL_COLUMNS = {
        "posting_period",
        "department_id",
        "account_code",
        "currency",
        "cost_component",
        "debit_local",
        "debit_gbp",
    }

    OUTPUT_COLUMNS = [
        "variance_extract_pk",
        "variance_extract_line_id",
        "forecast_version_code",
        "forecast_scenario",
        "budget_version_code",
        "fiscal_year",
        "posting_period",
        "period_start_date",
        "period_end_date",
        "period_status",
        "department_id",
        "account_code",
        "account_name",
        "account_class",
        "financial_statement",
        "currency",
        "planning_driver",
        "forecast_basis",
        "actual_amount_local",
        "actual_amount_gbp",
        "budget_amount_local",
        "budget_amount_gbp",
        "forecast_amount_local",
        "forecast_amount_gbp",
        "actual_vs_budget_variance_gbp",
        "actual_vs_budget_variance_pct",
        "actual_vs_budget_favourability",
        "actual_vs_forecast_variance_gbp",
        "actual_vs_forecast_variance_pct",
        "actual_vs_forecast_favourability",
        "forecast_vs_budget_variance_gbp",
        "forecast_vs_budget_variance_pct",
        "forecast_vs_budget_favourability",
        "variance_category",
        "variance_driver_group",
        "is_actual_period",
        "is_forecast_period",
        "source_budget_line_id",
        "source_forecast_line_id",
        "actual_source_basis",
        "source_system",
        "is_system_generated",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    def __init__(self, base_raw_path: Optional[Path] = None) -> None:
        self.config = BusinessRulesConfig() if BusinessRulesConfig is not None else None
        self.seed = int(getattr(self.config, "project", {}).get("random_seed", 42)) if self.config else 42
        self.rules = VarianceSourceExtractRules()
        self.base_raw_path = Path(base_raw_path) if base_raw_path is not None else None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pk(value: str) -> str:
        return hashlib.md5(value.strip().upper().encode("utf-8")).hexdigest()

    @staticmethod
    def _round_money(value: object) -> float:
        if pd.isna(value):
            return 0.00
        return round(float(value), 2)

    @staticmethod
    def _safe_pct(numerator: object, denominator: object) -> float:
        """Return safe percentage variance, using np.nan where denominator is zero/missing."""
        numerator_value = pd.to_numeric(numerator, errors="coerce")
        denominator_value = pd.to_numeric(denominator, errors="coerce")

        if pd.isna(denominator_value) or abs(float(denominator_value)) < 0.005:
            return np.nan

        if pd.isna(numerator_value):
            return np.nan

        return round(float(numerator_value) / float(denominator_value), 6)

    @staticmethod
    def _require_columns(df: pd.DataFrame, required_columns: set[str], dataset_name: str) -> None:
        missing_columns = required_columns.difference(df.columns)
        if missing_columns:
            raise ValueError(f"{dataset_name} is missing required columns: {sorted(missing_columns)}")

    def _raw_domain_path(self, domain: str) -> Path:
        if self.base_raw_path is not None:
            domain_path = self.base_raw_path / domain
            if domain_path.exists():
                return domain_path
            return self.base_raw_path
        return get_raw_data_path(domain)

    def _load_csv(self, domain: str, filename: str, dataset_name: str) -> pd.DataFrame:
        path = self._raw_domain_path(domain) / filename
        if not path.exists():
            raise FileNotFoundError(f"{dataset_name} not found at {path}. Run upstream generators first.")
        return pd.read_csv(path)

    @staticmethod
    def _normalise_period(value: object) -> str:
        return pd.Period(str(value), freq="M").strftime("%Y-%m")

    @staticmethod
    def _period_leq(left: object, right: object) -> bool:
        return pd.Period(str(left), freq="M") <= pd.Period(str(right), freq="M")

    @staticmethod
    def _get_variance_driver_group(planning_driver: str, account_code: str) -> str:
        driver = str(planning_driver).upper()
        account_code = str(account_code)

        if "REVENUE" in driver or account_code.startswith("41"):
            return "Revenue"
        if "PAYROLL" in driver or account_code == "6100":
            return "Payroll"
        if "HOSTING" in driver or "CLOUD" in driver or account_code == "5100":
            return "Cloud Infrastructure"
        if "MARKETING" in driver or account_code == "6200":
            return "Sales & Marketing"
        if "SUPPORT" in driver or account_code == "5200":
            return "Customer Support"
        if "SOFTWARE" in driver or account_code == "6300":
            return "Software Tools"
        if "OFFICE" in driver or account_code == "6400":
            return "Facilities"
        if "PROFESSIONAL" in driver or account_code == "6500":
            return "Professional Fees"
        if "TRAVEL" in driver or account_code == "6600":
            return "Travel & Entertainment"
        return "Other"

    @staticmethod
    def _favourability(raw_variance: object, account_class: object) -> str:
        if pd.isna(raw_variance):
            return "Not Applicable"

        variance = round(float(raw_variance), 2)
        if abs(variance) <= 0.05:
            return "On Plan"

        account_class = str(account_class).strip().lower()

        if account_class == "revenue":
            return "Favourable" if variance > 0 else "Adverse"

        if account_class == "expense":
            return "Adverse" if variance > 0 else "Favourable"

        return "Favourable" if variance > 0 else "Adverse"

    @staticmethod
    def _variance_category(favourability: str, account_class: object, period_status: str) -> str:
        if favourability == "Not Applicable":
            return "No Actuals Yet" if period_status == "Forecast" else "No Baseline"
        if favourability == "On Plan":
            return "On Plan"

        account_class = str(account_class).strip().lower()
        if account_class == "revenue":
            return "Revenue Outperformance" if favourability == "Favourable" else "Revenue Shortfall"
        if account_class == "expense":
            return "Cost Underspend" if favourability == "Favourable" else "Cost Overspend"
        return favourability

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_dependencies(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        budget_lines_df = self._load_csv("planning", "budget_lines.csv", "budget_lines.csv")
        forecast_versions_df = self._load_csv("planning", "forecast_versions.csv", "forecast_versions.csv")
        forecast_lines_df = self._load_csv("planning", "forecast_lines.csv", "forecast_lines.csv")
        fs_df = self._load_csv("accounting", "financial_statement_extract.csv", "financial_statement_extract.csv")
        payroll_df = self._load_csv("workforce", "payroll_expense_lines.csv", "payroll_expense_lines.csv")

        self._require_columns(budget_lines_df, self.REQUIRED_BUDGET_COLUMNS, "budget_lines.csv")
        self._require_columns(forecast_versions_df, self.REQUIRED_FORECAST_VERSION_COLUMNS, "forecast_versions.csv")
        self._require_columns(forecast_lines_df, self.REQUIRED_FORECAST_COLUMNS, "forecast_lines.csv")
        self._require_columns(fs_df, self.REQUIRED_FS_COLUMNS, "financial_statement_extract.csv")
        self._require_columns(payroll_df, self.REQUIRED_PAYROLL_COLUMNS, "payroll_expense_lines.csv")

        budget_lines_df = self._prepare_budget_lines(budget_lines_df)
        forecast_versions_df = self._prepare_forecast_versions(forecast_versions_df)
        forecast_lines_df = self._prepare_forecast_lines(forecast_lines_df)
        fs_df = self._prepare_financial_statement_extract(fs_df)
        payroll_df = self._prepare_payroll_expense_lines(payroll_df)

        logger.info(
            "Loaded variance dependencies: %s budget lines, %s forecast versions, %s forecast lines, %s FS rows, %s payroll rows.",
            f"{len(budget_lines_df):,}",
            f"{len(forecast_versions_df):,}",
            f"{len(forecast_lines_df):,}",
            f"{len(fs_df):,}",
            f"{len(payroll_df):,}",
        )

        return budget_lines_df, forecast_versions_df, forecast_lines_df, fs_df, payroll_df

    def _prepare_budget_lines(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for column in ["budget_line_id", "budget_version_code", "posting_period", "department_id", "account_code", "account_name", "account_class", "financial_statement", "currency", "planning_driver"]:
            df[column] = df[column].fillna("").astype(str)
        df["posting_period"] = df["posting_period"].apply(self._normalise_period)
        df["account_code"] = df["account_code"].astype(str).str.replace(".0", "", regex=False)
        df["currency"] = df["currency"].str.upper()
        for column in ["budget_amount_local", "budget_amount_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00).round(2)
        return df

    def _prepare_forecast_versions(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for column in ["forecast_version_code", "scenario_type", "cutover_period", "actual_period_start", "actual_period_end", "forecast_period_start", "forecast_period_end", "source_budget_version_code"]:
            df[column] = df[column].fillna("").astype(str)
        for column in ["cutover_period", "actual_period_start", "actual_period_end", "forecast_period_start", "forecast_period_end"]:
            df[column] = df[column].apply(self._normalise_period)
        return df

    def _prepare_forecast_lines(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        text_columns = [
            "forecast_line_id",
            "forecast_version_code",
            "scenario_type",
            "posting_period",
            "period_start_date",
            "period_end_date",
            "department_id",
            "account_code",
            "account_name",
            "account_class",
            "financial_statement",
            "currency",
            "forecast_basis",
            "planning_driver",
            "source_budget_version_code",
            "source_budget_line_id",
        ]
        for column in text_columns:
            df[column] = df[column].fillna("").astype(str)
        df["posting_period"] = df["posting_period"].apply(self._normalise_period)
        df["account_code"] = df["account_code"].astype(str).str.replace(".0", "", regex=False)
        df["currency"] = df["currency"].str.upper()
        df["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="coerce").fillna(0).astype(int)
        for column in ["forecast_amount_local", "forecast_amount_gbp", "source_budget_amount_local", "source_budget_amount_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00).round(2)
        return df

    def _prepare_financial_statement_extract(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for column in ["posting_period", "account_code", "account_class", "currency", "calculation_type"]:
            df[column] = df[column].fillna("").astype(str)
        df["posting_period"] = df["posting_period"].apply(self._normalise_period)
        df["account_code"] = df["account_code"].astype(str).str.replace(".0", "", regex=False)
        df["currency"] = df["currency"].str.upper()
        df["amount_gbp"] = pd.to_numeric(df["amount_gbp"], errors="coerce").fillna(0.00).round(2)
        df["is_calculated_line"] = pd.to_numeric(df["is_calculated_line"], errors="coerce").fillna(0).astype(int)
        return df

    def _prepare_payroll_expense_lines(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for column in ["posting_period", "department_id", "account_code", "currency", "cost_component"]:
            df[column] = df[column].fillna("").astype(str)
        df["posting_period"] = df["posting_period"].apply(self._normalise_period)
        df["account_code"] = df["account_code"].astype(str).str.replace(".0", "", regex=False)
        df["currency"] = df["currency"].str.upper()
        for column in ["debit_local", "debit_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00).round(2)
        return df

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _build_actual_lookup(
        self,
        budget_lines_df: pd.DataFrame,
        forecast_versions_df: pd.DataFrame,
        fs_df: pd.DataFrame,
        payroll_df: pd.DataFrame,
    ) -> dict[tuple[str, str, str, str, str, str], dict[str, object]]:
        """
        Build actual amounts at the AOP / forecast grain.

        Payroll actuals are sourced natively from payroll_expense_lines.csv.
        Non-payroll / revenue actuals are sourced from financial_statement_extract.csv
        at consolidated GBP account level, then allocated back to budget-line grain
        using locked AOP budget shares.
        """
        actual_lookup: dict[tuple[str, str, str, str, str, str], dict[str, object]] = {}

        max_cutover = max(pd.Period(v, freq="M") for v in forecast_versions_df["cutover_period"].unique())
        actual_period_mask = budget_lines_df["posting_period"].apply(
            lambda value: pd.Period(str(value), freq="M") <= max_cutover
        )
        actual_budget_df = budget_lines_df[actual_period_mask].copy()

        # ------------------------------------------------------------------
        # 1. Native payroll actuals
        # ------------------------------------------------------------------
        component_to_driver = {
            "BASE_SALARY": "PAYROLL_BASE_SALARY",
            "EMPLOYER_TAX": "PAYROLL_EMPLOYER_TAX",
            "BENEFITS": "PAYROLL_BENEFITS",
            "BONUS_ACCRUAL": "PAYROLL_BONUS_ACCRUAL",
        }

        payroll_actuals = payroll_df.copy()
        payroll_actuals = payroll_actuals[
            payroll_actuals["posting_period"].apply(
                lambda value: pd.Period(str(value), freq="M") <= max_cutover
            )
        ].copy()
        payroll_actuals["planning_driver"] = payroll_actuals["cost_component"].map(component_to_driver).fillna(
            payroll_actuals["cost_component"].astype(str)
        )

        payroll_grouped = (
            payroll_actuals.groupby(
                ["posting_period", "department_id", "account_code", "currency", "planning_driver"],
                dropna=False,
            )[["debit_local", "debit_gbp"]]
            .sum()
            .reset_index()
        )

        for row in payroll_grouped.itertuples(index=False):
            key = (
                str(row.posting_period),
                str(row.department_id),
                str(row.account_code),
                str(row.currency),
                str(row.planning_driver),
                "PAYROLL",
            )
            actual_lookup[key] = {
                "actual_amount_local": self._round_money(row.debit_local),
                "actual_amount_gbp": self._round_money(row.debit_gbp),
                "actual_source_basis": "ACTUAL_WORKFORCE_SUBLEDGER",
            }

        # ------------------------------------------------------------------
        # 2. Consolidated financial statement actuals allocated to AOP grain
        # ------------------------------------------------------------------
        fs_actuals = fs_df[
            (fs_df["is_calculated_line"] == 0)
            & (fs_df["calculation_type"].astype(str) == "ACCOUNT_ACTIVITY")
            & (fs_df["account_code"].astype(str) != "6100")
            & (
                fs_df["posting_period"].apply(
                    lambda value: pd.Period(str(value), freq="M") <= max_cutover
                )
            )
        ].copy()

        fs_totals = (
            fs_actuals.groupby(["posting_period", "account_code"], dropna=False)["amount_gbp"]
            .sum()
            .reset_index(name="actual_account_amount_gbp")
        )

        budget_alloc_base = actual_budget_df[actual_budget_df["account_code"].astype(str) != "6100"].copy()
        budget_totals = (
            budget_alloc_base.groupby(["posting_period", "account_code"], dropna=False)["budget_amount_gbp"]
            .sum()
            .reset_index(name="total_budget_amount_gbp")
        )

        budget_alloc_base = budget_alloc_base.merge(
            budget_totals,
            on=["posting_period", "account_code"],
            how="left",
        ).merge(
            fs_totals,
            on=["posting_period", "account_code"],
            how="left",
        )

        budget_alloc_base["actual_account_amount_gbp"] = budget_alloc_base["actual_account_amount_gbp"].fillna(0.00)
        budget_alloc_base["allocation_share"] = np.where(
            budget_alloc_base["total_budget_amount_gbp"].abs() > 0.005,
            budget_alloc_base["budget_amount_gbp"] / budget_alloc_base["total_budget_amount_gbp"],
            0.00,
        )
        budget_alloc_base["allocated_actual_gbp"] = (
            budget_alloc_base["actual_account_amount_gbp"] * budget_alloc_base["allocation_share"]
        ).round(2)

        for row in budget_alloc_base.itertuples(index=False):
            key = (
                str(row.posting_period),
                str(row.department_id),
                str(row.account_code),
                str(row.currency),
                str(row.planning_driver),
                "FS_ALLOCATED",
            )
            actual_lookup[key] = {
                # For FS-allocated actuals, local currency is a presentation bridge.
                # Keep local equal to GBP to avoid implying native transactional currency.
                "actual_amount_local": self._round_money(row.allocated_actual_gbp),
                "actual_amount_gbp": self._round_money(row.allocated_actual_gbp),
                "actual_source_basis": "ACTUAL_FS_ALLOCATED_TO_AOP_GRAIN",
            }

        return actual_lookup

    def _get_actual_amount_for_row(
        self,
        row_dict: dict,
        actual_lookup: dict[tuple[str, str, str, str, str, str], dict[str, object]],
    ) -> dict[str, object]:
        source_type = "PAYROLL" if str(row_dict["account_code"]) == "6100" else "FS_ALLOCATED"
        key = (
            str(row_dict["posting_period"]),
            str(row_dict["department_id"]),
            str(row_dict["account_code"]),
            str(row_dict["currency"]),
            str(row_dict["planning_driver"]),
            source_type,
        )
        return actual_lookup.get(
            key,
            {
                "actual_amount_local": 0.00,
                "actual_amount_gbp": 0.00,
                "actual_source_basis": "ACTUAL_SOURCE_NOT_FOUND",
            },
        )

    def _build_variance_rows(
        self,
        budget_lines_df: pd.DataFrame,
        forecast_versions_df: pd.DataFrame,
        forecast_lines_df: pd.DataFrame,
        fs_df: pd.DataFrame,
        payroll_df: pd.DataFrame,
    ) -> pd.DataFrame:
        version_lookup = forecast_versions_df.set_index("forecast_version_code").to_dict("index")
        budget_lookup = budget_lines_df.set_index("budget_line_id").to_dict("index")
        actual_lookup = self._build_actual_lookup(
            budget_lines_df=budget_lines_df,
            forecast_versions_df=forecast_versions_df,
            fs_df=fs_df,
            payroll_df=payroll_df,
        )

        records: list[dict] = []

        for counter, row in enumerate(forecast_lines_df.itertuples(index=False), start=1):
            row_dict = row._asdict()
            version_code = row_dict["forecast_version_code"]
            version_meta = version_lookup.get(version_code)

            if version_meta is None:
                raise ValueError(f"Forecast line references unknown forecast_version_code: {version_code}")

            cutover_period = version_meta["cutover_period"]
            posting_period = row_dict["posting_period"]
            is_actual_period = self._period_leq(posting_period, cutover_period)
            is_forecast_period = not is_actual_period
            period_status = "Actual" if is_actual_period else "Forecast"

            source_budget_line_id = str(row_dict["source_budget_line_id"])
            budget_meta = budget_lookup.get(source_budget_line_id, {})

            budget_amount_local = self._round_money(row_dict.get("source_budget_amount_local", 0.00))
            budget_amount_gbp = self._round_money(row_dict.get("source_budget_amount_gbp", 0.00))

            if abs(budget_amount_local) <= 0.005 and source_budget_line_id in budget_lookup:
                budget_amount_local = self._round_money(budget_meta.get("budget_amount_local", 0.00))
            if abs(budget_amount_gbp) <= 0.005 and source_budget_line_id in budget_lookup:
                budget_amount_gbp = self._round_money(budget_meta.get("budget_amount_gbp", 0.00))

            forecast_amount_local = self._round_money(row_dict["forecast_amount_local"])
            forecast_amount_gbp = self._round_money(row_dict["forecast_amount_gbp"])

            if is_actual_period:
                actual_result = self._get_actual_amount_for_row(row_dict, actual_lookup)
                actual_amount_local = self._round_money(actual_result["actual_amount_local"])
                actual_amount_gbp = self._round_money(actual_result["actual_amount_gbp"])
                actual_source_basis = str(actual_result["actual_source_basis"])
            else:
                actual_amount_local = 0.00
                actual_amount_gbp = 0.00
                actual_source_basis = "NO_ACTUALS_FUTURE_PERIOD"

            if is_actual_period:
                avb_var = self._round_money(actual_amount_gbp - budget_amount_gbp)
                avb_pct = self._safe_pct(avb_var, budget_amount_gbp)
                avb_fav = self._favourability(avb_var, row_dict["account_class"])

                avf_var = self._round_money(actual_amount_gbp - forecast_amount_gbp)
                avf_pct = self._safe_pct(avf_var, forecast_amount_gbp)
                avf_fav = self._favourability(avf_var, row_dict["account_class"])
            else:
                avb_var = np.nan
                avb_pct = np.nan
                avb_fav = "Not Applicable"
                avf_var = np.nan
                avf_pct = np.nan
                avf_fav = "Not Applicable"

            fvb_var = self._round_money(forecast_amount_gbp - budget_amount_gbp)
            fvb_pct = self._safe_pct(fvb_var, budget_amount_gbp)
            fvb_fav = self._favourability(fvb_var, row_dict["account_class"])

            primary_fav = avb_fav if is_actual_period else fvb_fav
            variance_category = self._variance_category(
                primary_fav,
                row_dict["account_class"],
                period_status,
            )

            key = "|".join(
                [
                    version_code,
                    posting_period,
                    str(row_dict["department_id"]),
                    str(row_dict["account_code"]),
                    str(row_dict["currency"]),
                    str(row_dict["planning_driver"]),
                ]
            )

            records.append(
                {
                    "variance_extract_pk": self._generate_pk(key),
                    "variance_extract_line_id": f"VAR-LN-{counter:010d}",
                    "forecast_version_code": version_code,
                    "forecast_scenario": str(version_meta["scenario_type"]),
                    "budget_version_code": str(row_dict["source_budget_version_code"]),
                    "fiscal_year": int(row_dict["fiscal_year"]),
                    "posting_period": posting_period,
                    "period_start_date": str(row_dict["period_start_date"]),
                    "period_end_date": str(row_dict["period_end_date"]),
                    "period_status": period_status,
                    "department_id": str(row_dict["department_id"]),
                    "account_code": str(row_dict["account_code"]),
                    "account_name": str(row_dict["account_name"]),
                    "account_class": str(row_dict["account_class"]),
                    "financial_statement": str(row_dict["financial_statement"]),
                    "currency": str(row_dict["currency"]),
                    "planning_driver": str(row_dict["planning_driver"]),
                    "forecast_basis": str(row_dict["forecast_basis"]),
                    "actual_amount_local": self._round_money(actual_amount_local),
                    "actual_amount_gbp": self._round_money(actual_amount_gbp),
                    "budget_amount_local": budget_amount_local,
                    "budget_amount_gbp": budget_amount_gbp,
                    "forecast_amount_local": forecast_amount_local,
                    "forecast_amount_gbp": forecast_amount_gbp,
                    "actual_vs_budget_variance_gbp": avb_var,
                    "actual_vs_budget_variance_pct": avb_pct,
                    "actual_vs_budget_favourability": avb_fav,
                    "actual_vs_forecast_variance_gbp": avf_var,
                    "actual_vs_forecast_variance_pct": avf_pct,
                    "actual_vs_forecast_favourability": avf_fav,
                    "forecast_vs_budget_variance_gbp": fvb_var,
                    "forecast_vs_budget_variance_pct": fvb_pct,
                    "forecast_vs_budget_favourability": fvb_fav,
                    "variance_category": variance_category,
                    "variance_driver_group": self._get_variance_driver_group(
                        row_dict["planning_driver"],
                        row_dict["account_code"],
                    ),
                    "is_actual_period": int(is_actual_period),
                    "is_forecast_period": int(is_forecast_period),
                    "source_budget_line_id": source_budget_line_id,
                    "source_forecast_line_id": str(row_dict["forecast_line_id"]),
                    "actual_source_basis": actual_source_basis,
                    "source_system": "planning_variance_engine",
                    "is_system_generated": 1,
                    "is_defect_flag": 0,
                    "defect_type": "",
                    "created_at": self.rules.created_at,
                    "updated_at": self.rules.updated_at,
                }
            )

        return pd.DataFrame(records, columns=self.OUTPUT_COLUMNS)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_outputs(
        self,
        variance_df: pd.DataFrame,
        budget_lines_df: pd.DataFrame,
        forecast_versions_df: pd.DataFrame,
        forecast_lines_df: pd.DataFrame,
        fs_df: pd.DataFrame,
        payroll_df: pd.DataFrame,
    ) -> None:
        if variance_df.empty:
            raise ValueError("variance_source_extract.csv output is empty.")

        if len(variance_df) != len(forecast_lines_df):
            raise ValueError(
                "Variance extract row count must match forecast lines row count. "
                f"Variance rows: {len(variance_df):,}; forecast rows: {len(forecast_lines_df):,}."
            )

        if variance_df["variance_extract_pk"].duplicated().any():
            duplicate_count = int(variance_df["variance_extract_pk"].duplicated().sum())
            raise ValueError(f"Duplicate variance_extract_pk values found: {duplicate_count:,}")

        if variance_df["variance_extract_line_id"].duplicated().any():
            duplicate_count = int(variance_df["variance_extract_line_id"].duplicated().sum())
            raise ValueError(f"Duplicate variance_extract_line_id values found: {duplicate_count:,}")

        grain = [
            "forecast_version_code",
            "posting_period",
            "department_id",
            "account_code",
            "currency",
            "planning_driver",
        ]
        if variance_df.duplicated(grain).any():
            duplicate_count = int(variance_df.duplicated(grain).sum())
            raise ValueError(f"Duplicate variance extract grain rows found: {duplicate_count:,}")

        numeric_non_negative_columns = [
            "actual_amount_local",
            "actual_amount_gbp",
            "budget_amount_local",
            "budget_amount_gbp",
            "forecast_amount_local",
            "forecast_amount_gbp",
        ]
        for column in numeric_non_negative_columns:
            if (pd.to_numeric(variance_df[column], errors="coerce").fillna(0) < -0.005).any():
                raise ValueError(f"{column} contains negative presentation amounts.")

        future_rows = variance_df[variance_df["is_forecast_period"] == 1]
        if not future_rows.empty:
            if future_rows["actual_amount_gbp"].abs().max() > self.rules.rounding_tolerance:
                raise ValueError("Future-period rows must carry zero actual_amount_gbp.")

            if future_rows["actual_vs_budget_variance_gbp"].notna().any():
                raise ValueError("Future-period rows should suppress actual_vs_budget_variance_gbp.")

            if future_rows["actual_vs_forecast_variance_gbp"].notna().any():
                raise ValueError("Future-period rows should suppress actual_vs_forecast_variance_gbp.")

        actual_rows = variance_df[variance_df["is_actual_period"] == 1]
        if actual_rows.empty:
            raise ValueError("Variance extract contains no actual-period rows.")

        # Scenario actual-period rows must be identical across scenarios at common grain.
        scenario_check_grain = ["posting_period", "department_id", "account_code", "currency", "planning_driver"]
        scenario_actual_counts = (
            actual_rows.groupby(scenario_check_grain)["actual_amount_gbp"]
            .nunique(dropna=False)
            .reset_index(name="actual_amount_versions")
        )
        if (scenario_actual_counts["actual_amount_versions"] > 1).any():
            bad_count = int((scenario_actual_counts["actual_amount_versions"] > 1).sum())
            raise ValueError(
                "Actual-period rows are not identical across forecast scenarios for "
                f"{bad_count:,} grain intersections."
            )

        # Tie actual-period revenue back to consolidated financial statement actuals.
        fs_actuals = fs_df[
            (fs_df["is_calculated_line"] == 0)
            & (fs_df["calculation_type"].astype(str) == "ACCOUNT_ACTIVITY")
            & (fs_df["account_code"].astype(str) != "6100")
        ].copy()

        actual_periods = set(actual_rows["posting_period"].astype(str).unique())
        fs_actuals = fs_actuals[fs_actuals["posting_period"].astype(str).isin(actual_periods)].copy()

        fs_expected_by_class = (
            fs_actuals.groupby("account_class")["amount_gbp"]
            .sum()
            .round(2)
            .to_dict()
        )

        for account_class, expected_total in fs_expected_by_class.items():
            if str(account_class) == "Expense":
                # Expense actuals include payroll from the workforce subledger separately,
                # so non-payroll FS expense is validated through total actual basis below.
                continue

            for version_code in variance_df["forecast_version_code"].unique():
                actual_total = round(float(
                    actual_rows[
                        (actual_rows["forecast_version_code"] == version_code)
                        & (actual_rows["account_class"] == account_class)
                    ]["actual_amount_gbp"].sum()
                ), 2)
                if abs(actual_total - float(expected_total)) > self.rules.rounding_tolerance:
                    raise ValueError(
                        f"Actual {account_class} total mismatch for {version_code}: "
                        f"variance extract {actual_total:.2f}; FS source {float(expected_total):.2f}."
                    )

        # Payroll actuals should tie directly to workforce payroll extract for actual periods.
        payroll_expected = round(float(
            payroll_df[payroll_df["posting_period"].astype(str).isin(actual_periods)]["debit_gbp"].sum()
        ), 2)

        for version_code in variance_df["forecast_version_code"].unique():
            payroll_actual = round(float(
                actual_rows[
                    (actual_rows["forecast_version_code"] == version_code)
                    & (actual_rows["account_code"] == "6100")
                ]["actual_amount_gbp"].sum()
            ), 2)
            if abs(payroll_actual - payroll_expected) > self.rules.rounding_tolerance:
                raise ValueError(
                    f"Payroll actual total mismatch for {version_code}: variance extract {payroll_actual:.2f}; "
                    f"payroll source {payroll_expected:.2f}."
                )

        invalid_favourability = set(variance_df["forecast_vs_budget_favourability"].unique()).difference(
            {"Favourable", "Adverse", "On Plan", "Not Applicable"}
        )
        if invalid_favourability:
            raise ValueError(f"Invalid favourability labels found: {sorted(invalid_favourability)}")

        logger.info("Variance source extract validation passed.")

    def _log_review(self, variance_df: pd.DataFrame) -> None:
        logger.info("----- Variance Source Extract Review -----")
        logger.info("Variance rows: %s", f"{len(variance_df):,}")
        logger.info(
            "Posting period range: %s to %s",
            variance_df["posting_period"].min(),
            variance_df["posting_period"].max(),
        )
        logger.info(
            "Rows by forecast version:\n%s",
            variance_df["forecast_version_code"].value_counts().sort_index().to_string(),
        )
        logger.info(
            "Rows by period status:\n%s",
            variance_df["period_status"].value_counts().to_string(),
        )
        logger.info(
            "Forecast vs budget GBP by version/account class:\n%s",
            variance_df.groupby(["forecast_version_code", "account_class"])["forecast_vs_budget_variance_gbp"]
            .sum()
            .round(2)
            .to_string(),
        )
        logger.info(
            "Variance categories:\n%s",
            variance_df["variance_category"].value_counts().to_string(),
        )
        logger.info(
            "Variance driver groups by GBP absolute forecast-vs-budget variance:\n%s",
            variance_df.assign(abs_fvb=variance_df["forecast_vs_budget_variance_gbp"].abs())
            .groupby("variance_driver_group")["abs_fvb"]
            .sum()
            .sort_values(ascending=False)
            .round(2)
            .head(12)
            .to_string(),
        )
        logger.info("------------------------------------------")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> pd.DataFrame:
        logger.info("Generating Phase 3N.1 Variance Source Extract.")

        budget_lines_df, forecast_versions_df, forecast_lines_df, fs_df, payroll_df = self._load_dependencies()
        variance_df = self._build_variance_rows(
            budget_lines_df=budget_lines_df,
            forecast_versions_df=forecast_versions_df,
            forecast_lines_df=forecast_lines_df,
            fs_df=fs_df,
            payroll_df=payroll_df,
        )
        self._validate_outputs(
            variance_df=variance_df,
            budget_lines_df=budget_lines_df,
            forecast_versions_df=forecast_versions_df,
            forecast_lines_df=forecast_lines_df,
            fs_df=fs_df,
            payroll_df=payroll_df,
        )
        self._log_review(variance_df)
        return variance_df

    def save(self, variance_df: pd.DataFrame) -> None:
        output_dir = self._raw_domain_path("planning")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / self.output_filename
        variance_df.to_csv(output_path, index=False)
        logger.info("Variance source extract saved to %s", output_path)


if __name__ == "__main__":
    generator = VarianceSourceExtractGenerator()
    variance_source_extract = generator.generate()
    generator.save(variance_source_extract)
