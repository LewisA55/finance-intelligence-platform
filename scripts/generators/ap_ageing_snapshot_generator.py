"""
ap_ageing_snapshot_generator.py

Project Atlas / Nexus Technologies
Phase 3I.4 - AP Ageing / Open AP Snapshot

Purpose
-------
Generates:
- data/raw/procurement/ap_ageing_snapshot.csv

This file captures open supplier liabilities as of the extraction date and
classifies them into AP ageing buckets.

Design
------
vendor_invoices.csv
    = AP liability source document

vendor_payments.csv
    = AP cash settlement events

ap_ageing_snapshot.csv
    = point-in-time CFO/AP reporting snapshot

Grain
-----
One row per vendor invoice with open AP balance as of snapshot_date.

Core accounting principle
-------------------------
Open AP = vendor invoice total - cleared vendor payments.

In the current Phase 3I.3 design, payments are one-to-one with paid invoices,
so the expected open AP population is:

    vendor_invoices where payment_status != 'Paid'

or any invoice where total paid amount is less than invoice total.
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


logger = get_logger("APAgeingSnapshotGenerator", "generation_execution.log")


@dataclass(frozen=True)
class APAgeingSnapshotRules:
    """Business rules for AP ageing snapshot generation."""

    snapshot_date: date = date(2026, 6, 3)
    created_at: date = date(2026, 6, 3)
    updated_at: date = date(2026, 6, 3)
    rounding_tolerance: float = 0.05


class APAgeingSnapshotGenerator:
    """
    Generates a point-in-time AP ageing snapshot.

    Inputs
    ------
    data/raw/procurement/vendor_invoices.csv
    data/raw/procurement/vendor_payments.csv

    Output
    ------
    data/raw/procurement/ap_ageing_snapshot.csv
    """

    output_filename = "ap_ageing_snapshot.csv"

    REQUIRED_INVOICE_COLUMNS = {
        "vendor_invoice_id",
        "vendor_id",
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "due_date",
        "currency",
        "total_local",
        "total_gbp",
        "payment_status",
        "source_system",
        "is_defect_flag",
        "defect_type",
    }

    REQUIRED_PAYMENT_COLUMNS = {
        "vendor_payment_id",
        "vendor_invoice_id",
        "vendor_id",
        "payment_date",
        "currency",
        "payment_amount_local",
        "payment_amount_gbp",
        "payment_status",
        "source_system",
        "is_defect_flag",
        "defect_type",
    }

    SNAPSHOT_COLUMNS = [
        "snapshot_pk",
        "snapshot_date",
        "vendor_invoice_id",
        "vendor_id",
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "due_date",
        "days_past_due",
        "ageing_bucket",
        "ap_status",
        "currency",
        "invoice_total_local",
        "invoice_total_gbp",
        "paid_amount_local",
        "paid_amount_gbp",
        "open_amount_local",
        "open_amount_gbp",
        "source_system",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    VALID_AGEING_BUCKETS = {
        "Current",
        "1-30 Days",
        "31-60 Days",
        "61-90 Days",
        "91+ Days",
    }

    VALID_AP_STATUSES = {
        "Open",
        "Overdue",
    }

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.rules = APAgeingSnapshotRules()

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
        df["currency"] = df["currency"].astype(str).str.upper()
        df["payment_status"] = df["payment_status"].astype(str)
        df["source_system"] = df["source_system"].fillna("NEXUS_ERP_AP").astype(str)
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

        if df[["total_local", "total_gbp"]].isna().any().any():
            raise ValueError("vendor_invoices.csv contains invalid monetary values.")

        return df

    def _load_vendor_payments(self) -> pd.DataFrame:
        path = get_raw_data_path("procurement") / "vendor_payments.csv"
        df = self._load_csv(path, "vendor_payments.csv")

        self._validate_input_columns(
            df=df,
            required_columns=self.REQUIRED_PAYMENT_COLUMNS,
            dataset_name="vendor_payments.csv",
        )

        df["vendor_payment_id"] = df["vendor_payment_id"].astype(str)
        df["vendor_invoice_id"] = df["vendor_invoice_id"].astype(str)
        df["vendor_id"] = df["vendor_id"].astype(str)
        df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce")
        df["currency"] = df["currency"].astype(str).str.upper()
        df["payment_status"] = df["payment_status"].astype(str)
        df["source_system"] = df["source_system"].fillna("NEXUS_ERP_AP").astype(str)
        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        for column in ["payment_amount_local", "payment_amount_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        if df["payment_date"].isna().any():
            raise ValueError("vendor_payments.csv contains invalid payment_date values.")

        if df[["payment_amount_local", "payment_amount_gbp"]].isna().any().any():
            raise ValueError("vendor_payments.csv contains invalid monetary values.")

        return df

    def _load_dependencies(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        invoices_df = self._load_vendor_invoices()
        payments_df = self._load_vendor_payments()

        logger.info(
            "Loaded AP ageing dependencies: %s vendor invoices, %s vendor payments.",
            f"{len(invoices_df):,}",
            f"{len(payments_df):,}",
        )

        return invoices_df, payments_df

    # ------------------------------------------------------------------
    # Ageing logic
    # ------------------------------------------------------------------

    def _get_ageing_bucket(self, days_past_due: int) -> str:
        if days_past_due <= 0:
            return "Current"

        if days_past_due <= 30:
            return "1-30 Days"

        if days_past_due <= 60:
            return "31-60 Days"

        if days_past_due <= 90:
            return "61-90 Days"

        return "91+ Days"

    def _get_ap_status(self, days_past_due: int) -> str:
        return "Open" if days_past_due <= 0 else "Overdue"

    def _build_payment_summary(self, payments_df: pd.DataFrame) -> pd.DataFrame:
        """
        Summarise cleared payments by vendor invoice as of snapshot_date.
        """
        snapshot_date = pd.Timestamp(self.rules.snapshot_date)

        cleared_payments = payments_df[
            (payments_df["payment_status"].astype(str).str.lower() == "cleared")
            & (payments_df["payment_date"] <= snapshot_date)
        ].copy()

        if cleared_payments.empty:
            return pd.DataFrame(
                columns=[
                    "vendor_invoice_id",
                    "paid_amount_local",
                    "paid_amount_gbp",
                ]
            )

        summary_df = (
            cleared_payments.groupby("vendor_invoice_id", as_index=False)
            .agg(
                paid_amount_local=("payment_amount_local", "sum"),
                paid_amount_gbp=("payment_amount_gbp", "sum"),
            )
        )

        summary_df["paid_amount_local"] = summary_df["paid_amount_local"].round(2)
        summary_df["paid_amount_gbp"] = summary_df["paid_amount_gbp"].round(2)

        return summary_df

    def _build_snapshot(
        self,
        invoices_df: pd.DataFrame,
        payments_df: pd.DataFrame,
    ) -> pd.DataFrame:
        snapshot_date = pd.Timestamp(self.rules.snapshot_date)

        payment_summary_df = self._build_payment_summary(payments_df)

        df = invoices_df.merge(
            payment_summary_df,
            on="vendor_invoice_id",
            how="left",
        )

        df["paid_amount_local"] = df["paid_amount_local"].fillna(0.00)
        df["paid_amount_gbp"] = df["paid_amount_gbp"].fillna(0.00)

        df["open_amount_local"] = (
            df["total_local"] - df["paid_amount_local"]
        ).round(2)
        df["open_amount_gbp"] = (
            df["total_gbp"] - df["paid_amount_gbp"]
        ).round(2)

        open_df = df[
            (df["open_amount_local"].abs() > self.rules.rounding_tolerance)
            | (df["open_amount_gbp"].abs() > self.rules.rounding_tolerance)
        ].copy()

        open_df["days_past_due"] = (
            snapshot_date - open_df["due_date"]
        ).dt.days.astype(int)

        open_df["ageing_bucket"] = open_df["days_past_due"].apply(
            self._get_ageing_bucket
        )

        open_df["ap_status"] = open_df["days_past_due"].apply(
            self._get_ap_status
        )

        open_df["snapshot_date"] = snapshot_date.date().isoformat()

        open_df["snapshot_pk"] = open_df.apply(
            lambda row: self._generate_pk(
                f"{row['vendor_invoice_id']}_{row['snapshot_date']}"
            ),
            axis=1,
        )

        output_df = pd.DataFrame(
            {
                "snapshot_pk": open_df["snapshot_pk"],
                "snapshot_date": open_df["snapshot_date"],
                "vendor_invoice_id": open_df["vendor_invoice_id"],
                "vendor_id": open_df["vendor_id"],
                "vendor_name": open_df["vendor_name"],
                "invoice_number": open_df["invoice_number"],
                "invoice_date": open_df["invoice_date"].dt.date.astype(str),
                "due_date": open_df["due_date"].dt.date.astype(str),
                "days_past_due": open_df["days_past_due"],
                "ageing_bucket": open_df["ageing_bucket"],
                "ap_status": open_df["ap_status"],
                "currency": open_df["currency"],
                "invoice_total_local": open_df["total_local"].round(2),
                "invoice_total_gbp": open_df["total_gbp"].round(2),
                "paid_amount_local": open_df["paid_amount_local"].round(2),
                "paid_amount_gbp": open_df["paid_amount_gbp"].round(2),
                "open_amount_local": open_df["open_amount_local"].round(2),
                "open_amount_gbp": open_df["open_amount_gbp"].round(2),
                "source_system": open_df["source_system"],
                "is_defect_flag": open_df["is_defect_flag"],
                "defect_type": open_df["defect_type"],
                "created_at": self.rules.created_at.isoformat(),
                "updated_at": self.rules.updated_at.isoformat(),
            }
        )

        output_df = output_df[self.SNAPSHOT_COLUMNS].copy()
        output_df = output_df.sort_values(
            ["snapshot_date", "ageing_bucket", "vendor_name", "vendor_invoice_id"]
        ).reset_index(drop=True)

        return output_df

    # ------------------------------------------------------------------
    # Validation and review
    # ------------------------------------------------------------------

    def _validate_output(
        self,
        invoices_df: pd.DataFrame,
        payments_df: pd.DataFrame,
        snapshot_df: pd.DataFrame,
    ) -> None:
        is_valid, validation_logs = verify_dataset_integrity(
            df=snapshot_df,
            required_columns=self.SNAPSHOT_COLUMNS,
            unique_keys=["snapshot_pk"],
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

        if snapshot_df.empty:
            raise ValueError("AP ageing snapshot cannot be empty.")

        if snapshot_df["snapshot_pk"].duplicated().any():
            duplicate_count = int(snapshot_df["snapshot_pk"].duplicated().sum())
            raise ValueError(
                f"ap_ageing_snapshot.csv contains duplicate snapshot_pk values: {duplicate_count:,}"
            )

        if snapshot_df["vendor_invoice_id"].duplicated().any():
            duplicate_count = int(snapshot_df["vendor_invoice_id"].duplicated().sum())
            raise ValueError(
                f"ap_ageing_snapshot.csv contains duplicate vendor_invoice_id rows: {duplicate_count:,}"
            )

        invalid_buckets = set(snapshot_df["ageing_bucket"]).difference(
            self.VALID_AGEING_BUCKETS
        )

        if invalid_buckets:
            raise ValueError(f"Invalid AP ageing buckets found: {sorted(invalid_buckets)}")

        invalid_statuses = set(snapshot_df["ap_status"]).difference(
            self.VALID_AP_STATUSES
        )

        if invalid_statuses:
            raise ValueError(f"Invalid AP statuses found: {sorted(invalid_statuses)}")

        if (snapshot_df["open_amount_local"].abs() <= self.rules.rounding_tolerance).any():
            raise ValueError("AP ageing snapshot contains near-zero open local balances.")

        if (snapshot_df["open_amount_gbp"].abs() <= self.rules.rounding_tolerance).any():
            raise ValueError("AP ageing snapshot contains near-zero open GBP balances.")

        paid_invoice_ids = set(
            invoices_df.loc[
                invoices_df["payment_status"].astype(str).str.lower() == "paid",
                "vendor_invoice_id",
            ].astype(str)
        )

        snapshot_invoice_ids = set(snapshot_df["vendor_invoice_id"].astype(str))

        paid_invoices_in_snapshot = snapshot_invoice_ids.intersection(paid_invoice_ids)

        if paid_invoices_in_snapshot:
            raise ValueError(
                f"Paid vendor invoices found in AP ageing snapshot: {len(paid_invoices_in_snapshot):,}"
            )

        payment_summary_df = self._build_payment_summary(payments_df)

        full_recalc_df = invoices_df.merge(
            payment_summary_df,
            on="vendor_invoice_id",
            how="left",
        )

        full_recalc_df["paid_amount_local"] = full_recalc_df["paid_amount_local"].fillna(0.00)
        full_recalc_df["paid_amount_gbp"] = full_recalc_df["paid_amount_gbp"].fillna(0.00)
        full_recalc_df["open_amount_local"] = (
            full_recalc_df["total_local"] - full_recalc_df["paid_amount_local"]
        ).round(2)
        full_recalc_df["open_amount_gbp"] = (
            full_recalc_df["total_gbp"] - full_recalc_df["paid_amount_gbp"]
        ).round(2)

        expected_open_df = full_recalc_df[
            (full_recalc_df["open_amount_local"].abs() > self.rules.rounding_tolerance)
            | (full_recalc_df["open_amount_gbp"].abs() > self.rules.rounding_tolerance)
        ].copy()

        if len(expected_open_df) != len(snapshot_df):
            raise ValueError(
                f"AP ageing row count mismatch. Expected {len(expected_open_df):,}, "
                f"got {len(snapshot_df):,}."
            )

        if len(snapshot_df) != 87:
            logger.warning(
                "AP ageing snapshot row count is %s, not the current expected 87. "
                "This may be valid if upstream payment status generation changed.",
                f"{len(snapshot_df):,}",
            )

        logger.info("AP ageing snapshot validation passed.")

    def _log_output_review(self, snapshot_df: pd.DataFrame) -> None:
        logger.info("----- AP Ageing Snapshot Review -----")
        logger.info("AP ageing snapshot rows: %s", f"{len(snapshot_df):,}")

        logger.info(
            "Snapshot by ageing bucket:\n%s",
            snapshot_df["ageing_bucket"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Snapshot by AP status:\n%s",
            snapshot_df["ap_status"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Snapshot by currency:\n%s",
            snapshot_df["currency"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Open AP GBP by ageing bucket:\n%s",
            snapshot_df.groupby("ageing_bucket")["open_amount_gbp"]
            .sum()
            .round(2)
            .sort_index()
            .to_string(),
        )

        logger.info(
            "Total open AP GBP: %.2f",
            float(snapshot_df["open_amount_gbp"].sum()),
        )

        logger.info("----------------------------------")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> pd.DataFrame:
        logger.info("Generating Phase 3I.4 AP ageing snapshot.")

        invoices_df, payments_df = self._load_dependencies()

        snapshot_df = self._build_snapshot(
            invoices_df=invoices_df,
            payments_df=payments_df,
        )

        self._validate_output(
            invoices_df=invoices_df,
            payments_df=payments_df,
            snapshot_df=snapshot_df,
        )

        self._log_output_review(snapshot_df)

        logger.info(
            "Phase 3I.4 generation complete: %s AP ageing rows.",
            f"{len(snapshot_df):,}",
        )

        return snapshot_df

    def save(self, snapshot_df: pd.DataFrame) -> None:
        output_dir = get_raw_data_path("procurement")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / self.output_filename
        snapshot_df.to_csv(output_path, index=False, encoding="utf-8")

        logger.info("AP ageing snapshot written to %s", output_path)


def main() -> None:
    generator = APAgeingSnapshotGenerator()
    snapshot_df = generator.generate()
    generator.save(snapshot_df)

    logger.info(
        "Phase 3I.4 standalone run complete. Saved %s AP ageing rows.",
        f"{len(snapshot_df):,}",
    )


if __name__ == "__main__":
    main()