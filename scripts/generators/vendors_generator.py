"""
vendors_generator.py

Project Atlas / Nexus Technologies
Phase 3I.1 - Vendor Master Generator

Purpose
-------
Generates:
- data/raw/procurement/vendors.csv

This file acts as the procurement/vendor master source for the Phase 3I
Procure-to-Pay cost subledger.

Design
------
The vendor master provides:
- supplier identity
- default expense account mapping
- default department ownership
- operating currency
- cash account linkage
- payment terms
- vendor risk metadata
- recurring/vendor classification

Downstream uses:
- vendor invoice generation
- vendor payment generation
- AP ageing
- P2P GL journal postings
- vendor spend analytics
- AP control testing
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

import pandas as pd

from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("VendorsGenerator", "generation_execution.log")


@dataclass(frozen=True)
class VendorGenerationRules:
    """Static generation rules for vendor master."""

    created_at: date = date(2026, 6, 3)
    updated_at: date = date(2026, 6, 3)


class VendorsGenerator:
    """
    Generates the vendor master for Phase 3I Procure-to-Pay.

    Output
    ------
    data/raw/procurement/vendors.csv
    """

    output_filename = "vendors.csv"

    VENDOR_COLUMNS = [
        "vendor_pk",
        "vendor_id",
        "vendor_name",
        "vendor_category",
        "default_account_code",
        "default_department_id",
        "region_id",
        "currency",
        "cash_account_code",
        "payment_terms",
        "vendor_status",
        "approval_status",
        "is_strategic_vendor",
        "is_recurring_vendor",
        "risk_rating",
        "source_system",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    VALID_CURRENCIES = {"GBP", "USD", "EUR", "SGD"}

    VALID_PAYMENT_TERMS = {
        "Immediate",
        "Net 15",
        "Net 30",
        "Net 45",
        "Net 60",
    }

    VALID_RISK_RATINGS = {
        "Low",
        "Medium",
        "High",
    }

    CASH_ACCOUNT_BY_CURRENCY = {
        "GBP": "1010",
        "USD": "1020",
        "EUR": "1030",
        "SGD": "1040",
    }

    def __init__(self) -> None:
        self.rules = VendorGenerationRules()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pk(value: str) -> str:
        """Generate deterministic MD5 surrogate key."""
        return hashlib.md5(value.strip().upper().encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Vendor definition
    # ------------------------------------------------------------------

    def _vendor_records(self) -> list[dict]:
        """
        Define the static vendor catalogue.

        Account mapping:
        5100 Hosting / Cloud Infrastructure COGS
        5200 Customer Support COGS
        6200 Sales & Marketing Expense
        6300 Software / SaaS Tools Expense
        6400 Rent & Office Expense
        6500 Professional Fees
        6600 Travel & Entertainment
        6900 Depreciation & Amortisation
        """

        vendors = [
            # ----------------------------------------------------------
            # Cloud infrastructure / COGS
            # ----------------------------------------------------------
            {
                "vendor_id": "VEN-0001",
                "vendor_name": "Amazon Web Services",
                "vendor_category": "Cloud Infrastructure",
                "default_account_code": "5100",
                "default_department_id": "DEPT-ENG",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 1,
                "is_recurring_vendor": 1,
                "risk_rating": "Medium",
            },
            {
                "vendor_id": "VEN-0002",
                "vendor_name": "Google Cloud Platform",
                "vendor_category": "Cloud Infrastructure",
                "default_account_code": "5100",
                "default_department_id": "DEPT-ENG",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 1,
                "is_recurring_vendor": 1,
                "risk_rating": "Medium",
            },
            {
                "vendor_id": "VEN-0003",
                "vendor_name": "Snowflake",
                "vendor_category": "Cloud Infrastructure",
                "default_account_code": "5100",
                "default_department_id": "DEPT-ENG",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Net 45",
                "is_strategic_vendor": 1,
                "is_recurring_vendor": 1,
                "risk_rating": "Medium",
            },
            {
                "vendor_id": "VEN-0004",
                "vendor_name": "Datadog",
                "vendor_category": "Cloud Infrastructure",
                "default_account_code": "5100",
                "default_department_id": "DEPT-ENG",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },

            # ----------------------------------------------------------
            # Software / SaaS tools
            # ----------------------------------------------------------
            {
                "vendor_id": "VEN-0005",
                "vendor_name": "Microsoft",
                "vendor_category": "Software / SaaS Tools",
                "default_account_code": "6300",
                "default_department_id": "DEPT-IT",
                "region_id": "REG-UKI",
                "currency": "GBP",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 1,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0006",
                "vendor_name": "Salesforce",
                "vendor_category": "Software / SaaS Tools",
                "default_account_code": "6300",
                "default_department_id": "DEPT-SALES",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Net 60",
                "is_strategic_vendor": 1,
                "is_recurring_vendor": 1,
                "risk_rating": "Medium",
            },
            {
                "vendor_id": "VEN-0007",
                "vendor_name": "HubSpot",
                "vendor_category": "Software / SaaS Tools",
                "default_account_code": "6300",
                "default_department_id": "DEPT-MKT",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0008",
                "vendor_name": "Slack",
                "vendor_category": "Software / SaaS Tools",
                "default_account_code": "6300",
                "default_department_id": "DEPT-OPS",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Immediate",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0009",
                "vendor_name": "GitHub",
                "vendor_category": "Software / SaaS Tools",
                "default_account_code": "6300",
                "default_department_id": "DEPT-ENG",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Immediate",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0010",
                "vendor_name": "Atlassian",
                "vendor_category": "Software / SaaS Tools",
                "default_account_code": "6300",
                "default_department_id": "DEPT-ENG",
                "region_id": "REG-APAC",
                "currency": "SGD",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0011",
                "vendor_name": "Notion Labs",
                "vendor_category": "Software / SaaS Tools",
                "default_account_code": "6300",
                "default_department_id": "DEPT-OPS",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Immediate",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },

            # ----------------------------------------------------------
            # Marketing
            # ----------------------------------------------------------
            {
                "vendor_id": "VEN-0012",
                "vendor_name": "Google Ads",
                "vendor_category": "Marketing",
                "default_account_code": "6200",
                "default_department_id": "DEPT-MKT",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Immediate",
                "is_strategic_vendor": 1,
                "is_recurring_vendor": 1,
                "risk_rating": "Medium",
            },
            {
                "vendor_id": "VEN-0013",
                "vendor_name": "Meta Business",
                "vendor_category": "Marketing",
                "default_account_code": "6200",
                "default_department_id": "DEPT-MKT",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Immediate",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Medium",
            },
            {
                "vendor_id": "VEN-0014",
                "vendor_name": "LinkedIn Marketing Solutions",
                "vendor_category": "Marketing",
                "default_account_code": "6200",
                "default_department_id": "DEPT-MKT",
                "region_id": "REG-UKI",
                "currency": "GBP",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0015",
                "vendor_name": "Capterra",
                "vendor_category": "Marketing",
                "default_account_code": "6200",
                "default_department_id": "DEPT-MKT",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 0,
                "risk_rating": "Low",
            },

            # ----------------------------------------------------------
            # Professional fees
            # ----------------------------------------------------------
            {
                "vendor_id": "VEN-0016",
                "vendor_name": "Deloitte LLP",
                "vendor_category": "Professional Fees",
                "default_account_code": "6500",
                "default_department_id": "DEPT-FIN",
                "region_id": "REG-UKI",
                "currency": "GBP",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 1,
                "is_recurring_vendor": 0,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0017",
                "vendor_name": "PwC LLP",
                "vendor_category": "Professional Fees",
                "default_account_code": "6500",
                "default_department_id": "DEPT-FIN",
                "region_id": "REG-UKI",
                "currency": "GBP",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 1,
                "is_recurring_vendor": 0,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0018",
                "vendor_name": "Freshfields Bruckhaus Deringer",
                "vendor_category": "Professional Fees",
                "default_account_code": "6500",
                "default_department_id": "DEPT-LEGAL",
                "region_id": "REG-UKI",
                "currency": "GBP",
                "payment_terms": "Net 45",
                "is_strategic_vendor": 1,
                "is_recurring_vendor": 0,
                "risk_rating": "Medium",
            },
            {
                "vendor_id": "VEN-0019",
                "vendor_name": "EY Tax Advisory",
                "vendor_category": "Professional Fees",
                "default_account_code": "6500",
                "default_department_id": "DEPT-FIN",
                "region_id": "REG-UKI",
                "currency": "GBP",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 0,
                "risk_rating": "Low",
            },

            # ----------------------------------------------------------
            # Facilities / office
            # ----------------------------------------------------------
            {
                "vendor_id": "VEN-0020",
                "vendor_name": "WeWork",
                "vendor_category": "Facilities",
                "default_account_code": "6400",
                "default_department_id": "DEPT-OPS",
                "region_id": "REG-UKI",
                "currency": "GBP",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0021",
                "vendor_name": "British Gas Business",
                "vendor_category": "Facilities",
                "default_account_code": "6400",
                "default_department_id": "DEPT-OPS",
                "region_id": "REG-UKI",
                "currency": "GBP",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0022",
                "vendor_name": "Singapore Office Services",
                "vendor_category": "Facilities",
                "default_account_code": "6400",
                "default_department_id": "DEPT-OPS",
                "region_id": "REG-APAC",
                "currency": "SGD",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },

            # ----------------------------------------------------------
            # Customer support / COGS
            # ----------------------------------------------------------
            {
                "vendor_id": "VEN-0023",
                "vendor_name": "Zendesk",
                "vendor_category": "Customer Support",
                "default_account_code": "5200",
                "default_department_id": "DEPT-CS",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0024",
                "vendor_name": "Intercom",
                "vendor_category": "Customer Support",
                "default_account_code": "5200",
                "default_department_id": "DEPT-CS",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 1,
                "risk_rating": "Low",
            },

            # ----------------------------------------------------------
            # Recruitment / travel / fixed asset support
            # ----------------------------------------------------------
            {
                "vendor_id": "VEN-0025",
                "vendor_name": "Hays Recruitment",
                "vendor_category": "Recruitment",
                "default_account_code": "6500",
                "default_department_id": "DEPT-HR",
                "region_id": "REG-UKI",
                "currency": "GBP",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 0,
                "risk_rating": "Medium",
            },
            {
                "vendor_id": "VEN-0026",
                "vendor_name": "Expedia Business Travel",
                "vendor_category": "Travel",
                "default_account_code": "6600",
                "default_department_id": "DEPT-OPS",
                "region_id": "REG-UKI",
                "currency": "GBP",
                "payment_terms": "Net 15",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 0,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0027",
                "vendor_name": "Dell Technologies",
                "vendor_category": "Fixed Assets",
                "default_account_code": "6900",
                "default_department_id": "DEPT-IT",
                "region_id": "REG-UKI",
                "currency": "GBP",
                "payment_terms": "Net 30",
                "is_strategic_vendor": 0,
                "is_recurring_vendor": 0,
                "risk_rating": "Low",
            },
            {
                "vendor_id": "VEN-0028",
                "vendor_name": "Stripe",
                "vendor_category": "Payment Processing",
                "default_account_code": "6500",
                "default_department_id": "DEPT-FIN",
                "region_id": "REG-NA",
                "currency": "USD",
                "payment_terms": "Immediate",
                "is_strategic_vendor": 1,
                "is_recurring_vendor": 1,
                "risk_rating": "Medium",
            },
        ]

        return vendors

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self) -> pd.DataFrame:
        """Generate vendor master dataframe."""
        logger.info("Generating vendor master.")

        records: list[dict] = []

        for vendor in self._vendor_records():
            vendor_id = str(vendor["vendor_id"])
            currency = str(vendor["currency"]).upper()

            record = {
                "vendor_pk": self._generate_pk(vendor_id),
                "vendor_id": vendor_id,
                "vendor_name": str(vendor["vendor_name"]),
                "vendor_category": str(vendor["vendor_category"]),
                "default_account_code": str(vendor["default_account_code"]),
                "default_department_id": str(vendor["default_department_id"]),
                "region_id": str(vendor["region_id"]),
                "currency": currency,
                "cash_account_code": self.CASH_ACCOUNT_BY_CURRENCY[currency],
                "payment_terms": str(vendor["payment_terms"]),
                "vendor_status": "Active",
                "approval_status": "Approved",
                "is_strategic_vendor": int(vendor["is_strategic_vendor"]),
                "is_recurring_vendor": int(vendor["is_recurring_vendor"]),
                "risk_rating": str(vendor["risk_rating"]),
                "source_system": "procurement_master",
                "is_defect_flag": 0,
                "defect_type": "",
                "created_at": self.rules.created_at.isoformat(),
                "updated_at": self.rules.updated_at.isoformat(),
            }

            records.append(record)

        df = pd.DataFrame(records)
        df = self._finalise_dataframe(df)

        self._validate_output(df)
        self._log_output_review(df)

        logger.info("Generated %s vendor master rows.", f"{len(df):,}")

        return df

    def _finalise_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply final column order and stable sorting."""
        df = df.reindex(columns=self.VENDOR_COLUMNS)
        df = df.sort_values("vendor_id").reset_index(drop=True)

        return df

    # ------------------------------------------------------------------
    # Validation and logging
    # ------------------------------------------------------------------

    def _validate_output(self, df: pd.DataFrame) -> None:
        """Validate vendor master output."""
        if df.empty:
            raise ValueError("Vendor master output cannot be empty.")

        missing_columns = set(self.VENDOR_COLUMNS).difference(df.columns)
        if missing_columns:
            raise ValueError(
                f"Vendor master output missing columns: {sorted(missing_columns)}"
            )

        if df["vendor_id"].duplicated().any():
            duplicate_count = int(df["vendor_id"].duplicated().sum())
            raise ValueError(f"Duplicate vendor_id values found: {duplicate_count:,}")

        if df["vendor_pk"].duplicated().any():
            duplicate_count = int(df["vendor_pk"].duplicated().sum())
            raise ValueError(f"Duplicate vendor_pk values found: {duplicate_count:,}")

        invalid_currencies = set(df["currency"]).difference(self.VALID_CURRENCIES)
        if invalid_currencies:
            raise ValueError(
                f"Invalid vendor currencies found: {sorted(invalid_currencies)}"
            )

        invalid_terms = set(df["payment_terms"]).difference(self.VALID_PAYMENT_TERMS)
        if invalid_terms:
            raise ValueError(
                f"Invalid payment_terms values found: {sorted(invalid_terms)}"
            )

        invalid_risk_ratings = set(df["risk_rating"]).difference(self.VALID_RISK_RATINGS)
        if invalid_risk_ratings:
            raise ValueError(
                f"Invalid risk_rating values found: {sorted(invalid_risk_ratings)}"
            )

        invalid_cash_accounts = df[
            ~df.apply(
                lambda row: self.CASH_ACCOUNT_BY_CURRENCY[row["currency"]]
                == str(row["cash_account_code"]),
                axis=1,
            )
        ]

        if not invalid_cash_accounts.empty:
            raise ValueError("Vendor cash_account_code does not match currency mapping.")

        for column in [
            "is_strategic_vendor",
            "is_recurring_vendor",
            "is_defect_flag",
        ]:
            if not df[column].isin([0, 1]).all():
                raise ValueError(f"{column} must only contain 0 or 1.")

        required_vendors = {
            "Amazon Web Services",
            "Snowflake",
            "Microsoft",
            "Salesforce",
            "Google Ads",
            "Deloitte LLP",
            "WeWork",
            "Zendesk",
        }

        missing_required_vendors = required_vendors.difference(set(df["vendor_name"]))

        if missing_required_vendors:
            raise ValueError(
                f"Required vendor names missing: {sorted(missing_required_vendors)}"
            )

        logger.info("Vendor master validation passed.")

    def _log_output_review(self, df: pd.DataFrame) -> None:
        """Log vendor master review summaries."""
        logger.info("----- Vendor Master Review -----")
        logger.info("Vendor rows: %s", f"{len(df):,}")

        logger.info(
            "Vendors by category:\n%s",
            df["vendor_category"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Vendors by currency:\n%s",
            df["currency"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Vendors by payment terms:\n%s",
            df["payment_terms"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Strategic vendor count: %s",
            f"{int(df['is_strategic_vendor'].sum()):,}",
        )

        logger.info(
            "Recurring vendor count: %s",
            f"{int(df['is_recurring_vendor'].sum()):,}",
        )

    def save(self, df: pd.DataFrame) -> None:
        """Save vendor master output."""
        output_dir = get_raw_data_path("procurement")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / self.output_filename
        df.to_csv(output_path, index=False, encoding="utf-8")

        logger.info("Vendor master written to %s", output_path)


def main() -> None:
    generator = VendorsGenerator()
    df = generator.generate()
    generator.save(df)

    logger.info(
        "Phase 3I.1 standalone run complete. Saved %s vendor master rows.",
        f"{len(df):,}",
    )


if __name__ == "__main__":
    main()