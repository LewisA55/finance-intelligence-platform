"""
billing_invoices_generator.py

Project Atlas / Nexus Technologies
Phase 3E - Billing Invoice & Invoice Line Generation

Purpose
-------
Generates:
- billing_invoices.csv
- billing_invoice_lines.csv

This layer converts subscription schedules and subscription event history into
actual customer billing documents.

Design
------
billing_subscriptions.csv
    = contract schedule / billing setup

billing_subscription_events.csv
    = commercial MRR/ARR movement ledger

billing_invoices.csv
    = customer-level invoice document header

billing_invoice_lines.csv
    = subscription-level billing detail

Grain
-----
billing_invoices.csv:
    One row per customer_id + invoice_date + currency.

billing_invoice_lines.csv:
    One row per subscription invoice line on a billing document.

Normal billing generation uses clean subscription event rows only.
Invoice-specific audit traps are injected separately afterwards.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("BillingInvoicesGenerator", "generation_execution.log")


@dataclass(frozen=True)
class BillingInvoiceRules:
    """Business rules for invoice generation."""

    start_date: date = date(2023, 1, 1)
    end_date: date = date(2026, 6, 3)
    created_at: date = date(2026, 6, 3)
    updated_at: date = date(2026, 6, 3)


@dataclass(frozen=True)
class BillingInvoiceDefectRates:
    """Controlled synthetic defect rates for invoice data."""

    duplicate_invoice: float = 0.005
    orphan_subscription_line: float = 0.005
    tax_calculation_error: float = 0.005
    invoice_after_churn: float = 0.005
    payment_term_mismatch: float = 0.005
    zero_value_invoice: float = 0.005
    currency_mismatch: float = 0.005


class BillingInvoicesGenerator:
    """
    Generates customer-level billing invoices and subscription-level invoice lines.

    Inputs
    ------
    data/raw/billing/billing_subscriptions.csv
    data/raw/billing/billing_subscription_events.csv

    Outputs
    -------
    data/raw/billing/billing_invoices.csv
    data/raw/billing/billing_invoice_lines.csv
    """

    header_filename = "billing_invoices.csv"
    lines_filename = "billing_invoice_lines.csv"

    REQUIRED_SUBSCRIPTION_COLUMNS = {
        "subscription_id",
        "customer_id",
        "product_id",
        "contract_start_date",
        "contract_end_date",
        "contract_term_months",
        "billing_frequency",
        "payment_terms",
        "mrr_local",
        "mrr_gbp",
        "arr_local",
        "arr_gbp",
        "currency",
        "source_system",
        "acquisition_source",
        "is_defect_flag",
        "defect_type",
    }

    REQUIRED_EVENT_COLUMNS = {
        "subscription_id",
        "customer_id",
        "event_date",
        "event_sequence",
        "event_type",
        "event_reason",
        "new_mrr_local",
        "new_mrr_gbp",
        "new_arr_local",
        "new_arr_gbp",
        "currency",
        "is_defect_flag",
        "defect_type",
    }

    HEADER_COLUMNS = [
        "invoice_pk",
        "invoice_id",
        "customer_id",
        "invoice_date",
        "billing_period_start",
        "billing_period_end",
        "due_date",
        "payment_terms",
        "invoice_status",
        "currency",
        "subtotal_local",
        "tax_rate",
        "tax_amount_local",
        "total_local",
        "subtotal_gbp",
        "tax_amount_gbp",
        "total_gbp",
        "source_system",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    LINE_COLUMNS = [
        "invoice_line_pk",
        "invoice_line_id",
        "invoice_id",
        "subscription_id",
        "customer_id",
        "product_id",
        "line_type",
        "service_period_start",
        "service_period_end",
        "billing_frequency",
        "quantity",
        "unit_price_local",
        "line_amount_local",
        "unit_price_gbp",
        "line_amount_gbp",
        "currency",
        "revenue_category",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    VALID_BILLING_FREQUENCIES = {"Monthly", "Annual"}

    VALID_INVOICE_STATUSES = {
        "Issued",
        "Open",
        "Overdue",
        "Written Off",
        "Voided",
    }

    VALID_CURRENCIES = {"GBP", "EUR", "USD", "SGD", "AUD", "CAD"}

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.rng = np.random.default_rng(self.seed + 900)

        self.rules = BillingInvoiceRules()
        self.defect_rates = BillingInvoiceDefectRates()

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pk(value: str) -> str:
        """Generate deterministic MD5 surrogate key."""
        return hashlib.md5(value.strip().upper().encode("utf-8")).hexdigest()

    @staticmethod
    def _normalise_bool_int(value: object, default: int = 0) -> int:
        """Normalize common boolean/integer/string flags into 0/1."""
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
    def _round_money(value: float) -> float:
        """Stable financial rounding."""
        return round(float(value), 2)

    @staticmethod
    def _validate_input_columns(
        df: pd.DataFrame,
        required_columns: set[str],
        dataset_name: str,
    ) -> None:
        """Validate required columns exist."""
        missing_columns = required_columns.difference(df.columns)

        if missing_columns:
            raise ValueError(
                f"{dataset_name} is missing required columns: "
                f"{sorted(missing_columns)}"
            )

    def _get_tax_rate(self, currency: str) -> float:
        """Apply simplified regional B2B SaaS tax framework."""
        currency = str(currency).upper()

        if currency == "GBP":
            return 0.20

        if currency == "EUR":
            return 0.19

        return 0.00

    def _get_mismatched_valid_currency(self, current_currency: str) -> str:
        """Return a different valid system currency for CURRENCY_MISMATCH defects."""
        current_currency = str(current_currency).upper()
        valid_choices = sorted(c for c in self.VALID_CURRENCIES if c != current_currency)
        if not valid_choices:
            return "USD"
        return str(self.rng.choice(valid_choices))

    def _calculate_due_date(
        self,
        invoice_date: pd.Timestamp,
        payment_terms: str,
    ) -> pd.Timestamp:
        """Calculate due date from payment terms."""
        terms = str(payment_terms).strip().lower()

        if "receipt" in terms:
            return invoice_date

        if "90" in terms:
            return invoice_date + pd.Timedelta(days=90)

        if "60" in terms:
            return invoice_date + pd.Timedelta(days=60)

        if "30" in terms:
            return invoice_date + pd.Timedelta(days=30)

        return invoice_date + pd.Timedelta(days=30)

    def _get_invoice_status(
        self,
        invoice_date: pd.Timestamp,
        due_date: pd.Timestamp,
    ) -> str:
        """
        Assign invoice lifecycle status.

        Payments will later provide settlement detail. This status is only the
        invoice document state at source-system level.
        """
        current_date = pd.Timestamp(self.rules.end_date)
        days_past_due = (current_date - due_date).days

        if invoice_date > current_date:
            return "Issued"

        if days_past_due < 0:
            return "Issued"

        if days_past_due <= 30:
            return "Open"

        return str(
            self.rng.choice(
                ["Open", "Overdue", "Written Off"],
                p=[0.18, 0.80, 0.02],
            )
        )

    # ------------------------------------------------------------------
    # Loading and preparation
    # ------------------------------------------------------------------

    def _load_dependencies(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Load subscriptions and subscription events."""
        billing_dir = get_raw_data_path("billing")

        subscriptions_path = billing_dir / "billing_subscriptions.csv"
        events_path = billing_dir / "billing_subscription_events.csv"

        if not subscriptions_path.exists():
            raise FileNotFoundError(
                f"billing_subscriptions.csv not found at: {subscriptions_path}. "
                "Run the subscription generator first."
            )

        if not events_path.exists():
            raise FileNotFoundError(
                f"billing_subscription_events.csv not found at: {events_path}. "
                "Run the subscription event generator first."
            )

        subscriptions_df = pd.read_csv(subscriptions_path)
        events_df = pd.read_csv(events_path)

        self._validate_input_columns(
            df=subscriptions_df,
            required_columns=self.REQUIRED_SUBSCRIPTION_COLUMNS,
            dataset_name="billing_subscriptions.csv",
        )

        self._validate_input_columns(
            df=events_df,
            required_columns=self.REQUIRED_EVENT_COLUMNS,
            dataset_name="billing_subscription_events.csv",
        )

        subscriptions_df = self._prepare_subscriptions(subscriptions_df)
        events_df = self._prepare_events(events_df)

        logger.info(
            "Loaded invoice dependencies: %s subscriptions, %s subscription events.",
            f"{len(subscriptions_df):,}",
            f"{len(events_df):,}",
        )

        return subscriptions_df, events_df

    def _prepare_subscriptions(self, subscriptions_df: pd.DataFrame) -> pd.DataFrame:
        """Normalize subscriptions before invoice generation."""
        df = subscriptions_df.copy()

        if df.empty:
            raise ValueError("billing_subscriptions.csv is empty.")

        df["subscription_id"] = df["subscription_id"].astype(str)
        df["customer_id"] = df["customer_id"].astype(str)
        df["product_id"] = df["product_id"].astype(str)
        df["billing_frequency"] = df["billing_frequency"].astype(str)
        df["payment_terms"] = df["payment_terms"].fillna("Net 30").astype(str)
        df["currency"] = df["currency"].astype(str).str.upper()
        df["source_system"] = df["source_system"].fillna("unknown").astype(str)
        df["acquisition_source"] = df["acquisition_source"].fillna("unknown").astype(str)

        df["contract_start_date"] = pd.to_datetime(
            df["contract_start_date"],
            errors="coerce",
        )

        df["contract_end_date"] = pd.to_datetime(
            df["contract_end_date"],
            errors="coerce",
        )

        if df["contract_start_date"].isna().any():
            bad_count = int(df["contract_start_date"].isna().sum())
            raise ValueError(
                f"billing_subscriptions.csv contains {bad_count:,} invalid contract_start_date values."
            )

        for column in ["mrr_local", "mrr_gbp", "arr_local", "arr_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

            if df[column].isna().any():
                bad_count = int(df[column].isna().sum())
                raise ValueError(
                    f"billing_subscriptions.csv contains {bad_count:,} invalid {column} values."
                )

        df["contract_term_months"] = pd.to_numeric(
            df["contract_term_months"],
            errors="coerce",
        ).fillna(12).astype(int)

        df.loc[df["contract_term_months"] <= 0, "contract_term_months"] = 12

        invalid_frequencies = set(df["billing_frequency"].dropna().unique()).difference(
            self.VALID_BILLING_FREQUENCIES
        )

        if invalid_frequencies:
            raise ValueError(
                f"Invalid billing_frequency values in billing_subscriptions.csv: "
                f"{sorted(invalid_frequencies)}"
            )

        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )

        return df

    def _prepare_events(self, events_df: pd.DataFrame) -> pd.DataFrame:
        """Normalize subscription events before invoice generation."""
        df = events_df.copy()

        if df.empty:
            raise ValueError("billing_subscription_events.csv is empty.")

        df["subscription_id"] = df["subscription_id"].astype(str)
        df["customer_id"] = df["customer_id"].astype(str)
        df["event_type"] = df["event_type"].astype(str).str.lower()
        df["event_reason"] = df["event_reason"].fillna("unknown").astype(str)
        df["currency"] = df["currency"].astype(str).str.upper()

        df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")

        if df["event_date"].isna().any():
            bad_count = int(df["event_date"].isna().sum())
            raise ValueError(
                f"billing_subscription_events.csv contains {bad_count:,} invalid event_date values."
            )

        df["event_sequence"] = pd.to_numeric(
            df["event_sequence"],
            errors="coerce",
        ).fillna(0).astype(int)

        for column in ["new_mrr_local", "new_mrr_gbp", "new_arr_local", "new_arr_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

            if df[column].isna().any():
                bad_count = int(df[column].isna().sum())
                raise ValueError(
                    f"billing_subscription_events.csv contains {bad_count:,} invalid {column} values."
                )

        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )

        return df

    # ------------------------------------------------------------------
    # Billing logic
    # ------------------------------------------------------------------

    def _is_subscription_due(
        self,
        subscription: pd.Series,
        invoice_date: pd.Timestamp,
    ) -> bool:
        """Return whether a subscription should be billed on this bill-run date."""
        start_date = pd.Timestamp(subscription["contract_start_date"])
        frequency = str(subscription["billing_frequency"])

        if invoice_date < start_date.replace(day=1):
            return False

        if frequency == "Monthly":
            return True

        if frequency == "Annual":
            months_since_start = (
                (invoice_date.year - start_date.year) * 12
                + (invoice_date.month - start_date.month)
            )

            return months_since_start >= 0 and months_since_start % 12 == 0

        return False

    def _get_latest_clean_event(
        self,
        clean_events_df: pd.DataFrame,
        subscription_id: str,
        invoice_date: pd.Timestamp,
    ) -> Optional[pd.Series]:
        """Return latest clean subscription event on or before invoice date."""
        relevant_events = clean_events_df[
            (clean_events_df["subscription_id"] == subscription_id)
            & (clean_events_df["event_date"] <= invoice_date)
        ]

        if relevant_events.empty:
            return None

        return relevant_events.sort_values(
            ["event_date", "event_sequence"],
            ascending=[True, True],
        ).iloc[-1]

    def _get_service_period_end(
        self,
        invoice_date: pd.Timestamp,
        billing_frequency: str,
        term_months: int,
    ) -> pd.Timestamp:
        """Return invoice service period end date."""
        if billing_frequency == "Monthly":
            return invoice_date + relativedelta(months=1) - pd.Timedelta(days=1)

        return invoice_date + relativedelta(months=12) - pd.Timedelta(days=1)

    def _build_invoice_line(
        self,
        line_id: str,
        invoice_id: str,
        subscription: pd.Series,
        latest_event: pd.Series,
        invoice_date: pd.Timestamp,
    ) -> dict:
        """Build a clean invoice line from subscription and latest event state."""
        billing_frequency = str(subscription["billing_frequency"])
        term_months = int(subscription["contract_term_months"])

        mrr_local = float(latest_event["new_mrr_local"])
        mrr_gbp = float(latest_event["new_mrr_gbp"])
        arr_local = float(latest_event["new_arr_local"])
        arr_gbp = float(latest_event["new_arr_gbp"])

        if billing_frequency == "Monthly":
            quantity = 1
            line_amount_local = mrr_local
            line_amount_gbp = mrr_gbp
            unit_price_local = mrr_local
            unit_price_gbp = mrr_gbp
        else:
            quantity = 12
            line_amount_local = arr_local
            line_amount_gbp = arr_gbp
            unit_price_local = mrr_local
            unit_price_gbp = mrr_gbp

        line_type = (
            "Legacy Subscription"
            if str(subscription["acquisition_source"]) == "DataPulse Analytics"
            else "Recurring SaaS"
        )

        service_period_end = self._get_service_period_end(
            invoice_date=invoice_date,
            billing_frequency=billing_frequency,
            term_months=term_months,
        )

        return {
            "invoice_line_pk": self._generate_pk(f"{line_id}_{invoice_id}"),
            "invoice_line_id": line_id,
            "invoice_id": invoice_id,
            "subscription_id": str(subscription["subscription_id"]),
            "customer_id": str(subscription["customer_id"]),
            "product_id": str(subscription["product_id"]),
            "line_type": line_type,
            "service_period_start": invoice_date.strftime("%Y-%m-%d"),
            "service_period_end": service_period_end.strftime("%Y-%m-%d"),
            "billing_frequency": billing_frequency,
            "quantity": quantity,
            "unit_price_local": self._round_money(unit_price_local),
            "line_amount_local": self._round_money(line_amount_local),
            "unit_price_gbp": self._round_money(unit_price_gbp),
            "line_amount_gbp": self._round_money(line_amount_gbp),
            "currency": str(subscription["currency"]),
            "revenue_category": "Subscription Revenue",
            "is_defect_flag": False,
            "defect_type": None,
            "created_at": invoice_date.strftime("%Y-%m-%d"),
            "updated_at": invoice_date.strftime("%Y-%m-%d"),
        }

    def _build_invoice_header(
        self,
        invoice_id: str,
        customer_id: str,
        currency: str,
        invoice_date: pd.Timestamp,
        customer_lines: list[dict],
        payment_terms: str,
        source_system: str,
    ) -> dict:
        """Build clean invoice header from invoice lines."""
        subtotal_local = self._round_money(
            sum(float(line["line_amount_local"]) for line in customer_lines)
        )
        subtotal_gbp = self._round_money(
            sum(float(line["line_amount_gbp"]) for line in customer_lines)
        )

        tax_rate = self._get_tax_rate(currency)
        tax_amount_local = self._round_money(subtotal_local * tax_rate)
        tax_amount_gbp = self._round_money(subtotal_gbp * tax_rate)

        total_local = self._round_money(subtotal_local + tax_amount_local)
        total_gbp = self._round_money(subtotal_gbp + tax_amount_gbp)

        due_date = self._calculate_due_date(invoice_date, payment_terms)

        billing_period_end = max(
            pd.to_datetime(line["service_period_end"]) for line in customer_lines
        )

        return {
            "invoice_pk": self._generate_pk(invoice_id),
            "invoice_id": invoice_id,
            "customer_id": str(customer_id),
            "invoice_date": invoice_date.strftime("%Y-%m-%d"),
            "billing_period_start": invoice_date.strftime("%Y-%m-%d"),
            "billing_period_end": billing_period_end.strftime("%Y-%m-%d"),
            "due_date": due_date.strftime("%Y-%m-%d"),
            "payment_terms": payment_terms,
            "invoice_status": self._get_invoice_status(invoice_date, due_date),
            "currency": str(currency),
            "subtotal_local": subtotal_local,
            "tax_rate": tax_rate,
            "tax_amount_local": tax_amount_local,
            "total_local": total_local,
            "subtotal_gbp": subtotal_gbp,
            "tax_amount_gbp": tax_amount_gbp,
            "total_gbp": total_gbp,
            "source_system": source_system,
            "is_defect_flag": False,
            "defect_type": None,
            "created_at": invoice_date.strftime("%Y-%m-%d"),
            "updated_at": invoice_date.strftime("%Y-%m-%d"),
        }

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Generate invoice headers and invoice lines."""
        logger.info("Generating Billing Invoices and Invoice Lines...")
        subscriptions_df, events_df = self._load_dependencies()

        # Normal invoice generation uses only clean event history.
        clean_events_df = events_df[events_df["is_defect_flag"] == 0].copy()

        bill_months = pd.date_range(
            start=pd.Timestamp(self.rules.start_date),
            end=pd.Timestamp(self.rules.end_date),
            freq="MS",
        )

        header_records: list[dict] = []
        line_records: list[dict] = []
        invoice_counter = 1
        line_counter = 1

        logger.info(
            "Running monthly invoice bill runs from %s to %s.",
            self.rules.start_date,
            self.rules.end_date,
        )

        for invoice_date in bill_months:
            active_subs_pool = subscriptions_df[
                subscriptions_df["contract_start_date"] <= invoice_date
            ].copy()

            if active_subs_pool.empty:
                continue

            # One invoice header per customer + currency + bill-run date.
            for (customer_id, currency), customer_subs in active_subs_pool.groupby(
                ["customer_id", "currency"]
            ):
                customer_lines: list[dict] = []

                # Choose stable header-level attributes from the customer/currency group.
                sample_sub = customer_subs.iloc[0]
                payment_terms = str(sample_sub["payment_terms"])
                source_system = str(sample_sub["source_system"])
                invoice_id = f"INV-{invoice_date.year}-{invoice_counter:08d}"

                for _, subscription in customer_subs.iterrows():
                    if not self._is_subscription_due(subscription, invoice_date):
                        continue

                    latest_event = self._get_latest_clean_event(
                        clean_events_df=clean_events_df,
                        subscription_id=str(subscription["subscription_id"]),
                        invoice_date=invoice_date,
                    )

                    if latest_event is None:
                        continue

                    # Terminal event state means no further regular billing.
                    if str(latest_event["event_type"]).lower() in {"churn", "pause"}:
                        continue

                    mrr_local = float(latest_event["new_mrr_local"])
                    mrr_gbp = float(latest_event["new_mrr_gbp"])

                    if mrr_local <= 0 or mrr_gbp <= 0:
                        continue

                    line_id = f"INV-LN-{line_counter:09d}"
                    line_counter += 1

                    customer_lines.append(
                        self._build_invoice_line(
                            line_id=line_id,
                            invoice_id=invoice_id,
                            subscription=subscription,
                            latest_event=latest_event,
                            invoice_date=invoice_date,
                        )
                    )

                if not customer_lines:
                    continue

                header_record = self._build_invoice_header(
                    invoice_id=invoice_id,
                    customer_id=str(customer_id),
                    currency=str(currency),
                    invoice_date=invoice_date,
                    customer_lines=customer_lines,
                    payment_terms=payment_terms,
                    source_system=source_system,
                )

                header_records.append(header_record)
                line_records.extend(customer_lines)
                invoice_counter += 1

        headers_df = pd.DataFrame(header_records)
        lines_df = pd.DataFrame(line_records)

        headers_df, lines_df = self._inject_audit_traps(
            headers_df=headers_df,
            lines_df=lines_df,
            events_df=events_df,
            subscriptions_df=subscriptions_df,
            starting_invoice_counter=invoice_counter,
            starting_line_counter=line_counter,
        )

        headers_df, lines_df = self._finalise_dataframes(headers_df, lines_df)
        self._validate_output(headers_df, lines_df, subscriptions_df)
        self._log_output_review(headers_df, lines_df)

        logger.info(
            "Generated %s invoice headers and %s invoice lines.",
            f"{len(headers_df):,}",
            f"{len(lines_df):,}",
        )

        return headers_df, lines_df

    # ------------------------------------------------------------------
    # Defect injection
    # ------------------------------------------------------------------

    def _sample_clean_indices(
        self,
        df: pd.DataFrame,
        sample_size: int,
    ) -> np.ndarray:
        """Sample indices from clean rows only."""
        if sample_size <= 0 or df.empty:
            return np.array([], dtype=int)

        clean_indices = df.index[df["is_defect_flag"].astype(bool) == False]
        if len(clean_indices) == 0:
            return np.array([], dtype=int)

        sample_size = min(sample_size, len(clean_indices))
        return self.rng.choice(clean_indices, size=sample_size, replace=False)

    def _sample_clean_header_indices_without_defective_lines(
        self,
        headers_df: pd.DataFrame,
        lines_df: pd.DataFrame,
        sample_size: int,
    ) -> np.ndarray:
        """Sample clean header rows whose invoice has no defective lines."""
        if sample_size <= 0 or headers_df.empty:
            return np.array([], dtype=int)

        defective_line_invoice_ids = set(
            lines_df.loc[
                lines_df["is_defect_flag"].astype(bool),
                "invoice_id",
            ].astype(str)
        )

        eligible_headers = headers_df[
            (headers_df["is_defect_flag"].astype(bool) == False)
            & (~headers_df["invoice_id"].astype(str).isin(defective_line_invoice_ids))
        ]

        if eligible_headers.empty:
            return np.array([], dtype=int)

        sample_size = min(sample_size, len(eligible_headers))
        return self.rng.choice(eligible_headers.index, size=sample_size, replace=False)

    def _inject_audit_traps(
        self,
        headers_df: pd.DataFrame,
        lines_df: pd.DataFrame,
        events_df: pd.DataFrame,
        subscriptions_df: pd.DataFrame,
        starting_invoice_counter: int,
        starting_line_counter: int,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Inject controlled invoice and invoice-line defects without stacking."""
        logger.info("Injecting invoice audit traps.")
        if headers_df.empty or lines_df.empty:
            return headers_df, lines_df

        base_header_count = len(headers_df)
        base_line_count = len(lines_df)

        # -----------------------------------------------------------------
        # 1. DUPLICATE_INVOICE (Independent duplication)
        # -----------------------------------------------------------------
        duplicate_count = int(base_header_count * self.defect_rates.duplicate_invoice)
        duplicate_indices = self._sample_clean_indices(headers_df, duplicate_count)

        duplicate_headers: list[dict] = []
        duplicate_lines: list[dict] = []
        invoice_counter = starting_invoice_counter
        line_counter = starting_line_counter

        for index in duplicate_indices:
            original_header = headers_df.loc[index].copy()
            original_invoice_id = str(original_header["invoice_id"])

            invoice_counter += 1
            duplicate_invoice_id = f"INV-DUP-{invoice_counter:08d}"

            duplicate_header = original_header.to_dict()
            duplicate_header["invoice_id"] = duplicate_invoice_id
            duplicate_header["invoice_pk"] = self._generate_pk(duplicate_invoice_id)
            duplicate_header["is_defect_flag"] = True
            duplicate_header["defect_type"] = "DUPLICATE_INVOICE"
            duplicate_headers.append(duplicate_header)

            matching_lines = lines_df[lines_df["invoice_id"] == original_invoice_id]
            for _, line in matching_lines.iterrows():
                line_counter += 1
                duplicate_line_id = f"INV-LN-DUP-{line_counter:09d}"
                duplicate_line = line.to_dict()
                duplicate_line["invoice_id"] = duplicate_invoice_id
                duplicate_line["invoice_line_id"] = duplicate_line_id
                duplicate_line["invoice_line_pk"] = self._generate_pk(
                    f"{duplicate_line_id}_{duplicate_invoice_id}"
                )
                duplicate_line["is_defect_flag"] = True
                duplicate_line["defect_type"] = "DUPLICATE_INVOICE"
                duplicate_lines.append(duplicate_line)

        if duplicate_headers:
            headers_df = pd.concat([headers_df, pd.DataFrame(duplicate_headers)], ignore_index=True)
        if duplicate_lines:
            lines_df = pd.concat([lines_df, pd.DataFrame(duplicate_lines)], ignore_index=True)

        # -----------------------------------------------------------------
        # 2. Header-Level Defects (Safely isolated using helper)
        # -----------------------------------------------------------------

        # A. TAX_CALCULATION_ERROR
        tax_count = int(base_header_count * self.defect_rates.tax_calculation_error)
        tax_indices = self._sample_clean_header_indices_without_defective_lines(
            headers_df=headers_df,
            lines_df=lines_df,
            sample_size=tax_count,
        )
        if len(tax_indices) > 0:
            local_delta = 45.50
            sub_local = pd.to_numeric(headers_df.loc[tax_indices, "subtotal_local"], errors="coerce").fillna(0)
            sub_gbp = pd.to_numeric(headers_df.loc[tax_indices, "subtotal_gbp"], errors="coerce").fillna(0)
            
            gbp_ratio = np.where(sub_local > 0, sub_gbp / sub_local, 1.00)
            gbp_delta = np.round(local_delta * gbp_ratio, 2)

            headers_df.loc[tax_indices, "tax_amount_local"] = headers_df.loc[tax_indices, "tax_amount_local"] + local_delta
            headers_df.loc[tax_indices, "total_local"] = headers_df.loc[tax_indices, "total_local"] + local_delta
            headers_df.loc[tax_indices, "tax_amount_gbp"] = headers_df.loc[tax_indices, "tax_amount_gbp"] + gbp_delta
            headers_df.loc[tax_indices, "total_gbp"] = headers_df.loc[tax_indices, "total_gbp"] + gbp_delta

            headers_df.loc[tax_indices, "is_defect_flag"] = True
            headers_df.loc[tax_indices, "defect_type"] = "TAX_CALCULATION_ERROR"

        # B. PAYMENT_TERM_MISMATCH
        pt_count = int(base_header_count * self.defect_rates.payment_term_mismatch)
        pt_indices = self._sample_clean_header_indices_without_defective_lines(
            headers_df=headers_df,
            lines_df=lines_df,
            sample_size=pt_count,
        )
        if len(pt_indices) > 0:
            bad_due_dates = (
                pd.to_datetime(headers_df.loc[pt_indices, "invoice_date"])
                - pd.Timedelta(days=5)
            )
            headers_df.loc[pt_indices, "due_date"] = bad_due_dates.dt.strftime("%Y-%m-%d")
            headers_df.loc[pt_indices, "is_defect_flag"] = True
            headers_df.loc[pt_indices, "defect_type"] = "PAYMENT_TERM_MISMATCH"

        # C. ZERO_VALUE_INVOICE
        zero_count = int(base_header_count * self.defect_rates.zero_value_invoice)
        zero_indices = self._sample_clean_header_indices_without_defective_lines(
            headers_df=headers_df,
            lines_df=lines_df,
            sample_size=zero_count,
        )
        if len(zero_indices) > 0:
            money_cols = ["subtotal_local", "tax_amount_local", "total_local", "subtotal_gbp", "tax_amount_gbp", "total_gbp"]
            headers_df.loc[zero_indices, money_cols] = 0.0
            headers_df.loc[zero_indices, "is_defect_flag"] = True
            headers_df.loc[zero_indices, "defect_type"] = "ZERO_VALUE_INVOICE"

        # D. CURRENCY_MISMATCH
        curr_count = int(base_header_count * self.defect_rates.currency_mismatch)
        curr_indices = self._sample_clean_header_indices_without_defective_lines(
            headers_df=headers_df,
            lines_df=lines_df,
            sample_size=curr_count,
        )
        if len(curr_indices) > 0:
            for index in curr_indices:
                headers_df.at[index, "currency"] = self._get_mismatched_valid_currency(
                    headers_df.at[index, "currency"]
                )
            headers_df.loc[curr_indices, "is_defect_flag"] = True
            headers_df.loc[curr_indices, "defect_type"] = "CURRENCY_MISMATCH"

        # -----------------------------------------------------------------
        # E. INVOICE_AFTER_CHURN
        # -----------------------------------------------------------------
        churn_count = int(base_header_count * self.defect_rates.invoice_after_churn)
        if churn_count > 0:
            clean_churn_events = events_df[
                (events_df["is_defect_flag"] == 0)
                & (events_df["event_type"].str.lower() == "churn")
            ].copy()

            if not clean_churn_events.empty:
                churn_sample_size = min(churn_count, len(clean_churn_events))
                sampled_churns = clean_churn_events.sample(
                    n=churn_sample_size, 
                    random_state=self.seed + 950
                )

                post_churn_headers = []
                post_churn_lines = []

                for _, churn_event in sampled_churns.iterrows():
                    sub_id = str(churn_event["subscription_id"])
                    cust_id = str(churn_event["customer_id"])
                    curr_curr = str(churn_event["currency"])
                    churn_date = pd.Timestamp(churn_event["event_date"])

                    # Generate an invoice date 1 month after the official churn event occurred
                    bad_invoice_date = churn_date + relativedelta(months=1)
                    bad_invoice_date = bad_invoice_date.replace(day=1)

                    bad_invoice_date = max(
                        bad_invoice_date,
                        pd.Timestamp(self.rules.start_date),
                    )

                    if bad_invoice_date > pd.Timestamp(self.rules.end_date):
                        continue

                    matching_subs = subscriptions_df[subscriptions_df["subscription_id"] == sub_id]
                    if matching_subs.empty:
                        continue
                    sub_row = matching_subs.iloc[0]

                    invoice_counter += 1
                    bad_invoice_id = f"INV-CHURN-{invoice_counter:08d}"

                    line_counter += 1
                    bad_line_id = f"INV-LN-CHURN-{line_counter:09d}"

                    # Reconstruct mock service periods
                    srv_end = self._get_service_period_end(bad_invoice_date, str(sub_row["billing_frequency"]), 12)

                    # Reconstruct amount structure based on billing frequency
                    billing_frequency = str(sub_row["billing_frequency"])

                    if billing_frequency == "Annual":
                        quantity = 12
                        line_amt_local = self._round_money(float(sub_row["arr_local"]))
                        line_amt_gbp = self._round_money(float(sub_row["arr_gbp"]))
                        unit_price_local = self._round_money(float(sub_row["mrr_local"]))
                        unit_price_gbp = self._round_money(float(sub_row["mrr_gbp"]))
                    else:
                        quantity = 1
                        line_amt_local = self._round_money(float(sub_row["mrr_local"]))
                        line_amt_gbp = self._round_money(float(sub_row["mrr_gbp"]))
                        unit_price_local = line_amt_local
                        unit_price_gbp = line_amt_gbp

                    line_rec = {
                        "invoice_line_pk": self._generate_pk(f"{bad_line_id}_{bad_invoice_id}"),
                        "invoice_line_id": bad_line_id,
                        "invoice_id": bad_invoice_id,
                        "subscription_id": sub_id,
                        "customer_id": cust_id,
                        "product_id": str(sub_row["product_id"]),
                        "line_type": "Recurring SaaS",
                        "service_period_start": bad_invoice_date.strftime("%Y-%m-%d"),
                        "service_period_end": srv_end.strftime("%Y-%m-%d"),
                        "billing_frequency": str(sub_row["billing_frequency"]),
                        "quantity": 1,
                        "unit_price_local": line_amt_local,
                        "line_amount_local": line_amt_local,
                        "unit_price_gbp": line_amt_gbp,
                        "line_amount_gbp": line_amt_gbp,
                        "currency": curr_curr,
                        "revenue_category": "Subscription Revenue",
                        "is_defect_flag": True,
                        "defect_type": "INVOICE_AFTER_CHURN",
                        "created_at": bad_invoice_date.strftime("%Y-%m-%d"),
                        "updated_at": bad_invoice_date.strftime("%Y-%m-%d"),
                        "quantity": quantity,
                        "unit_price_local": unit_price_local,
                        "line_amount_local": line_amt_local,
                        "unit_price_gbp": unit_price_gbp,
                        "line_amount_gbp": line_amt_gbp,
                    }
                    post_churn_lines.append(line_rec)

                    # Compute Header financial aggregates
                    t_rate = self._get_tax_rate(curr_curr)
                    tax_loc = self._round_money(line_amt_local * t_rate)
                    tax_gbp = self._round_money(line_amt_gbp * t_rate)
                    due_dt = self._calculate_due_date(bad_invoice_date, str(sub_row["payment_terms"]))

                    head_rec = {
                        "invoice_pk": self._generate_pk(bad_invoice_id),
                        "invoice_id": bad_invoice_id,
                        "customer_id": cust_id,
                        "invoice_date": bad_invoice_date.strftime("%Y-%m-%d"),
                        "billing_period_start": bad_invoice_date.strftime("%Y-%m-%d"),
                        "billing_period_end": srv_end.strftime("%Y-%m-%d"),
                        "due_date": due_dt.strftime("%Y-%m-%d"),
                        "payment_terms": str(sub_row["payment_terms"]),
                        "invoice_status": self._get_invoice_status(bad_invoice_date, due_dt),
                        "currency": curr_curr,
                        "subtotal_local": line_amt_local,
                        "tax_rate": t_rate,
                        "tax_amount_local": tax_loc,
                        "total_local": self._round_money(line_amt_local + tax_loc),
                        "subtotal_gbp": line_amt_gbp,
                        "tax_amount_gbp": tax_gbp,
                        "total_gbp": self._round_money(line_amt_gbp + tax_gbp),
                        "source_system": str(sub_row["source_system"]),
                        "is_defect_flag": True,
                        "defect_type": "INVOICE_AFTER_CHURN",
                        "created_at": bad_invoice_date.strftime("%Y-%m-%d"),
                        "updated_at": bad_invoice_date.strftime("%Y-%m-%d"),
                    }
                    post_churn_headers.append(head_rec)

                if post_churn_headers:
                    headers_df = pd.concat([headers_df, pd.DataFrame(post_churn_headers)], ignore_index=True)
                if post_churn_lines:
                    lines_df = pd.concat([lines_df, pd.DataFrame(post_churn_lines)], ignore_index=True)

        # -----------------------------------------------------------------
        # 3. Line-Level Defects: ORPHAN_SUBSCRIPTION_LINE (Remains Last)
        # -----------------------------------------------------------------
        clean_header_invoice_ids = set(
            headers_df.loc[headers_df["is_defect_flag"].astype(bool) == False, "invoice_id"].astype(str)
        )
        eligible_orphan_lines = lines_df[
            (lines_df["is_defect_flag"].astype(bool) == False)
            & (lines_df["invoice_id"].astype(str).isin(clean_header_invoice_ids))
        ]

        orphan_line_count = int(base_line_count * self.defect_rates.orphan_subscription_line)
        orphan_line_count = min(orphan_line_count, len(eligible_orphan_lines))

        if orphan_line_count > 0:
            orphan_line_indices = self.rng.choice(eligible_orphan_lines.index, size=orphan_line_count, replace=False)
            lines_df.loc[orphan_line_indices, "subscription_id"] = "SUB-ORPHAN-RECON"
            lines_df.loc[orphan_line_indices, "is_defect_flag"] = True
            lines_df.loc[orphan_line_indices, "defect_type"] = "ORPHAN_SUBSCRIPTION_LINE"

        return headers_df, lines_df

    # ------------------------------------------------------------------
    # Pipeline Finalisation and Output Validation
    # ------------------------------------------------------------------

    def _finalise_dataframes(
        self,
        headers_df: pd.DataFrame,
        lines_df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Enforce standard columns, explicit schemas, formatting rules, and sort orders."""
        headers_df = headers_df.reindex(columns=self.HEADER_COLUMNS)
        lines_df = lines_df.reindex(columns=self.LINE_COLUMNS)

        headers_df["is_defect_flag"] = headers_df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )
        lines_df["is_defect_flag"] = lines_df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )

        headers_df["defect_type"] = headers_df["defect_type"].fillna("")
        lines_df["defect_type"] = lines_df["defect_type"].fillna("")

        headers_df = headers_df.sort_values(["invoice_date", "invoice_id"]).reset_index(drop=True)
        lines_df = lines_df.sort_values(["invoice_id", "invoice_line_id"]).reset_index(drop=True)

        return headers_df, lines_df

    def _validate_output(
        self,
        headers_df: pd.DataFrame,
        lines_df: pd.DataFrame,
        subscriptions_df: pd.DataFrame,
    ) -> None:
        """Perform system assertions checking integrity boundaries."""
        if headers_df.empty or lines_df.empty:
            raise ValueError("Generated output tables cannot be empty.")

        # 1. Base Null checks
        header_nulls = headers_df[["invoice_pk", "invoice_id", "customer_id", "invoice_date"]].isna().sum().sum()
        line_nulls = lines_df[["invoice_line_pk", "invoice_line_id", "invoice_id", "customer_id"]].isna().sum().sum()
        if header_nulls > 0 or line_nulls > 0:
            raise ValueError("Core relational keys cannot contain null values.")

        # 2. Key uniqueness checks
        if headers_df["invoice_id"].duplicated().any():
            dups = headers_df.loc[headers_df["invoice_id"].duplicated(), "invoice_id"].unique()
            raise ValueError(f"Duplicate invoice_id values detected in master ledger: {list(dups[:5])}")

        if headers_df["invoice_pk"].duplicated().any():
            raise ValueError("Surrogate invoice_pk constraints violated via duplicate entries.")

        if lines_df["invoice_line_id"].duplicated().any():
            raise ValueError("Invoice lines contain duplicated surrogate tracking ids.")

        if lines_df["invoice_line_pk"].duplicated().any():
            raise ValueError("Invoice subledger contains duplicated surrogate invoice_line_pk metrics.")

        # 3. Join footprint matching checks
        line_invoice_ids = set(lines_df["invoice_id"].astype(str))
        header_invoice_ids = set(headers_df["invoice_id"].astype(str))
        missing_headers = line_invoice_ids.difference(header_invoice_ids)
        if missing_headers:
            raise ValueError(f"Orphan subledger invoice lines found lacking a structural header join footprint: {list(missing_headers)[:5]}")

        # 4. Status framework validation
        invalid_statuses = set(headers_df["invoice_status"].unique()).difference(self.VALID_INVOICE_STATUSES)
        if invalid_statuses:
            raise ValueError(f"Prohibited invoice transaction status states registered: {invalid_statuses}")

        # 5. Invalid subscription checks restricted strictly to ORPHAN_SUBSCRIPTION_LINE boundaries
        valid_subscription_ids = set(subscriptions_df["subscription_id"].astype(str))
        invalid_subs_mask = ~lines_df["subscription_id"].astype(str).isin(valid_subscription_ids)
        if invalid_subs_mask.any():
            illegal_leaks = lines_df[invalid_subs_mask & (lines_df["defect_type"] != "ORPHAN_SUBSCRIPTION_LINE")]
            if not illegal_leaks.empty:
                raise ValueError(f"Data corruption leak: Invalid subscription_ids mapped outside controlled orphan testing tracks: {list(illegal_leaks['subscription_id'].unique()[:5])}")

            
        # 6. Clean Document Financial Reconciliation Integrity Bounds
        defective_invoice_ids = set(
            headers_df.loc[
                headers_df["is_defect_flag"].astype(bool),
                "invoice_id",
            ].astype(str)
        )

        defective_invoice_ids.update(
            lines_df.loc[
                lines_df["is_defect_flag"].astype(bool),
                "invoice_id",
            ].astype(str)
        )

        clean_headers = headers_df[
            ~headers_df["invoice_id"].astype(str).isin(defective_invoice_ids)
        ].copy()

        clean_lines = lines_df[
            ~lines_df["invoice_id"].astype(str).isin(defective_invoice_ids)
        ].copy()

        if not clean_headers.empty and not clean_lines.empty:
            rolled_subtotals = clean_lines.groupby("invoice_id").agg(
                calculated_subtotal_local=("line_amount_local", "sum"),
                calculated_subtotal_gbp=("line_amount_gbp", "sum"),
            )

            reconciled_df = clean_headers.merge(
                rolled_subtotals,
                on="invoice_id",
                how="left",
            )

            reconciled_df["calculated_subtotal_local"] = (
                reconciled_df["calculated_subtotal_local"].fillna(0)
            )
            reconciled_df["calculated_subtotal_gbp"] = (
                reconciled_df["calculated_subtotal_gbp"].fillna(0)
            )

            mismatch_subtotals_local = (
                reconciled_df["subtotal_local"] - reconciled_df["calculated_subtotal_local"]
            ).abs() > 0.05

            mismatch_subtotals_gbp = (
                reconciled_df["subtotal_gbp"] - reconciled_df["calculated_subtotal_gbp"]
            ).abs() > 0.05

            if mismatch_subtotals_local.any() or mismatch_subtotals_gbp.any():
                raise ValueError(
                    "Reconciliation failed: Clean document subtotal ledger differences caught. "
                    f"Local breaks: {int(mismatch_subtotals_local.sum()):,}; "
                    f"GBP breaks: {int(mismatch_subtotals_gbp.sum()):,}."
                )

            calculated_tax_local = (
                reconciled_df["subtotal_local"] * reconciled_df["tax_rate"]
            ).round(2)

            calculated_tax_gbp = (
                reconciled_df["subtotal_gbp"] * reconciled_df["tax_rate"]
            ).round(2)

            mismatch_taxes_local = (
                reconciled_df["tax_amount_local"] - calculated_tax_local
            ).abs() > 0.05

            mismatch_taxes_gbp = (
                reconciled_df["tax_amount_gbp"] - calculated_tax_gbp
            ).abs() > 0.05

            if mismatch_taxes_local.any() or mismatch_taxes_gbp.any():
                raise ValueError(
                    "Reconciliation failed: Prohibited tax miscalculations caught inside clean validation subsets. "
                    f"Local breaks: {int(mismatch_taxes_local.sum()):,}; "
                    f"GBP breaks: {int(mismatch_taxes_gbp.sum()):,}."
                )

    def _log_output_review(self, headers_df: pd.DataFrame, lines_df: pd.DataFrame) -> None:
        """Log transactional statistics covering system health."""
        logger.info("----------------------------------")
        logger.info("Invoice Generation Diagnostics")
        logger.info("----------------------------------")
        logger.info("Total Invoice Headers: %d", len(headers_df))
        logger.info("Total Invoice Lines: %d", len(lines_df))
        logger.info(
            "Header Defect Type Counts:\n%s",
            headers_df["defect_type"].value_counts(dropna=False).to_string(),
        )
        logger.info(
            "Line Defect Type Counts:\n%s",
            lines_df["defect_type"].value_counts(dropna=False).to_string(),
        )
        logger.info(
            "Currency counts:\n%s",
            headers_df["currency"].value_counts(dropna=False).to_string(),
        )
        logger.info(
            "Total local amount summary:\n%s",
            headers_df["total_local"].describe().round(2).to_string(),
        )
        logger.info(
            "Total GBP amount summary:\n%s",
            headers_df["total_gbp"].describe().round(2).to_string(),
        )
        logger.info("----------------------------------")

    def save(self, headers_df: pd.DataFrame, lines_df: pd.DataFrame) -> tuple[Path, Path]:
        """Save invoice headers and lines to the billing raw folder."""
        output_dir = get_raw_data_path("billing")
        output_dir.mkdir(parents=True, exist_ok=True)

        header_path = output_dir / self.header_filename
        lines_path = output_dir / self.lines_filename

        headers_df.to_csv(header_path, index=False)
        lines_df.to_csv(lines_path, index=False)

        logger.info("Billing invoice headers saved to %s", header_path)
        logger.info("Billing invoice lines saved to %s", lines_path)

        return header_path, lines_path


def main() -> None:
    """Execute generator entry point."""
    generator = BillingInvoicesGenerator()
    headers_df, lines_df = generator.generate()
    generator.save(headers_df, lines_df)


if __name__ == "__main__":
    main()