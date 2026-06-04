import hashlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path
from scripts.utils.validation import raise_if_invalid, verify_dataset_integrity


logger = get_logger("CustomerGenerator", "generation_execution.log")


class CustomerGenerator:
    """Generates the billing customer master source dataset."""

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.output_filename = "billing_customers.csv"

        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.organic_customer_count: int = 3500
        self.datapulse_customer_count: int = int(
            self.config.acquisition.get("acquired_customers", 400)
        )

    @staticmethod
    def _generate_customer_pk(customer_id: str) -> str:
        """Creates a deterministic stable surrogate key from customer ID."""
        return hashlib.md5(customer_id.strip().upper().encode("utf-8")).hexdigest()

    @staticmethod
    def _random_date_between(start_date: date, end_date: date) -> str:
        """Returns a random ISO-format date between two date boundaries."""
        delta_days = (end_date - start_date).days

        if delta_days < 0:
            raise ValueError("start_date cannot be after end_date.")

        random_offset = np.random.randint(0, delta_days + 1)
        return (start_date + timedelta(days=int(random_offset))).isoformat()

    @staticmethod
    def _normalise_segment_name(segment_key: str) -> str:
        """Converts YAML keys into clean customer segment names."""
        mapping = {
            "enterprise": "Enterprise",
            "mid_market": "Mid-Market",
            "smb": "SMB",
        }

        return mapping.get(segment_key, segment_key)
    
    def _get_customer_lifecycle_status(self, is_acquired_customer: bool) -> tuple[str, int]:
        """
        Assign realistic customer lifecycle status.

        Most customers remain active, but a controlled minority are churned or paused.
        This creates realistic inputs for churn, retention, NRR and GRR analytics.
        """

        if is_acquired_customer:
            # Migrated DataPulse customers carry slightly higher churn/paused risk.
            status = np.random.choice(
                ["Active", "Churned", "Paused"],
                p=[0.93, 0.05, 0.02],
            )
        else:
            # Organic Nexus customers are slightly more stable.
            status = np.random.choice(
                ["Active", "Churned", "Paused"],
                p=[0.95, 0.04, 0.01],
            )

        active_flag = 1 if status == "Active" else 0

        return str(status), active_flag

    def _get_region_choices(self) -> tuple[list[dict], list[float]]:
        """Extracts region choices and validates revenue-share weighting."""
        regions = self.config.regions

        if not regions:
            raise ValueError("No regions found in business_rules.yaml.")

        weights = [float(region["revenue_share"]) for region in regions]
        total_weight = round(sum(weights), 6)

        if total_weight != 1.0:
            raise ValueError(
                f"Region revenue shares must sum to 1.0. Actual total: {total_weight}"
            )

        return regions, weights

    def _get_organic_segment_choices(self) -> tuple[list[str], list[float]]:
        """Extracts organic Nexus segment mix from business rules."""
        customer_segments = self.config.customer_segments

        if not customer_segments:
            raise ValueError("No customer segment rules found in business_rules.yaml.")

        segment_keys = list(customer_segments.keys())
        segment_labels = [self._normalise_segment_name(key) for key in segment_keys]
        weights = [
            float(customer_segments[key].get("logo_share", 0.0))
            for key in segment_keys
        ]

        total_weight = round(sum(weights), 6)

        if total_weight != 1.0:
            raise ValueError(
                f"Customer segment logo shares must sum to 1.0. Actual total: {total_weight}"
            )

        return segment_labels, weights

    def _get_industry_choices(self) -> tuple[list[str], list[float]]:
        """Extracts organic Nexus industry mix from business rules."""
        industries = self.config.customer_industries

        if not industries:
            raise ValueError("No customer industry rules found in business_rules.yaml.")

        labels = [industry["industry"] for industry in industries]
        weights = [float(industry["share"]) for industry in industries]

        total_weight = round(sum(weights), 6)

        if total_weight != 1.0:
            raise ValueError(
                f"Customer industry shares must sum to 1.0. Actual total: {total_weight}"
            )

        return labels, weights

    def _get_organic_cohort_choices(self) -> tuple[list[str], list[float]]:
        """Extracts organic customer cohort distribution from business rules."""
        cohort_rules = self.config.customer_cohorts

        if not cohort_rules:
            raise ValueError("No customer cohort rules found in business_rules.yaml.")

        cohort_keys = list(cohort_rules.keys())
        weights = [float(cohort_rules[key]) for key in cohort_keys]

        total_weight = round(sum(weights), 6)

        if total_weight != 1.0:
            raise ValueError(
                f"Customer cohort shares must sum to 1.0. Actual total: {total_weight}"
            )

        return cohort_keys, weights

    def _cohort_to_created_date(self, cohort_key: str) -> tuple[int, str]:
        """Converts a cohort bucket into cohort year and realistic created date."""
        if cohort_key == "pre_2022":
            created_date = self._random_date_between(
                start_date=date(2018, 1, 1),
                end_date=date(2021, 12, 31),
            )
            return 2021, created_date

        cohort_year = int(cohort_key)
        created_date = self._random_date_between(
            start_date=date(cohort_year, 1, 1),
            end_date=date(cohort_year, 12, 31),
        )

        return cohort_year, created_date

    def _maybe_null_industry(self, industry: str, missing_share: float = 0.05) -> str | None:
        """Injects a controlled missing industry defect."""
        if np.random.random() < missing_share:
            return None

        return industry

    def _generate_organic_customers(self) -> list[dict]:
        """Generates organic Nexus customer records."""
        regions, region_weights = self._get_region_choices()
        segment_labels, segment_weights = self._get_organic_segment_choices()
        industry_labels, industry_weights = self._get_industry_choices()
        cohort_labels, cohort_weights = self._get_organic_cohort_choices()

        records: list[dict] = []

        for index in range(1, self.organic_customer_count + 1):
            customer_id = f"CUST-{index:06d}"

            region = np.random.choice(regions, p=region_weights)
            segment = np.random.choice(segment_labels, p=segment_weights)
            industry = np.random.choice(industry_labels, p=industry_weights)
            cohort_key = np.random.choice(cohort_labels, p=cohort_weights)

            cohort_year, created_date = self._cohort_to_created_date(cohort_key)

            customer_status, active_flag = self._get_customer_lifecycle_status(
                is_acquired_customer=False,
            )

            records.append(
                {
                    "customer_pk": self._generate_customer_pk(customer_id),
                    "customer_id": customer_id,
                    "legacy_id": None,
                    "customer_name": f"Nexus Client {index:06d}",
                    "customer_segment": segment,
                    "industry": self._maybe_null_industry(
                        industry=industry,
                        missing_share=float(
                            self.config.data_quality_defects
                            .get("crm", {})
                            .get("missing_industry_share", 0.05)
                        ),
                    ),
                    "region_id": region["region_id"],
                    "currency_code": region["currency_code"],
                    "cohort_year": cohort_year,
                    "is_acquired_customer": 0,
                    "acquisition_source": "Nexus Organic",
                    "created_date": created_date,
                    "customer_status": customer_status,
                    "active_flag": active_flag,
                }
            )

        return records

    def _generate_datapulse_customers(self) -> list[dict]:
        """Generates acquired DataPulse customer records."""
        segment_labels = ["SMB", "Mid-Market", "Enterprise"]
        segment_weights = [0.30, 0.50, 0.20]

        industry_labels = [
            "Financial Services",
            "Technology / SaaS",
            "Manufacturing / Logistics",
            "Healthcare / Life Sciences",
            "Retail & E-commerce",
            "Professional Services / Other",
        ]
        industry_weights = [0.30, 0.25, 0.20, 0.10, 0.10, 0.05]

        records: list[dict] = []

        for index in range(1, self.datapulse_customer_count + 1):
            customer_id = f"DP-{index:04d}"
            legacy_id = str(800000 + index)

            industry = np.random.choice(industry_labels, p=industry_weights)

            customer_status, active_flag = self._get_customer_lifecycle_status(
                is_acquired_customer=True,
            )

            records.append(
                {
                    "customer_pk": self._generate_customer_pk(customer_id),
                    "customer_id": customer_id,
                    "legacy_id": legacy_id,
                    "customer_name": f"DataPulse Client {index:04d}",
                    "customer_segment": np.random.choice(
                        segment_labels,
                        p=segment_weights,
                    ),
                    "industry": self._maybe_null_industry(
                        industry=industry,
                        missing_share=float(
                            self.config.acquisition
                            .get("injected_defects", {})
                            .get("missing_industry_share", 0.05)
                        ),
                    ),
                    "region_id": self.config.acquisition.get("primary_region", "DE"),
                    "currency_code": self.config.acquisition.get("currency_code", "EUR"),
                    "cohort_year": 2024,
                    "is_acquired_customer": 1,
                    "acquisition_source": self.config.acquisition.get(
                        "company_name",
                        "DataPulse Analytics",
                    ),
                    "created_date": self._random_date_between(
                        start_date=date(2024, 10, 1),
                        end_date=date(2024, 10, 31),
                    ),
                    "customer_status": customer_status,
                    "active_flag": active_flag,
                }
            )

        return records

    def generate(self) -> pd.DataFrame:
        """Generates the full customer master dataset."""
        logger.info("Generating billing customer master.")

        np.random.seed(self.seed)

        organic_records = self._generate_organic_customers()
        datapulse_records = self._generate_datapulse_customers()

        df = pd.DataFrame(organic_records + datapulse_records)

        required_columns = [
            "customer_pk",
            "customer_id",
            "legacy_id",
            "customer_name",
            "customer_segment",
            "industry",
            "region_id",
            "currency_code",
            "cohort_year",
            "is_acquired_customer",
            "acquisition_source",
            "created_date",
            "customer_status",
            "active_flag",
        ]

        df = df[required_columns]

        is_valid, validation_logs = verify_dataset_integrity(
            df=df,
            required_columns=required_columns,
            unique_keys=["customer_pk"],
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

        expected_rows = self.organic_customer_count + self.datapulse_customer_count

        if len(df) != expected_rows:
            raise ValueError(
                f"Customer row count mismatch. Expected {expected_rows}, got {len(df)}."
            )

        if df["customer_id"].nunique() != len(df):
            raise ValueError("Customer master contains duplicate customer_id values.")

        acquired_count = int(df["is_acquired_customer"].sum())
        if acquired_count != self.datapulse_customer_count:
            raise ValueError(
                f"DataPulse customer count mismatch. "
                f"Expected {self.datapulse_customer_count}, got {acquired_count}."
            )

        organic_count = len(df[df["is_acquired_customer"] == 0])
        if organic_count != self.organic_customer_count:
            raise ValueError(
                f"Organic customer count mismatch. "
                f"Expected {self.organic_customer_count}, got {organic_count}."
            )

        datapulse_regions = set(
            df.loc[df["is_acquired_customer"] == 1, "region_id"].unique()
        )
        if datapulse_regions != {"DE"}:
            raise ValueError(
                f"DataPulse customers must be locked to DE. Actual regions: {datapulse_regions}"
            )

        datapulse_currencies = set(
            df.loc[df["is_acquired_customer"] == 1, "currency_code"].unique()
        )
        if datapulse_currencies != {"EUR"}:
            raise ValueError(
                f"DataPulse customers must be locked to EUR. "
                f"Actual currencies: {datapulse_currencies}"
            )

        logger.info("Generated customer master with %s rows.", len(df))

        return df

    def save(self, df: pd.DataFrame) -> None:
        output_dir = get_raw_data_path("billing")
        output_path = output_dir / self.output_filename

        df.to_csv(output_path, index=False, encoding="utf-8")

        logger.info("Billing customer master written to %s", output_path)


def main() -> None:
    generator = CustomerGenerator()
    df = generator.generate()
    generator.save(df)


if __name__ == "__main__":
    main()