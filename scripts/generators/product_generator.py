import hashlib

import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path
from scripts.utils.validation import raise_if_invalid, verify_dataset_integrity


logger = get_logger("ProductGenerator", "generation_execution.log")


class ProductGenerator:
    """Generates the product catalogue reference dataset."""

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.output_filename = "product_catalog.csv"

    @staticmethod
    def _generate_product_pk(sku_code: str) -> str:
        """Creates a deterministic stable surrogate key from SKU code."""
        return hashlib.md5(sku_code.upper().encode("utf-8")).hexdigest()

    def generate(self) -> pd.DataFrame:
        product_family_lookup = {
            product["product_id"]: product
            for product in self.config.products
        }

        records: list[dict] = []

        for sku in self.config.product_skus:
            product_family_code = sku["product_family_code"]

            if product_family_code not in product_family_lookup:
                raise KeyError(
                    f"SKU {sku.get('sku_code')} references unknown product_family_code: "
                    f"{product_family_code}"
                )

            product_family = product_family_lookup[product_family_code]
            sku_code = sku["sku_code"]

            record = {
                "product_pk": self._generate_product_pk(sku_code),
                "product_id": int(sku["product_id"]),
                "product_family_code": product_family_code,
                "sku_code": sku_code,
                "product_name": sku["product_name"],
                "product_suite": product_family["product_suite"],
                "product_category": sku["product_category"],
                "revenue_mix_target": product_family.get("revenue_mix_target", 0.0),
                "gross_margin_target": product_family.get("gross_margin_target", 0.0),
                "is_recurring": int(bool(product_family.get("is_recurring", False))),
                "is_usage_based": int(bool(sku.get("is_usage_based", False))),
                "is_legacy_product": int(
                    bool(product_family.get("is_legacy_product", False))
                ),
                "acquisition_source": product_family.get("acquisition_source"),
                "launch_date": sku.get(
                    "launch_date",
                    product_family.get("launch_date", "2022-01-01"),
                ),
                "retirement_date": sku.get(
                    "retirement_date",
                    product_family.get("retirement_date"),
                ),
                "active_flag": 1,
            }

            records.append(record)

        df = pd.DataFrame(records)

        required_columns = [
            "product_pk",
            "product_id",
            "product_family_code",
            "sku_code",
            "product_name",
            "product_suite",
            "product_category",
            "revenue_mix_target",
            "gross_margin_target",
            "is_recurring",
            "is_usage_based",
            "is_legacy_product",
            "acquisition_source",
            "launch_date",
            "retirement_date",
            "active_flag",
        ]

        is_valid, validation_logs = verify_dataset_integrity(
            df=df,
            required_columns=required_columns,
            unique_keys=["product_pk"],
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

        expected_rows = 13

        if len(df) != expected_rows:
            raise ValueError(
                f"Product catalogue row count mismatch. "
                f"Expected {expected_rows}, got {len(df)}."
            )

        if df["product_pk"].nunique() != len(df):
            raise ValueError("Product catalogue contains duplicate product_pk values.")

        if df["product_id"].nunique() != len(df):
            raise ValueError("Product catalogue contains duplicate product_id values.")

        if df["sku_code"].nunique() != len(df):
            raise ValueError("Product catalogue contains duplicate SKU codes.")

        ai_rows = df[df["product_suite"] == "AI"]
        if not ai_rows.empty and not (ai_rows["is_usage_based"] == 1).all():
            raise ValueError("All AI products must be flagged as usage-based.")

        services_rows = df[df["product_suite"] == "Professional Services"]
        if not services_rows.empty and not (services_rows["is_recurring"] == 0).all():
            raise ValueError("Professional Services products must not be recurring.")

        logger.info("Generated product catalogue with %s rows.", len(df))

        return df

    def save(self, df: pd.DataFrame) -> None:
        output_dir = get_raw_data_path("products")
        output_path = output_dir / self.output_filename

        df.to_csv(output_path, index=False, encoding="utf-8")

        logger.info("Product catalogue written to %s", output_path)


def main() -> None:
    generator = ProductGenerator()
    df = generator.generate()
    generator.save(df)


if __name__ == "__main__":
    main()