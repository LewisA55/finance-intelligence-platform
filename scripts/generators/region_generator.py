import hashlib

import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path
from scripts.utils.validation import raise_if_invalid, verify_dataset_integrity


logger = get_logger("RegionGenerator", "generation_execution.log")


class RegionGenerator:
    """Generates the conformed global geographical region reference dimension."""

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.output_filename = "region_catalog.csv"

    @staticmethod
    def _generate_region_pk(region_id: str) -> str:
        """Computes a stable MD5 surrogate key hash for the regional market."""
        return hashlib.md5(region_id.strip().upper().encode("utf-8")).hexdigest()

    def generate(self) -> pd.DataFrame:
        logger.info("Parsing business rules configuration for global operating regions.")

        raw_regions = self.config.regions

        if not raw_regions:
            raise ValueError("No regional layouts found in business_rules.yaml.")

        records: list[dict] = []

        for region in raw_regions:
            region_id = region["region_id"]

            records.append(
                {
                    "region_pk": self._generate_region_pk(region_id),
                    "region_id": region_id.upper(),
                    "region_name": region["region_name"],
                    "currency_code": region["currency_code"].upper(),
                    "revenue_share": float(region.get("revenue_share", 0.0)),
                    "salary_multiplier": float(region.get("salary_multiplier", 1.0)),
                    "active_flag": 1,
                }
            )

        df = pd.DataFrame(records)

        required_columns = [
            "region_pk",
            "region_id",
            "region_name",
            "currency_code",
            "revenue_share",
            "salary_multiplier",
            "active_flag",
        ]

        is_valid, validation_logs = verify_dataset_integrity(
            df=df,
            required_columns=required_columns,
            unique_keys=["region_pk"],
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

        expected_rows = 4

        if len(df) != expected_rows:
            raise ValueError(
                f"Region map count mismatch. Expected {expected_rows}, got {len(df)}."
            )

        if df["region_id"].nunique() != len(df):
            raise ValueError("Region catalogue contains duplicate region_id values.")

        revenue_share_total = round(df["revenue_share"].sum(), 6)

        if revenue_share_total != 1.0:
            raise ValueError(
                f"Region revenue shares must sum to 1.0. Actual total: {revenue_share_total}"
            )

        valid_currencies = set(self.config.fx.get("currencies", []))
        invalid_currencies = set(df["currency_code"]) - valid_currencies

        if invalid_currencies:
            raise ValueError(
                f"Region catalogue contains currencies missing from FX config: {invalid_currencies}"
            )

        logger.info("Generated region catalogue with %s rows.", len(df))

        return df

    def save(self, df: pd.DataFrame) -> None:
        output_dir = get_raw_data_path("regions")
        output_path = output_dir / self.output_filename

        df.to_csv(output_path, index=False, encoding="utf-8")

        logger.info("Region catalogue written to %s", output_path)


def main() -> None:
    generator = RegionGenerator()
    df = generator.generate()
    generator.save(df)


if __name__ == "__main__":
    main()