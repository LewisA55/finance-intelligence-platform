"""
financial_statement_extract_generator.py

Project Atlas / Nexus Technologies
Phase 3J.2 - Financial Statement Extract Generation

Purpose
-------
Generates:
- data/raw/accounting/financial_statement_extract.csv

This layer converts the locked Trial Balance extract into CFO-ready financial
statement structures for management reporting:
- Income Statement
- Balance Sheet

Design
------
trial_balance.csv is the baseline of truth.

The generator does not read raw GL journal lines directly. It treats the Trial
Balance as an ERP-produced accounting extract and applies statement mapping,
presentation sign logic, calculated subtotal rows, and a derived accumulated
earnings bridge so the Balance Sheet reconciles after separating P&L accounts
from balance sheet accounts.

Accounting convention
---------------------
The Trial Balance stores balances using universal algebraic signs:
- Assets / Expenses usually positive
- Liabilities / Equity / Revenue usually negative

Financial statements use executive presentation signs:
- Assets and Expenses remain positive
- Liabilities, Equity and Revenue are multiplied by -1

The derived accumulated earnings row is a presentation bridge only. It is not a
source GL journal and should not be treated as a posted accounting transaction.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("FinancialStatementExtractGenerator", "generation_execution.log")


@dataclass(frozen=True)
class FinancialStatementExtractRules:
    created_at: str = "2026-06-03"
    updated_at: str = "2026-06-03"
    balance_tolerance: float = 0.01


class FinancialStatementExtractGenerator:
    """
    Generate ERP-style financial statement extracts from the locked Trial Balance.

    Inputs
    ------
    data/raw/accounting/trial_balance.csv
    data/raw/accounting/chart_of_accounts.csv

    Output
    ------
    data/raw/accounting/financial_statement_extract.csv
    """

    output_filename = "financial_statement_extract.csv"

    SOURCE_SYSTEM = "atlas_erp_financial_statements"

    OUTPUT_COLUMNS = [
        "financial_statement_pk",
        "posting_period",
        "period_start_date",
        "period_end_date",
        "statement_type",
        "statement_type_sort",
        "statement_section",
        "statement_section_sort",
        "statement_line",
        "statement_line_sort",
        "account_code",
        "account_name",
        "account_class",
        "currency",
        "amount_local",
        "amount_gbp",
        "presentation_sign_multiplier",
        "is_calculated_line",
        "calculation_type",
        "source_system",
        "is_system_generated",
        "is_defect_flag",
        "defect_type",
        "created_at",
        "updated_at",
    ]

    REQUIRED_TB_COLUMNS = {
        "posting_period",
        "period_start_date",
        "period_end_date",
        "account_code",
        "account_name",
        "account_class",
        "financial_statement",
        "currency",
        "period_debits_local",
        "period_credits_local",
        "closing_balance_local",
        "period_debits_gbp",
        "period_credits_gbp",
        "closing_balance_gbp",
        "is_defect_flag",
        "defect_type",
    }

    REQUIRED_COA_COLUMNS = {
        "account_code",
        "account_name",
        "account_class",
        "account_type",
        "financial_statement",
        "report_group",
        "report_subgroup",
        "active_flag",
    }

    PRESENTATION_MULTIPLIER_BY_CLASS = {
        "Asset": 1,
        "Expense": 1,
        "Liability": -1,
        "Equity": -1,
        "Revenue": -1,
    }

    VALID_ACCOUNT_CLASSES = set(PRESENTATION_MULTIPLIER_BY_CLASS)

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.rules = FinancialStatementExtractRules()

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
    def _normalise_bool_int(value: object, default: int = 0) -> int:
        if pd.isna(value):
            return default

        if isinstance(value, bool):
            return int(value)

        if isinstance(value, (int, float)):
            return int(value == 1)

        value_str = str(value).strip().lower()

        if value_str in {"1", "true", "yes", "y"}:
            return 1

        if value_str in {"0", "false", "no", "n", ""}:
            return 0

        return default

    @staticmethod
    def _normalise_account_code(value: object) -> str:
        if pd.isna(value):
            return ""

        value_str = str(value).strip()

        if value_str.endswith(".0") and value_str.replace(".0", "").isdigit():
            return value_str.replace(".0", "")

        return value_str

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

    @staticmethod
    def _concat_defect_types(values: pd.Series) -> str:
        defect_types = sorted(
            {
                str(value).strip()
                for value in values.dropna().tolist()
                if str(value).strip() not in {"", "nan", "None"}
            }
        )
        return " | ".join(defect_types)

    # ------------------------------------------------------------------
    # Loading and preparation
    # ------------------------------------------------------------------

    def _load_csv(self, path: Path, dataset_name: str) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(
                f"{dataset_name} not found at {path}. Run upstream generators first."
            )

        return pd.read_csv(path)

    def _load_dependencies(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        accounting_dir = get_raw_data_path("accounting")

        tb_df = self._load_csv(
            accounting_dir / "trial_balance.csv",
            "trial_balance.csv",
        )

        coa_df = self._load_csv(
            accounting_dir / "chart_of_accounts.csv",
            "chart_of_accounts.csv",
        )

        tb_df = self._prepare_trial_balance(tb_df)
        coa_df = self._prepare_chart_of_accounts(coa_df)

        tb_df = tb_df.merge(
            coa_df[
                [
                    "account_code",
                    "account_type",
                    "report_group",
                    "report_subgroup",
                    "active_flag",
                ]
            ],
            on="account_code",
            how="left",
        )

        if tb_df["account_type"].isna().any():
            missing_accounts = sorted(
                tb_df.loc[tb_df["account_type"].isna(), "account_code"]
                .astype(str)
                .unique()
                .tolist()
            )
            raise ValueError(
                "Trial Balance contains accounts missing from active Chart of Accounts: "
                f"{missing_accounts}"
            )

        logger.info(
            "Loaded financial statement dependencies: %s trial balance rows, %s CoA rows.",
            f"{len(tb_df):,}",
            f"{len(coa_df):,}",
        )

        return tb_df, coa_df

    def _prepare_trial_balance(self, tb_df: pd.DataFrame) -> pd.DataFrame:
        df = tb_df.copy()

        if df.empty:
            raise ValueError("trial_balance.csv is empty.")

        self._require_columns(df, self.REQUIRED_TB_COLUMNS, "trial_balance.csv")

        df["posting_period"] = df["posting_period"].astype(str)
        df["period_start_date"] = pd.to_datetime(df["period_start_date"], errors="coerce")
        df["period_end_date"] = pd.to_datetime(df["period_end_date"], errors="coerce")
        df["account_code"] = df["account_code"].apply(self._normalise_account_code)
        df["account_name"] = df["account_name"].fillna("").astype(str)
        df["account_class"] = df["account_class"].fillna("").astype(str)
        df["financial_statement"] = df["financial_statement"].fillna("").astype(str)
        df["currency"] = df["currency"].astype(str).str.upper()
        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )
        df["defect_type"] = df["defect_type"].fillna("").astype(str)

        for column in [
            "period_debits_local",
            "period_credits_local",
            "closing_balance_local",
            "period_debits_gbp",
            "period_credits_gbp",
            "closing_balance_gbp",
        ]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.00)

        if df["period_start_date"].isna().any():
            bad_count = int(df["period_start_date"].isna().sum())
            raise ValueError(
                f"trial_balance.csv contains invalid period_start_date values: {bad_count:,}"
            )

        if df["period_end_date"].isna().any():
            bad_count = int(df["period_end_date"].isna().sum())
            raise ValueError(
                f"trial_balance.csv contains invalid period_end_date values: {bad_count:,}"
            )

        invalid_classes = set(df["account_class"].unique()).difference(
            self.VALID_ACCOUNT_CLASSES
        )
        if invalid_classes:
            raise ValueError(
                "trial_balance.csv contains invalid account_class values: "
                f"{sorted(invalid_classes)}"
            )

        duplicate_grain_count = int(
            df.duplicated(["posting_period", "account_code", "currency"]).sum()
        )
        if duplicate_grain_count:
            raise ValueError(
                "trial_balance.csv contains duplicate rows at posting_period + "
                f"account_code + currency grain: {duplicate_grain_count:,}"
            )

        return df

    def _prepare_chart_of_accounts(self, coa_df: pd.DataFrame) -> pd.DataFrame:
        df = coa_df.copy()

        if df.empty:
            raise ValueError("chart_of_accounts.csv is empty.")

        self._require_columns(df, self.REQUIRED_COA_COLUMNS, "chart_of_accounts.csv")

        df["account_code"] = df["account_code"].apply(self._normalise_account_code)
        df["account_name"] = df["account_name"].fillna("").astype(str)
        df["account_class"] = df["account_class"].fillna("").astype(str)
        df["account_type"] = df["account_type"].fillna("").astype(str)
        df["financial_statement"] = df["financial_statement"].fillna("").astype(str)
        df["report_group"] = df["report_group"].fillna("").astype(str)
        df["report_subgroup"] = df["report_subgroup"].fillna("").astype(str)
        df["active_flag"] = df["active_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=1)
        )

        duplicate_account_count = int(df["account_code"].duplicated().sum())
        if duplicate_account_count:
            raise ValueError(
                "chart_of_accounts.csv contains duplicate account_code values: "
                f"{duplicate_account_count:,}"
            )

        active_df = df[df["active_flag"] == 1].copy()
        if active_df.empty:
            raise ValueError("chart_of_accounts.csv contains no active accounts.")

        return active_df

    # ------------------------------------------------------------------
    # Statement mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_statement_type_sort(statement_type: str) -> int:
        return {"Income Statement": 1, "Balance Sheet": 2}.get(statement_type, 99)

    @staticmethod
    def _get_income_section_sort(account_type: str, report_group: str) -> int:
        account_type = str(account_type)
        report_group = str(report_group)

        if account_type == "Operating Revenue" or report_group == "Revenue":
            return 1000
        if account_type == "Cost of Sales" or report_group == "Cost of Sales":
            return 2000
        if account_type == "Operating Expense" or report_group == "Operating Expenses":
            return 4000
        if account_type == "Other Expense" or report_group == "Other Income / Expense":
            return 7000
        return 8999

    @staticmethod
    def _get_income_section(account_type: str, report_group: str) -> str:
        section_sort = FinancialStatementExtractGenerator._get_income_section_sort(
            account_type,
            report_group,
        )
        return {
            1000: "Revenue",
            2000: "Cost of Goods Sold",
            4000: "Operating Expenses",
            7000: "Other Income / Expense",
        }.get(section_sort, "Other Income Statement")

    @staticmethod
    def _get_balance_section_sort(account_class: str, report_group: str) -> int:
        account_class = str(account_class)
        report_group = str(report_group)

        if account_class == "Asset":
            if report_group == "Cash and Cash Equivalents":
                return 1000
            if report_group == "Accounts Receivable":
                return 1100
            if report_group == "Prepayments":
                return 1200
            if report_group == "Fixed Assets":
                return 1500
            return 1800

        if account_class == "Liability":
            if report_group == "Accounts Payable":
                return 2000
            if report_group == "Deferred Revenue":
                return 2100
            if report_group == "Customer Credits":
                return 2200
            if report_group == "Accrued Expenses":
                return 2300
            if report_group == "Tax Payable":
                return 2400
            return 2800

        if account_class == "Equity":
            return 3000

        return 8999

    @staticmethod
    def _get_balance_section(account_class: str, report_group: str) -> str:
        section_sort = FinancialStatementExtractGenerator._get_balance_section_sort(
            account_class,
            report_group,
        )

        if 1000 <= section_sort < 2000:
            return "Assets"
        if 2000 <= section_sort < 3000:
            return "Liabilities"
        if 3000 <= section_sort < 4000:
            return "Equity"
        return "Other Balance Sheet"

    @staticmethod
    def _get_account_line_sort(account_code: str, section_sort: int) -> int:
        try:
            code_int = int(str(account_code))
        except ValueError:
            code_int = 999
        return int(section_sort + min(code_int % 1000, 999))

    def _base_output_record(
        self,
        *,
        posting_period: str,
        period_start_date: pd.Timestamp,
        period_end_date: pd.Timestamp,
        statement_type: str,
        statement_section: str,
        statement_section_sort: int,
        statement_line: str,
        statement_line_sort: int,
        account_code: str,
        account_name: str,
        account_class: str,
        currency: str,
        amount_local: float,
        amount_gbp: float,
        presentation_sign_multiplier: int,
        is_calculated_line: int,
        calculation_type: str,
        is_defect_flag: int,
        defect_type: str,
    ) -> dict:
        key = "|".join(
            [
                posting_period,
                statement_type,
                statement_section,
                statement_line,
                account_code,
                currency,
                calculation_type,
            ]
        )

        return {
            "financial_statement_pk": self._generate_pk(key),
            "posting_period": posting_period,
            "period_start_date": pd.Timestamp(period_start_date).date().isoformat(),
            "period_end_date": pd.Timestamp(period_end_date).date().isoformat(),
            "statement_type": statement_type,
            "statement_type_sort": self._get_statement_type_sort(statement_type),
            "statement_section": statement_section,
            "statement_section_sort": statement_section_sort,
            "statement_line": statement_line,
            "statement_line_sort": statement_line_sort,
            "account_code": account_code,
            "account_name": account_name,
            "account_class": account_class,
            "currency": currency,
            "amount_local": self._round_money(amount_local),
            "amount_gbp": self._round_money(amount_gbp),
            "presentation_sign_multiplier": int(presentation_sign_multiplier),
            "is_calculated_line": int(is_calculated_line),
            "calculation_type": calculation_type,
            "source_system": self.SOURCE_SYSTEM,
            "is_system_generated": 1,
            "is_defect_flag": int(is_defect_flag),
            "defect_type": defect_type if defect_type else None,
            "created_at": self.rules.created_at,
            "updated_at": self.rules.updated_at,
        }

    # ------------------------------------------------------------------
    # Row builders
    # ------------------------------------------------------------------

    def _build_income_statement_account_rows(self, tb_df: pd.DataFrame) -> pd.DataFrame:
        df = tb_df[tb_df["account_class"].isin(["Revenue", "Expense"])].copy()

        records = []

        for _, row in df.iterrows():
            multiplier = self.PRESENTATION_MULTIPLIER_BY_CLASS[row["account_class"]]
            period_net_local = float(row["period_debits_local"]) - float(row["period_credits_local"])
            period_net_gbp = float(row["period_debits_gbp"]) - float(row["period_credits_gbp"])
            section_sort = self._get_income_section_sort(
                row["account_type"],
                row["report_group"],
            )
            section = self._get_income_section(row["account_type"], row["report_group"])
            line_sort = self._get_account_line_sort(row["account_code"], section_sort)

            records.append(
                self._base_output_record(
                    posting_period=row["posting_period"],
                    period_start_date=row["period_start_date"],
                    period_end_date=row["period_end_date"],
                    statement_type="Income Statement",
                    statement_section=section,
                    statement_section_sort=section_sort,
                    statement_line=row["account_name"],
                    statement_line_sort=line_sort,
                    account_code=row["account_code"],
                    account_name=row["account_name"],
                    account_class=row["account_class"],
                    currency=row["currency"],
                    amount_local=period_net_local * multiplier,
                    amount_gbp=period_net_gbp * multiplier,
                    presentation_sign_multiplier=multiplier,
                    is_calculated_line=0,
                    calculation_type="ACCOUNT_ACTIVITY",
                    is_defect_flag=row["is_defect_flag"],
                    defect_type=row["defect_type"],
                )
            )

        output = pd.DataFrame(records)
        logger.info("Income Statement account rows generated: %s", f"{len(output):,}")
        return output

    def _build_balance_sheet_account_rows(self, tb_df: pd.DataFrame) -> pd.DataFrame:
        df = tb_df[tb_df["account_class"].isin(["Asset", "Liability", "Equity"])].copy()

        records = []

        for _, row in df.iterrows():
            multiplier = self.PRESENTATION_MULTIPLIER_BY_CLASS[row["account_class"]]
            section_sort = self._get_balance_section_sort(
                row["account_class"],
                row["report_group"],
            )
            section = self._get_balance_section(row["account_class"], row["report_group"])
            line_sort = self._get_account_line_sort(row["account_code"], section_sort)

            records.append(
                self._base_output_record(
                    posting_period=row["posting_period"],
                    period_start_date=row["period_start_date"],
                    period_end_date=row["period_end_date"],
                    statement_type="Balance Sheet",
                    statement_section=section,
                    statement_section_sort=section_sort,
                    statement_line=row["account_name"],
                    statement_line_sort=line_sort,
                    account_code=row["account_code"],
                    account_name=row["account_name"],
                    account_class=row["account_class"],
                    currency=row["currency"],
                    amount_local=float(row["closing_balance_local"]) * multiplier,
                    amount_gbp=float(row["closing_balance_gbp"]) * multiplier,
                    presentation_sign_multiplier=multiplier,
                    is_calculated_line=0,
                    calculation_type="ACCOUNT_CLOSING_BALANCE",
                    is_defect_flag=row["is_defect_flag"],
                    defect_type=row["defect_type"],
                )
            )

        output = pd.DataFrame(records)
        logger.info("Balance Sheet account rows generated: %s", f"{len(output):,}")
        return output

    def _period_currency_metadata(self, tb_df: pd.DataFrame) -> pd.DataFrame:
        return (
            tb_df[
                [
                    "posting_period",
                    "period_start_date",
                    "period_end_date",
                    "currency",
                ]
            ]
            .drop_duplicates()
            .sort_values(["currency", "posting_period"])
            .reset_index(drop=True)
        )

    def _build_income_statement_calculated_rows(
        self,
        income_account_rows: pd.DataFrame,
        tb_df: pd.DataFrame,
    ) -> pd.DataFrame:
        metadata = self._period_currency_metadata(tb_df)

        group_cols = ["posting_period", "currency"]
        line_amounts = (
            income_account_rows.groupby(group_cols + ["statement_section"], as_index=False)[
                ["amount_local", "amount_gbp"]
            ]
            .sum()
            .rename(
                columns={
                    "amount_local": "section_amount_local",
                    "amount_gbp": "section_amount_gbp",
                }
            )
        )

        def get_section(section_name: str) -> pd.DataFrame:
            section = line_amounts[line_amounts["statement_section"] == section_name][
                group_cols + ["section_amount_local", "section_amount_gbp"]
            ].copy()
            return section.rename(
                columns={
                    "section_amount_local": f"{section_name}_local",
                    "section_amount_gbp": f"{section_name}_gbp",
                }
            )

        calc = metadata.copy()

        for section_name in [
            "Revenue",
            "Cost of Goods Sold",
            "Operating Expenses",
            "Other Income / Expense",
        ]:
            calc = calc.merge(get_section(section_name), on=group_cols, how="left")

        for column in calc.columns:
            if column.endswith("_local") or column.endswith("_gbp"):
                calc[column] = calc[column].fillna(0.00)

        calc["gross_profit_local"] = calc["Revenue_local"] - calc["Cost of Goods Sold_local"]
        calc["gross_profit_gbp"] = calc["Revenue_gbp"] - calc["Cost of Goods Sold_gbp"]
        calc["operating_profit_local"] = calc["gross_profit_local"] - calc["Operating Expenses_local"]
        calc["operating_profit_gbp"] = calc["gross_profit_gbp"] - calc["Operating Expenses_gbp"]
        calc["net_income_local"] = calc["operating_profit_local"] - calc["Other Income / Expense_local"]
        calc["net_income_gbp"] = calc["operating_profit_gbp"] - calc["Other Income / Expense_gbp"]

        records = []
        calculated_specs = [
            (
                "Gross Profit",
                3000,
                "FS_GROSS_PROFIT",
                "GROSS_PROFIT",
                "gross_profit_local",
                "gross_profit_gbp",
            ),
            (
                "Operating Profit",
                5000,
                "FS_OPERATING_PROFIT",
                "OPERATING_PROFIT",
                "operating_profit_local",
                "operating_profit_gbp",
            ),
            (
                "Net Income",
                9000,
                "FS_NET_INCOME",
                "NET_INCOME",
                "net_income_local",
                "net_income_gbp",
            ),
        ]

        for _, row in calc.iterrows():
            for line_name, line_sort, code, calc_type, local_col, gbp_col in calculated_specs:
                records.append(
                    self._base_output_record(
                        posting_period=row["posting_period"],
                        period_start_date=row["period_start_date"],
                        period_end_date=row["period_end_date"],
                        statement_type="Income Statement",
                        statement_section="Calculated Performance Measures",
                        statement_section_sort=line_sort,
                        statement_line=line_name,
                        statement_line_sort=line_sort,
                        account_code=code,
                        account_name=line_name,
                        account_class="Calculated",
                        currency=row["currency"],
                        amount_local=row[local_col],
                        amount_gbp=row[gbp_col],
                        presentation_sign_multiplier=1,
                        is_calculated_line=1,
                        calculation_type=calc_type,
                        is_defect_flag=0,
                        defect_type="",
                    )
                )

        output = pd.DataFrame(records)
        logger.info("Income Statement calculated rows generated: %s", f"{len(output):,}")
        return output

    def _build_accumulated_earnings_rows(
        self,
        income_account_rows: pd.DataFrame,
        tb_df: pd.DataFrame,
    ) -> pd.DataFrame:
        metadata = self._period_currency_metadata(tb_df)

        income_source = income_account_rows.copy()
        income_source["signed_net_income_local"] = income_source["amount_local"]
        income_source["signed_net_income_gbp"] = income_source["amount_gbp"]
        expense_mask = income_source["account_class"] == "Expense"
        income_source.loc[expense_mask, "signed_net_income_local"] *= -1
        income_source.loc[expense_mask, "signed_net_income_gbp"] *= -1

        income_by_period = (
            income_source.groupby(["posting_period", "currency"], as_index=False)[
                ["signed_net_income_local", "signed_net_income_gbp"]
            ]
            .sum()
            .rename(
                columns={
                    "signed_net_income_local": "net_income_local",
                    "signed_net_income_gbp": "net_income_gbp",
                }
            )
        )

        earnings = metadata.merge(
            income_by_period,
            on=["posting_period", "currency"],
            how="left",
        )
        earnings["net_income_local"] = earnings["net_income_local"].fillna(0.00)
        earnings["net_income_gbp"] = earnings["net_income_gbp"].fillna(0.00)
        earnings = earnings.sort_values(["currency", "posting_period"]).copy()
        earnings["accumulated_earnings_local"] = earnings.groupby("currency")[
            "net_income_local"
        ].cumsum()
        earnings["accumulated_earnings_gbp"] = earnings.groupby("currency")[
            "net_income_gbp"
        ].cumsum()

        defect_source = tb_df[tb_df["account_class"].isin(["Revenue", "Expense"])].copy()
        defect_rollup = (
            defect_source.groupby(["posting_period", "currency"], as_index=False)
            .agg(
                is_defect_flag=("is_defect_flag", "max"),
                defect_type=("defect_type", self._concat_defect_types),
            )
        )

        earnings = earnings.merge(
            defect_rollup,
            on=["posting_period", "currency"],
            how="left",
        )
        earnings["is_defect_flag"] = earnings["is_defect_flag"].fillna(0).astype(int)
        earnings["defect_type"] = earnings["defect_type"].fillna("").astype(str)

        records = []
        for _, row in earnings.iterrows():
            records.append(
                self._base_output_record(
                    posting_period=row["posting_period"],
                    period_start_date=row["period_start_date"],
                    period_end_date=row["period_end_date"],
                    statement_type="Balance Sheet",
                    statement_section="Equity",
                    statement_section_sort=3100,
                    statement_line="Accumulated Earnings",
                    statement_line_sort=3100,
                    account_code="FS_ACCUMULATED_EARNINGS",
                    account_name="Accumulated Earnings",
                    account_class="Equity",
                    currency=row["currency"],
                    amount_local=row["accumulated_earnings_local"],
                    amount_gbp=row["accumulated_earnings_gbp"],
                    presentation_sign_multiplier=1,
                    is_calculated_line=1,
                    calculation_type="ACCUMULATED_EARNINGS_BRIDGE",
                    is_defect_flag=row["is_defect_flag"],
                    defect_type=row["defect_type"],
                )
            )

        output = pd.DataFrame(records)
        logger.info("Accumulated Earnings bridge rows generated: %s", f"{len(output):,}")
        return output

    def _build_balance_sheet_calculated_rows(
        self,
        balance_account_rows: pd.DataFrame,
        accumulated_earnings_rows: pd.DataFrame,
        tb_df: pd.DataFrame,
    ) -> pd.DataFrame:
        base_bs = pd.concat(
            [balance_account_rows, accumulated_earnings_rows],
            ignore_index=True,
        )

        metadata = self._period_currency_metadata(tb_df)

        group_cols = ["posting_period", "currency"]
        section_totals = (
            base_bs.groupby(group_cols + ["statement_section"], as_index=False)[
                ["amount_local", "amount_gbp"]
            ]
            .sum()
            .rename(
                columns={
                    "amount_local": "section_amount_local",
                    "amount_gbp": "section_amount_gbp",
                }
            )
        )

        def get_section(section_name: str) -> pd.DataFrame:
            section = section_totals[section_totals["statement_section"] == section_name][
                group_cols + ["section_amount_local", "section_amount_gbp"]
            ].copy()
            return section.rename(
                columns={
                    "section_amount_local": f"{section_name}_local",
                    "section_amount_gbp": f"{section_name}_gbp",
                }
            )

        calc = metadata.copy()
        for section_name in ["Assets", "Liabilities", "Equity"]:
            calc = calc.merge(get_section(section_name), on=group_cols, how="left")

        for column in calc.columns:
            if column.endswith("_local") or column.endswith("_gbp"):
                calc[column] = calc[column].fillna(0.00)

        calc["liabilities_and_equity_local"] = calc["Liabilities_local"] + calc["Equity_local"]
        calc["liabilities_and_equity_gbp"] = calc["Liabilities_gbp"] + calc["Equity_gbp"]
        calc["balance_check_local"] = calc["Assets_local"] - calc["liabilities_and_equity_local"]
        calc["balance_check_gbp"] = calc["Assets_gbp"] - calc["liabilities_and_equity_gbp"]

        calculated_specs = [
            (
                "Total Assets",
                1900,
                "Assets",
                1900,
                "FS_TOTAL_ASSETS",
                "TOTAL_ASSETS",
                "Assets_local",
                "Assets_gbp",
            ),
            (
                "Total Liabilities",
                2900,
                "Liabilities",
                2900,
                "FS_TOTAL_LIABILITIES",
                "TOTAL_LIABILITIES",
                "Liabilities_local",
                "Liabilities_gbp",
            ),
            (
                "Total Equity",
                3900,
                "Equity",
                3900,
                "FS_TOTAL_EQUITY",
                "TOTAL_EQUITY",
                "Equity_local",
                "Equity_gbp",
            ),
            (
                "Total Liabilities and Equity",
                9990,
                "Balance Sheet Check",
                9990,
                "FS_TOTAL_LIABILITIES_AND_EQUITY",
                "TOTAL_LIABILITIES_AND_EQUITY",
                "liabilities_and_equity_local",
                "liabilities_and_equity_gbp",
            ),
            (
                "Balance Sheet Check",
                9999,
                "Balance Sheet Check",
                9999,
                "FS_BALANCE_SHEET_CHECK",
                "BALANCE_SHEET_CHECK",
                "balance_check_local",
                "balance_check_gbp",
            ),
        ]

        records = []
        for _, row in calc.iterrows():
            for (
                line_name,
                line_sort,
                section,
                section_sort,
                code,
                calc_type,
                local_col,
                gbp_col,
            ) in calculated_specs:
                records.append(
                    self._base_output_record(
                        posting_period=row["posting_period"],
                        period_start_date=row["period_start_date"],
                        period_end_date=row["period_end_date"],
                        statement_type="Balance Sheet",
                        statement_section=section,
                        statement_section_sort=section_sort,
                        statement_line=line_name,
                        statement_line_sort=line_sort,
                        account_code=code,
                        account_name=line_name,
                        account_class="Calculated",
                        currency=row["currency"],
                        amount_local=row[local_col],
                        amount_gbp=row[gbp_col],
                        presentation_sign_multiplier=1,
                        is_calculated_line=1,
                        calculation_type=calc_type,
                        is_defect_flag=0,
                        defect_type="",
                    )
                )

        output = pd.DataFrame(records)
        logger.info("Balance Sheet calculated rows generated: %s", f"{len(output):,}")
        return output

    # ------------------------------------------------------------------
    # Validation and save
    # ------------------------------------------------------------------

    def _validate_output(
        self,
        fs_df: pd.DataFrame,
        tb_df: pd.DataFrame,
    ) -> None:
        if fs_df.empty:
            raise ValueError("financial_statement_extract output is empty.")

        duplicate_grain_cols = [
            "posting_period",
            "statement_type",
            "statement_section",
            "statement_line",
            "account_code",
            "currency",
        ]
        duplicate_grain_count = int(fs_df.duplicated(duplicate_grain_cols).sum())
        if duplicate_grain_count:
            raise ValueError(
                "financial_statement_extract contains duplicate output grain rows: "
                f"{duplicate_grain_count:,}"
            )

        duplicate_pk_count = int(fs_df["financial_statement_pk"].duplicated().sum())
        if duplicate_pk_count:
            raise ValueError(
                "financial_statement_extract contains duplicate financial_statement_pk values: "
                f"{duplicate_pk_count:,}"
            )

        # Account-level IS should equal period activity with presentation signs.
        is_account_rows = fs_df[
            (fs_df["statement_type"] == "Income Statement")
            & (fs_df["is_calculated_line"] == 0)
        ].copy()
        tb_is = tb_df[tb_df["account_class"].isin(["Revenue", "Expense"])].copy()
        tb_is["expected_amount_local"] = (
            tb_is["period_debits_local"] - tb_is["period_credits_local"]
        ) * tb_is["account_class"].map(self.PRESENTATION_MULTIPLIER_BY_CLASS)
        tb_is["expected_amount_gbp"] = (
            tb_is["period_debits_gbp"] - tb_is["period_credits_gbp"]
        ) * tb_is["account_class"].map(self.PRESENTATION_MULTIPLIER_BY_CLASS)

        is_compare = is_account_rows.merge(
            tb_is[
                [
                    "posting_period",
                    "account_code",
                    "currency",
                    "expected_amount_local",
                    "expected_amount_gbp",
                ]
            ],
            on=["posting_period", "account_code", "currency"],
            how="left",
        )
        is_compare["local_variance"] = (
            is_compare["amount_local"] - is_compare["expected_amount_local"]
        ).round(2)
        is_compare["gbp_variance"] = (
            is_compare["amount_gbp"] - is_compare["expected_amount_gbp"]
        ).round(2)

        if (
            is_compare["local_variance"].abs() > self.rules.balance_tolerance
        ).any() or (
            is_compare["gbp_variance"].abs() > self.rules.balance_tolerance
        ).any():
            raise ValueError("Income Statement account rows do not tie to TB activity.")

        # Account-level BS should equal closing balances with presentation signs.
        bs_account_rows = fs_df[
            (fs_df["statement_type"] == "Balance Sheet")
            & (fs_df["is_calculated_line"] == 0)
        ].copy()
        tb_bs = tb_df[tb_df["account_class"].isin(["Asset", "Liability", "Equity"])].copy()
        tb_bs["expected_amount_local"] = tb_bs["closing_balance_local"] * tb_bs[
            "account_class"
        ].map(self.PRESENTATION_MULTIPLIER_BY_CLASS)
        tb_bs["expected_amount_gbp"] = tb_bs["closing_balance_gbp"] * tb_bs[
            "account_class"
        ].map(self.PRESENTATION_MULTIPLIER_BY_CLASS)

        bs_compare = bs_account_rows.merge(
            tb_bs[
                [
                    "posting_period",
                    "account_code",
                    "currency",
                    "expected_amount_local",
                    "expected_amount_gbp",
                ]
            ],
            on=["posting_period", "account_code", "currency"],
            how="left",
        )
        bs_compare["local_variance"] = (
            bs_compare["amount_local"] - bs_compare["expected_amount_local"]
        ).round(2)
        bs_compare["gbp_variance"] = (
            bs_compare["amount_gbp"] - bs_compare["expected_amount_gbp"]
        ).round(2)

        if (
            bs_compare["local_variance"].abs() > self.rules.balance_tolerance
        ).any() or (
            bs_compare["gbp_variance"].abs() > self.rules.balance_tolerance
        ).any():
            raise ValueError("Balance Sheet account rows do not tie to TB closing balances.")

        net_income_rows = fs_df[
            (fs_df["statement_type"] == "Income Statement")
            & (fs_df["calculation_type"] == "NET_INCOME")
        ][["posting_period", "currency", "amount_local", "amount_gbp"]].copy()

        income_account_source = is_account_rows.copy()
        income_account_source["expected_net_income_local"] = income_account_source["amount_local"]
        income_account_source["expected_net_income_gbp"] = income_account_source["amount_gbp"]
        expense_mask = income_account_source["account_class"] == "Expense"
        income_account_source.loc[expense_mask, "expected_net_income_local"] *= -1
        income_account_source.loc[expense_mask, "expected_net_income_gbp"] *= -1

        income_account_totals = (
            income_account_source.groupby(["posting_period", "currency"], as_index=False)[
                ["expected_net_income_local", "expected_net_income_gbp"]
            ]
            .sum()
        )
        net_income_compare = net_income_rows.merge(
            income_account_totals,
            on=["posting_period", "currency"],
            how="left",
        )
        net_income_compare["local_variance"] = (
            net_income_compare["amount_local"]
            - net_income_compare["expected_net_income_local"]
        ).round(2)
        net_income_compare["gbp_variance"] = (
            net_income_compare["amount_gbp"]
            - net_income_compare["expected_net_income_gbp"]
        ).round(2)

        if (
            net_income_compare["local_variance"].abs() > self.rules.balance_tolerance
        ).any() or (
            net_income_compare["gbp_variance"].abs() > self.rules.balance_tolerance
        ).any():
            raise ValueError("Net Income calculated rows do not tie to account-level Income Statement.")

        bs_check_rows = fs_df[
            (fs_df["statement_type"] == "Balance Sheet")
            & (fs_df["calculation_type"] == "BALANCE_SHEET_CHECK")
        ].copy()
        max_local_bs_imbalance = float(bs_check_rows["amount_local"].abs().max())
        max_gbp_bs_imbalance = float(bs_check_rows["amount_gbp"].abs().max())

        if max_local_bs_imbalance > self.rules.balance_tolerance:
            raise ValueError(
                "Balance Sheet local equation failed. Max imbalance: "
                f"{max_local_bs_imbalance:,.2f}"
            )

        if max_gbp_bs_imbalance > self.rules.balance_tolerance:
            raise ValueError(
                "Balance Sheet GBP equation failed. Max imbalance: "
                f"{max_gbp_bs_imbalance:,.2f}"
            )

        logger.info("Financial Statement Extract validation passed.")

    def _log_review_summary(self, fs_df: pd.DataFrame) -> None:
        logger.info("----- Financial Statement Extract Review -----")
        logger.info("Financial Statement rows: %s", f"{len(fs_df):,}")
        logger.info(
            "Posting period range: %s to %s",
            fs_df["posting_period"].min(),
            fs_df["posting_period"].max(),
        )
        logger.info("Statement type counts:\n%s", fs_df["statement_type"].value_counts().to_string())
        logger.info("Currency counts:\n%s", fs_df["currency"].value_counts().to_string())
        logger.info(
            "Calculated line counts:\n%s",
            fs_df["calculation_type"].value_counts().to_string(),
        )

        balance_checks = fs_df[
            (fs_df["statement_type"] == "Balance Sheet")
            & (fs_df["calculation_type"] == "BALANCE_SHEET_CHECK")
        ]
        logger.info(
            "Largest Balance Sheet check amount GBP: %.2f",
            float(balance_checks["amount_gbp"].abs().max()),
        )
        logger.info(
            "Rows carrying defect lineage: %s",
            f"{int((fs_df['is_defect_flag'] == 1).sum()):,}",
        )
        logger.info("----------------------------------------------")

    def generate(self) -> pd.DataFrame:
        logger.info("Generating Phase 3J.2 Financial Statement extract.")

        tb_df, _ = self._load_dependencies()

        income_account_rows = self._build_income_statement_account_rows(tb_df)
        balance_account_rows = self._build_balance_sheet_account_rows(tb_df)
        income_calculated_rows = self._build_income_statement_calculated_rows(
            income_account_rows=income_account_rows,
            tb_df=tb_df,
        )
        accumulated_earnings_rows = self._build_accumulated_earnings_rows(
            income_account_rows=income_account_rows,
            tb_df=tb_df,
        )
        balance_calculated_rows = self._build_balance_sheet_calculated_rows(
            balance_account_rows=balance_account_rows,
            accumulated_earnings_rows=accumulated_earnings_rows,
            tb_df=tb_df,
        )

        fs_df = pd.concat(
            [
                income_account_rows,
                income_calculated_rows,
                balance_account_rows,
                accumulated_earnings_rows,
                balance_calculated_rows,
            ],
            ignore_index=True,
        )

        fs_df = fs_df[self.OUTPUT_COLUMNS].copy()
        fs_df = fs_df.sort_values(
            [
                "posting_period",
                "currency",
                "statement_type_sort",
                "statement_section_sort",
                "statement_line_sort",
                "account_code",
            ]
        ).reset_index(drop=True)

        self._validate_output(fs_df=fs_df, tb_df=tb_df)
        self._log_review_summary(fs_df)

        return fs_df

    def save(self, fs_df: pd.DataFrame) -> None:
        output_path = get_raw_data_path("accounting") / self.output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fs_df.to_csv(output_path, index=False)
        logger.info("Financial Statement extract saved to %s", output_path)


if __name__ == "__main__":
    generator = FinancialStatementExtractGenerator()
    output_df = generator.generate()
    generator.save(output_df)
