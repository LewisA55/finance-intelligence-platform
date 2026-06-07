"""
source_generation_qa.py

Project Atlas / Finance Intelligence Platform
Phase 3O - Source Generation QA Results

Purpose
-------
Runs high-level source-generation readiness checks and writes:
- data/raw/governance/source_generation_qa_results.csv

This script is intentionally macro-level. It is not a replacement for dbt tests.
It provides a compact sign-off artefact before DuckDB/dbt ingestion.
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


logger = get_logger("SourceGenerationQA", "generation_execution.log")


@dataclass(frozen=True)
class SourceQARules:
    created_at: str = "2026-06-03"
    output_filename: str = "source_generation_qa_results.csv"
    tolerance: float = 1.00
    tight_tolerance: float = 0.05
    actual_period_start: str = "2026-01"
    actual_period_end: str = "2026-03"
    fy2025_budget_version: str = "AOP_FY2025_ORIGINAL"
    fy2026_budget_version: str = "AOP_FY2026_BOARD_APPROVED"
    fy2025_revenue_target_gbp: float = 72_000_000.00
    fy2026_revenue_target_gbp: float = 96_000_000.00


class SourceGenerationQA:
    """Run Phase 3O high-level source-generation QA checks."""

    OUTPUT_COLUMNS = [
        "check_name",
        "check_category",
        "expected_value",
        "actual_value",
        "variance",
        "status",
        "severity",
        "notes",
        "created_at",
    ]

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or self._resolve_project_root()
        self.raw_root = self.project_root / "data" / "raw"
        self.output_dir = self.raw_root / "governance"
        self.rules = SourceQARules()
        self.results: list[dict] = []

    @staticmethod
    def _resolve_project_root() -> Path:
        current = Path.cwd().resolve()
        for candidate in [current, *current.parents]:
            if (candidate / "data" / "raw").exists() and (candidate / "scripts").exists():
                return candidate
        return current

    @staticmethod
    def _round_money(value: object) -> float:
        if pd.isna(value):
            return 0.00
        return round(float(value), 2)

    def _csv(self, domain: str, filename: str, required: bool = True) -> pd.DataFrame:
        path = self.raw_root / domain / filename
        if not path.exists():
            if required:
                raise FileNotFoundError(f"Required source file missing: {path}")
            return pd.DataFrame()
        return pd.read_csv(path)

    def _add_result(
        self,
        *,
        check_name: str,
        check_category: str,
        expected_value: object,
        actual_value: object,
        variance: object,
        passed: bool,
        severity: str,
        notes: str,
    ) -> None:
        self.results.append(
            {
                "check_name": check_name,
                "check_category": check_category,
                "expected_value": expected_value,
                "actual_value": actual_value,
                "variance": variance,
                "status": "PASS" if passed else "FAIL",
                "severity": "INFO" if passed else severity,
                "notes": notes,
                "created_at": self.rules.created_at,
            }
        )

    def _run_safely(self, check_name: str, func) -> None:
        try:
            func()
        except Exception as error:  # noqa: BLE001 - QA should continue and report failures
            self._add_result(
                check_name=check_name,
                check_category="Execution",
                expected_value="Check completes without exception",
                actual_value=type(error).__name__,
                variance="N/A",
                passed=False,
                severity="HIGH",
                notes=str(error),
            )

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def check_gl_journal_balance(self) -> None:
        gl = self._csv("accounting", "erp_gl_journal_lines.csv")
        grouped = gl.groupby("journal_id", as_index=False).agg(
            debit_gbp=("debit_gbp", "sum"),
            credit_gbp=("credit_gbp", "sum"),
            debit_local=("debit_local", "sum"),
            credit_local=("credit_local", "sum"),
        )
        grouped["variance_gbp"] = (grouped["debit_gbp"] - grouped["credit_gbp"]).round(2)
        grouped["variance_local"] = (grouped["debit_local"] - grouped["credit_local"]).round(2)
        max_abs_gbp = self._round_money(grouped["variance_gbp"].abs().max())
        max_abs_local = self._round_money(grouped["variance_local"].abs().max())
        unbalanced = int(
            ((grouped["variance_gbp"].abs() > self.rules.tight_tolerance) | (grouped["variance_local"].abs() > self.rules.tight_tolerance)).sum()
        )
        self._add_result(
            check_name="GL_JOURNAL_BALANCE_CHECK",
            check_category="Accounting Integrity",
            expected_value="0 unbalanced journals",
            actual_value=unbalanced,
            variance=max(max_abs_gbp, max_abs_local),
            passed=unbalanced == 0,
            severity="CRITICAL",
            notes=f"Max abs GBP variance {max_abs_gbp}; max abs local variance {max_abs_local}; journals checked {len(grouped):,}.",
        )

    def check_trial_balance_zero(self) -> None:
        tb = self._csv("accounting", "trial_balance.csv")
        by_period = tb.groupby("posting_period", as_index=False)["closing_balance_gbp"].sum()
        by_period["closing_balance_gbp"] = by_period["closing_balance_gbp"].round(2)
        max_abs = self._round_money(by_period["closing_balance_gbp"].abs().max())
        self._add_result(
            check_name="TRIAL_BALANCE_GBP_ZERO_CHECK",
            check_category="Accounting Integrity",
            expected_value=0.00,
            actual_value=max_abs,
            variance=max_abs,
            passed=max_abs <= self.rules.tight_tolerance,
            severity="CRITICAL",
            notes=f"Max absolute period-level closing balance GBP imbalance across {len(by_period):,} periods.",
        )

    def check_balance_sheet_check(self) -> None:
        fs = self._csv("accounting", "financial_statement_extract.csv")
        checks = fs[fs.get("calculation_type", "").astype(str) == "BALANCE_SHEET_CHECK"].copy()
        if checks.empty:
            self._add_result(
                check_name="BALANCE_SHEET_EQUATION_CHECK",
                check_category="Financial Statement Integrity",
                expected_value="BALANCE_SHEET_CHECK rows present",
                actual_value=0,
                variance="N/A",
                passed=False,
                severity="CRITICAL",
                notes="No BALANCE_SHEET_CHECK rows found in financial_statement_extract.csv.",
            )
            return
        max_abs = self._round_money(checks["amount_gbp"].abs().max())
        self._add_result(
            check_name="BALANCE_SHEET_EQUATION_CHECK",
            check_category="Financial Statement Integrity",
            expected_value=0.00,
            actual_value=max_abs,
            variance=max_abs,
            passed=max_abs <= self.rules.tight_tolerance,
            severity="CRITICAL",
            notes=f"Max absolute balance sheet check amount GBP across {len(checks):,} rows.",
        )

    def check_controls_to_findings(self) -> None:
        controls = self._csv("accounting", "financial_statement_controls.csv")
        findings = self._csv("accounting", "control_findings_register.csv")
        failed = controls[controls["control_status"].astype(str).str.upper() == "FAIL"].copy()
        failed_check_count = int(failed["control_check"].nunique())
        finding_check_count = int(findings["control_check"].nunique())
        failed_row_count = int(len(failed))
        finding_failed_rows = int(pd.to_numeric(findings.get("failed_control_row_count", 0), errors="coerce").fillna(0).sum())
        passed = failed_check_count == finding_check_count and failed_row_count == finding_failed_rows
        self._add_result(
            check_name="CONTROL_FINDINGS_RECONCILE_FAILED_CONTROLS",
            check_category="Governance",
            expected_value=f"{failed_check_count} failed control groups / {failed_row_count} failed rows",
            actual_value=f"{finding_check_count} findings / {finding_failed_rows} source failed rows",
            variance=failed_row_count - finding_failed_rows,
            passed=passed,
            severity="HIGH",
            notes="Validates that failed financial controls are represented in the deduplicated findings register.",
        )

    def check_payroll_to_compensation(self) -> None:
        comp = self._csv("workforce", "employee_compensation.csv")
        payroll = self._csv("workforce", "payroll_expense_lines.csv")
        comp_group = comp.groupby(
            ["posting_period", "department_id", "currency", "compensation_component"],
            as_index=False,
        )["amount_gbp"].sum()
        comp_group = comp_group.rename(columns={"compensation_component": "cost_component", "amount_gbp": "compensation_gbp"})
        payroll_group = payroll.groupby(
            ["posting_period", "department_id", "currency", "cost_component"],
            as_index=False,
        )["debit_gbp"].sum()
        merged = comp_group.merge(payroll_group, on=["posting_period", "department_id", "currency", "cost_component"], how="outer")
        merged[["compensation_gbp", "debit_gbp"]] = merged[["compensation_gbp", "debit_gbp"]].fillna(0.00)
        merged["variance_gbp"] = (merged["compensation_gbp"] - merged["debit_gbp"]).round(2)
        max_abs = self._round_money(merged["variance_gbp"].abs().max())
        mismatch_count = int((merged["variance_gbp"].abs() > self.rules.tolerance).sum())
        self._add_result(
            check_name="PAYROLL_TO_COMPENSATION_TIE_OUT",
            check_category="Workforce Integrity",
            expected_value="0 mismatched payroll groups",
            actual_value=mismatch_count,
            variance=max_abs,
            passed=mismatch_count == 0,
            severity="HIGH",
            notes=f"Payroll expense lines tie to employee compensation at period/department/currency/component grain. Groups checked {len(merged):,}.",
        )

    def check_budget_revenue_targets(self) -> None:
        budget = self._csv("planning", "budget_lines.csv")
        revenue = budget[budget["account_class"].astype(str).str.lower() == "revenue"].copy()
        totals = revenue.groupby("budget_version_code")["budget_amount_gbp"].sum().round(2).to_dict()
        expected = {
            self.rules.fy2025_budget_version: self.rules.fy2025_revenue_target_gbp,
            self.rules.fy2026_budget_version: self.rules.fy2026_revenue_target_gbp,
        }
        variances = {version: self._round_money(totals.get(version, 0.00) - target) for version, target in expected.items()}
        max_abs = max(abs(v) for v in variances.values()) if variances else 0.00
        self._add_result(
            check_name="BUDGET_REVENUE_TARGET_CHECK",
            check_category="Planning Integrity",
            expected_value=expected,
            actual_value={k: self._round_money(v) for k, v in totals.items()},
            variance=variances,
            passed=max_abs <= self.rules.tolerance,
            severity="HIGH",
            notes="Validates locked AOP revenue targets for FY2025 and FY2026.",
        )

    def _fs_actual_revenue_basis(self) -> float:
        fs = self._csv("accounting", "financial_statement_extract.csv")
        mask = (
            (fs["posting_period"].astype(str) >= self.rules.actual_period_start)
            & (fs["posting_period"].astype(str) <= self.rules.actual_period_end)
            & (fs["account_class"].astype(str).str.lower() == "revenue")
            & (pd.to_numeric(fs["is_calculated_line"], errors="coerce").fillna(0).astype(int) == 0)
        )
        return self._round_money(fs.loc[mask, "amount_gbp"].sum())

    def check_forecast_actual_revenue_tie_out(self) -> None:
        forecast = self._csv("planning", "forecast_lines.csv")
        fs_revenue = self._fs_actual_revenue_basis()
        mask = (
            (forecast["posting_period"].astype(str) >= self.rules.actual_period_start)
            & (forecast["posting_period"].astype(str) <= self.rules.actual_period_end)
            & (forecast["account_class"].astype(str).str.lower() == "revenue")
        )
        scenario_totals = forecast.loc[mask].groupby("forecast_version_code")["forecast_amount_gbp"].sum().round(2).to_dict()
        variances = {version: self._round_money(value - fs_revenue) for version, value in scenario_totals.items()}
        max_abs = max(abs(v) for v in variances.values()) if variances else 0.00
        self._add_result(
            check_name="FORECAST_ACTUAL_PERIOD_REVENUE_TIE_OUT",
            check_category="Planning Integrity",
            expected_value=fs_revenue,
            actual_value={k: self._round_money(v) for k, v in scenario_totals.items()},
            variance=variances,
            passed=max_abs <= self.rules.tolerance,
            severity="HIGH",
            notes="Forecast actual-period revenue should equal consolidated financial statement actual revenue for every scenario.",
        )

    def check_variance_extract_shape_and_lineage(self) -> None:
        forecast = self._csv("planning", "forecast_lines.csv")
        variance = self._csv("planning", "variance_source_extract.csv")
        grain = ["forecast_version_code", "posting_period", "department_id", "account_code", "currency", "planning_driver"]
        duplicate_count = int(variance.duplicated(grain).sum())
        missing_lineage = int(
            variance["source_budget_line_id"].isna().sum() + variance["source_forecast_line_id"].isna().sum()
        )
        passed = len(variance) == len(forecast) and duplicate_count == 0 and missing_lineage == 0
        self._add_result(
            check_name="VARIANCE_SOURCE_SHAPE_AND_LINEAGE_CHECK",
            check_category="Variance Integrity",
            expected_value=f"{len(forecast):,} rows, 0 duplicate grain, 0 missing lineage values",
            actual_value=f"{len(variance):,} rows, {duplicate_count} duplicate grain, {missing_lineage} missing lineage values",
            variance=len(variance) - len(forecast),
            passed=passed,
            severity="HIGH",
            notes="Variance source extract should mirror forecast line count and retain source budget/forecast lineage.",
        )

    def check_variance_actual_revenue_tie_out(self) -> None:
        variance_df = self._csv("planning", "variance_source_extract.csv")
        fs_revenue = self._fs_actual_revenue_basis()
        mask = (
            (variance_df["period_status"].astype(str) == "Actual")
            & (variance_df["account_class"].astype(str).str.lower() == "revenue")
        )
        scenario_totals = variance_df.loc[mask].groupby("forecast_version_code")["actual_amount_gbp"].sum().round(2).to_dict()
        variances = {version: self._round_money(value - fs_revenue) for version, value in scenario_totals.items()}
        max_abs = max(abs(v) for v in variances.values()) if variances else 0.00
        self._add_result(
            check_name="VARIANCE_ACTUAL_REVENUE_TIE_OUT",
            check_category="Variance Integrity",
            expected_value=fs_revenue,
            actual_value={k: self._round_money(v) for k, v in scenario_totals.items()},
            variance=variances,
            passed=max_abs <= self.rules.tolerance,
            severity="HIGH",
            notes="Variance extract actual-period revenue should equal consolidated financial statement actual revenue for every scenario.",
        )

    def check_variance_future_actual_suppression(self) -> None:
        variance_df = self._csv("planning", "variance_source_extract.csv")
        future = variance_df[variance_df["period_status"].astype(str) == "Forecast"].copy()
        non_zero_actuals = int((pd.to_numeric(future["actual_amount_gbp"], errors="coerce").fillna(0).abs() > self.rules.tight_tolerance).sum())
        populated_actual_variances = int(
            future["actual_vs_budget_variance_gbp"].notna().sum()
            + future["actual_vs_forecast_variance_gbp"].notna().sum()
        )
        passed = non_zero_actuals == 0 and populated_actual_variances == 0
        self._add_result(
            check_name="VARIANCE_FUTURE_ACTUAL_SUPPRESSION_CHECK",
            check_category="Variance Integrity",
            expected_value="0 future actuals and 0 populated future actual variance fields",
            actual_value=f"{non_zero_actuals} non-zero future actuals; {populated_actual_variances} populated future actual variance fields",
            variance=non_zero_actuals + populated_actual_variances,
            passed=passed,
            severity="MEDIUM",
            notes="Future periods should not create false actual-vs-plan noise before actuals exist.",
        )

    def generate(self) -> pd.DataFrame:
        checks = [
            ("GL_JOURNAL_BALANCE_CHECK", self.check_gl_journal_balance),
            ("TRIAL_BALANCE_GBP_ZERO_CHECK", self.check_trial_balance_zero),
            ("BALANCE_SHEET_EQUATION_CHECK", self.check_balance_sheet_check),
            ("CONTROL_FINDINGS_RECONCILE_FAILED_CONTROLS", self.check_controls_to_findings),
            ("PAYROLL_TO_COMPENSATION_TIE_OUT", self.check_payroll_to_compensation),
            ("BUDGET_REVENUE_TARGET_CHECK", self.check_budget_revenue_targets),
            ("FORECAST_ACTUAL_PERIOD_REVENUE_TIE_OUT", self.check_forecast_actual_revenue_tie_out),
            ("VARIANCE_SOURCE_SHAPE_AND_LINEAGE_CHECK", self.check_variance_extract_shape_and_lineage),
            ("VARIANCE_ACTUAL_REVENUE_TIE_OUT", self.check_variance_actual_revenue_tie_out),
            ("VARIANCE_FUTURE_ACTUAL_SUPPRESSION_CHECK", self.check_variance_future_actual_suppression),
        ]
        for check_name, func in checks:
            self._run_safely(check_name, func)

        results = pd.DataFrame(self.results, columns=self.OUTPUT_COLUMNS)
        fail_count = int((results["status"] == "FAIL").sum())
        logger.info(
            "Source generation QA results generated: %s checks, %s failures.",
            f"{len(results):,}",
            f"{fail_count:,}",
        )
        return results

    def save(self, results: pd.DataFrame) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / self.rules.output_filename
        results.to_csv(output_path, index=False)
        logger.info("Source generation QA results saved to %s", output_path)


def main() -> None:
    try:
        qa = SourceGenerationQA()
        results = qa.generate()
        qa.save(results)
        if (results["status"] == "FAIL").any():
            sys.exit(1)
    except Exception as error:  # noqa: BLE001
        logger.critical("Source generation QA failed: %s", error, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
