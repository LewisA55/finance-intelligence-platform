"""
generate_billing_subscriptions.py

Project Atlas / Nexus Technologies
Phase 3D - Billing & Subscription Generation

Purpose
-------
Generates billing_subscriptions.csv as the Quote-to-Cash subscription master.

This dataset is designed to support:
- ARR / MRR analytics
- SaaS revenue reporting
- Invoice generation
- Revenue recognition
- AR / deferred revenue modelling
- GL transaction generation
- dbt data quality testing
- audit/control simulation

Grain
-----
One row per subscription contract/version.

Intentional synthetic defects are embedded and labelled using:
- is_defect_flag
- defect_type

These labels are for synthetic test validation only. Downstream dbt tests should
detect the defects from business logic, not by relying on the labels.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("SubscriptionGenerator", "generation_execution.log")


@dataclass(frozen=True)
class SubscriptionDefectRates:
    """Controlled synthetic defect rates for the subscription master."""

    zombie_subscription: float = 0.015
    missing_product_mapping: float = 0.005
    zero_value_pricing_error: float = 0.0075
    currency_region_mismatch: float = 0.005
    duplicate_active_subscription: float = 0.005


@dataclass(frozen=True)
class SubscriptionGenerationRules:
    """Business rules for subscription generation."""

    no_subscription_rate: float = 0.02
    legitimate_zero_value_rate: float = 0.02
    current_date: date = date(2026, 6, 3)


class SubscriptionGenerator:
    """
    Generates the billing subscriptions master with embedded Q2C audit defects.

    Inputs
    ------
    data/raw/billing/billing_customers.csv
    data/raw/products/product_catalog.csv

    Output
    ------
    data/raw/billing/billing_subscriptions.csv
    """

    REQUIRED_CUSTOMER_COLUMNS = {
        "customer_id",
        "created_date",
        "currency_code",
        "customer_segment",
        "acquisition_source",
        "customer_status",
    }

    REQUIRED_PRODUCT_COLUMNS = {
        "product_id",
        "product_name",
        "product_suite",
        "product_category",
        "is_recurring",
        "is_legacy_product",
         "active_flag",
    }

    REQUIRED_PRICE_BOOK_COLUMNS = {
        "price_book_id",
        "product_id",
        "customer_segment",
        "currency",
        "monthly_list_price",
        "annual_list_price",
        "price_source",
        "is_legacy_price",
        "active_flag",
    }

    VALID_CUSTOMER_SEGMENTS = {"SMB", "Mid-Market", "Enterprise"}

    VALID_CONTRACT_STATUSES = {"Active", "Churned", "Paused"}

    VALID_BILLING_FREQUENCIES = {"Monthly", "Annual"}

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.output_filename = "billing_subscriptions.csv"

        self.defect_rates = SubscriptionDefectRates()
        self.rules = SubscriptionGenerationRules()

        self.rng = np.random.default_rng(self.seed)

    # ---------------------------------------------------------------------
    # Core helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def _generate_pk(subscription_id: str) -> str:
        """Generate deterministic MD5 surrogate key from subscription_id."""
        return hashlib.md5(subscription_id.encode("utf-8")).hexdigest()

    def _random_date_between(self, start_date: date, end_date: date) -> date:
        """
        Return a random date between start_date and end_date, inclusive.

        If the range is invalid, returns start_date. Invalid ranges should be
        avoided upstream where possible.
        """
        delta_days = (end_date - start_date).days
        if delta_days <= 0:
            return start_date

        offset = int(self.rng.integers(0, delta_days + 1))
        return start_date + timedelta(days=offset)

    @staticmethod
    def _to_date(value: object, column_name: str) -> date:
        """Robustly parse a date-like value from CSV input."""
        parsed = pd.to_datetime(value, errors="coerce")

        if pd.isna(parsed):
            raise ValueError(f"Unable to parse {column_name}: {value!r}")

        return parsed.date()

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

    # ---------------------------------------------------------------------
    # Dependency loading and validation
    # ---------------------------------------------------------------------

    def _load_dependencies(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Load customers, product catalog and product price book from the raw data layer."""
        customers_path = get_raw_data_path("billing") / "billing_customers.csv"
        products_path = get_raw_data_path("products") / "product_catalog.csv"
        price_book_path = get_raw_data_path("products") / "product_price_book.csv"

        if not customers_path.exists():
            raise FileNotFoundError(
                f"billing_customers.csv not found at: {customers_path}. "
                "Run the billing customer generator first."
            )

        if not products_path.exists():
            raise FileNotFoundError(
                f"product_catalog.csv not found at: {products_path}. "
                "Run the product catalog generator first."
            )

        if not price_book_path.exists():
            raise FileNotFoundError(
                f"product_price_book.csv not found at: {price_book_path}. "
                "Run the product price book generator first."
            )

        customers_df = pd.read_csv(customers_path)
        products_df = pd.read_csv(products_path)
        price_book_df = pd.read_csv(price_book_path)

        self._validate_input_columns(
            df=customers_df,
            required_columns=self.REQUIRED_CUSTOMER_COLUMNS,
            dataset_name="billing_customers.csv",
        )

        self._validate_input_columns(
            df=products_df,
            required_columns=self.REQUIRED_PRODUCT_COLUMNS,
            dataset_name="product_catalog.csv",
        )

        self._validate_input_columns(
            df=price_book_df,
            required_columns=self.REQUIRED_PRICE_BOOK_COLUMNS,
            dataset_name="product_price_book.csv",
        )

        customers_df = self._prepare_customers(customers_df)
        products_df = self._prepare_products(products_df)
        price_book_df = self._prepare_price_book(price_book_df)

        logger.info(
            "Loaded dependencies: %s customers, %s products, %s price book rows.",
            f"{len(customers_df):,}",
            f"{len(products_df):,}",
            f"{len(price_book_df):,}",
        )

        return customers_df, products_df, price_book_df

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

    def _prepare_customers(self, customers_df: pd.DataFrame) -> pd.DataFrame:
        """Normalize customer fields before subscription generation."""
        df = customers_df.copy()

        df["created_date"] = pd.to_datetime(df["created_date"], errors="coerce")

        if df["created_date"].isna().any():
            bad_count = int(df["created_date"].isna().sum())
            raise ValueError(
                f"billing_customers.csv contains {bad_count:,} invalid created_date values."
            )

        if "active_flag" not in df.columns:
            df["active_flag"] = 1

        if "is_acquired_customer" not in df.columns:
            df["is_acquired_customer"] = np.where(
                df["acquisition_source"].astype(str).str.contains("DataPulse", case=False, na=False),
                1,
                0,
            )

        df["active_flag"] = df["active_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=1)
        )

        df["is_acquired_customer"] = df["is_acquired_customer"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )

        df["customer_segment"] = df["customer_segment"].fillna("SMB").astype(str)

        df["customer_status"] = df["customer_status"].fillna("Active").astype(str)

        valid_customer_statuses = {"Active", "Churned", "Paused"}
        invalid_customer_statuses = set(df["customer_status"].unique()).difference(
            valid_customer_statuses
        )

        if invalid_customer_statuses:
            raise ValueError(
                f"Invalid customer_status values found in billing_customers.csv: "
                f"{sorted(invalid_customer_statuses)}"
            )

        invalid_segments = set(df["customer_segment"].unique()).difference(
            self.VALID_CUSTOMER_SEGMENTS
        )

        if invalid_segments:
            logger.warning(
                "Unexpected customer segments found and treated as SMB fallback: %s",
                sorted(invalid_segments),
            )

        df["currency_code"] = df["currency_code"].fillna("GBP").astype(str).str.upper()

        return df

    @staticmethod
    def _prepare_products(products_df: pd.DataFrame) -> pd.DataFrame:
        """Normalize product catalog fields before subscription generation."""
        df = products_df.copy()

        if df.empty:
            raise ValueError("product_catalog.csv is empty.")

        df["product_id"] = df["product_id"].astype(str)
        df["product_name"] = df["product_name"].fillna("").astype(str)
        df["product_suite"] = df["product_suite"].fillna("").astype(str)
        df["product_category"] = df["product_category"].fillna("").astype(str)

        df["is_recurring"] = df["is_recurring"].apply(
            lambda x: SubscriptionGenerator._normalise_bool_int(x, default=1)
        )

        df["is_legacy_product"] = df["is_legacy_product"].apply(
            lambda x: SubscriptionGenerator._normalise_bool_int(x, default=0)
        )

        df["active_flag"] = df["active_flag"].apply(
            lambda x: SubscriptionGenerator._normalise_bool_int(x, default=1)
        )

        # Subscriptions should only be generated for active recurring products.
        df = df[
            (df["is_recurring"] == 1)
            & (df["active_flag"] == 1)
        ].copy()

        if df.empty:
            raise ValueError(
                "product_catalog.csv contains no active recurring products."
            )

        # Preserve old internal naming so downstream product selection logic stays simple.
        df["is_legacy"] = df["is_legacy_product"]

        return df
    
    @staticmethod
    def _prepare_price_book(price_book_df: pd.DataFrame) -> pd.DataFrame:
        """Normalize product price book fields before subscription generation."""
        df = price_book_df.copy()

        if df.empty:
            raise ValueError("product_price_book.csv is empty.")

        df["product_id"] = df["product_id"].astype(str)
        df["customer_segment"] = df["customer_segment"].astype(str)
        df["currency"] = df["currency"].astype(str).str.upper()

        df["monthly_list_price"] = pd.to_numeric(
            df["monthly_list_price"],
            errors="coerce",
        )

        df["annual_list_price"] = pd.to_numeric(
            df["annual_list_price"],
            errors="coerce",
        )

        df["active_flag"] = df["active_flag"].apply(
            lambda x: SubscriptionGenerator._normalise_bool_int(x, default=1)
        )

        df["is_legacy_price"] = df["is_legacy_price"].apply(
            lambda x: SubscriptionGenerator._normalise_bool_int(x, default=0)
        )

        if df["monthly_list_price"].isna().any():
            bad_count = int(df["monthly_list_price"].isna().sum())
            raise ValueError(
                f"product_price_book.csv contains {bad_count:,} invalid monthly_list_price values."
            )

        if df["annual_list_price"].isna().any():
            bad_count = int(df["annual_list_price"].isna().sum())
            raise ValueError(
                f"product_price_book.csv contains {bad_count:,} invalid annual_list_price values."
            )

        df = df[df["active_flag"] == 1].copy()

        if df.empty:
            raise ValueError("product_price_book.csv contains no active price book rows.")

        return df

    # ---------------------------------------------------------------------
    # Business logic
    # ---------------------------------------------------------------------

    def _get_source_fields(
        self,
        is_datapulse: bool,
        price_source: str,
    ) -> tuple[str, str]:
        """
        Return acquisition_source and source_system values for subscription records.

        acquisition_source = commercial origin of the customer/contract.
        source_system = operational system the contract is assumed to come from.

        This gives the Q2C layer a realistic systems lineage:
        - Nexus organic contracts come from the Nexus billing platform.
        - DataPulse contracts come from migrated legacy billing.
        - Manual adjustments are flagged as finance operations amendments.
        """

        if is_datapulse:
            acquisition_source = "DataPulse Analytics"
            source_system = "datapulse_legacy_billing"
        elif price_source == "manual_adjustment":
            acquisition_source = "Nexus Organic"
            source_system = "finance_ops_manual_adjustment"
        elif price_source == "sales_override":
            acquisition_source = "Nexus Organic"
            source_system = "crm_sales_override"
        elif price_source == "promotional_bundle":
            acquisition_source = "Nexus Organic"
            source_system = "billing_promotions_module"
        else:
            acquisition_source = "Nexus Organic"
            source_system = "nexus_billing_platform"

        return acquisition_source, source_system

    def _select_product_for_customer(
        self,
        customer_segment: str,
        is_datapulse: bool,
        products_df: pd.DataFrame,
    ) -> pd.Series:
        """
        Select product using customer segment weighting.

        DataPulse customers are assigned to a legacy product where possible.
        Nexus organic customers are weighted by broad product category.
        """
        if is_datapulse:
            legacy_products = products_df[products_df["is_legacy"] == 1]

            if not legacy_products.empty:
                return legacy_products.sample(
                    n=1,
                    random_state=int(self.rng.integers(0, 1_000_000)),
                ).iloc[0]

            logger.warning(
                "No legacy product found for DataPulse customer. "
                "Falling back to active recurring product."
            )

        non_legacy = products_df[products_df["is_legacy"] == 0].copy()

        if non_legacy.empty:
            non_legacy = products_df.copy()

        product_text = (
            non_legacy["product_name"].fillna("").astype(str)
            + " "
            + non_legacy["product_suite"].fillna("").astype(str)
            + " "
            + non_legacy["product_category"].fillna("").astype(str)
        ).str.lower()

        core_products = non_legacy[
            product_text.str.contains("core|platform|base|suite", regex=True)
        ]

        analytics_products = non_legacy[
            product_text.str.contains("analytics|insight|reporting|dashboard", regex=True)
        ]

        advanced_products = non_legacy[
            product_text.str.contains(
                "ai|automation|security|risk|compliance|integration|workflow",
                regex=True,
            )
        ]

        if core_products.empty:
            core_products = non_legacy

        if analytics_products.empty:
            analytics_products = non_legacy

        if advanced_products.empty:
            advanced_products = non_legacy

        if customer_segment == "Enterprise":
            product_group = self.rng.choice(
                ["core", "analytics", "advanced"],
                p=[0.20, 0.30, 0.50],
            )
        elif customer_segment == "Mid-Market":
            product_group = self.rng.choice(
                ["core", "analytics", "advanced"],
                p=[0.35, 0.40, 0.25],
            )
        else:
            product_group = self.rng.choice(
                ["core", "analytics", "advanced"],
                p=[0.60, 0.30, 0.10],
            )

        if product_group == "core":
            product_pool = core_products
        elif product_group == "analytics":
            product_pool = analytics_products
        else:
            product_pool = advanced_products

        return product_pool.sample(
            n=1,
            random_state=int(self.rng.integers(0, 1_000_000)),
        ).iloc[0]
    
    def _select_products_for_customer(
        self,
        customer_segment: str,
        is_datapulse: bool,
        products_df: pd.DataFrame,
        subscription_count: int,
    ) -> list[pd.Series]:
        """
        Select one or more unique products for a customer.

        This prevents accidental duplicate product subscriptions. Intentional
        duplicate active subscriptions are still handled separately by the defect
        injection logic.
        """

        selected_products: list[pd.Series] = []
        selected_product_ids: set[str] = set()

        if is_datapulse:
            product = self._select_product_for_customer(
                customer_segment=customer_segment,
                is_datapulse=True,
                products_df=products_df,
            )
            return [product]

        max_attempts = 25

        for _ in range(subscription_count):
            selected_product: pd.Series | None = None

            for _attempt in range(max_attempts):
                candidate = self._select_product_for_customer(
                    customer_segment=customer_segment,
                    is_datapulse=False,
                    products_df=products_df,
                )

                candidate_product_id = str(candidate["product_id"])

                if candidate_product_id not in selected_product_ids:
                    selected_product = candidate
                    break

            if selected_product is None:
                # No unique product could be found after repeated attempts.
                break

            selected_products.append(selected_product)
            selected_product_ids.add(str(selected_product["product_id"]))

        if not selected_products:
            selected_products.append(
                self._select_product_for_customer(
                    customer_segment=customer_segment,
                    is_datapulse=False,
                    products_df=products_df,
                )
            )

        return selected_products
    
    def _get_subscription_count_for_customer(
        self,
        customer_segment: str,
        is_datapulse: bool,
    ) -> int:
        """
        Decide how many subscriptions a customer should have.

        Most customers have one subscription. Enterprise and Mid-Market customers
        have higher add-on/product-suite adoption.
        """

        if is_datapulse:
            return 1

        if customer_segment == "Enterprise":
            return int(self.rng.choice([1, 2, 3], p=[0.68, 0.25, 0.07]))

        if customer_segment == "Mid-Market":
            return int(self.rng.choice([1, 2, 3], p=[0.85, 0.12, 0.03]))

        return int(self.rng.choice([1, 2], p=[0.97, 0.03]))

    def _get_billing_frequency_and_term(
        self,
        customer_segment: str,
        is_datapulse: bool,
    ) -> tuple[str, int]:
        """Return billing frequency and contract term based on customer profile."""
        if is_datapulse:
            frequency = self.rng.choice(["Annual", "Monthly"], p=[0.75, 0.25])
        elif customer_segment == "Enterprise":
            frequency = self.rng.choice(["Annual", "Monthly"], p=[0.85, 0.15])
        elif customer_segment == "Mid-Market":
            frequency = self.rng.choice(["Annual", "Monthly"], p=[0.65, 0.35])
        else:
            frequency = self.rng.choice(["Annual", "Monthly"], p=[0.45, 0.55])

        if frequency == "Monthly":
            term_months = 1
        elif customer_segment == "Enterprise":
            term_months = int(self.rng.choice([12, 24, 36], p=[0.70, 0.20, 0.10]))
        else:
            term_months = int(self.rng.choice([12, 24, 36], p=[0.85, 0.12, 0.03]))

        return str(frequency), term_months

    def _get_payment_terms(
        self,
        customer_segment: str,
        is_datapulse: bool,
    ) -> str:
        """Return payment terms using customer/tier-sensitive distribution."""
        if is_datapulse:
            return str(self.rng.choice(["Net 30", "Net 60", "Due on Receipt"], p=[0.55, 0.35, 0.10]))

        if customer_segment == "Enterprise":
            return str(self.rng.choice(["Net 30", "Net 60", "Due on Receipt"], p=[0.55, 0.40, 0.05]))

        if customer_segment == "Mid-Market":
            return str(self.rng.choice(["Net 30", "Net 60", "Due on Receipt"], p=[0.75, 0.20, 0.05]))

        return str(self.rng.choice(["Net 30", "Net 60", "Due on Receipt"], p=[0.65, 0.05, 0.30]))

    @staticmethod
    def _get_fx_rate_from_gbp(currency_code: str) -> float:
        """
        Approximate FX conversion from GBP to local currency.

        Note
        ----
        This is intentionally simplified for this generator. In the warehouse,
        FX should eventually join to the generated FX rates table by currency/date.
        """
        fx_rates = {
            "GBP": 1.00,
            "USD": 1.30,
            "EUR": 1.15,
            "SGD": 1.80,
            "AUD": 1.95,
            "CAD": 1.75,
        }

        return fx_rates.get(str(currency_code).upper(), 1.00)

    def _get_contract_dates(
        self,
        customer_created_date: date,
        is_datapulse: bool,
        customer_status: str,
        active_flag: int,
        term_months: int,
    ) -> tuple[date, Optional[date], str]:
        """
        Return contract_start_date, contract_end_date and contract_status.

        DataPulse contracts may pre-date Nexus acquisition/migration.
        Churned subscriptions must have a plausible end date.
        Recent customers are protected from unrealistic churn.
        """
        current_date = self.rules.current_date

        if is_datapulse:
            start_date = self._random_date_between(date(2019, 1, 1), customer_created_date)
        else:
            start_date = customer_created_date + timedelta(
                days=int(self.rng.integers(0, 15))
            )

        # Customer-level paused status should create a paused subscription, not churn.
        if customer_status == "Paused":
            return start_date, None, "Paused"

        # Customer-level churn should create a realistic churned subscription.
        if customer_status == "Churned" or active_flag == 0:
            min_end_date = start_date + relativedelta(months=max(term_months, 3))

            if min_end_date < current_date:
                end_date = self._random_date_between(min_end_date, current_date)
                return start_date, end_date, "Churned"

            # If too new to churn plausibly, pause instead of creating impossible churn.
            return start_date, None, "Paused"

        # Small chance of paused subscriptions among otherwise active customers.
        if self.rng.random() < 0.01:
            return start_date, None, "Paused"

        return start_date, None, "Active"

    def _calculate_pricing(
        self,
        product: pd.Series,
        price_book_df: pd.DataFrame,
        currency_code: str,
        is_datapulse: bool,
        customer_segment: str,
    ) -> tuple[float, float, float, float, float, str]:
        """
        Calculate MRR/ARR in local currency and GBP using product_price_book.csv.

        product_price_book monthly_list_price is in the contract currency.
        GBP values are converted back using fx_rate_from_gbp when available.
        """
        product_id = str(product["product_id"])
        currency_code = str(currency_code).upper()

        price_rows = price_book_df[
            (price_book_df["product_id"].astype(str) == product_id)
            & (price_book_df["customer_segment"].astype(str) == customer_segment)
            & (price_book_df["currency"].astype(str).str.upper() == currency_code)
            & (price_book_df["active_flag"] == 1)
        ].copy()

        if price_rows.empty:
            # Conservative fallback: same product/segment in GBP, then convert to local.
            price_rows = price_book_df[
                (price_book_df["product_id"].astype(str) == product_id)
                & (price_book_df["customer_segment"].astype(str) == customer_segment)
                & (price_book_df["currency"].astype(str).str.upper() == "GBP")
                & (price_book_df["active_flag"] == 1)
            ].copy()

        if price_rows.empty:
            raise ValueError(
                "No active price book row found for "
                f"product_id={product_id}, customer_segment={customer_segment}, currency={currency_code}."
            )

        price_row = price_rows.sort_values("effective_start_date").iloc[-1]

        mrr_local_list = float(price_row["monthly_list_price"])

        fx_rate_from_gbp = float(
            price_row.get(
                "fx_rate_from_gbp",
                self._get_fx_rate_from_gbp(currency_code),
            )
        )

        if fx_rate_from_gbp <= 0:
            raise ValueError(
                f"Invalid fx_rate_from_gbp for product_id={product_id}, currency={currency_code}."
            )

        if is_datapulse:
            price_source = "datapulse_legacy"
            discount_pct = float(
                self.rng.choice(
                    [0.00, 0.05, 0.10, 0.15],
                    p=[0.55, 0.20, 0.15, 0.10],
                )
            )
        elif customer_segment == "Enterprise":
            price_source = str(
                self.rng.choice(
                    ["standard_rate_card", "sales_override"],
                    p=[0.70, 0.30],
                )
            )
            discount_pct = float(
                self.rng.choice(
                    [0.00, 0.05, 0.10, 0.15, 0.20],
                    p=[0.40, 0.20, 0.20, 0.15, 0.05],
                )
            )
        elif customer_segment == "Mid-Market":
            price_source = str(
                self.rng.choice(
                    ["standard_rate_card", "sales_override"],
                    p=[0.85, 0.15],
                )
            )
            discount_pct = float(
                self.rng.choice(
                    [0.00, 0.05, 0.10, 0.15],
                    p=[0.60, 0.20, 0.15, 0.05],
                )
            )
        else:
            price_source = "standard_rate_card"
            discount_pct = float(
                self.rng.choice(
                    [0.00, 0.05, 0.10],
                    p=[0.80, 0.15, 0.05],
                )
            )

        # Legitimate zero-value contracts: controlled and explainable.
        if (not is_datapulse) and self.rng.random() < self.rules.legitimate_zero_value_rate:
            discount_pct = 1.00
            price_source = "promotional_bundle"

        mrr_local = round(mrr_local_list * (1 - discount_pct), 2)
        arr_local = round(mrr_local * 12, 2)

        mrr_gbp = round(mrr_local / fx_rate_from_gbp, 2)
        arr_gbp = round(mrr_gbp * 12, 2)

        return mrr_local, mrr_gbp, arr_local, arr_gbp, discount_pct, price_source

    # ---------------------------------------------------------------------
    # Defect injection
    # ---------------------------------------------------------------------

    def _inject_primary_defect(
        self,
        record: dict,
        customer_currency: str,
    ) -> dict:
        """
        Inject at most one primary defect into a subscription record.

        Defect exclusivity is intentional. It makes synthetic test validation
        easier because each defective row has one clearly labelled reason.
        """
        defect_roll = self.rng.random()

        zombie_threshold = self.defect_rates.zombie_subscription
        missing_product_threshold = zombie_threshold + self.defect_rates.missing_product_mapping
        zero_value_threshold = missing_product_threshold + self.defect_rates.zero_value_pricing_error
        currency_mismatch_threshold = zero_value_threshold + self.defect_rates.currency_region_mismatch

        status = record["contract_status"]

        # 1. Zombie subscription:
        # Active contract but end date already passed.
        if defect_roll < zombie_threshold and status == "Active":
            record["contract_end_date"] = (
                self.rules.current_date - timedelta(days=int(self.rng.integers(15, 120)))
            ).isoformat()
            record["is_defect_flag"] = True
            record["defect_type"] = "ZOMBIE_SUBSCRIPTION"
            return record

        # 2. Missing product mapping:
        # Product FK does not exist in product_catalog.csv.
        if defect_roll < missing_product_threshold:
            record["product_id"] = "PROD-UNKNOWN"
            record["is_defect_flag"] = True
            record["defect_type"] = "MISSING_PRODUCT_MAPPING"
            return record

        # 3. Zero-value active contract:
        # No discount explanation, active status, zero commercial value.
        if defect_roll < zero_value_threshold and status == "Active":
            record["mrr_local"] = 0.00
            record["mrr_gbp"] = 0.00
            record["arr_local"] = 0.00
            record["arr_gbp"] = 0.00
            record["discount_pct"] = 0.00
            record["price_source"] = "manual_adjustment"
            record["source_system"] = "finance_ops_manual_adjustment"
            record["is_defect_flag"] = True
            record["defect_type"] = "ZERO_VALUE_ACTIVE_CONTRACT"
            return record

        # 4. Currency-region/customer mismatch:
        # Contract currency differs from customer master currency.
        if defect_roll < currency_mismatch_threshold:
            record["currency"] = "EUR" if customer_currency != "EUR" else "GBP"
            record["is_defect_flag"] = True
            record["defect_type"] = "CURRENCY_REGION_MISMATCH"
            return record

        return record

    def _create_duplicate_active_subscription(
        self,
        base_record: dict,
        duplicate_subscription_id: str,
    ) -> dict:
        """
        Create a business-duplicate active subscription.

        This is not a row-level duplicate. It has a unique subscription_id and
        subscription_pk, but duplicates the commercial contract footprint.
        """
        duplicate_record = base_record.copy()

        duplicate_record.update(
            {
                "subscription_pk": self._generate_pk(duplicate_subscription_id),
                "subscription_id": duplicate_subscription_id,
                "is_defect_flag": True,
                "defect_type": "DUPLICATE_ACTIVE_SUBSCRIPTION",
                "created_at": base_record["created_at"],
                "updated_at": base_record["updated_at"],
            }
        )

        return duplicate_record

    # ---------------------------------------------------------------------
    # Generation
    # ---------------------------------------------------------------------

    def generate(self) -> pd.DataFrame:
        """Generate billing subscription records."""
        logger.info("Generating Billing Subscriptions Master...")

        customers_df, products_df, price_book_df = self._load_dependencies()

        records: list[dict] = []
        subscription_counter = 1

        for _, customer in customers_df.iterrows():
            if self.rng.random() < self.rules.no_subscription_rate:
                continue

            customer_id = str(customer["customer_id"])
            customer_segment = str(customer["customer_segment"])

            if customer_segment not in self.VALID_CUSTOMER_SEGMENTS:
                customer_segment = "SMB"

            customer_currency = str(customer["currency_code"]).upper()
            is_datapulse = int(customer["is_acquired_customer"]) == 1
            active_flag = int(customer["active_flag"])
            customer_status = str(customer["customer_status"])
            customer_created_date = self._to_date(customer["created_date"], "created_date")

            subscription_count = self._get_subscription_count_for_customer(
                customer_segment=customer_segment,
                is_datapulse=is_datapulse,
            )

            selected_products = self._select_products_for_customer(
                customer_segment=customer_segment,
                is_datapulse=is_datapulse,
                products_df=products_df,
                subscription_count=subscription_count,
            )
            for product in selected_products:
                billing_frequency, term_months = self._get_billing_frequency_and_term(
                    customer_segment=customer_segment,
                    is_datapulse=is_datapulse,
                )

                start_date, end_date, contract_status = self._get_contract_dates(
                customer_created_date=customer_created_date,
                is_datapulse=is_datapulse,
                customer_status=customer_status,
                active_flag=active_flag,
                term_months=term_months,
            )

                billing_anchor_day = min(start_date.day, 28)

                (
                    mrr_local,
                    mrr_gbp,
                    arr_local,
                    arr_gbp,
                    discount_pct,
                    price_source,
                ) = self._calculate_pricing(
                    product=product,
                    price_book_df=price_book_df,
                    currency_code=customer_currency,
                    is_datapulse=is_datapulse,
                    customer_segment=customer_segment,
                )

                acquisition_source, source_system = self._get_source_fields(
                    is_datapulse=is_datapulse,
                    price_source=price_source,
                )

                subscription_id = f"SUB-{subscription_counter:06d}"

                record = {
                    "subscription_pk": self._generate_pk(subscription_id),
                    "subscription_id": subscription_id,
                    "customer_id": customer_id,
                    "product_id": str(product["product_id"]),
                    "customer_segment": customer_segment,
                    "plan_tier": "Not Applicable",
                    "contract_start_date": start_date.isoformat(),
                    "contract_end_date": end_date.isoformat() if end_date else None,
                    "contract_term_months": term_months,
                    "billing_frequency": billing_frequency,
                    "billing_anchor_day": billing_anchor_day,
                    "contract_status": contract_status,
                    "mrr_local": mrr_local,
                    "mrr_gbp": mrr_gbp,
                    "arr_local": arr_local,
                    "arr_gbp": arr_gbp,
                    "currency": customer_currency,
                    "payment_terms": self._get_payment_terms(
                        customer_segment=customer_segment,
                        is_datapulse=is_datapulse,
                    ),
                    "auto_renew_flag": 1 if end_date is None and contract_status == "Active" else 0,
                    "discount_pct": round(discount_pct, 4),
                    "price_source": price_source,
                    "acquisition_source": acquisition_source,
                    "source_system": source_system,
                    "created_at": start_date.isoformat(),
                    "updated_at": start_date.isoformat(),
                    "is_defect_flag": False,
                    "defect_type": None,
                }

                record = self._inject_primary_defect(
                    record=record,
                    customer_currency=customer_currency,
                )

                records.append(record)

                # Duplicate active subscription defect.
                # This is deliberately separate from primary defects.
                if (
                    record["contract_status"] == "Active"
                    and record["is_defect_flag"] is False
                    and self.rng.random() < self.defect_rates.duplicate_active_subscription
                ):
                    subscription_counter += 1
                    duplicate_subscription_id = f"SUB-{subscription_counter:06d}"

                    duplicate_record = self._create_duplicate_active_subscription(
                        base_record=record,
                        duplicate_subscription_id=duplicate_subscription_id,
                    )

                    records.append(duplicate_record)

                subscription_counter += 1

        df = pd.DataFrame(records)

        df = self._finalise_dataframe(df)

        self._validate_output(df=df, customers_df=customers_df, products_df=products_df)
        self._log_output_review(df=df, customers_df=customers_df)

        logger.info("Generated %s subscription records.", f"{len(df):,}")

        return df

    @staticmethod
    def _finalise_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Apply final column ordering and stable output formatting."""
        expected_columns = [
        "subscription_pk",
        "subscription_id",
        "customer_id",
        "product_id",
        "customer_segment",
        "plan_tier",
        "contract_start_date",
        "contract_end_date",
        "contract_term_months",
        "billing_frequency",
        "billing_anchor_day",
        "contract_status",
        "mrr_local",
        "mrr_gbp",
        "arr_local",
        "arr_gbp",
        "currency",
        "payment_terms",
        "auto_renew_flag",
        "discount_pct",
        "price_source",
        "acquisition_source",
        "source_system",
        "created_at",
        "updated_at",
        "is_defect_flag",
        "defect_type",
    ]

        for column in expected_columns:
            if column not in df.columns:
                df[column] = None

        df = df[expected_columns].copy()

        # Stable sorting for reproducible output review.
        df = df.sort_values(["subscription_id"]).reset_index(drop=True)

        return df

    # ---------------------------------------------------------------------
    # Validation and logging
    # ---------------------------------------------------------------------

    def _validate_output(
        self,
        df: pd.DataFrame,
        customers_df: pd.DataFrame,
        products_df: pd.DataFrame,
    ) -> None:
        """
        Validate output structure.

        Intentional business defects are not failed here. The generator should
        fail only on structural corruption that would make the dataset unusable.
        """
        if df.empty:
            raise ValueError("No subscription records generated.")

        if df["subscription_id"].duplicated().any():
            duplicate_count = int(df["subscription_id"].duplicated().sum())
            raise ValueError(f"Duplicate subscription_id detected: {duplicate_count:,}")

        if df["subscription_pk"].duplicated().any():
            duplicate_count = int(df["subscription_pk"].duplicated().sum())
            raise ValueError(f"Duplicate subscription_pk detected: {duplicate_count:,}")

        invalid_statuses = set(df["contract_status"].dropna().unique()).difference(
            self.VALID_CONTRACT_STATUSES
        )

        if invalid_statuses:
            raise ValueError(f"Invalid contract_status values found: {sorted(invalid_statuses)}")

        invalid_frequencies = set(df["billing_frequency"].dropna().unique()).difference(
            self.VALID_BILLING_FREQUENCIES
        )

        if invalid_frequencies:
            raise ValueError(
                f"Invalid billing_frequency values found: {sorted(invalid_frequencies)}"
            )

        if df["customer_id"].isna().any():
            raise ValueError("Null customer_id values found.")

        if df["customer_segment"].isna().any():
            raise ValueError("Null customer_segment values found.")

        invalid_segments = set(df["customer_segment"].dropna().unique()).difference(
            self.VALID_CUSTOMER_SEGMENTS
        )

        if invalid_segments:
            raise ValueError(
                f"Invalid customer_segment values found in subscriptions: "
                f"{sorted(invalid_segments)}"
            )

        if df["product_id"].isna().any():
            raise ValueError("Null product_id values found.")

        if (df["mrr_gbp"] < 0).any():
            raise ValueError("Negative mrr_gbp values found.")

        if (df["arr_gbp"] < 0).any():
            raise ValueError("Negative arr_gbp values found.")

        if not df["billing_anchor_day"].between(1, 28).all():
            raise ValueError("billing_anchor_day must be between 1 and 28.")

        # Structural relationship check:
        # All non-defect customers should exist in customer master.
        valid_customer_ids = set(customers_df["customer_id"].astype(str))
        orphan_customer_rows = ~df["customer_id"].astype(str).isin(valid_customer_ids)

        if orphan_customer_rows.any():
            orphan_count = int(orphan_customer_rows.sum())
            raise ValueError(f"Subscription rows with unknown customer_id found: {orphan_count:,}")

        # Do not fail missing product mapping defects. They are intentional.
        valid_product_ids = set(products_df["product_id"].astype(str))
        invalid_product_rows = ~df["product_id"].astype(str).isin(valid_product_ids)

        invalid_product_non_defect_rows = invalid_product_rows & ~(
            df["defect_type"].eq("MISSING_PRODUCT_MAPPING")
        )

        if invalid_product_non_defect_rows.any():
            bad_count = int(invalid_product_non_defect_rows.sum())
            raise ValueError(
                "Unknown product_id values found outside intentional "
                f"MISSING_PRODUCT_MAPPING defects: {bad_count:,}"
            )

        logger.info("Subscription output structural validation passed.")

    def _log_output_review(
        self,
        df: pd.DataFrame,
        customers_df: pd.DataFrame,
    ) -> None:
        """Log useful QA summaries for manual output review."""
        customer_count = len(customers_df)
        subscribed_customer_count = df["customer_id"].nunique()
        no_subscription_count = customer_count - subscribed_customer_count

        logger.info("----- Billing Subscriptions Review -----")
        logger.info("Customer master rows: %s", f"{customer_count:,}")
        logger.info("Customers with subscriptions: %s", f"{subscribed_customer_count:,}")
        logger.info("Customers without subscriptions: %s", f"{no_subscription_count:,}")
        logger.info(
            "Customers without subscriptions %%: %.2f%%",
            (no_subscription_count / customer_count) * 100 if customer_count else 0,
        )

        logger.info("Contract status counts:\n%s", df["contract_status"].value_counts(dropna=False).to_string())
        logger.info(
            "Customer segment counts:\n%s",
            df["customer_segment"].value_counts(dropna=False).to_string(),
        )
        logger.info("Billing frequency counts:\n%s", df["billing_frequency"].value_counts(dropna=False).to_string())
        logger.info("Billing frequency mix:\n%s", df["billing_frequency"].value_counts(normalize=True).round(3).to_string())
        logger.info("Currency counts:\n%s", df["currency"].value_counts(dropna=False).to_string())
        logger.info("Plan tier counts:\n%s", df["plan_tier"].value_counts(dropna=False).to_string())
        logger.info("Price source counts:\n%s", df["price_source"].value_counts(dropna=False).to_string())
        logger.info("Source system counts:\n%s", df["source_system"].value_counts(dropna=False).to_string())
        logger.info("Defect type counts:\n%s", df["defect_type"].value_counts(dropna=False).to_string())
        logger.info("MRR GBP summary:\n%s", df["mrr_gbp"].describe().round(2).to_string())
        logger.info("ARR GBP summary:\n%s", df["arr_gbp"].describe().round(2).to_string())

        active_arr = df.loc[df["contract_status"].eq("Active"), "arr_gbp"].sum()
        total_arr = df["arr_gbp"].sum()

        logger.info("Active ARR GBP: %.2f", active_arr)
        logger.info("Total ARR GBP: %.2f", total_arr)
        logger.info("----------------------------------------")

    # ---------------------------------------------------------------------
    # Save
    # ---------------------------------------------------------------------

    def save(self, df: pd.DataFrame) -> Path:
        """Save subscriptions to raw billing folder."""
        output_dir = get_raw_data_path("billing")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / self.output_filename
        df.to_csv(output_path, index=False)

        logger.info("Subscriptions saved to %s", output_path)

        return output_path


def main() -> None:
    generator = SubscriptionGenerator()
    subscriptions_df = generator.generate()
    generator.save(subscriptions_df)


if __name__ == "__main__":
    main()