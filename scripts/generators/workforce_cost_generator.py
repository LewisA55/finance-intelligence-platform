"""
workforce_cost_generator.py

Project Atlas / Nexus Technologies
Phase 3K.1 - Workforce Cost & Payroll Expense Source Generation

Purpose
-------
Generates:
- data/raw/workforce/employee_compensation.csv
- data/raw/workforce/payroll_expense_lines.csv
- data/raw/workforce/headcount_plan.csv

This phase bridges HRIS headcount data into finance-ready workforce cost source
extracts without mutating the locked ERP GL / Trial Balance spine.

Design
------
hr_employees.csv
    = employee master / HRIS worker dimension

hr_headcount_snapshot.csv
    = monthly active headcount snapshot

employee_compensation.csv
    = line-level monthly compensation subledger

payroll_expense_lines.csv
    = department/account/currency payroll expense aggregation extract

headcount_plan.csv
    = active roles plus approved open requisitions for budget and forecast phases

Grain
-----
employee_compensation.csv:
    employee_id + posting_period + compensation_component

payroll_expense_lines.csv:
    posting_period + department_id + account_code + currency + cost_component

headcount_plan.csv:
    position_id

Important
---------
This phase does not post payroll into erp_gl_journal_lines.csv. It creates the
workforce subledger and finance extract required for later budget, forecast and
optional payroll-to-GL integration phases.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("WorkforceCostGenerator", "generation_execution.log")


@dataclass(frozen=True)
class WorkforceCostRules:
    """Rules for workforce cost generation."""

    created_at: str = "2026-06-03"
    updated_at: str = "2026-06-03"
    payroll_account_code: str = "6100"
    accrual_account_code: str = "2400"
    rounding_tolerance: float = 0.05
    open_requisition_rate: float = 0.08
    min_open_requisitions: int = 35
    max_open_requisitions: int = 90


class WorkforceCostGenerator:
    """
    Generate workforce compensation, payroll expense and headcount plan extracts.

    Inputs
    ------
    data/raw/hris/hr_employees.csv
    data/raw/hris/hr_headcount_snapshot.csv
    data/raw/accounting/chart_of_accounts.csv
    data/raw/fx/exchange_rates_2022_2026.csv

    Outputs
    -------
    data/raw/workforce/employee_compensation.csv
    data/raw/workforce/payroll_expense_lines.csv
    data/raw/workforce/headcount_plan.csv
    """

    employee_compensation_filename = "employee_compensation.csv"
    payroll_expense_lines_filename = "payroll_expense_lines.csv"
    headcount_plan_filename = "headcount_plan.csv"

    COMPENSATION_COLUMNS = [
        "compensation_pk",
        "compensation_line_id",
        "employee_id",
        "posting_period",
        "period_start_date",
        "period_end_date",
        "department_id",
        "region_id",
        "country_code",
        "currency",
        "compensation_component",
        "annual_base_salary_local",
        "monthly_base_salary_local",
        "component_rate",
        "amount_local",
        "amount_gbp",
        "fx_rate_to_gbp",
        "source_system",
        "is_system_generated",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    PAYROLL_COLUMNS = [
        "payroll_expense_pk",
        "payroll_expense_line_id",
        "posting_period",
        "period_start_date",
        "period_end_date",
        "department_id",
        "account_code",
        "account_name",
        "currency",
        "cost_component",
        "employee_count",
        "debit_local",
        "credit_local",
        "debit_gbp",
        "credit_gbp",
        "source_system",
        "is_system_generated",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    HEADCOUNT_PLAN_COLUMNS = [
        "position_pk",
        "position_id",
        "employee_id",
        "plan_status",
        "department_id",
        "region_id",
        "country_code",
        "currency",
        "role_family",
        "seniority_level",
        "planned_hire_date",
        "planned_start_period",
        "target_salary_low_local",
        "target_salary_mid_local",
        "target_salary_high_local",
        "target_salary_mid_gbp",
        "fx_rate_to_gbp",
        "backfill_flag",
        "source_system",
        "is_system_generated",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    COMPONENT_RATES = {
        "BASE_SALARY": 1.00,
        "EMPLOYER_TAX": None,
        "BENEFITS": None,
        "BONUS_ACCRUAL": None,
    }

    EMPLOYER_TAX_RATE_BY_COUNTRY = {
        "GB": 0.138,
        "UK": 0.138,
        "US": 0.0765,
        "DE": 0.195,
        "SG": 0.17,
    }

    BENEFIT_RATE_BY_COUNTRY = {
        "GB": 0.08,
        "UK": 0.08,
        "US": 0.12,
        "DE": 0.10,
        "SG": 0.07,
    }

    BONUS_RATE_BY_SENIORITY = {
        "Executive": 0.20,
        "Director": 0.15,
        "Manager": 0.10,
        "Senior": 0.07,
        "Mid": 0.05,
        "Junior": 0.03,
        "Unknown": 0.04,
    }

    BASE_SALARY_GBP_BY_ROLE = {
        "Executive": 150_000.00,
        "Director": 115_000.00,
        "Manager": 82_000.00,
        "Senior": 62_000.00,
        "Mid": 45_000.00,
        "Junior": 32_000.00,
        "Unknown": 48_000.00,
    }

    LOCAL_SALARY_MULTIPLIER_BY_CURRENCY = {
        "GBP": 1.00,
        "USD": 1.38,
        "EUR": 1.18,
        "SGD": 1.72,
    }

    CURRENCY_BY_COUNTRY = {
        "GB": "GBP",
        "UK": "GBP",
        "US": "USD",
        "DE": "EUR",
        "SG": "SGD",
    }

    COUNTRY_BY_REGION = {
        "UKI": "GB",
        "UK": "GB",
        "GB": "GB",
        "United Kingdom": "GB",
        "North America": "US",
        "NA": "US",
        "US": "US",
        "United States": "US",
        "DACH": "DE",
        "Germany": "DE",
        "DE": "DE",
        "APAC": "SG",
        "Singapore": "SG",
        "SG": "SG",
    }

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.rules = WorkforceCostRules()
        self._comp_line_counter = 0
        self._payroll_line_counter = 0

    # ------------------------------------------------------------------
    # Generic helpers
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
    def _normalise_bool_int(value: object, default: int = 0) -> int:
        if pd.isna(value):
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value == 1)
        value_str = str(value).strip().lower()
        if value_str in {"1", "true", "yes", "y", "active"}:
            return 1
        if value_str in {"0", "false", "no", "n", "inactive", "terminated"}:
            return 0
        return default

    @staticmethod
    def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
        for column in candidates:
            if column in df.columns:
                return column
        return None

    @staticmethod
    def _require_columns(
        df: pd.DataFrame,
        required_columns: set[str],
        dataset_name: str,
    ) -> None:
        missing_columns = required_columns.difference(df.columns)
        if missing_columns:
            raise ValueError(
                f"{dataset_name} is missing required columns: {sorted(missing_columns)}"
            )

    def _stable_ratio(self, value: str) -> float:
        hash_value = self._generate_pk(f"{self.seed}|{value}")
        return (int(hash_value[:10], 16) % 10_000) / 10_000

    def _next_compensation_line_id(self) -> str:
        self._comp_line_counter += 1
        return f"COMP-LN-{self._comp_line_counter:010d}"

    def _next_payroll_line_id(self) -> str:
        self._payroll_line_counter += 1
        return f"PAY-LN-{self._payroll_line_counter:010d}"

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_csv(self, path: Path, dataset_name: str) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(
                f"{dataset_name} not found at {path}. Run upstream generators first."
            )
        return pd.read_csv(path)

    def _load_dependencies(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        hris_dir = get_raw_data_path("hris")
        accounting_dir = get_raw_data_path("accounting")
        fx_dir = get_raw_data_path("fx")

        employees_df = self._load_csv(hris_dir / "hr_employees.csv", "hr_employees.csv")
        headcount_df = self._load_csv(
            hris_dir / "hr_headcount_snapshot.csv",
            "hr_headcount_snapshot.csv",
        )
        coa_df = self._load_csv(
            accounting_dir / "chart_of_accounts.csv",
            "chart_of_accounts.csv",
        )
        fx_df = self._load_csv(
            fx_dir / "exchange_rates_2022_2026.csv",
            "exchange_rates_2022_2026.csv",
        )

        employees_df = self._prepare_employees(employees_df)
        headcount_df = self._prepare_headcount_snapshot(headcount_df)
        coa_df = self._prepare_chart_of_accounts(coa_df)
        fx_df = self._prepare_fx_rates(fx_df)

        logger.info(
            "Loaded workforce dependencies: %s employees, %s headcount snapshot rows, %s CoA rows, %s FX rows.",
            f"{len(employees_df):,}",
            f"{len(headcount_df):,}",
            f"{len(coa_df):,}",
            f"{len(fx_df):,}",
        )

        return employees_df, headcount_df, coa_df, fx_df

    # ------------------------------------------------------------------
    # Preparation
    # ------------------------------------------------------------------

    def _prepare_employees(self, employees_df: pd.DataFrame) -> pd.DataFrame:
        df = employees_df.copy()
        if df.empty:
            raise ValueError("hr_employees.csv is empty.")

        employee_id_col = self._first_existing_column(
            df,
            ["employee_id", "worker_id", "employee_number"],
        )
        department_col = self._first_existing_column(
            df,
            ["department_id", "cost_center_id", "department_code", "cost_centre_id"],
        )

        if employee_id_col is None:
            raise ValueError("hr_employees.csv must contain employee_id, worker_id or employee_number.")
        if department_col is None:
            raise ValueError("hr_employees.csv must contain department_id or cost_center_id.")

        df = df.rename(
            columns={
                employee_id_col: "employee_id",
                department_col: "department_id",
            }
        )

        for optional_col in [
            "region_id",
            "country_code",
            "currency",
            "job_title",
            "role_family",
            "seniority_level",
            "hire_date",
            "termination_date",
            "employment_status",
            "active_flag",
            "annual_salary_local",
            "base_salary_local",
        ]:
            if optional_col not in df.columns:
                df[optional_col] = None

        df["employee_id"] = df["employee_id"].astype(str)
        df["department_id"] = df["department_id"].fillna("UNKNOWN").astype(str)
        df["region_id"] = df["region_id"].fillna("UKI").astype(str)
        df["country_code"] = df.apply(self._derive_country_code, axis=1)
        df["currency"] = df.apply(self._derive_currency, axis=1)
        df["role_family"] = df.apply(self._derive_role_family, axis=1)
        df["seniority_level"] = df.apply(self._derive_seniority_level, axis=1)

        for date_col in ["hire_date", "termination_date"]:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        if "active_flag" in df.columns:
            df["active_flag"] = df["active_flag"].apply(
                lambda x: self._normalise_bool_int(x, default=1)
            )
        else:
            df["active_flag"] = 1

        df["annual_salary_local"] = df.apply(self._derive_annual_salary_local, axis=1)
        df["source_system"] = "hris_workday_simulated"
        df["is_defect_flag"] = 0
        df["defect_type"] = ""

        if df["employee_id"].duplicated().any():
            duplicate_count = int(df["employee_id"].duplicated().sum())
            raise ValueError(f"Duplicate employee_id values in hr_employees.csv: {duplicate_count:,}")

        return df

    def _prepare_headcount_snapshot(self, headcount_df: pd.DataFrame) -> pd.DataFrame:
        df = headcount_df.copy()
        if df.empty:
            raise ValueError("hr_headcount_snapshot.csv is empty.")

        employee_id_col = self._first_existing_column(
            df,
            ["employee_id", "worker_id", "employee_number"],
        )
        period_col = self._first_existing_column(
            df,
            [
                "posting_period",
                "snapshot_period",
                "period_month",
                "snapshot_month",
                "month_start_date",
                "snapshot_date",
                "reporting_month",
            ],
        )
        department_col = self._first_existing_column(
            df,
            ["department_id", "cost_center_id", "department_code", "cost_centre_id"],
        )

        if employee_id_col is None:
            raise ValueError("hr_headcount_snapshot.csv must contain employee_id, worker_id or employee_number.")
        if period_col is None:
            raise ValueError(
                "hr_headcount_snapshot.csv must contain a monthly period column such as posting_period, snapshot_month or month_start_date."
            )

        rename_map = {employee_id_col: "employee_id", period_col: "posting_period_raw"}
        if department_col is not None:
            rename_map[department_col] = "department_id"
        df = df.rename(columns=rename_map)

        if "department_id" not in df.columns:
            df["department_id"] = None

        active_col = self._first_existing_column(
            df,
            ["active_flag", "is_active", "headcount_flag", "is_headcount", "employed_flag"],
        )
        if active_col is None:
            df["active_headcount_flag"] = 1
        else:
            df["active_headcount_flag"] = df[active_col].apply(
                lambda x: self._normalise_bool_int(x, default=1)
            )

        df["employee_id"] = df["employee_id"].astype(str)
        df["posting_period_date"] = pd.to_datetime(df["posting_period_raw"], errors="coerce")

        if df["posting_period_date"].isna().any():
            # Handle YYYY-MM strings explicitly.
            df.loc[df["posting_period_date"].isna(), "posting_period_date"] = pd.to_datetime(
                df.loc[df["posting_period_date"].isna(), "posting_period_raw"].astype(str) + "-01",
                errors="coerce",
            )

        if df["posting_period_date"].isna().any():
            bad_count = int(df["posting_period_date"].isna().sum())
            raise ValueError(
                f"hr_headcount_snapshot.csv contains {bad_count:,} invalid posting period values."
            )

        df["period_start_date"] = df["posting_period_date"].dt.to_period("M").dt.to_timestamp()
        df["period_end_date"] = df["period_start_date"] + pd.offsets.MonthEnd(0)
        df["posting_period"] = df["period_start_date"].dt.strftime("%Y-%m")
        df["department_id"] = df["department_id"].fillna("UNKNOWN").astype(str)

        df = df[df["active_headcount_flag"] == 1].copy()

        if df.empty:
            raise ValueError("hr_headcount_snapshot.csv contains no active headcount rows.")

        duplicate_grain = df.duplicated(subset=["employee_id", "posting_period"])
        if duplicate_grain.any():
            duplicate_count = int(duplicate_grain.sum())
            raise ValueError(
                f"Duplicate employee_id + posting_period rows in hr_headcount_snapshot.csv: {duplicate_count:,}"
            )

        return df[
            [
                "employee_id",
                "posting_period",
                "period_start_date",
                "period_end_date",
                "department_id",
                "active_headcount_flag",
            ]
        ].copy()

    def _prepare_chart_of_accounts(self, coa_df: pd.DataFrame) -> pd.DataFrame:
        df = coa_df.copy()
        self._require_columns(
            df,
            {"account_code", "account_name", "account_class", "active_flag"},
            "chart_of_accounts.csv",
        )
        df["account_code"] = df["account_code"].astype(str).str.replace(".0", "", regex=False)
        df["active_flag"] = df["active_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=1)
        )
        df = df[df["active_flag"] == 1].copy()
        if self.rules.payroll_account_code not in set(df["account_code"]):
            raise ValueError(
                f"chart_of_accounts.csv missing payroll account {self.rules.payroll_account_code}."
            )
        if self.rules.accrual_account_code not in set(df["account_code"]):
            raise ValueError(
                f"chart_of_accounts.csv missing accrual account {self.rules.accrual_account_code}."
            )
        return df

    def _prepare_fx_rates(self, fx_df: pd.DataFrame) -> pd.DataFrame:
        df = fx_df.copy()
        self._require_columns(
            df,
            {"currency_code", "month_start_date", "monthly_average_rate_to_gbp"},
            "exchange_rates_2022_2026.csv",
        )
        df["currency_code"] = df["currency_code"].astype(str).str.upper()
        df["period_start_date"] = pd.to_datetime(df["month_start_date"], errors="coerce")
        df["posting_period"] = df["period_start_date"].dt.strftime("%Y-%m")
        df["monthly_average_rate_to_gbp"] = pd.to_numeric(
            df["monthly_average_rate_to_gbp"], errors="coerce"
        )
        if df["period_start_date"].isna().any() or df["monthly_average_rate_to_gbp"].isna().any():
            raise ValueError("exchange_rates_2022_2026.csv contains invalid period or FX values.")
        return df[["currency_code", "posting_period", "monthly_average_rate_to_gbp"]].copy()

    # ------------------------------------------------------------------
    # Derivation helpers
    # ------------------------------------------------------------------

    def _derive_country_code(self, row: pd.Series) -> str:
        explicit_country = str(row.get("country_code", "") or "").strip()
        if explicit_country and explicit_country.lower() not in {"nan", "none"}:
            return explicit_country.upper()
        region = str(row.get("region_id", "UKI") or "UKI").strip()
        return self.COUNTRY_BY_REGION.get(region, "GB")

    def _derive_currency(self, row: pd.Series) -> str:
        explicit_currency = str(row.get("currency", "") or "").strip().upper()
        if explicit_currency and explicit_currency.lower() not in {"nan", "none"}:
            return explicit_currency
        country = str(row.get("country_code", "GB") or "GB").upper()
        return self.CURRENCY_BY_COUNTRY.get(country, "GBP")

    def _derive_role_family(self, row: pd.Series) -> str:
        explicit_role = str(row.get("role_family", "") or "").strip()
        if explicit_role and explicit_role.lower() not in {"nan", "none"}:
            return explicit_role
        job_title = str(row.get("job_title", "") or "").lower()
        if any(term in job_title for term in ["sales", "account executive", "customer success"]):
            return "Commercial"
        if any(term in job_title for term in ["engineer", "developer", "data", "product"]):
            return "Product & Engineering"
        if any(term in job_title for term in ["finance", "accounting", "controller"]):
            return "Finance"
        if any(term in job_title for term in ["people", "hr", "talent"]):
            return "People"
        return "Operations"

    def _derive_seniority_level(self, row: pd.Series) -> str:
        explicit_level = str(row.get("seniority_level", "") or "").strip()
        if explicit_level and explicit_level.lower() not in {"nan", "none"}:
            return explicit_level
        job_title = str(row.get("job_title", "") or "").lower()
        if any(term in job_title for term in ["chief", "cfo", "cto", "ceo", "vp", "vice president"]):
            return "Executive"
        if "director" in job_title or "head of" in job_title:
            return "Director"
        if "manager" in job_title or "lead" in job_title:
            return "Manager"
        if "senior" in job_title or "sr" in job_title:
            return "Senior"
        if "junior" in job_title or "associate" in job_title or "graduate" in job_title:
            return "Junior"
        ratio = self._stable_ratio(str(row.get("employee_id", "")))
        if ratio < 0.10:
            return "Director"
        if ratio < 0.28:
            return "Manager"
        if ratio < 0.58:
            return "Senior"
        if ratio < 0.88:
            return "Mid"
        return "Junior"

    def _derive_annual_salary_local(self, row: pd.Series) -> float:
        for salary_col in ["annual_salary_local", "base_salary_local"]:
            value = row.get(salary_col)
            parsed = pd.to_numeric(value, errors="coerce")
            if not pd.isna(parsed) and float(parsed) > 0:
                return self._round_money(parsed)

        seniority = str(row.get("seniority_level", "Unknown"))
        currency = str(row.get("currency", "GBP")).upper()
        base_gbp = self.BASE_SALARY_GBP_BY_ROLE.get(seniority, self.BASE_SALARY_GBP_BY_ROLE["Unknown"])
        multiplier = self.LOCAL_SALARY_MULTIPLIER_BY_CURRENCY.get(currency, 1.00)
        jitter = 0.85 + (self._stable_ratio(str(row.get("employee_id", ""))) * 0.35)
        return self._round_money(base_gbp * multiplier * jitter)

    def _get_component_rate(self, component: str, country_code: str, seniority_level: str) -> float:
        country_code = str(country_code).upper()
        seniority_level = str(seniority_level)
        if component == "BASE_SALARY":
            return 1.00
        if component == "EMPLOYER_TAX":
            return self.EMPLOYER_TAX_RATE_BY_COUNTRY.get(country_code, 0.10)
        if component == "BENEFITS":
            return self.BENEFIT_RATE_BY_COUNTRY.get(country_code, 0.08)
        if component == "BONUS_ACCRUAL":
            return self.BONUS_RATE_BY_SENIORITY.get(seniority_level, self.BONUS_RATE_BY_SENIORITY["Unknown"])
        return 0.00

    # ------------------------------------------------------------------
    # Build outputs
    # ------------------------------------------------------------------

    def _build_employee_compensation(
        self,
        employees_df: pd.DataFrame,
        headcount_df: pd.DataFrame,
        fx_df: pd.DataFrame,
    ) -> pd.DataFrame:
        df = headcount_df.merge(
            employees_df,
            on="employee_id",
            how="left",
            suffixes=("_snapshot", "_employee"),
        )

        if df["currency"].isna().any():
            missing_count = int(df["currency"].isna().sum())
            raise ValueError(
                f"Headcount snapshot contains {missing_count:,} employee rows not found in hr_employees.csv."
            )

        # Prefer snapshot department where it exists, because this allows department drift over time.
        df["department_id"] = df["department_id_snapshot"].where(
            df["department_id_snapshot"].notna() & (df["department_id_snapshot"].astype(str) != "UNKNOWN"),
            df["department_id_employee"],
        )
        df["department_id"] = df["department_id"].fillna("UNKNOWN").astype(str)

        df = df.merge(
            fx_df,
            left_on=["currency", "posting_period"],
            right_on=["currency_code", "posting_period"],
            how="left",
        )

        if df["monthly_average_rate_to_gbp"].isna().any():
            missing = df.loc[df["monthly_average_rate_to_gbp"].isna(), ["currency", "posting_period"]].drop_duplicates()
            raise ValueError(
                "Missing FX rates for workforce compensation currencies/periods: "
                f"{missing.to_dict(orient='records')[:10]}"
            )

        records: list[dict] = []
        components = ["BASE_SALARY", "EMPLOYER_TAX", "BENEFITS", "BONUS_ACCRUAL"]

        for _, row in df.iterrows():
            annual_base_salary = self._round_money(row["annual_salary_local"])
            monthly_base_salary = self._round_money(annual_base_salary / 12)
            fx_rate = float(row["monthly_average_rate_to_gbp"])

            for component in components:
                component_rate = self._get_component_rate(
                    component=component,
                    country_code=str(row["country_code"]),
                    seniority_level=str(row["seniority_level"]),
                )

                if component == "BASE_SALARY":
                    amount_local = monthly_base_salary
                else:
                    amount_local = self._round_money(monthly_base_salary * component_rate)

                amount_gbp = self._round_money(amount_local * fx_rate)
                line_id = self._next_compensation_line_id()

                records.append(
                    {
                        "compensation_pk": self._generate_pk(line_id),
                        "compensation_line_id": line_id,
                        "employee_id": str(row["employee_id"]),
                        "posting_period": str(row["posting_period"]),
                        "period_start_date": pd.Timestamp(row["period_start_date"]).date().isoformat(),
                        "period_end_date": pd.Timestamp(row["period_end_date"]).date().isoformat(),
                        "department_id": str(row["department_id"]),
                        "region_id": str(row["region_id"]),
                        "country_code": str(row["country_code"]),
                        "currency": str(row["currency"]),
                        "compensation_component": component,
                        "annual_base_salary_local": annual_base_salary,
                        "monthly_base_salary_local": monthly_base_salary,
                        "component_rate": round(float(component_rate), 4),
                        "amount_local": amount_local,
                        "amount_gbp": amount_gbp,
                        "fx_rate_to_gbp": round(fx_rate, 6),
                        "source_system": "hris_compensation_engine",
                        "is_system_generated": 1,
                        "is_defect_flag": int(row.get("is_defect_flag", 0) or 0),
                        "defect_type": str(row.get("defect_type", "") or ""),
                        "created_at": self.rules.created_at,
                        "updated_at": self.rules.updated_at,
                    }
                )

        compensation_df = pd.DataFrame(records, columns=self.COMPENSATION_COLUMNS)

        logger.info(
            "Employee compensation rows generated: %s",
            f"{len(compensation_df):,}",
        )

        return compensation_df

    def _build_payroll_expense_lines(
        self,
        compensation_df: pd.DataFrame,
        coa_df: pd.DataFrame,
    ) -> pd.DataFrame:
        account_lookup = coa_df.set_index("account_code")["account_name"].to_dict()
        payroll_account_name = account_lookup[self.rules.payroll_account_code]

        grouped = (
            compensation_df.groupby(
                [
                    "posting_period",
                    "period_start_date",
                    "period_end_date",
                    "department_id",
                    "currency",
                    "compensation_component",
                ],
                dropna=False,
            )
            .agg(
                employee_count=("employee_id", "nunique"),
                debit_local=("amount_local", "sum"),
                debit_gbp=("amount_gbp", "sum"),
                is_defect_flag=("is_defect_flag", "max"),
                defect_type=("defect_type", lambda s: " | ".join(sorted({str(x) for x in s if str(x).strip()}))),
            )
            .reset_index()
        )

        records: list[dict] = []
        for _, row in grouped.iterrows():
            line_id = self._next_payroll_line_id()
            debit_local = self._round_money(row["debit_local"])
            debit_gbp = self._round_money(row["debit_gbp"])
            records.append(
                {
                    "payroll_expense_pk": self._generate_pk(line_id),
                    "payroll_expense_line_id": line_id,
                    "posting_period": str(row["posting_period"]),
                    "period_start_date": str(row["period_start_date"]),
                    "period_end_date": str(row["period_end_date"]),
                    "department_id": str(row["department_id"]),
                    "account_code": self.rules.payroll_account_code,
                    "account_name": payroll_account_name,
                    "currency": str(row["currency"]),
                    "cost_component": str(row["compensation_component"]),
                    "employee_count": int(row["employee_count"]),
                    "debit_local": debit_local,
                    "credit_local": 0.00,
                    "debit_gbp": debit_gbp,
                    "credit_gbp": 0.00,
                    "source_system": "workforce_cost_engine",
                    "is_system_generated": 1,
                    "is_defect_flag": int(row["is_defect_flag"]),
                    "defect_type": str(row["defect_type"]),
                    "created_at": self.rules.created_at,
                    "updated_at": self.rules.updated_at,
                }
            )

        payroll_df = pd.DataFrame(records, columns=self.PAYROLL_COLUMNS)

        logger.info(
            "Payroll expense lines generated: %s",
            f"{len(payroll_df):,}",
        )

        return payroll_df

    def _build_headcount_plan(
        self,
        employees_df: pd.DataFrame,
        headcount_df: pd.DataFrame,
        fx_df: pd.DataFrame,
    ) -> pd.DataFrame:
        latest_period = sorted(headcount_df["posting_period"].unique())[-1]
        latest_headcount = headcount_df[headcount_df["posting_period"] == latest_period].copy()

        active_roles = latest_headcount.merge(employees_df, on="employee_id", how="left", suffixes=("_snapshot", "_employee"))
        active_records: list[dict] = []

        latest_fx = fx_df[fx_df["posting_period"] == latest_period].copy()
        fx_lookup = latest_fx.set_index("currency_code")["monthly_average_rate_to_gbp"].to_dict()

        for _, row in active_roles.iterrows():
            currency = str(row.get("currency", "GBP"))
            fx_rate = float(fx_lookup.get(currency, 1.00))
            salary_mid = self._round_money(row.get("annual_salary_local", 0.00))
            position_id = f"POS-ACTIVE-{row['employee_id']}"
            active_records.append(
                {
                    "position_pk": self._generate_pk(position_id),
                    "position_id": position_id,
                    "employee_id": str(row["employee_id"]),
                    "plan_status": "ACTIVE",
                    "department_id": str(row.get("department_id_snapshot", row.get("department_id_employee", "UNKNOWN"))),
                    "region_id": str(row.get("region_id", "UKI")),
                    "country_code": str(row.get("country_code", "GB")),
                    "currency": currency,
                    "role_family": str(row.get("role_family", "Operations")),
                    "seniority_level": str(row.get("seniority_level", "Unknown")),
                    "planned_hire_date": "",
                    "planned_start_period": latest_period,
                    "target_salary_low_local": self._round_money(salary_mid * 0.90),
                    "target_salary_mid_local": salary_mid,
                    "target_salary_high_local": self._round_money(salary_mid * 1.10),
                    "target_salary_mid_gbp": self._round_money(salary_mid * fx_rate),
                    "fx_rate_to_gbp": round(fx_rate, 6),
                    "backfill_flag": 0,
                    "source_system": "headcount_plan_engine",
                    "is_system_generated": 1,
                    "is_defect_flag": 0,
                    "defect_type": "",
                    "created_at": self.rules.created_at,
                    "updated_at": self.rules.updated_at,
                }
            )

        active_count = len(active_records)
        open_req_count = max(
            self.rules.min_open_requisitions,
            min(self.rules.max_open_requisitions, round(active_count * self.rules.open_requisition_rate)),
        )

        base_roles = active_roles.sample(
            n=min(open_req_count, len(active_roles)),
            random_state=self.seed,
            replace=False,
        ).reset_index(drop=True)

        open_records: list[dict] = []
        latest_start = pd.to_datetime(f"{latest_period}-01")
        for index, (_, row) in enumerate(base_roles.iterrows(), start=1):
            currency = str(row.get("currency", "GBP"))
            fx_rate = float(fx_lookup.get(currency, 1.00))
            backfill_flag = int(self._stable_ratio(f"backfill|{index}") < 0.30)
            uplift = 0.95 + self._stable_ratio(f"req-salary|{index}") * 0.25
            salary_mid = self._round_money(float(row.get("annual_salary_local", 48_000.00)) * uplift)
            hire_month_offset = 1 + int(self._stable_ratio(f"hire-month|{index}") * 12)
            hire_date = latest_start + pd.DateOffset(months=hire_month_offset)
            hire_date = hire_date.replace(day=1)
            position_id = f"POS-OPEN-{index:04d}"
            plan_status = "BACKFILL" if backfill_flag else "OPEN_BUDGETED"

            open_records.append(
                {
                    "position_pk": self._generate_pk(position_id),
                    "position_id": position_id,
                    "employee_id": "",
                    "plan_status": plan_status,
                    "department_id": str(row.get("department_id_snapshot", row.get("department_id_employee", "UNKNOWN"))),
                    "region_id": str(row.get("region_id", "UKI")),
                    "country_code": str(row.get("country_code", "GB")),
                    "currency": currency,
                    "role_family": str(row.get("role_family", "Operations")),
                    "seniority_level": str(row.get("seniority_level", "Unknown")),
                    "planned_hire_date": hire_date.date().isoformat(),
                    "planned_start_period": hire_date.strftime("%Y-%m"),
                    "target_salary_low_local": self._round_money(salary_mid * 0.90),
                    "target_salary_mid_local": salary_mid,
                    "target_salary_high_local": self._round_money(salary_mid * 1.10),
                    "target_salary_mid_gbp": self._round_money(salary_mid * fx_rate),
                    "fx_rate_to_gbp": round(fx_rate, 6),
                    "backfill_flag": backfill_flag,
                    "source_system": "headcount_plan_engine",
                    "is_system_generated": 1,
                    "is_defect_flag": 0,
                    "defect_type": "",
                    "created_at": self.rules.created_at,
                    "updated_at": self.rules.updated_at,
                }
            )

        headcount_plan_df = pd.DataFrame(active_records + open_records, columns=self.HEADCOUNT_PLAN_COLUMNS)

        logger.info(
            "Headcount plan rows generated: %s active positions and %s open requisitions.",
            f"{len(active_records):,}",
            f"{len(open_records):,}",
        )

        return headcount_plan_df

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_outputs(
        self,
        compensation_df: pd.DataFrame,
        payroll_df: pd.DataFrame,
        headcount_plan_df: pd.DataFrame,
    ) -> None:
        if compensation_df.empty:
            raise ValueError("employee_compensation.csv output is empty.")
        if payroll_df.empty:
            raise ValueError("payroll_expense_lines.csv output is empty.")
        if headcount_plan_df.empty:
            raise ValueError("headcount_plan.csv output is empty.")

        comp_grain_dupes = compensation_df.duplicated(
            subset=["employee_id", "posting_period", "compensation_component"]
        )
        if comp_grain_dupes.any():
            duplicate_count = int(comp_grain_dupes.sum())
            raise ValueError(
                f"Duplicate employee compensation grain rows found: {duplicate_count:,}"
            )

        payroll_grain_dupes = payroll_df.duplicated(
            subset=["posting_period", "department_id", "account_code", "currency", "cost_component"]
        )
        if payroll_grain_dupes.any():
            duplicate_count = int(payroll_grain_dupes.sum())
            raise ValueError(
                f"Duplicate payroll expense line grain rows found: {duplicate_count:,}"
            )

        if headcount_plan_df["position_id"].duplicated().any():
            duplicate_count = int(headcount_plan_df["position_id"].duplicated().sum())
            raise ValueError(f"Duplicate position_id values in headcount_plan.csv: {duplicate_count:,}")

        comp_totals = compensation_df.groupby(["posting_period", "currency"], dropna=False).agg(
            amount_local=("amount_local", "sum"),
            amount_gbp=("amount_gbp", "sum"),
        ).reset_index()
        payroll_totals = payroll_df.groupby(["posting_period", "currency"], dropna=False).agg(
            debit_local=("debit_local", "sum"),
            debit_gbp=("debit_gbp", "sum"),
        ).reset_index()
        tieout = comp_totals.merge(payroll_totals, on=["posting_period", "currency"], how="outer").fillna(0.00)
        tieout["local_variance"] = (tieout["amount_local"] - tieout["debit_local"]).round(2)
        tieout["gbp_variance"] = (tieout["amount_gbp"] - tieout["debit_gbp"]).round(2)

        if (tieout["local_variance"].abs() > self.rules.rounding_tolerance).any():
            raise ValueError("Payroll local totals do not tie to employee compensation totals.")
        if (tieout["gbp_variance"].abs() > self.rules.rounding_tolerance).any():
            raise ValueError("Payroll GBP totals do not tie to employee compensation totals.")

        if (compensation_df["amount_local"] < 0).any() or (compensation_df["amount_gbp"] < 0).any():
            raise ValueError("Compensation output contains negative amounts.")

        valid_components = {"BASE_SALARY", "EMPLOYER_TAX", "BENEFITS", "BONUS_ACCRUAL"}
        invalid_components = set(compensation_df["compensation_component"].unique()).difference(valid_components)
        if invalid_components:
            raise ValueError(f"Invalid compensation components found: {sorted(invalid_components)}")

        logger.info("Workforce cost validation passed.")

    def _log_review(
        self,
        compensation_df: pd.DataFrame,
        payroll_df: pd.DataFrame,
        headcount_plan_df: pd.DataFrame,
    ) -> None:
        logger.info("----- Workforce Cost Review -----")
        logger.info("Employee compensation rows: %s", f"{len(compensation_df):,}")
        logger.info("Payroll expense rows: %s", f"{len(payroll_df):,}")
        logger.info("Headcount plan rows: %s", f"{len(headcount_plan_df):,}")
        logger.info(
            "Posting period range: %s to %s",
            compensation_df["posting_period"].min(),
            compensation_df["posting_period"].max(),
        )
        logger.info(
            "Compensation by component:\n%s",
            compensation_df.groupby("compensation_component")["amount_gbp"].sum().round(2).sort_values(ascending=False).to_string(),
        )
        logger.info(
            "Payroll by currency:\n%s",
            payroll_df.groupby("currency")["debit_gbp"].sum().round(2).sort_values(ascending=False).to_string(),
        )
        logger.info(
            "Headcount plan status counts:\n%s",
            headcount_plan_df["plan_status"].value_counts(dropna=False).to_string(),
        )
        logger.info("---------------------------------")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        logger.info("Generating Phase 3K.1 Workforce Cost source extracts.")

        employees_df, headcount_df, coa_df, fx_df = self._load_dependencies()
        compensation_df = self._build_employee_compensation(
            employees_df=employees_df,
            headcount_df=headcount_df,
            fx_df=fx_df,
        )
        payroll_df = self._build_payroll_expense_lines(
            compensation_df=compensation_df,
            coa_df=coa_df,
        )
        headcount_plan_df = self._build_headcount_plan(
            employees_df=employees_df,
            headcount_df=headcount_df,
            fx_df=fx_df,
        )

        self._validate_outputs(compensation_df, payroll_df, headcount_plan_df)
        self._log_review(compensation_df, payroll_df, headcount_plan_df)

        return compensation_df, payroll_df, headcount_plan_df

    def save(
        self,
        compensation_df: pd.DataFrame,
        payroll_df: pd.DataFrame,
        headcount_plan_df: pd.DataFrame,
    ) -> None:
        output_dir = get_raw_data_path("workforce")
        output_dir.mkdir(parents=True, exist_ok=True)

        compensation_path = output_dir / self.employee_compensation_filename
        payroll_path = output_dir / self.payroll_expense_lines_filename
        headcount_plan_path = output_dir / self.headcount_plan_filename

        compensation_df.to_csv(compensation_path, index=False)
        payroll_df.to_csv(payroll_path, index=False)
        headcount_plan_df.to_csv(headcount_plan_path, index=False)

        logger.info("Employee compensation saved to %s", compensation_path)
        logger.info("Payroll expense lines saved to %s", payroll_path)
        logger.info("Headcount plan saved to %s", headcount_plan_path)


if __name__ == "__main__":
    generator = WorkforceCostGenerator()
    compensation, payroll, headcount_plan = generator.generate()
    generator.save(
        compensation_df=compensation,
        payroll_df=payroll,
        headcount_plan_df=headcount_plan,
    )
