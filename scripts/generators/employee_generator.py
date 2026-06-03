import hashlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.dates import generate_monthly_spine
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path
from scripts.utils.validation import raise_if_invalid, verify_dataset_integrity


logger = get_logger("EmployeeGenerator", "generation_execution.log")


class EmployeeGenerator:
    """Generates HRIS employee master and monthly headcount snapshot exports."""

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()

        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.total_employee_pool: int = 950

        self.employee_master_filename = "hr_employees.csv"
        self.headcount_snapshot_filename = "hr_headcount_snapshot.csv"

        self.missing_manager_rate: float = 0.05
        self.orphan_manager_rate: float = 0.02
        self.department_drift_rate: float = 0.02
        self.ghost_headcount_rate: float = 0.01
        self.termination_rate: float = 0.08

        self.employee_region_weights = {
            "UK": 0.35,
            "US": 0.35,
            "DE": 0.20,
            "SG": 0.10,
        }

        self.job_level_weights = {
            "analyst": 0.45,
            "manager": 0.25,
            "senior_manager": 0.15,
            "director": 0.10,
            "vp": 0.05,
        }

    @staticmethod
    def _generate_employee_pk(employee_id: str) -> str:
        return hashlib.md5(employee_id.strip().upper().encode("utf-8")).hexdigest()

    @staticmethod
    def _random_date_between(start_date: date, end_date: date) -> str:
        delta_days = (end_date - start_date).days

        if delta_days < 0:
            raise ValueError("start_date cannot be after end_date.")

        offset = np.random.randint(0, delta_days + 1)
        return (start_date + timedelta(days=int(offset))).isoformat()

    @staticmethod
    def _parse_date_or_none(value: str | None) -> date | None:
        if value is None or pd.isna(value) or value == "":
            return None

        return date.fromisoformat(str(value))

    @staticmethod
    def _append_issue(issues: list[str], issue: str) -> None:
        if issue not in issues:
            issues.append(issue)

    @staticmethod
    def _normalise_level_name(level_key: str) -> str:
        mapping = {
            "analyst": "Analyst",
            "manager": "Manager",
            "senior_manager": "Senior Manager",
            "director": "Director",
            "vp": "VP",
        }

        return mapping.get(level_key, level_key)

    def _load_department_catalogue(self) -> pd.DataFrame:
        path = get_raw_data_path("departments") / "department_catalog.csv"

        if not path.exists():
            raise FileNotFoundError(
                f"Department catalogue not found at {path}. "
                "Run DepartmentGenerator before EmployeeGenerator."
            )

        df = pd.read_csv(path, dtype="string")

        required_columns = [
            "department_pk",
            "department_id",
            "department_code",
            "department_name",
            "functional_group",
            "cost_center_type",
            "active_flag",
        ]

        is_valid, validation_logs = verify_dataset_integrity(
            df=df,
            required_columns=required_columns,
            unique_keys=["department_id"],
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

        return df

    def _load_region_catalogue(self) -> pd.DataFrame:
        path = get_raw_data_path("regions") / "region_catalog.csv"

        if not path.exists():
            raise FileNotFoundError(
                f"Region catalogue not found at {path}. "
                "Run RegionGenerator before EmployeeGenerator."
            )

        df = pd.read_csv(
            path,
            dtype={
                "region_id": "string",
                "currency_code": "string",
            },
        )

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
            unique_keys=["region_id"],
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

        return df

    def _get_department_choices(self) -> tuple[list[str], list[float]]:
        departments = self.config.departments

        if not departments:
            raise ValueError("No department rules found in business_rules.yaml.")

        department_ids = [department["department_id"] for department in departments]
        weights = [
            float(department.get("headcount_share", 0.0))
            for department in departments
        ]

        total_weight = round(sum(weights), 6)

        if total_weight != 1.0:
            raise ValueError(
                f"Department headcount_share values must sum to 1.0. "
                f"Actual total: {total_weight}"
            )

        return department_ids, weights

    def _get_region_choices(self) -> tuple[list[str], list[float]]:
        region_ids = list(self.employee_region_weights.keys())
        weights = list(self.employee_region_weights.values())

        total_weight = round(sum(weights), 6)

        if total_weight != 1.0:
            raise ValueError(
                f"Employee region weights must sum to 1.0. Actual total: {total_weight}"
            )

        return region_ids, weights

    def _get_job_level_choices(self) -> tuple[list[str], list[float]]:
        levels = list(self.job_level_weights.keys())
        weights = list(self.job_level_weights.values())

        total_weight = round(sum(weights), 6)

        if total_weight != 1.0:
            raise ValueError(
                f"Job level weights must sum to 1.0. Actual total: {total_weight}"
            )

        return levels, weights

    def _generate_hire_years(self) -> list[int]:
        """
        Creates hire years aligned to the target year-end headcount curve.

        Target active headcount story:
        2022: 450
        2023: 560
        2024: 700
        2025: 850
        2026: 950
        """
        hire_years = (
            [2021] * 450
            + [2023] * 110
            + [2024] * 140
            + [2025] * 150
            + [2026] * 100
        )

        if len(hire_years) != self.total_employee_pool:
            raise ValueError(
                f"Hire year allocation must equal {self.total_employee_pool}. "
                f"Actual total: {len(hire_years)}"
            )

        np.random.shuffle(hire_years)

        return hire_years

    def _generate_hire_date(self, hire_year: int) -> str:
        return self._random_date_between(
            start_date=date(hire_year, 1, 1),
            end_date=date(hire_year, 12, 31),
        )

    def _generate_termination_date(self, hire_date: str) -> str | None:
        if np.random.random() >= self.termination_rate:
            return None

        hire_dt = date.fromisoformat(hire_date)
        min_term_date = hire_dt + timedelta(days=180)

        if min_term_date > date(2026, 12, 31):
            return None

        return self._random_date_between(
            start_date=min_term_date,
            end_date=date(2026, 12, 31),
        )

    def _choose_salary(
        self,
        job_level_key: str,
        salary_multiplier: float,
    ) -> tuple[float, float]:
        level_rules = self.config.employee_levels.get(job_level_key)

        if not level_rules:
            raise KeyError(f"Employee level '{job_level_key}' missing from YAML.")

        base_min = float(level_rules["salary_min_gbp"])
        base_max = float(level_rules["salary_max_gbp"])

        base_salary_gbp = np.random.uniform(base_min, base_max) * salary_multiplier

        # Local salary is retained as the simulated payroll amount.
        # FX conversion is handled downstream using currency_code and exchange rates.
        base_salary_local = base_salary_gbp

        return round(base_salary_local, 2), round(base_salary_gbp, 2)

    @staticmethod
    def _derive_job_title(job_level: str, department_code: str) -> str:
        return f"{job_level} - {department_code}"

    def _assign_manager(
        self,
        employee_id: str,
        existing_employee_ids: list[str],
        job_level_key: str,
    ) -> tuple[str | None, list[str]]:
        issues: list[str] = []

        if job_level_key == "vp":
            return None, issues

        random_value = np.random.random()

        if random_value < self.missing_manager_rate:
            self._append_issue(issues, "missing_manager_id")
            return None, issues

        if random_value < self.missing_manager_rate + self.orphan_manager_rate:
            self._append_issue(issues, "orphan_manager")
            return "EMP-999999", issues

        valid_managers = [
            candidate_id
            for candidate_id in existing_employee_ids
            if candidate_id != employee_id
        ]

        if not valid_managers:
            self._append_issue(issues, "missing_manager_id")
            return None, issues

        return str(np.random.choice(valid_managers)), issues

    def _force_ghost_headcount_target(self, df: pd.DataFrame) -> pd.DataFrame:
        ghost_target = max(1, round(self.total_employee_pool * self.ghost_headcount_rate))
        ghost_actual = int(df["is_ghost_headcount"].sum())

        if ghost_actual >= ghost_target:
            return df

        required_extra_ghosts = ghost_target - ghost_actual

        terminated_candidates = df[
            (df["termination_date"].notna())
            & (df["is_ghost_headcount"] == 0)
        ]

        if len(terminated_candidates) < required_extra_ghosts:
            raise ValueError(
                f"Not enough terminated employees to inject ghost headcount defects. "
                f"Needed {required_extra_ghosts}, available {len(terminated_candidates)}."
            )

        selected_indices = terminated_candidates.sample(
            n=required_extra_ghosts,
            random_state=self.seed,
        ).index

        for idx in selected_indices:
            existing_issue = df.at[idx, "data_quality_issue"]
            issue_parts = [] if pd.isna(existing_issue) else str(existing_issue).split("|")

            self._append_issue(issue_parts, "ghost_headcount")

            df.at[idx, "employment_status"] = "Active"
            df.at[idx, "active_flag"] = 1
            df.at[idx, "is_ghost_headcount"] = 1
            df.at[idx, "data_quality_flag"] = 1
            df.at[idx, "data_quality_issue"] = "|".join(issue_parts)

        return df

    def _generate_employee_master(self) -> pd.DataFrame:
        department_catalogue = self._load_department_catalogue()
        region_catalogue = self._load_region_catalogue()

        department_lookup = (
            department_catalogue.set_index("department_id").to_dict(orient="index")
        )
        region_lookup = region_catalogue.set_index("region_id").to_dict(orient="index")

        department_ids, department_weights = self._get_department_choices()
        region_ids, region_weights = self._get_region_choices()
        job_level_keys, job_level_weights = self._get_job_level_choices()
        hire_years = self._generate_hire_years()

        records: list[dict] = []
        existing_employee_ids: list[str] = []

        for index in range(1, self.total_employee_pool + 1):
            employee_id = f"EMP-{index:05d}"
            hire_date = self._generate_hire_date(hire_years[index - 1])
            termination_date = self._generate_termination_date(hire_date)

            department_id = str(np.random.choice(department_ids, p=department_weights))
            region_id = str(np.random.choice(region_ids, p=region_weights))
            job_level_key = str(np.random.choice(job_level_keys, p=job_level_weights))

            department = department_lookup[department_id]
            region = region_lookup[region_id]

            department_code = str(department["department_code"])
            functional_group = str(department["functional_group"])
            salary_multiplier = float(region["salary_multiplier"])

            issues: list[str] = []

            if np.random.random() < self.department_drift_rate:
                department_id = "DEPT_UNKNOWN"
                department_code = "LEGACY_OPS"
                functional_group = "Unknown"
                self._append_issue(issues, "department_drift")

            manager_employee_id, manager_issues = self._assign_manager(
                employee_id=employee_id,
                existing_employee_ids=existing_employee_ids,
                job_level_key=job_level_key,
            )
            issues.extend(manager_issues)

            is_ghost_headcount = False
            employment_status = "Active"
            active_flag = 1

            if termination_date is not None:
                employment_status = "Terminated"
                active_flag = 0

            if termination_date is not None and np.random.random() < self.ghost_headcount_rate:
                employment_status = "Active"
                active_flag = 1
                is_ghost_headcount = True
                self._append_issue(issues, "ghost_headcount")

            job_level = self._normalise_level_name(job_level_key)
            base_salary_local, base_salary_gbp = self._choose_salary(
                job_level_key=job_level_key,
                salary_multiplier=salary_multiplier,
            )

            record = {
                "employee_pk": self._generate_employee_pk(employee_id),
                "employee_id": employee_id,
                "employee_name": f"Nexus Employee {index:05d}",
                "department_id": department_id,
                "department_code": department_code,
                "functional_group": functional_group,
                "region_id": region_id,
                "currency_code": region["currency_code"],
                "job_level": job_level,
                "job_title": self._derive_job_title(job_level, department_code),
                "manager_employee_id": manager_employee_id,
                "hire_date": hire_date,
                "termination_date": termination_date,
                "employment_status": employment_status,
                "base_salary_local": base_salary_local,
                "base_salary_gbp": base_salary_gbp,
                "salary_multiplier": salary_multiplier,
                "is_sales_employee": int(department_code == "SALES"),
                "is_ghost_headcount": int(is_ghost_headcount),
                "data_quality_flag": int(len(issues) > 0),
                "data_quality_issue": "|".join(issues) if issues else None,
                "active_flag": active_flag,
            }

            records.append(record)
            existing_employee_ids.append(employee_id)

        df = pd.DataFrame(records)
        df = self._force_ghost_headcount_target(df)

        return df

    def _generate_headcount_snapshot(self, employee_df: pd.DataFrame) -> pd.DataFrame:
        month_ends = generate_monthly_spine("2022-01-01", "2026-12-31")
        snapshot_records: list[dict] = []

        for month_end in month_ends:
            for _, employee in employee_df.iterrows():
                hire_date = date.fromisoformat(employee["hire_date"])
                termination_date = self._parse_date_or_none(employee["termination_date"])

                if hire_date > month_end:
                    continue

                if termination_date is not None and termination_date <= month_end:
                    if int(employee["active_flag"]) == 0:
                        continue

                snapshot_records.append(
                    {
                        "employee_id": employee["employee_id"],
                        "snapshot_month": month_end.isoformat(),
                        "department_id": employee["department_id"],
                        "department_code": employee["department_code"],
                        "functional_group": employee["functional_group"],
                        "region_id": employee["region_id"],
                        "currency_code": employee["currency_code"],
                        "job_level": employee["job_level"],
                        "employment_status": employee["employment_status"],
                        "monthly_salary_local": round(
                            float(employee["base_salary_local"]) / 12,
                            2,
                        ),
                        "monthly_salary_gbp": round(
                            float(employee["base_salary_gbp"]) / 12,
                            2,
                        ),
                        "fte_count": 1.0,
                        "is_active_flag": 1,
                        "is_ghost_headcount": int(employee["is_ghost_headcount"]),
                    }
                )

        return pd.DataFrame(snapshot_records)

    def _validate_employee_master(self, df: pd.DataFrame) -> None:
        required_columns = [
            "employee_pk",
            "employee_id",
            "employee_name",
            "department_id",
            "department_code",
            "functional_group",
            "region_id",
            "currency_code",
            "job_level",
            "job_title",
            "manager_employee_id",
            "hire_date",
            "termination_date",
            "employment_status",
            "base_salary_local",
            "base_salary_gbp",
            "salary_multiplier",
            "is_sales_employee",
            "is_ghost_headcount",
            "data_quality_flag",
            "data_quality_issue",
            "active_flag",
        ]

        is_valid, validation_logs = verify_dataset_integrity(
            df=df,
            required_columns=required_columns,
            unique_keys=["employee_pk"],
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

        if len(df) != self.total_employee_pool:
            raise ValueError(
                f"Employee master row count mismatch. "
                f"Expected {self.total_employee_pool}, got {len(df)}."
            )

        if df["employee_id"].nunique() != len(df):
            raise ValueError("Employee master contains duplicate employee_id values.")

        ghost_target = max(1, round(self.total_employee_pool * self.ghost_headcount_rate))
        ghost_actual = int(df["is_ghost_headcount"].sum())

        if ghost_actual != ghost_target:
            raise ValueError(
                f"Ghost headcount count mismatch. "
                f"Expected {ghost_target}, got {ghost_actual}."
            )

    def _validate_headcount_snapshot(self, df: pd.DataFrame) -> None:
        required_columns = [
            "employee_id",
            "snapshot_month",
            "department_id",
            "department_code",
            "functional_group",
            "region_id",
            "currency_code",
            "job_level",
            "employment_status",
            "monthly_salary_local",
            "monthly_salary_gbp",
            "fte_count",
            "is_active_flag",
            "is_ghost_headcount",
        ]

        is_valid, validation_logs = verify_dataset_integrity(
            df=df,
            required_columns=required_columns,
            unique_keys=["employee_id", "snapshot_month"],
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

    def generate(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        logger.info("Generating HRIS employee master and monthly headcount snapshot.")

        np.random.seed(self.seed)

        employee_df = self._generate_employee_master()
        snapshot_df = self._generate_headcount_snapshot(employee_df)

        self._validate_employee_master(employee_df)
        self._validate_headcount_snapshot(snapshot_df)

        logger.info("Generated HR employee master with %s rows.", len(employee_df))
        logger.info("Generated HR headcount snapshot with %s rows.", len(snapshot_df))

        return employee_df, snapshot_df

    def save(self, employee_df: pd.DataFrame, snapshot_df: pd.DataFrame) -> None:
        output_dir = get_raw_data_path("hris")

        employee_path = output_dir / self.employee_master_filename
        snapshot_path = output_dir / self.headcount_snapshot_filename

        employee_df.to_csv(employee_path, index=False, encoding="utf-8")
        snapshot_df.to_csv(snapshot_path, index=False, encoding="utf-8")

        logger.info("HR employee master written to %s", employee_path)
        logger.info("HR headcount snapshot written to %s", snapshot_path)


def main() -> None:
    generator = EmployeeGenerator()
    employee_df, snapshot_df = generator.generate()
    generator.save(employee_df, snapshot_df)


if __name__ == "__main__":
    main()