from __future__ import annotations

import json
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from apps.persister.worker import PersisterWorker


class DummyProcessContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyIncomingMessage:
    def __init__(self, body: str, *, message_id: str = "msg-1") -> None:
        self.body = body.encode("utf-8")
        self.message_id = message_id
        self.ack = AsyncMock()
        self.nack = AsyncMock()

    def process(self, ignore_processed: bool = True) -> DummyProcessContext:
        return DummyProcessContext()


class FakeSession:
    def __init__(self) -> None:
        self.execute = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.add = Mock()

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest.mark.asyncio
async def test_persister_worker_acknowledges_successful_persistence(
    monkeypatch: pytest.MonkeyPatch,
    normalized_station: object,
) -> None:
    worker = PersisterWorker()
    session = FakeSession()
    monkeypatch.setattr("apps.persister.worker.AsyncSessionLocal", lambda: session)

    message = DummyIncomingMessage(
        json.dumps(normalized_station.model_dump(mode="json")),
        message_id="msg-success",
    )

    await worker.process_message(message)

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    message.ack.assert_awaited_once()
    message.nack.assert_not_called()


@pytest.mark.asyncio
async def test_persister_worker_nacks_on_database_error(
    monkeypatch: pytest.MonkeyPatch,
    normalized_station: object,
) -> None:
    worker = PersisterWorker()
    session = FakeSession()
    session.execute.side_effect = SQLAlchemyError("db down")
    monkeypatch.setattr("apps.persister.worker.AsyncSessionLocal", lambda: session)

    message = DummyIncomingMessage(
        json.dumps(normalized_station.model_dump(mode="json")),
        message_id="msg-db-error",
    )

    await worker.process_message(message)

    session.rollback.assert_awaited_once()
    message.ack.assert_not_called()
    message.nack.assert_awaited_once_with(requeue=False)


@pytest.mark.asyncio
async def test_persister_worker_nacks_invalid_json() -> None:
    worker = PersisterWorker()
    message = DummyIncomingMessage("not-json", message_id="msg-invalid-json")

    await worker.process_message(message)

    message.ack.assert_not_called()
    message.nack.assert_awaited_once_with(requeue=False)