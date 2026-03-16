from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock, Mock

import pytest

from apps.normalizer.worker import NormalizerWorker
from domain.itv_stations.schemas import NormalizedStation


def _build_station(base_payload: dict[str, object], *, station_id: str, raw_id: str) -> NormalizedStation:
    payload = deepcopy(base_payload)
    payload["station_id"] = station_id
    payload["raw_id"] = raw_id
    return NormalizedStation(**payload)


@pytest.mark.asyncio
async def test_process_message_transforms_and_publishes_every_station(
    normalized_station_payload: dict[str, object],
) -> None:
    worker = NormalizerWorker()
    first_station = _build_station(normalized_station_payload, station_id="CAT_BCN-001", raw_id="BCN-001")
    second_station = _build_station(normalized_station_payload, station_id="CAT_GIR-002", raw_id="GIR-002")
    transformer = Mock(transform=Mock(return_value=[first_station, second_station]))

    worker.factory = Mock(create=Mock(return_value=transformer))
    worker.publisher = Mock(publish=AsyncMock())

    await worker.process_message(
        {
            "message_id": "msg-1",
            "source": "catalunya",
            "payload": "<stations />",
            "format": "xml",
        }
    )

    worker.factory.create.assert_called_once_with("catalunya")
    assert worker.publisher.publish.await_count == 2
    assert worker.messages_processed == 1
    assert worker.messages_failed == 0


@pytest.mark.asyncio
async def test_process_message_accepts_empty_transformation_result() -> None:
    worker = NormalizerWorker()
    transformer = Mock(transform=Mock(return_value=[]))
    worker.factory = Mock(create=Mock(return_value=transformer))
    worker.publisher = Mock(publish=AsyncMock())

    await worker.process_message(
        {
            "message_id": "msg-2",
            "source": "galicia",
            "payload": {"stations": []},
            "format": "json",
        }
    )

    worker.publisher.publish.assert_not_called()
    assert worker.messages_processed == 1
    assert worker.messages_failed == 0


@pytest.mark.asyncio
async def test_process_message_marks_failure_for_invalid_message() -> None:
    worker = NormalizerWorker()

    with pytest.raises(ValueError, match="missing source or payload"):
        await worker.process_message(
            {
                "message_id": "msg-3",
                "source": "catalunya",
                "payload": None,
                "format": "xml",
            }
        )

    assert worker.messages_processed == 0
    assert worker.messages_failed == 1


@pytest.mark.asyncio
async def test_shutdown_disconnects_consumer_and_publisher() -> None:
    worker = NormalizerWorker()
    worker.consumer = Mock(disconnect=AsyncMock())
    worker.publisher = Mock(disconnect=AsyncMock())
    worker.messages_processed = 4
    worker.messages_failed = 1

    await worker.shutdown()

    worker.consumer.disconnect.assert_awaited_once()
    worker.publisher.disconnect.assert_awaited_once()