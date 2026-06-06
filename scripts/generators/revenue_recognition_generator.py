"""
revenue_recognition_generator.py

Project Atlas / Nexus Technologies
Phase 3G - Revenue Recognition & Deferred Revenue

Purpose
-------
Generates:
- revenue_recognition_schedule.csv
- deferred_revenue_rollforward.csv

Design
------
billing_invoice_lines.csv
    = billed performance obligations at invoice-line level

revenue_recognition_schedule.csv
    = detailed monthly revenue recognition schedule

deferred_revenue_rollforward.csv
    = CFO-ready deferred revenue control schedule

Core accounting principle
-------------------------
Revenue recognition is driven by performance obligations and service periods,
not cash collection timing.

Recognition basis
-----------------
Recurring SaaS and Legacy Subscription lines use daily pro-rata straight-line
recognition over the service period, with final-month residual adjustment to
ensure invoice-line parity.

Grain
-----
revenue_recognition_schedule.csv:
    One row per invoice_line_id per recognition_month.

deferred_revenue_rollforward.csv:
    One row per period_month + currency + revenue_category.
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


logger = get_logger("RevenueRecognitionGenerator", "generation_execution.log")


@dataclass(frozen=True)
class RevenueRecognitionRules:
    """Business rules for revenue recognition generation."""

    start_date: date = date(2023, 1, 1)
    end_date: date = date(2026, 6, 3)
    created_at: date = date(2026, 6, 3)
    updated_at: date = date(2026, 6, 3)
    rounding_tolerance: float = 0.05


@dataclass(frozen=True)
class RevenueRecognitionDefectRates:
    """Controlled synthetic defect rates for revenue recognition data."""

    missing_service_period: float = 0.0025
    point_in_time_misclassification: float = 0.0025
    revenue_before_service_start: float = 0.0025
    recognition_after_service_end: float = 0.0025
    over_recognised_revenue: float = 0.0025
    deferred_rollforward_mismatch: float = 0.005


class RevenueRecognitionGenerator:
    """
    Generates revenue recognition schedule and deferred revenue roll-forward.

    Inputs
    ------
    data/raw/billing/billing_invoices.csv
    data/raw/billing/billing_invoice_lines.csv

    Outputs
    -------
    data/raw/revenue/revenue_recognition_schedule.csv
    data/raw/revenue/deferred_revenue_rollforward.csv
    """

    schedule_filename = "revenue_recognition_schedule.csv"
    rollforward_filename = "deferred_revenue_rollforward.csv"

    REQUIRED_INVOICE_COLUMNS = {
        "invoice_id",
        "customer_id",
        "invoice_date",
        "currency",
        "total_local",
        "total_gbp",
        "source_system",
        "is_defect_flag",
        "defect_type",
    }

    REQUIRED_LINE_COLUMNS = {
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
        "line_amount_local",
        "line_amount_gbp",
        "currency",
        "revenue_category",
        "is_defect_flag",
        "defect_type",
    }

    SCHEDULE_COLUMNS = [
        "revenue_recognition_pk",
        "recognition_id",
        "invoice_id",
        "invoice_line_id",
        "customer_id",
        "subscription_id",
        "product_id",
        "recognition_month",
        "service_period_start",
        "service_period_end",
        "recognition_start_date",
        "recognition_end_date",
        "days_in_service_period",
        "days_recognised_in_month",
        "currency",
        "invoice_line_amount_local",
        "invoice_line_amount_gbp",
        "recognised_revenue_local",
        "recognised_revenue_gbp",
        "deferred_revenue_local_after_month",
        "deferred_revenue_gbp_after_month",
        "revenue_category",
        "recognition_method",
        "recognition_status",
        "source_system",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    ROLLFORWARD_COLUMNS = [
        "rollforward_pk",
        "period_month",
        "period_status",
        "currency",
        "revenue_category",
        "opening_deferred_revenue_local",
        "new_billings_deferred_local",
        "recognised_revenue_local",
        "closing_deferred_revenue_local",
        "opening_deferred_revenue_gbp",
        "new_billings_deferred_gbp",
        "recognised_revenue_gbp",
        "closing_deferred_revenue_gbp",
        "source_system",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    RECOGNISABLE_LINE_TYPES = {
        "Recurring SaaS",
        "Legacy Subscription",
    }

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.rng = np.random.default_rng(self.seed + 1200)

        self.rules = RevenueRecognitionRules()
        self.defect_rates = RevenueRecognitionDefectRates()

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pk(value: str) -> str:
        """Generate deterministic MD5 surrogate key."""
        return hashlib.md5(value.strip().upper().encode("utf-8")).hexdigest()

    @staticmethod
    def _round_money(value: float) -> float:
        """Stable financial rounding."""
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
        """Validate required columns exist."""
        missing_columns = required_columns.difference(df.columns)

        if missing_columns:
            raise ValueError(
                f"{dataset_name} is missing required columns: "
                f"{sorted(missing_columns)}"
            )
        
    def _stable_probability(self, value: str) -> float:
        """
        Convert a stable string key into a deterministic probability between 0 and 1.

        This avoids machine/environment-specific randomness and keeps defect
        assignment reproducible across runs.
        """
        hash_value = self._generate_pk(value)
        integer_value = int(hash_value[:12], 16)
        return (integer_value % 1_000_000) / 1_000_000    

    # ------------------------------------------------------------------
    # Loading and preparation
    # ------------------------------------------------------------------

    def _load_dependencies(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Load billing invoices and invoice lines."""
        billing_dir = get_raw_data_path("billing")

        invoices_path = billing_dir / "billing_invoices.csv"
        lines_path = billing_dir / "billing_invoice_lines.csv"

        if not invoices_path.exists():
            raise FileNotFoundError(
                f"billing_invoices.csv not found at: {invoices_path}. "
                "Run BillingInvoicesGenerator before RevenueRecognitionGenerator."
            )

        if not lines_path.exists():
            raise FileNotFoundError(
                f"billing_invoice_lines.csv not found at: {lines_path}. "
                "Run BillingInvoicesGenerator before RevenueRecognitionGenerator."
            )

        invoices_df = pd.read_csv(invoices_path)
        lines_df = pd.read_csv(lines_path)

        self._validate_input_columns(
            df=invoices_df,
            required_columns=self.REQUIRED_INVOICE_COLUMNS,
            dataset_name="billing_invoices.csv",
        )

        self._validate_input_columns(
            df=lines_df,
            required_columns=self.REQUIRED_LINE_COLUMNS,
            dataset_name="billing_invoice_lines.csv",
        )

        invoices_df = self._prepare_invoices(invoices_df)
        lines_df = self._prepare_invoice_lines(lines_df)

        logger.info(
            "Loaded revenue recognition dependencies: %s invoice headers, %s invoice lines.",
            f"{len(invoices_df):,}",
            f"{len(lines_df):,}",
        )

        return invoices_df, lines_df

    def _prepare_invoices(self, invoices_df: pd.DataFrame) -> pd.DataFrame:
        """Normalize invoice header fields."""
        df = invoices_df.copy()

        if df.empty:
            raise ValueError("billing_invoices.csv is empty.")

        df["invoice_id"] = df["invoice_id"].astype(str)
        df["customer_id"] = df["customer_id"].astype(str)
        df["currency"] = df["currency"].astype(str).str.upper()
        df["source_system"] = df["source_system"].fillna("unknown").astype(str)

        df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")

        if df["invoice_date"].isna().any():
            bad_count = int(df["invoice_date"].isna().sum())
            raise ValueError(
                f"billing_invoices.csv contains {bad_count:,} invalid invoice_date values."
            )

        for column in ["total_local", "total_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

            if df[column].isna().any():
                bad_count = int(df[column].isna().sum())
                raise ValueError(
                    f"billing_invoices.csv contains {bad_count:,} invalid {column} values."
                )

        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        return df

    def _prepare_invoice_lines(self, lines_df: pd.DataFrame) -> pd.DataFrame:
        """Normalize invoice line fields before recognition generation."""
        df = lines_df.copy()

        if df.empty:
            raise ValueError("billing_invoice_lines.csv is empty.")

        for column in [
            "invoice_line_id",
            "invoice_id",
            "subscription_id",
            "customer_id",
            "product_id",
            "line_type",
            "billing_frequency",
            "currency",
            "revenue_category",
        ]:
            df[column] = df[column].fillna("").astype(str)

        df["currency"] = df["currency"].str.upper()

        df["service_period_start"] = pd.to_datetime(
            df["service_period_start"],
            errors="coerce",
        )
        df["service_period_end"] = pd.to_datetime(
            df["service_period_end"],
            errors="coerce",
        )

        for column in ["quantity", "line_amount_local", "line_amount_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

            if df[column].isna().any():
                bad_count = int(df[column].isna().sum())
                raise ValueError(
                    f"billing_invoice_lines.csv contains {bad_count:,} invalid {column} values."
                )

        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        return df

    def _get_recognisable_lines(self, lines_df: pd.DataFrame) -> pd.DataFrame:
        """
        Return invoice lines eligible for Phase 3G recognition.

        Current scope:
        - Recurring SaaS
        - Legacy Subscription
        """
        recognisable_df = lines_df[
            lines_df["line_type"].isin(self.RECOGNISABLE_LINE_TYPES)
        ].copy()

        logger.info(
            "Recognisable invoice lines selected: %s of %s total lines.",
            f"{len(recognisable_df):,}",
            f"{len(lines_df):,}",
        )

        logger.info(
            "Recognisable lines by line_type:\n%s",
            recognisable_df["line_type"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Recognisable lines by billing_frequency:\n%s",
            recognisable_df["billing_frequency"].value_counts(dropna=False).to_string(),
        )

        return recognisable_df

    # ------------------------------------------------------------------
    # Timeline helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _month_start(value: pd.Timestamp) -> pd.Timestamp:
        """Return first day of the month for a timestamp."""
        value = pd.Timestamp(value)
        return pd.Timestamp(year=value.year, month=value.month, day=1)

    @staticmethod
    def _month_end(value: pd.Timestamp) -> pd.Timestamp:
        """Return last day of the month for a timestamp."""
        value = pd.Timestamp(value)
        return value + pd.offsets.MonthEnd(0)

    def _get_touched_months(
        self,
        service_period_start: pd.Timestamp,
        service_period_end: pd.Timestamp,
    ) -> list[pd.Timestamp]:
        """
        Return calendar month starts touched by the service period.

        Example:
        2025-01-15 to 2025-03-14
        -> [2025-01-01, 2025-02-01, 2025-03-01]
        """
        start_month = self._month_start(service_period_start)
        end_month = self._month_start(service_period_end)

        return pd.date_range(
            start=start_month,
            end=end_month,
            freq="MS",
        ).to_list()

    @staticmethod
    def _calculate_overlap_days(
        service_period_start: pd.Timestamp,
        service_period_end: pd.Timestamp,
        month_start: pd.Timestamp,
        month_end: pd.Timestamp,
    ) -> tuple[pd.Timestamp, pd.Timestamp, int]:
        """
        Calculate inclusive overlap days between service period and calendar month.
        """
        recognition_start = max(service_period_start, month_start)
        recognition_end = min(service_period_end, month_end)

        if recognition_end < recognition_start:
            return recognition_start, recognition_end, 0

        overlap_days = int((recognition_end - recognition_start).days) + 1

        return recognition_start, recognition_end, overlap_days
    
    def _get_recognition_status(self, recognition_month: pd.Timestamp) -> str:
        """Return Actual or Scheduled based on extract month."""
        extract_month = pd.Timestamp(self.rules.end_date).replace(day=1)
        recognition_month = pd.Timestamp(recognition_month).replace(day=1)

        return "Actual" if recognition_month <= extract_month else "Scheduled"

    def _build_daily_pro_rata_rows_for_line(
        self,
        line: pd.Series,
        invoice_date: pd.Timestamp,
        recognition_counter_start: int,
        defect_type: str = "",
    ) -> tuple[list[dict], int]:
        """
        Build monthly daily pro-rata recognition rows for one invoice line.

        Supports controlled schedule defects:
        - MISSING_SERVICE_PERIOD
        - POINT_IN_TIME_MISCLASSIFICATION
        - REVENUE_BEFORE_SERVICE_START
        - RECOGNITION_AFTER_SERVICE_END
        - OVER_RECOGNISED_REVENUE
        """
        invoice_line_id = str(line["invoice_line_id"])
        invoice_id = str(line["invoice_id"])

        if defect_type == "MISSING_SERVICE_PERIOD":
            # Billed line exists but receives no release path.
            return [], recognition_counter_start

        if defect_type == "POINT_IN_TIME_MISCLASSIFICATION":
            return self._build_point_in_time_row_for_line(
                line=line,
                invoice_date=invoice_date,
                recognition_counter_start=recognition_counter_start,
                defect_type=defect_type,
            )

        service_period_start = pd.Timestamp(line["service_period_start"])
        service_period_end = pd.Timestamp(line["service_period_end"])

        if pd.isna(service_period_start) or pd.isna(service_period_end):
            raise ValueError(
                f"Invoice line {invoice_line_id} has invalid service period dates."
            )

        if service_period_end < service_period_start:
            raise ValueError(
                f"Invoice line {invoice_line_id} has service_period_end before service_period_start."
            )

        target_local = self._round_money(float(line["line_amount_local"]))
        target_gbp = self._round_money(float(line["line_amount_gbp"]))

        total_service_days = int((service_period_end - service_period_start).days) + 1

        if total_service_days <= 0:
            raise ValueError(
                f"Invoice line {invoice_line_id} has non-positive service period days."
            )

        touched_months = self._get_touched_months(
            service_period_start=service_period_start,
            service_period_end=service_period_end,
        )

        if defect_type == "REVENUE_BEFORE_SERVICE_START":
            first_month = pd.Timestamp(touched_months[0])
            prior_month = first_month - pd.DateOffset(months=1)
            touched_months = [self._month_start(prior_month)] + touched_months

        if defect_type == "RECOGNITION_AFTER_SERVICE_END":
            final_month = pd.Timestamp(touched_months[-1])
            next_month = final_month + pd.DateOffset(months=1)
            touched_months = touched_months + [self._month_start(next_month)]

        if not touched_months:
            raise ValueError(
                f"Invoice line {invoice_line_id} generated no touched recognition months."
            )

        # Timing defects deliberately spread the same target value over an altered
        # month count. This isolates timing error from total-recognition parity.
        if defect_type in {
            "REVENUE_BEFORE_SERVICE_START",
            "RECOGNITION_AFTER_SERVICE_END",
        }:
            total_allocation_days = 0
            overlap_lookup: list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, int]] = []

            for month_start in touched_months:
                month_start = pd.Timestamp(month_start)
                month_end = self._month_end(month_start)

                if defect_type == "REVENUE_BEFORE_SERVICE_START" and month_start < self._month_start(service_period_start):
                    recognition_start = month_start
                    recognition_end = month_end
                    overlap_days = int((recognition_end - recognition_start).days) + 1

                elif defect_type == "RECOGNITION_AFTER_SERVICE_END" and month_start > self._month_start(service_period_end):
                    recognition_start = month_start
                    recognition_end = month_end
                    overlap_days = int((recognition_end - recognition_start).days) + 1

                else:
                    recognition_start, recognition_end, overlap_days = self._calculate_overlap_days(
                        service_period_start=service_period_start,
                        service_period_end=service_period_end,
                        month_start=month_start,
                        month_end=month_end,
                    )

                if overlap_days > 0:
                    total_allocation_days += overlap_days
                    overlap_lookup.append(
                        (month_start, recognition_start, recognition_end, overlap_days)
                    )

        else:
            total_allocation_days = total_service_days
            overlap_lookup = []

            for month_start in touched_months:
                month_start = pd.Timestamp(month_start)
                month_end = self._month_end(month_start)

                recognition_start, recognition_end, overlap_days = self._calculate_overlap_days(
                    service_period_start=service_period_start,
                    service_period_end=service_period_end,
                    month_start=month_start,
                    month_end=month_end,
                )

                if overlap_days > 0:
                    overlap_lookup.append(
                        (month_start, recognition_start, recognition_end, overlap_days)
                    )

        if total_allocation_days <= 0:
            raise ValueError(
                f"Invoice line {invoice_line_id} has non-positive allocation days."
            )

        daily_rate_local = target_local / total_allocation_days
        daily_rate_gbp = target_gbp / total_allocation_days

        recognised_local_running = 0.00
        recognised_gbp_running = 0.00

        records: list[dict] = []
        recognition_counter = recognition_counter_start

        for month_index, (
            month_start,
            recognition_start,
            recognition_end,
            overlap_days,
        ) in enumerate(overlap_lookup):
            recognition_counter += 1

            is_final_month = month_index == len(overlap_lookup) - 1

            if is_final_month:
                recognised_local = self._round_money(target_local - recognised_local_running)
                recognised_gbp = self._round_money(target_gbp - recognised_gbp_running)

                if defect_type == "OVER_RECOGNISED_REVENUE":
                    recognised_local = self._round_money(recognised_local * 1.10)
                    recognised_gbp = self._round_money(recognised_gbp * 1.10)
            else:
                recognised_local = self._round_money(daily_rate_local * overlap_days)
                recognised_gbp = self._round_money(daily_rate_gbp * overlap_days)

            recognised_local_running = self._round_money(
                recognised_local_running + recognised_local
            )
            recognised_gbp_running = self._round_money(
                recognised_gbp_running + recognised_gbp
            )

            deferred_local_after = self._round_money(target_local - recognised_local_running)
            deferred_gbp_after = self._round_money(target_gbp - recognised_gbp_running)

            recognition_id = f"REVREC-{recognition_counter:09d}"

            records.append(
                {
                    "revenue_recognition_pk": self._generate_pk(
                        f"{recognition_id}_{invoice_line_id}"
                    ),
                    "recognition_id": recognition_id,
                    "invoice_id": invoice_id,
                    "invoice_line_id": invoice_line_id,
                    "customer_id": str(line["customer_id"]),
                    "subscription_id": str(line["subscription_id"]),
                    "product_id": str(line["product_id"]),
                    "recognition_month": pd.Timestamp(month_start).strftime("%Y-%m-%d"),
                    "service_period_start": service_period_start.strftime("%Y-%m-%d"),
                    "service_period_end": service_period_end.strftime("%Y-%m-%d"),
                    "recognition_start_date": pd.Timestamp(recognition_start).strftime("%Y-%m-%d"),
                    "recognition_end_date": pd.Timestamp(recognition_end).strftime("%Y-%m-%d"),
                    "days_in_service_period": total_service_days,
                    "days_recognised_in_month": overlap_days,
                    "currency": str(line["currency"]),
                    "invoice_line_amount_local": target_local,
                    "invoice_line_amount_gbp": target_gbp,
                    "recognised_revenue_local": recognised_local,
                    "recognised_revenue_gbp": recognised_gbp,
                    "deferred_revenue_local_after_month": deferred_local_after,
                    "deferred_revenue_gbp_after_month": deferred_gbp_after,
                    "revenue_category": str(line["revenue_category"]),
                    "recognition_method": "Daily Pro-Rata Straight Line",
                    "recognition_status": self._get_recognition_status(pd.Timestamp(month_start)),
                    "source_system": "revenue_recognition_engine",
                    "is_defect_flag": int(defect_type != ""),
                    "defect_type": defect_type,
                    "created_at": self.rules.created_at.isoformat(),
                    "updated_at": self.rules.updated_at.isoformat(),
                }
            )

        return records, recognition_counter
    
    def _build_point_in_time_row_for_line(
        self,
        line: pd.Series,
        invoice_date: pd.Timestamp,
        recognition_counter_start: int,
        defect_type: str,
    ) -> tuple[list[dict], int]:
        """
        Build a single immediate recognition row for a misclassified subscription line.
        """
        recognition_counter = recognition_counter_start + 1

        invoice_line_id = str(line["invoice_line_id"])
        invoice_id = str(line["invoice_id"])

        service_period_start = pd.Timestamp(line["service_period_start"])
        service_period_end = pd.Timestamp(line["service_period_end"])

        recognition_month = pd.Timestamp(invoice_date).replace(day=1)
        recognition_id = f"REVREC-{recognition_counter:09d}"

        target_local = self._round_money(float(line["line_amount_local"]))
        target_gbp = self._round_money(float(line["line_amount_gbp"]))

        record = {
            "revenue_recognition_pk": self._generate_pk(
                f"{recognition_id}_{invoice_line_id}"
            ),
            "recognition_id": recognition_id,
            "invoice_id": invoice_id,
            "invoice_line_id": invoice_line_id,
            "customer_id": str(line["customer_id"]),
            "subscription_id": str(line["subscription_id"]),
            "product_id": str(line["product_id"]),
            "recognition_month": recognition_month.strftime("%Y-%m-%d"),
            "service_period_start": service_period_start.strftime("%Y-%m-%d"),
            "service_period_end": service_period_end.strftime("%Y-%m-%d"),
            "recognition_start_date": pd.Timestamp(invoice_date).strftime("%Y-%m-%d"),
            "recognition_end_date": pd.Timestamp(invoice_date).strftime("%Y-%m-%d"),
            "days_in_service_period": int((service_period_end - service_period_start).days) + 1,
            "days_recognised_in_month": 1,
            "currency": str(line["currency"]),
            "invoice_line_amount_local": target_local,
            "invoice_line_amount_gbp": target_gbp,
            "recognised_revenue_local": target_local,
            "recognised_revenue_gbp": target_gbp,
            "deferred_revenue_local_after_month": 0.00,
            "deferred_revenue_gbp_after_month": 0.00,
            "revenue_category": str(line["revenue_category"]),
            "recognition_method": "Point in Time",
            "recognition_status": self._get_recognition_status(recognition_month),
            "source_system": "revenue_recognition_engine",
            "is_defect_flag": 1,
            "defect_type": defect_type,
            "created_at": self.rules.created_at.isoformat(),
            "updated_at": self.rules.updated_at.isoformat(),
        }

        return [record], recognition_counter

    # ------------------------------------------------------------------
    # Defect assignment placeholder
    # ------------------------------------------------------------------

    def _assign_schedule_defects(self, invoice_lines_df: pd.DataFrame) -> dict[str, str]:
        """
        Assign mutually exclusive schedule-layer revenue recognition defects.

        Uses deterministic hash brackets so each invoice line can receive at most
        one primary schedule defect.
        """
        logger.info("Assigning Phase 3G schedule defects.")

        defect_assignments: dict[str, str] = {}

        cumulative_missing = self.defect_rates.missing_service_period
        cumulative_point_in_time = cumulative_missing + self.defect_rates.point_in_time_misclassification
        cumulative_before_start = cumulative_point_in_time + self.defect_rates.revenue_before_service_start
        cumulative_after_end = cumulative_before_start + self.defect_rates.recognition_after_service_end
        cumulative_over_recognised = cumulative_after_end + self.defect_rates.over_recognised_revenue

        for _, line in invoice_lines_df.iterrows():
            invoice_line_id = str(line["invoice_line_id"])
            probability = self._stable_probability(f"REVREC_DEFECT_{invoice_line_id}")

            if probability < cumulative_missing:
                defect_assignments[invoice_line_id] = "MISSING_SERVICE_PERIOD"

            elif probability < cumulative_point_in_time:
                defect_assignments[invoice_line_id] = "POINT_IN_TIME_MISCLASSIFICATION"

            elif probability < cumulative_before_start:
                defect_assignments[invoice_line_id] = "REVENUE_BEFORE_SERVICE_START"

            elif probability < cumulative_after_end:
                defect_assignments[invoice_line_id] = "RECOGNITION_AFTER_SERVICE_END"

            elif probability < cumulative_over_recognised:
                defect_assignments[invoice_line_id] = "OVER_RECOGNISED_REVENUE"

        if defect_assignments:
            defect_counts = pd.Series(defect_assignments).value_counts()
            logger.info(
                "Assigned schedule defects:\n%s",
                defect_counts.to_string(),
            )
        else:
            logger.info("No schedule defects assigned.")

        return defect_assignments

    # ------------------------------------------------------------------
    # Recognition schedule placeholder
    # ------------------------------------------------------------------

    def _build_recognition_schedule(
        self,
        invoice_headers_df: pd.DataFrame,
        invoice_lines_df: pd.DataFrame,
        defect_assignments: dict[str, str],
    ) -> pd.DataFrame:
        """
        Build detailed revenue recognition schedule.

        Current baseline:
        - clean daily pro-rata straight-line recognition
        - defect assignments accepted but not actively transforming behaviour yet
        """
        logger.info("Building revenue recognition schedule.")

        invoice_dates = (
            invoice_headers_df[["invoice_id", "invoice_date"]]
            .drop_duplicates(subset=["invoice_id"])
            .copy()
        )

        working_lines = invoice_lines_df.merge(
            invoice_dates,
            on="invoice_id",
            how="left",
        )

        if working_lines["invoice_date"].isna().any():
            missing_count = int(working_lines["invoice_date"].isna().sum())
            raise ValueError(
                f"Invoice date enrichment failed for {missing_count:,} invoice lines."
            )

        records: list[dict] = []
        recognition_counter = 0

        for _, line in working_lines.iterrows():
            invoice_line_id = str(line["invoice_line_id"])
            defect_type = defect_assignments.get(invoice_line_id, "")

            line_records, recognition_counter = self._build_daily_pro_rata_rows_for_line(
                line=line,
                invoice_date=pd.Timestamp(line["invoice_date"]),
                recognition_counter_start=recognition_counter,
                defect_type=defect_type,
            )

            records.extend(line_records)

        schedule_df = pd.DataFrame(records)
        schedule_df = schedule_df.reindex(columns=self.SCHEDULE_COLUMNS)

        logger.info(
            "Generated revenue recognition schedule rows: %s",
            f"{len(schedule_df):,}",
        )

        if not schedule_df.empty:
            logger.info(
                "Recognition status distribution:\n%s",
                schedule_df["recognition_status"].value_counts(dropna=False).to_string(),
            )

            logger.info(
                "Recognition rows by method:\n%s",
                schedule_df["recognition_method"].value_counts(dropna=False).to_string(),
            )

            logger.info(
                "Recognition rows by currency:\n%s",
                schedule_df["currency"].value_counts(dropna=False).to_string(),
            )

        return schedule_df

    # ------------------------------------------------------------------
    # Deferred revenue roll-forward placeholder
    # ------------------------------------------------------------------

    def _build_deferred_revenue_rollforward(
        self,
        invoice_headers_df: pd.DataFrame,
        invoice_lines_df: pd.DataFrame,
        schedule_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Build deferred revenue roll-forward as a chronological monthly ledger.

        Grain:
            period_month + currency + revenue_category

        Logic:
            opening deferred revenue
            + new billings deferred
            - recognised revenue
            = closing deferred revenue
        """
        logger.info("Building deferred revenue roll-forward.")

        if invoice_lines_df.empty:
            raise ValueError("Cannot build deferred revenue roll-forward from empty invoice lines.")

        if schedule_df.empty:
            raise ValueError("Cannot build deferred revenue roll-forward from empty recognition schedule.")

        invoice_dates = (
            invoice_headers_df[["invoice_id", "invoice_date"]]
            .drop_duplicates(subset=["invoice_id"])
            .copy()
        )

        invoice_dates["invoice_date"] = pd.to_datetime(
            invoice_dates["invoice_date"],
            errors="coerce",
        )

        if invoice_dates["invoice_date"].isna().any():
            bad_count = int(invoice_dates["invoice_date"].isna().sum())
            raise ValueError(
                f"Invoice headers contain {bad_count:,} invalid invoice_date values."
            )

        billings_df = invoice_lines_df.merge(
            invoice_dates,
            on="invoice_id",
            how="left",
        )

        if billings_df["invoice_date"].isna().any():
            missing_count = int(billings_df["invoice_date"].isna().sum())
            raise ValueError(
                f"Invoice date enrichment failed for {missing_count:,} invoice lines."
            )

        # Normalize all calendar keys to month-start timestamps.
        billings_df["invoice_month"] = (
            pd.to_datetime(billings_df["invoice_date"], errors="coerce")
            .dt.to_period("M")
            .dt.to_timestamp()
        )

        schedule_working = schedule_df.copy()
        schedule_working["recognition_month"] = (
            pd.to_datetime(schedule_working["recognition_month"], errors="coerce")
            .dt.to_period("M")
            .dt.to_timestamp()
        )

        if billings_df["invoice_month"].isna().any():
            bad_count = int(billings_df["invoice_month"].isna().sum())
            raise ValueError(
                f"Unable to derive invoice_month for {bad_count:,} invoice lines."
            )

        if schedule_working["recognition_month"].isna().any():
            bad_count = int(schedule_working["recognition_month"].isna().sum())
            raise ValueError(
                f"Unable to derive recognition_month for {bad_count:,} schedule rows."
            )

        # New billings come from invoice lines, not schedule rows.
        # This is essential because MISSING_SERVICE_PERIOD lines should still
        # create deferred revenue even if they have no recognition schedule.
        billings_agg = (
            billings_df
            .groupby(["invoice_month", "currency", "revenue_category"], as_index=False)
            .agg(
                new_billings_deferred_local=("line_amount_local", "sum"),
                new_billings_deferred_gbp=("line_amount_gbp", "sum"),
            )
        )

        billings_agg["new_billings_deferred_local"] = (
            billings_agg["new_billings_deferred_local"].round(2)
        )
        billings_agg["new_billings_deferred_gbp"] = (
            billings_agg["new_billings_deferred_gbp"].round(2)
        )

        # Revenue release comes from the recognition schedule.
        recognised_agg = (
            schedule_working
            .groupby(["recognition_month", "currency", "revenue_category"], as_index=False)
            .agg(
                recognised_revenue_local=("recognised_revenue_local", "sum"),
                recognised_revenue_gbp=("recognised_revenue_gbp", "sum"),
            )
            .rename(columns={"recognition_month": "period_month"})
        )

        recognised_agg["recognised_revenue_local"] = (
            recognised_agg["recognised_revenue_local"].round(2)
        )
        recognised_agg["recognised_revenue_gbp"] = (
            recognised_agg["recognised_revenue_gbp"].round(2)
        )

        billings_agg = billings_agg.rename(columns={"invoice_month": "period_month"})

        start_month = min(
            billings_agg["period_month"].min(),
            recognised_agg["period_month"].min(),
        )

        end_month = max(
            billings_agg["period_month"].max(),
            recognised_agg["period_month"].max(),
        )

        month_spine = pd.date_range(
            start=start_month,
            end=end_month,
            freq="MS",
        )

        currency_values = sorted(
            set(billings_df["currency"].dropna().astype(str))
            | set(schedule_working["currency"].dropna().astype(str))
        )

        revenue_category_values = sorted(
            set(billings_df["revenue_category"].dropna().astype(str))
            | set(schedule_working["revenue_category"].dropna().astype(str))
        )

        if not currency_values:
            raise ValueError("No currencies available for deferred revenue roll-forward.")

        if not revenue_category_values:
            raise ValueError("No revenue categories available for deferred revenue roll-forward.")

        spine_index = pd.MultiIndex.from_product(
            [month_spine, currency_values, revenue_category_values],
            names=["period_month", "currency", "revenue_category"],
        )

        spine_df = spine_index.to_frame(index=False)

        ledger_df = spine_df.merge(
            billings_agg,
            on=["period_month", "currency", "revenue_category"],
            how="left",
        ).merge(
            recognised_agg,
            on=["period_month", "currency", "revenue_category"],
            how="left",
        )

        amount_columns = [
            "new_billings_deferred_local",
            "new_billings_deferred_gbp",
            "recognised_revenue_local",
            "recognised_revenue_gbp",
        ]

        for column in amount_columns:
            ledger_df[column] = pd.to_numeric(
                ledger_df[column],
                errors="coerce",
            ).fillna(0.00)

        ledger_df = ledger_df.sort_values(
            ["currency", "revenue_category", "period_month"]
        ).reset_index(drop=True)

        extract_month = pd.Timestamp(self.rules.end_date).replace(day=1)

        records: list[dict] = []

        for (currency, revenue_category), group in ledger_df.groupby(
            ["currency", "revenue_category"],
            sort=True,
        ):
            opening_local = 0.00
            opening_gbp = 0.00

            group = group.sort_values("period_month")

            for _, row in group.iterrows():
                period_month = pd.Timestamp(row["period_month"])
                period_month_str = period_month.strftime("%Y-%m-%d")

                new_billings_local = self._round_money(
                    float(row["new_billings_deferred_local"])
                )
                new_billings_gbp = self._round_money(
                    float(row["new_billings_deferred_gbp"])
                )
                recognised_local = self._round_money(
                    float(row["recognised_revenue_local"])
                )
                recognised_gbp = self._round_money(
                    float(row["recognised_revenue_gbp"])
                )

                opening_local = self._round_money(opening_local)
                opening_gbp = self._round_money(opening_gbp)

                closing_local = self._round_money(
                    opening_local + new_billings_local - recognised_local
                )
                closing_gbp = self._round_money(
                    opening_gbp + new_billings_gbp - recognised_gbp
                )

                rollforward_id = (
                    f"RF-{period_month_str}-{str(currency).upper()}-"
                    f"{str(revenue_category).strip().upper().replace(' ', '_')}"
                )

                period_status = (
                    "Actual"
                    if period_month <= extract_month
                    else "Scheduled"
                )

                records.append(
                    {
                        "rollforward_pk": self._generate_pk(rollforward_id),
                        "period_month": period_month_str,
                        "period_status": period_status,
                        "currency": str(currency),
                        "revenue_category": str(revenue_category),
                        "opening_deferred_revenue_local": opening_local,
                        "new_billings_deferred_local": new_billings_local,
                        "recognised_revenue_local": recognised_local,
                        "closing_deferred_revenue_local": closing_local,
                        "opening_deferred_revenue_gbp": opening_gbp,
                        "new_billings_deferred_gbp": new_billings_gbp,
                        "recognised_revenue_gbp": recognised_gbp,
                        "closing_deferred_revenue_gbp": closing_gbp,
                        "source_system": "deferred_revenue_engine",
                        "is_defect_flag": 0,
                        "defect_type": "",
                        "created_at": self.rules.created_at.isoformat(),
                        "updated_at": self.rules.updated_at.isoformat(),
                    }
                )

                opening_local = closing_local
                opening_gbp = closing_gbp

        rollforward_df = pd.DataFrame(records)
        rollforward_df = rollforward_df.reindex(columns=self.ROLLFORWARD_COLUMNS)

        logger.info(
            "Generated deferred revenue roll-forward rows: %s",
            f"{len(rollforward_df):,}",
        )

        if not rollforward_df.empty:
            logger.info(
                "Roll-forward period status distribution:\n%s",
                rollforward_df["period_status"].value_counts(dropna=False).to_string(),
            )

            logger.info(
                "Roll-forward rows by currency:\n%s",
                rollforward_df["currency"].value_counts(dropna=False).to_string(),
            )

            logger.info(
                "Roll-forward rows by revenue_category:\n%s",
                rollforward_df["revenue_category"].value_counts(dropna=False).to_string(),
            )

            logger.info(
                "Roll-forward max period_month: %s",
                rollforward_df["period_month"].max(),
            )

        return rollforward_df

    def _inject_rollforward_defects(
        self,
        rollforward_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Inject isolated deferred revenue roll-forward mismatch defects.

        This defect is applied after the clean ledger is built. It intentionally
        breaks the roll-forward equation for selected rows only:

            opening + new billings - recognised != closing

        The defect does not cascade into future opening balances.
        """
        logger.info("Injecting roll-forward defects.")

        if rollforward_df.empty:
            return rollforward_df

        output_df = rollforward_df.copy()

        clean_candidates = output_df[
            output_df["is_defect_flag"].astype(int) == 0
        ].copy()

        if clean_candidates.empty:
            logger.warning("No clean roll-forward rows available for defect injection.")
            return output_df

        target_count = max(
            1,
            int(round(len(output_df) * self.defect_rates.deferred_rollforward_mismatch)),
        )

        target_count = min(target_count, len(clean_candidates))

        clean_candidates["stable_probability"] = clean_candidates.apply(
            lambda row: self._stable_probability(
                "ROLLFORWARD_MISMATCH_"
                f"{row['period_month']}_{row['currency']}_{row['revenue_category']}"
            ),
            axis=1,
        )

        selected_indices = (
            clean_candidates
            .sort_values("stable_probability")
            .head(target_count)
            .index
        )

        for index in selected_indices:
            row = output_df.loc[index]

            closing_local = float(row["closing_deferred_revenue_local"])
            closing_gbp = float(row["closing_deferred_revenue_gbp"])

            # Deterministic direction and magnitude based on the row key.
            row_key = (
                f"{row['period_month']}_{row['currency']}_{row['revenue_category']}"
            )
            probability = self._stable_probability(f"ROLLFORWARD_DELTA_{row_key}")

            direction = 1 if probability >= 0.50 else -1

            # Use a material but controlled break. GBP delta is fixed so the
            # audit signal is easy to detect. Local delta is adjusted in the
            # same direction using a stable multiplier to avoid identical local
            # and GBP noise on every currency.
            gbp_delta = direction * 5_000.00
            local_multiplier = 1.00 + (probability % 0.25)
            local_delta = self._round_money(gbp_delta * local_multiplier)

            output_df.at[index, "closing_deferred_revenue_local"] = self._round_money(
                closing_local + local_delta
            )
            output_df.at[index, "closing_deferred_revenue_gbp"] = self._round_money(
                closing_gbp + gbp_delta
            )
            output_df.at[index, "is_defect_flag"] = 1
            output_df.at[index, "defect_type"] = "DEFERRED_REVENUE_ROLLFORWARD_MISMATCH"

        logger.info(
            "Injected DEFERRED_REVENUE_ROLLFORWARD_MISMATCH defects: %s rows.",
            f"{len(selected_indices):,}",
        )

        return output_df

    # ------------------------------------------------------------------
    # Finalisation / validation placeholders
    # ------------------------------------------------------------------

    def _finalise_schedule(self, schedule_df: pd.DataFrame) -> pd.DataFrame:
        """Apply final schedule column order and stable sorting."""
        schedule_df = schedule_df.reindex(columns=self.SCHEDULE_COLUMNS)

        if not schedule_df.empty:
            schedule_df = schedule_df.sort_values(
                ["invoice_line_id", "recognition_month", "recognition_id"]
            ).reset_index(drop=True)

        return schedule_df

    def _finalise_rollforward(self, rollforward_df: pd.DataFrame) -> pd.DataFrame:
        """Apply final roll-forward column order and stable sorting."""
        rollforward_df = rollforward_df.reindex(columns=self.ROLLFORWARD_COLUMNS)

        if not rollforward_df.empty:
            rollforward_df = rollforward_df.sort_values(
                ["period_month", "currency", "revenue_category"]
            ).reset_index(drop=True)

        return rollforward_df

    def _validate_output(
        self,
        invoice_lines_df: pd.DataFrame,
        schedule_df: pd.DataFrame,
        rollforward_df: pd.DataFrame,
        defect_assignments: dict[str, str],
    ) -> None:
        """
        Validate Phase 3G outputs.

        Schedule validation is active. Roll-forward validation remains light until
        the ledger aggregator is implemented.
        """
        logger.info("Running Phase 3G baseline validation.")

        if invoice_lines_df.empty:
            raise ValueError("Recognisable invoice lines cannot be empty.")

        if schedule_df.empty:
            raise ValueError("Revenue recognition schedule cannot be empty.")

        if rollforward_df.empty:
            raise ValueError("Deferred revenue roll-forward cannot be empty.")

        if schedule_df["recognition_id"].duplicated().any():
            duplicate_count = int(schedule_df["recognition_id"].duplicated().sum())
            raise ValueError(
                f"Duplicate recognition_id values found: {duplicate_count:,}"
            )

        if schedule_df["revenue_recognition_pk"].duplicated().any():
            duplicate_count = int(schedule_df["revenue_recognition_pk"].duplicated().sum())
            raise ValueError(
                f"Duplicate revenue_recognition_pk values found: {duplicate_count:,}"
            )

        if schedule_df.duplicated(
            subset=["invoice_line_id", "recognition_month"]
        ).any():
            duplicate_count = int(
                schedule_df.duplicated(
                    subset=["invoice_line_id", "recognition_month"]
                ).sum()
            )
            raise ValueError(
                "Duplicate recognition rows found for invoice_line_id + recognition_month: "
                f"{duplicate_count:,}"
            )

        for column in [
            "invoice_line_amount_local",
            "invoice_line_amount_gbp",
            "recognised_revenue_local",
            "recognised_revenue_gbp",
            "deferred_revenue_local_after_month",
            "deferred_revenue_gbp_after_month",
        ]:
            numeric_values = pd.to_numeric(schedule_df[column], errors="coerce")

            if numeric_values.isna().any():
                bad_count = int(numeric_values.isna().sum())
                raise ValueError(
                    f"Schedule column {column} contains invalid numeric values: {bad_count:,}"
                )

        if (schedule_df["recognised_revenue_local"] < 0).any():
            raise ValueError("Negative recognised_revenue_local values found.")

        if (schedule_df["recognised_revenue_gbp"] < 0).any():
            raise ValueError("Negative recognised_revenue_gbp values found.")

        # Clean-line parity check.
        clean_schedule = schedule_df[schedule_df["is_defect_flag"].astype(int) == 0].copy()

        recognised_totals = (
            clean_schedule
            .groupby("invoice_line_id", as_index=False)
            .agg(
                recognised_total_local=("recognised_revenue_local", "sum"),
                recognised_total_gbp=("recognised_revenue_gbp", "sum"),
                invoice_line_amount_local=("invoice_line_amount_local", "max"),
                invoice_line_amount_gbp=("invoice_line_amount_gbp", "max"),
            )
        )

        assigned_missing_service_ids = {
            invoice_line_id
            for invoice_line_id, assigned_defect in defect_assignments.items()
            if assigned_defect == "MISSING_SERVICE_PERIOD"
        }

        scheduled_invoice_line_ids = set(schedule_df["invoice_line_id"].astype(str))

        missing_service_with_rows = assigned_missing_service_ids.intersection(
            scheduled_invoice_line_ids
        )

        if missing_service_with_rows:
            raise ValueError(
                "MISSING_SERVICE_PERIOD lines should not generate schedule rows. "
                f"Examples: {list(missing_service_with_rows)[:5]}"
            )

        non_missing_defect_ids = {
            invoice_line_id
            for invoice_line_id, assigned_defect in defect_assignments.items()
            if assigned_defect != "MISSING_SERVICE_PERIOD"
        }

        non_missing_without_rows = non_missing_defect_ids.difference(
            scheduled_invoice_line_ids
        )

        if non_missing_without_rows:
            raise ValueError(
                "Non-missing-service defect lines should generate schedule rows. "
                f"Examples: {list(non_missing_without_rows)[:5]}"
            )

        logger.info(
            "Missing service period validation passed: %s assigned lines generated no schedule rows.",
            f"{len(assigned_missing_service_ids):,}",
        )

        # Defect behaviour checks.
        defective_schedule = schedule_df[
            schedule_df["is_defect_flag"].astype(int) == 1
        ].copy()

        if not defective_schedule.empty:
            logger.info(
                "Schedule defect distribution:\n%s",
                defective_schedule["defect_type"].value_counts(dropna=False).to_string(),
            )

        point_in_time_rows = defective_schedule[
            defective_schedule["defect_type"].eq("POINT_IN_TIME_MISCLASSIFICATION")
        ]

        if not point_in_time_rows.empty:
            point_counts = point_in_time_rows.groupby("invoice_line_id").size()
            if (point_counts != 1).any():
                raise ValueError(
                    "POINT_IN_TIME_MISCLASSIFICATION lines must generate exactly one schedule row."
                )

            point_amounts = (
                point_in_time_rows
                .groupby("invoice_line_id", as_index=False)
                .agg(
                    recognised_total_gbp=("recognised_revenue_gbp", "sum"),
                    invoice_line_amount_gbp=("invoice_line_amount_gbp", "max"),
                )
            )

            point_delta = (
                point_amounts["recognised_total_gbp"]
                - point_amounts["invoice_line_amount_gbp"]
            ).abs()

            if (point_delta > self.rules.rounding_tolerance).any():
                raise ValueError(
                    "POINT_IN_TIME_MISCLASSIFICATION rows must recognise full line amount."
                )

        over_recognised_rows = defective_schedule[
            defective_schedule["defect_type"].eq("OVER_RECOGNISED_REVENUE")
        ]

        if not over_recognised_rows.empty:
            over_totals = (
                over_recognised_rows
                .groupby("invoice_line_id", as_index=False)
                .agg(
                    recognised_total_gbp=("recognised_revenue_gbp", "sum"),
                    invoice_line_amount_gbp=("invoice_line_amount_gbp", "max"),
                )
            )

            bad_over = over_totals[
                over_totals["recognised_total_gbp"]
                <= over_totals["invoice_line_amount_gbp"]
            ]

            if not bad_over.empty:
                raise ValueError(
                    "OVER_RECOGNISED_REVENUE rows must recognise more than the invoice line amount."
                )

        before_start_rows = defective_schedule[
            defective_schedule["defect_type"].eq("REVENUE_BEFORE_SERVICE_START")
        ].copy()

        if not before_start_rows.empty:
            before_start_rows["recognition_start_date_check"] = pd.to_datetime(
                before_start_rows["recognition_start_date"],
                errors="coerce",
            )
            before_start_rows["service_period_start_check"] = pd.to_datetime(
                before_start_rows["service_period_start"],
                errors="coerce",
            )

            if not (
                before_start_rows["recognition_start_date_check"]
                < before_start_rows["service_period_start_check"]
            ).any():
                raise ValueError(
                    "REVENUE_BEFORE_SERVICE_START must create at least one row before service_period_start."
                )

        after_end_rows = defective_schedule[
            defective_schedule["defect_type"].eq("RECOGNITION_AFTER_SERVICE_END")
        ].copy()

        if not after_end_rows.empty:
            after_end_rows["recognition_end_date_check"] = pd.to_datetime(
                after_end_rows["recognition_end_date"],
                errors="coerce",
            )
            after_end_rows["service_period_end_check"] = pd.to_datetime(
                after_end_rows["service_period_end"],
                errors="coerce",
            )

            if not (
                after_end_rows["recognition_end_date_check"]
                > after_end_rows["service_period_end_check"]
            ).any():
                raise ValueError(
                    "RECOGNITION_AFTER_SERVICE_END must create at least one row after service_period_end."
                )

        local_delta = (
            recognised_totals["recognised_total_local"]
            - recognised_totals["invoice_line_amount_local"]
        ).abs()

        gbp_delta = (
            recognised_totals["recognised_total_gbp"]
            - recognised_totals["invoice_line_amount_gbp"]
        ).abs()

        if (local_delta > self.rules.rounding_tolerance).any():
            bad_count = int((local_delta > self.rules.rounding_tolerance).sum())
            raise ValueError(
                f"Clean schedule local parity failed for {bad_count:,} invoice lines."
            )

        if (gbp_delta > self.rules.rounding_tolerance).any():
            bad_count = int((gbp_delta > self.rules.rounding_tolerance).sum())
            raise ValueError(
                f"Clean schedule GBP parity failed for {bad_count:,} invoice lines."
            )
        
        if rollforward_df["rollforward_pk"].duplicated().any():
            duplicate_count = int(rollforward_df["rollforward_pk"].duplicated().sum())
            raise ValueError(
                f"Duplicate rollforward_pk values found: {duplicate_count:,}"
            )

        if rollforward_df.duplicated(
            subset=["period_month", "currency", "revenue_category"]
        ).any():
            duplicate_count = int(
                rollforward_df.duplicated(
                    subset=["period_month", "currency", "revenue_category"]
                ).sum()
            )
            raise ValueError(
                "Duplicate roll-forward business keys found for "
                "period_month + currency + revenue_category: "
                f"{duplicate_count:,}"
            )

        rollforward_working = rollforward_df.copy()

        for column in [
            "opening_deferred_revenue_local",
            "new_billings_deferred_local",
            "recognised_revenue_local",
            "closing_deferred_revenue_local",
            "opening_deferred_revenue_gbp",
            "new_billings_deferred_gbp",
            "recognised_revenue_gbp",
            "closing_deferred_revenue_gbp",
        ]:
            rollforward_working[column] = pd.to_numeric(
                rollforward_working[column],
                errors="coerce",
            )

            if rollforward_working[column].isna().any():
                bad_count = int(rollforward_working[column].isna().sum())
                raise ValueError(
                    f"Roll-forward column {column} contains invalid numeric values: {bad_count:,}"
                )

        clean_rollforward = rollforward_working[
            rollforward_working["is_defect_flag"].astype(int) == 0
        ].copy()

        local_recon_delta = (
            clean_rollforward["opening_deferred_revenue_local"]
            + clean_rollforward["new_billings_deferred_local"]
            - clean_rollforward["recognised_revenue_local"]
            - clean_rollforward["closing_deferred_revenue_local"]
        ).abs()

        gbp_recon_delta = (
            clean_rollforward["opening_deferred_revenue_gbp"]
            + clean_rollforward["new_billings_deferred_gbp"]
            - clean_rollforward["recognised_revenue_gbp"]
            - clean_rollforward["closing_deferred_revenue_gbp"]
        ).abs()

        if (local_recon_delta > self.rules.rounding_tolerance).any():
            bad_count = int((local_recon_delta > self.rules.rounding_tolerance).sum())
            raise ValueError(
                f"Clean roll-forward local equation failed for {bad_count:,} rows."
            )

        if (gbp_recon_delta > self.rules.rounding_tolerance).any():
            bad_count = int((gbp_recon_delta > self.rules.rounding_tolerance).sum())
            raise ValueError(
                f"Clean roll-forward GBP equation failed for {bad_count:,} rows."
            )
        
        # --- Defective Roll-forward Equation Validation ---
        mismatch_rows = rollforward_working[
            rollforward_working["defect_type"].eq(
                "DEFERRED_REVENUE_ROLLFORWARD_MISMATCH"
            )
        ].copy()

        if not mismatch_rows.empty:
            mismatch_local_delta = (
                mismatch_rows["opening_deferred_revenue_local"]
                + mismatch_rows["new_billings_deferred_local"]
                - mismatch_rows["recognised_revenue_local"]
                - mismatch_rows["closing_deferred_revenue_local"]
            ).abs()

            mismatch_gbp_delta = (
                mismatch_rows["opening_deferred_revenue_gbp"]
                + mismatch_rows["new_billings_deferred_gbp"]
                - mismatch_rows["recognised_revenue_gbp"]
                - mismatch_rows["closing_deferred_revenue_gbp"]
            ).abs()

            mismatch_passes_equation = (
                (mismatch_local_delta <= self.rules.rounding_tolerance)
                & (mismatch_gbp_delta <= self.rules.rounding_tolerance)
            )

            if mismatch_passes_equation.any():
                bad_count = int(mismatch_passes_equation.sum())
                raise ValueError(
                    "DEFERRED_REVENUE_ROLLFORWARD_MISMATCH rows should fail "
                    f"the roll-forward equation. Bad rows: {bad_count:,}"
                )

            logger.info(
                "Roll-forward mismatch validation passed: %s defective rows intentionally break the equation.",
                f"{len(mismatch_rows):,}",
            )

        # --- Carry-forward Continuity Loop ---
        carry_forward_breaks = []

        for (currency, revenue_category), group in rollforward_working.groupby(
            ["currency", "revenue_category"],
            sort=True,
        ):
            group = group.sort_values("period_month").copy()

            group["prior_closing_local"] = group["closing_deferred_revenue_local"].shift(1)
            group["prior_closing_gbp"] = group["closing_deferred_revenue_gbp"].shift(1)
            group["prior_is_defect_flag"] = group["is_defect_flag"].astype(int).shift(1)

            comparable_rows = group[
                (group["is_defect_flag"].astype(int) == 0)
                & (group["prior_is_defect_flag"].fillna(0).astype(int) == 0)
                & group["prior_closing_local"].notna()
                & group["prior_closing_gbp"].notna()
            ].copy()

            if comparable_rows.empty:
                continue

            local_break_mask = (
                comparable_rows["opening_deferred_revenue_local"]
                - comparable_rows["prior_closing_local"]
            ).abs() > self.rules.rounding_tolerance

            gbp_break_mask = (
                comparable_rows["opening_deferred_revenue_gbp"]
                - comparable_rows["prior_closing_gbp"]
            ).abs() > self.rules.rounding_tolerance

            if local_break_mask.any() or gbp_break_mask.any():
                carry_forward_breaks.append(
                    {
                        "currency": currency,
                        "revenue_category": revenue_category,
                        "local_breaks": int(local_break_mask.sum()),
                        "gbp_breaks": int(gbp_break_mask.sum()),
                    }
                )

        if carry_forward_breaks:
            raise ValueError(
                f"Roll-forward carry-forward continuity failed: {carry_forward_breaks[:5]}"
            )

        logger.info("Phase 3G schedule and roll-forward validation passed.")

    def _log_output_review(
        self,
        schedule_df: pd.DataFrame,
        rollforward_df: pd.DataFrame,
    ) -> None:
        """Log useful QA summaries."""
        logger.info("----- Revenue Recognition Output Review -----")
        logger.info("Recognition schedule rows: %s", f"{len(schedule_df):,}")
        logger.info("Deferred revenue roll-forward rows: %s", f"{len(rollforward_df):,}")

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Generate revenue recognition schedule and deferred revenue roll-forward."""
        logger.info("Generating Phase 3G revenue recognition and deferred revenue.")

        invoice_headers_df, invoice_lines_df = self._load_dependencies()

        recognisable_lines_df = self._get_recognisable_lines(invoice_lines_df)

        defect_assignments = self._assign_schedule_defects(recognisable_lines_df)

        schedule_df = self._build_recognition_schedule(
            invoice_headers_df=invoice_headers_df,
            invoice_lines_df=recognisable_lines_df,
            defect_assignments=defect_assignments,
        )

        rollforward_df = self._build_deferred_revenue_rollforward(
            invoice_headers_df=invoice_headers_df,
            invoice_lines_df=recognisable_lines_df,
            schedule_df=schedule_df,
        )

        rollforward_df = self._inject_rollforward_defects(rollforward_df)

        schedule_df = self._finalise_schedule(schedule_df)
        rollforward_df = self._finalise_rollforward(rollforward_df)

        self._validate_output(
            invoice_lines_df=recognisable_lines_df,
            schedule_df=schedule_df,
            rollforward_df=rollforward_df,
            defect_assignments=defect_assignments,
        )

        self._log_output_review(schedule_df, rollforward_df)

        logger.info(
            "Phase 3G baseline generation complete: %s schedule rows, %s roll-forward rows.",
            f"{len(schedule_df):,}",
            f"{len(rollforward_df):,}",
        )

        return schedule_df, rollforward_df

    def save(
        self,
        schedule_df: pd.DataFrame,
        rollforward_df: pd.DataFrame,
    ) -> None:
        """Save Phase 3G outputs."""
        output_dir = get_raw_data_path("revenue")
        output_dir.mkdir(parents=True, exist_ok=True)

        schedule_path = output_dir / self.schedule_filename
        rollforward_path = output_dir / self.rollforward_filename

        schedule_df.to_csv(schedule_path, index=False, encoding="utf-8")
        rollforward_df.to_csv(rollforward_path, index=False, encoding="utf-8")

        logger.info("Revenue recognition schedule written to %s", schedule_path)
        logger.info("Deferred revenue roll-forward written to %s", rollforward_path)


def main() -> None:
    generator = RevenueRecognitionGenerator()
    schedule_df, rollforward_df = generator.generate()
    generator.save(schedule_df, rollforward_df)

    logger.info(
        "Phase 3G standalone run complete. Saved %s schedule rows and %s roll-forward rows.",
    )

if __name__ == "__main__":
    main()