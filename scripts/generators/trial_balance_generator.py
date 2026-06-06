"""
trial_balance_generator.py

Project Atlas / Nexus Technologies
Phase 3J.1 - Trial Balance Extract Generation

Purpose
-------
Generates:
- data/raw/accounting/trial_balance.csv

This table represents an ERP-style monthly Trial Balance export built from the
balanced general ledger journal lines. It is intentionally generated as a raw
source-system artefact so DuckDB/dbt can later ingest, test, govern and model it
into reporting marts.

Grain
-----
One row per:
    posting_period + account_code + currency

Accounting convention
---------------------
Balances are stored using universal algebraic signs:
- debits increase balances
- credits reduce balances

Therefore the same roll-forward formula applies to every account class:
    closing_balance = opening_balance + period_debits - period_credits

This means Asset and Expense accounts naturally present as positive when
debit-heavy, while Liability, Equity and Revenue accounts naturally present as
negative when credit-heavy.

Primary control
---------------
For every posting_period:
    sum(closing_balance_gbp) = 0.00

This is the Trial Balance invariant used to validate ledger integrity.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("TrialBalanceGenerator", "generation_execution.log")


@dataclass(frozen=True)
class TrialBalanceRules:
    created_at: str = "2026-06-03"
    updated_at: str = "2026-06-03"
    balance_tolerance: float = 0.01


class TrialBalanceGenerator:
    """
    Generate an ERP-style monthly Trial Balance extract.

    Inputs
    ------
    data/raw/accounting/chart_of_accounts.csv
    data/raw/accounting/erp_gl_journal_lines.csv

    Output
    ------
    data/raw/accounting/trial_balance.csv
    """

    output_filename = "trial_balance.csv"

    REQUIRED_COA_COLUMNS = {
        "account_code",
        "account_name",
        "account_class",
        "financial_statement",
        "active_flag",
    }

    REQUIRED_GL_COLUMNS = {
        "journal_line_pk",
        "journal_id",
        "journal_date",
        "posting_period",
        "account_code",
        "currency",
        "debit_local",
        "credit_local",
        "debit_gbp",
        "credit_gbp",
        "is_defect_flag",
        "defect_type",
    }

    VALID_ACCOUNT_CLASSES = {
        "Asset",
        "Liability",
        "Equity",
        "Revenue",
        "Expense",
    }

    OUTPUT_COLUMNS = [
        "trial_balance_pk",
        "posting_period",
        "period_start_date",
        "period_end_date",
        "account_code",
        "account_name",
        "account_class",
        "financial_statement",
        "currency",
        "opening_balance_local",
        "period_debits_local",
        "period_credits_local",
        "closing_balance_local",
        "opening_balance_gbp",
        "period_debits_gbp",
        "period_credits_gbp",
        "closing_balance_gbp",
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
        self.rules = TrialBalanceRules()

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

        if value_str in {"1", "true", "yes", "y"}:
            return 1

        if value_str in {"0", "false", "no", "n"}:
            return 0

        return default

    @staticmethod
    def _normalise_account_code(value: object) -> str:
        if pd.isna(value):
            return ""

        value_str = str(value).strip()

        if value_str.endswith(".0") and value_str.replace(".0", "").isdigit():
            return value_str.replace(".0", "")

        return value_str

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

    def _load_csv(self, path: Path, dataset_name: str) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(
                f"{dataset_name} not found at {path}. Run upstream generators first."
            )

        return pd.read_csv(path)

    # ------------------------------------------------------------------
    # Loading and preparation
    # ------------------------------------------------------------------

    def _load_dependencies(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        accounting_dir = get_raw_data_path("accounting")

        coa_df = self._load_csv(
            accounting_dir / "chart_of_accounts.csv",
            "chart_of_accounts.csv",
        )

        gl_df = self._load_csv(
            accounting_dir / "erp_gl_journal_lines.csv",
            "erp_gl_journal_lines.csv",
        )

        coa_df = self._prepare_chart_of_accounts(coa_df)
        gl_df = self._prepare_gl_journal_lines(gl_df, coa_df)

        logger.info(
            "Loaded Trial Balance dependencies: %s accounts, %s GL journal lines.",
            f"{len(coa_df):,}",
            f"{len(gl_df):,}",
        )

        return coa_df, gl_df

    def _prepare_chart_of_accounts(self, coa_df: pd.DataFrame) -> pd.DataFrame:
        df = coa_df.copy()

        self._require_columns(df, self.REQUIRED_COA_COLUMNS, "chart_of_accounts.csv")

        df["account_code"] = df["account_code"].apply(self._normalise_account_code)
        df["account_name"] = df["account_name"].fillna("").astype(str)
        df["account_class"] = df["account_class"].fillna("").astype(str)
        df["financial_statement"] = df["financial_statement"].fillna("").astype(str)
        df["active_flag"] = df["active_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=1)
        )

        if df.empty:
            raise ValueError("chart_of_accounts.csv is empty.")

        if df["account_code"].eq("").any():
            raise ValueError("chart_of_accounts.csv contains blank account_code values.")

        if df["account_code"].duplicated().any():
            duplicate_count = int(df["account_code"].duplicated().sum())
            raise ValueError(
                f"Duplicate account_code values in chart_of_accounts.csv: {duplicate_count:,}"
            )

        invalid_classes = set(df["account_class"].unique()).difference(
            self.VALID_ACCOUNT_CLASSES
        )
        if invalid_classes:
            raise ValueError(
                "chart_of_accounts.csv contains invalid account_class values: "
                f"{sorted(invalid_classes)}"
            )

        active_df = df[df["active_flag"] == 1].copy()
        if active_df.empty:
            raise ValueError("chart_of_accounts.csv contains no active accounts.")

        return active_df

    def _prepare_gl_journal_lines(
        self,
        gl_df: pd.DataFrame,
        coa_df: pd.DataFrame,
    ) -> pd.DataFrame:
        df = gl_df.copy()

        self._require_columns(df, self.REQUIRED_GL_COLUMNS, "erp_gl_journal_lines.csv")

        if df.empty:
            raise ValueError("erp_gl_journal_lines.csv is empty.")

        df["journal_line_pk"] = df["journal_line_pk"].astype(str)
        df["journal_id"] = df["journal_id"].astype(str)
        df["journal_date"] = pd.to_datetime(df["journal_date"], errors="coerce")
        df["posting_period"] = df["posting_period"].fillna("").astype(str)
        df["account_code"] = df["account_code"].apply(self._normalise_account_code)
        df["currency"] = df["currency"].fillna("").astype(str).str.upper()
        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        if df["journal_date"].isna().any():
            bad_count = int(df["journal_date"].isna().sum())
            raise ValueError(
                f"erp_gl_journal_lines.csv contains invalid journal_date values: {bad_count:,}"
            )

        if df["posting_period"].eq("").any():
            bad_count = int(df["posting_period"].eq("").sum())
            raise ValueError(
                f"erp_gl_journal_lines.csv contains blank posting_period values: {bad_count:,}"
            )

        if df["account_code"].eq("").any():
            bad_count = int(df["account_code"].eq("").sum())
            raise ValueError(
                f"erp_gl_journal_lines.csv contains blank account_code values: {bad_count:,}"
            )

        if df["currency"].eq("").any():
            bad_count = int(df["currency"].eq("").sum())
            raise ValueError(
                f"erp_gl_journal_lines.csv contains blank currency values: {bad_count:,}"
            )

        for column in ["debit_local", "credit_local", "debit_gbp", "credit_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00)

            negative_count = int((df[column] < 0).sum())
            if negative_count > 0:
                raise ValueError(
                    f"erp_gl_journal_lines.csv contains negative {column} values: "
                    f"{negative_count:,}"
                )

        valid_accounts = set(coa_df["account_code"].astype(str))
        missing_accounts = set(df["account_code"].astype(str)).difference(valid_accounts)
        if missing_accounts:
            raise ValueError(
                "erp_gl_journal_lines.csv contains account codes not present in "
                f"active chart_of_accounts.csv: {sorted(missing_accounts)}"
            )

        self._validate_journal_balance(df)

        return df

    # ------------------------------------------------------------------
    # Trial Balance generation
    # ------------------------------------------------------------------

    def _validate_journal_balance(self, gl_df: pd.DataFrame) -> None:
        journal_balance = (
            gl_df.groupby("journal_id", as_index=False)
            .agg(
                debit_local=("debit_local", "sum"),
                credit_local=("credit_local", "sum"),
                debit_gbp=("debit_gbp", "sum"),
                credit_gbp=("credit_gbp", "sum"),
            )
        )

        journal_balance["local_variance"] = (
            journal_balance["debit_local"] - journal_balance["credit_local"]
        ).round(2)
        journal_balance["gbp_variance"] = (
            journal_balance["debit_gbp"] - journal_balance["credit_gbp"]
        ).round(2)

        unbalanced = journal_balance[
            (journal_balance["local_variance"].abs() > self.rules.balance_tolerance)
            | (journal_balance["gbp_variance"].abs() > self.rules.balance_tolerance)
        ]

        if not unbalanced.empty:
            raise ValueError(
                "Unbalanced source journals detected before Trial Balance generation: "
                f"{len(unbalanced):,} journal_id values."
            )

    def _build_period_activity(self, gl_df: pd.DataFrame) -> pd.DataFrame:
        amount_activity = (
            gl_df.groupby(
                ["posting_period", "account_code", "currency"],
                as_index=False,
            )
            .agg(
                period_debits_local=("debit_local", "sum"),
                period_credits_local=("credit_local", "sum"),
                period_debits_gbp=("debit_gbp", "sum"),
                period_credits_gbp=("credit_gbp", "sum"),
            )
        )

        defect_activity = (
            gl_df.assign(
                clean_defect_type=lambda d: d["defect_type"].where(
                    d["defect_type"].str.strip().ne(""),
                    None,
                )
            )
            .groupby(["posting_period", "account_code", "currency"], as_index=False)
            .agg(
                is_defect_flag=("is_defect_flag", "max"),
                defect_type=(
                    "clean_defect_type",
                    lambda values: " | ".join(
                        sorted({str(value) for value in values if pd.notna(value)})
                    ),
                ),
            )
        )

        activity = amount_activity.merge(
            defect_activity,
            on=["posting_period", "account_code", "currency"],
            how="left",
        )

        activity["is_defect_flag"] = activity["is_defect_flag"].fillna(0).astype(int)
        activity["defect_type"] = activity["defect_type"].fillna("").astype(str)

        for column in [
            "period_debits_local",
            "period_credits_local",
            "period_debits_gbp",
            "period_credits_gbp",
        ]:
            activity[column] = activity[column].apply(self._round_money)

        return activity

    @staticmethod
    def _build_period_dimension(posting_periods: list[str]) -> pd.DataFrame:
        parsed_periods = pd.to_datetime(
            [f"{period}-01" for period in posting_periods],
            errors="coerce",
        )

        if pd.isna(parsed_periods).any():
            raise ValueError("Unable to parse one or more posting_period values.")

        continuous_periods = pd.date_range(
            start=parsed_periods.min(),
            end=parsed_periods.max(),
            freq="MS",
        )

        period_df = pd.DataFrame({"period_start_date": continuous_periods})
        period_df["posting_period"] = period_df["period_start_date"].dt.strftime("%Y-%m")
        period_df["period_end_date"] = period_df["period_start_date"] + pd.offsets.MonthEnd(0)

        period_df["period_start_date"] = period_df["period_start_date"].dt.date.astype(str)
        period_df["period_end_date"] = period_df["period_end_date"].dt.date.astype(str)

        return period_df[["posting_period", "period_start_date", "period_end_date"]]

    def _build_complete_scaffold(
        self,
        coa_df: pd.DataFrame,
        gl_df: pd.DataFrame,
    ) -> pd.DataFrame:
        period_df = self._build_period_dimension(
            sorted(gl_df["posting_period"].dropna().astype(str).unique())
        )
        account_df = coa_df[
            ["account_code", "account_name", "account_class", "financial_statement"]
        ].copy()
        currency_df = pd.DataFrame(
            {"currency": sorted(gl_df["currency"].dropna().astype(str).unique())}
        )

        scaffold = period_df.merge(account_df, how="cross").merge(currency_df, how="cross")

        return scaffold

    def _calculate_trial_balance(
        self,
        scaffold_df: pd.DataFrame,
        activity_df: pd.DataFrame,
    ) -> pd.DataFrame:
        df = scaffold_df.merge(
            activity_df,
            on=["posting_period", "account_code", "currency"],
            how="left",
        )

        for column in [
            "period_debits_local",
            "period_credits_local",
            "period_debits_gbp",
            "period_credits_gbp",
        ]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00)

        df["is_defect_flag"] = df["is_defect_flag"].fillna(0).astype(int)
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        df = df.sort_values(
            ["account_code", "currency", "posting_period"],
            kind="mergesort",
        ).reset_index(drop=True)

        df["period_movement_local"] = (
            df["period_debits_local"] - df["period_credits_local"]
        ).round(2)
        df["period_movement_gbp"] = (
            df["period_debits_gbp"] - df["period_credits_gbp"]
        ).round(2)

        df["closing_balance_local"] = (
            df.groupby(["account_code", "currency"])["period_movement_local"]
            .cumsum()
            .round(2)
        )
        df["closing_balance_gbp"] = (
            df.groupby(["account_code", "currency"])["period_movement_gbp"]
            .cumsum()
            .round(2)
        )

        df["opening_balance_local"] = (
            df["closing_balance_local"] - df["period_movement_local"]
        ).round(2)
        df["opening_balance_gbp"] = (
            df["closing_balance_gbp"] - df["period_movement_gbp"]
        ).round(2)

        for column in [
            "opening_balance_local",
            "period_debits_local",
            "period_credits_local",
            "closing_balance_local",
            "opening_balance_gbp",
            "period_debits_gbp",
            "period_credits_gbp",
            "closing_balance_gbp",
        ]:
            df[column] = df[column].apply(self._round_money)

        df["source_system"] = "atlas_erp_trial_balance"
        df["is_system_generated"] = 1
        df["created_at"] = self.rules.created_at
        df["updated_at"] = self.rules.updated_at

        df["trial_balance_pk"] = df.apply(
            lambda row: self._generate_pk(
                f"{row['posting_period']}|{row['account_code']}|{row['currency']}"
            ),
            axis=1,
        )

        return df[self.OUTPUT_COLUMNS].copy()

    # ------------------------------------------------------------------
    # Validation and review
    # ------------------------------------------------------------------

    def _validate_output(self, tb_df: pd.DataFrame, coa_df: pd.DataFrame) -> None:
        self._require_columns(tb_df, set(self.OUTPUT_COLUMNS), "trial_balance.csv")

        grain_columns = ["posting_period", "account_code", "currency"]
        duplicate_count = int(tb_df.duplicated(grain_columns).sum())
        if duplicate_count > 0:
            raise ValueError(
                "trial_balance.csv contains duplicate grain rows: "
                f"{duplicate_count:,} duplicates across {grain_columns}."
            )

        if tb_df["trial_balance_pk"].duplicated().any():
            duplicate_count = int(tb_df["trial_balance_pk"].duplicated().sum())
            raise ValueError(
                f"Duplicate trial_balance_pk values detected: {duplicate_count:,}"
            )

        valid_accounts = set(coa_df["account_code"].astype(str))
        missing_accounts = set(tb_df["account_code"].astype(str)).difference(valid_accounts)
        if missing_accounts:
            raise ValueError(
                "trial_balance.csv contains account codes missing from chart_of_accounts.csv: "
                f"{sorted(missing_accounts)}"
            )

        rollforward_variance = (
            tb_df["opening_balance_gbp"]
            + tb_df["period_debits_gbp"]
            - tb_df["period_credits_gbp"]
            - tb_df["closing_balance_gbp"]
        ).round(2)
        bad_rollforward_count = int(
            (rollforward_variance.abs() > self.rules.balance_tolerance).sum()
        )
        if bad_rollforward_count > 0:
            raise ValueError(
                "Trial Balance GBP roll-forward formula failed for "
                f"{bad_rollforward_count:,} rows."
            )

        local_rollforward_variance = (
            tb_df["opening_balance_local"]
            + tb_df["period_debits_local"]
            - tb_df["period_credits_local"]
            - tb_df["closing_balance_local"]
        ).round(2)
        bad_local_rollforward_count = int(
            (local_rollforward_variance.abs() > self.rules.balance_tolerance).sum()
        )
        if bad_local_rollforward_count > 0:
            raise ValueError(
                "Trial Balance local roll-forward formula failed for "
                f"{bad_local_rollforward_count:,} rows."
            )

        period_gbp_balance = (
            tb_df.groupby("posting_period", as_index=False)["closing_balance_gbp"]
            .sum()
            .assign(closing_balance_gbp=lambda d: d["closing_balance_gbp"].round(2))
        )
        bad_periods = period_gbp_balance[
            period_gbp_balance["closing_balance_gbp"].abs() > self.rules.balance_tolerance
        ]
        if not bad_periods.empty:
            raise ValueError(
                "Trial Balance GBP invariant failed. Periods with non-zero closing balance: "
                f"{bad_periods.to_dict(orient='records')[:10]}"
            )

        period_currency_balance = (
            tb_df.groupby(["posting_period", "currency"], as_index=False)[
                "closing_balance_local"
            ]
            .sum()
            .assign(closing_balance_local=lambda d: d["closing_balance_local"].round(2))
        )
        bad_period_currencies = period_currency_balance[
            period_currency_balance["closing_balance_local"].abs()
            > self.rules.balance_tolerance
        ]
        if not bad_period_currencies.empty:
            raise ValueError(
                "Trial Balance local-currency invariant failed. Period/currency values "
                f"with non-zero closing balance: {bad_period_currencies.to_dict(orient='records')[:10]}"
            )

    def _log_review_summary(self, tb_df: pd.DataFrame) -> None:
        final_period = str(tb_df["posting_period"].max())
        final_period_df = tb_df[tb_df["posting_period"] == final_period].copy()

        period_balance = (
            tb_df.groupby("posting_period")["closing_balance_gbp"].sum().round(2)
        )
        largest_abs_period_imbalance = period_balance.abs().max()

        logger.info("----- Trial Balance Review -----")
        logger.info("Trial Balance rows: %s", f"{len(tb_df):,}")
        logger.info(
            "Posting period range: %s to %s",
            tb_df["posting_period"].min(),
            tb_df["posting_period"].max(),
        )
        logger.info("Account count: %s", f"{tb_df['account_code'].nunique():,}")
        logger.info("Currency count: %s", f"{tb_df['currency'].nunique():,}")
        logger.info(
            "Largest absolute period imbalance GBP: %.2f",
            float(largest_abs_period_imbalance),
        )
        logger.info(
            "Rows carrying defect lineage: %s",
            f"{int(tb_df['is_defect_flag'].sum()):,}",
        )
        logger.info(
            "Rows by account class in final period:\n%s",
            final_period_df.groupby("account_class")["closing_balance_gbp"]
            .sum()
            .round(2)
            .to_string(),
        )
        logger.info(
            "Top 10 final-period closing balances by absolute GBP value:\n%s",
            final_period_df.assign(
                abs_closing=lambda d: d["closing_balance_gbp"].abs()
            )
            .sort_values("abs_closing", ascending=False)
            .head(10)[
                [
                    "account_code",
                    "account_name",
                    "currency",
                    "closing_balance_gbp",
                ]
            ]
            .to_string(index=False),
        )
        logger.info("--------------------------------")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> pd.DataFrame:
        logger.info("Generating Phase 3J.1 Trial Balance extract.")

        coa_df, gl_df = self._load_dependencies()
        activity_df = self._build_period_activity(gl_df)
        scaffold_df = self._build_complete_scaffold(coa_df, gl_df)
        tb_df = self._calculate_trial_balance(scaffold_df, activity_df)

        self._validate_output(tb_df, coa_df)
        self._log_review_summary(tb_df)

        return tb_df

    def save(self, trial_balance_df: pd.DataFrame) -> None:
        accounting_dir = get_raw_data_path("accounting")
        accounting_dir.mkdir(parents=True, exist_ok=True)

        output_path = accounting_dir / self.output_filename
        trial_balance_df.to_csv(output_path, index=False)

        logger.info("Trial Balance extract written to %s", output_path)


if __name__ == "__main__":
    generator = TrialBalanceGenerator()
    trial_balance = generator.generate()
    generator.save(trial_balance)
