"""
erp_gl_journal_lines_generator.py

Project Atlas / Nexus Technologies
Phase 3H.2 - ERP GL Journal Lines Generation

Purpose
-------
Generates:
- data/raw/accounting/erp_gl_journal_lines.csv

This table bridges quote-to-cash subledgers into a synthetic ERP-style
general ledger using balanced double-entry journal lines.

Scope
-----
Quote-to-cash only:

1. Invoice posting
   Dr Accounts Receivable
   Cr Deferred Revenue - Current
   Cr Sales Tax / VAT Payable

2. Cash receipt posting
   Dr Cash at Bank
   Cr Accounts Receivable for applied cash
   Cr Unapplied Cash / Customer Credits for unapplied cash

3. Revenue recognition posting
   Dr Deferred Revenue - Current
   Cr SaaS Subscription Revenue / Legacy Subscription Revenue

Design principle
----------------
Every journal_id must balance:
    total debits = total credits

This starter version excludes labelled defective source rows from normal GL
posting so the GL remains structurally valid. Source-layer defects remain
available for dbt/audit testing in the subledgers.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("ERPGLJournalLinesGenerator", "generation_execution.log")


@dataclass(frozen=True)
class GLGenerationRules:
    created_at: str = "2026-06-03"
    updated_at: str = "2026-06-03"
    balance_tolerance: float = 0.005


class ERPGLJournalLinesGenerator:
    """
    Generate balanced ERP-style GL journal lines for quote-to-cash.

    Inputs
    ------
    data/raw/accounting/chart_of_accounts.csv
    data/raw/billing/billing_invoices.csv
    data/raw/billing/billing_invoice_lines.csv
    data/raw/billing/billing_payments.csv
    data/raw/billing/billing_payment_allocations.csv
    data/raw/revenue/revenue_recognition_schedule.csv

    Output
    ------
    data/raw/accounting/erp_gl_journal_lines.csv
    """

    output_filename = "erp_gl_journal_lines.csv"

    # Core Q2C accounts from chart_of_accounts.csv
    ACCOUNT_CASH_GBP = "1010"
    ACCOUNT_CASH_USD = "1020"
    ACCOUNT_CASH_EUR = "1030"
    ACCOUNT_CASH_SGD = "1040"

    ACCOUNT_AR = "1100"
    ACCOUNT_DEFERRED_REVENUE_CURRENT = "2100"
    ACCOUNT_UNAPPLIED_CASH = "2200"
    ACCOUNT_VAT_PAYABLE = "2500"

    ACCOUNT_SAAS_REVENUE = "4100"
    ACCOUNT_LEGACY_REVENUE = "4110"

    CASH_ACCOUNT_BY_CURRENCY = {
        "GBP": ACCOUNT_CASH_GBP,
        "USD": ACCOUNT_CASH_USD,
        "EUR": ACCOUNT_CASH_EUR,
        "SGD": ACCOUNT_CASH_SGD,
    }

    SUPPORTED_GL_CURRENCIES = {"GBP", "USD", "EUR", "SGD"}

    OUTPUT_COLUMNS = [
        "journal_line_pk",
        "journal_id",
        "journal_line_id",
        "journal_date",
        "posting_period",
        "source_system",
        "source_document_type",
        "source_document_id",
        "source_line_id",
        "customer_id",
        "subscription_id",
        "invoice_id",
        "payment_id",
        "allocation_id",
        "revenue_schedule_id",
        "account_code",
        "account_name",
        "account_class",
        "financial_statement",
        "dc_indicator",
        "debit_local",
        "credit_local",
        "debit_gbp",
        "credit_gbp",
        "currency",
        "description",
        "is_system_generated",
        "is_reversal",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.rules = GLGenerationRules()
        self._journal_line_counter = 0

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

    @staticmethod
    def _first_existing_column(
        df: pd.DataFrame,
        candidates: list[str],
    ) -> str | None:
        for column in candidates:
            if column in df.columns:
                return column
        return None

    def _next_line_id(self) -> str:
        self._journal_line_counter += 1
        return f"GL-LN-{self._journal_line_counter:010d}"

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_csv(self, path: Path, dataset_name: str) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(
                f"{dataset_name} not found at {path}. Run upstream generators first."
            )

        return pd.read_csv(path)

    def _load_dependencies(
        self,
    ) -> tuple[
        pd.DataFrame,
        pd.DataFrame,
        pd.DataFrame,
        pd.DataFrame,
        pd.DataFrame,
        pd.DataFrame,
    ]:
        accounting_dir = get_raw_data_path("accounting")
        billing_dir = get_raw_data_path("billing")
        revenue_dir = get_raw_data_path("revenue")

        coa_df = self._load_csv(
            accounting_dir / "chart_of_accounts.csv",
            "chart_of_accounts.csv",
        )

        invoices_df = self._load_csv(
            billing_dir / "billing_invoices.csv",
            "billing_invoices.csv",
        )

        invoice_lines_df = self._load_csv(
            billing_dir / "billing_invoice_lines.csv",
            "billing_invoice_lines.csv",
        )

        payments_df = self._load_csv(
            billing_dir / "billing_payments.csv",
            "billing_payments.csv",
        )

        allocations_df = self._load_csv(
            billing_dir / "billing_payment_allocations.csv",
            "billing_payment_allocations.csv",
        )

        revrec_df = self._load_csv(
            revenue_dir / "revenue_recognition_schedule.csv",
            "revenue_recognition_schedule.csv",
        )

        coa_df = self._prepare_chart_of_accounts(coa_df)
        invoices_df = self._prepare_invoices(invoices_df)
        invoice_lines_df = self._prepare_invoice_lines(invoice_lines_df)
        payments_df = self._prepare_payments(payments_df)
        allocations_df = self._prepare_payment_allocations(allocations_df)
        revrec_df = self._prepare_revenue_recognition_schedule(revrec_df)

        invoices_df = self._filter_supported_gl_currencies(
            invoices_df,
            dataset_name="billing_invoices.csv",
        )

        invoice_lines_df = self._filter_supported_gl_currencies(
            invoice_lines_df,
            dataset_name="billing_invoice_lines.csv",
        )

        payments_df = self._filter_supported_gl_currencies(
            payments_df,
            dataset_name="billing_payments.csv",
        )

        allocations_df = self._filter_supported_gl_currencies(
            allocations_df,
            dataset_name="billing_payment_allocations.csv",
        )

        revrec_df = self._filter_supported_gl_currencies(
            revrec_df,
            dataset_name="revenue_recognition_schedule.csv",
        )

        retained_invoice_ids = set(invoices_df["invoice_id"].astype(str))

        invoice_lines_df = invoice_lines_df[
            invoice_lines_df["invoice_id"].astype(str).isin(retained_invoice_ids)
        ].copy()

        revrec_df = revrec_df[
            revrec_df["invoice_id"].astype(str).isin(retained_invoice_ids)
        ].copy()

        retained_payment_ids = set(payments_df["payment_id"].astype(str))

        allocations_df = allocations_df[
            allocations_df["payment_id"].astype(str).isin(retained_payment_ids)
        ].copy()

        logger.info(
            "Loaded GL dependencies: %s accounts, %s invoices, %s invoice lines, "
            "%s payments, %s allocations, %s recognition rows.",
            f"{len(coa_df):,}",
            f"{len(invoices_df):,}",
            f"{len(invoice_lines_df):,}",
            f"{len(payments_df):,}",
            f"{len(allocations_df):,}",
            f"{len(revrec_df):,}",
        )

        logger.info(
        "Filtered child GL records to retained parent documents: %s invoice lines, %s allocations, %s recognition rows retained.",
        f"{len(invoice_lines_df):,}",
        f"{len(allocations_df):,}",
        f"{len(revrec_df):,}",
        )
    
        return (
            coa_df,
            invoices_df,
            invoice_lines_df,
            payments_df,
            allocations_df,
            revrec_df,
        )

    # ------------------------------------------------------------------
    # Preparation
    # ------------------------------------------------------------------

    def _prepare_chart_of_accounts(self, coa_df: pd.DataFrame) -> pd.DataFrame:
        df = coa_df.copy()

        self._require_columns(
            df,
            {
                "account_code",
                "account_name",
                "account_class",
                "financial_statement",
                "active_flag",
            },
            "chart_of_accounts.csv",
        )

        df["account_code"] = df["account_code"].apply(self._normalise_account_code)
        df["account_name"] = df["account_name"].astype(str)
        df["account_class"] = df["account_class"].astype(str)
        df["financial_statement"] = df["financial_statement"].astype(str)
        df["active_flag"] = df["active_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=1)
        )

        if df["account_code"].duplicated().any():
            duplicate_count = int(df["account_code"].duplicated().sum())
            raise ValueError(
                f"Duplicate account_code values in chart_of_accounts.csv: {duplicate_count:,}"
            )

        required_accounts = {
            self.ACCOUNT_CASH_GBP,
            self.ACCOUNT_CASH_USD,
            self.ACCOUNT_CASH_EUR,
            self.ACCOUNT_CASH_SGD,
            self.ACCOUNT_AR,
            self.ACCOUNT_DEFERRED_REVENUE_CURRENT,
            self.ACCOUNT_UNAPPLIED_CASH,
            self.ACCOUNT_VAT_PAYABLE,
            self.ACCOUNT_SAAS_REVENUE,
            self.ACCOUNT_LEGACY_REVENUE,
        }

        missing_accounts = required_accounts.difference(set(df["account_code"]))

        if missing_accounts:
            raise ValueError(
                f"chart_of_accounts.csv missing required GL accounts: {sorted(missing_accounts)}"
            )

        return df

    def _prepare_invoices(self, invoices_df: pd.DataFrame) -> pd.DataFrame:
        df = invoices_df.copy()

        self._require_columns(
            df,
            {
                "invoice_id",
                "customer_id",
                "invoice_date",
                "currency",
                "subtotal_local",
                "tax_amount_local",
                "total_local",
                "subtotal_gbp",
                "tax_amount_gbp",
                "total_gbp",
                "source_system",
                "is_defect_flag",
                "defect_type",
            },
            "billing_invoices.csv",
        )

        df["invoice_id"] = df["invoice_id"].astype(str)
        df["customer_id"] = df["customer_id"].astype(str)
        df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
        df["currency"] = df["currency"].astype(str).str.upper()
        df["source_system"] = df["source_system"].fillna("billing").astype(str)
        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        if df["invoice_date"].isna().any():
            bad_count = int(df["invoice_date"].isna().sum())
            raise ValueError(
                f"billing_invoices.csv contains invalid invoice_date values: {bad_count:,}"
            )

        for column in [
            "subtotal_local",
            "tax_amount_local",
            "total_local",
            "subtotal_gbp",
            "tax_amount_gbp",
            "total_gbp",
        ]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00)

        return df

    def _prepare_invoice_lines(self, invoice_lines_df: pd.DataFrame) -> pd.DataFrame:
        df = invoice_lines_df.copy()

        self._require_columns(
            df,
            {
                "invoice_line_id",
                "invoice_id",
                "subscription_id",
                "customer_id",
                "line_type",
                "line_amount_local",
                "line_amount_gbp",
                "currency",
                "is_defect_flag",
                "defect_type",
            },
            "billing_invoice_lines.csv",
        )

        for column in [
            "invoice_line_id",
            "invoice_id",
            "subscription_id",
            "customer_id",
            "line_type",
        ]:
            df[column] = df[column].fillna("").astype(str)

        df["currency"] = df["currency"].astype(str).str.upper()
        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        for column in ["line_amount_local", "line_amount_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00)

        return df

    def _prepare_payments(self, payments_df: pd.DataFrame) -> pd.DataFrame:
        df = payments_df.copy()

        payment_id_col = self._first_existing_column(
            df,
            ["payment_id", "cash_receipt_id", "receipt_id"],
        )
        payment_date_col = self._first_existing_column(
            df,
            ["payment_date", "receipt_date", "cash_receipt_date"],
        )
        currency_col = self._first_existing_column(df, ["currency", "currency_code"])

        if payment_id_col is None or payment_date_col is None or currency_col is None:
            raise ValueError(
                "billing_payments.csv must contain payment_id, payment_date and currency."
            )

        df = df.rename(
            columns={
                payment_id_col: "payment_id",
                payment_date_col: "payment_date",
                currency_col: "currency",
            }
        )

        if "customer_id" not in df.columns:
            df["customer_id"] = None

        if "source_system" not in df.columns:
            df["source_system"] = "billing_payments"

        if "is_defect_flag" not in df.columns:
            df["is_defect_flag"] = 0

        if "defect_type" not in df.columns:
            df["defect_type"] = ""

        local_amount_col = self._first_existing_column(
            df,
            [
                "payment_amount_local",
                "cash_amount_local",
                "receipt_amount_local",
                "amount_local",
                "total_local",
            ],
        )
        gbp_amount_col = self._first_existing_column(
            df,
            [
                "payment_amount_gbp",
                "cash_amount_gbp",
                "receipt_amount_gbp",
                "amount_gbp",
                "total_gbp",
            ],
        )

        if local_amount_col is None or gbp_amount_col is None:
            raise ValueError(
                "billing_payments.csv must contain local and GBP payment amount columns."
            )

        df["payment_amount_local"] = pd.to_numeric(
            df[local_amount_col],
            errors="coerce",
        ).fillna(0.00)
        df["payment_amount_gbp"] = pd.to_numeric(
            df[gbp_amount_col],
            errors="coerce",
        ).fillna(0.00)

        df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce")
        df["currency"] = df["currency"].astype(str).str.upper()
        df["source_system"] = df["source_system"].fillna("billing_payments").astype(str)
        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        if df["payment_date"].isna().any():
            bad_count = int(df["payment_date"].isna().sum())
            raise ValueError(
                f"billing_payments.csv contains invalid payment_date values: {bad_count:,}"
            )

        return df

    def _prepare_payment_allocations(self, allocations_df: pd.DataFrame) -> pd.DataFrame:
        df = allocations_df.copy()

        allocation_id_col = self._first_existing_column(
            df,
            ["allocation_id", "payment_allocation_id", "cash_allocation_id"],
        )
        payment_id_col = self._first_existing_column(
            df,
            ["payment_id", "cash_receipt_id", "receipt_id"],
        )
        invoice_id_col = self._first_existing_column(
            df,
            ["invoice_id", "allocated_invoice_id"],
        )

        if allocation_id_col is None or payment_id_col is None or invoice_id_col is None:
            raise ValueError(
                "billing_payment_allocations.csv must contain allocation_id, payment_id and invoice_id."
            )

        df = df.rename(
            columns={
                allocation_id_col: "allocation_id",
                payment_id_col: "payment_id",
                invoice_id_col: "invoice_id",
            }
        )

        if "customer_id" not in df.columns:
            df["customer_id"] = None

        if "is_defect_flag" not in df.columns:
            df["is_defect_flag"] = 0

        if "defect_type" not in df.columns:
            df["defect_type"] = ""

        local_amount_col = self._first_existing_column(
            df,
            [
                "allocated_amount_local",
                "allocation_amount_local",
                "applied_amount_local",
                "amount_local",
            ],
        )
        gbp_amount_col = self._first_existing_column(
            df,
            [
                "allocated_amount_gbp",
                "allocation_amount_gbp",
                "applied_amount_gbp",
                "amount_gbp",
            ],
        )

        if local_amount_col is None or gbp_amount_col is None:
            raise ValueError(
                "billing_payment_allocations.csv must contain local and GBP allocated amount columns."
            )

        df["allocated_amount_local"] = pd.to_numeric(
            df[local_amount_col],
            errors="coerce",
        ).fillna(0.00)
        df["allocated_amount_gbp"] = pd.to_numeric(
            df[gbp_amount_col],
            errors="coerce",
        ).fillna(0.00)

        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        return df

    def _prepare_revenue_recognition_schedule(self, revrec_df: pd.DataFrame) -> pd.DataFrame:
        df = revrec_df.copy()

        schedule_id_col = self._first_existing_column(
            df,
            [
                "revenue_schedule_id",
                "recognition_id",
                "recognition_schedule_id",
                "schedule_id",
            ],
        )
        recognition_date_col = self._first_existing_column(
            df,
            [
                "recognition_date",
                "recognition_month",
                "revenue_recognition_date",
                "posting_date",
            ],
        )

        if schedule_id_col is None or recognition_date_col is None:
            raise ValueError(
                "revenue_recognition_schedule.csv must contain recognition_id "
                "and recognition_month/date fields."
            )

        df = df.rename(
            columns={
                schedule_id_col: "revenue_schedule_id",
                recognition_date_col: "recognition_date",
            }
        )

        for column in ["invoice_id", "invoice_line_id", "subscription_id", "customer_id"]:
            if column not in df.columns:
                df[column] = None

        if "currency" not in df.columns:
            raise ValueError("revenue_recognition_schedule.csv must contain currency.")

        if "revenue_category" not in df.columns:
            df["revenue_category"] = "Subscription Revenue"

        if "recognition_method" not in df.columns:
            df["recognition_method"] = ""

        if "source_system" not in df.columns:
            df["source_system"] = "revenue_recognition"

        if "is_defect_flag" not in df.columns:
            df["is_defect_flag"] = 0

        if "defect_type" not in df.columns:
            df["defect_type"] = ""

        local_amount_col = self._first_existing_column(
            df,
            [
                "recognised_revenue_local",
                "recognized_revenue_local",
                "recognition_amount_local",
                "revenue_amount_local",
                "amount_local",
            ],
        )
        gbp_amount_col = self._first_existing_column(
            df,
            [
                "recognised_revenue_gbp",
                "recognized_revenue_gbp",
                "recognition_amount_gbp",
                "revenue_amount_gbp",
                "amount_gbp",
            ],
        )

        if local_amount_col is None or gbp_amount_col is None:
            raise ValueError(
                "revenue_recognition_schedule.csv must contain recognised revenue local and GBP columns."
            )

        df["recognised_revenue_local"] = pd.to_numeric(
            df[local_amount_col],
            errors="coerce",
        ).fillna(0.00)
        df["recognised_revenue_gbp"] = pd.to_numeric(
            df[gbp_amount_col],
            errors="coerce",
        ).fillna(0.00)

        df["revenue_schedule_id"] = df["revenue_schedule_id"].astype(str)
        df["recognition_date"] = pd.to_datetime(df["recognition_date"], errors="coerce")
        df["currency"] = df["currency"].astype(str).str.upper()
        df["source_system"] = df["source_system"].fillna("revenue_recognition").astype(str)
        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        if df["recognition_date"].isna().any():
            bad_count = int(df["recognition_date"].isna().sum())
            raise ValueError(
                f"revenue_recognition_schedule.csv contains invalid recognition dates: {bad_count:,}"
            )

        return df

    # ------------------------------------------------------------------
    # Account helpers and line construction
    # ------------------------------------------------------------------

    def _account_lookup(self, coa_df: pd.DataFrame) -> dict[str, dict]:
        active_df = coa_df[coa_df["active_flag"] == 1].copy()
        return active_df.set_index("account_code").to_dict(orient="index")

    def _get_cash_account_code(
        self,
        currency: str,
        coa_lookup: dict[str, dict],
    ) -> str:
        currency = str(currency).upper()

        if currency not in self.CASH_ACCOUNT_BY_CURRENCY:
            raise ValueError(
                f"No configured cash account for currency {currency}. "
                "Add currency mapping or CoA account before GL generation."
            )

        account_code = self.CASH_ACCOUNT_BY_CURRENCY[currency]

        if account_code not in coa_lookup:
            raise ValueError(
                f"Cash account {account_code} for {currency} is missing from active CoA."
            )

        return account_code

    def _build_line(
        self,
        *,
        coa_lookup: dict[str, dict],
        journal_id: str,
        journal_date: object,
        source_system: str,
        source_document_type: str,
        source_document_id: str,
        account_code: str,
        dc_indicator: str,
        amount_local: float,
        amount_gbp: float,
        currency: str,
        description: str,
        source_line_id: str | None = None,
        customer_id: str | None = None,
        subscription_id: str | None = None,
        invoice_id: str | None = None,
        payment_id: str | None = None,
        allocation_id: str | None = None,
        revenue_schedule_id: str | None = None,
    ) -> dict:
        if dc_indicator not in {"D", "C"}:
            raise ValueError(f"Invalid dc_indicator: {dc_indicator}")

        account_code = self._normalise_account_code(account_code)

        if account_code not in coa_lookup:
            raise ValueError(f"Account code {account_code} missing from active CoA.")

        parsed_date = pd.to_datetime(journal_date, errors="coerce")

        if pd.isna(parsed_date):
            raise ValueError(f"Invalid journal date for {journal_id}: {journal_date!r}")

        amount_local = self._round_money(amount_local)
        amount_gbp = self._round_money(amount_gbp)

        if amount_local < 0 or amount_gbp < 0:
            raise ValueError(
                f"Negative GL amount for journal {journal_id}, account {account_code}."
            )

        if amount_local == 0 and amount_gbp == 0:
            raise ValueError(
                f"Zero-value GL amount for journal {journal_id}, account {account_code}."
            )

        line_id = self._next_line_id()
        account = coa_lookup[account_code]

        debit_local = amount_local if dc_indicator == "D" else 0.00
        credit_local = amount_local if dc_indicator == "C" else 0.00
        debit_gbp = amount_gbp if dc_indicator == "D" else 0.00
        credit_gbp = amount_gbp if dc_indicator == "C" else 0.00

        return {
            "journal_line_pk": self._generate_pk(
                f"{journal_id}_{line_id}_{account_code}_{dc_indicator}"
            ),
            "journal_id": journal_id,
            "journal_line_id": line_id,
            "journal_date": parsed_date.strftime("%Y-%m-%d"),
            "posting_period": parsed_date.strftime("%Y-%m"),
            "source_system": source_system,
            "source_document_type": source_document_type,
            "source_document_id": str(source_document_id),
            "source_line_id": source_line_id,
            "customer_id": customer_id,
            "subscription_id": subscription_id,
            "invoice_id": invoice_id,
            "payment_id": payment_id,
            "allocation_id": allocation_id,
            "revenue_schedule_id": revenue_schedule_id,
            "account_code": account_code,
            "account_name": account.get("account_name"),
            "account_class": account.get("account_class"),
            "financial_statement": account.get("financial_statement"),
            "dc_indicator": dc_indicator,
            "debit_local": debit_local,
            "credit_local": credit_local,
            "debit_gbp": debit_gbp,
            "credit_gbp": credit_gbp,
            "currency": str(currency).upper(),
            "description": description,
            "is_system_generated": 1,
            "is_reversal": 0,
            "is_defect_flag": 0,
            "defect_type": "",
            "created_at": self.rules.created_at,
            "updated_at": self.rules.updated_at,
        }
    
    def _filter_supported_gl_currencies(
        self,
        df: pd.DataFrame,
        dataset_name: str,
        currency_column: str = "currency",
    ) -> pd.DataFrame:
        """
        Keep only rows in currencies supported by the current GL CoA.

        AUD/CAD can exist upstream as pricing or currency-mismatch audit traps,
        but Phase 3H.2 v1 only posts Nexus operating currencies to the GL.
        """
        if currency_column not in df.columns:
            raise ValueError(
                f"{dataset_name} is missing currency column: {currency_column}"
            )

        unsupported_mask = ~df[currency_column].astype(str).str.upper().isin(
            self.SUPPORTED_GL_CURRENCIES
        )

        if unsupported_mask.any():
            unsupported_counts = (
                df.loc[unsupported_mask, currency_column]
                .astype(str)
                .str.upper()
                .value_counts()
                .to_dict()
            )

            logger.warning(
                "Excluding %s rows from %s due to unsupported GL currencies: %s",
                f"{int(unsupported_mask.sum()):,}",
                dataset_name,
                unsupported_counts,
            )

        return df.loc[~unsupported_mask].copy()

    # ------------------------------------------------------------------
    # Journal builders
    # ------------------------------------------------------------------

    def _generate_invoice_postings(
        self,
        coa_lookup: dict[str, dict],
        invoices_df: pd.DataFrame,
        invoice_lines_df: pd.DataFrame,
    ) -> list[dict]:
        records: list[dict] = []

        defective_invoice_ids = set(
            invoices_df.loc[invoices_df["is_defect_flag"] == 1, "invoice_id"].astype(str)
        )
        defective_invoice_ids.update(
            invoice_lines_df.loc[
                invoice_lines_df["is_defect_flag"] == 1,
                "invoice_id",
            ].astype(str)
        )

        clean_invoices = invoices_df[
            ~invoices_df["invoice_id"].astype(str).isin(defective_invoice_ids)
        ].copy()

        clean_lines = invoice_lines_df[
            ~invoice_lines_df["invoice_id"].astype(str).isin(defective_invoice_ids)
        ].copy()

        line_groups = clean_lines.groupby("invoice_id")

        for _, invoice in clean_invoices.iterrows():
            invoice_id = str(invoice["invoice_id"])

            if invoice_id not in line_groups.groups:
                continue

            journal_id = f"GL-INV-{invoice_id}"
            invoice_date = invoice["invoice_date"]
            currency = str(invoice["currency"]).upper()
            customer_id = str(invoice["customer_id"])
            source_system = str(invoice["source_system"])

            total_local = self._round_money(invoice["total_local"])
            total_gbp = self._round_money(invoice["total_gbp"])
            subtotal_local = self._round_money(invoice["subtotal_local"])
            subtotal_gbp = self._round_money(invoice["subtotal_gbp"])
            tax_local = self._round_money(invoice["tax_amount_local"])
            tax_gbp = self._round_money(invoice["tax_amount_gbp"])

            if total_local <= 0 and total_gbp <= 0:
                continue

            # Dr AR total
            records.append(
                self._build_line(
                    coa_lookup=coa_lookup,
                    journal_id=journal_id,
                    journal_date=invoice_date,
                    source_system=source_system,
                    source_document_type="Invoice",
                    source_document_id=invoice_id,
                    account_code=self.ACCOUNT_AR,
                    dc_indicator="D",
                    amount_local=total_local,
                    amount_gbp=total_gbp,
                    currency=currency,
                    description=f"Invoice AR debit for {invoice_id}",
                    customer_id=customer_id,
                    invoice_id=invoice_id,
                )
            )

            invoice_line_rows = line_groups.get_group(invoice_id).copy()
            line_local_total = self._round_money(invoice_line_rows["line_amount_local"].sum())
            line_gbp_total = self._round_money(invoice_line_rows["line_amount_gbp"].sum())

            local_adjustment = self._round_money(subtotal_local - line_local_total)
            gbp_adjustment = self._round_money(subtotal_gbp - line_gbp_total)

            last_index = invoice_line_rows.index[-1]

            # Cr deferred revenue by invoice line
            for line_index, line in invoice_line_rows.iterrows():
                credit_local = self._round_money(line["line_amount_local"])
                credit_gbp = self._round_money(line["line_amount_gbp"])

                # residual rounding to ensure header subtotal balance
                if line_index == last_index:
                    credit_local = self._round_money(credit_local + local_adjustment)
                    credit_gbp = self._round_money(credit_gbp + gbp_adjustment)

                if credit_local <= 0 and credit_gbp <= 0:
                    continue

                records.append(
                    self._build_line(
                        coa_lookup=coa_lookup,
                        journal_id=journal_id,
                        journal_date=invoice_date,
                        source_system=source_system,
                        source_document_type="InvoiceLine",
                        source_document_id=invoice_id,
                        source_line_id=str(line["invoice_line_id"]),
                        account_code=self.ACCOUNT_DEFERRED_REVENUE_CURRENT,
                        dc_indicator="C",
                        amount_local=credit_local,
                        amount_gbp=credit_gbp,
                        currency=currency,
                        description=f"Invoice deferred revenue credit for {invoice_id}",
                        customer_id=customer_id,
                        subscription_id=str(line["subscription_id"]),
                        invoice_id=invoice_id,
                    )
                )

            # Cr VAT payable if applicable
            if tax_local > 0 or tax_gbp > 0:
                records.append(
                    self._build_line(
                        coa_lookup=coa_lookup,
                        journal_id=journal_id,
                        journal_date=invoice_date,
                        source_system=source_system,
                        source_document_type="InvoiceTax",
                        source_document_id=invoice_id,
                        account_code=self.ACCOUNT_VAT_PAYABLE,
                        dc_indicator="C",
                        amount_local=tax_local,
                        amount_gbp=tax_gbp,
                        currency=currency,
                        description=f"Invoice tax payable credit for {invoice_id}",
                        customer_id=customer_id,
                        invoice_id=invoice_id,
                    )
                )

        logger.info("Generated invoice GL posting lines: %s", f"{len(records):,}")
        return records

    def _generate_payment_postings(
        self,
        coa_lookup: dict[str, dict],
        payments_df: pd.DataFrame,
        allocations_df: pd.DataFrame,
    ) -> list[dict]:
        records: list[dict] = []

        clean_payments = payments_df[payments_df["is_defect_flag"] == 0].copy()
        clean_allocations = allocations_df[allocations_df["is_defect_flag"] == 0].copy()

        allocation_groups = (
            clean_allocations.groupby("payment_id")
            if not clean_allocations.empty
            else None
        )

        for _, payment in clean_payments.iterrows():
            payment_id = str(payment["payment_id"])
            payment_date = payment["payment_date"]
            journal_id = f"GL-PAY-{payment_id}"
            currency = str(payment["currency"]).upper()
            customer_id = (
                None
                if pd.isna(payment.get("customer_id"))
                else str(payment.get("customer_id"))
            )
            source_system = str(payment.get("source_system", "billing_payments"))

            payment_local = self._round_money(payment["payment_amount_local"])
            payment_gbp = self._round_money(payment["payment_amount_gbp"])

            if payment_local <= 0 and payment_gbp <= 0:
                continue

            cash_account_code = self._get_cash_account_code(
                currency=currency,
                coa_lookup=coa_lookup,
            )

            # Dr Cash
            records.append(
                self._build_line(
                    coa_lookup=coa_lookup,
                    journal_id=journal_id,
                    journal_date=payment_date,
                    source_system=source_system,
                    source_document_type="Payment",
                    source_document_id=payment_id,
                    account_code=cash_account_code,
                    dc_indicator="D",
                    amount_local=payment_local,
                    amount_gbp=payment_gbp,
                    currency=currency,
                    description=f"Cash receipt debit for {payment_id}",
                    customer_id=customer_id,
                    payment_id=payment_id,
                )
            )

            applied_local_total = 0.00
            applied_gbp_total = 0.00

            # Cr AR for applied allocations
            if allocation_groups is not None and payment_id in allocation_groups.groups:
                payment_allocations = allocation_groups.get_group(payment_id)

                for _, allocation in payment_allocations.iterrows():
                    allocated_local = self._round_money(allocation["allocated_amount_local"])
                    allocated_gbp = self._round_money(allocation["allocated_amount_gbp"])

                    if allocated_local <= 0 and allocated_gbp <= 0:
                        continue

                    applied_local_total = self._round_money(
                        applied_local_total + allocated_local
                    )
                    applied_gbp_total = self._round_money(
                        applied_gbp_total + allocated_gbp
                    )

                    allocation_customer_id = (
                        customer_id
                        if pd.isna(allocation.get("customer_id"))
                        else str(allocation.get("customer_id"))
                    )

                    records.append(
                        self._build_line(
                            coa_lookup=coa_lookup,
                            journal_id=journal_id,
                            journal_date=payment_date,
                            source_system=source_system,
                            source_document_type="PaymentAllocation",
                            source_document_id=payment_id,
                            source_line_id=str(allocation["allocation_id"]),
                            account_code=self.ACCOUNT_AR,
                            dc_indicator="C",
                            amount_local=allocated_local,
                            amount_gbp=allocated_gbp,
                            currency=currency,
                            description=f"Cash application AR credit for {payment_id}",
                            customer_id=allocation_customer_id,
                            invoice_id=str(allocation["invoice_id"]),
                            payment_id=payment_id,
                            allocation_id=str(allocation["allocation_id"]),
                        )
                    )

            unapplied_local = self._round_money(payment_local - applied_local_total)
            unapplied_gbp = self._round_money(payment_gbp - applied_gbp_total)

            if unapplied_local < -0.01 or unapplied_gbp < -0.01:
                raise ValueError(
                    f"Payment {payment_id} is over-allocated after excluding defects. "
                    f"Payment local/GBP={payment_local}/{payment_gbp}; "
                    f"allocated local/GBP={applied_local_total}/{applied_gbp_total}."
                )

            # Cr unapplied cash/customer credits for any remaining balance.
            if unapplied_local > 0.00 or unapplied_gbp > 0.00:
                records.append(
                    self._build_line(
                        coa_lookup=coa_lookup,
                        journal_id=journal_id,
                        journal_date=payment_date,
                        source_system=source_system,
                        source_document_type="UnappliedPayment",
                        source_document_id=payment_id,
                        account_code=self.ACCOUNT_UNAPPLIED_CASH,
                        dc_indicator="C",
                        amount_local=max(0.00, unapplied_local),
                        amount_gbp=max(0.00, unapplied_gbp),
                        currency=currency,
                        description=f"Unapplied customer cash credit for {payment_id}",
                        customer_id=customer_id,
                        payment_id=payment_id,
                    )
                )

        logger.info("Generated payment GL posting lines: %s", f"{len(records):,}")
        return records

    def _generate_revenue_recognition_postings(
        self,
        coa_lookup: dict[str, dict],
        revrec_df: pd.DataFrame,
        invoice_lines_df: pd.DataFrame,
    ) -> list[dict]:
        records: list[dict] = []

        clean_revrec = revrec_df[revrec_df["is_defect_flag"] == 0].copy()
        clean_invoice_lines = invoice_lines_df[
            invoice_lines_df["is_defect_flag"] == 0
        ].copy()

        line_lookup = (
            clean_invoice_lines.set_index("invoice_line_id").to_dict(orient="index")
            if not clean_invoice_lines.empty
            else {}
        )

        for _, schedule in clean_revrec.iterrows():
            schedule_id = str(schedule["revenue_schedule_id"])
            recognition_date = schedule["recognition_date"]
            journal_id = f"GL-REV-{schedule_id}"
            currency = str(schedule["currency"]).upper()

            amount_local = self._round_money(schedule["recognised_revenue_local"])
            amount_gbp = self._round_money(schedule["recognised_revenue_gbp"])

            if amount_local <= 0 and amount_gbp <= 0:
                continue

            invoice_line_id = (
                None
                if pd.isna(schedule.get("invoice_line_id"))
                else str(schedule.get("invoice_line_id"))
            )
            invoice_id = (
                None
                if pd.isna(schedule.get("invoice_id"))
                else str(schedule.get("invoice_id"))
            )
            subscription_id = (
                None
                if pd.isna(schedule.get("subscription_id"))
                else str(schedule.get("subscription_id"))
            )
            customer_id = (
                None
                if pd.isna(schedule.get("customer_id"))
                else str(schedule.get("customer_id"))
            )

            line_type = ""

            if invoice_line_id and invoice_line_id in line_lookup:
                source_line = line_lookup[invoice_line_id]
                line_type = str(source_line.get("line_type", ""))
                invoice_id = invoice_id or str(source_line.get("invoice_id", ""))
                subscription_id = subscription_id or str(source_line.get("subscription_id", ""))
                customer_id = customer_id or str(source_line.get("customer_id", ""))

            revenue_account_code = (
                self.ACCOUNT_LEGACY_REVENUE
                if "legacy" in line_type.lower()
                else self.ACCOUNT_SAAS_REVENUE
            )

            source_system = str(schedule.get("source_system", "revenue_recognition"))

            # Dr deferred revenue
            records.append(
                self._build_line(
                    coa_lookup=coa_lookup,
                    journal_id=journal_id,
                    journal_date=recognition_date,
                    source_system=source_system,
                    source_document_type="RevenueRecognition",
                    source_document_id=schedule_id,
                    source_line_id=invoice_line_id,
                    account_code=self.ACCOUNT_DEFERRED_REVENUE_CURRENT,
                    dc_indicator="D",
                    amount_local=amount_local,
                    amount_gbp=amount_gbp,
                    currency=currency,
                    description=f"Deferred revenue release for {schedule_id}",
                    customer_id=customer_id,
                    subscription_id=subscription_id,
                    invoice_id=invoice_id,
                    revenue_schedule_id=schedule_id,
                )
            )

            # Cr revenue
            records.append(
                self._build_line(
                    coa_lookup=coa_lookup,
                    journal_id=journal_id,
                    journal_date=recognition_date,
                    source_system=source_system,
                    source_document_type="RevenueRecognition",
                    source_document_id=schedule_id,
                    source_line_id=invoice_line_id,
                    account_code=revenue_account_code,
                    dc_indicator="C",
                    amount_local=amount_local,
                    amount_gbp=amount_gbp,
                    currency=currency,
                    description=f"Recognised revenue credit for {schedule_id}",
                    customer_id=customer_id,
                    subscription_id=subscription_id,
                    invoice_id=invoice_id,
                    revenue_schedule_id=schedule_id,
                )
            )

        logger.info(
            "Generated revenue recognition GL posting lines: %s",
            f"{len(records):,}",
        )

        return records

    # ------------------------------------------------------------------
    # Finalisation / validation
    # ------------------------------------------------------------------

    def _finalise_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        for column in self.OUTPUT_COLUMNS:
            if column not in df.columns:
                df[column] = None

        df = df[self.OUTPUT_COLUMNS].copy()

        for column in ["debit_local", "credit_local", "debit_gbp", "credit_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00).round(2)

        for column in ["is_system_generated", "is_reversal", "is_defect_flag"]:
            df[column] = df[column].fillna(0).astype(int)

        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        df = df.sort_values(
            ["journal_date", "journal_id", "journal_line_id"]
        ).reset_index(drop=True)

        return df

    def _validate_output(self, df: pd.DataFrame, coa_df: pd.DataFrame) -> None:
        logger.info("Running ERP GL journal validation.")

        if df.empty:
            raise ValueError("No GL journal lines generated.")

        if df["journal_line_id"].duplicated().any():
            duplicate_count = int(df["journal_line_id"].duplicated().sum())
            raise ValueError(f"Duplicate journal_line_id values found: {duplicate_count:,}")

        if df["journal_line_pk"].duplicated().any():
            duplicate_count = int(df["journal_line_pk"].duplicated().sum())
            raise ValueError(f"Duplicate journal_line_pk values found: {duplicate_count:,}")

        invalid_dc = set(df["dc_indicator"].dropna().unique()).difference({"D", "C"})
        if invalid_dc:
            raise ValueError(f"Invalid dc_indicator values found: {sorted(invalid_dc)}")

        both_sides = df[
            ((df["debit_local"] > 0) & (df["credit_local"] > 0))
            | ((df["debit_gbp"] > 0) & (df["credit_gbp"] > 0))
        ]

        if not both_sides.empty:
            raise ValueError(f"GL lines with both debit and credit found: {len(both_sides):,}")

        zero_lines = df[
            (df["debit_local"] == 0)
            & (df["credit_local"] == 0)
            & (df["debit_gbp"] == 0)
            & (df["credit_gbp"] == 0)
        ]

        if not zero_lines.empty:
            raise ValueError(f"Zero-value GL lines found: {len(zero_lines):,}")

        valid_account_codes = set(coa_df["account_code"].astype(str))
        invalid_account_codes = set(df["account_code"].astype(str)).difference(
            valid_account_codes
        )

        if invalid_account_codes:
            raise ValueError(
                f"GL contains account codes missing from CoA: {sorted(invalid_account_codes)}"
            )

        balance_check = (
            df.groupby("journal_id", as_index=False)
            .agg(
                debit_local=("debit_local", "sum"),
                credit_local=("credit_local", "sum"),
                debit_gbp=("debit_gbp", "sum"),
                credit_gbp=("credit_gbp", "sum"),
                line_count=("journal_line_id", "count"),
            )
        )

        balance_check["local_delta"] = (
            balance_check["debit_local"] - balance_check["credit_local"]
        ).round(2)
        balance_check["gbp_delta"] = (
            balance_check["debit_gbp"] - balance_check["credit_gbp"]
        ).round(2)

        out_of_balance = balance_check[
            (balance_check["local_delta"].abs() > self.rules.balance_tolerance)
            | (balance_check["gbp_delta"].abs() > self.rules.balance_tolerance)
        ]

        if not out_of_balance.empty:
            sample = out_of_balance.head(10).to_dict(orient="records")
            raise ValueError(
                "GL journal balance validation failed. Sample failures: "
                f"{sample}"
            )

        single_line_journals = balance_check[balance_check["line_count"] < 2]

        if not single_line_journals.empty:
            raise ValueError(
                f"Single-line journals found: {len(single_line_journals):,}"
            )

        logger.info(
            "ERP GL journal validation passed for %s journals.",
            f"{len(balance_check):,}",
        )

    def _log_output_review(self, df: pd.DataFrame) -> None:
        logger.info("----- ERP GL Journal Lines Review -----")
        logger.info("Journal line rows: %s", f"{len(df):,}")
        logger.info("Journal count: %s", f"{df['journal_id'].nunique():,}")

        logger.info(
            "Lines by source document type:\n%s",
            df["source_document_type"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Rows by account:\n%s",
            df["account_code"].value_counts().sort_index().to_string(),
        )

        net_by_account = (
            df.assign(net_gbp=df["debit_gbp"] - df["credit_gbp"])
            .groupby(["account_code", "account_name"], dropna=False)["net_gbp"]
            .sum()
            .round(2)
            .sort_index()
        )

        logger.info(
            "Net GBP by account:\n%s",
            net_by_account.to_string(),
        )

        logger.info(
            "Journal rows by posting period:\n%s",
            df["posting_period"].value_counts().sort_index().to_string(),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> pd.DataFrame:
        logger.info("Generating ERP GL Journal Lines.")

        (
            coa_df,
            invoices_df,
            invoice_lines_df,
            payments_df,
            allocations_df,
            revrec_df,
        ) = self._load_dependencies()

        coa_lookup = self._account_lookup(coa_df)

        records: list[dict] = []

        records.extend(
            self._generate_invoice_postings(
                coa_lookup=coa_lookup,
                invoices_df=invoices_df,
                invoice_lines_df=invoice_lines_df,
            )
        )

        records.extend(
            self._generate_payment_postings(
                coa_lookup=coa_lookup,
                payments_df=payments_df,
                allocations_df=allocations_df,
            )
        )

        records.extend(
            self._generate_revenue_recognition_postings(
                coa_lookup=coa_lookup,
                revrec_df=revrec_df,
                invoice_lines_df=invoice_lines_df,
            )
        )

        df = pd.DataFrame(records)
        df = self._finalise_dataframe(df)

        self._validate_output(df=df, coa_df=coa_df)
        self._log_output_review(df)

        logger.info("Generated %s ERP GL journal line records.", f"{len(df):,}")

        return df

    def save(self, df: pd.DataFrame) -> None:
        output_dir = get_raw_data_path("accounting")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / self.output_filename
        df.to_csv(output_path, index=False, encoding="utf-8")

        logger.info("ERP GL journal lines written to %s", output_path)


def main() -> None:
    generator = ERPGLJournalLinesGenerator()
    df = generator.generate()
    generator.save(df)

    logger.info(
        "Phase 3H.2 standalone run complete. Saved %s ERP GL journal lines.",
        f"{len(df):,}",
    )


if __name__ == "__main__":
    main()