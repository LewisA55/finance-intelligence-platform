import hashlib

import pandas as pd

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path
from scripts.utils.validation import raise_if_invalid, verify_dataset_integrity


logger = get_logger("DepartmentGenerator", "generation_execution.log")


class DepartmentGenerator:
    """Generates the conformed corporate department cost centre master."""

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.output_filename = "department_catalog.csv"

    @staticmethod
    def _generate_department_pk(department_id: str) -> str:
        """Computes a stable MD5 surrogate key hash for the department."""
        return hashlib.md5(department_id.strip().upper().encode("utf-8")).hexdigest()

    @staticmethod
    def _derive_department_code(department_id: str) -> str:
        """Creates a clean reporting code from the configured department ID."""
        return department_id.replace("DEPT_", "").strip().upper()

    @staticmethod
    def _derive_functional_group(department_id: str, raw_function: str) -> str:
        """Conforms broad configuration function values into reporting groups."""
        if raw_function == "Sales & Marketing":
            if "SALES" in department_id:
                return "Sales"
            if "MARKETING" in department_id:
                return "Marketing"

        return raw_function

    @staticmethod
    def _derive_cost_center_type(functional_group: str) -> str:
        """Classifies departments into direct or indirect cost centres."""
        direct_groups = {
            "R&D",
            "Sales",
            "Marketing",
            "Customer Success",
            "Product",
        }

        return "Direct" if functional_group in direct_groups else "Indirect"

    def generate(self) -> pd.DataFrame:
        logger.info("Generating conformed department catalogue.")

        raw_departments = self.config.departments

        if not raw_departments:
            raise ValueError("No departments found in business_rules.yaml.")

        records: list[dict] = []

        for department in raw_departments:
            department_id = department["department_id"]
            raw_function = department.get("function", "G&A")

            functional_group = self._derive_functional_group(
                department_id=department_id,
                raw_function=raw_function,
            )

            record = {
                "department_pk": self._generate_department_pk(department_id),
                "department_id": department_id,
                "department_code": self._derive_department_code(department_id),
                "department_name": department["department_name"],
                "functional_group": functional_group,
                "cost_center_type": self._derive_cost_center_type(functional_group),
                "active_flag": 1,
            }

            records.append(record)

        df = pd.DataFrame(records)

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
            unique_keys=["department_pk"],
        )

        for message in validation_logs:
            if is_valid:
                logger.info(message)
            else:
                logger.error(message)

        raise_if_invalid(is_valid, validation_logs)

        if df["department_id"].nunique() != len(df):
            raise ValueError("Department catalogue contains duplicate department_id values.")

        if df["department_code"].nunique() != len(df):
            raise ValueError("Department catalogue contains duplicate department_code values.")

        logger.info("Generated department catalogue with %s rows.", len(df))

        return df

    def save(self, df: pd.DataFrame) -> None:
        output_dir = get_raw_data_path("departments")
        output_path = output_dir / self.output_filename

        df.to_csv(output_path, index=False, encoding="utf-8")

        logger.info("Department catalogue written to %s", output_path)


def main() -> None:
    generator = DepartmentGenerator()
    df = generator.generate()
    generator.save(df)


if __name__ == "__main__":
    main()