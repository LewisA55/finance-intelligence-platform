"""
modeling_layer_generator.py

Project Atlas / Nexus Technologies
Phase 8 - CFO Modelling Layer Sources

Purpose
-------
Generates lightweight raw source files that anchor the CFO model-serving layer:
- data/raw/accounting/opening_balance_sheet.csv
- data/raw/governance/model_readiness_controls.csv

These files are intentionally small policy/source artifacts. The warehouse
serves actuals and readiness classifications; Excel owns forecast assumptions
and integrated statement logic.
"""

from __future__ import annotations

import pandas as pd

from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path
from scripts.utils.validation import raise_if_invalid, verify_dataset_integrity


logger = get_logger("ModelingLayerGenerator", "generation_execution.log")


class ModelingLayerGenerator:
    """Generate CFO modelling layer source anchors and readiness policy."""

    opening_balance_filename = "opening_balance_sheet.csv"
    readiness_controls_filename = "model_readiness_controls.csv"

    def generate(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        opening_balance_sheet = pd.DataFrame(
            [
                {
                    "as_of_date": "2025-12-31",
                    "cash_gbp": 28_000_000.00,
                    "accounts_receivable_gbp": 1_487_011.84,
                    "prepaids_other_current_assets_gbp": 1_250_000.00,
                    "ppe_gbp": 8_500_000.00,
                    "accumulated_depreciation_gbp": -2_100_000.00,
                    "accounts_payable_gbp": 0.00,
                    "deferred_revenue_gbp": 20_964_418.64,
                    "debt_gbp": 6_000_000.00,
                    "share_capital_gbp": 5_000_000.00,
                    "retained_earnings_gbp": 5_172_593.20,
                    "source_system": "Atlas synthetic opening balance sheet",
                    "model_note": "Opening statutory balance sheet anchor for the CFO modelling layer.",
                }
            ]
        )

        model_readiness_controls = pd.DataFrame(
            [
                {
                    "control_key": "financial_performance_defects",
                    "control_name": "Financial performance source defects",
                    "control_domain": "Financial Performance",
                    "severity": "High",
                    "model_blocking_flag": True,
                    "accepted_limitation_flag": False,
                    "recommended_treatment": "Block model sign-off until financial performance defects are cleared or explained.",
                },
                {
                    "control_key": "o2c_collection_defects",
                    "control_name": "Order-to-cash allocation and invoice defects",
                    "control_domain": "Order-to-Cash",
                    "severity": "Medium",
                    "model_blocking_flag": False,
                    "accepted_limitation_flag": False,
                    "recommended_treatment": "Monitor as cash-conversion quality signal; review large or increasing exception trends.",
                },
                {
                    "control_key": "o2c_over_applied_cash",
                    "control_name": "Over-applied cash in O2C",
                    "control_domain": "Order-to-Cash",
                    "severity": "Medium",
                    "model_blocking_flag": False,
                    "accepted_limitation_flag": False,
                    "recommended_treatment": "Monitor and normalise in working-capital assumptions where exposure is immaterial.",
                },
                {
                    "control_key": "revenue_governance_exceptions",
                    "control_name": "Revenue recognition governance exceptions",
                    "control_domain": "Revenue Recognition",
                    "severity": "High",
                    "model_blocking_flag": False,
                    "accepted_limitation_flag": False,
                    "recommended_treatment": (
                        "Use in forecast baseline only after reviewing revenue exception trend "
                        "and excluding materially defective periods if required."
                    ),
                },
                {
                    "control_key": "deferred_revenue_control_exceptions",
                    "control_name": "Deferred revenue rollforward exceptions",
                    "control_domain": "Deferred Revenue",
                    "severity": "High",
                    "model_blocking_flag": True,
                    "accepted_limitation_flag": False,
                    "recommended_treatment": "Block model sign-off until rollforward arithmetic and continuity are clean.",
                },
                {
                    "control_key": "ap_control_exceptions",
                    "control_name": "Accounts payable control exceptions",
                    "control_domain": "Accounts Payable",
                    "severity": "Medium",
                    "model_blocking_flag": False,
                    "accepted_limitation_flag": True,
                    "recommended_treatment": "Treat as accepted source limitation for modelling actuals; forecast AP through DPO assumptions.",
                },
                {
                    "control_key": "workforce_control_issues",
                    "control_name": "Workforce HRIS/payroll control issues",
                    "control_domain": "Workforce",
                    "severity": "Medium",
                    "model_blocking_flag": False,
                    "accepted_limitation_flag": True,
                    "recommended_treatment": (
                        "Treat as accepted source limitation unless payroll cost or FTE totals "
                        "are materially affected."
                    ),
                },
                {
                    "control_key": "saas_arr_control_issues",
                    "control_name": "SaaS ARR bridge control issues",
                    "control_domain": "SaaS",
                    "severity": "Medium",
                    "model_blocking_flag": False,
                    "accepted_limitation_flag": True,
                    "recommended_treatment": "Accepted source definition limitation; forecast headline ARR directly from model assumptions.",
                },
                {
                    "control_key": "saas_retention_control_issues",
                    "control_name": "SaaS retention control issues",
                    "control_domain": "SaaS",
                    "severity": "Medium",
                    "model_blocking_flag": False,
                    "accepted_limitation_flag": True,
                    "recommended_treatment": (
                        "Accepted source definition limitation; use NRR/GRR as directional KPI "
                        "inputs, not model-blocking checks."
                    ),
                },
            ]
        )

        self._validate(opening_balance_sheet, model_readiness_controls)
        logger.info(
            "Generated modelling layer sources: %s opening balance sheet row, %s readiness controls.",
            len(opening_balance_sheet),
            len(model_readiness_controls),
        )
        return opening_balance_sheet, model_readiness_controls

    @staticmethod
    def _validate(opening_balance_sheet: pd.DataFrame, model_readiness_controls: pd.DataFrame) -> None:
        opening_required = [
            "as_of_date",
            "cash_gbp",
            "accounts_receivable_gbp",
            "prepaids_other_current_assets_gbp",
            "ppe_gbp",
            "accumulated_depreciation_gbp",
            "accounts_payable_gbp",
            "deferred_revenue_gbp",
            "debt_gbp",
            "share_capital_gbp",
            "retained_earnings_gbp",
        ]
        readiness_required = [
            "control_key",
            "control_name",
            "control_domain",
            "severity",
            "model_blocking_flag",
            "accepted_limitation_flag",
            "recommended_treatment",
        ]

        is_valid, validation_logs = verify_dataset_integrity(
            df=opening_balance_sheet,
            required_columns=opening_required,
            unique_keys=["as_of_date"],
        )
        raise_if_invalid(is_valid, validation_logs)

        is_valid, validation_logs = verify_dataset_integrity(
            df=model_readiness_controls,
            required_columns=readiness_required,
            unique_keys=["control_key"],
        )
        raise_if_invalid(is_valid, validation_logs)

        valid_severities = {"High", "Medium", "Low"}
        invalid_severities = set(model_readiness_controls["severity"]) - valid_severities
        if invalid_severities:
            raise ValueError(f"Invalid model readiness severities: {sorted(invalid_severities)}")

    def save(
        self,
        opening_balance_sheet: pd.DataFrame,
        model_readiness_controls: pd.DataFrame,
    ) -> None:
        accounting_dir = get_raw_data_path("accounting")
        governance_dir = get_raw_data_path("governance")

        opening_balance_sheet.to_csv(
            accounting_dir / self.opening_balance_filename,
            index=False,
            encoding="utf-8",
        )
        model_readiness_controls.to_csv(
            governance_dir / self.readiness_controls_filename,
            index=False,
            encoding="utf-8",
        )

        logger.info("Opening balance sheet written to %s", accounting_dir / self.opening_balance_filename)
        logger.info("Model readiness controls written to %s", governance_dir / self.readiness_controls_filename)


def main() -> None:
    generator = ModelingLayerGenerator()
    opening_balance_sheet, model_readiness_controls = generator.generate()
    generator.save(opening_balance_sheet, model_readiness_controls)


if __name__ == "__main__":
    main()
