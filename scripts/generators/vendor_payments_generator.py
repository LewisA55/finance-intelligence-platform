"""
vendor_payments_generator.py

Project Atlas / Nexus Technologies
Phase 3I.3 - Vendor Payments / AP Settlement

Purpose
-------
Generates:
- data/raw/procurement/vendor_payments.csv

This layer converts paid AP vendor invoices into supplier cash settlement
events.

Design
------
vendor_invoices.csv
    = supplier invoice liability / AP document header

vendor_payments.csv
    = supplier cash settlement event

Grain
-----
vendor_payments.csv:
    One row per paid vendor invoice settlement.

Core accounting principle
-------------------------
Payments clear Accounts Payable and reduce cash.

This generator does not create new FX variance. The GBP value of the payment
matches the GBP total already established on the source vendor invoice.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path
from scripts.utils.validation import raise_if_invalid, verify_dataset_integrity


logger = get_logger("VendorPaymentsGenerator", "generation_execution.log")


@dataclass(frozen=True)
class VendorPaymentRules:
    """Business rules for vendor payment generation."""

    start_date: date = date(2023, 1, 1)
    end_date: date = date(2026, 6, 3)
    created_at: date = date(2026, 6, 3)
    updated_at: date = date(2026, 6, 3)


class VendorPaymentsGenerator:
    """
    Generates supplier payment settlements for paid AP invoices.

    Inputs
    ------
    data/raw/procurement/vendors.csv
    data/raw/procurement/vendor_invoices.csv

    Output
    ------
    data/raw/procurement/vendor_payments.csv
    """

    output_filename = "vendor_payments.csv"

    REQUIRED_VENDOR_COLUMNS = {
        "vendor_id",
        "vendor_name",
        "payment_terms",
        "currency",
        "cash_account_code",
        "is_strategic_vendor",
        "vendor_status",
        "approval_status",
    }

    REQUIRED_INVOICE_COLUMNS = {
        "vendor_invoice_id",
        "vendor_id",
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "due_date",
        "posting_date",
        "currency",
        "total_local",
        "total_gbp",
        "payment_status",
        "is_defect_flag",
        "defect_type",
    }

    PAYMENT_COLUMNS = [
        "vendor_payment_pk",
        "vendor_payment_id",
        "vendor_invoice_id",
        "vendor_id",
        "vendor_name",
        "invoice_number",
        "payment_date",
        "currency",
        "payment_amount_local",
        "payment_amount_gbp",
        "cash_account_code",
        "payment_method",
        "payment_reference",
        "payment_status",
        "source_system",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    CASH_ACCOUNT_BY_CURRENCY = {
        "GBP": "1010",
        "USD": "1020",
        "EUR": "1030",
        "SGD": "1040",
    }

    VALID_PAYMENT_STATUSES = {"Cleared"}

    VALID_PAYMENT_METHODS = {
        "Electronic Transfer",
        "Credit Card",
        "Direct Debit",
    }

    SOURCE_SYSTEM = "NEXUS_ERP_AP"

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.rules = VendorPaymentRules()

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pk(value: str) -> str:
        """Generate deterministic MD5 surrogate key."""
        return hashlib.md5(value.strip().upper().encode("utf-8")).hexdigest()

    @staticmethod
    def _round_money(value: object) -> float:
        if pd.isna(value):
            return 0.00

        return round(float(value), 2)

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
    def _validate_input_columns(
        df: pd.DataFrame,
        required_columns: set[str],
        dataset_name: str,
    ) -> None:
        missing_columns = required_columns.difference(df.columns)

        if missing_columns:
            raise ValueError(
                f"{dataset_name} is missing required columns: {sorted(missing_columns)}"
            )

    # ------------------------------------------------------------------
    # Loading and preparation
    # ------------------------------------------------------------------

    def _load_csv(self, path: Path, dataset_name: str) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(
                f"{dataset_name} not found at: {path}. Run upstream generators first."
            )

        return pd.read_csv(path)

    def _load_vendors(self) -> pd.DataFrame:
        path = get_raw_data_path("procurement") / "vendors.csv"
        df = self._load_csv(path, "vendors.csv")

        self._validate_input_columns(
            df=df,
            required_columns=self.REQUIRED_VENDOR_COLUMNS,
            dataset_name="vendors.csv",
        )

        df["vendor_id"] = df["vendor_id"].astype(str)
        df["vendor_name"] = df["vendor_name"].astype(str)
        df["payment_terms"] = df["payment_terms"].astype(str)
        df["currency"] = df["currency"].astype(str).str.upper()
        df["cash_account_code"] = df["cash_account_code"].astype(str)
        df["vendor_status"] = df["vendor_status"].fillna("Active").astype(str)
        df["approval_status"] = df["approval_status"].fillna("Approved").astype(str)
        df["is_strategic_vendor"] = df["is_strategic_vendor"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )

        df = df[
            (df["vendor_status"].str.lower() == "active")
            & (df["approval_status"].str.lower() == "approved")
        ].copy()

        if df.empty:
            raise ValueError("vendors.csv contains no active approved vendors.")

        return df

    def _load_vendor_invoices(self) -> pd.DataFrame:
        path = get_raw_data_path("procurement") / "vendor_invoices.csv"
        df = self._load_csv(path, "vendor_invoices.csv")

        self._validate_input_columns(
            df=df,
            required_columns=self.REQUIRED_INVOICE_COLUMNS,
            dataset_name="vendor_invoices.csv",
        )

        df["vendor_invoice_id"] = df["vendor_invoice_id"].astype(str)
        df["vendor_id"] = df["vendor_id"].astype(str)
        df["vendor_name"] = df["vendor_name"].astype(str)
        df["invoice_number"] = df["invoice_number"].astype(str)
        df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
        df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
        df["posting_date"] = pd.to_datetime(df["posting_date"], errors="coerce")
        df["currency"] = df["currency"].astype(str).str.upper()
        df["payment_status"] = df["payment_status"].astype(str)
        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        for column in ["total_local", "total_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        if df["invoice_date"].isna().any():
            raise ValueError("vendor_invoices.csv contains invalid invoice_date values.")

        if df["due_date"].isna().any():
            raise ValueError("vendor_invoices.csv contains invalid due_date values.")

        if df["posting_date"].isna().any():
            raise ValueError("vendor_invoices.csv contains invalid posting_date values.")

        if df[["total_local", "total_gbp"]].isna().any().any():
            raise ValueError("vendor_invoices.csv contains invalid monetary values.")

        return df

    def _load_dependencies(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        vendors_df = self._load_vendors()
        invoices_df = self._load_vendor_invoices()

        logger.info(
            "Loaded vendor payment dependencies: %s vendors, %s vendor invoices.",
            f"{len(vendors_df):,}",
            f"{len(invoices_df):,}",
        )

        return vendors_df, invoices_df

    # ------------------------------------------------------------------
    # Payment derivation
    # ------------------------------------------------------------------

    def _derive_payment_date(
        self,
        invoice: pd.Series,
        payment_terms: str,
    ) -> pd.Timestamp:
        """
        Derive settlement date.

        Immediate terms settle on invoice_date.
        Net terms settle on due_date.
        """
        terms = str(payment_terms).strip().lower()

        if "immediate" in terms or "receipt" in terms:
            return pd.Timestamp(invoice["invoice_date"])

        return pd.Timestamp(invoice["due_date"])

    def _derive_payment_method(
        self,
        invoice: pd.Series,
        vendor: pd.Series,
    ) -> str:
        """Derive realistic AP settlement method."""
        payment_terms = str(vendor["payment_terms"]).strip().lower()
        vendor_name = str(vendor["vendor_name"]).lower()
        is_strategic = int(vendor["is_strategic_vendor"]) == 1

        if "immediate" in payment_terms:
            return "Credit Card"

        if is_strategic:
            return "Electronic Transfer"

        if any(name in vendor_name for name in ["wework", "british gas", "office"]):
            return "Direct Debit"

        return "Electronic Transfer"

    def _get_cash_account_code(
        self,
        currency: str,
        invoice_cash_account_code: str | None = None,
    ) -> str:
        currency = str(currency).upper()

        expected_account = self.CASH_ACCOUNT_BY_CURRENCY.get(currency)

        if expected_account is None:
            raise ValueError(f"No AP cash account mapping configured for currency={currency}.")

        if invoice_cash_account_code is not None and str(invoice_cash_account_code).strip():
            invoice_cash_account_code = str(invoice_cash_account_code).strip()

            if invoice_cash_account_code != expected_account:
                raise ValueError(
                    f"Vendor cash account mismatch for currency={currency}: "
                    f"expected {expected_account}, got {invoice_cash_account_code}."
                )

        return expected_account

    def _generate_payment_id(
        self,
        vendor_invoice_id: str,
        payment_date: pd.Timestamp,
    ) -> str:
        return f"VPMT-{payment_date.strftime('%Y%m%d')}-{vendor_invoice_id}"

    def _build_payment_record(
        self,
        invoice: pd.Series,
        vendor_lookup: dict[str, dict],
    ) -> dict:
        vendor_id = str(invoice["vendor_id"])

        if vendor_id not in vendor_lookup:
            raise ValueError(
                f"vendor_invoices.csv references vendor_id missing from vendors.csv: {vendor_id}"
            )

        vendor = pd.Series(vendor_lookup[vendor_id])

        payment_date = self._derive_payment_date(
            invoice=invoice,
            payment_terms=str(vendor["payment_terms"]),
        )

        if payment_date > pd.Timestamp(self.rules.end_date):
            raise ValueError(
                f"Paid invoice {invoice['vendor_invoice_id']} has payment_date after extract date: "
                f"{payment_date.date().isoformat()}"
            )

        currency = str(invoice["currency"]).upper()

        cash_account_code = self._get_cash_account_code(
            currency=currency,
            invoice_cash_account_code=str(vendor.get("cash_account_code", "")),
        )

        vendor_invoice_id = str(invoice["vendor_invoice_id"])
        vendor_payment_id = self._generate_payment_id(
            vendor_invoice_id=vendor_invoice_id,
            payment_date=payment_date,
        )

        payment_reference = f"VPMT-{payment_date.strftime('%Y%m')}-{self._generate_pk(vendor_payment_id)[:8].upper()}"

        return {
            "vendor_payment_pk": self._generate_pk(vendor_payment_id),
            "vendor_payment_id": vendor_payment_id,
            "vendor_invoice_id": vendor_invoice_id,
            "vendor_id": vendor_id,
            "vendor_name": str(invoice["vendor_name"]),
            "invoice_number": str(invoice["invoice_number"]),
            "payment_date": payment_date.date().isoformat(),
            "currency": currency,
            "payment_amount_local": self._round_money(invoice["total_local"]),
            "payment_amount_gbp": self._round_money(invoice["total_gbp"]),
            "cash_account_code": cash_account_code,
            "payment_method": self._derive_payment_method(invoice=invoice, vendor=vendor),
            "payment_reference": payment_reference,
            "payment_status": "Cleared",
            "source_system": self.SOURCE_SYSTEM,
            "is_defect_flag": int(invoice["is_defect_flag"]),
            "defect_type": str(invoice["defect_type"]),
            "created_at": self.rules.created_at.isoformat(),
            "updated_at": self.rules.updated_at.isoformat(),
        }

    # ------------------------------------------------------------------
    # Validation and review
    # ------------------------------------------------------------------

    def _validate_output(
        self,
        invoices_df: pd.DataFrame,
        payments_df: pd.DataFrame,
    ) -> None:
        is_valid, validation_logs = verify_dataset_integrity(
            df=payments_df,
            required_columns=self.PAYMENT_COLUMNS,
            unique_keys=["vendor_payment_pk"],
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

        if payments_df["vendor_payment_id"].duplicated().any():
            duplicate_count = int(payments_df["vendor_payment_id"].duplicated().sum())
            raise ValueError(
                f"vendor_payments.csv contains duplicate vendor_payment_id values: {duplicate_count:,}"
            )

        paid_invoices_df = invoices_df[
            invoices_df["payment_status"].astype(str).str.lower() == "paid"
        ].copy()

        paid_invoice_ids = set(paid_invoices_df["vendor_invoice_id"].astype(str))
        paid_payment_invoice_ids = set(payments_df["vendor_invoice_id"].astype(str))

        missing_payments = paid_invoice_ids.difference(paid_payment_invoice_ids)

        if missing_payments:
            raise ValueError(
                f"Paid vendor invoices missing payment records: {len(missing_payments):,}"
            )

        unexpected_payments = paid_payment_invoice_ids.difference(paid_invoice_ids)

        if unexpected_payments:
            raise ValueError(
                f"Payments generated for non-paid vendor invoices: {len(unexpected_payments):,}"
            )

        if len(payments_df) != len(paid_invoices_df):
            raise ValueError(
                f"Payment count mismatch. Expected {len(paid_invoices_df):,}, "
                f"got {len(payments_df):,}."
            )

        merged = payments_df.merge(
            paid_invoices_df[
                [
                    "vendor_invoice_id",
                    "invoice_date",
                    "due_date",
                    "currency",
                    "total_local",
                    "total_gbp",
                    "is_defect_flag",
                    "defect_type",
                ]
            ],
            on="vendor_invoice_id",
            how="left",
            suffixes=("_payment", "_invoice"),
        )

        if merged["currency_payment"].ne(merged["currency_invoice"]).any():
            raise ValueError("Payment currency does not match vendor invoice currency.")

        merged["local_delta"] = (
            merged["payment_amount_local"] - merged["total_local"]
        ).round(2)
        merged["gbp_delta"] = (
            merged["payment_amount_gbp"] - merged["total_gbp"]
        ).round(2)

        bad_amounts = merged[
            (merged["local_delta"].abs() > 0.00)
            | (merged["gbp_delta"].abs() > 0.00)
        ]

        if not bad_amounts.empty:
            raise ValueError(
                f"Payment amount does not match source invoice total for {len(bad_amounts):,} rows."
            )

        invalid_cash_accounts = payments_df[
            payments_df.apply(
                lambda row: self.CASH_ACCOUNT_BY_CURRENCY[str(row["currency"]).upper()]
                != str(row["cash_account_code"]),
                axis=1,
            )
        ]

        if not invalid_cash_accounts.empty:
            raise ValueError("Cash account mapping does not match payment currency.")

        if not payments_df["payment_status"].isin(self.VALID_PAYMENT_STATUSES).all():
            invalid_statuses = set(payments_df["payment_status"]).difference(
                self.VALID_PAYMENT_STATUSES
            )
            raise ValueError(f"Invalid payment statuses: {sorted(invalid_statuses)}")

        if not payments_df["payment_method"].isin(self.VALID_PAYMENT_METHODS).all():
            invalid_methods = set(payments_df["payment_method"]).difference(
                self.VALID_PAYMENT_METHODS
            )
            raise ValueError(f"Invalid payment methods: {sorted(invalid_methods)}")

        payment_dates = pd.to_datetime(payments_df["payment_date"], errors="coerce")

        if payment_dates.isna().any():
            raise ValueError("vendor_payments.csv contains invalid payment_date values.")

        if (payment_dates > pd.Timestamp(self.rules.end_date)).any():
            raise ValueError("vendor_payments.csv contains payment_date after extract date.")

        duplicate_invoice_payments = payments_df[
            payments_df["defect_type"] == "DUPLICATE_VENDOR_INVOICE"
        ]

        if len(duplicate_invoice_payments) != 2:
            raise ValueError(
                "Expected exactly two payments for DUPLICATE_VENDOR_INVOICE records."
            )

        cutoff_payments = payments_df[
            payments_df["defect_type"] == "AP_CUTOFF_FAILURE"
        ]

        if len(cutoff_payments) != 1:
            raise ValueError(
                "Expected exactly one payment for AP_CUTOFF_FAILURE record."
            )

        cutoff_payment = cutoff_payments.iloc[0]

        if str(cutoff_payment["payment_date"]) != "2026-03-12":
            raise ValueError(
                "AP_CUTOFF_FAILURE payment did not settle on expected due date 2026-03-12."
            )

        logger.info("Vendor payment output validation passed.")

    def _log_output_review(self, payments_df: pd.DataFrame) -> None:
        logger.info("----- Vendor Payments Review -----")
        logger.info("Vendor payment rows: %s", f"{len(payments_df):,}")

        logger.info(
            "Payments by currency:\n%s",
            payments_df["currency"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Payments by cash account:\n%s",
            payments_df["cash_account_code"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Payments by method:\n%s",
            payments_df["payment_method"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Payment defect distribution:\n%s",
            payments_df["defect_type"]
            .replace("", "None")
            .value_counts(dropna=False)
            .to_string(),
        )

        logger.info(
            "Total vendor payments GBP: %.2f",
            float(payments_df["payment_amount_gbp"].sum()),
        )

        logger.info("---------------------------------")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> pd.DataFrame:
        logger.info("Generating Phase 3I.3 vendor payments / AP settlement.")

        vendors_df, invoices_df = self._load_dependencies()

        vendor_lookup = vendors_df.set_index("vendor_id").to_dict(orient="index")

        paid_invoices_df = invoices_df[
            invoices_df["payment_status"].astype(str).str.lower() == "paid"
        ].copy()

        logger.info(
            "Selected paid vendor invoices for settlement: %s of %s invoices.",
            f"{len(paid_invoices_df):,}",
            f"{len(invoices_df):,}",
        )

        records: list[dict] = []

        for _, invoice in paid_invoices_df.iterrows():
            records.append(
                self._build_payment_record(
                    invoice=invoice,
                    vendor_lookup=vendor_lookup,
                )
            )

        payments_df = pd.DataFrame(records)

        if payments_df.empty:
            raise ValueError("No vendor payment records generated.")

        payments_df = payments_df[self.PAYMENT_COLUMNS].copy()

        self._validate_output(
            invoices_df=invoices_df,
            payments_df=payments_df,
        )
        self._log_output_review(payments_df)

        logger.info(
            "Phase 3I.3 generation complete: %s vendor payments.",
            f"{len(payments_df):,}",
        )

        return payments_df

    def save(self, payments_df: pd.DataFrame) -> None:
        output_dir = get_raw_data_path("procurement")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / self.output_filename
        payments_df.to_csv(output_path, index=False, encoding="utf-8")

        logger.info("Vendor payments written to %s", output_path)


def main() -> None:
    generator = VendorPaymentsGenerator()
    payments_df = generator.generate()
    generator.save(payments_df)

    logger.info(
        "Phase 3I.3 standalone run complete. Saved %s vendor payments.",
        f"{len(payments_df):,}",
    )


if __name__ == "__main__":
    main()