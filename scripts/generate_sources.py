import sys

from scripts.generators.department_generator import DepartmentGenerator
from scripts.generators.fx_generator import FXRateGenerator
from scripts.generators.region_generator import RegionGenerator
from scripts.generators.product_generator import ProductGenerator
from scripts.generators.customer_generator import CustomerGenerator
from scripts.utils.logger import get_logger


logger = get_logger("PipelineOrchestrator", "generation_execution.log")


def main() -> None:
    logger.info("=" * 72)
    logger.info("STARTING PROJECT ATLAS SYNTHETIC SOURCE GENERATION")
    logger.info("=" * 72)

    try:
        logger.info("Phase 3A.1: Generating FX rates")
        fx_generator = FXRateGenerator()
        fx_rates = fx_generator.generate()
        fx_generator.save(fx_rates)
        logger.info("FX generation complete: %s rows", len(fx_rates))

        logger.info("Phase 3A.2: Generating product catalogue")
        product_generator = ProductGenerator()
        products = product_generator.generate()
        product_generator.save(products)
        logger.info("Product generation complete: %s rows", len(products))

        logger.info("Phase 3A.3: Generating department catalogue")
        department_generator = DepartmentGenerator()
        departments = department_generator.generate()
        department_generator.save(departments)
        logger.info("Department generation complete: %s rows", len(departments))

        logger.info("Phase 3A.2: Generating region catalogue")
        region_generator = RegionGenerator()
        regions = region_generator.generate()
        region_generator.save(regions)
        logger.info("Region generation complete: %s rows", len(regions))

        logger.info("Phase 3B.1: Generating billing customer master")
        customer_generator = CustomerGenerator()
        customers = customer_generator.generate()
        customer_generator.save(customers)
        logger.info("Customer generation complete: %s rows", len(customers))

        logger.info("=" * 72)
        logger.info("SOURCE GENERATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 72)

    except Exception as error:
        logger.critical(
            "Source generation failed: %s",
            error,
            exc_info=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()