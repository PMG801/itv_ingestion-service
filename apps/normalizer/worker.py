"""
Normalizer Worker
Consumes raw data from RabbitMQ, normalizes it, and publishes to the next queue.
"""
import logging
import time

logger = logging.getLogger(__name__)


def main():
    """Main worker loop."""
    logger.info("Normalizer worker starting...")
    
    try:
        while True:
            # TODO: Connect to RabbitMQ and process messages
            logger.debug("Normalizer worker is running (placeholder)")
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Normalizer worker shutting down...")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    main()
