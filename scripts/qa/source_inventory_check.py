"""
source_inventory_check.py

Project Atlas / Finance Intelligence Platform
Phase 3O - Source Output Inventory Check

Purpose
-------
Scans data/raw/**/*.csv and produces a lightweight source-output inventory:
- data/raw/governance/source_output_inventory.csv

This is a governance/readiness artefact for the DuckDB/dbt ingestion phase.
It does not mutate any source-system data.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd

try:
    from scripts.utils.logger import get_logger
except Exception:  # pragma: no cover - fallback for standalone execution
    import logging

    def get_logger(name: str, log_file: str):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
        return logging.getLogger(name)


logger = get_logger("SourceInventoryCheck", "generation_execution.log")


@dataclass(frozen=True)
class SourceInventoryRules:
    created_at: str = "2026-06-03"
    output_filename: str = "source_output_inventory.csv"


class SourceInventoryCheck:
    """Build a raw source file inventory for Project Atlas."""

    OUTPUT_COLUMNS = [
        "source_domain",
        "file_name",
        "file_path",
        "row_count",
        "column_count",
        "file_size_mb",
        "last_modified_at",
        "status",
        "notes",
        "created_at",
    ]

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or self._resolve_project_root()
        self.raw_root = self.project_root / "data" / "raw"
        self.output_dir = self.raw_root / "governance"
        self.rules = SourceInventoryRules()

    @staticmethod
    def _resolve_project_root() -> Path:
        current = Path.cwd().resolve()
        for candidate in [current, *current.parents]:
            if (candidate / "data" / "raw").exists() and (candidate / "scripts").exists():
                return candidate
        return current

    @staticmethod
    def _file_size_mb(path: Path) -> float:
        return round(path.stat().st_size / (1024 * 1024), 4)

    @staticmethod
    def _last_modified(path: Path) -> str:
        return pd.Timestamp(path.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S")

    def _inspect_csv(self, path: Path) -> dict:
        source_domain = path.parent.name
        relative_path = path.relative_to(self.project_root).as_posix()

        try:
            # Use streaming to keep the check usable as data grows.
            row_count = 0
            column_count = 0
            for chunk in pd.read_csv(path, chunksize=100_000):
                if column_count == 0:
                    column_count = len(chunk.columns)
                row_count += len(chunk)

            status = "PASS" if row_count > 0 else "WARN"
            notes = "OK" if row_count > 0 else "CSV has zero data rows"

        except Exception as error:  # noqa: BLE001 - governance artefact should capture failures
            row_count = 0
            column_count = 0
            status = "FAIL"
            notes = f"Could not read CSV: {error}"

        return {
            "source_domain": source_domain,
            "file_name": path.name,
            "file_path": relative_path,
            "row_count": row_count,
            "column_count": column_count,
            "file_size_mb": self._file_size_mb(path),
            "last_modified_at": self._last_modified(path),
            "status": status,
            "notes": notes,
            "created_at": self.rules.created_at,
        }

    def generate(self) -> pd.DataFrame:
        if not self.raw_root.exists():
            raise FileNotFoundError(f"Raw data folder not found: {self.raw_root}")

        csv_paths = sorted(self.raw_root.glob("**/*.csv"))
        if not csv_paths:
            raise FileNotFoundError(f"No CSV files found under {self.raw_root}")

        rows = [self._inspect_csv(path) for path in csv_paths]
        inventory = pd.DataFrame(rows, columns=self.OUTPUT_COLUMNS)

        logger.info(
            "Source output inventory generated: %s CSV files scanned across %s domains.",
            f"{len(inventory):,}",
            f"{inventory['source_domain'].nunique():,}",
        )
        return inventory

    def save(self, inventory: pd.DataFrame) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / self.rules.output_filename
        inventory.to_csv(output_path, index=False)
        logger.info("Source output inventory saved to %s", output_path)


def main() -> None:
    try:
        check = SourceInventoryCheck()
        inventory = check.generate()
        check.save(inventory)
    except Exception as error:  # noqa: BLE001
        logger.critical("Source inventory check failed: %s", error, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
