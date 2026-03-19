from __future__ import annotations

from copy import deepcopy
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest

from apps.normalizer.worker import NormalizerWorker
from domain.itv_stations.schemas import NormalizedStation


def _build_station(base_payload: dict[str, object], *, station_id: str, raw_id: str) -> NormalizedStation:
    payload = cast(dict[str, Any], deepcopy(base_payload))
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
    transformer.rejected_items = []
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

    worker.publisher.publish.assert_awaited_once()
    publish_call = worker.publisher.publish.await_args
    assert publish_call.kwargs["exchange_name"] == "rejected_data"
    assert publish_call.kwargs["routing_key"] == "itv_stations"
    assert publish_call.kwargs["message"]["reason"] == "no_stations_extracted"
    assert publish_call.kwargs["message"]["rejection_level"] == "message"
    assert worker.messages_processed == 1
    assert worker.messages_failed == 0
    assert worker.messages_rejected == 1
    assert worker.stations_rejected == 0


@pytest.mark.asyncio
async def test_process_message_publishes_station_level_rejections(
    normalized_station_payload: dict[str, object],
) -> None:
    worker = NormalizerWorker()
    station = _build_station(normalized_station_payload, station_id="GAL_LU-001", raw_id="LU-001")
    transformer = Mock(transform=Mock(return_value=[station]))
    transformer.rejected_items = [
        {
            "reason": "missing_raw_id",
            "raw_fragment": {"nome": "Invalid station"},
        }
    ]
    worker.factory = Mock(create=Mock(return_value=transformer))
    worker.publisher = Mock(publish=AsyncMock())

    await worker.process_message(
        {
            "message_id": "msg-2b",
            "source": "galicia",
            "payload": {"stations": [{"id": "LU-001"}]},
            "format": "json",
        }
    )

    assert worker.publisher.publish.await_count == 2
    first_call = worker.publisher.publish.await_args_list[0]
    second_call = worker.publisher.publish.await_args_list[1]

    assert first_call.kwargs["exchange_name"] == "rejected_data"
    assert first_call.kwargs["message"]["rejection_level"] == "station"
    assert second_call.kwargs["exchange_name"] == "normalized_data"
    assert second_call.kwargs["message"]["station_id"] == "GAL_LU-001"

    assert worker.messages_processed == 1
    assert worker.messages_failed == 0
    assert worker.messages_rejected == 0
    assert worker.stations_rejected == 1


@pytest.mark.asyncio
async def test_process_message_avoids_duplicate_message_rejection_when_station_rejected() -> None:
    worker = NormalizerWorker()
    transformer = Mock(transform=Mock(return_value=[]))
    transformer.rejected_items = [
        {
            "reason": "missing_raw_id",
            "raw_fragment": {"nome": "Invalid station"},
        }
    ]
    worker.factory = Mock(create=Mock(return_value=transformer))
    worker.publisher = Mock(publish=AsyncMock())

    await worker.process_message(
        {
            "message_id": "msg-2c",
            "source": "galicia",
            "payload": {"stations": [{"nome": "Sin ID"}]},
            "format": "json",
        }
    )

    worker.publisher.publish.assert_awaited_once()
    publish_call = worker.publisher.publish.await_args
    assert publish_call.kwargs["exchange_name"] == "rejected_data"
    assert publish_call.kwargs["message"]["rejection_level"] == "station"
    assert publish_call.kwargs["message"]["reason"] == "missing_raw_id"

    assert worker.messages_processed == 1
    assert worker.messages_failed == 0
    assert worker.messages_rejected == 0
    assert worker.stations_rejected == 1


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