"""
RabbitMQ Quality Test Message Sender.

This script sends quality test data files as messages through RabbitMQ
to test the complete ingestion pipeline end-to-end.

Usage:
    docker compose run --rm gateway python tests/fixtures/quality_data/send_qa_messages.py

Environment Requirements:
    - RabbitMQ must be running (docker compose up -d rabbitmq)
    - Connection settings from core/config.py
"""

import json
import base64
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import pika
    from core.config import settings
    from core.messaging.producer import DataProducer
except ImportError as e:
    logger.error(f"Could not import required modules: {e}")
    logger.info("Run with: docker compose run --rm gateway python tests/fixtures/quality_data/send_qa_messages.py")
    sys.exit(1)


class QAMessageSender:
    """Send quality assurance test messages to RabbitMQ."""

    def __init__(self):
        """Initialize sender."""
        self.fixtures_path = Path(__file__).parent
        self.producer = None

    def connect(self) -> None:
        """Connect to RabbitMQ."""
        try:
            self.producer = DataProducer()
            logger.info("✅ Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"❌ Failed to connect to RabbitMQ: {e}")
            raise

    def disconnect(self) -> None:
        """Disconnect from RabbitMQ."""
        if self.producer:
            self.producer.close()

    def send_all_tests(self) -> None:
        """Send all quality test files."""
        logger.info("\n" + "=" * 80)
        logger.info("🧪 SENDING QUALITY TEST MESSAGES TO RABBITMQ")
        logger.info("=" * 80 + "\n")

        tests = [
            ("catalunya", "quality_test_catalunya.xml", "xml"),
            ("valencia", "quality_test_valencia.json", "json"),
            ("galicia", "quality_test_galicia.csv", "csv"),
        ]

        for source, filename, format_type in tests:
            self._send_test_file(source, filename, format_type)

        logger.info("\n" + "=" * 80)
        logger.info("✅ All quality test messages sent successfully!")
        logger.info("=" * 80 + "\n")

    def _send_test_file(self, source: str, filename: str, format_type: str) -> None:
        """Send a single test file."""
        file_path = self.fixtures_path / filename

        if not file_path.exists():
            logger.error(f"❌ Test file not found: {file_path}")
            return

        logger.info(f"📨 Sending {source.upper()} ({filename})")

        try:
            # Read file content
            with open(file_path, "rb") as f:
                raw_content = f.read()

            # Create message envelope
            message = {
                "header": {
                    "message_id": f"qa-test-{source}-{datetime.now().isoformat()}",
                    "timestamp": datetime.now().isoformat(),
                    "domain": "itv_stations",
                    "source_system": source,
                    "content_type": f"application/{format_type}",
                },
                "payload": {
                    "raw_content": base64.b64encode(raw_content).decode('utf-8')
                },
            }

            # Send to RabbitMQ
            self.producer.publish(
                routing_key=f"raw_data.itv_stations",
                message=json.dumps(message),
                exchange="data_exchange",
            )

            logger.info(f"   ✅ Sent {len(raw_content)} bytes for {source}")

        except Exception as e:
            logger.error(f"   ❌ Error sending {source}: {e}")

    def send_individual_test(self, source: str) -> None:
        """Send a single test file by source."""
        tests_map = {
            "catalunya": ("quality_test_catalunya.xml", "xml"),
            "valencia": ("quality_test_valencia.json", "json"),
            "galicia": ("quality_test_galicia.csv", "csv"),
        }

        if source not in tests_map:
            logger.error(f"Unknown source: {source}")
            logger.info(f"Supported sources: {', '.join(tests_map.keys())}")
            return

        filename, format_type = tests_map[source]
        self._send_test_file(source, filename, format_type)


def main():
    """Main entry point."""
    sender = QAMessageSender()

    try:
        sender.connect()
        sender.send_all_tests()
    except KeyboardInterrupt:
        logger.info("\n⏹️  Interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        sender.disconnect()


if __name__ == "__main__":
    main()
