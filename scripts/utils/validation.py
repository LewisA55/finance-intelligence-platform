from typing import Sequence

import pandas as pd


def verify_dataset_integrity(
    df: pd.DataFrame,
    required_columns: Sequence[str],
    unique_keys: Sequence[str] | None = None,
) -> tuple[bool, list[str]]:
    logs: list[str] = []
    is_valid = True

    if df is None or df.empty:
        return False, ["Target DataFrame is empty or None."]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        logs.append(f"Missing required columns: {missing_columns}")
        is_valid = False

    if unique_keys:
        missing_keys = [key for key in unique_keys if key not in df.columns]

        if missing_keys:
            logs.append(f"Unique key columns missing from DataFrame: {missing_keys}")
            is_valid = False
        else:
            duplicate_count = df.duplicated(subset=list(unique_keys)).sum()

            if duplicate_count > 0:
                logs.append(
                    f"Found {duplicate_count} duplicate records for keys: {list(unique_keys)}"
                )
                is_valid = False

            for key in unique_keys:
                null_count = df[key].isna().sum()

                if null_count > 0:
                    logs.append(f"Column '{key}' contains {null_count} null values.")
                    is_valid = False

    if is_valid:
        logs.append("Data validation checks passed.")

    return is_valid, logs


def raise_if_invalid(is_valid: bool, logs: list[str]) -> None:
    if not is_valid:
        message = "\n".join(logs)
        raise ValueError(f"Dataset validation failed:\n{message}")