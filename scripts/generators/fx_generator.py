from datetime import date

import numpy as np
import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.dates import generate_monthly_spine
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path
from scripts.utils.validation import raise_if_invalid, verify_dataset_integrity


logger = get_logger("FXRateGenerator", "generation_execution.log")


class FXRateGenerator:
    """Generates monthly simulated FX rates for group GBP consolidation."""

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()

        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.start_date: str = self.config.project.get("start_date", "2022-01-01")
        self.end_date: str = self.config.project.get("end_date", "2026-12-31")

        self.base_currency: str = self.config.fx.get("base_currency", "GBP")
        self.currencies: list[str] = self.config.fx.get(
            "currencies",
            ["GBP", "USD", "EUR", "SGD"],
        )

        self.minimum_rate_floor: float = float(
            self.config.fx.get("minimum_rate_floor", 0.25)
        )

        self.output_filename = "exchange_rates_2022_2026.csv"

    def generate(self) -> pd.DataFrame:
        np.random.seed(self.seed)

        month_ends = generate_monthly_spine(
            start_str=self.start_date,
            end_str=self.end_date,
        )

        records: list[dict] = []

        for currency_code in self.currencies:
            records.extend(self._generate_currency_walk(currency_code, month_ends))

        df = pd.DataFrame(records)

        required_columns = [
            "currency_code",
            "base_currency",
            "month_start_date",
            "month_end_date",
            "monthly_average_rate_to_gbp",
            "month_end_spot_rate_to_gbp",
            "rate_source",
            "is_shock_month",
            "shock_description",
        ]

        unique_keys = ["currency_code", "month_end_date"]

        is_valid, validation_logs = verify_dataset_integrity(
            df=df,
            required_columns=required_columns,
            unique_keys=unique_keys,
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

        expected_rows = len(self.currencies) * len(month_ends)
        if len(df) != expected_rows:
            raise ValueError(
                f"FX row count mismatch. Expected {expected_rows}, got {len(df)}."
            )

        logger.info("Generated FX dataset with %s rows.", len(df))

        return df

    def _generate_currency_walk(
        self,
        currency_code: str,
        month_ends: list[date],
    ) -> list[dict]:
        currency_rules = self.config.get_currency_assumption(currency_code)

        prior_spot = float(currency_rules.get("base_rate_to_gbp", 1.0))

        records: list[dict] = []

        for month_end in month_ends:
            month_start = date(month_end.year, month_end.month, 1)
            month_key = month_end.strftime("%Y-%m")

            is_shock_month = False
            shock_description = None

            if currency_code == self.base_currency:
                spot_rate = 1.0
                average_rate = 1.0
            else:
                annual_drift = float(currency_rules.get("annual_drift", 0.0))
                monthly_volatility = float(currency_rules.get("monthly_volatility", 0.0))

                spot_rate = prior_spot * (1 + annual_drift / 12)
                spot_rate += np.random.normal(loc=0.0, scale=1.0) * monthly_volatility

                shock_config = currency_rules.get("shock")
                if shock_config and month_key == shock_config.get("shock_month"):
                    shock_pct = float(shock_config.get("shock_pct", 0.0))
                    spot_rate *= 1 + shock_pct

                    is_shock_month = True
                    shock_description = shock_config.get("description")

                    logger.warning(
                        "FX shock applied for %s in %s: %.2f%%",
                        currency_code,
                        month_key,
                        shock_pct * 100,
                    )

                spot_rate = max(self.minimum_rate_floor, spot_rate)
                average_rate = (prior_spot + spot_rate) / 2

            records.append(
                {
                    "currency_code": currency_code,
                    "base_currency": self.base_currency,
                    "month_start_date": month_start.isoformat(),
                    "month_end_date": month_end.isoformat(),
                    "monthly_average_rate_to_gbp": round(average_rate, 6),
                    "month_end_spot_rate_to_gbp": round(spot_rate, 6),
                    "rate_source": "SIMULATED",
                    "is_shock_month": int(is_shock_month),
                    "shock_description": shock_description,
                }
            )

            prior_spot = spot_rate

        return records

    def save(self, df: pd.DataFrame) -> None:
        output_dir = get_raw_data_path("fx")
        output_path = output_dir / self.output_filename

        df.to_csv(output_path, index=False, encoding="utf-8")

        logger.info("FX rates written to %s", output_path)


def main() -> None:
    generator = FXRateGenerator()
    df = generator.generate()
    generator.save(df)


if __name__ == "__main__":
    main()