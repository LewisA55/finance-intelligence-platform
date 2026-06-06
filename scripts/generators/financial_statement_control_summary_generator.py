"""
financial_statement_control_summary_generator.py

Project Atlas / Nexus Technologies
Phase 3J.3 - Financial Statement Control Summary

Purpose
-------
Generates:
- data/raw/accounting/financial_statement_controls.csv

This dataset converts key ledger, financial statement and subledger reconciliation
checks into a formal raw control artifact. It is designed to support CFO review,
analytics engineering validation, and audit-style control testing.

Design
------
The control summary reads from locked accounting extracts and subledgers:
- trial_balance.csv
- financial_statement_extract.csv
- erp_gl_journal_lines.csv
- vendor_invoices.csv
- vendor_payments.csv
- billing_invoices.csv
- billing_payment_allocations.csv
- deferred_revenue_rollforward.csv

Control approach
----------------
1. Macro accounting controls are evaluated across all posting periods.
2. Subledger tie-outs are evaluated at the latest actual reporting period only.
3. Expected values are normally zero variance.
4. Controlled defects and upstream model mismatches are surfaced as FAIL rows;
   the generator does not hide or force-pass failed controls.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("FinancialStatementControlSummaryGenerator", "generation_execution.log")


@dataclass(frozen=True)
class FinancialStatementControlRules:
    """Rules for financial statement control summary generation."""

    created_at: str = "2026-06-03"
    updated_at: str = "2026-06-03"
    current_reporting_period: str = "2026-06"
    materiality_threshold: float = 0.01


class FinancialStatementControlSummaryGenerator:
    """
    Generate formal control summary rows across Trial Balance, Financial Statement
    and selected subledger reconciliation checks.

    Inputs
    ------
    data/raw/accounting/trial_balance.csv
    data/raw/accounting/financial_statement_extract.csv
    data/raw/accounting/erp_gl_journal_lines.csv
    data/raw/procurement/vendor_invoices.csv
    data/raw/procurement/vendor_payments.csv
    data/raw/billing/billing_invoices.csv
    data/raw/billing/billing_payment_allocations.csv
    data/raw/revenue/deferred_revenue_rollforward.csv

    Output
    ------
    data/raw/accounting/financial_statement_controls.csv
    """

    output_filename = "financial_statement_controls.csv"

    ACCOUNT_AR = "1100"
    ACCOUNT_DEFERRED_REVENUE = "2100"
    ACCOUNT_AP = "2300"

    OUTPUT_COLUMNS = [
        "control_pk",
        "posting_period",
        "currency",
        "control_check",
        "control_category",
        "expected_value_local",
        "actual_value_local",
        "variance_value_local",
        "absolute_variance_local",
        "expected_value_gbp",
        "actual_value_gbp",
        "variance_value_gbp",
        "absolute_variance_gbp",
        "materiality_threshold",
        "control_status",
        "severity",
        "source_dataset",
        "description",
        "is_system_generated",
        "created_at",
        "updated_at",
    ]

    REQUIRED_TB_COLUMNS = {
        "posting_period",
        "period_start_date",
        "period_end_date",
        "account_code",
        "account_name",
        "account_class",
        "currency",
        "closing_balance_local",
        "closing_balance_gbp",
        "period_debits_local",
        "period_credits_local",
        "period_debits_gbp",
        "period_credits_gbp",
    }

    REQUIRED_FS_COLUMNS = {
        "posting_period",
        "statement_type",
        "statement_section",
        "statement_line",
        "account_code",
        "account_class",
        "currency",
        "amount_local",
        "amount_gbp",
        "is_calculated_line",
        "calculation_type",
    }

    def __init__(self) -> None:
        self.rules = FinancialStatementControlRules()

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
    def _normalise_account_code(value: object) -> str:
        if pd.isna(value):
            return ""
        value_str = str(value).strip()
        if value_str.endswith(".0") and value_str.replace(".0", "").isdigit():
            return value_str.replace(".0", "")
        return value_str

    @staticmethod
    def _require_columns(df: pd.DataFrame, required_columns: set[str], dataset_name: str) -> None:
        missing_columns = required_columns.difference(df.columns)
        if missing_columns:
            raise ValueError(
                f"{dataset_name} is missing required columns: {sorted(missing_columns)}"
            )

    @staticmethod
    def _read_csv(path: Path, dataset_name: str, usecols: list[str] | None = None) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(
                f"{dataset_name} not found at {path}. Run upstream generators first."
            )
        return pd.read_csv(path, usecols=usecols)

    def _status_from_variance(self, absolute_variance_gbp: float) -> tuple[str, str]:
        if round(abs(float(absolute_variance_gbp)), 2) <= self.rules.materiality_threshold:
            return "PASS", "INFO"
        return "FAIL", "HIGH"

    def _make_control_row(
        self,
        *,
        posting_period: str,
        currency: str,
        control_check: str,
        control_category: str,
        actual_value_local: float,
        actual_value_gbp: float,
        source_dataset: str,
        description: str,
        expected_value_local: float = 0.00,
        expected_value_gbp: float = 0.00,
    ) -> dict:
        actual_value_local = self._round_money(actual_value_local)
        actual_value_gbp = self._round_money(actual_value_gbp)
        expected_value_local = self._round_money(expected_value_local)
        expected_value_gbp = self._round_money(expected_value_gbp)

        variance_value_local = self._round_money(actual_value_local - expected_value_local)
        variance_value_gbp = self._round_money(actual_value_gbp - expected_value_gbp)
        absolute_variance_local = self._round_money(abs(variance_value_local))
        absolute_variance_gbp = self._round_money(abs(variance_value_gbp))
        control_status, severity = self._status_from_variance(absolute_variance_gbp)

        control_key = "|".join(
            [
                str(posting_period),
                str(currency),
                str(control_check),
                str(source_dataset),
            ]
        )

        return {
            "control_pk": self._generate_pk(control_key),
            "posting_period": str(posting_period),
            "currency": str(currency),
            "control_check": str(control_check),
            "control_category": str(control_category),
            "expected_value_local": expected_value_local,
            "actual_value_local": actual_value_local,
            "variance_value_local": variance_value_local,
            "absolute_variance_local": absolute_variance_local,
            "expected_value_gbp": expected_value_gbp,
            "actual_value_gbp": actual_value_gbp,
            "variance_value_gbp": variance_value_gbp,
            "absolute_variance_gbp": absolute_variance_gbp,
            "materiality_threshold": self.rules.materiality_threshold,
            "control_status": control_status,
            "severity": severity,
            "source_dataset": str(source_dataset),
            "description": str(description),
            "is_system_generated": 1,
            "created_at": self.rules.created_at,
            "updated_at": self.rules.updated_at,
        }

    # ------------------------------------------------------------------
    # Loading and preparation
    # ------------------------------------------------------------------

    def _load_dependencies(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        accounting_dir = get_raw_data_path("accounting")
        procurement_dir = get_raw_data_path("procurement")
        billing_dir = get_raw_data_path("billing")
        revenue_dir = get_raw_data_path("revenue")

        trial_balance_df = self._read_csv(
            accounting_dir / "trial_balance.csv",
            "trial_balance.csv",
        )

        financial_statement_df = self._read_csv(
            accounting_dir / "financial_statement_extract.csv",
            "financial_statement_extract.csv",
        )

        # Loaded as a health dependency so controls can confirm the upstream GL exists.
        erp_gl_df = self._read_csv(
            accounting_dir / "erp_gl_journal_lines.csv",
            "erp_gl_journal_lines.csv",
            usecols=[
                "journal_id",
                "debit_local",
                "credit_local",
                "debit_gbp",
                "credit_gbp",
                "currency",
            ],
        )

        vendor_invoices_df = self._read_csv(
            procurement_dir / "vendor_invoices.csv",
            "vendor_invoices.csv",
            usecols=["currency", "total_local", "total_gbp"],
        )

        vendor_payments_df = self._read_csv(
            procurement_dir / "vendor_payments.csv",
            "vendor_payments.csv",
            usecols=["currency", "payment_amount_local", "payment_amount_gbp"],
        )

        billing_invoices_df = self._read_csv(
            billing_dir / "billing_invoices.csv",
            "billing_invoices.csv",
            usecols=["currency", "total_local", "total_gbp"],
        )

        payment_allocations_df = self._read_csv(
            billing_dir / "billing_payment_allocations.csv",
            "billing_payment_allocations.csv",
            usecols=["currency", "allocated_amount_local", "allocated_amount_gbp"],
        )

        deferred_revenue_rollforward_df = self._read_csv(
            revenue_dir / "deferred_revenue_rollforward.csv",
            "deferred_revenue_rollforward.csv",
            usecols=[
                "period_month",
                "currency",
                "closing_deferred_revenue_local",
                "closing_deferred_revenue_gbp",
            ],
        )

        trial_balance_df = self._prepare_trial_balance(trial_balance_df)
        financial_statement_df = self._prepare_financial_statement(financial_statement_df)
        erp_gl_df = self._prepare_erp_gl(erp_gl_df)
        vendor_invoices_df = self._prepare_vendor_invoices(vendor_invoices_df)
        vendor_payments_df = self._prepare_vendor_payments(vendor_payments_df)
        billing_invoices_df = self._prepare_billing_invoices(billing_invoices_df)
        payment_allocations_df = self._prepare_payment_allocations(payment_allocations_df)
        deferred_revenue_rollforward_df = self._prepare_deferred_revenue_rollforward(
            deferred_revenue_rollforward_df
        )

        logger.info(
            "Loaded financial statement control dependencies: %s TB rows, %s FS rows, "
            "%s GL rows, %s vendor invoices, %s vendor payments, %s billing invoices, "
            "%s AR allocations, %s deferred roll-forward rows.",
            f"{len(trial_balance_df):,}",
            f"{len(financial_statement_df):,}",
            f"{len(erp_gl_df):,}",
            f"{len(vendor_invoices_df):,}",
            f"{len(vendor_payments_df):,}",
            f"{len(billing_invoices_df):,}",
            f"{len(payment_allocations_df):,}",
            f"{len(deferred_revenue_rollforward_df):,}",
        )

        return (
            trial_balance_df,
            financial_statement_df,
            erp_gl_df,
            vendor_invoices_df,
            vendor_payments_df,
            billing_invoices_df,
            payment_allocations_df,
            deferred_revenue_rollforward_df,
        )

    def _prepare_trial_balance(self, df: pd.DataFrame) -> pd.DataFrame:
        self._require_columns(df, self.REQUIRED_TB_COLUMNS, "trial_balance.csv")
        df = df.copy()
        df["posting_period"] = df["posting_period"].astype(str)
        df["account_code"] = df["account_code"].apply(self._normalise_account_code)
        df["currency"] = df["currency"].astype(str).str.upper()
        for column in [
            "closing_balance_local",
            "closing_balance_gbp",
            "period_debits_local",
            "period_credits_local",
            "period_debits_gbp",
            "period_credits_gbp",
        ]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00)

        grain = ["posting_period", "account_code", "currency"]
        if df.duplicated(grain).any():
            duplicate_count = int(df.duplicated(grain).sum())
            raise ValueError(f"trial_balance.csv has duplicate grain rows: {duplicate_count:,}")
        return df

    def _prepare_financial_statement(self, df: pd.DataFrame) -> pd.DataFrame:
        self._require_columns(df, self.REQUIRED_FS_COLUMNS, "financial_statement_extract.csv")
        df = df.copy()
        df["posting_period"] = df["posting_period"].astype(str)
        df["account_code"] = df["account_code"].fillna("").apply(self._normalise_account_code)
        df["currency"] = df["currency"].astype(str).str.upper()
        df["is_calculated_line"] = pd.to_numeric(
            df["is_calculated_line"], errors="coerce"
        ).fillna(0).astype(int)
        df["calculation_type"] = df["calculation_type"].fillna("").astype(str)
        for column in ["amount_local", "amount_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00)
        return df

    def _prepare_erp_gl(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for column in ["debit_local", "credit_local", "debit_gbp", "credit_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00)
        df["currency"] = df["currency"].astype(str).str.upper()
        return df

    def _prepare_vendor_invoices(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["currency"] = df["currency"].astype(str).str.upper()
        df["total_local"] = pd.to_numeric(df["total_local"], errors="coerce").fillna(0.00)
        df["total_gbp"] = pd.to_numeric(df["total_gbp"], errors="coerce").fillna(0.00)
        return df

    def _prepare_vendor_payments(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["currency"] = df["currency"].astype(str).str.upper()
        df["payment_amount_local"] = pd.to_numeric(
            df["payment_amount_local"], errors="coerce"
        ).fillna(0.00)
        df["payment_amount_gbp"] = pd.to_numeric(
            df["payment_amount_gbp"], errors="coerce"
        ).fillna(0.00)
        return df

    def _prepare_billing_invoices(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["currency"] = df["currency"].astype(str).str.upper()
        df["total_local"] = pd.to_numeric(df["total_local"], errors="coerce").fillna(0.00)
        df["total_gbp"] = pd.to_numeric(df["total_gbp"], errors="coerce").fillna(0.00)
        return df

    def _prepare_payment_allocations(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["currency"] = df["currency"].astype(str).str.upper()
        df["allocated_amount_local"] = pd.to_numeric(
            df["allocated_amount_local"], errors="coerce"
        ).fillna(0.00)
        df["allocated_amount_gbp"] = pd.to_numeric(
            df["allocated_amount_gbp"], errors="coerce"
        ).fillna(0.00)
        return df

    def _prepare_deferred_revenue_rollforward(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["posting_period"] = pd.to_datetime(df["period_month"], errors="coerce").dt.strftime("%Y-%m")
        if df["posting_period"].isna().any():
            bad_count = int(df["posting_period"].isna().sum())
            raise ValueError(
                f"deferred_revenue_rollforward.csv contains invalid period_month values: {bad_count:,}"
            )
        df["currency"] = df["currency"].astype(str).str.upper()
        df["closing_deferred_revenue_local"] = pd.to_numeric(
            df["closing_deferred_revenue_local"], errors="coerce"
        ).fillna(0.00)
        df["closing_deferred_revenue_gbp"] = pd.to_numeric(
            df["closing_deferred_revenue_gbp"], errors="coerce"
        ).fillna(0.00)
        return df

    # ------------------------------------------------------------------
    # Control builders
    # ------------------------------------------------------------------

    def _build_gl_balance_control(self, erp_gl_df: pd.DataFrame) -> list[dict]:
        by_journal = erp_gl_df.groupby("journal_id", as_index=False).agg(
            debit_local=("debit_local", "sum"),
            credit_local=("credit_local", "sum"),
            debit_gbp=("debit_gbp", "sum"),
            credit_gbp=("credit_gbp", "sum"),
        )
        by_journal["variance_local"] = (by_journal["debit_local"] - by_journal["credit_local"]).round(2)
        by_journal["variance_gbp"] = (by_journal["debit_gbp"] - by_journal["credit_gbp"]).round(2)

        max_local = float(by_journal["variance_local"].abs().max() or 0.00)
        max_gbp = float(by_journal["variance_gbp"].abs().max() or 0.00)

        return [
            self._make_control_row(
                posting_period="ALL",
                currency="ALL",
                control_check="GL_JOURNAL_BALANCE_CHECK",
                control_category="Ledger Integrity",
                expected_value_local=0.00,
                actual_value_local=max_local,
                expected_value_gbp=0.00,
                actual_value_gbp=max_gbp,
                source_dataset="erp_gl_journal_lines.csv",
                description="Maximum absolute journal-level imbalance across ERP GL journal lines.",
            )
        ]

    def _build_trial_balance_controls(self, trial_balance_df: pd.DataFrame) -> list[dict]:
        records: list[dict] = []

        gbp_check = trial_balance_df.groupby("posting_period", as_index=False).agg(
            actual_gbp=("closing_balance_gbp", "sum")
        )

        for _, row in gbp_check.iterrows():
            records.append(
                self._make_control_row(
                    posting_period=row["posting_period"],
                    currency="GBP_CONSOLIDATED",
                    control_check="TRIAL_BALANCE_GBP_ZERO_CHECK",
                    control_category="Trial Balance Integrity",
                    expected_value_local=0.00,
                    actual_value_local=0.00,
                    expected_value_gbp=0.00,
                    actual_value_gbp=float(row["actual_gbp"]),
                    source_dataset="trial_balance.csv",
                    description="Consolidated GBP closing Trial Balance net balance should equal zero by posting period.",
                )
            )

        local_check = trial_balance_df.groupby(["posting_period", "currency"], as_index=False).agg(
            actual_local=("closing_balance_local", "sum"),
            actual_gbp=("closing_balance_gbp", "sum"),
        )

        for _, row in local_check.iterrows():
            records.append(
                self._make_control_row(
                    posting_period=row["posting_period"],
                    currency=row["currency"],
                    control_check="TRIAL_BALANCE_LOCAL_ZERO_CHECK",
                    control_category="Trial Balance Integrity",
                    expected_value_local=0.00,
                    actual_value_local=float(row["actual_local"]),
                    expected_value_gbp=0.00,
                    actual_value_gbp=float(row["actual_gbp"]),
                    source_dataset="trial_balance.csv",
                    description="Local-currency closing Trial Balance net balance should equal zero by posting period and currency.",
                )
            )

        return records

    def _build_balance_sheet_controls(self, financial_statement_df: pd.DataFrame) -> list[dict]:
        rows = financial_statement_df[
            financial_statement_df["calculation_type"] == "BALANCE_SHEET_CHECK"
        ].copy()

        records: list[dict] = []
        for _, row in rows.iterrows():
            records.append(
                self._make_control_row(
                    posting_period=row["posting_period"],
                    currency=row["currency"],
                    control_check="BALANCE_SHEET_EQUATION_CHECK",
                    control_category="Financial Statement Integrity",
                    expected_value_local=0.00,
                    actual_value_local=float(row["amount_local"]),
                    expected_value_gbp=0.00,
                    actual_value_gbp=float(row["amount_gbp"]),
                    source_dataset="financial_statement_extract.csv",
                    description="Balance Sheet equation check: Total Assets less Total Liabilities and Equity should equal zero.",
                )
            )
        return records

    def _build_profit_and_loss_controls(self, financial_statement_df: pd.DataFrame) -> list[dict]:
        records: list[dict] = []
        account_rows = financial_statement_df[
            (financial_statement_df["statement_type"] == "Income Statement")
            & (financial_statement_df["is_calculated_line"] == 0)
        ].copy()

        revenue = account_rows[account_rows["account_class"] == "Revenue"].groupby(
            ["posting_period", "currency"], as_index=False
        ).agg(revenue_local=("amount_local", "sum"), revenue_gbp=("amount_gbp", "sum"))

        expense = account_rows[account_rows["account_class"] == "Expense"].groupby(
            ["posting_period", "currency"], as_index=False
        ).agg(expense_local=("amount_local", "sum"), expense_gbp=("amount_gbp", "sum"))

        net_income = financial_statement_df[
            financial_statement_df["calculation_type"] == "NET_INCOME"
        ][["posting_period", "currency", "amount_local", "amount_gbp"]].copy()
        net_income = net_income.rename(
            columns={"amount_local": "net_income_local", "amount_gbp": "net_income_gbp"}
        )

        check_df = revenue.merge(expense, on=["posting_period", "currency"], how="outer").merge(
            net_income, on=["posting_period", "currency"], how="outer"
        ).fillna(0.00)

        check_df["expected_net_income_local"] = check_df["revenue_local"] - check_df["expense_local"]
        check_df["expected_net_income_gbp"] = check_df["revenue_gbp"] - check_df["expense_gbp"]
        check_df["variance_local"] = check_df["net_income_local"] - check_df["expected_net_income_local"]
        check_df["variance_gbp"] = check_df["net_income_gbp"] - check_df["expected_net_income_gbp"]

        for _, row in check_df.iterrows():
            records.append(
                self._make_control_row(
                    posting_period=row["posting_period"],
                    currency=row["currency"],
                    control_check="P_AND_L_NET_INCOME_CHECK",
                    control_category="Financial Statement Integrity",
                    expected_value_local=0.00,
                    actual_value_local=float(row["variance_local"]),
                    expected_value_gbp=0.00,
                    actual_value_gbp=float(row["variance_gbp"]),
                    source_dataset="financial_statement_extract.csv",
                    description="Net Income should equal presentation Revenue less presentation Expenses by posting period and currency.",
                )
            )

        return records

    def _get_latest_actual_reporting_period(self, trial_balance_df: pd.DataFrame) -> str:
        candidate_periods = sorted(
            period for period in trial_balance_df["posting_period"].unique() if period <= self.rules.current_reporting_period
        )
        if not candidate_periods:
            raise ValueError(
                "No Trial Balance posting periods are less than or equal to current reporting period "
                f"{self.rules.current_reporting_period}."
            )
        return candidate_periods[-1]

    def _build_ap_tie_out_controls(
        self,
        trial_balance_df: pd.DataFrame,
        vendor_invoices_df: pd.DataFrame,
        vendor_payments_df: pd.DataFrame,
        latest_actual_period: str,
    ) -> list[dict]:
        ledger = trial_balance_df[
            (trial_balance_df["posting_period"] == latest_actual_period)
            & (trial_balance_df["account_code"] == self.ACCOUNT_AP)
        ].copy()
        ledger = ledger.groupby("currency", as_index=False).agg(
            ledger_local=("closing_balance_local", "sum"),
            ledger_gbp=("closing_balance_gbp", "sum"),
        )
        ledger["ledger_local"] = ledger["ledger_local"] * -1
        ledger["ledger_gbp"] = ledger["ledger_gbp"] * -1

        invoices = vendor_invoices_df.groupby("currency", as_index=False).agg(
            invoice_local=("total_local", "sum"),
            invoice_gbp=("total_gbp", "sum"),
        )
        payments = vendor_payments_df.groupby("currency", as_index=False).agg(
            payment_local=("payment_amount_local", "sum"),
            payment_gbp=("payment_amount_gbp", "sum"),
        )
        subledger = invoices.merge(payments, on="currency", how="outer").fillna(0.00)
        subledger["subledger_local"] = subledger["invoice_local"] - subledger["payment_local"]
        subledger["subledger_gbp"] = subledger["invoice_gbp"] - subledger["payment_gbp"]

        check_df = ledger.merge(subledger[["currency", "subledger_local", "subledger_gbp"]], on="currency", how="outer").fillna(0.00)
        check_df["variance_local"] = check_df["ledger_local"] - check_df["subledger_local"]
        check_df["variance_gbp"] = check_df["ledger_gbp"] - check_df["subledger_gbp"]

        records: list[dict] = []
        for _, row in check_df.iterrows():
            records.append(
                self._make_control_row(
                    posting_period=latest_actual_period,
                    currency=row["currency"],
                    control_check="AP_CONTROL_TIE_OUT_CHECK",
                    control_category="Subledger Tie-Out",
                    expected_value_local=0.00,
                    actual_value_local=float(row["variance_local"]),
                    expected_value_gbp=0.00,
                    actual_value_gbp=float(row["variance_gbp"]),
                    source_dataset="trial_balance.csv | vendor_invoices.csv | vendor_payments.csv",
                    description="AP ledger balance for account 2300 should tie to vendor invoice totals less vendor payment totals at latest actual reporting period.",
                )
            )
        return records

    def _build_ar_tie_out_controls(
        self,
        trial_balance_df: pd.DataFrame,
        billing_invoices_df: pd.DataFrame,
        payment_allocations_df: pd.DataFrame,
        latest_actual_period: str,
    ) -> list[dict]:
        ledger = trial_balance_df[
            (trial_balance_df["posting_period"] == latest_actual_period)
            & (trial_balance_df["account_code"] == self.ACCOUNT_AR)
        ].copy()
        ledger = ledger.groupby("currency", as_index=False).agg(
            ledger_local=("closing_balance_local", "sum"),
            ledger_gbp=("closing_balance_gbp", "sum"),
        )

        invoices = billing_invoices_df.groupby("currency", as_index=False).agg(
            invoice_local=("total_local", "sum"),
            invoice_gbp=("total_gbp", "sum"),
        )
        allocations = payment_allocations_df.groupby("currency", as_index=False).agg(
            allocation_local=("allocated_amount_local", "sum"),
            allocation_gbp=("allocated_amount_gbp", "sum"),
        )
        subledger = invoices.merge(allocations, on="currency", how="outer").fillna(0.00)
        subledger["subledger_local"] = subledger["invoice_local"] - subledger["allocation_local"]
        subledger["subledger_gbp"] = subledger["invoice_gbp"] - subledger["allocation_gbp"]

        check_df = ledger.merge(subledger[["currency", "subledger_local", "subledger_gbp"]], on="currency", how="outer").fillna(0.00)
        check_df["variance_local"] = check_df["ledger_local"] - check_df["subledger_local"]
        check_df["variance_gbp"] = check_df["ledger_gbp"] - check_df["subledger_gbp"]

        records: list[dict] = []
        for _, row in check_df.iterrows():
            records.append(
                self._make_control_row(
                    posting_period=latest_actual_period,
                    currency=row["currency"],
                    control_check="AR_CONTROL_TIE_OUT_CHECK",
                    control_category="Subledger Tie-Out",
                    expected_value_local=0.00,
                    actual_value_local=float(row["variance_local"]),
                    expected_value_gbp=0.00,
                    actual_value_gbp=float(row["variance_gbp"]),
                    source_dataset="trial_balance.csv | billing_invoices.csv | billing_payment_allocations.csv",
                    description="AR ledger balance for account 1100 should tie to customer invoice totals less allocated cash at latest actual reporting period.",
                )
            )
        return records

    def _build_deferred_revenue_tie_out_controls(
        self,
        trial_balance_df: pd.DataFrame,
        deferred_revenue_rollforward_df: pd.DataFrame,
        latest_actual_period: str,
    ) -> list[dict]:
        ledger = trial_balance_df[
            (trial_balance_df["posting_period"] == latest_actual_period)
            & (trial_balance_df["account_code"] == self.ACCOUNT_DEFERRED_REVENUE)
        ].copy()
        ledger = ledger.groupby("currency", as_index=False).agg(
            ledger_local=("closing_balance_local", "sum"),
            ledger_gbp=("closing_balance_gbp", "sum"),
        )
        ledger["ledger_local"] = ledger["ledger_local"] * -1
        ledger["ledger_gbp"] = ledger["ledger_gbp"] * -1

        rollforward = deferred_revenue_rollforward_df[
            deferred_revenue_rollforward_df["posting_period"] == latest_actual_period
        ].groupby("currency", as_index=False).agg(
            subledger_local=("closing_deferred_revenue_local", "sum"),
            subledger_gbp=("closing_deferred_revenue_gbp", "sum"),
        )

        check_df = ledger.merge(rollforward, on="currency", how="outer").fillna(0.00)
        check_df["variance_local"] = check_df["ledger_local"] - check_df["subledger_local"]
        check_df["variance_gbp"] = check_df["ledger_gbp"] - check_df["subledger_gbp"]

        records: list[dict] = []
        for _, row in check_df.iterrows():
            records.append(
                self._make_control_row(
                    posting_period=latest_actual_period,
                    currency=row["currency"],
                    control_check="DEFERRED_REVENUE_CONTROL_TIE_OUT_CHECK",
                    control_category="Subledger Tie-Out",
                    expected_value_local=0.00,
                    actual_value_local=float(row["variance_local"]),
                    expected_value_gbp=0.00,
                    actual_value_gbp=float(row["variance_gbp"]),
                    source_dataset="trial_balance.csv | deferred_revenue_rollforward.csv",
                    description="Deferred revenue ledger balance for account 2100 should tie to the deferred revenue roll-forward closing balance at latest actual reporting period.",
                )
            )
        return records

    # ------------------------------------------------------------------
    # Output validation and review
    # ------------------------------------------------------------------

    def _validate_output(self, controls_df: pd.DataFrame) -> None:
        if controls_df.empty:
            raise ValueError("financial_statement_controls.csv would be empty.")

        missing_columns = set(self.OUTPUT_COLUMNS).difference(controls_df.columns)
        if missing_columns:
            raise ValueError(
                f"Financial Statement Controls output missing columns: {sorted(missing_columns)}"
            )

        if controls_df["control_pk"].duplicated().any():
            duplicate_count = int(controls_df["control_pk"].duplicated().sum())
            raise ValueError(f"Duplicate control_pk values generated: {duplicate_count:,}")

        grain = ["posting_period", "currency", "control_check"]
        if controls_df.duplicated(grain).any():
            duplicate_count = int(controls_df.duplicated(grain).sum())
            raise ValueError(
                f"Duplicate Financial Statement Control grain rows generated: {duplicate_count:,}"
            )

        valid_statuses = {"PASS", "FAIL"}
        invalid_statuses = set(controls_df["control_status"].unique()).difference(valid_statuses)
        if invalid_statuses:
            raise ValueError(f"Invalid control_status values generated: {sorted(invalid_statuses)}")

        logger.info("Financial Statement Controls validation passed.")

    def _log_review_summary(self, controls_df: pd.DataFrame) -> None:
        logger.info("----- Financial Statement Controls Review -----")
        logger.info("Financial Statement control rows: %s", f"{len(controls_df):,}")
        logger.info(
            "Posting period range: %s to %s",
            controls_df.loc[controls_df["posting_period"] != "ALL", "posting_period"].min(),
            controls_df.loc[controls_df["posting_period"] != "ALL", "posting_period"].max(),
        )
        logger.info(
            "Control status counts:\n%s",
            controls_df["control_status"].value_counts(dropna=False).to_string(),
        )
        logger.info(
            "Control check counts:\n%s",
            controls_df["control_check"].value_counts(dropna=False).to_string(),
        )
        logger.info(
            "Failed controls by check:\n%s",
            controls_df.loc[controls_df["control_status"] == "FAIL", "control_check"]
            .value_counts(dropna=False)
            .to_string(),
        )
        logger.info(
            "Largest absolute GBP variance by control:\n%s",
            controls_df.groupby("control_check")["absolute_variance_gbp"]
            .max()
            .sort_values(ascending=False)
            .round(2)
            .to_string(),
        )
        logger.info("-----------------------------------------------")

    # ------------------------------------------------------------------
    # Main entry points
    # ------------------------------------------------------------------

    def generate(self) -> pd.DataFrame:
        logger.info("Generating Phase 3J.3 Financial Statement Control Summary.")

        (
            trial_balance_df,
            financial_statement_df,
            erp_gl_df,
            vendor_invoices_df,
            vendor_payments_df,
            billing_invoices_df,
            payment_allocations_df,
            deferred_revenue_rollforward_df,
        ) = self._load_dependencies()

        latest_actual_period = self._get_latest_actual_reporting_period(trial_balance_df)
        logger.info("Latest actual reporting period selected for subledger tie-outs: %s", latest_actual_period)

        records: list[dict] = []
        records.extend(self._build_gl_balance_control(erp_gl_df))
        records.extend(self._build_trial_balance_controls(trial_balance_df))
        records.extend(self._build_balance_sheet_controls(financial_statement_df))
        records.extend(self._build_profit_and_loss_controls(financial_statement_df))
        records.extend(
            self._build_ap_tie_out_controls(
                trial_balance_df=trial_balance_df,
                vendor_invoices_df=vendor_invoices_df,
                vendor_payments_df=vendor_payments_df,
                latest_actual_period=latest_actual_period,
            )
        )
        records.extend(
            self._build_ar_tie_out_controls(
                trial_balance_df=trial_balance_df,
                billing_invoices_df=billing_invoices_df,
                payment_allocations_df=payment_allocations_df,
                latest_actual_period=latest_actual_period,
            )
        )
        records.extend(
            self._build_deferred_revenue_tie_out_controls(
                trial_balance_df=trial_balance_df,
                deferred_revenue_rollforward_df=deferred_revenue_rollforward_df,
                latest_actual_period=latest_actual_period,
            )
        )

        controls_df = pd.DataFrame(records)
        controls_df = controls_df[self.OUTPUT_COLUMNS].copy()
        controls_df = controls_df.sort_values(
            ["posting_period", "currency", "control_category", "control_check"]
        ).reset_index(drop=True)

        self._validate_output(controls_df)
        self._log_review_summary(controls_df)

        return controls_df

    def save(self, controls_df: pd.DataFrame) -> None:
        output_path = get_raw_data_path("accounting") / self.output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        controls_df.to_csv(output_path, index=False)
        logger.info("Financial Statement controls saved to %s", output_path)


if __name__ == "__main__":
    generator = FinancialStatementControlSummaryGenerator()
    controls = generator.generate()
    generator.save(controls)
