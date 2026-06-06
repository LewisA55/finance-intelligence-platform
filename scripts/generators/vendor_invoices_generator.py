"""
vendor_invoices_generator.py

Project Atlas / Nexus Technologies
Phase 3I.2 - Vendor Invoices & Vendor Invoice Lines

Purpose
-------
Generates:
- data/raw/procurement/vendor_invoices.csv
- data/raw/procurement/vendor_invoice_lines.csv

This layer builds the Procure-to-Pay vendor invoice subledger for Nexus Technologies.

Design
------
vendors.csv
    = vendor master

vendor_invoices.csv
    = AP invoice header grain

vendor_invoice_lines.csv
    = AP invoice line grain

Core accounting principle
-------------------------
Vendor spend is recorded based on supplier invoice documents and service periods.

This generator intentionally embeds controlled AP audit defects:
- AP_CUTOFF_FAILURE
- DUPLICATE_VENDOR_INVOICE

These are labelled for synthetic validation, but downstream dbt tests should
detect them through business logic rather than relying on the defect labels.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path
from scripts.utils.validation import raise_if_invalid, verify_dataset_integrity


logger = get_logger("VendorInvoicesGenerator", "generation_execution.log")


@dataclass(frozen=True)
class VendorInvoiceRules:
    """Business rules for vendor invoice generation."""

    start_date: date = date(2023, 1, 1)
    end_date: date = date(2026, 6, 3)
    created_at: date = date(2026, 6, 3)
    updated_at: date = date(2026, 6, 3)
    tax_rate_gbp: float = 0.20
    tax_rate_eur: float = 0.19
    tax_rate_usd: float = 0.00
    tax_rate_sgd: float = 0.09


class VendorInvoicesGenerator:
    """
    Generates vendor invoice headers and vendor invoice lines.

    Inputs
    ------
    data/raw/procurement/vendors.csv
    data/raw/fx/exchange_rates_2022_2026.csv

    Outputs
    -------
    data/raw/procurement/vendor_invoices.csv
    data/raw/procurement/vendor_invoice_lines.csv
    """

    header_filename = "vendor_invoices.csv"
    lines_filename = "vendor_invoice_lines.csv"

    REQUIRED_VENDOR_COLUMNS = {
        "vendor_id",
        "vendor_name",
        "vendor_category",
        "currency",
        "payment_terms",
        "default_account_code",
        "is_recurring_vendor",
        "is_strategic_vendor",
        "vendor_status",
        "approval_status",
    }

    REQUIRED_FX_COLUMNS = {
        "currency_code",
        "month_start_date",
        "monthly_average_rate_to_gbp",
    }

    HEADER_COLUMNS = [
        "vendor_invoice_pk",
        "vendor_invoice_id",
        "vendor_id",
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "due_date",
        "posting_date",
        "posting_period",
        "currency",
        "subtotal_local",
        "tax_rate",
        "tax_amount_local",
        "total_local",
        "subtotal_gbp",
        "tax_amount_gbp",
        "total_gbp",
        "payment_status",
        "source_system",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    LINE_COLUMNS = [
        "vendor_invoice_line_pk",
        "vendor_invoice_line_id",
        "vendor_invoice_id",
        "vendor_id",
        "vendor_name",
        "line_number",
        "account_code",
        "expense_category",
        "service_period_start",
        "service_period_end",
        "line_description",
        "line_amount_local",
        "line_amount_gbp",
        "source_system",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    RECURRING_VENDOR_BASE_AMOUNTS_GBP = {
        "Amazon Web Services": 72_000.00,
        "Google Cloud": 38_000.00,
        "Snowflake": 42_000.00,
        "Microsoft": 18_000.00,
        "Salesforce": 24_000.00,
        "HubSpot": 12_500.00,
        "Slack": 4_800.00,
        "GitHub": 3_200.00,
        "WeWork": 16_000.00,
        "Intercom": 6_500.00,
        "Zendesk": 5_800.00,
    }

    VARIABLE_VENDOR_AMOUNT_RANGES_GBP = {
        "Marketing": (8_000.00, 65_000.00),
        "Professional Fees": (15_000.00, 120_000.00),
        "Recruitment": (6_000.00, 35_000.00),
        "Travel": (2_000.00, 18_000.00),
        "Fixed Assets": (10_000.00, 80_000.00),
        "Facilities": (3_000.00, 22_000.00),
        "Customer Support": (4_000.00, 20_000.00),
        "Software / SaaS Tools": (3_000.00, 40_000.00),
        "Payment Processing": (8_000.00, 55_000.00),
        "Cloud Infrastructure": (15_000.00, 100_000.00),
    }

    SOURCE_SYSTEM = "nexus_ap_platform"

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.rng = np.random.default_rng(self.seed + 1500)
        self.rules = VendorInvoiceRules()

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
        """Validate required input columns exist."""
        missing_columns = required_columns.difference(df.columns)

        if missing_columns:
            raise ValueError(
                f"{dataset_name} is missing required columns: {sorted(missing_columns)}"
            )

    @staticmethod
    def _month_start(value: pd.Timestamp) -> pd.Timestamp:
        value = pd.Timestamp(value)
        return pd.Timestamp(year=value.year, month=value.month, day=1)

    @staticmethod
    def _month_end(value: pd.Timestamp) -> pd.Timestamp:
        return pd.Timestamp(value) + pd.offsets.MonthEnd(0)

    def _calculate_due_date(
        self,
        invoice_date: pd.Timestamp,
        payment_terms: str,
    ) -> pd.Timestamp:
        """Calculate due date from vendor payment terms."""
        terms = str(payment_terms).strip().lower()

        if "immediate" in terms or "receipt" in terms:
            return invoice_date

        if "60" in terms:
            return invoice_date + pd.Timedelta(days=60)

        if "45" in terms:
            return invoice_date + pd.Timedelta(days=45)

        if "30" in terms:
            return invoice_date + pd.Timedelta(days=30)

        if "15" in terms:
            return invoice_date + pd.Timedelta(days=15)

        return invoice_date + pd.Timedelta(days=30)

    def _get_tax_rate(self, currency: str) -> float:
        """Apply simplified regional supplier tax logic."""
        currency = str(currency).upper()

        if currency == "GBP":
            return self.rules.tax_rate_gbp

        if currency == "EUR":
            return self.rules.tax_rate_eur

        if currency == "SGD":
            return self.rules.tax_rate_sgd

        if currency == "USD":
            return self.rules.tax_rate_usd

        return 0.00

    def _get_payment_status(self, due_date: pd.Timestamp) -> str:
        """
        Assign provisional AP payment status.

        Vendor payments are generated in Phase 3I.3.
        """
        extract_date = pd.Timestamp(self.rules.end_date)

        if due_date > extract_date:
            return "Open"

        days_overdue = int((extract_date - due_date).days)

        if days_overdue <= 0:
            return "Open"

        if self.rng.random() < 0.94:
            return "Paid"

        return "Overdue"

    def _local_from_gbp(
        self,
        amount_gbp: float,
        currency: str,
        invoice_date: pd.Timestamp,
        fx_lookup: dict[tuple[str, str], float],
    ) -> float:
        """
        Convert GBP planning amount into vendor local currency.

        If amount_gbp = amount_local / FX rate,
        then amount_local = amount_gbp * FX rate.
        """
        currency = str(currency).upper()
        month_key = self._month_start(invoice_date).strftime("%Y-%m-%d")

        rate = fx_lookup.get((currency, month_key))

        if rate is None:
            raise ValueError(
                f"Missing FX rate for currency={currency}, month_start_date={month_key}"
            )

        return self._round_money(float(amount_gbp) * float(rate))

    def _convert_local_to_gbp(
        self,
        amount_local: float,
        currency: str,
        invoice_date: pd.Timestamp,
        fx_lookup: dict[tuple[str, str], float],
    ) -> float:
        """Convert vendor local amount into GBP using monthly average FX rate."""
        currency = str(currency).upper()
        month_key = self._month_start(invoice_date).strftime("%Y-%m-%d")

        rate = fx_lookup.get((currency, month_key))

        if rate is None:
            raise ValueError(
                f"Missing FX rate for currency={currency}, month_start_date={month_key}"
            )

        return self._round_money(float(amount_local) / float(rate))

    # ------------------------------------------------------------------
    # Dependency loading
    # ------------------------------------------------------------------

    def _load_vendors(self) -> pd.DataFrame:
        path = get_raw_data_path("procurement") / "vendors.csv"

        if not path.exists():
            raise FileNotFoundError(
                f"vendors.csv not found at: {path}. "
                "Run VendorsGenerator before VendorInvoicesGenerator."
            )

        df = pd.read_csv(path)

        self._validate_input_columns(
            df=df,
            required_columns=self.REQUIRED_VENDOR_COLUMNS,
            dataset_name="vendors.csv",
        )

        df["vendor_id"] = df["vendor_id"].astype(str)
        df["vendor_name"] = df["vendor_name"].astype(str)
        df["vendor_category"] = df["vendor_category"].astype(str)
        df["currency"] = df["currency"].astype(str).str.upper()
        df["payment_terms"] = df["payment_terms"].astype(str)
        df["default_account_code"] = df["default_account_code"].astype(str)

        for column in ["is_recurring_vendor", "is_strategic_vendor"]:
            df[column] = df[column].apply(
                lambda x: self._normalise_bool_int(x, default=0)
            )

        df["vendor_status"] = df["vendor_status"].fillna("Active").astype(str)
        df["approval_status"] = df["approval_status"].fillna("Approved").astype(str)

        df = df[
            (df["vendor_status"].str.lower() == "active")
            & (df["approval_status"].str.lower() == "approved")
        ].copy()

        if df.empty:
            raise ValueError("vendors.csv contains no active approved vendors.")

        return df

    def _load_fx_rates(self) -> pd.DataFrame:
        path = get_raw_data_path("fx") / "exchange_rates_2022_2026.csv"

        if not path.exists():
            raise FileNotFoundError(
                f"exchange_rates_2022_2026.csv not found at: {path}. "
                "Run FXRateGenerator before VendorInvoicesGenerator."
            )

        df = pd.read_csv(path)

        self._validate_input_columns(
            df=df,
            required_columns=self.REQUIRED_FX_COLUMNS,
            dataset_name="exchange_rates_2022_2026.csv",
        )

        df["currency_code"] = df["currency_code"].astype(str).str.upper()
        df["month_start_date"] = (
            pd.to_datetime(df["month_start_date"], errors="coerce")
            .dt.strftime("%Y-%m-%d")
        )
        df["monthly_average_rate_to_gbp"] = pd.to_numeric(
            df["monthly_average_rate_to_gbp"],
            errors="coerce",
        )

        if df["month_start_date"].isna().any():
            raise ValueError("exchange_rates_2022_2026.csv contains invalid month_start_date values.")

        if df["monthly_average_rate_to_gbp"].isna().any():
            raise ValueError(
                "exchange_rates_2022_2026.csv contains invalid monthly_average_rate_to_gbp values."
            )

        return df

    @staticmethod
    def _prepare_fx_lookup(fx_df: pd.DataFrame) -> dict[tuple[str, str], float]:
        """Prepare currency/month FX lookup."""
        return {
            (str(row["currency_code"]).upper(), str(row["month_start_date"])): float(
                row["monthly_average_rate_to_gbp"]
            )
            for _, row in fx_df.iterrows()
        }

    def _load_dependencies(self) -> tuple[pd.DataFrame, dict[tuple[str, str], float]]:
        vendors_df = self._load_vendors()
        fx_df = self._load_fx_rates()
        fx_lookup = self._prepare_fx_lookup(fx_df)

        logger.info(
            "Loaded AP invoice dependencies: %s vendors, %s FX rate rows.",
            f"{len(vendors_df):,}",
            f"{len(fx_df):,}",
        )

        return vendors_df, fx_lookup

    # ------------------------------------------------------------------
    # Base invoice event generation
    # ------------------------------------------------------------------

    def _generate_invoice_id(
        self,
        vendor_id: str,
        invoice_date: pd.Timestamp,
        sequence: int,
    ) -> str:
        return f"VINV-{vendor_id}-{invoice_date.strftime('%Y%m%d')}-{sequence:05d}"

    def _generate_line_id(
        self,
        vendor_invoice_id: str,
        line_number: int,
    ) -> str:
        return f"{vendor_invoice_id}-LINE-{line_number:03d}"

    def _build_header_and_line(
        self,
        vendor: pd.Series,
        invoice_date: pd.Timestamp,
        posting_date: pd.Timestamp,
        service_period_start: pd.Timestamp,
        service_period_end: pd.Timestamp,
        amount_gbp_planning: float,
        sequence: int,
        invoice_number: str | None = None,
        line_description: str | None = None,
        is_defect_flag: int = 0,
        defect_type: str = "",
        fx_lookup: dict[tuple[str, str], float] | None = None,
    ) -> tuple[dict, dict]:
        """Build one AP invoice header and one invoice line."""

        if fx_lookup is None:
            raise ValueError("fx_lookup must be provided.")

        vendor_id = str(vendor["vendor_id"])
        vendor_name = str(vendor["vendor_name"])
        currency = str(vendor["currency"]).upper()
        payment_terms = str(vendor["payment_terms"])
        account_code = str(vendor["default_account_code"])
        expense_category = str(vendor["vendor_category"])

        vendor_invoice_id = self._generate_invoice_id(
            vendor_id=vendor_id,
            invoice_date=invoice_date,
            sequence=sequence,
        )

        if invoice_number is None:
            invoice_number = f"INV-{vendor_id}-{invoice_date.strftime('%Y%m')}"

        due_date = self._calculate_due_date(invoice_date, payment_terms)
        tax_rate = self._get_tax_rate(currency)

        subtotal_local = self._local_from_gbp(
            amount_gbp=amount_gbp_planning,
            currency=currency,
            invoice_date=invoice_date,
            fx_lookup=fx_lookup,
        )
        tax_amount_local = self._round_money(subtotal_local * tax_rate)
        total_local = self._round_money(subtotal_local + tax_amount_local)

        subtotal_gbp = self._convert_local_to_gbp(
            amount_local=subtotal_local,
            currency=currency,
            invoice_date=invoice_date,
            fx_lookup=fx_lookup,
        )
        tax_amount_gbp = self._convert_local_to_gbp(
            amount_local=tax_amount_local,
            currency=currency,
            invoice_date=invoice_date,
            fx_lookup=fx_lookup,
        )
        total_gbp = self._round_money(subtotal_gbp + tax_amount_gbp)

        payment_status = self._get_payment_status(due_date)

        header = {
            "vendor_invoice_pk": self._generate_pk(vendor_invoice_id),
            "vendor_invoice_id": vendor_invoice_id,
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date.date().isoformat(),
            "due_date": due_date.date().isoformat(),
            "posting_date": posting_date.date().isoformat(),
            "posting_period": posting_date.strftime("%Y-%m"),
            "currency": currency,
            "subtotal_local": subtotal_local,
            "tax_rate": tax_rate,
            "tax_amount_local": tax_amount_local,
            "total_local": total_local,
            "subtotal_gbp": subtotal_gbp,
            "tax_amount_gbp": tax_amount_gbp,
            "total_gbp": total_gbp,
            "payment_status": payment_status,
            "source_system": self.SOURCE_SYSTEM,
            "is_defect_flag": int(is_defect_flag),
            "defect_type": defect_type,
            "created_at": self.rules.created_at.isoformat(),
            "updated_at": self.rules.updated_at.isoformat(),
        }

        vendor_invoice_line_id = self._generate_line_id(vendor_invoice_id, 1)

        if line_description is None:
            line_description = f"{vendor_name} {expense_category} services"

        line = {
            "vendor_invoice_line_pk": self._generate_pk(vendor_invoice_line_id),
            "vendor_invoice_line_id": vendor_invoice_line_id,
            "vendor_invoice_id": vendor_invoice_id,
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "line_number": 1,
            "account_code": account_code,
            "expense_category": expense_category,
            "service_period_start": service_period_start.date().isoformat(),
            "service_period_end": service_period_end.date().isoformat(),
            "line_description": line_description,
            "line_amount_local": subtotal_local,
            "line_amount_gbp": subtotal_gbp,
            "source_system": self.SOURCE_SYSTEM,
            "is_defect_flag": int(is_defect_flag),
            "defect_type": defect_type,
            "created_at": self.rules.created_at.isoformat(),
            "updated_at": self.rules.updated_at.isoformat(),
        }

        return header, line

    def _generate_recurring_invoices(
        self,
        vendors_df: pd.DataFrame,
        fx_lookup: dict[tuple[str, str], float],
    ) -> tuple[list[dict], list[dict]]:
        """Generate monthly recurring vendor invoices."""

        headers: list[dict] = []
        lines: list[dict] = []

        recurring_vendors = vendors_df[vendors_df["is_recurring_vendor"] == 1].copy()

        month_spine = pd.date_range(
            start=pd.Timestamp(self.rules.start_date),
            end=pd.Timestamp(self.rules.end_date),
            freq="MS",
        )

        sequence = 1

        for _, vendor in recurring_vendors.iterrows():
            vendor_name = str(vendor["vendor_name"])
            base_amount_gbp = self.RECURRING_VENDOR_BASE_AMOUNTS_GBP.get(
                vendor_name,
                self._derive_default_recurring_amount(vendor),
            )

            for month_index, month_start in enumerate(month_spine):
                service_period_start = month_start
                service_period_end = self._month_end(month_start)

                # Normal recurring AP invoice arrives near month-end or shortly after.
                invoice_offset_days = int(self.rng.integers(0, 6))
                invoice_date = service_period_end + pd.Timedelta(days=invoice_offset_days)

                if invoice_date > pd.Timestamp(self.rules.end_date):
                    continue

                posting_date = invoice_date

                # Scale recurring costs as Nexus grows.
                growth_factor = 1 + (month_index * self.rng.uniform(0.003, 0.012))
                seasonal_noise = self.rng.normal(loc=1.0, scale=0.045)
                amount_gbp = self._round_money(base_amount_gbp * growth_factor * seasonal_noise)

                header, line = self._build_header_and_line(
                    vendor=vendor,
                    invoice_date=invoice_date,
                    posting_date=posting_date,
                    service_period_start=service_period_start,
                    service_period_end=service_period_end,
                    amount_gbp_planning=amount_gbp,
                    sequence=sequence,
                    fx_lookup=fx_lookup,
                )

                headers.append(header)
                lines.append(line)
                sequence += 1

        return headers, lines

    def _generate_variable_invoices(
        self,
        vendors_df: pd.DataFrame,
        fx_lookup: dict[tuple[str, str], float],
        starting_sequence: int,
    ) -> tuple[list[dict], list[dict]]:
        """Generate ad-hoc and variable vendor invoices."""

        headers: list[dict] = []
        lines: list[dict] = []
        sequence = starting_sequence

        variable_vendors = vendors_df[vendors_df["is_recurring_vendor"] == 0].copy()

        month_spine = pd.date_range(
            start=pd.Timestamp(self.rules.start_date),
            end=pd.Timestamp(self.rules.end_date),
            freq="MS",
        )

        for _, vendor in variable_vendors.iterrows():
            category = str(vendor["vendor_category"])

            if category in {"Professional Fees", "Marketing"}:
                invoice_probability = 0.45
            elif category in {"Recruitment", "Fixed Assets"}:
                invoice_probability = 0.20
            elif category in {"Travel", "Facilities"}:
                invoice_probability = 0.28
            else:
                invoice_probability = 0.25

            low_gbp, high_gbp = self.VARIABLE_VENDOR_AMOUNT_RANGES_GBP.get(
                category,
                (3_000.00, 25_000.00),
            )

            for month_start in month_spine:
                if self.rng.random() > invoice_probability:
                    continue

                service_period_start = month_start
                service_period_end = self._month_end(month_start)

                invoice_day = int(self.rng.integers(5, min(26, service_period_end.day) + 1))
                invoice_date = pd.Timestamp(
                    year=month_start.year,
                    month=month_start.month,
                    day=invoice_day,
                )

                if invoice_date > pd.Timestamp(self.rules.end_date):
                    continue

                posting_date = invoice_date

                amount_gbp = self._round_money(
                    float(self.rng.uniform(low_gbp, high_gbp))
                )

                header, line = self._build_header_and_line(
                    vendor=vendor,
                    invoice_date=invoice_date,
                    posting_date=posting_date,
                    service_period_start=service_period_start,
                    service_period_end=service_period_end,
                    amount_gbp_planning=amount_gbp,
                    sequence=sequence,
                    fx_lookup=fx_lookup,
                )

                headers.append(header)
                lines.append(line)
                sequence += 1

        return headers, lines

    def _derive_default_recurring_amount(self, vendor: pd.Series) -> float:
        """Fallback monthly amount for recurring vendors not explicitly mapped."""
        category = str(vendor["vendor_category"])

        if category == "Cloud Infrastructure":
            return 30_000.00

        if category == "Software / SaaS Tools":
            return 8_000.00

        if category == "Facilities":
            return 12_000.00

        if category == "Customer Support":
            return 6_000.00

        if category == "Payment Processing":
            return 18_000.00

        return 5_000.00

    # ------------------------------------------------------------------
    # Defect injection
    # ------------------------------------------------------------------

    def _find_vendor(
        self,
        vendors_df: pd.DataFrame,
        name_contains: str,
        fallback_category: str | None = None,
    ) -> pd.Series:
        """Find a vendor by name pattern with category fallback."""
        mask = vendors_df["vendor_name"].astype(str).str.contains(
            name_contains,
            case=False,
            na=False,
        )

        matches = vendors_df[mask]

        if not matches.empty:
            return matches.iloc[0]

        if fallback_category is not None:
            fallback = vendors_df[
                vendors_df["vendor_category"].astype(str).eq(fallback_category)
            ]

            if not fallback.empty:
                return fallback.iloc[0]

        raise ValueError(f"Unable to find vendor matching {name_contains!r}.")

    def _inject_ap_cutoff_failure(
        self,
        headers: list[dict],
        lines: list[dict],
        vendors_df: pd.DataFrame,
        fx_lookup: dict[tuple[str, str], float],
        sequence: int,
    ) -> tuple[list[dict], list[dict], int]:
        """
        Inject AP_CUTOFF_FAILURE.

        December 2025 service activity is captured and posted in February 2026.
        """

        vendor = self._find_vendor(
            vendors_df=vendors_df,
            name_contains="Amazon",
            fallback_category="Cloud Infrastructure",
        )

        invoice_date = pd.Timestamp("2026-02-10")
        posting_date = pd.Timestamp("2026-02-10")
        service_period_start = pd.Timestamp("2025-12-01")
        service_period_end = pd.Timestamp("2025-12-31")

        amount_gbp = 85_000.00

        header, line = self._build_header_and_line(
            vendor=vendor,
            invoice_date=invoice_date,
            posting_date=posting_date,
            service_period_start=service_period_start,
            service_period_end=service_period_end,
            amount_gbp_planning=amount_gbp,
            sequence=sequence,
            invoice_number="INV-AWS-202512-CUTOFF",
            line_description="AWS cloud infrastructure services - December 2025 captured late",
            is_defect_flag=1,
            defect_type="AP_CUTOFF_FAILURE",
            fx_lookup=fx_lookup,
        )

        headers.append(header)
        lines.append(line)

        logger.info(
            "Injected AP_CUTOFF_FAILURE vendor invoice: %s",
            header["vendor_invoice_id"],
        )

        return headers, lines, sequence + 1

    def _inject_duplicate_vendor_invoice(
        self,
        headers: list[dict],
        lines: list[dict],
        vendors_df: pd.DataFrame,
        fx_lookup: dict[tuple[str, str], float],
        sequence: int,
    ) -> tuple[list[dict], list[dict], int]:
        """
        Inject DUPLICATE_VENDOR_INVOICE.

        Two separate internal invoice records share the same vendor invoice number,
        vendor, invoice date and amount.
        """

        vendor = self._find_vendor(
            vendors_df=vendors_df,
            name_contains="Meta",
            fallback_category="Marketing",
        )

        invoice_date = pd.Timestamp("2025-07-18")
        posting_date = invoice_date
        service_period_start = pd.Timestamp("2025-07-01")
        service_period_end = pd.Timestamp("2025-07-31")
        invoice_number = "INV-META-202507-CAMPAIGN"
        amount_gbp = 42_500.00

        duplicate_headers: list[dict] = []
        duplicate_lines: list[dict] = []

        for duplicate_index in range(2):
            header, line = self._build_header_and_line(
                vendor=vendor,
                invoice_date=invoice_date,
                posting_date=posting_date,
                service_period_start=service_period_start,
                service_period_end=service_period_end,
                amount_gbp_planning=amount_gbp,
                sequence=sequence,
                invoice_number=invoice_number,
                line_description="Meta paid social campaign - duplicated AP capture",
                is_defect_flag=1,
                defect_type="DUPLICATE_VENDOR_INVOICE",
                fx_lookup=fx_lookup,
            )

            # Make sure the two internal records are genuinely unique even though
            # the physical supplier invoice attributes match.
            if duplicate_index == 1:
                original_id = header["vendor_invoice_id"]
                new_id = f"{original_id}-DUP"
                header["vendor_invoice_id"] = new_id
                header["vendor_invoice_pk"] = self._generate_pk(new_id)

                old_line_id = line["vendor_invoice_line_id"]
                new_line_id = f"{old_line_id}-DUP"
                line["vendor_invoice_id"] = new_id
                line["vendor_invoice_line_id"] = new_line_id
                line["vendor_invoice_line_pk"] = self._generate_pk(new_line_id)

            header["payment_status"] = "Paid"

            duplicate_headers.append(header)
            duplicate_lines.append(line)
            sequence += 1

        headers.extend(duplicate_headers)
        lines.extend(duplicate_lines)

        logger.info(
            "Injected DUPLICATE_VENDOR_INVOICE pair for invoice_number=%s.",
            invoice_number,
        )

        return headers, lines, sequence

    # ------------------------------------------------------------------
    # Validation and review
    # ------------------------------------------------------------------

    def _validate_output(
        self,
        headers_df: pd.DataFrame,
        lines_df: pd.DataFrame,
    ) -> None:
        """Validate vendor invoice outputs."""

        is_valid, validation_logs = verify_dataset_integrity(
            df=headers_df,
            required_columns=self.HEADER_COLUMNS,
            unique_keys=["vendor_invoice_pk"],
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

        is_valid, validation_logs = verify_dataset_integrity(
            df=lines_df,
            required_columns=self.LINE_COLUMNS,
            unique_keys=["vendor_invoice_line_pk"],
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

        if headers_df["vendor_invoice_id"].duplicated().any():
            duplicate_count = int(headers_df["vendor_invoice_id"].duplicated().sum())
            raise ValueError(
                f"vendor_invoices.csv contains duplicate vendor_invoice_id values: {duplicate_count:,}"
            )

        missing_parent_ids = set(lines_df["vendor_invoice_id"]) - set(
            headers_df["vendor_invoice_id"]
        )

        if missing_parent_ids:
            raise ValueError(
                f"vendor_invoice_lines.csv contains {len(missing_parent_ids):,} "
                "vendor_invoice_id values missing from vendor_invoices.csv."
            )

        for column in [
            "subtotal_local",
            "tax_amount_local",
            "total_local",
            "subtotal_gbp",
            "tax_amount_gbp",
            "total_gbp",
        ]:
            headers_df[column] = pd.to_numeric(headers_df[column], errors="coerce")

        for column in ["line_amount_local", "line_amount_gbp"]:
            lines_df[column] = pd.to_numeric(lines_df[column], errors="coerce")

        if headers_df[["subtotal_local", "total_local", "subtotal_gbp", "total_gbp"]].isna().any().any():
            raise ValueError("vendor_invoices.csv contains invalid monetary values.")

        if lines_df[["line_amount_local", "line_amount_gbp"]].isna().any().any():
            raise ValueError("vendor_invoice_lines.csv contains invalid monetary values.")

        header_subtotals = headers_df.set_index("vendor_invoice_id")[
            ["subtotal_local", "subtotal_gbp"]
        ]

        line_subtotals = lines_df.groupby("vendor_invoice_id", as_index=True).agg(
            line_subtotal_local=("line_amount_local", "sum"),
            line_subtotal_gbp=("line_amount_gbp", "sum"),
        )

        reconciliation_df = header_subtotals.join(line_subtotals, how="left")

        reconciliation_df["local_delta"] = (
            reconciliation_df["subtotal_local"]
            - reconciliation_df["line_subtotal_local"]
        ).round(2)

        reconciliation_df["gbp_delta"] = (
            reconciliation_df["subtotal_gbp"]
            - reconciliation_df["line_subtotal_gbp"]
        ).round(2)

        bad_reconciliation = reconciliation_df[
            (reconciliation_df["local_delta"].abs() > 0.05)
            | (reconciliation_df["gbp_delta"].abs() > 0.05)
        ]

        if not bad_reconciliation.empty:
            raise ValueError(
                "Vendor invoice header-to-line reconciliation failed. "
                f"Bad invoices: {len(bad_reconciliation):,}"
            )

        duplicate_control = headers_df.duplicated(
            subset=["vendor_id", "invoice_number", "invoice_date", "total_local"],
            keep=False,
        )

        duplicate_defects = headers_df[
            duplicate_control
            & (headers_df["defect_type"] == "DUPLICATE_VENDOR_INVOICE")
        ]

        if len(duplicate_defects) < 2:
            raise ValueError(
                "Expected at least one flagged DUPLICATE_VENDOR_INVOICE pair."
            )

        cutoff_rows = lines_df[lines_df["defect_type"] == "AP_CUTOFF_FAILURE"]

        if cutoff_rows.empty:
            raise ValueError("Expected one AP_CUTOFF_FAILURE line but found none.")

        cutoff_header_ids = set(cutoff_rows["vendor_invoice_id"])
        cutoff_headers = headers_df[
            headers_df["vendor_invoice_id"].isin(cutoff_header_ids)
        ]

        if cutoff_headers.empty:
            raise ValueError("AP_CUTOFF_FAILURE line has no matching header.")

        cutoff_service_month = pd.to_datetime(
            cutoff_rows.iloc[0]["service_period_end"]
        ).strftime("%Y-%m")

        cutoff_posting_period = str(cutoff_headers.iloc[0]["posting_period"])

        if cutoff_service_month == cutoff_posting_period:
            raise ValueError(
                "AP_CUTOFF_FAILURE did not create a service-period/posting-period mismatch."
            )

        logger.info("Vendor invoice output validation passed.")

    def _log_output_review(
        self,
        headers_df: pd.DataFrame,
        lines_df: pd.DataFrame,
    ) -> None:
        logger.info("----- Vendor Invoices Review -----")
        logger.info("Vendor invoice header rows: %s", f"{len(headers_df):,}")
        logger.info("Vendor invoice line rows: %s", f"{len(lines_df):,}")

        logger.info(
            "Headers by payment_status:\n%s",
            headers_df["payment_status"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Headers by currency:\n%s",
            headers_df["currency"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Lines by expense_category:\n%s",
            lines_df["expense_category"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Header defect distribution:\n%s",
            headers_df["defect_type"].replace("", "None").value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Line defect distribution:\n%s",
            lines_df["defect_type"].replace("", "None").value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Total vendor invoice spend GBP: %.2f",
            float(headers_df["total_gbp"].sum()),
        )

        logger.info("----------------------------------")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        logger.info("Generating Phase 3I.2 vendor invoices and invoice lines.")

        vendors_df, fx_lookup = self._load_dependencies()

        headers, lines = self._generate_recurring_invoices(
            vendors_df=vendors_df,
            fx_lookup=fx_lookup,
        )

        variable_headers, variable_lines = self._generate_variable_invoices(
            vendors_df=vendors_df,
            fx_lookup=fx_lookup,
            starting_sequence=len(headers) + 1,
        )

        headers.extend(variable_headers)
        lines.extend(variable_lines)

        next_sequence = len(headers) + 1

        headers, lines, next_sequence = self._inject_ap_cutoff_failure(
            headers=headers,
            lines=lines,
            vendors_df=vendors_df,
            fx_lookup=fx_lookup,
            sequence=next_sequence,
        )

        headers, lines, next_sequence = self._inject_duplicate_vendor_invoice(
            headers=headers,
            lines=lines,
            vendors_df=vendors_df,
            fx_lookup=fx_lookup,
            sequence=next_sequence,
        )

        headers_df = pd.DataFrame(headers)[self.HEADER_COLUMNS].copy()
        lines_df = pd.DataFrame(lines)[self.LINE_COLUMNS].copy()

        self._validate_output(headers_df=headers_df, lines_df=lines_df)
        self._log_output_review(headers_df=headers_df, lines_df=lines_df)

        logger.info(
            "Phase 3I.2 generation complete: %s vendor invoice headers, %s vendor invoice lines.",
            f"{len(headers_df):,}",
            f"{len(lines_df):,}",
        )

        return headers_df, lines_df

    def save(
        self,
        headers_df: pd.DataFrame,
        lines_df: pd.DataFrame,
    ) -> None:
        output_dir = get_raw_data_path("procurement")
        output_dir.mkdir(parents=True, exist_ok=True)

        headers_path = output_dir / self.header_filename
        lines_path = output_dir / self.lines_filename

        headers_df.to_csv(headers_path, index=False, encoding="utf-8")
        lines_df.to_csv(lines_path, index=False, encoding="utf-8")

        logger.info("Vendor invoices written to %s", headers_path)
        logger.info("Vendor invoice lines written to %s", lines_path)


def main() -> None:
    generator = VendorInvoicesGenerator()
    headers_df, lines_df = generator.generate()
    generator.save(headers_df=headers_df, lines_df=lines_df)

    logger.info(
        "Phase 3I.2 standalone run complete. Saved %s vendor invoice headers and %s vendor invoice lines.",
        f"{len(headers_df):,}",
        f"{len(lines_df):,}",
    )


if __name__ == "__main__":
    main()