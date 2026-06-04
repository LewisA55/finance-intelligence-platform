"""
product_price_book_generator.py

Project Atlas / Nexus Technologies
Phase 3D - Product Pricing Layer

Purpose
-------
Generates product_price_book.csv from product_catalog.csv.

This file acts as the commercial pricing reference layer used by:
- billing_subscriptions.csv
- billing_invoices.csv
- billing_invoice_lines.csv
- revenue recognition
- ARR / MRR reporting
- pricing and discount analysis
- audit / control testing

Grain
-----
One row per:
    product_id + customer_segment + currency + effective_start_date

Design Notes
------------
product_catalog.csv tells us:
    What products exist?

product_price_book.csv tells us:
    What should a customer be charged for a product, by segment and currency?

Pricing assumptions are controlled inside this script so the output remains:
- deterministic
- repeatable
- version-controlled
- easy to modify later
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


logger = get_logger("ProductPriceBookGenerator", "generation_execution.log")


@dataclass(frozen=True)
class PriceBookGenerationRules:
    """Controlled business rules for product price book generation."""

    standard_effective_start_date: date = date(2023, 1, 1)
    legacy_effective_start_date: date = date(2019, 1, 1)
    created_at: date = date(2026, 6, 3)
    updated_at: date = date(2026, 6, 3)


class ProductPriceBookGenerator:
    """
    Generates the product price book from the product catalog.

    Input
    -----
    data/raw/products/product_catalog.csv

    Output
    ------
    data/raw/products/product_price_book.csv
    """

    REQUIRED_PRODUCT_COLUMNS = {
        "product_id",
        "product_name",
        "product_suite",
        "product_category",
        "is_recurring",
        "is_usage_based",
        "is_legacy_product",
        "active_flag",
        "launch_date",
        "retirement_date",
        "acquisition_source",
    }

    CUSTOMER_SEGMENTS = ["SMB", "Mid-Market", "Enterprise"]

    CURRENCIES = ["GBP", "EUR", "USD", "SGD", "AUD", "CAD"]

    FX_RATES_FROM_GBP = {
        "GBP": 1.00,
        "EUR": 1.15,
        "USD": 1.30,
        "SGD": 1.80,
        "AUD": 1.95,
        "CAD": 1.75,
    }

    PRICING_REGIONS = {
        "GBP": "UKI",
        "EUR": "DACH",
        "USD": "North America",
        "SGD": "APAC",
        "AUD": "APAC",
        "CAD": "North America",
    }

    SEGMENT_PRICE_MULTIPLIERS = {
        "SMB": 1.00,
        "Mid-Market": 1.35,
        "Enterprise": 2.25,
    }

    # These are monthly GBP base prices before segment and currency modifiers.
    # The product-specific base price is derived from the product metadata.
    CATEGORY_BASE_MONTHLY_PRICES_GBP = {
        "core_platform": 500.00,
        "analytics": 1200.00,
        "automation": 1500.00,
        "ai": 2500.00,
        "security": 1800.00,
        "integration": 1000.00,
        "professional_services": 3000.00,
        "legacy": 3500.00,
        "default": 1000.00,
    }

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.output_filename = "product_price_book.csv"

        self.rules = PriceBookGenerationRules()
        self.rng = np.random.default_rng(self.seed)

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pk(value: str) -> str:
        """Generate deterministic MD5 surrogate key."""
        return hashlib.md5(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalise_bool_int(value: object, default: int = 0) -> int:
        """
        Normalize common boolean/integer/string flags into 0/1.

        Handles:
        - 1 / 0
        - 1.0 / 0.0
        - True / False
        - '1' / '0'
        - 'true' / 'false'
        - 'yes' / 'no'
        """
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
    def _safe_text(value: object) -> str:
        """Return safe lowercase text for product classification."""
        if pd.isna(value):
            return ""

        return str(value).strip().lower()

    # ------------------------------------------------------------------
    # Dependency loading
    # ------------------------------------------------------------------

    def _load_product_catalog(self) -> pd.DataFrame:
        """Load and validate product_catalog.csv."""
        product_catalog_path = get_raw_data_path("products") / "product_catalog.csv"

        if not product_catalog_path.exists():
            raise FileNotFoundError(
                f"product_catalog.csv not found at: {product_catalog_path}. "
                "Run the product catalog generator first."
            )

        products_df = pd.read_csv(product_catalog_path)

        self._validate_input_columns(
            df=products_df,
            required_columns=self.REQUIRED_PRODUCT_COLUMNS,
            dataset_name="product_catalog.csv",
        )

        products_df = self._prepare_product_catalog(products_df)

        logger.info(
            "Loaded product catalog: %s products.",
            f"{len(products_df):,}",
        )

        return products_df

    @staticmethod
    def _validate_input_columns(
        df: pd.DataFrame,
        required_columns: set[str],
        dataset_name: str,
    ) -> None:
        """Validate that an input dataframe contains required columns."""
        missing_columns = required_columns.difference(df.columns)

        if missing_columns:
            raise ValueError(
                f"{dataset_name} is missing required columns: "
                f"{sorted(missing_columns)}"
            )

    def _prepare_product_catalog(self, products_df: pd.DataFrame) -> pd.DataFrame:
        """Normalize product catalog fields before price book generation."""
        df = products_df.copy()

        if df.empty:
            raise ValueError("product_catalog.csv is empty.")

        df["product_id"] = df["product_id"].astype(str)
        df["product_name"] = df["product_name"].fillna("").astype(str)
        df["product_suite"] = df["product_suite"].fillna("").astype(str)
        df["product_category"] = df["product_category"].fillna("").astype(str)
        df["acquisition_source"] = df["acquisition_source"].fillna("Nexus Organic").astype(str)

        df["is_recurring"] = df["is_recurring"].apply(
            lambda x: self._normalise_bool_int(x, default=1)
        )

        df["is_usage_based"] = df["is_usage_based"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )

        df["is_legacy_product"] = df["is_legacy_product"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )

        df["active_flag"] = df["active_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=1)
        )

        recurring_products = df[df["is_recurring"] == 1].copy()

        if recurring_products.empty:
            raise ValueError(
                "product_catalog.csv contains no recurring products. "
                "At least one recurring product is required for subscription pricing."
            )

        return recurring_products

    # ------------------------------------------------------------------
    # Pricing logic
    # ------------------------------------------------------------------

    def _classify_pricing_category(self, product: pd.Series) -> str:
        """
        Classify product into a pricing category using product metadata.

        This keeps the existing product_catalog.csv clean while allowing the
        price book to apply controlled commercial assumptions.
        """
        combined_text = " ".join(
            [
                self._safe_text(product.get("product_family_code", "")),
                self._safe_text(product.get("sku_code", "")),
                self._safe_text(product.get("product_name", "")),
                self._safe_text(product.get("product_suite", "")),
                self._safe_text(product.get("product_category", "")),
            ]
        )

        is_legacy = int(product["is_legacy_product"]) == 1

        if is_legacy:
            return "legacy"

        if any(term in combined_text for term in ["ai", "intelligence", "copilot", "assistant"]):
            return "ai"

        if any(term in combined_text for term in ["security", "risk", "compliance", "control"]):
            return "security"

        if any(term in combined_text for term in ["automation", "workflow", "orchestration"]):
            return "automation"

        if any(term in combined_text for term in ["analytics", "insight", "reporting", "dashboard"]):
            return "analytics"

        if any(term in combined_text for term in ["integration", "connector", "api", "sync"]):
            return "integration"

        if any(term in combined_text for term in ["service", "implementation", "consulting"]):
            return "professional_services"

        if any(term in combined_text for term in ["core", "platform", "base", "suite"]):
            return "core_platform"

        return "default"

    def _get_base_monthly_price_gbp(self, product: pd.Series) -> float:
        """Return base monthly GBP list price before segment/currency modifiers."""
        pricing_category = self._classify_pricing_category(product)
        base_price = self.CATEGORY_BASE_MONTHLY_PRICES_GBP.get(
            pricing_category,
            self.CATEGORY_BASE_MONTHLY_PRICES_GBP["default"],
        )

        # Usage-based products usually have a lower platform fee because variable
        # usage revenue is expected to be generated later through invoice lines.
        is_usage_based = int(product["is_usage_based"]) == 1

        if is_usage_based:
            base_price *= 0.75

        return round(float(base_price), 2)

    def _get_price_source(self, product: pd.Series, currency: str) -> str:
        """Return price source lineage value."""
        is_legacy = int(product["is_legacy_product"]) == 1

        if is_legacy:
            return "datapulse_legacy_rate_card"

        if currency != "GBP":
            return "regional_rate_card"

        return "standard_rate_card"

    def _get_effective_start_date(self, product: pd.Series) -> date:
        """Return effective start date for product price."""
        is_legacy = int(product["is_legacy_product"]) == 1

        if is_legacy:
            return self.rules.legacy_effective_start_date

        launch_date = pd.to_datetime(product.get("launch_date"), errors="coerce")

        if pd.notna(launch_date):
            return max(launch_date.date(), self.rules.standard_effective_start_date)

        return self.rules.standard_effective_start_date

    def _get_effective_end_date(self, product: pd.Series) -> str | None:
        """
        Return effective end date.

        Retired products retain price book history but are inactive.
        Active products have no effective end date.
        """
        retirement_date = pd.to_datetime(product.get("retirement_date"), errors="coerce")

        if pd.notna(retirement_date):
            return retirement_date.date().isoformat()

        return None

    def _get_price_book_active_flag(self, product: pd.Series) -> int:
        """Return active flag for price book row."""
        product_active = int(product["active_flag"]) == 1
        retirement_date = pd.to_datetime(product.get("retirement_date"), errors="coerce")

        if not product_active:
            return 0

        if pd.notna(retirement_date) and retirement_date.date() <= self.rules.created_at:
            return 0

        return 1

    def _calculate_monthly_price(
        self,
        base_monthly_price_gbp: float,
        customer_segment: str,
        currency: str,
    ) -> tuple[float, float, float]:
        """
        Calculate monthly and annual list price for segment/currency.

        Returns:
            monthly_list_price
            annual_list_price
            fx_rate_from_gbp
        """
        segment_multiplier = self.SEGMENT_PRICE_MULTIPLIERS[customer_segment]
        fx_rate_from_gbp = self.FX_RATES_FROM_GBP[currency]

        monthly_list_price = round(
            base_monthly_price_gbp * segment_multiplier * fx_rate_from_gbp,
            2,
        )

        annual_list_price = round(monthly_list_price * 12, 2)

        return monthly_list_price, annual_list_price, fx_rate_from_gbp

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self) -> pd.DataFrame:
        """Generate product price book records."""
        logger.info("Generating Product Price Book...")

        products_df = self._load_product_catalog()

        records: list[dict] = []
        price_counter = 1

        for _, product in products_df.iterrows():
            base_monthly_price_gbp = self._get_base_monthly_price_gbp(product)
            effective_start_date = self._get_effective_start_date(product)
            effective_end_date = self._get_effective_end_date(product)
            price_book_active_flag = self._get_price_book_active_flag(product)
            is_legacy_price = int(product["is_legacy_product"])

            for customer_segment in self.CUSTOMER_SEGMENTS:
                for currency in self.CURRENCIES:
                    monthly_list_price, annual_list_price, fx_rate_from_gbp = (
                        self._calculate_monthly_price(
                            base_monthly_price_gbp=base_monthly_price_gbp,
                            customer_segment=customer_segment,
                            currency=currency,
                        )
                    )

                    price_book_id = f"PB-{price_counter:06d}"
                    pricing_region = self.PRICING_REGIONS[currency]
                    segment_price_multiplier = self.SEGMENT_PRICE_MULTIPLIERS[
                        customer_segment
                    ]
                    price_source = self._get_price_source(product, currency)

                    record = {
                        "price_book_pk": self._generate_pk(price_book_id),
                        "price_book_id": price_book_id,
                        "product_id": str(product["product_id"]),
                        "customer_segment": customer_segment,
                        "currency": currency,
                        "pricing_region": pricing_region,
                        "monthly_list_price": monthly_list_price,
                        "annual_list_price": annual_list_price,
                        "base_monthly_price_gbp": round(base_monthly_price_gbp, 2),
                        "fx_rate_from_gbp": round(fx_rate_from_gbp, 4),
                        "segment_price_multiplier": round(segment_price_multiplier, 4),
                        "effective_start_date": effective_start_date.isoformat(),
                        "effective_end_date": effective_end_date,
                        "price_source": price_source,
                        "is_legacy_price": is_legacy_price,
                        "active_flag": price_book_active_flag,
                        "created_at": self.rules.created_at.isoformat(),
                        "updated_at": self.rules.updated_at.isoformat(),
                    }

                    records.append(record)
                    price_counter += 1

        df = pd.DataFrame(records)

        df = self._finalise_dataframe(df)

        self._validate_output(df=df, products_df=products_df)
        self._log_output_review(df=df, products_df=products_df)

        logger.info("Generated %s price book records.", f"{len(df):,}")

        return df

    @staticmethod
    def _finalise_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Apply stable column ordering and sorting."""
        expected_columns = [
            "price_book_pk",
            "price_book_id",
            "product_id",
            "customer_segment",
            "currency",
            "pricing_region",
            "monthly_list_price",
            "annual_list_price",
            "base_monthly_price_gbp",
            "fx_rate_from_gbp",
            "segment_price_multiplier",
            "effective_start_date",
            "effective_end_date",
            "price_source",
            "is_legacy_price",
            "active_flag",
            "created_at",
            "updated_at",
        ]

        for column in expected_columns:
            if column not in df.columns:
                df[column] = None

        df = df[expected_columns].copy()

        df = df.sort_values(
            [
                "product_id",
                "customer_segment",
                "currency",
                "effective_start_date",
            ]
        ).reset_index(drop=True)

        return df

    # ------------------------------------------------------------------
    # Validation and logging
    # ------------------------------------------------------------------

    def _validate_output(
        self,
        df: pd.DataFrame,
        products_df: pd.DataFrame,
    ) -> None:
        """Validate generated price book structure."""
        if df.empty:
            raise ValueError("No price book records generated.")

        if df["price_book_id"].duplicated().any():
            duplicate_count = int(df["price_book_id"].duplicated().sum())
            raise ValueError(f"Duplicate price_book_id values found: {duplicate_count:,}")

        if df["price_book_pk"].duplicated().any():
            duplicate_count = int(df["price_book_pk"].duplicated().sum())
            raise ValueError(f"Duplicate price_book_pk values found: {duplicate_count:,}")

        business_key_columns = [
            "product_id",
            "customer_segment",
            "currency",
            "effective_start_date",
        ]

        if df.duplicated(subset=business_key_columns).any():
            duplicate_count = int(df.duplicated(subset=business_key_columns).sum())
            raise ValueError(
                "Duplicate price book business keys found for "
                "product_id + customer_segment + currency + effective_start_date: "
                f"{duplicate_count:,}"
            )

        valid_product_ids = set(products_df["product_id"].astype(str))
        invalid_product_rows = ~df["product_id"].astype(str).isin(valid_product_ids)

        if invalid_product_rows.any():
            invalid_count = int(invalid_product_rows.sum())
            raise ValueError(f"Price book rows with invalid product_id found: {invalid_count:,}")

        if (df["monthly_list_price"] < 0).any():
            raise ValueError("Negative monthly_list_price values found.")

        if (df["annual_list_price"] < 0).any():
            raise ValueError("Negative annual_list_price values found.")

        invalid_segments = set(df["customer_segment"].unique()).difference(
            self.CUSTOMER_SEGMENTS
        )

        if invalid_segments:
            raise ValueError(f"Invalid customer_segment values found: {sorted(invalid_segments)}")

        invalid_currencies = set(df["currency"].unique()).difference(self.CURRENCIES)

        if invalid_currencies:
            raise ValueError(f"Invalid currency values found: {sorted(invalid_currencies)}")

        if not df["active_flag"].isin([0, 1]).all():
            raise ValueError("active_flag must only contain 0 or 1.")

        if not df["is_legacy_price"].isin([0, 1]).all():
            raise ValueError("is_legacy_price must only contain 0 or 1.")

        logger.info("Product price book structural validation passed.")

    def _log_output_review(
        self,
        df: pd.DataFrame,
        products_df: pd.DataFrame,
    ) -> None:
        """Log useful QA summaries for manual output review."""
        logger.info("----- Product Price Book Review -----")
        logger.info("Recurring products priced: %s", f"{products_df['product_id'].nunique():,}")
        logger.info("Price book rows: %s", f"{len(df):,}")

        logger.info(
            "Rows by customer segment:\n%s",
            df["customer_segment"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Rows by currency:\n%s",
            df["currency"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Rows by price source:\n%s",
            df["price_source"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Rows by active flag:\n%s",
            df["active_flag"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Monthly list price summary:\n%s",
            df["monthly_list_price"].describe().round(2).to_string(),
        )

        logger.info(
            "Annual list price summary:\n%s",
            df["annual_list_price"].describe().round(2).to_string(),
        )

        logger.info("-------------------------------------")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self, df: pd.DataFrame) -> Path:
        """Save product price book to raw products folder."""
        output_dir = get_raw_data_path("products")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / self.output_filename
        df.to_csv(output_path, index=False)

        logger.info("Product price book saved to %s", output_path)

        return output_path


def main() -> None:
    generator = ProductPriceBookGenerator()
    price_book_df = generator.generate()
    generator.save(price_book_df)


if __name__ == "__main__":
    main()