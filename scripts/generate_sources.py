import sys

from scripts.generators.fx_generator import FXRateGenerator
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