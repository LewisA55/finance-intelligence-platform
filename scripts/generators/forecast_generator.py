"""
forecast_generator.py

Project Atlas / Nexus Technologies
Phase 3M.1 - Forecast / Reforecast Scenario Source Generation

Purpose
-------
Generates:
- data/raw/planning/forecast_versions.csv
- data/raw/planning/forecast_lines.csv

This phase creates an active management forecast layer. It does not mutate
actuals, the ERP GL, Trial Balance, Financial Statement extracts, controls,
findings, workforce subledgers, or the locked Annual Operating Plan.

Design
------
The forecast mirrors the budget line grain so downstream dbt models can perform
clean Budget vs Forecast vs Actual variance analysis.

Completed months are blended using actuals where available. Because the locked
financial statement extract is not department-granular, completed-month non-
payroll actuals are allocated back to the forecast grain using the locked AOP
line-share for the same period/account/currency.

Future months apply deterministic scenario driver logic:
- FC_BASE_CASE: realistic operating leverage; payroll onboarding scaled down;
  cloud hosting efficiency improves.
- FC_UPSIDE_CASE: stronger SaaS adoption; revenue accelerates; GTM and hiring
  flex upward.
- FC_DOWNSIDE_CASE: market contraction; revenue growth stalls; marketing and
  hiring are constrained.

Grain
-----
forecast_lines.csv:
    forecast_version_code + posting_period + department_id + account_code +
    currency + planning_driver
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("ForecastGenerator", "generation_execution.log")


@dataclass(frozen=True)
class ForecastGenerationRules:
    created_at: str = "2026-06-03"
    updated_at: str = "2026-06-03"
    fiscal_year: int = 2026
    planning_start_period: str = "2026-01"
    planning_end_period: str = "2026-12"
    cutover_period: str = "2026-03"
    budget_version_code: str = "AOP_FY2026_BOARD_APPROVED"
    rounding_tolerance: float = 1.00
    revenue_account_saas: str = "4100"
    revenue_account_legacy: str = "4110"
    payroll_account: str = "6100"


class ForecastGenerator:
    """Generate forecast versions and scenario forecast lines."""

    versions_filename = "forecast_versions.csv"
    lines_filename = "forecast_lines.csv"

    VERSION_COLUMNS = [
        "forecast_version_pk",
        "forecast_version_code",
        "forecast_name",
        "fiscal_year",
        "scenario_type",
        "scenario_description",
        "cutover_period",
        "actual_period_start",
        "actual_period_end",
        "forecast_period_start",
        "forecast_period_end",
        "source_budget_version_code",
        "approval_status",
        "is_locked_flag",
        "source_system",
        "created_at",
        "updated_at",
    ]

    LINE_COLUMNS = [
        "forecast_line_pk",
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
        "driver_quantity",
        "driver_rate",
        "scenario_multiplier",
        "forecast_method",
        "source_budget_version_code",
        "source_budget_line_id",
        "is_locked_flag",
        "source_system",
        "is_system_generated",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    SCENARIOS = {
        "FC_BASE_CASE": {
            "scenario_type": "Base Case",
            "name": "FY2026 3+9 Base Case Forecast",
            "description": "Updated run-rate forecast with operating leverage, moderated hiring and cloud optimisation.",
            "revenue_multiplier": 1.00,
            "payroll_multiplier": 0.85,
            "marketing_multiplier": 0.90,
            "hosting_rate_multiplier": 0.11 / 0.145,
            "product_cloud_multiplier": 0.035 / 0.045,
            "support_cogs_multiplier": 0.95,
            "payroll_scaled_opex_multiplier": 0.90,
        },
        "FC_UPSIDE_CASE": {
            "scenario_type": "Upside Case",
            "name": "FY2026 3+9 Upside Forecast",
            "description": "Accelerated SaaS adoption with higher GTM investment and faster headcount activation.",
            "revenue_multiplier": 1.25,
            "payroll_multiplier": 1.10,
            "marketing_multiplier": 1.20,
            "hosting_rate_multiplier": 0.125 / 0.145,
            "product_cloud_multiplier": 0.040 / 0.045,
            "support_cogs_multiplier": 1.10,
            "payroll_scaled_opex_multiplier": 1.08,
        },
        "FC_DOWNSIDE_CASE": {
            "scenario_type": "Downside Case",
            "name": "FY2026 3+9 Downside Forecast",
            "description": "Market contraction case with reduced revenue, marketing cuts and hiring freeze.",
            "revenue_multiplier": 0.50,
            "payroll_multiplier": 0.80,
            "marketing_multiplier": 0.60,
            "hosting_rate_multiplier": 0.130 / 0.145,
            "product_cloud_multiplier": 0.040 / 0.045,
            "support_cogs_multiplier": 0.80,
            "payroll_scaled_opex_multiplier": 0.82,
        },
    }

    def __init__(self) -> None:
        self.rules = ForecastGenerationRules()
        self._line_counter = 0

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
    def _normalise_account_code(value: object) -> str:
        if pd.isna(value):
            return ""
        value_str = str(value).strip()
        if value_str.endswith(".0") and value_str.replace(".0", "").isdigit():
            return value_str.replace(".0", "")
        return value_str

    @staticmethod
    def _require_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f"{name} is missing required columns: {sorted(missing)}")

    def _next_line_id(self) -> str:
        self._line_counter += 1
        return f"FC-LN-{self._line_counter:010d}"

    @staticmethod
    def _period_end(period_start: pd.Timestamp) -> pd.Timestamp:
        return period_start + pd.offsets.MonthEnd(0)

    @staticmethod
    def _period_range(start_period: str, end_period: str) -> list[pd.Timestamp]:
        return pd.date_range(
            start=pd.Timestamp(f"{start_period}-01"),
            end=pd.Timestamp(f"{end_period}-01"),
            freq="MS",
        ).to_list()

    @staticmethod
    def _load_csv(path: Path, dataset_name: str) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"{dataset_name} not found at {path}. Run upstream generators first.")
        return pd.read_csv(path)

    # ------------------------------------------------------------------
    # Loading / preparation
    # ------------------------------------------------------------------

    def _load_dependencies(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        planning_dir = get_raw_data_path("planning")
        accounting_dir = get_raw_data_path("accounting")
        workforce_dir = get_raw_data_path("workforce")

        budget_versions_df = self._load_csv(planning_dir / "budget_versions.csv", "budget_versions.csv")
        budget_lines_df = self._load_csv(planning_dir / "budget_lines.csv", "budget_lines.csv")
        fs_df = self._load_csv(accounting_dir / "financial_statement_extract.csv", "financial_statement_extract.csv")
        payroll_df = self._load_csv(workforce_dir / "payroll_expense_lines.csv", "payroll_expense_lines.csv")
        headcount_plan_df = self._load_csv(workforce_dir / "headcount_plan.csv", "headcount_plan.csv")

        budget_versions_df = self._prepare_budget_versions(budget_versions_df)
        budget_lines_df = self._prepare_budget_lines(budget_lines_df)
        fs_df = self._prepare_financial_statement_extract(fs_df)
        payroll_df = self._prepare_payroll(payroll_df)
        headcount_plan_df = self._prepare_headcount_plan(headcount_plan_df)

        logger.info(
            "Loaded forecast dependencies: %s budget versions, %s budget lines, %s financial statement rows, %s payroll rows, %s headcount plan rows.",
            f"{len(budget_versions_df):,}",
            f"{len(budget_lines_df):,}",
            f"{len(fs_df):,}",
            f"{len(payroll_df):,}",
            f"{len(headcount_plan_df):,}",
        )
        return budget_versions_df, budget_lines_df, fs_df, payroll_df, headcount_plan_df

    def _prepare_budget_versions(self, df: pd.DataFrame) -> pd.DataFrame:
        self._require_columns(df, {"budget_version_code", "fiscal_year", "planning_start_period", "planning_end_period"}, "budget_versions.csv")
        out = df.copy()
        out["budget_version_code"] = out["budget_version_code"].astype(str)
        out["fiscal_year"] = pd.to_numeric(out["fiscal_year"], errors="coerce").astype(int)
        return out

    def _prepare_budget_lines(self, df: pd.DataFrame) -> pd.DataFrame:
        required = {
            "budget_line_id",
            "budget_version_code",
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
            "budget_amount_local",
            "budget_amount_gbp",
            "planning_driver",
            "driver_quantity",
            "driver_rate",
        }
        self._require_columns(df, required, "budget_lines.csv")
        out = df.copy()
        out = out[out["budget_version_code"].astype(str) == self.rules.budget_version_code].copy()
        out = out[out["fiscal_year"].astype(int) == self.rules.fiscal_year].copy()
        if out.empty:
            raise ValueError(f"No budget lines found for {self.rules.budget_version_code} / FY{self.rules.fiscal_year}.")
        out["posting_period"] = out["posting_period"].astype(str)
        out["department_id"] = out["department_id"].astype(str)
        out["account_code"] = out["account_code"].apply(self._normalise_account_code)
        out["currency"] = out["currency"].astype(str).str.upper()
        out["planning_driver"] = out["planning_driver"].astype(str)
        for col in ["budget_amount_local", "budget_amount_gbp", "driver_quantity", "driver_rate"]:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.00)
        return out

    def _prepare_financial_statement_extract(self, df: pd.DataFrame) -> pd.DataFrame:
        required = {"posting_period", "statement_type", "account_code", "account_name", "account_class", "currency", "amount_local", "amount_gbp", "calculation_type"}
        self._require_columns(df, required, "financial_statement_extract.csv")
        out = df.copy()
        out = out[(out["statement_type"].astype(str) == "Income Statement") & (out["calculation_type"].astype(str) == "ACCOUNT_ACTIVITY")].copy()
        out["posting_period"] = out["posting_period"].astype(str)
        out["account_code"] = out["account_code"].apply(self._normalise_account_code)
        out["currency"] = out["currency"].astype(str).str.upper()
        out["amount_local"] = pd.to_numeric(out["amount_local"], errors="coerce").fillna(0.00)
        out["amount_gbp"] = pd.to_numeric(out["amount_gbp"], errors="coerce").fillna(0.00)
        return out

    def _prepare_payroll(self, df: pd.DataFrame) -> pd.DataFrame:
        required = {"posting_period", "department_id", "account_code", "currency", "cost_component", "debit_local", "debit_gbp"}
        self._require_columns(df, required, "payroll_expense_lines.csv")
        out = df.copy()
        out["posting_period"] = out["posting_period"].astype(str)
        out["department_id"] = out["department_id"].astype(str)
        out["account_code"] = out["account_code"].apply(self._normalise_account_code)
        out["currency"] = out["currency"].astype(str).str.upper()
        out["cost_component"] = out["cost_component"].astype(str)
        out["debit_local"] = pd.to_numeric(out["debit_local"], errors="coerce").fillna(0.00)
        out["debit_gbp"] = pd.to_numeric(out["debit_gbp"], errors="coerce").fillna(0.00)
        return out[out["account_code"] == self.rules.payroll_account].copy()

    def _prepare_headcount_plan(self, df: pd.DataFrame) -> pd.DataFrame:
        required = {"position_id", "plan_status", "department_id", "currency", "planned_start_period"}
        self._require_columns(df, required, "headcount_plan.csv")
        out = df.copy()
        for col in ["position_id", "plan_status", "department_id", "currency", "planned_start_period"]:
            out[col] = out[col].fillna("").astype(str)
        out["currency"] = out["currency"].str.upper()
        return out

    # ------------------------------------------------------------------
    # Build logic
    # ------------------------------------------------------------------

    def _build_forecast_versions(self) -> pd.DataFrame:
        records = []
        for version_code, rule in self.SCENARIOS.items():
            row = {
                "forecast_version_code": version_code,
                "forecast_name": rule["name"],
                "fiscal_year": self.rules.fiscal_year,
                "scenario_type": rule["scenario_type"],
                "scenario_description": rule["description"],
                "cutover_period": self.rules.cutover_period,
                "actual_period_start": self.rules.planning_start_period,
                "actual_period_end": self.rules.cutover_period,
                "forecast_period_start": (pd.Timestamp(f"{self.rules.cutover_period}-01") + pd.DateOffset(months=1)).strftime("%Y-%m"),
                "forecast_period_end": self.rules.planning_end_period,
                "source_budget_version_code": self.rules.budget_version_code,
                "approval_status": "Management Forecast",
                "is_locked_flag": 0,
                "source_system": "planning_forecast_engine",
                "created_at": self.rules.created_at,
                "updated_at": self.rules.updated_at,
            }
            row["forecast_version_pk"] = self._generate_pk(version_code)
            records.append(row)
        return pd.DataFrame(records)[self.VERSION_COLUMNS]

    def _actual_financial_statement_totals(self, fs_df: pd.DataFrame) -> pd.DataFrame:
        """
        Return completed-period financial statement actuals for allocation.

        The AOP/forecast grain is a planning grain and revenue/non-payroll budget
        lines are GBP presentation rows. The Financial Statement extract, however,
        contains actuals by source ledger currency. For completed-month forecast
        blending, we consolidate actuals to GBP by posting_period + account_code
        before allocating them back to the AOP grain. This avoids dropping valid
        EUR/USD/SGD actual activity simply because the AOP line is denominated in
        GBP.
        """
        actual = fs_df[
            (fs_df["posting_period"] >= self.rules.planning_start_period)
            & (fs_df["posting_period"] <= self.rules.cutover_period)
            & (fs_df["statement_type"] == "Income Statement")
            & (fs_df["is_calculated_line"] == 0)
        ].copy()

        return (
            actual.groupby(["posting_period", "account_code"], as_index=False)
            .agg(actual_amount_gbp=("amount_gbp", "sum"))
        )

    def _actual_payroll_lines(self, budget_actual_rows: pd.DataFrame, payroll_df: pd.DataFrame) -> pd.DataFrame:
        payroll_actuals = (
            payroll_df[
                (payroll_df["posting_period"] >= self.rules.planning_start_period)
                & (payroll_df["posting_period"] <= self.rules.cutover_period)
            ]
            .groupby(["posting_period", "department_id", "currency", "cost_component"], as_index=False)
            .agg(actual_amount_local=("debit_local", "sum"), actual_amount_gbp=("debit_gbp", "sum"))
        )
        payroll_actuals["planning_driver"] = "PAYROLL_" + payroll_actuals["cost_component"].astype(str).str.upper()
        join_cols = ["posting_period", "department_id", "currency", "planning_driver"]
        rows = budget_actual_rows[budget_actual_rows["account_code"] == self.rules.payroll_account].copy()
        rows = rows.merge(payroll_actuals[join_cols + ["actual_amount_local", "actual_amount_gbp"]], on=join_cols, how="left")
        rows["actual_amount_local"] = rows["actual_amount_local"].fillna(rows["budget_amount_local"])
        rows["actual_amount_gbp"] = rows["actual_amount_gbp"].fillna(rows["budget_amount_gbp"])
        rows["forecast_basis"] = "ACTUAL_WORKFORCE_SUBLEDGER"
        return rows

    def _actual_allocated_nonpayroll_lines(self, budget_actual_rows: pd.DataFrame, fs_df: pd.DataFrame) -> pd.DataFrame:
        rows = budget_actual_rows[budget_actual_rows["account_code"] != self.rules.payroll_account].copy()
        fs_totals = self._actual_financial_statement_totals(fs_df)

        # Allocate consolidated GBP actuals to the AOP planning grain. Do not join
        # on currency here: the AOP revenue/non-payroll lines are GBP planning rows,
        # while the Financial Statement actuals retain ledger currencies.
        group_cols = ["posting_period", "account_code"]
        budget_group_totals = rows.groupby(group_cols, as_index=False).agg(group_budget_gbp=("budget_amount_gbp", "sum"))

        rows = rows.merge(budget_group_totals, on=group_cols, how="left")
        rows = rows.merge(fs_totals, on=group_cols, how="left")

        rows["actual_amount_gbp"] = rows["actual_amount_gbp"].fillna(rows["budget_amount_gbp"])
        rows["allocation_share"] = rows.apply(
            lambda row: 1.0 if float(row["group_budget_gbp"]) == 0 else float(row["budget_amount_gbp"]) / float(row["group_budget_gbp"]),
            axis=1,
        )

        rows["actual_amount_gbp"] = rows["actual_amount_gbp"] * rows["allocation_share"]

        # These are planning presentation lines. For GBP AOP rows, local = GBP.
        # If a future budget line is introduced in another currency, local falls
        # back to the GBP allocated amount rather than silently retaining budget.
        rows["actual_amount_local"] = rows["actual_amount_gbp"]
        rows["forecast_basis"] = "ACTUAL_FS_ALLOCATED_TO_AOP_GRAIN"
        return rows

    def _scenario_multiplier(self, row: pd.Series, scenario_rule: dict) -> float:
        account_code = str(row["account_code"])
        driver = str(row["planning_driver"])

        if account_code in {self.rules.revenue_account_saas, self.rules.revenue_account_legacy}:
            return float(scenario_rule["revenue_multiplier"])

        if account_code == self.rules.payroll_account or driver.startswith("PAYROLL_"):
            return float(scenario_rule["payroll_multiplier"])

        if driver == "MARKETING_SPEND_PERCENT_OF_REVENUE":
            return float(scenario_rule["revenue_multiplier"]) * float(scenario_rule["marketing_multiplier"])

        if driver == "HOSTING_COGS_PERCENT_OF_REVENUE":
            return float(scenario_rule["revenue_multiplier"]) * float(scenario_rule["hosting_rate_multiplier"])

        if driver == "PRODUCT_CLOUD_COGS_PERCENT_OF_REVENUE":
            return float(scenario_rule["revenue_multiplier"]) * float(scenario_rule["product_cloud_multiplier"])

        if driver == "CUSTOMER_SUPPORT_COGS_PERCENT_OF_REVENUE":
            return float(scenario_rule["revenue_multiplier"]) * float(scenario_rule["support_cogs_multiplier"])

        if "PERCENT_OF_PAYROLL" in driver:
            return float(scenario_rule["payroll_multiplier"]) * float(scenario_rule["payroll_scaled_opex_multiplier"])

        return 1.0

    def _forecast_future_lines(self, budget_future_rows: pd.DataFrame, scenario_rule: dict) -> pd.DataFrame:
        rows = budget_future_rows.copy()
        rows["scenario_multiplier"] = rows.apply(lambda row: self._scenario_multiplier(row, scenario_rule), axis=1)
        rows["actual_amount_local"] = rows["budget_amount_local"] * rows["scenario_multiplier"]
        rows["actual_amount_gbp"] = rows["budget_amount_gbp"] * rows["scenario_multiplier"]
        rows["forecast_basis"] = "SCENARIO_DRIVER_FORECAST"
        return rows

    def _make_line(self, base_row: pd.Series, version_code: str, scenario_type: str) -> dict:
        posting_period = str(base_row["posting_period"])
        period_start = pd.Timestamp(f"{posting_period}-01")
        line_id = self._next_line_id()
        key = "|".join(
            [
                version_code,
                posting_period,
                str(base_row["department_id"]),
                str(base_row["account_code"]),
                str(base_row["currency"]),
                str(base_row["planning_driver"]),
            ]
        )
        scenario_multiplier = float(base_row.get("scenario_multiplier", 1.0))
        return {
            "forecast_line_pk": self._generate_pk(key),
            "forecast_line_id": line_id,
            "forecast_version_code": version_code,
            "scenario_type": scenario_type,
            "fiscal_year": int(base_row["fiscal_year"]),
            "posting_period": posting_period,
            "period_start_date": period_start.date().isoformat(),
            "period_end_date": self._period_end(period_start).date().isoformat(),
            "department_id": str(base_row["department_id"]),
            "account_code": str(base_row["account_code"]),
            "account_name": str(base_row["account_name"]),
            "account_class": str(base_row["account_class"]),
            "financial_statement": str(base_row["financial_statement"]),
            "currency": str(base_row["currency"]),
            "forecast_amount_local": self._round_money(base_row["actual_amount_local"]),
            "forecast_amount_gbp": self._round_money(base_row["actual_amount_gbp"]),
            "source_budget_amount_local": self._round_money(base_row["budget_amount_local"]),
            "source_budget_amount_gbp": self._round_money(base_row["budget_amount_gbp"]),
            "forecast_basis": str(base_row["forecast_basis"]),
            "planning_driver": str(base_row["planning_driver"]),
            "driver_quantity": round(float(base_row.get("driver_quantity", 0.00)), 6),
            "driver_rate": round(float(base_row.get("driver_rate", 0.00)), 6),
            "scenario_multiplier": round(scenario_multiplier, 6),
            "forecast_method": self._get_forecast_method(base_row),
            "source_budget_version_code": self.rules.budget_version_code,
            "source_budget_line_id": str(base_row["budget_line_id"]),
            "is_locked_flag": 0,
            "source_system": "planning_forecast_engine",
            "is_system_generated": 1,
            "is_defect_flag": int(base_row.get("is_defect_flag", 0) or 0),
            "defect_type": base_row.get("defect_type", None),
            "created_at": self.rules.created_at,
            "updated_at": self.rules.updated_at,
        }

    @staticmethod
    def _get_forecast_method(row: pd.Series) -> str:
        basis = str(row["forecast_basis"])
        if basis == "ACTUAL_WORKFORCE_SUBLEDGER":
            return "Completed month payroll actual from workforce payroll expense extract"
        if basis == "ACTUAL_FS_ALLOCATED_TO_AOP_GRAIN":
            return "Completed month financial statement actual allocated to AOP department/driver grain"
        return "Future month scenario driver applied to locked AOP baseline"

    def _build_forecast_lines(
        self,
        versions_df: pd.DataFrame,
        budget_lines_df: pd.DataFrame,
        fs_df: pd.DataFrame,
        payroll_df: pd.DataFrame,
    ) -> pd.DataFrame:
        records = []
        actual_rows = budget_lines_df[budget_lines_df["posting_period"] <= self.rules.cutover_period].copy()
        future_rows = budget_lines_df[budget_lines_df["posting_period"] > self.rules.cutover_period].copy()

        actual_payroll = self._actual_payroll_lines(actual_rows, payroll_df)
        actual_nonpayroll = self._actual_allocated_nonpayroll_lines(actual_rows, fs_df)
        actual_blend = pd.concat([actual_payroll, actual_nonpayroll], ignore_index=True)
        actual_blend["scenario_multiplier"] = 1.0

        for _, version in versions_df.iterrows():
            version_code = str(version["forecast_version_code"])
            scenario_type = str(version["scenario_type"])
            scenario_rule = self.SCENARIOS[version_code]
            future_blend = self._forecast_future_lines(future_rows, scenario_rule)
            combined = pd.concat([actual_blend, future_blend], ignore_index=True)
            for _, row in combined.iterrows():
                records.append(self._make_line(row, version_code, scenario_type))

        lines_df = pd.DataFrame(records)
        if lines_df.empty:
            raise ValueError("Forecast line generation produced no rows.")
        lines_df = lines_df[self.LINE_COLUMNS]
        lines_df = lines_df.sort_values(
            ["forecast_version_code", "posting_period", "department_id", "account_code", "currency", "planning_driver"]
        ).reset_index(drop=True)
        return lines_df

    # ------------------------------------------------------------------
    # Validation / logging
    # ------------------------------------------------------------------

    def _validate_outputs(self, versions_df: pd.DataFrame, lines_df: pd.DataFrame) -> None:
        if versions_df.empty:
            raise ValueError("forecast_versions.csv output is empty.")
        if lines_df.empty:
            raise ValueError("forecast_lines.csv output is empty.")

        if versions_df["forecast_version_pk"].duplicated().any():
            raise ValueError("Duplicate forecast_version_pk values generated.")
        if versions_df["forecast_version_code"].duplicated().any():
            raise ValueError("Duplicate forecast_version_code values generated.")
        if lines_df["forecast_line_pk"].duplicated().any():
            raise ValueError("Duplicate forecast_line_pk values generated.")
        if lines_df["forecast_line_id"].duplicated().any():
            raise ValueError("Duplicate forecast_line_id values generated.")

        grain = ["forecast_version_code", "posting_period", "department_id", "account_code", "currency", "planning_driver"]
        duplicate_grain_count = int(lines_df.duplicated(subset=grain).sum())
        if duplicate_grain_count:
            raise ValueError(f"Duplicate forecast line grain rows generated: {duplicate_grain_count:,}")

        for column in ["forecast_amount_local", "forecast_amount_gbp"]:
            if (pd.to_numeric(lines_df[column], errors="coerce") < -self.rules.rounding_tolerance).any():
                raise ValueError(f"Forecast lines contain negative {column} values.")

        actual_periods = set(lines_df[lines_df["posting_period"] <= self.rules.cutover_period]["forecast_basis"].unique())
        if not actual_periods.issubset({"ACTUAL_WORKFORCE_SUBLEDGER", "ACTUAL_FS_ALLOCATED_TO_AOP_GRAIN"}):
            raise ValueError(f"Unexpected forecast_basis in actual period rows: {sorted(actual_periods)}")

        future_basis = set(lines_df[lines_df["posting_period"] > self.rules.cutover_period]["forecast_basis"].unique())
        if future_basis != {"SCENARIO_DRIVER_FORECAST"}:
            raise ValueError(f"Unexpected forecast_basis in future period rows: {sorted(future_basis)}")

        actual_signature = (
            lines_df[lines_df["posting_period"] <= self.rules.cutover_period]
            .groupby(["forecast_version_code"])["forecast_amount_gbp"]
            .sum()
            .round(2)
        )
        if actual_signature.nunique() != 1:
            raise ValueError("Actual-period forecast amounts differ across scenarios; completed months should be identical.")

        # Completed-month non-payroll / revenue actuals should be fully allocated
        # from the Financial Statement extract at account level. This catches
        # accidental currency-key joins that drop non-GBP actuals.
        actual_fs_allocated = lines_df[
            (lines_df["posting_period"] <= self.rules.cutover_period)
            & (lines_df["forecast_basis"] == "ACTUAL_FS_ALLOCATED_TO_AOP_GRAIN")
        ]

        if actual_fs_allocated.empty:
            raise ValueError("No completed-period Financial Statement actual rows were allocated to the forecast.")

        future_revenue = lines_df[
            (lines_df["posting_period"] > self.rules.cutover_period)
            & (lines_df["account_class"] == "Revenue")
        ]
        revenue_by_version = future_revenue.groupby("forecast_version_code")["forecast_amount_gbp"].sum()
        if revenue_by_version.get("FC_UPSIDE_CASE", 0.0) <= revenue_by_version.get("FC_BASE_CASE", 0.0):
            raise ValueError("Upside forecast revenue should exceed Base Case revenue.")
        if revenue_by_version.get("FC_DOWNSIDE_CASE", 0.0) >= revenue_by_version.get("FC_BASE_CASE", 0.0):
            raise ValueError("Downside forecast revenue should be below Base Case revenue.")

        logger.info("Forecast output validation passed.")

    def _log_review(self, versions_df: pd.DataFrame, lines_df: pd.DataFrame) -> None:
        logger.info("----- Forecast / Reforecast Scenario Review -----")
        logger.info("Forecast versions: %s", f"{len(versions_df):,}")
        logger.info("Forecast lines: %s", f"{len(lines_df):,}")
        logger.info(
            "Posting period range: %s to %s",
            lines_df["posting_period"].min(),
            lines_df["posting_period"].max(),
        )
        logger.info("Cutover period: %s", self.rules.cutover_period)
        logger.info(
            "Forecast lines by version:\n%s",
            lines_df["forecast_version_code"].value_counts().to_string(),
        )
        logger.info(
            "Forecast basis counts:\n%s",
            lines_df["forecast_basis"].value_counts().to_string(),
        )
        logger.info(
            "Forecast amount GBP by version/account class:\n%s",
            lines_df.groupby(["forecast_version_code", "account_class"])["forecast_amount_gbp"]
            .sum()
            .round(2)
            .to_string(),
        )
        logger.info(
            "Future-period revenue by version GBP:\n%s",
            lines_df[
                (lines_df["posting_period"] > self.rules.cutover_period)
                & (lines_df["account_class"] == "Revenue")
            ]
            .groupby("forecast_version_code")["forecast_amount_gbp"]
            .sum()
            .round(2)
            .to_string(),
        )
        logger.info("-------------------------------------------------")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        logger.info("Generating Phase 3M.1 Forecast / Reforecast scenario source extracts.")
        _, budget_lines_df, fs_df, payroll_df, _ = self._load_dependencies()
        versions_df = self._build_forecast_versions()
        lines_df = self._build_forecast_lines(versions_df, budget_lines_df, fs_df, payroll_df)
        self._validate_outputs(versions_df, lines_df)
        self._log_review(versions_df, lines_df)
        return versions_df, lines_df

    def save(self, versions_df: pd.DataFrame, lines_df: pd.DataFrame) -> None:
        output_dir = get_raw_data_path("planning")
        output_dir.mkdir(parents=True, exist_ok=True)
        versions_path = output_dir / self.versions_filename
        lines_path = output_dir / self.lines_filename
        versions_df.to_csv(versions_path, index=False)
        lines_df.to_csv(lines_path, index=False)
        logger.info("Forecast versions saved to %s", versions_path)
        logger.info("Forecast lines saved to %s", lines_path)


if __name__ == "__main__":
    generator = ForecastGenerator()
    forecast_versions, forecast_lines = generator.generate()
    generator.save(forecast_versions, forecast_lines)
