"""
chart_of_accounts_generator.py

Project Atlas / Nexus Technologies
Phase 3H.1 - Chart of Accounts

Purpose
-------
Generates chart_of_accounts.csv as the accounting reference spine for the
general ledger.

This table supports:
- GL journal generation
- trial balance reporting
- P&L and balance sheet modelling
- dbt financial statement marts
- account-level validation
- normal balance checks
- control account reconciliation

Design
------
The source-layer output is called chart_of_accounts.csv.

Downstream dbt will transform this into dim_chart_of_accounts.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

import pandas as pd

from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("ChartOfAccountsGenerator", "generation_execution.log")


@dataclass(frozen=True)
class ChartOfAccountsRules:
    """Static metadata rules for the chart of accounts."""

    created_at: date = date(2026, 6, 3)
    updated_at: date = date(2026, 6, 3)


class ChartOfAccountsGenerator:
    """
    Generates a static 4-digit Chart of Accounts reference file.

    Output
    ------
    data/raw/accounting/chart_of_accounts.csv
    """

    output_filename = "chart_of_accounts.csv"

    ACCOUNT_COLUMNS = [
        "account_pk",
        "account_code",
        "account_name",
        "account_class",
        "account_type",
        "financial_statement",
        "report_group",
        "report_subgroup",
        "normal_balance",
        "is_pnl",
        "is_balance_sheet",
        "is_cash_account",
        "is_control_account",
        "active_flag",
        "created_at",
        "updated_at",
    ]

    VALID_ACCOUNT_CLASSES = {
        "Asset",
        "Liability",
        "Equity",
        "Revenue",
        "Expense",
    }

    VALID_NORMAL_BALANCES = {
        "Debit",
        "Credit",
    }

    VALID_FINANCIAL_STATEMENTS = {
        "Balance Sheet",
        "Income Statement",
    }

    def __init__(self) -> None:
        self.rules = ChartOfAccountsRules()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pk(value: str) -> str:
        """Generate deterministic MD5 surrogate key."""
        return hashlib.md5(value.strip().upper().encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Account definition
    # ------------------------------------------------------------------

    def _account_records(self) -> list[dict]:
        """
        Define static account metadata.

        Account ranges:
        1000-1999 Assets
        2000-2999 Liabilities
        3000-3999 Equity
        4000-4999 Revenue
        5000-9999 Expenses
        """
        accounts = [
            # ----------------------------------------------------------
            # Assets
            # ----------------------------------------------------------
            {
                "account_code": "1010",
                "account_name": "Cash at Bank - GBP",
                "account_class": "Asset",
                "account_type": "Current Asset",
                "financial_statement": "Balance Sheet",
                "report_group": "Cash and Cash Equivalents",
                "report_subgroup": "Cash at Bank",
                "normal_balance": "Debit",
                "is_cash_account": 1,
                "is_control_account": 1,
            },
            {
                "account_code": "1020",
                "account_name": "Cash at Bank - USD",
                "account_class": "Asset",
                "account_type": "Current Asset",
                "financial_statement": "Balance Sheet",
                "report_group": "Cash and Cash Equivalents",
                "report_subgroup": "Cash at Bank",
                "normal_balance": "Debit",
                "is_cash_account": 1,
                "is_control_account": 1,
            },
            {
                "account_code": "1030",
                "account_name": "Cash at Bank - EUR",
                "account_class": "Asset",
                "account_type": "Current Asset",
                "financial_statement": "Balance Sheet",
                "report_group": "Cash and Cash Equivalents",
                "report_subgroup": "Cash at Bank",
                "normal_balance": "Debit",
                "is_cash_account": 1,
                "is_control_account": 1,
            },
            {
                "account_code": "1040",
                "account_name": "Cash at Bank - SGD",
                "account_class": "Asset",
                "account_type": "Current Asset",
                "financial_statement": "Balance Sheet",
                "report_group": "Cash and Cash Equivalents",
                "report_subgroup": "Cash at Bank",
                "normal_balance": "Debit",
                "is_cash_account": 1,
                "is_control_account": 1,
            },
            {
                "account_code": "1100",
                "account_name": "Accounts Receivable",
                "account_class": "Asset",
                "account_type": "Current Asset",
                "financial_statement": "Balance Sheet",
                "report_group": "Accounts Receivable",
                "report_subgroup": "Trade Receivables",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 1,
            },
            {
                "account_code": "1200",
                "account_name": "Prepaid Expenses",
                "account_class": "Asset",
                "account_type": "Current Asset",
                "financial_statement": "Balance Sheet",
                "report_group": "Prepayments",
                "report_subgroup": "Operating Prepayments",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "1500",
                "account_name": "Property and Equipment",
                "account_class": "Asset",
                "account_type": "Non-Current Asset",
                "financial_statement": "Balance Sheet",
                "report_group": "Fixed Assets",
                "report_subgroup": "Property and Equipment",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "1590",
                "account_name": "Accumulated Depreciation",
                "account_class": "Asset",
                "account_type": "Contra Asset",
                "financial_statement": "Balance Sheet",
                "report_group": "Fixed Assets",
                "report_subgroup": "Accumulated Depreciation",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },

            # ----------------------------------------------------------
            # Liabilities
            # ----------------------------------------------------------
            {
                "account_code": "2100",
                "account_name": "Deferred Revenue - Current",
                "account_class": "Liability",
                "account_type": "Current Liability",
                "financial_statement": "Balance Sheet",
                "report_group": "Deferred Revenue",
                "report_subgroup": "Current Deferred Revenue",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 1,
            },
            {
                "account_code": "2110",
                "account_name": "Deferred Revenue - Non-Current",
                "account_class": "Liability",
                "account_type": "Non-Current Liability",
                "financial_statement": "Balance Sheet",
                "report_group": "Deferred Revenue",
                "report_subgroup": "Non-Current Deferred Revenue",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 1,
            },
            {
                "account_code": "2200",
                "account_name": "Unapplied Cash / Customer Credits",
                "account_class": "Liability",
                "account_type": "Current Liability",
                "financial_statement": "Balance Sheet",
                "report_group": "Customer Credits",
                "report_subgroup": "Unapplied Cash",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 1,
            },
            {
                "account_code": "2300",
                "account_name": "Accounts Payable",
                "account_class": "Liability",
                "account_type": "Current Liability",
                "financial_statement": "Balance Sheet",
                "report_group": "Accounts Payable",
                "report_subgroup": "Trade Payables",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 1,
            },
            {
                "account_code": "2400",
                "account_name": "Accrued Expenses",
                "account_class": "Liability",
                "account_type": "Current Liability",
                "financial_statement": "Balance Sheet",
                "report_group": "Accrued Expenses",
                "report_subgroup": "Operating Accruals",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "2500",
                "account_name": "Sales Tax / VAT Payable",
                "account_class": "Liability",
                "account_type": "Current Liability",
                "financial_statement": "Balance Sheet",
                "report_group": "Tax Payable",
                "report_subgroup": "Sales Tax / VAT",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 1,
            },

            # ----------------------------------------------------------
            # Equity
            # ----------------------------------------------------------
            {
                "account_code": "3100",
                "account_name": "Share Capital",
                "account_class": "Equity",
                "account_type": "Equity",
                "financial_statement": "Balance Sheet",
                "report_group": "Shareholders Equity",
                "report_subgroup": "Share Capital",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "3200",
                "account_name": "Retained Earnings",
                "account_class": "Equity",
                "account_type": "Equity",
                "financial_statement": "Balance Sheet",
                "report_group": "Shareholders Equity",
                "report_subgroup": "Retained Earnings",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },

            # ----------------------------------------------------------
            # Revenue
            # ----------------------------------------------------------
            {
                "account_code": "4100",
                "account_name": "SaaS Subscription Revenue",
                "account_class": "Revenue",
                "account_type": "Operating Revenue",
                "financial_statement": "Income Statement",
                "report_group": "Revenue",
                "report_subgroup": "Subscription Revenue",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "4110",
                "account_name": "Legacy Subscription Revenue",
                "account_class": "Revenue",
                "account_type": "Operating Revenue",
                "financial_statement": "Income Statement",
                "report_group": "Revenue",
                "report_subgroup": "Legacy Subscription Revenue",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "4200",
                "account_name": "Professional Services Revenue",
                "account_class": "Revenue",
                "account_type": "Operating Revenue",
                "financial_statement": "Income Statement",
                "report_group": "Revenue",
                "report_subgroup": "Professional Services Revenue",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "4300",
                "account_name": "Usage-Based Revenue",
                "account_class": "Revenue",
                "account_type": "Operating Revenue",
                "financial_statement": "Income Statement",
                "report_group": "Revenue",
                "report_subgroup": "Usage-Based Revenue",
                "normal_balance": "Credit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },

            # ----------------------------------------------------------
            # Cost of Sales / COGS
            # ----------------------------------------------------------
            {
                "account_code": "5100",
                "account_name": "Hosting / Cloud Infrastructure COGS",
                "account_class": "Expense",
                "account_type": "Cost of Sales",
                "financial_statement": "Income Statement",
                "report_group": "Cost of Sales",
                "report_subgroup": "Cloud Infrastructure",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "5200",
                "account_name": "Customer Support COGS",
                "account_class": "Expense",
                "account_type": "Cost of Sales",
                "financial_statement": "Income Statement",
                "report_group": "Cost of Sales",
                "report_subgroup": "Customer Support",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },

            # ----------------------------------------------------------
            # Operating Expenses
            # ----------------------------------------------------------
            {
                "account_code": "6100",
                "account_name": "Payroll Expense",
                "account_class": "Expense",
                "account_type": "Operating Expense",
                "financial_statement": "Income Statement",
                "report_group": "Operating Expenses",
                "report_subgroup": "Payroll",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "6200",
                "account_name": "Sales & Marketing Expense",
                "account_class": "Expense",
                "account_type": "Operating Expense",
                "financial_statement": "Income Statement",
                "report_group": "Operating Expenses",
                "report_subgroup": "Sales & Marketing",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "6300",
                "account_name": "Software / SaaS Tools Expense",
                "account_class": "Expense",
                "account_type": "Operating Expense",
                "financial_statement": "Income Statement",
                "report_group": "Operating Expenses",
                "report_subgroup": "Software Tools",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "6400",
                "account_name": "Rent & Office Expense",
                "account_class": "Expense",
                "account_type": "Operating Expense",
                "financial_statement": "Income Statement",
                "report_group": "Operating Expenses",
                "report_subgroup": "Facilities",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "6500",
                "account_name": "Professional Fees",
                "account_class": "Expense",
                "account_type": "Operating Expense",
                "financial_statement": "Income Statement",
                "report_group": "Operating Expenses",
                "report_subgroup": "Professional Fees",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "6600",
                "account_name": "Travel & Entertainment",
                "account_class": "Expense",
                "account_type": "Operating Expense",
                "financial_statement": "Income Statement",
                "report_group": "Operating Expenses",
                "report_subgroup": "Travel & Entertainment",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "6700",
                "account_name": "Bad Debt Expense",
                "account_class": "Expense",
                "account_type": "Operating Expense",
                "financial_statement": "Income Statement",
                "report_group": "Operating Expenses",
                "report_subgroup": "Bad Debt",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "6800",
                "account_name": "FX Gain / Loss",
                "account_class": "Expense",
                "account_type": "Other Expense",
                "financial_statement": "Income Statement",
                "report_group": "Other Income / Expense",
                "report_subgroup": "Foreign Exchange",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
            {
                "account_code": "6900",
                "account_name": "Depreciation & Amortisation",
                "account_class": "Expense",
                "account_type": "Operating Expense",
                "financial_statement": "Income Statement",
                "report_group": "Operating Expenses",
                "report_subgroup": "Depreciation & Amortisation",
                "normal_balance": "Debit",
                "is_cash_account": 0,
                "is_control_account": 0,
            },
        ]

        return accounts

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self) -> pd.DataFrame:
        """Generate chart of accounts dataframe."""
        logger.info("Generating Chart of Accounts.")

        records: list[dict] = []

        for account in self._account_records():
            account_code = str(account["account_code"])

            account_class = str(account["account_class"])
            financial_statement = str(account["financial_statement"])

            record = {
                "account_pk": self._generate_pk(account_code),
                "account_code": account_code,
                "account_name": str(account["account_name"]),
                "account_class": account_class,
                "account_type": str(account["account_type"]),
                "financial_statement": financial_statement,
                "report_group": str(account["report_group"]),
                "report_subgroup": str(account["report_subgroup"]),
                "normal_balance": str(account["normal_balance"]),
                "is_pnl": int(financial_statement == "Income Statement"),
                "is_balance_sheet": int(financial_statement == "Balance Sheet"),
                "is_cash_account": int(account["is_cash_account"]),
                "is_control_account": int(account["is_control_account"]),
                "active_flag": 1,
                "created_at": self.rules.created_at.isoformat(),
                "updated_at": self.rules.updated_at.isoformat(),
            }

            records.append(record)

        df = pd.DataFrame(records)
        df = self._finalise_dataframe(df)

        self._validate_output(df)
        self._log_output_review(df)

        logger.info("Generated %s chart of accounts rows.", f"{len(df):,}")

        return df

    def _finalise_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply final column order and stable sorting."""
        df = df.reindex(columns=self.ACCOUNT_COLUMNS)

        df = df.sort_values("account_code").reset_index(drop=True)

        return df

    # ------------------------------------------------------------------
    # Validation and logging
    # ------------------------------------------------------------------

    def _validate_output(self, df: pd.DataFrame) -> None:
        """Validate Chart of Accounts structure."""
        if df.empty:
            raise ValueError("Chart of Accounts output cannot be empty.")

        missing_columns = set(self.ACCOUNT_COLUMNS).difference(df.columns)

        if missing_columns:
            raise ValueError(
                f"Chart of Accounts output missing columns: {sorted(missing_columns)}"
            )

        if df["account_code"].duplicated().any():
            duplicate_count = int(df["account_code"].duplicated().sum())
            raise ValueError(f"Duplicate account_code values found: {duplicate_count:,}")

        if df["account_pk"].duplicated().any():
            duplicate_count = int(df["account_pk"].duplicated().sum())
            raise ValueError(f"Duplicate account_pk values found: {duplicate_count:,}")

        if not df["account_code"].astype(str).str.fullmatch(r"\d{4}").all():
            raise ValueError("All account_code values must be 4-digit numeric strings.")

        invalid_classes = set(df["account_class"]).difference(self.VALID_ACCOUNT_CLASSES)

        if invalid_classes:
            raise ValueError(f"Invalid account_class values found: {sorted(invalid_classes)}")

        invalid_normal_balances = set(df["normal_balance"]).difference(
            self.VALID_NORMAL_BALANCES
        )

        if invalid_normal_balances:
            raise ValueError(
                f"Invalid normal_balance values found: {sorted(invalid_normal_balances)}"
            )

        invalid_statements = set(df["financial_statement"]).difference(
            self.VALID_FINANCIAL_STATEMENTS
        )

        if invalid_statements:
            raise ValueError(
                f"Invalid financial_statement values found: {sorted(invalid_statements)}"
            )

        for column in [
            "is_pnl",
            "is_balance_sheet",
            "is_cash_account",
            "is_control_account",
            "active_flag",
        ]:
            if not df[column].isin([0, 1]).all():
                raise ValueError(f"{column} must only contain 0 or 1.")

        pnl_mismatch = df[
            (df["financial_statement"] == "Income Statement")
            & (df["is_pnl"] != 1)
        ]

        if not pnl_mismatch.empty:
            raise ValueError("Income Statement accounts must have is_pnl = 1.")

        bs_mismatch = df[
            (df["financial_statement"] == "Balance Sheet")
            & (df["is_balance_sheet"] != 1)
        ]

        if not bs_mismatch.empty:
            raise ValueError("Balance Sheet accounts must have is_balance_sheet = 1.")

        required_codes = {
            "1010",
            "1020",
            "1030",
            "1040",
            "1100",
            "2100",
            "2200",
            "4100",
            "4110",
            "6700",
        }

        missing_required_codes = required_codes.difference(
            set(df["account_code"].astype(str))
        )

        if missing_required_codes:
            raise ValueError(
                f"Required GL account codes missing: {sorted(missing_required_codes)}"
            )

        logger.info("Chart of Accounts validation passed.")

    def _log_output_review(self, df: pd.DataFrame) -> None:
        """Log useful CoA review summaries."""
        logger.info("----- Chart of Accounts Review -----")
        logger.info("Account rows: %s", f"{len(df):,}")

        logger.info(
            "Accounts by class:\n%s",
            df["account_class"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Accounts by financial statement:\n%s",
            df["financial_statement"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Control account count: %s",
            f"{int(df['is_control_account'].sum()):,}",
        )

        logger.info(
            "Cash account count: %s",
            f"{int(df['is_cash_account'].sum()):,}",
        )

    def save(self, df: pd.DataFrame) -> None:
        """Save Chart of Accounts output."""
        output_dir = get_raw_data_path("accounting")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / self.output_filename

        df.to_csv(output_path, index=False, encoding="utf-8")

        logger.info("Chart of Accounts written to %s", output_path)


def main() -> None:
    generator = ChartOfAccountsGenerator()
    df = generator.generate()
    generator.save(df)

    logger.info(
        "Phase 3H.1 standalone run complete. Saved %s Chart of Accounts rows.",
        f"{len(df):,}",
    )


if __name__ == "__main__":
    main()