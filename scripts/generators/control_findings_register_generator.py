"""
control_findings_register_generator.py

Project Atlas / Nexus Technologies
Phase 3J.4 - Control Findings Register

Purpose
-------
Generates:
- data/raw/accounting/control_findings_register.csv

This dataset converts failed financial statement controls into an itemised,
deduplicated internal controls findings register. It is designed to support
CFO review, analytics engineering ownership, audit-style remediation tracking,
and downstream governance dashboards.

Design
------
financial_statement_controls.csv
    = time-series control execution result grid

control_findings_register.csv
    = consolidated register of open control deficiencies requiring ownership,
      severity assessment, and remediation tracking

The generator intentionally groups repeated failed control rows into systemic
findings rather than creating one issue per failed control row.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pandas as pd

from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("ControlFindingsRegisterGenerator", "generation_execution.log")


@dataclass(frozen=True)
class ControlFindingsRegisterRules:
    """Rules for control findings register generation."""

    created_at: str = "2026-06-03"
    updated_at: str = "2026-06-03"
    default_status: str = "Open"
    high_threshold_gbp: float = 1_000_000.00
    medium_threshold_gbp: float = 100_000.00


class ControlFindingsRegisterGenerator:
    """
    Generate a deduplicated control findings register from failed control rows.

    Input
    -----
    data/raw/accounting/financial_statement_controls.csv

    Output
    ------
    data/raw/accounting/control_findings_register.csv
    """

    input_filename = "financial_statement_controls.csv"
    output_filename = "control_findings_register.csv"

    REQUIRED_CONTROL_COLUMNS = {
        "control_pk",
        "posting_period",
        "currency",
        "control_check",
        "control_category",
        "expected_value_gbp",
        "actual_value_gbp",
        "variance_value_gbp",
        "absolute_variance_gbp",
        "materiality_threshold",
        "control_status",
        "severity",
        "source_dataset",
        "description",
        "created_at",
        "updated_at",
    }

    OUTPUT_COLUMNS = [
        "finding_pk",
        "finding_id",
        "finding_title",
        "finding_description",
        "control_check",
        "control_category",
        "root_cause_category",
        "financial_statement_area",
        "owner_team",
        "affected_currencies",
        "affected_currency_count",
        "first_failed_period",
        "latest_failed_period",
        "failed_control_row_count",
        "source_control_row_ids",
        "largest_variance_gbp",
        "latest_variance_gbp",
        "risk_rating",
        "severity",
        "finding_status",
        "remediation_action",
        "target_resolution_date",
        "source_dataset",
        "source_system",
        "is_system_generated",
        "created_at",
        "updated_at",
    ]

    FINDING_METADATA = {
        "AR_CONTROL_TIE_OUT_CHECK": {
            "title": "Accounts receivable subledger does not reconcile to GL control account",
            "description": (
                "Customer AR subledger open balances do not reconcile to Trial Balance "
                "account 1100 Accounts Receivable at the latest actual reporting period. "
                "The finding is driven by a combination of unsupported billing currencies "
                "and broader O2C subledger-to-ledger alignment differences."
            ),
            "root_cause_category": "Unsupported Ledger Currency / Configuration Gap",
            "financial_statement_area": "Balance Sheet - Current Assets / Accounts Receivable",
            "owner_team": "Finance Systems / O2C Operations",
            "remediation_action": (
                "Review supported GL posting currencies, AR control account mapping, "
                "cash account provisioning, and billing-to-ledger interface rules. Decide "
                "whether AUD/CAD should be onboarded into the ERP ledger or explicitly "
                "classified as out-of-scope in downstream control views."
            ),
            "target_resolution_date": "2026-09-30",
        },
        "DEFERRED_REVENUE_CONTROL_TIE_OUT_CHECK": {
            "title": "Deferred revenue roll-forward does not reconcile to GL control account",
            "description": (
                "Deferred revenue roll-forward closing balances do not reconcile to Trial "
                "Balance account 2100 Deferred Revenue at the latest actual reporting period. "
                "The finding indicates a subledger-to-ledger reconciliation break between "
                "the operational revenue schedule and the ERP GL posting layer."
            ),
            "root_cause_category": "Subledger / GL Reconciliation Break",
            "financial_statement_area": "Balance Sheet - Liabilities / Deferred Revenue",
            "owner_team": "Revenue Accounting / Finance Systems",
            "remediation_action": (
                "Reconcile deferred revenue roll-forward logic to GL posting rules, review "
                "revenue recognition schedule completeness, inspect period cut-off handling, "
                "and determine whether an interface mapping or timing adjustment is required."
            ),
            "target_resolution_date": "2026-09-30",
        },
        "AP_CONTROL_TIE_OUT_CHECK": {
            "title": "Accounts payable subledger does not reconcile to GL control account",
            "description": (
                "Vendor AP subledger open obligations do not reconcile to Trial Balance "
                "account 2300 Accounts Payable at the latest actual reporting period."
            ),
            "root_cause_category": "Subledger / GL Reconciliation Break",
            "financial_statement_area": "Balance Sheet - Current Liabilities / Accounts Payable",
            "owner_team": "P2P Operations / Finance Systems",
            "remediation_action": (
                "Review vendor invoice posting, vendor payment allocation, and AP ageing "
                "snapshot logic to identify the source of unreconciled AP balances."
            ),
            "target_resolution_date": "2026-09-30",
        },
    }

    def __init__(self) -> None:
        self.rules = ControlFindingsRegisterRules()

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pk(value: str) -> str:
        return hashlib.md5(value.strip().upper().encode("utf-8")).hexdigest()

    @staticmethod
    def _round_money(value: object) -> float:
        if pd.isna(value):
            return 0.00
        return round(float(value), 2)

    @staticmethod
    def _require_columns(
        df: pd.DataFrame,
        required_columns: set[str],
        dataset_name: str,
    ) -> None:
        missing_columns = required_columns.difference(df.columns)

        if missing_columns:
            raise ValueError(
                f"{dataset_name} is missing required columns: {sorted(missing_columns)}"
            )

    # ------------------------------------------------------------------
    # Loading and preparation
    # ------------------------------------------------------------------

    def _load_controls(self) -> pd.DataFrame:
        accounting_dir = get_raw_data_path("accounting")
        path = accounting_dir / self.input_filename

        if not path.exists():
            raise FileNotFoundError(
                f"{self.input_filename} not found at {path}. Run Phase 3J.3 first."
            )

        controls_df = pd.read_csv(path)
        self._require_columns(
            controls_df,
            self.REQUIRED_CONTROL_COLUMNS,
            self.input_filename,
        )

        controls_df = self._prepare_controls(controls_df)

        logger.info(
            "Loaded control findings dependency: %s financial statement control rows.",
            f"{len(controls_df):,}",
        )

        return controls_df

    def _prepare_controls(self, controls_df: pd.DataFrame) -> pd.DataFrame:
        df = controls_df.copy()

        if df.empty:
            raise ValueError("financial_statement_controls.csv is empty.")

        for column in [
            "control_pk",
            "posting_period",
            "currency",
            "control_check",
            "control_category",
            "control_status",
            "severity",
            "source_dataset",
            "description",
        ]:
            df[column] = df[column].fillna("").astype(str)

        for column in [
            "expected_value_gbp",
            "actual_value_gbp",
            "variance_value_gbp",
            "absolute_variance_gbp",
            "materiality_threshold",
        ]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00)

        if df["posting_period"].eq("").any():
            raise ValueError("financial_statement_controls.csv contains blank posting_period values.")

        if df["control_check"].eq("").any():
            raise ValueError("financial_statement_controls.csv contains blank control_check values.")

        return df

    # ------------------------------------------------------------------
    # Finding classification
    # ------------------------------------------------------------------

    def _classify_risk_rating(self, largest_variance_gbp: float, control_check: str) -> str:
        if largest_variance_gbp >= self.rules.high_threshold_gbp:
            return "High"

        if control_check in {
            "BALANCE_SHEET_EQUATION_CHECK",
            "TRIAL_BALANCE_GBP_ZERO_CHECK",
            "GL_JOURNAL_BALANCE_CHECK",
        }:
            return "High"

        if largest_variance_gbp >= self.rules.medium_threshold_gbp:
            return "Medium"

        return "Low"

    def _classify_severity(self, risk_rating: str) -> str:
        return risk_rating.upper()

    def _fallback_metadata(self, control_check: str, control_category: str) -> dict[str, str]:
        friendly_name = control_check.replace("_", " ").title()
        return {
            "title": f"{friendly_name} failed control threshold",
            "description": (
                f"Control check {control_check} has one or more failed rows in the "
                "financial statement control summary and requires investigation."
            ),
            "root_cause_category": "Unknown",
            "financial_statement_area": control_category,
            "owner_team": "Finance Systems / Data Platform",
            "remediation_action": (
                "Review failed control rows, validate upstream source data, and determine "
                "whether the issue is caused by source data, posting logic, mapping, or timing."
            ),
            "target_resolution_date": "2026-09-30",
        }

    # ------------------------------------------------------------------
    # Finding construction
    # ------------------------------------------------------------------

    def _build_findings(self, controls_df: pd.DataFrame) -> pd.DataFrame:
        failed_df = controls_df[
            controls_df["control_status"].str.upper().eq("FAIL")
        ].copy()

        if failed_df.empty:
            logger.info("No failed controls found. Control findings register will be empty.")
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        records: list[dict] = []

        for sequence, (control_check, group) in enumerate(
            failed_df.groupby("control_check", sort=True),
            start=1,
        ):
            group = group.copy().sort_values(["posting_period", "currency"])

            control_category = str(group["control_category"].mode().iloc[0])
            affected_currencies = sorted(group["currency"].dropna().astype(str).unique())
            first_failed_period = str(group["posting_period"].min())
            latest_failed_period = str(group["posting_period"].max())

            largest_variance_gbp = self._round_money(group["absolute_variance_gbp"].max())

            latest_group = group[group["posting_period"] == latest_failed_period]
            latest_variance_gbp = self._round_money(latest_group["absolute_variance_gbp"].max())

            risk_rating = self._classify_risk_rating(largest_variance_gbp, control_check)
            severity = self._classify_severity(risk_rating)

            metadata = self.FINDING_METADATA.get(
                control_check,
                self._fallback_metadata(control_check, control_category),
            )

            source_control_ids = " | ".join(group["control_pk"].astype(str).tolist())
            source_datasets = " | ".join(
                sorted(set(" | ".join(group["source_dataset"].astype(str)).split(" | ")))
            )

            finding_id = f"FIND-3J4-{sequence:04d}"
            finding_pk = self._generate_pk(finding_id)

            records.append(
                {
                    "finding_pk": finding_pk,
                    "finding_id": finding_id,
                    "finding_title": metadata["title"],
                    "finding_description": metadata["description"],
                    "control_check": control_check,
                    "control_category": control_category,
                    "root_cause_category": metadata["root_cause_category"],
                    "financial_statement_area": metadata["financial_statement_area"],
                    "owner_team": metadata["owner_team"],
                    "affected_currencies": " | ".join(affected_currencies),
                    "affected_currency_count": int(len(affected_currencies)),
                    "first_failed_period": first_failed_period,
                    "latest_failed_period": latest_failed_period,
                    "failed_control_row_count": int(len(group)),
                    "source_control_row_ids": source_control_ids,
                    "largest_variance_gbp": largest_variance_gbp,
                    "latest_variance_gbp": latest_variance_gbp,
                    "risk_rating": risk_rating,
                    "severity": severity,
                    "finding_status": self.rules.default_status,
                    "remediation_action": metadata["remediation_action"],
                    "target_resolution_date": metadata["target_resolution_date"],
                    "source_dataset": source_datasets,
                    "source_system": "project_atlas_financial_controls",
                    "is_system_generated": 1,
                    "created_at": self.rules.created_at,
                    "updated_at": self.rules.updated_at,
                }
            )

        findings_df = pd.DataFrame(records)
        findings_df = findings_df[self.OUTPUT_COLUMNS].copy()
        findings_df = findings_df.sort_values(
            ["risk_rating", "largest_variance_gbp", "control_check"],
            ascending=[True, False, True],
        ).reset_index(drop=True)

        return findings_df

    # ------------------------------------------------------------------
    # Validation and review
    # ------------------------------------------------------------------

    def _validate_output(self, findings_df: pd.DataFrame, controls_df: pd.DataFrame) -> None:
        missing_columns = set(self.OUTPUT_COLUMNS).difference(findings_df.columns)
        if missing_columns:
            raise ValueError(f"Output is missing required columns: {sorted(missing_columns)}")

        if findings_df.empty:
            failed_count = int(controls_df["control_status"].str.upper().eq("FAIL").sum())
            if failed_count > 0:
                raise ValueError("Failed controls exist but no findings were generated.")
            return

        if findings_df["finding_pk"].duplicated().any():
            duplicate_count = int(findings_df["finding_pk"].duplicated().sum())
            raise ValueError(f"Duplicate finding_pk values detected: {duplicate_count:,}")

        if findings_df["finding_id"].duplicated().any():
            duplicate_count = int(findings_df["finding_id"].duplicated().sum())
            raise ValueError(f"Duplicate finding_id values detected: {duplicate_count:,}")

        if findings_df["control_check"].duplicated().any():
            duplicate_count = int(findings_df["control_check"].duplicated().sum())
            raise ValueError(
                "Control findings register should contain one consolidated row per failed "
                f"control_check. Duplicate checks detected: {duplicate_count:,}"
            )

        failed_control_checks = set(
            controls_df.loc[
                controls_df["control_status"].str.upper().eq("FAIL"),
                "control_check",
            ].astype(str)
        )
        finding_control_checks = set(findings_df["control_check"].astype(str))

        if failed_control_checks != finding_control_checks:
            raise ValueError(
                "Finding coverage mismatch. Failed controls: "
                f"{sorted(failed_control_checks)}. Findings: {sorted(finding_control_checks)}"
            )

        invalid_statuses = set(findings_df["finding_status"].unique()).difference(
            {"Open", "In Review", "Remediation In Progress", "Resolved", "Accepted Risk"}
        )
        if invalid_statuses:
            raise ValueError(f"Invalid finding_status values: {sorted(invalid_statuses)}")

        invalid_risk_ratings = set(findings_df["risk_rating"].unique()).difference(
            {"High", "Medium", "Low"}
        )
        if invalid_risk_ratings:
            raise ValueError(f"Invalid risk_rating values: {sorted(invalid_risk_ratings)}")

        if (findings_df["largest_variance_gbp"] < 0).any():
            raise ValueError("largest_variance_gbp should never be negative.")

        logger.info("Control Findings Register validation passed.")

    def _log_review_summary(self, findings_df: pd.DataFrame, controls_df: pd.DataFrame) -> None:
        failed_controls_count = int(controls_df["control_status"].str.upper().eq("FAIL").sum())

        logger.info("----- Control Findings Register Review -----")
        logger.info("Failed control rows consumed: %s", f"{failed_controls_count:,}")
        logger.info("Control findings generated: %s", f"{len(findings_df):,}")

        if findings_df.empty:
            logger.info("No open findings generated.")
            logger.info("--------------------------------------------")
            return

        logger.info(
            "Findings by risk rating:\n%s",
            findings_df["risk_rating"].value_counts(dropna=False).to_string(),
        )
        logger.info(
            "Findings by owner team:\n%s",
            findings_df["owner_team"].value_counts(dropna=False).to_string(),
        )
        logger.info(
            "Largest finding variances GBP:\n%s",
            findings_df.set_index("finding_id")["largest_variance_gbp"]
            .sort_values(ascending=False)
            .round(2)
            .to_string(),
        )
        logger.info("--------------------------------------------")

    # ------------------------------------------------------------------
    # Main entry points
    # ------------------------------------------------------------------

    def generate(self) -> pd.DataFrame:
        logger.info("Generating Phase 3J.4 Control Findings Register.")
        controls_df = self._load_controls()
        findings_df = self._build_findings(controls_df)
        self._validate_output(findings_df, controls_df)
        self._log_review_summary(findings_df, controls_df)
        return findings_df

    def save(self, findings_df: pd.DataFrame) -> None:
        output_path = get_raw_data_path("accounting") / self.output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        findings_df.to_csv(output_path, index=False)
        logger.info("Control findings register saved to %s", output_path)


if __name__ == "__main__":
    generator = ControlFindingsRegisterGenerator()
    findings = generator.generate()
    generator.save(findings)
