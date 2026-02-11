"""
Persister Worker
Consumes normalized data from RabbitMQ and persists it to PostgreSQL.
"""
import logging
import time

logger = logging.getLogger(__name__)


def main():
    """Main worker loop."""
    logger.info("Persister worker starting...")
    
    try:
        while True:
            # TODO: Connect to RabbitMQ and process messages
            logger.debug("Persister worker is running (placeholder)")
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Persister worker shutting down...")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    main()
