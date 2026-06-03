import logging
import time

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("question-worker")


def main() -> None:
    logger.info("starting question worker in %s", settings.app_env)
    while True:
        # Placeholder loop for async generation queue consumption.
        logger.info("worker heartbeat")
        time.sleep(15)


if __name__ == "__main__":
    main()
