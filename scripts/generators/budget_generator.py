"""
budget_generator.py

Project Atlas / Nexus Technologies
Phase 3L.1 - Annual Operating Plan / Budget Source Generation

Purpose
-------
Generates:
- data/raw/planning/budget_versions.csv
- data/raw/planning/budget_lines.csv

This phase creates an independent FP&A planning ledger. It does not mutate
actuals, the ERP GL, Trial Balance, Financial Statement extracts, controls, or
findings. Amounts use planning presentation signs: revenue and expenses are
stored as positive targets / spend envelopes.

Design
------
Inputs:
- department catalogue / observed workforce departments
- chart_of_accounts.csv
- workforce/headcount_plan.csv
- workforce/payroll_expense_lines.csv
- exchange_rates_2022_2026.csv

Outputs:
- budget_versions.csv = budget metadata / governance layer
- budget_lines.csv = monthly budget line ledger

Grain
-----
budget_lines.csv:
    budget_version_code + posting_period + department_id + account_code +
    currency + planning_driver
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("BudgetGenerator", "generation_execution.log")


@dataclass(frozen=True)
class BudgetGenerationRules:
    created_at: str = "2026-06-03"
    updated_at: str = "2026-06-03"
    planning_start_period: str = "2025-01"
    planning_end_period: str = "2026-12"
    current_reporting_period: str = "2026-06"
    fy2025_revenue_target_gbp: float = 72_000_000.00
    fy2026_revenue_target_gbp: float = 96_000_000.00
    fy2025_payroll_uplift: float = 0.035
    fy2026_payroll_uplift: float = 0.055
    budget_revenue_account_saas: str = "4100"
    budget_revenue_account_legacy: str = "4110"
    hosting_cogs_account: str = "5100"
    support_cogs_account: str = "5200"
    payroll_account: str = "6100"
    sales_marketing_account: str = "6200"
    software_tools_account: str = "6300"
    rent_office_account: str = "6400"
    professional_fees_account: str = "6500"
    travel_account: str = "6600"
    depreciation_account: str = "6900"
    rounding_tolerance: float = 1.00


class BudgetGenerator:
    """
    Generate AOP budget versions and monthly budget lines.
    """

    versions_filename = "budget_versions.csv"
    lines_filename = "budget_lines.csv"

    VERSION_COLUMNS = [
        "budget_version_pk",
        "budget_version_code",
        "budget_name",
        "fiscal_year",
        "scenario_type",
        "approval_status",
        "approved_by",
        "approval_date",
        "is_locked_flag",
        "planning_start_period",
        "planning_end_period",
        "source_system",
        "created_at",
        "updated_at",
    ]

    LINE_COLUMNS = [
        "budget_line_pk",
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
        "budget_method",
        "is_locked_flag",
        "source_system",
        "is_system_generated",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.rules = BudgetGenerationRules()
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
    def _normalise_bool_int(value: object, default: int = 0) -> int:
        if pd.isna(value):
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value == 1)
        value_str = str(value).strip().lower()
        if value_str in {"1", "true", "yes", "y"}:
            return 1
        if value_str in {"0", "false", "no", "n"}:
            return 0
        return default

    @staticmethod
    def _require_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f"{name} is missing required columns: {sorted(missing)}")

    def _next_line_id(self) -> str:
        self._line_counter += 1
        return f"BUD-LN-{self._line_counter:010d}"

    @staticmethod
    def _period_range(start_period: str, end_period: str) -> list[pd.Timestamp]:
        return pd.date_range(
            start=pd.Timestamp(f"{start_period}-01"),
            end=pd.Timestamp(f"{end_period}-01"),
            freq="MS",
        ).to_list()

    @staticmethod
    def _fiscal_year_from_period(period: str) -> int:
        # Phase 3L uses calendar-year AOPs because upstream source periods are YYYY-MM.
        return int(str(period)[:4])

    @staticmethod
    def _period_end(period_start: pd.Timestamp) -> pd.Timestamp:
        return period_start + pd.offsets.MonthEnd(0)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @staticmethod
    def _load_csv(path: Path, dataset_name: str) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(
                f"{dataset_name} not found at {path}. Run upstream generators first."
            )
        return pd.read_csv(path)

    def _load_optional_department_catalog(self, workforce_departments: Iterable[str]) -> pd.DataFrame:
        # Support both earlier and newer department locations.
        candidates = [
            get_raw_data_path("departments") / "department_catalog.csv",
            get_raw_data_path("hris") / "departments.csv",
            get_raw_data_path("hris") / "department_catalog.csv",
        ]

        for path in candidates:
            if path.exists():
                departments = pd.read_csv(path)
                if "department_id" not in departments.columns:
                    continue
                departments = departments.copy()
                departments["department_id"] = departments["department_id"].astype(str)
                if "active_flag" in departments.columns:
                    departments["active_flag"] = departments["active_flag"].apply(
                        lambda x: self._normalise_bool_int(x, default=1)
                    )
                    departments = departments[departments["active_flag"] == 1].copy()
                logger.info("Loaded department catalogue: %s rows.", f"{len(departments):,}")
                return departments

        # Fallback keeps the generator usable where only workforce extracts are mounted.
        observed = sorted({str(x) for x in workforce_departments if str(x).strip()})
        logger.warning(
            "Department catalogue not found. Falling back to observed workforce departments: %s",
            observed,
        )
        return pd.DataFrame(
            {
                "department_id": observed,
                "department_name": [x.replace("DEPT_", "").replace("_", " ").title() for x in observed],
                "active_flag": 1,
            }
        )

    def _load_dependencies(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        accounting_dir = get_raw_data_path("accounting")
        workforce_dir = get_raw_data_path("workforce")
        fx_dir = get_raw_data_path("fx")

        coa_df = self._load_csv(accounting_dir / "chart_of_accounts.csv", "chart_of_accounts.csv")
        headcount_plan_df = self._load_csv(workforce_dir / "headcount_plan.csv", "headcount_plan.csv")
        payroll_df = self._load_csv(workforce_dir / "payroll_expense_lines.csv", "payroll_expense_lines.csv")
        fx_df = self._load_csv(fx_dir / "exchange_rates_2022_2026.csv", "exchange_rates_2022_2026.csv")

        coa_df = self._prepare_coa(coa_df)
        headcount_plan_df = self._prepare_headcount_plan(headcount_plan_df)
        payroll_df = self._prepare_payroll(payroll_df)
        fx_df = self._prepare_fx(fx_df)
        observed_workforce_departments = sorted(
            set(payroll_df["department_id"].astype(str))
            .union(set(headcount_plan_df["department_id"].astype(str)))
        )

        departments_df = self._load_optional_department_catalog(
            observed_workforce_departments
        )
        departments_df = self._prepare_departments(departments_df)

        existing_departments = set(departments_df["department_id"].astype(str))
        missing_workforce_departments = sorted(
            set(observed_workforce_departments).difference(existing_departments)
        )

        if missing_workforce_departments:
            logger.warning(
                "Department catalogue missing workforce-observed departments. "
                "Appending controlled planning/suspense departments: %s",
                missing_workforce_departments,
            )

            suspense_departments = pd.DataFrame(
                {
                    "department_id": missing_workforce_departments,
                    "department_name": [
                        (
                            "Unmapped / Suspense Department"
                            if department_id == "DEPT_UNKNOWN"
                            else department_id.replace("DEPT_", "").replace("_", " ").title()
                        )
                        for department_id in missing_workforce_departments
                    ],
                    "active_flag": 1,
                }
            )

            departments_df = pd.concat(
                [departments_df, suspense_departments],
                ignore_index=True,
            )

            departments_df = self._prepare_departments(departments_df)

        logger.info(
            "Loaded budget dependencies: %s CoA rows, %s payroll rows, %s headcount plan rows, %s departments, %s FX rows.",
            f"{len(coa_df):,}",
            f"{len(payroll_df):,}",
            f"{len(headcount_plan_df):,}",
            f"{len(departments_df):,}",
            f"{len(fx_df):,}",
        )

        return coa_df, payroll_df, headcount_plan_df, departments_df, fx_df

    def _prepare_coa(self, coa_df: pd.DataFrame) -> pd.DataFrame:
        df = coa_df.copy()
        self._require_columns(
            df,
            {"account_code", "account_name", "account_class", "financial_statement", "active_flag"},
            "chart_of_accounts.csv",
        )
        df["account_code"] = df["account_code"].apply(self._normalise_account_code)
        df["account_name"] = df["account_name"].astype(str)
        df["account_class"] = df["account_class"].astype(str)
        df["financial_statement"] = df["financial_statement"].astype(str)
        df["active_flag"] = df["active_flag"].apply(lambda x: self._normalise_bool_int(x, default=1))
        df = df[df["active_flag"] == 1].copy()
        if df["account_code"].duplicated().any():
            raise ValueError("chart_of_accounts.csv contains duplicate active account_code values.")

        required_accounts = {
            self.rules.budget_revenue_account_saas,
            self.rules.budget_revenue_account_legacy,
            self.rules.hosting_cogs_account,
            self.rules.support_cogs_account,
            self.rules.payroll_account,
            self.rules.sales_marketing_account,
            self.rules.software_tools_account,
            self.rules.rent_office_account,
            self.rules.professional_fees_account,
            self.rules.travel_account,
            self.rules.depreciation_account,
        }
        missing = required_accounts.difference(set(df["account_code"]))
        if missing:
            raise ValueError(f"chart_of_accounts.csv missing required budget accounts: {sorted(missing)}")
        return df

    def _prepare_headcount_plan(self, headcount_plan_df: pd.DataFrame) -> pd.DataFrame:
        df = headcount_plan_df.copy()
        self._require_columns(
            df,
            {"position_id", "plan_status", "department_id", "currency", "planned_start_period", "target_salary_mid_gbp"},
            "headcount_plan.csv",
        )
        for column in ["position_id", "plan_status", "department_id", "currency", "planned_start_period"]:
            df[column] = df[column].fillna("").astype(str)
        df["currency"] = df["currency"].str.upper()
        df["target_salary_mid_gbp"] = pd.to_numeric(df["target_salary_mid_gbp"], errors="coerce").fillna(0.00)
        return df

    def _prepare_payroll(self, payroll_df: pd.DataFrame) -> pd.DataFrame:
        df = payroll_df.copy()
        self._require_columns(
            df,
            {"posting_period", "department_id", "account_code", "currency", "cost_component", "debit_local", "debit_gbp"},
            "payroll_expense_lines.csv",
        )
        df["posting_period"] = df["posting_period"].astype(str)
        df["department_id"] = df["department_id"].astype(str)
        df["account_code"] = df["account_code"].apply(self._normalise_account_code)
        df["currency"] = df["currency"].astype(str).str.upper()
        df["cost_component"] = df["cost_component"].astype(str)
        df["debit_local"] = pd.to_numeric(df["debit_local"], errors="coerce").fillna(0.00)
        df["debit_gbp"] = pd.to_numeric(df["debit_gbp"], errors="coerce").fillna(0.00)
        df = df[df["account_code"] == self.rules.payroll_account].copy()
        if df.empty:
            raise ValueError("payroll_expense_lines.csv contains no payroll account rows for account 6100.")
        return df

    def _prepare_departments(self, departments_df: pd.DataFrame) -> pd.DataFrame:
        df = departments_df.copy()
        self._require_columns(df, {"department_id"}, "department catalogue")
        df["department_id"] = df["department_id"].astype(str)
        if "active_flag" not in df.columns:
            df["active_flag"] = 1
        df["active_flag"] = df["active_flag"].apply(lambda x: self._normalise_bool_int(x, default=1))
        df = df[df["active_flag"] == 1].copy()
        if df["department_id"].duplicated().any():
            raise ValueError("Department catalogue contains duplicate active department_id values.")
        return df

    def _prepare_fx(self, fx_df: pd.DataFrame) -> pd.DataFrame:
        df = fx_df.copy()
        self._require_columns(
            df,
            {"currency_code", "month_start_date", "monthly_average_rate_to_gbp"},
            "exchange_rates_2022_2026.csv",
        )
        df["currency_code"] = df["currency_code"].astype(str).str.upper()
        df["month_start_date"] = pd.to_datetime(df["month_start_date"], errors="coerce")
        df["posting_period"] = df["month_start_date"].dt.strftime("%Y-%m")
        df["monthly_average_rate_to_gbp"] = pd.to_numeric(
            df["monthly_average_rate_to_gbp"], errors="coerce"
        ).fillna(1.00)
        return df[["posting_period", "currency_code", "monthly_average_rate_to_gbp"]].copy()

    # ------------------------------------------------------------------
    # Core build logic
    # ------------------------------------------------------------------

    def _build_budget_versions(self) -> pd.DataFrame:
        records = [
            {
                "budget_version_code": "AOP_FY2025_ORIGINAL",
                "budget_name": "FY2025 Original Annual Operating Plan",
                "fiscal_year": 2025,
                "scenario_type": "Annual Operating Plan",
                "approval_status": "Approved",
                "approved_by": "Board of Directors",
                "approval_date": "2024-12-15",
                "is_locked_flag": 1,
                "planning_start_period": "2025-01",
                "planning_end_period": "2025-12",
            },
            {
                "budget_version_code": "AOP_FY2026_BOARD_APPROVED",
                "budget_name": "FY2026 Board Approved Annual Operating Plan",
                "fiscal_year": 2026,
                "scenario_type": "Annual Operating Plan",
                "approval_status": "Board Approved",
                "approved_by": "Board of Directors",
                "approval_date": "2025-12-18",
                "is_locked_flag": 1,
                "planning_start_period": "2026-01",
                "planning_end_period": "2026-12",
            },
        ]

        versions = []
        for row in records:
            row = row.copy()
            row["budget_version_pk"] = self._generate_pk(row["budget_version_code"])
            row["source_system"] = "planning_aop_engine"
            row["created_at"] = self.rules.created_at
            row["updated_at"] = self.rules.updated_at
            versions.append(row)

        return pd.DataFrame(versions)[self.VERSION_COLUMNS]

    @staticmethod
    def _seasonality_weights() -> dict[int, float]:
        # Enterprise SaaS AOP pattern: slower Q1, mid-year close uplift, strong December close.
        raw = {
            1: 0.065,
            2: 0.066,
            3: 0.071,
            4: 0.078,
            5: 0.080,
            6: 0.105,
            7: 0.078,
            8: 0.079,
            9: 0.083,
            10: 0.086,
            11: 0.089,
            12: 0.120,
        }
        total = sum(raw.values())
        return {month: weight / total for month, weight in raw.items()}

    def _account_lookup(self, coa_df: pd.DataFrame) -> dict[str, dict]:
        return {
            str(row["account_code"]): {
                "account_name": str(row["account_name"]),
                "account_class": str(row["account_class"]),
                "financial_statement": str(row["financial_statement"]),
            }
            for _, row in coa_df.iterrows()
        }

    def _new_line(
        self,
        *,
        budget_version_code: str,
        fiscal_year: int,
        posting_period: str,
        department_id: str,
        account_code: str,
        currency: str,
        budget_amount_local: float,
        budget_amount_gbp: float,
        planning_driver: str,
        driver_quantity: float,
        driver_rate: float,
        budget_method: str,
        account_lookup: dict[str, dict],
    ) -> dict:
        period_start = pd.Timestamp(f"{posting_period}-01")
        line_id = self._next_line_id()
        account = account_lookup[str(account_code)]
        key = "|".join(
            [budget_version_code, posting_period, department_id, str(account_code), currency, planning_driver]
        )
        return {
            "budget_line_pk": self._generate_pk(key),
            "budget_line_id": line_id,
            "budget_version_code": budget_version_code,
            "fiscal_year": fiscal_year,
            "posting_period": posting_period,
            "period_start_date": period_start.date().isoformat(),
            "period_end_date": self._period_end(period_start).date().isoformat(),
            "department_id": department_id,
            "account_code": str(account_code),
            "account_name": account["account_name"],
            "account_class": account["account_class"],
            "financial_statement": account["financial_statement"],
            "currency": currency,
            "budget_amount_local": self._round_money(budget_amount_local),
            "budget_amount_gbp": self._round_money(budget_amount_gbp),
            "planning_driver": planning_driver,
            "driver_quantity": round(float(driver_quantity), 6),
            "driver_rate": round(float(driver_rate), 6),
            "budget_method": budget_method,
            "is_locked_flag": 1,
            "source_system": "planning_aop_engine",
            "is_system_generated": 1,
            "is_defect_flag": 0,
            "defect_type": None,
            "created_at": self.rules.created_at,
            "updated_at": self.rules.updated_at,
        }

    def _build_revenue_budget_lines(self, versions_df: pd.DataFrame, coa_df: pd.DataFrame) -> list[dict]:
        records: list[dict] = []
        account_lookup = self._account_lookup(coa_df)
        weights = self._seasonality_weights()

        revenue_targets = {
            2025: self.rules.fy2025_revenue_target_gbp,
            2026: self.rules.fy2026_revenue_target_gbp,
        }

        # DataPulse legacy runoff story: legacy share declines as migration continues.
        account_mix = {
            2025: {
                self.rules.budget_revenue_account_saas: 0.88,
                self.rules.budget_revenue_account_legacy: 0.12,
            },
            2026: {
                self.rules.budget_revenue_account_saas: 0.92,
                self.rules.budget_revenue_account_legacy: 0.08,
            },
        }

        for _, version in versions_df.iterrows():
            fy = int(version["fiscal_year"])
            target = float(revenue_targets[fy])
            for period_start in self._period_range(version["planning_start_period"], version["planning_end_period"]):
                posting_period = period_start.strftime("%Y-%m")
                month_weight = weights[int(period_start.month)]
                monthly_total = target * month_weight
                for account_code, share in account_mix[fy].items():
                    amount = monthly_total * share
                    records.append(
                        self._new_line(
                            budget_version_code=str(version["budget_version_code"]),
                            fiscal_year=fy,
                            posting_period=posting_period,
                            department_id="DEPT_SALES",
                            account_code=account_code,
                            currency="GBP",
                            budget_amount_local=amount,
                            budget_amount_gbp=amount,
                            planning_driver="SUBSCRIPTION_REVENUE_TARGET",
                            driver_quantity=monthly_total,
                            driver_rate=share,
                            budget_method="Annual revenue target phased by enterprise SaaS seasonality and DataPulse migration mix",
                            account_lookup=account_lookup,
                        )
                    )
        return records

    def _build_payroll_budget_lines(
        self,
        versions_df: pd.DataFrame,
        payroll_df: pd.DataFrame,
        headcount_plan_df: pd.DataFrame,
        coa_df: pd.DataFrame,
    ) -> list[dict]:
        records: list[dict] = []
        account_lookup = self._account_lookup(coa_df)
        uplift_by_fy = {
            2025: self.rules.fy2025_payroll_uplift,
            2026: self.rules.fy2026_payroll_uplift,
        }

        payroll_base = (
            payroll_df.groupby(["posting_period", "department_id", "currency", "cost_component"], as_index=False)
            .agg(
                budget_amount_local=("debit_local", "sum"),
                budget_amount_gbp=("debit_gbp", "sum"),
                employee_count=("employee_count", "max") if "employee_count" in payroll_df.columns else ("debit_gbp", "size"),
            )
        )

        # Active/open headcount driver used for explanatory quantities only.
        active_plan = headcount_plan_df[headcount_plan_df["plan_status"].isin(["ACTIVE", "OPEN_BUDGETED", "BACKFILL"])].copy()
        plan_counts = (
            active_plan.groupby(["department_id", "currency"], as_index=False)
            .agg(plan_position_count=("position_id", "nunique"))
        )

        payroll_base = payroll_base.merge(plan_counts, on=["department_id", "currency"], how="left")
        payroll_base["plan_position_count"] = payroll_base["plan_position_count"].fillna(0).astype(float)

        for _, version in versions_df.iterrows():
            fy = int(version["fiscal_year"])
            uplift = uplift_by_fy[fy]
            for period_start in self._period_range(version["planning_start_period"], version["planning_end_period"]):
                posting_period = period_start.strftime("%Y-%m")
                period_rows = payroll_base[payroll_base["posting_period"] == posting_period].copy()

                # If a specific budget month is missing, fall back to latest available payroll month.
                if period_rows.empty:
                    latest_period = payroll_base["posting_period"].max()
                    period_rows = payroll_base[payroll_base["posting_period"] == latest_period].copy()

                for _, row in period_rows.iterrows():
                    local_amount = float(row["budget_amount_local"]) * (1 + uplift)
                    gbp_amount = float(row["budget_amount_gbp"]) * (1 + uplift)
                    records.append(
                        self._new_line(
                            budget_version_code=str(version["budget_version_code"]),
                            fiscal_year=fy,
                            posting_period=posting_period,
                            department_id=str(row["department_id"]),
                            account_code=self.rules.payroll_account,
                            currency=str(row["currency"]),
                            budget_amount_local=local_amount,
                            budget_amount_gbp=gbp_amount,
                            planning_driver=f"PAYROLL_{str(row['cost_component']).upper()}",
                            driver_quantity=float(row.get("plan_position_count", 0.00)),
                            driver_rate=1 + uplift,
                            budget_method="Workforce cost run-rate from payroll expense lines with annual merit / burden uplift",
                            account_lookup=account_lookup,
                        )
                    )
        return records

    def _revenue_by_version_period(self, revenue_records: list[dict]) -> pd.DataFrame:
        revenue_df = pd.DataFrame(revenue_records)
        return (
            revenue_df.groupby(["budget_version_code", "fiscal_year", "posting_period"], as_index=False)
            .agg(revenue_budget_gbp=("budget_amount_gbp", "sum"))
        )

    def _payroll_by_version_period_department(self, payroll_records: list[dict]) -> pd.DataFrame:
        payroll_df = pd.DataFrame(payroll_records)
        return (
            payroll_df.groupby(["budget_version_code", "fiscal_year", "posting_period", "department_id"], as_index=False)
            .agg(payroll_budget_gbp=("budget_amount_gbp", "sum"))
        )

    def _build_nonpayroll_budget_lines(
        self,
        versions_df: pd.DataFrame,
        revenue_records: list[dict],
        payroll_records: list[dict],
        coa_df: pd.DataFrame,
    ) -> list[dict]:
        records: list[dict] = []
        account_lookup = self._account_lookup(coa_df)
        revenue = self._revenue_by_version_period(revenue_records)
        payroll = self._payroll_by_version_period_department(payroll_records)

        # COGS and growth spend are consolidated GBP AOP lines. Payroll remains local-currency by department.
        for _, row in revenue.iterrows():
            version_code = str(row["budget_version_code"])
            fy = int(row["fiscal_year"])
            posting_period = str(row["posting_period"])
            revenue_gbp = float(row["revenue_budget_gbp"])

            cogs_assumptions = [
                ("DEPT_ENG", self.rules.hosting_cogs_account, "HOSTING_COGS_PERCENT_OF_REVENUE", 0.145),
                ("DEPT_PRODUCT", self.rules.hosting_cogs_account, "PRODUCT_CLOUD_COGS_PERCENT_OF_REVENUE", 0.045),
                ("DEPT_CS", self.rules.support_cogs_account, "CUSTOMER_SUPPORT_COGS_PERCENT_OF_REVENUE", 0.035),
                ("DEPT_MARKETING", self.rules.sales_marketing_account, "MARKETING_SPEND_PERCENT_OF_REVENUE", 0.155 if fy == 2025 else 0.175),
            ]

            for department_id, account_code, driver, rate in cogs_assumptions:
                amount = revenue_gbp * rate
                records.append(
                    self._new_line(
                        budget_version_code=version_code,
                        fiscal_year=fy,
                        posting_period=posting_period,
                        department_id=department_id,
                        account_code=account_code,
                        currency="GBP",
                        budget_amount_local=amount,
                        budget_amount_gbp=amount,
                        planning_driver=driver,
                        driver_quantity=revenue_gbp,
                        driver_rate=rate,
                        budget_method="Revenue-linked planning driver",
                        account_lookup=account_lookup,
                    )
                )

        # Headcount/payroll-scaled OpEx by department.
        for _, row in payroll.iterrows():
            version_code = str(row["budget_version_code"])
            fy = int(row["fiscal_year"])
            posting_period = str(row["posting_period"])
            department_id = str(row["department_id"])
            payroll_gbp = float(row["payroll_budget_gbp"])
            if payroll_gbp <= 0:
                continue

            op_ex_assumptions = [
                (self.rules.software_tools_account, "SOFTWARE_TOOLS_PERCENT_OF_PAYROLL", 0.080),
                (self.rules.rent_office_account, "OFFICE_COST_PERCENT_OF_PAYROLL", 0.045),
                (self.rules.professional_fees_account, "PROFESSIONAL_FEES_PERCENT_OF_PAYROLL", 0.030),
                (self.rules.travel_account, "TRAVEL_PERCENT_OF_PAYROLL", 0.025 if department_id == "DEPT_SALES" else 0.010),
                (self.rules.depreciation_account, "DEPRECIATION_PERCENT_OF_PAYROLL", 0.018),
            ]
            for account_code, driver, rate in op_ex_assumptions:
                amount = payroll_gbp * rate
                records.append(
                    self._new_line(
                        budget_version_code=version_code,
                        fiscal_year=fy,
                        posting_period=posting_period,
                        department_id=department_id,
                        account_code=account_code,
                        currency="GBP",
                        budget_amount_local=amount,
                        budget_amount_gbp=amount,
                        planning_driver=driver,
                        driver_quantity=payroll_gbp,
                        driver_rate=rate,
                        budget_method="Department OpEx scaled from workforce cost base",
                        account_lookup=account_lookup,
                    )
                )
        return records

    def _build_budget_lines(
        self,
        versions_df: pd.DataFrame,
        payroll_df: pd.DataFrame,
        headcount_plan_df: pd.DataFrame,
        departments_df: pd.DataFrame,
        coa_df: pd.DataFrame,
    ) -> pd.DataFrame:
        revenue_records = self._build_revenue_budget_lines(versions_df, coa_df)
        payroll_records = self._build_payroll_budget_lines(versions_df, payroll_df, headcount_plan_df, coa_df)
        nonpayroll_records = self._build_nonpayroll_budget_lines(
            versions_df=versions_df,
            revenue_records=revenue_records,
            payroll_records=payroll_records,
            coa_df=coa_df,
        )

        lines_df = pd.DataFrame(revenue_records + payroll_records + nonpayroll_records)
        if lines_df.empty:
            raise ValueError("Budget line generation produced no rows.")

        # Consolidate accidental duplicate grain rows from shared drivers.
        grain = ["budget_version_code", "posting_period", "department_id", "account_code", "currency", "planning_driver"]
        if lines_df.duplicated(subset=grain).any():
            grouped = (
                lines_df.groupby(grain, as_index=False)
                .agg(
                    budget_line_id=("budget_line_id", "first"),
                    fiscal_year=("fiscal_year", "first"),
                    period_start_date=("period_start_date", "first"),
                    period_end_date=("period_end_date", "first"),
                    account_name=("account_name", "first"),
                    account_class=("account_class", "first"),
                    financial_statement=("financial_statement", "first"),
                    budget_amount_local=("budget_amount_local", "sum"),
                    budget_amount_gbp=("budget_amount_gbp", "sum"),
                    driver_quantity=("driver_quantity", "sum"),
                    driver_rate=("driver_rate", "mean"),
                    budget_method=("budget_method", "first"),
                    is_locked_flag=("is_locked_flag", "first"),
                    source_system=("source_system", "first"),
                    is_system_generated=("is_system_generated", "first"),
                    is_defect_flag=("is_defect_flag", "max"),
                    defect_type=("defect_type", "first"),
                    created_at=("created_at", "first"),
                    updated_at=("updated_at", "first"),
                )
            )
            grouped["budget_line_pk"] = grouped.apply(
                lambda row: self._generate_pk(
                    "|".join(str(row[col]) for col in grain)
                ),
                axis=1,
            )
            lines_df = grouped[self.LINE_COLUMNS]
        else:
            lines_df = lines_df[self.LINE_COLUMNS]

        lines_df = lines_df.sort_values(
            ["budget_version_code", "posting_period", "department_id", "account_code", "currency", "planning_driver"]
        ).reset_index(drop=True)
        return lines_df

    # ------------------------------------------------------------------
    # Validation / logging
    # ------------------------------------------------------------------

    def _validate_outputs(
        self,
        versions_df: pd.DataFrame,
        lines_df: pd.DataFrame,
        coa_df: pd.DataFrame,
        departments_df: pd.DataFrame,
    ) -> None:
        if versions_df.empty:
            raise ValueError("budget_versions.csv output is empty.")
        if lines_df.empty:
            raise ValueError("budget_lines.csv output is empty.")

        if versions_df["budget_version_pk"].duplicated().any():
            raise ValueError("Duplicate budget_version_pk values generated.")
        if versions_df["budget_version_code"].duplicated().any():
            raise ValueError("Duplicate budget_version_code values generated.")

        if lines_df["budget_line_pk"].duplicated().any():
            raise ValueError("Duplicate budget_line_pk values generated.")
        if lines_df["budget_line_id"].duplicated().any():
            raise ValueError("Duplicate budget_line_id values generated.")

        grain = ["budget_version_code", "posting_period", "department_id", "account_code", "currency", "planning_driver"]
        duplicate_grain_count = int(lines_df.duplicated(subset=grain).sum())
        if duplicate_grain_count:
            raise ValueError(f"Duplicate budget line grain rows generated: {duplicate_grain_count:,}")

        active_accounts = set(coa_df["account_code"].astype(str))
        missing_accounts = set(lines_df["account_code"].astype(str)).difference(active_accounts)
        if missing_accounts:
            raise ValueError(f"Budget lines contain account codes outside active CoA: {sorted(missing_accounts)}")

        active_departments = set(departments_df["department_id"].astype(str))
        missing_departments = set(lines_df["department_id"].astype(str)).difference(active_departments)
        if missing_departments:
            raise ValueError(f"Budget lines contain departments outside department catalogue/workforce scope: {sorted(missing_departments)}")

        for column in ["budget_amount_local", "budget_amount_gbp"]:
            if (pd.to_numeric(lines_df[column], errors="coerce") < -self.rules.rounding_tolerance).any():
                raise ValueError(f"Budget lines contain negative {column} values.")

        revenue = lines_df[lines_df["account_class"] == "Revenue"].copy()
        revenue_by_version = revenue.groupby("budget_version_code")["budget_amount_gbp"].sum().round(2)

        expected_targets = {
            "AOP_FY2025_ORIGINAL": self.rules.fy2025_revenue_target_gbp,
            "AOP_FY2026_BOARD_APPROVED": self.rules.fy2026_revenue_target_gbp,
        }
        for version_code, expected in expected_targets.items():
            actual = float(revenue_by_version.get(version_code, 0.00))
            if abs(actual - expected) > self.rules.rounding_tolerance:
                raise ValueError(
                    f"Revenue budget target mismatch for {version_code}: actual {actual:,.2f}, expected {expected:,.2f}"
                )

        payroll = lines_df[lines_df["account_code"] == self.rules.payroll_account]
        if payroll.empty:
            raise ValueError("Budget output contains no payroll expense lines.")

        logger.info("Budget output validation passed.")

    def _log_review(self, versions_df: pd.DataFrame, lines_df: pd.DataFrame) -> None:
        logger.info("----- Budget / Annual Operating Plan Review -----")
        logger.info("Budget versions: %s", f"{len(versions_df):,}")
        logger.info("Budget lines: %s", f"{len(lines_df):,}")
        logger.info(
            "Posting period range: %s to %s",
            lines_df["posting_period"].min(),
            lines_df["posting_period"].max(),
        )
        logger.info(
            "Budget lines by version:\n%s",
            lines_df["budget_version_code"].value_counts().to_string(),
        )
        logger.info(
            "Budget amount GBP by account class:\n%s",
            lines_df.groupby("account_class")["budget_amount_gbp"].sum().round(2).to_string(),
        )
        logger.info(
            "FY revenue budget totals GBP:\n%s",
            lines_df[lines_df["account_class"] == "Revenue"]
            .groupby("budget_version_code")["budget_amount_gbp"]
            .sum()
            .round(2)
            .to_string(),
        )
        logger.info(
            "Top planning drivers by GBP amount:\n%s",
            lines_df.groupby("planning_driver")["budget_amount_gbp"]
            .sum()
            .sort_values(ascending=False)
            .head(12)
            .round(2)
            .to_string(),
        )
        logger.info("------------------------------------------------")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        logger.info("Generating Phase 3L.1 Budget / Annual Operating Plan source extracts.")
        coa_df, payroll_df, headcount_plan_df, departments_df, fx_df = self._load_dependencies()

        versions_df = self._build_budget_versions()
        lines_df = self._build_budget_lines(
            versions_df=versions_df,
            payroll_df=payroll_df,
            headcount_plan_df=headcount_plan_df,
            departments_df=departments_df,
            coa_df=coa_df,
        )

        self._validate_outputs(versions_df, lines_df, coa_df, departments_df)
        self._log_review(versions_df, lines_df)

        return versions_df, lines_df

    def save(self, versions_df: pd.DataFrame, lines_df: pd.DataFrame) -> None:
        output_dir = get_raw_data_path("planning")
        output_dir.mkdir(parents=True, exist_ok=True)

        versions_path = output_dir / self.versions_filename
        lines_path = output_dir / self.lines_filename

        versions_df.to_csv(versions_path, index=False)
        lines_df.to_csv(lines_path, index=False)

        logger.info("Budget versions saved to %s", versions_path)
        logger.info("Budget lines saved to %s", lines_path)


if __name__ == "__main__":
    generator = BudgetGenerator()
    budget_versions, budget_lines = generator.generate()
    generator.save(budget_versions, budget_lines)
