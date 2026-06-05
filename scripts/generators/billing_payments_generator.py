"""
billing_payments_generator.py

Project Atlas / Nexus Technologies
Phase 3F - Payments, Cash Receipts & AR Ageing
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("BillingPaymentsGenerator", "generation_execution.log")


@dataclass(frozen=True)
class PaymentGenerationRules:
    start_date: date = date(2023, 1, 1)
    end_date: date = date(2026, 6, 3)
    rounding_tolerance: float = 0.05
    materiality_threshold_gbp: float = 100.00


class BillingPaymentsGenerator:
    REQUIRED_INVOICE_COLUMNS = {
        "invoice_id",
        "customer_id",
        "invoice_date",
        "due_date",
        "payment_terms",
        "invoice_status",
        "currency",
        "total_local",
        "total_gbp",
        "source_system",
        "is_defect_flag",
        "defect_type",
    }

    REQUIRED_CUSTOMER_COLUMNS = {
        "customer_id",
        "customer_segment",
        "is_acquired_customer",
        "acquisition_source",
        "customer_status",
        "region_id",
        "currency_code",
    }

    SCENARIOS = [
        "PAID_ON_TIME",
        "PAID_LATE",
        "PARTIALLY_PAID",
        "UNPAID_OVERDUE",
        "DISPUTED",
        "OVERPAID",
        "UNAPPLIED_CASH",
    ]

    BASE_PROBS = np.array([0.58, 0.22, 0.06, 0.06, 0.04, 0.02, 0.02])

    PAYMENT_COLUMNS = [
        "payment_pk",
        "payment_id",
        "customer_id",
        "payment_date",
        "payment_method",
        "payment_reference",
        "currency",
        "payment_amount_local",
        "payment_amount_gbp",
        "bank_account_region",
        "payment_status",
        "source_system",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    ALLOCATION_COLUMNS = [
        "allocation_pk",
        "allocation_id",
        "payment_id",
        "invoice_id",
        "customer_id",
        "allocation_date",
        "currency",
        "allocated_amount_local",
        "allocated_amount_gbp",
        "allocation_status",
        "source_system",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    AGEING_COLUMNS = [
        "snapshot_pk",
        "snapshot_date",
        "invoice_id",
        "customer_id",
        "invoice_date",
        "due_date",
        "currency",
        "invoice_total_local",
        "invoice_total_gbp",
        "paid_amount_local",
        "paid_amount_gbp",
        "open_amount_local",
        "open_amount_gbp",
        "days_past_due",
        "ageing_bucket",
        "ar_status",
        "collection_status",
        "is_disputed_flag",
        "is_writeoff_candidate_flag",
        "source_system",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    def generate(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Temporary Phase 3F development entry point.

        Builds payment intents, payment records, allocation records and AR ageing
        snapshots. CSV save will be added after validation.
        """
        logger.info("Generating Phase 3F payment intents...")

        invoices_df = self._load_invoices()
        customers_df = self._load_customers()

        enriched_invoices_df = invoices_df.merge(
            customers_df,
            on="customer_id",
            how="left",
        )

        if enriched_invoices_df["customer_segment"].isna().any():
            missing_count = int(enriched_invoices_df["customer_segment"].isna().sum())
            raise ValueError(
                f"Invoice customer enrichment failed for {missing_count:,} invoices."
            )

        intents_df = self._build_payment_intents()

        logger.info(
            "Payment intent generation complete: %s invoice intent rows.",
            f"{len(intents_df):,}",
        )

        payments_df, allocations_df = self._generate_payments_and_allocations(
            intents_df=intents_df,
        )

        ageing_df = self._generate_ageing_snapshot(
            invoices_df=enriched_invoices_df,
            allocations_df=allocations_df,
        )

        self._validate_output(
            invoices_df=enriched_invoices_df,
            payments_df=payments_df,
            allocations_df=allocations_df,
            ageing_df=ageing_df,
        )

        logger.info(
            "Phase 3F smoke test complete: %s payments, %s allocations, %s ageing rows.",
            f"{len(payments_df):,}",
            f"{len(allocations_df):,}",
            f"{len(ageing_df):,}",
        )

        return payments_df, allocations_df, ageing_df
    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed = int(self.config.project.get("random_seed", 42))
        self.rng = np.random.default_rng(self.seed + 1000)
        self.rules = PaymentGenerationRules()

    @staticmethod
    def _validate_columns(
        df: pd.DataFrame,
        required_columns: set[str],
        dataset_name: str,
    ) -> None:
        missing_columns = required_columns.difference(df.columns)

        if missing_columns:
            raise ValueError(
                f"{dataset_name} is missing required columns: {sorted(missing_columns)}"
            )

    def _load_invoices(self) -> pd.DataFrame:
        billing_dir = get_raw_data_path("billing")
        path = billing_dir / "billing_invoices.csv"

        if not path.exists():
            raise FileNotFoundError(
                f"billing_invoices.csv not found at: {path}. "
                "Run BillingInvoicesGenerator first."
            )

        df = pd.read_csv(path)
        self._validate_columns(df, self.REQUIRED_INVOICE_COLUMNS, "billing_invoices.csv")

        df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
        df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
        df["total_local"] = pd.to_numeric(df["total_local"], errors="coerce")
        df["total_gbp"] = pd.to_numeric(df["total_gbp"], errors="coerce")
        df["currency"] = df["currency"].astype(str).str.upper()
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        if df["invoice_date"].isna().any():
            raise ValueError("billing_invoices.csv contains invalid invoice_date values.")

        if df["due_date"].isna().any():
            raise ValueError("billing_invoices.csv contains invalid due_date values.")

        if df["total_gbp"].isna().any() or df["total_local"].isna().any():
            raise ValueError("billing_invoices.csv contains invalid invoice total values.")

        return df

    def _load_customers(self) -> pd.DataFrame:
        billing_dir = get_raw_data_path("billing")
        path = billing_dir / "billing_customers.csv"

        if not path.exists():
            raise FileNotFoundError(
                f"billing_customers.csv not found at: {path}. "
                "Run CustomerGenerator first."
            )

        df = pd.read_csv(path)
        self._validate_columns(df, self.REQUIRED_CUSTOMER_COLUMNS, "billing_customers.csv")

        return df[
            [
                "customer_id",
                "customer_segment",
                "is_acquired_customer",
                "acquisition_source",
                "customer_status",
                "region_id",
                "currency_code",
            ]
        ].copy()

    def _build_payment_intents(self) -> pd.DataFrame:
        invoices = self._load_invoices()
        customers = self._load_customers()

        df = invoices.merge(customers, on="customer_id", how="left")

        if df["customer_segment"].isna().any():
            missing_count = int(df["customer_segment"].isna().sum())
            raise ValueError(
                f"Invoice customer enrichment failed for {missing_count:,} invoices."
            )

        intent_records = []

        for _, row in df.iterrows():
            intent = self._classify_intent(row)
            resolved_intent = self._resolve_intent_to_transaction(pd.Series(intent))
            intent_records.append(resolved_intent)

        intents_df = pd.DataFrame(intent_records)

        logger.info(
            "Distribution of Settlement Scenarios:\n%s",
            intents_df["settlement_scenario"]
            .value_counts(normalize=True)
            .mul(100)
            .round(2)
            .astype(str)
            .add("%")
            .to_string(),
        )

        logger.info(
            "Cash realised flag distribution:\n%s",
            intents_df["cash_realised_flag"]
            .value_counts(dropna=False)
            .to_string(),
        )

        logger.info(
            "Allocation status distribution:\n%s",
            intents_df["allocation_status"]
            .value_counts(dropna=False)
            .to_string(),
        )

        return intents_df

    def _classify_intent(self, row: pd.Series) -> dict:
        probs = self.BASE_PROBS.copy()

        segment = str(row.get("customer_segment", "SMB")).lower()
        is_datapulse = int(row.get("is_acquired_customer", 0)) == 1
        total_gbp = float(row["total_gbp"])
        defect_type = str(row.get("defect_type", ""))
        extract_end_date = pd.Timestamp(self.rules.end_date)

        if pd.Timestamp(row["due_date"]) > extract_end_date:
            scenario = "UNPAID_CURRENT"

        elif abs(total_gbp) <= self.rules.rounding_tolerance:
            scenario = "SETTLED_ZERO_VALUE"

        else:
            probs = self.BASE_PROBS.copy()
            probs = self._apply_segment_modifiers(probs, segment)
            probs = self._apply_invoice_value_modifiers(probs, total_gbp)
            probs = self._apply_datapulse_modifiers(probs, is_datapulse)

            probs = np.maximum(probs, 0.001)
            probs = probs / probs.sum()

            scenario = str(self.rng.choice(self.SCENARIOS, p=probs))
            scenario = self._apply_defect_override(scenario, defect_type)

        return {
            "invoice_id": str(row["invoice_id"]),
            "customer_id": str(row["customer_id"]),
            "customer_segment": str(row["customer_segment"]),
            "is_acquired_customer": int(row.get("is_acquired_customer", 0)),
            "acquisition_source": str(row.get("acquisition_source", "")),
            "invoice_date": row["invoice_date"],
            "due_date": row["due_date"],
            "payment_terms": str(row["payment_terms"]),
            "currency": str(row["currency"]),
            "total_local": float(row["total_local"]),
            "total_gbp": total_gbp,
            "invoice_status": str(row["invoice_status"]),
            "source_system": str(row["source_system"]),
            "invoice_defect_type": defect_type,
            "settlement_scenario": scenario,
        }

    @staticmethod
    def _apply_segment_modifiers(probs: np.ndarray, segment: str) -> np.ndarray:
        probs = probs.copy()

        if segment == "enterprise":
            probs[0] += 0.04  # paid on time
            probs[1] += 0.04  # paid late
            probs[2] -= 0.03  # partially paid
            probs[3] -= 0.04  # unpaid overdue
            probs[4] -= 0.01  # disputed

        elif segment == "mid-market":
            probs[0] += 0.02
            probs[3] -= 0.02

        elif segment == "smb":
            probs[0] -= 0.04
            probs[1] += 0.02
            probs[2] += 0.01
            probs[3] += 0.01

        return probs

    @staticmethod
    def _apply_invoice_value_modifiers(probs: np.ndarray, total_gbp: float) -> np.ndarray:
        probs = probs.copy()

        if total_gbp > 25_000:
            probs[0] -= 0.06
            probs[1] += 0.03
            probs[4] += 0.02
            probs[2] += 0.01

        return probs

    @staticmethod
    def _apply_datapulse_modifiers(
        probs: np.ndarray,
        is_datapulse: bool,
    ) -> np.ndarray:
        probs = probs.copy()

        if is_datapulse:
            probs[0] -= 0.08
            probs[1] += 0.03
            probs[4] += 0.03
            probs[6] += 0.02

        return probs
    
    @staticmethod
    def _round_money(value: float) -> float:
        """Stable financial rounding."""
        return round(float(value), 2)

    def _apply_defect_override(
        self,
        scenario: str,
        defect_type: str,
        ) -> str:
        if defect_type == "ZERO_VALUE_INVOICE":
            return "SETTLED_ZERO_VALUE"

        if defect_type == "DUPLICATE_INVOICE":
            return "DISPUTED"

        if defect_type == "TAX_CALCULATION_ERROR":
            return str(self.rng.choice(["DISPUTED", "PARTIALLY_PAID"], p=[0.70, 0.30]))

        if defect_type == "PAYMENT_TERM_MISMATCH":
            return str(self.rng.choice(["PAID_LATE", "DISPUTED"], p=[0.75, 0.25]))

        if defect_type == "CURRENCY_MISMATCH":
            return str(self.rng.choice(["UNAPPLIED_CASH", "DISPUTED"], p=[0.65, 0.35]))

        if defect_type == "INVOICE_AFTER_CHURN":
            return str(self.rng.choice(["DISPUTED", "UNPAID_OVERDUE"], p=[0.80, 0.20]))

        return scenario

    def _derive_payment_date(
        self,
        row: pd.Series,
        settlement_scenario: str,
        ) -> Optional[pd.Timestamp]:
        invoice_date = pd.Timestamp(row["invoice_date"])
        due_date = pd.Timestamp(row["due_date"])

        if settlement_scenario in {
            "UNPAID_CURRENT",
            "UNPAID_OVERDUE",
            "DISPUTED",
            "SETTLED_ZERO_VALUE",
        }:
            return None

        if settlement_scenario == "PAID_ON_TIME":
            lag_days = int(self.rng.integers(-5, 6))
            payment_date = due_date + pd.Timedelta(days=lag_days)

        elif settlement_scenario == "PAID_LATE":
            lag_days = int(self.rng.integers(6, 46))
            payment_date = due_date + pd.Timedelta(days=lag_days)

        elif settlement_scenario == "PARTIALLY_PAID":
            lag_days = int(self.rng.integers(5, 61))
            payment_date = due_date + pd.Timedelta(days=lag_days)

        elif settlement_scenario in {"OVERPAID", "UNAPPLIED_CASH"}:
            lag_days = int(self.rng.integers(0, 31))
            payment_date = due_date + pd.Timedelta(days=lag_days)

        else:
            return None

        if payment_date < invoice_date:
            payment_date = invoice_date

        return payment_date

    def _derive_payment_amount(
        self,
        row: pd.Series,
        settlement_scenario: str,
        cash_realised_flag: int,
        ) -> tuple[float, float]:
        if cash_realised_flag == 0:
            return 0.00, 0.00

        total_local = float(row["total_local"])
        total_gbp = float(row["total_gbp"])

        if settlement_scenario == "PARTIALLY_PAID":
            payment_factor = float(self.rng.uniform(0.25, 0.85))
            return (
                self._round_money(total_local * payment_factor),
                self._round_money(total_gbp * payment_factor),
            )

        if settlement_scenario == "OVERPAID":
            payment_factor = float(self.rng.uniform(1.05, 1.25))
            return (
                self._round_money(total_local * payment_factor),
                self._round_money(total_gbp * payment_factor),
            )

        if settlement_scenario in {
            "PAID_ON_TIME",
            "PAID_LATE",
            "UNAPPLIED_CASH",
        }:
            return (
                self._round_money(total_local),
                self._round_money(total_gbp),
            )

        return 0.00, 0.00

    @staticmethod
    def _derive_allocation_status(
        settlement_scenario: str,
        cash_realised_flag: int,
        ) -> str:
        if cash_realised_flag == 0:
            return "Not Applicable"

        if settlement_scenario in {"PAID_ON_TIME", "PAID_LATE"}:
            return "Applied"

        if settlement_scenario == "PARTIALLY_PAID":
            return "Partially Applied"

        if settlement_scenario == "OVERPAID":
            return "Over Applied"

        if settlement_scenario == "UNAPPLIED_CASH":
            return "Unapplied"

        return "Not Applicable"

    def _resolve_intent_to_transaction(self, row: pd.Series) -> dict:
        settlement_scenario = str(row["settlement_scenario"])

        derived_payment_date = self._derive_payment_date(
            row=row,
            settlement_scenario=settlement_scenario,
        )

        extract_end_date = pd.Timestamp(self.rules.end_date)

        cash_realised_flag = int(
            derived_payment_date is not None
            and derived_payment_date <= extract_end_date
        )

        payment_amount_local, payment_amount_gbp = self._derive_payment_amount(
            row=row,
            settlement_scenario=settlement_scenario,
            cash_realised_flag=cash_realised_flag,
        )

        allocation_status = self._derive_allocation_status(
            settlement_scenario=settlement_scenario,
            cash_realised_flag=cash_realised_flag,
        )

        payment_date_value = (
            derived_payment_date.strftime("%Y-%m-%d")
            if cash_realised_flag == 1 and derived_payment_date is not None
            else None
        )

        return {
            **row.to_dict(),
            "payment_date": payment_date_value,
            "payment_amount_local": payment_amount_local,
            "payment_amount_gbp": payment_amount_gbp,
            "allocation_status": allocation_status,
            "cash_realised_flag": cash_realised_flag,
        }
    
    @staticmethod
    def _generate_pk(value: str) -> str:
        """Generate deterministic MD5 surrogate key."""
        return hashlib.md5(value.strip().upper().encode("utf-8")).hexdigest()

    def _get_payment_method(self, row: pd.Series) -> str:
        """Assign realistic payment method based on customer/payment profile."""
        segment = str(row.get("customer_segment", "SMB"))

        if segment == "Enterprise":
            return str(
                self.rng.choice(
                    ["Bank Transfer", "Wire", "Direct Debit"],
                    p=[0.55, 0.25, 0.20],
                )
            )

        if segment == "Mid-Market":
            return str(
                self.rng.choice(
                    ["Bank Transfer", "Direct Debit", "Card"],
                    p=[0.50, 0.35, 0.15],
                )
            )

        return str(
            self.rng.choice(
                ["Card", "Direct Debit", "Bank Transfer"],
                p=[0.45, 0.35, 0.20],
            )
        )

    @staticmethod
    def _get_bank_account_region(row: pd.Series) -> str:
        """Map invoice/customer region to simulated receiving bank account."""
        region_id = str(row.get("region_id", "")).upper()
        currency = str(row.get("currency", "")).upper()

        if region_id == "UK" or currency == "GBP":
            return "UK Operating Account"

        if region_id == "US" or currency == "USD":
            return "US Operating Account"

        if region_id == "DE" or currency == "EUR":
            return "EU Operating Account"

        if region_id == "SG" or currency == "SGD":
            return "APAC Operating Account"

        return "Group Treasury Account"

    @staticmethod
    def _derive_payment_status(allocation_status: str) -> str:
        """Map allocation status to bank/payment status."""
        if allocation_status == "Applied":
            return "Fully Applied"

        if allocation_status == "Partially Applied":
            return "Partially Applied"

        if allocation_status == "Unapplied":
            return "Unapplied"

        if allocation_status == "Over Applied":
            return "Fully Applied"

        return "Received"

    def _build_payment_record(
        self,
        row: pd.Series,
        payment_counter: int,
    ) -> dict:
        """Build one billing_payments.csv row from a realised cash intent."""
        payment_id = f"PAY-{payment_counter:09d}"
        payment_date = str(row["payment_date"])
        allocation_status = str(row["allocation_status"])

        return {
            "payment_pk": self._generate_pk(payment_id),
            "payment_id": payment_id,
            "customer_id": str(row["customer_id"]),
            "payment_date": payment_date,
            "payment_method": self._get_payment_method(row),
            "payment_reference": f"RCPT-{payment_date.replace('-', '')}-{payment_counter:09d}",
            "currency": str(row["currency"]),
            "payment_amount_local": self._round_money(float(row["payment_amount_local"])),
            "payment_amount_gbp": self._round_money(float(row["payment_amount_gbp"])),
            "bank_account_region": self._get_bank_account_region(row),
            "payment_status": self._derive_payment_status(allocation_status),
            "source_system": "cash_receipts_module",
            "is_defect_flag": 0,
            "defect_type": "",
            "created_at": payment_date,
            "updated_at": payment_date,
        }

    def _build_allocation_record(
        self,
        row: pd.Series,
        payment_id: str,
        allocation_counter: int,
    ) -> dict:
        """Build one billing_payment_allocations.csv row from a realised cash intent."""
        allocation_id = f"ALLOC-{allocation_counter:09d}"
        allocation_status = str(row["allocation_status"])

        return {
            "allocation_pk": self._generate_pk(f"{allocation_id}_{payment_id}"),
            "allocation_id": allocation_id,
            "payment_id": payment_id,
            "invoice_id": str(row["invoice_id"]),
            "customer_id": str(row["customer_id"]),
            "allocation_date": str(row["payment_date"]),
            "currency": str(row["currency"]),
            "allocated_amount_local": self._round_money(float(row["payment_amount_local"])),
            "allocated_amount_gbp": self._round_money(float(row["payment_amount_gbp"])),
            "allocation_status": allocation_status,
            "source_system": "ar_cash_application_module",
            "is_defect_flag": 0,
            "defect_type": "",
            "created_at": str(row["payment_date"]),
            "updated_at": str(row["payment_date"]),
        }

    def _generate_payments_and_allocations(
        self,
        intents_df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Generate payment and allocation records from resolved payment intents.

        Rules:
        - cash_realised_flag = 1 creates a payment row.
        - Applied / Partially Applied / Over Applied creates an allocation row.
        - Unapplied creates a payment row only.
        - Not Applicable creates neither.
        """
        payment_records: list[dict] = []
        allocation_records: list[dict] = []

        payment_counter = 1
        allocation_counter = 1

        realised_cash_df = intents_df[
            intents_df["cash_realised_flag"].astype(int) == 1
        ].copy()

        for _, intent in realised_cash_df.iterrows():
            payment_record = self._build_payment_record(
                row=intent,
                payment_counter=payment_counter,
            )
            payment_records.append(payment_record)

            allocation_status = str(intent["allocation_status"])

            if allocation_status in {"Applied", "Partially Applied", "Over Applied"}:
                allocation_record = self._build_allocation_record(
                    row=intent,
                    payment_id=payment_record["payment_id"],
                    allocation_counter=allocation_counter,
                )
                allocation_records.append(allocation_record)
                allocation_counter += 1

            payment_counter += 1

        payments_df = pd.DataFrame(payment_records)
        allocations_df = pd.DataFrame(allocation_records)

        payments_df = payments_df.reindex(columns=self.PAYMENT_COLUMNS)
        allocations_df = allocations_df.reindex(columns=self.ALLOCATION_COLUMNS)

        logger.info("Generated payment rows: %s", f"{len(payments_df):,}")
        logger.info("Generated allocation rows: %s", f"{len(allocations_df):,}")

        if not payments_df.empty:
            logger.info(
                "Payment status distribution:\n%s",
                payments_df["payment_status"].value_counts(dropna=False).to_string(),
            )

        if not allocations_df.empty:
            logger.info(
                "Allocation status distribution:\n%s",
                allocations_df["allocation_status"].value_counts(dropna=False).to_string(),
            )

        unapplied_count = int(
            payments_df["payment_status"].eq("Unapplied").sum()
        ) if not payments_df.empty else 0

        logger.info("Unapplied payment count: %s", f"{unapplied_count:,}")

        return payments_df, allocations_df
    
    def _generate_snapshot_dates(self) -> list[pd.Timestamp]:
        """
        Generate monthly AR ageing snapshot dates.

        Uses month-end snapshots plus the final extract date.
        """
        month_ends = pd.date_range(
            start=pd.Timestamp(self.rules.start_date),
            end=pd.Timestamp(self.rules.end_date),
            freq="ME",
        ).to_list()

        extract_end_date = pd.Timestamp(self.rules.end_date)

        if extract_end_date not in month_ends:
            month_ends.append(extract_end_date)

        return sorted(month_ends)

    @staticmethod
    def _derive_ageing_bucket(
        open_amount_gbp: float,
        days_past_due: int,
    ) -> str:
        """Derive AR ageing bucket."""
        if open_amount_gbp < -0.05:
            return "Overpaid"

        if abs(open_amount_gbp) <= 0.05:
            return "Closed"

        if days_past_due <= 0:
            return "Current"

        if days_past_due <= 30:
            return "1-30"

        if days_past_due <= 60:
            return "31-60"

        if days_past_due <= 90:
            return "61-90"

        if days_past_due <= 120:
            return "91-120"

        return "120+"

    @staticmethod
    def _derive_ar_status(
        invoice_status: str,
        open_amount_gbp: float,
    ) -> str:
        """Derive AR status from invoice state and open amount."""
        invoice_status = str(invoice_status)

        if invoice_status == "Voided":
            return "Voided"

        if invoice_status == "Written Off":
            return "Written Off"

        if open_amount_gbp < -0.05:
            return "Overpaid"

        if abs(open_amount_gbp) <= 0.05:
            return "Closed"

        return "Open"

    @staticmethod
    def _is_high_dispute_invoice_defect(defect_type: str) -> bool:
        """Return whether invoice defect type should drive dispute classification."""
        return str(defect_type) in {
            "TAX_CALCULATION_ERROR",
            "PAYMENT_TERM_MISMATCH",
            "INVOICE_AFTER_CHURN",
            "DUPLICATE_INVOICE",
            "CURRENCY_MISMATCH",
        }
    
    def _has_collection_action(
        self,
        invoice_id: str,
        open_amount_gbp: float,
        days_past_due: int,
        is_disputed_flag: int,
    ) -> int:
        """
        Derive stable collection action state per invoice.

        This prevents Payment Plan / stale status from randomly flashing between
        monthly snapshots.
        """
        if (
            open_amount_gbp <= self.rules.materiality_threshold_gbp
            or days_past_due <= 90
            or is_disputed_flag == 1
        ):
            return 0

        stable_roll = int(self._generate_pk(f"COLLECTION_ACTION_{invoice_id}")[:8], 16)
        stable_probability = (stable_roll % 10_000) / 10_000

        return int(stable_probability < 0.35)

    def _derive_collection_status(
        self,
        invoice_status: str,
        open_amount_gbp: float,
        days_past_due: int,
        is_disputed_flag: int,
        has_collection_action: int,
    ) -> str:
        """Derive collection status hierarchy for CFO-ready AR reporting."""
        invoice_status = str(invoice_status)

        if invoice_status == "Voided":
            return "Voided"

        if invoice_status == "Written Off":
            return "Written Off"

        if open_amount_gbp < -0.05:
            return "Overpaid"

        if abs(open_amount_gbp) <= 0.05:
            return "Closed"

        if is_disputed_flag == 1:
            return "Disputed"

        if has_collection_action == 1:
            return "Payment Plan"

        if days_past_due <= 0:
            return "Not Due"

        if (
            open_amount_gbp > self.rules.rounding_tolerance
            and days_past_due > 120
            and is_disputed_flag == 0
        ):
            return "Write-Off Candidate"

        if days_past_due > 0:
            return "Overdue"

        return "Open"

    def _derive_ageing_defect_type(
        self,
        open_amount_gbp: float,
        days_past_due: int,
        is_disputed_flag: int,
        invoice_status: str,
        has_collection_action: int,
    ) -> str:
        """
        Derive downstream ageing defects from structural AR conditions.

        These are deterministic reporting-layer control failures, not random
        injected defects.
        """
        invoice_status = str(invoice_status)

        if open_amount_gbp < -self.rules.rounding_tolerance:
            return "NEGATIVE_OPEN_AR"

        if (
            open_amount_gbp > self.rules.materiality_threshold_gbp
            and days_past_due > 120
            and is_disputed_flag == 0
            and invoice_status not in {"Written Off", "Voided"}
            and has_collection_action == 0
        ):
            return "STALE_OVERDUE_INVOICE"

        return ""

    def _generate_ageing_snapshot(
        self,
        invoices_df: pd.DataFrame,
        allocations_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Generate monthly point-in-time AR ageing snapshots.

        For each snapshot date:
        - include invoices issued on or before snapshot date
        - include allocations posted on or before snapshot date
        - calculate paid-to-date and open AR
        """
        snapshot_dates = self._generate_snapshot_dates()
        records: list[dict] = []

        invoices = invoices_df.copy()
        allocations = allocations_df.copy()

        invoices["invoice_date"] = pd.to_datetime(invoices["invoice_date"], errors="coerce")
        invoices["due_date"] = pd.to_datetime(invoices["due_date"], errors="coerce")

        if allocations.empty:
            allocations["allocation_date"] = pd.NaT
        else:
            allocations["allocation_date"] = pd.to_datetime(
                allocations["allocation_date"],
                errors="coerce",
            )

        for snapshot_date in snapshot_dates:
            eligible_invoices = invoices[
                invoices["invoice_date"] <= snapshot_date
            ].copy()

            if eligible_invoices.empty:
                continue

            eligible_allocations = allocations[
                allocations["allocation_date"] <= snapshot_date
            ].copy()

            if eligible_allocations.empty:
                paid_to_date = pd.DataFrame(
                    columns=[
                        "invoice_id",
                        "paid_amount_local",
                        "paid_amount_gbp",
                    ]
                )
            else:
                paid_to_date = (
                    eligible_allocations
                    .groupby("invoice_id", as_index=False)
                    .agg(
                        paid_amount_local=("allocated_amount_local", "sum"),
                        paid_amount_gbp=("allocated_amount_gbp", "sum"),
                    )
                )

            snapshot_df = eligible_invoices.merge(
                paid_to_date,
                on="invoice_id",
                how="left",
            )

            snapshot_df["paid_amount_local"] = (
                snapshot_df["paid_amount_local"].fillna(0.00)
            )
            snapshot_df["paid_amount_gbp"] = (
                snapshot_df["paid_amount_gbp"].fillna(0.00)
            )

            snapshot_df["open_amount_local"] = (
                snapshot_df["total_local"] - snapshot_df["paid_amount_local"]
            ).round(2)

            snapshot_df["open_amount_gbp"] = (
                snapshot_df["total_gbp"] - snapshot_df["paid_amount_gbp"]
            ).round(2)

            for _, row in snapshot_df.iterrows():
                invoice_id = str(row["invoice_id"])
                invoice_status = str(row["invoice_status"])
                invoice_defect_type = str(row.get("defect_type", ""))

                open_amount_gbp = float(row["open_amount_gbp"])
                days_past_due_raw = (snapshot_date - pd.Timestamp(row["due_date"])).days
                days_past_due = max(0, int(days_past_due_raw))

                ageing_bucket = self._derive_ageing_bucket(
                    open_amount_gbp=open_amount_gbp,
                    days_past_due=days_past_due,
                )

                ar_status = self._derive_ar_status(
                    invoice_status=invoice_status,
                    open_amount_gbp=open_amount_gbp,
                )

                is_disputed_flag = int(
                    invoice_defect_type in {
                        "TAX_CALCULATION_ERROR",
                        "PAYMENT_TERM_MISMATCH",
                        "INVOICE_AFTER_CHURN",
                        "DUPLICATE_INVOICE",
                        "CURRENCY_MISMATCH",
                    }
                    and open_amount_gbp > self.rules.rounding_tolerance
                )

                # Simulate some formal collection action for old debt.
                has_collection_action = self._has_collection_action(
                    invoice_id=invoice_id,
                    open_amount_gbp=open_amount_gbp,
                    days_past_due=days_past_due,
                    is_disputed_flag=is_disputed_flag,
)

                is_writeoff_candidate_flag = int(
                    open_amount_gbp > 100.00
                    and days_past_due > 120
                    and is_disputed_flag == 0
                    and invoice_status not in {"Written Off", "Voided"}
                )

                collection_status = self._derive_collection_status(
                    invoice_status=invoice_status,
                    open_amount_gbp=open_amount_gbp,
                    days_past_due=days_past_due,
                    is_disputed_flag=is_disputed_flag,
                    has_collection_action=has_collection_action,
                )

                ageing_defect_type = self._derive_ageing_defect_type(
                    open_amount_gbp=open_amount_gbp,
                    days_past_due=days_past_due,
                    is_disputed_flag=is_disputed_flag,
                    invoice_status=invoice_status,
                    has_collection_action=has_collection_action,
                )

                records.append(
                    {
                        "snapshot_pk": self._generate_pk(
                            f"{snapshot_date.strftime('%Y-%m-%d')}_{invoice_id}"
                        ),
                        "snapshot_date": snapshot_date.strftime("%Y-%m-%d"),
                        "invoice_id": invoice_id,
                        "customer_id": str(row["customer_id"]),
                        "invoice_date": pd.Timestamp(row["invoice_date"]).strftime("%Y-%m-%d"),
                        "due_date": pd.Timestamp(row["due_date"]).strftime("%Y-%m-%d"),
                        "currency": str(row["currency"]),
                        "invoice_total_local": self._round_money(float(row["total_local"])),
                        "invoice_total_gbp": self._round_money(float(row["total_gbp"])),
                        "paid_amount_local": self._round_money(float(row["paid_amount_local"])),
                        "paid_amount_gbp": self._round_money(float(row["paid_amount_gbp"])),
                        "open_amount_local": self._round_money(float(row["open_amount_local"])),
                        "open_amount_gbp": self._round_money(float(row["open_amount_gbp"])),
                        "days_past_due": days_past_due,
                        "ageing_bucket": ageing_bucket,
                        "ar_status": ar_status,
                        "collection_status": collection_status,
                        "is_disputed_flag": is_disputed_flag,
                        "is_writeoff_candidate_flag": is_writeoff_candidate_flag,
                        "source_system": "ar_ageing_extract",
                        "is_defect_flag": int(ageing_defect_type != ""),
                        "defect_type": ageing_defect_type,
                        "created_at": snapshot_date.strftime("%Y-%m-%d"),
                        "updated_at": snapshot_date.strftime("%Y-%m-%d"),
                    }
                )

        ageing_df = pd.DataFrame(records)
        ageing_df = ageing_df.reindex(columns=self.AGEING_COLUMNS)

        logger.info("Generated AR ageing snapshot rows: %s", f"{len(ageing_df):,}")

        if not ageing_df.empty:
            logger.info(
                "Ageing bucket distribution:\n%s",
                ageing_df["ageing_bucket"].value_counts(dropna=False).to_string(),
            )

            logger.info(
                "AR status distribution:\n%s",
                ageing_df["ar_status"].value_counts(dropna=False).to_string(),
            )

            logger.info(
                "Collection status distribution:\n%s",
                ageing_df["collection_status"].value_counts(dropna=False).to_string(),
            )

            logger.info(
                "Ageing defect distribution:\n%s",
                ageing_df["defect_type"].value_counts(dropna=False).to_string(),
            )

        return ageing_df
    
    def _validate_output(
        self,
        invoices_df: pd.DataFrame,
        payments_df: pd.DataFrame,
        allocations_df: pd.DataFrame,
        ageing_df: pd.DataFrame,
    ) -> None:
        """
        Validate Phase 3F payments, allocations and AR ageing outputs.

        Intentional ageing defects are allowed, but structural corruption is not.
        """
        logger.info("Running Phase 3F output validation...")

        if payments_df.empty:
            raise ValueError("billing_payments output cannot be empty.")

        if allocations_df.empty:
            raise ValueError("billing_payment_allocations output cannot be empty.")

        if ageing_df.empty:
            raise ValueError("ar_ageing_snapshot output cannot be empty.")

        # ------------------------------------------------------------------
        # 1. Primary key / identifier uniqueness
        # ------------------------------------------------------------------
        if payments_df["payment_id"].duplicated().any():
            duplicate_count = int(payments_df["payment_id"].duplicated().sum())
            raise ValueError(f"Duplicate payment_id values found: {duplicate_count:,}")

        if payments_df["payment_pk"].duplicated().any():
            duplicate_count = int(payments_df["payment_pk"].duplicated().sum())
            raise ValueError(f"Duplicate payment_pk values found: {duplicate_count:,}")

        if allocations_df["allocation_id"].duplicated().any():
            duplicate_count = int(allocations_df["allocation_id"].duplicated().sum())
            raise ValueError(f"Duplicate allocation_id values found: {duplicate_count:,}")

        if allocations_df["allocation_pk"].duplicated().any():
            duplicate_count = int(allocations_df["allocation_pk"].duplicated().sum())
            raise ValueError(f"Duplicate allocation_pk values found: {duplicate_count:,}")

        if ageing_df["snapshot_pk"].duplicated().any():
            duplicate_count = int(ageing_df["snapshot_pk"].duplicated().sum())
            raise ValueError(f"Duplicate snapshot_pk values found: {duplicate_count:,}")

        if ageing_df.duplicated(subset=["snapshot_date", "invoice_id"]).any():
            duplicate_count = int(
                ageing_df.duplicated(subset=["snapshot_date", "invoice_id"]).sum()
            )
            raise ValueError(
                "Duplicate AR ageing business keys found for "
                f"snapshot_date + invoice_id: {duplicate_count:,}"
            )

        # ------------------------------------------------------------------
        # 2. Referential integrity
        # ------------------------------------------------------------------
        valid_payment_ids = set(payments_df["payment_id"].astype(str))
        allocation_payment_ids = set(allocations_df["payment_id"].astype(str))
        missing_payment_ids = allocation_payment_ids.difference(valid_payment_ids)

        if missing_payment_ids:
            raise ValueError(
                "Allocation rows reference unknown payment_id values. "
                f"Examples: {list(missing_payment_ids)[:5]}"
            )

        valid_invoice_ids = set(invoices_df["invoice_id"].astype(str))
        allocation_invoice_ids = set(allocations_df["invoice_id"].astype(str))
        missing_invoice_ids = allocation_invoice_ids.difference(valid_invoice_ids)

        if missing_invoice_ids:
            raise ValueError(
                "Allocation rows reference unknown invoice_id values. "
                f"Examples: {list(missing_invoice_ids)[:5]}"
            )

        ageing_invoice_ids = set(ageing_df["invoice_id"].astype(str))
        missing_ageing_invoice_ids = ageing_invoice_ids.difference(valid_invoice_ids)

        if missing_ageing_invoice_ids:
            raise ValueError(
                "Ageing rows reference unknown invoice_id values. "
                f"Examples: {list(missing_ageing_invoice_ids)[:5]}"
            )

        # ------------------------------------------------------------------
        # 3. Cut-off integrity
        # ------------------------------------------------------------------
        extract_end_date = pd.Timestamp(self.rules.end_date)

        payment_dates = pd.to_datetime(payments_df["payment_date"], errors="coerce")
        allocation_dates = pd.to_datetime(allocations_df["allocation_date"], errors="coerce")
        snapshot_dates = pd.to_datetime(ageing_df["snapshot_date"], errors="coerce")

        if payment_dates.isna().any():
            bad_count = int(payment_dates.isna().sum())
            raise ValueError(f"Invalid/null payment_date values found: {bad_count:,}")

        if allocation_dates.isna().any():
            bad_count = int(allocation_dates.isna().sum())
            raise ValueError(f"Invalid/null allocation_date values found: {bad_count:,}")

        if snapshot_dates.isna().any():
            bad_count = int(snapshot_dates.isna().sum())
            raise ValueError(f"Invalid/null snapshot_date values found: {bad_count:,}")

        if (payment_dates > extract_end_date).any():
            bad_count = int((payment_dates > extract_end_date).sum())
            raise ValueError(
                f"Payment dates after extract end date detected: {bad_count:,}"
            )

        if (allocation_dates > extract_end_date).any():
            bad_count = int((allocation_dates > extract_end_date).sum())
            raise ValueError(
                f"Allocation dates after extract end date detected: {bad_count:,}"
            )

        if (snapshot_dates > extract_end_date).any():
            bad_count = int((snapshot_dates > extract_end_date).sum())
            raise ValueError(
                f"Snapshot dates after extract end date detected: {bad_count:,}"
            )

        # ------------------------------------------------------------------
        # 4. Unapplied cash integrity
        # ------------------------------------------------------------------
        unapplied_payment_ids = set(
            payments_df.loc[
                payments_df["payment_status"].eq("Unapplied"),
                "payment_id",
            ].astype(str)
        )

        allocated_unapplied_ids = set(
            allocations_df.loc[
                allocations_df["payment_id"].astype(str).isin(unapplied_payment_ids),
                "payment_id",
            ].astype(str)
        )

        if allocated_unapplied_ids:
            raise ValueError(
                "Unapplied cash payments should not have allocation rows. "
                f"Examples: {list(allocated_unapplied_ids)[:5]}"
            )

        # ------------------------------------------------------------------
        # 5. Amount sanity checks
        # ------------------------------------------------------------------
        for df_name, df, amount_columns in [
            (
                "billing_payments",
                payments_df,
                ["payment_amount_local", "payment_amount_gbp"],
            ),
            (
                "billing_payment_allocations",
                allocations_df,
                ["allocated_amount_local", "allocated_amount_gbp"],
            ),
            (
                "ar_ageing_snapshot",
                ageing_df,
                [
                    "invoice_total_local",
                    "invoice_total_gbp",
                    "paid_amount_local",
                    "paid_amount_gbp",
                ],
            ),
        ]:
            for column in amount_columns:
                if pd.to_numeric(df[column], errors="coerce").isna().any():
                    bad_count = int(pd.to_numeric(df[column], errors="coerce").isna().sum())
                    raise ValueError(
                        f"{df_name}.{column} contains invalid numeric values: {bad_count:,}"
                    )

                if (pd.to_numeric(df[column], errors="coerce") < 0).any():
                    bad_count = int((pd.to_numeric(df[column], errors="coerce") < 0).sum())
                    raise ValueError(
                        f"{df_name}.{column} contains negative values: {bad_count:,}"
                    )

        # Open amount can be negative by design because over-application creates
        # NEGATIVE_OPEN_AR. So do not reject negative open_amount values globally.

        # ------------------------------------------------------------------
        # 6. Ageing semantic checks
        # ------------------------------------------------------------------
        closed_bad = ageing_df[
            (ageing_df["ageing_bucket"].eq("Closed"))
            & (ageing_df["open_amount_gbp"].abs() > self.rules.rounding_tolerance)
        ]

        if not closed_bad.empty:
            raise ValueError(
                "Closed ageing bucket rows should have near-zero open_amount_gbp. "
                f"Bad rows: {len(closed_bad):,}"
            )

        current_bad = ageing_df[
            (ageing_df["ageing_bucket"].eq("Current"))
            & (ageing_df["days_past_due"] > 0)
        ]

        if not current_bad.empty:
            raise ValueError(
                "Current ageing bucket rows should not have days_past_due > 0. "
                f"Bad rows: {len(current_bad):,}"
            )

        bucket_120_bad = ageing_df[
            (ageing_df["ageing_bucket"].eq("120+"))
            & (ageing_df["days_past_due"] <= 120)
        ]

        if not bucket_120_bad.empty:
            raise ValueError(
                "120+ ageing bucket rows should have days_past_due > 120. "
                f"Bad rows: {len(bucket_120_bad):,}"
            )

        negative_open_ar_bad = ageing_df[
            (ageing_df["defect_type"].eq("NEGATIVE_OPEN_AR"))
            & (ageing_df["open_amount_gbp"] >= -self.rules.rounding_tolerance)
        ]

        if not negative_open_ar_bad.empty:
            raise ValueError(
                "NEGATIVE_OPEN_AR rows must have negative open_amount_gbp. "
                f"Bad rows: {len(negative_open_ar_bad):,}"
            )

        stale_overdue_bad = ageing_df[
            (ageing_df["defect_type"].eq("STALE_OVERDUE_INVOICE"))
            & (
                (ageing_df["open_amount_gbp"] <= self.rules.materiality_threshold_gbp)
                | (ageing_df["days_past_due"] <= 120)
                | (ageing_df["is_disputed_flag"] != 0)
            )
        ]

        if not stale_overdue_bad.empty:
            raise ValueError(
                "STALE_OVERDUE_INVOICE rows do not meet stale overdue criteria. "
                f"Bad rows: {len(stale_overdue_bad):,}"
            )

        # ------------------------------------------------------------------
        # 7. Reconciliation check: invoice total - paid amount = open amount
        # ------------------------------------------------------------------
        ageing_df = ageing_df.copy()

        local_recon_delta = (
            ageing_df["invoice_total_local"]
            - ageing_df["paid_amount_local"]
            - ageing_df["open_amount_local"]
        ).abs()

        gbp_recon_delta = (
            ageing_df["invoice_total_gbp"]
            - ageing_df["paid_amount_gbp"]
            - ageing_df["open_amount_gbp"]
        ).abs()

        if (local_recon_delta > self.rules.rounding_tolerance).any():
            bad_count = int((local_recon_delta > self.rules.rounding_tolerance).sum())
            raise ValueError(
                f"AR ageing local reconciliation failed for {bad_count:,} rows."
            )

        if (gbp_recon_delta > self.rules.rounding_tolerance).any():
            bad_count = int((gbp_recon_delta > self.rules.rounding_tolerance).sum())
            raise ValueError(
                f"AR ageing GBP reconciliation failed for {bad_count:,} rows."
            )

        logger.info("Phase 3F output validation passed.")

    def save(
        self,
        payments_df: pd.DataFrame,
        allocations_df: pd.DataFrame,
        ageing_df: pd.DataFrame,
    ) -> None:
        """Save Phase 3F payments, allocations and AR ageing outputs."""
        output_dir = get_raw_data_path("billing")
        output_dir.mkdir(parents=True, exist_ok=True)

        payments_path = output_dir / "billing_payments.csv"
        allocations_path = output_dir / "billing_payment_allocations.csv"
        ageing_path = output_dir / "ar_ageing_snapshot.csv"

        payments_df.to_csv(payments_path, index=False, encoding="utf-8")
        allocations_df.to_csv(allocations_path, index=False, encoding="utf-8")
        ageing_df.to_csv(ageing_path, index=False, encoding="utf-8")

        logger.info("Billing payments written to %s", payments_path)
        logger.info("Billing payment allocations written to %s", allocations_path)
        logger.info("AR ageing snapshot written to %s", ageing_path)
    
def main() -> None:
    generator = BillingPaymentsGenerator()
    payments_df, allocations_df, ageing_df = generator.generate()
    generator.save(payments_df, allocations_df, ageing_df)

    logger.info(
        "Phase 3F standalone run complete. Saved %s payment rows, %s allocation rows and %s ageing rows.",
        f"{len(payments_df):,}",
        f"{len(allocations_df):,}",
        f"{len(ageing_df):,}",
    )


if __name__ == "__main__":
    main()