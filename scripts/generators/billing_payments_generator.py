"""
billing_payments_generator.py

Project Atlas / Nexus Technologies
Phase 3F - Payments, Cash Receipts & AR Ageing
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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

    def generate(self) -> pd.DataFrame:
        """
        Temporary Phase 3F development entry point.

        Builds invoice-level payment intents only.
        Full payment, allocation and ageing outputs will be added next.
        """
        logger.info("Generating Phase 3F payment intents...")

        intents_df = self._build_payment_intents()

        logger.info(
            "Payment intent generation complete: %s invoice intent rows.",
            f"{len(intents_df):,}",
        )

        return intents_df

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
    
def main() -> None:
    generator = BillingPaymentsGenerator()
    intents_df = generator.generate()

    logger.info(
        "Intent engine smoke test complete. Generated %s rows.",
        f"{len(intents_df):,}",
    )


if __name__ == "__main__":
    main()
        