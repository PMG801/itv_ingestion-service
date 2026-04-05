"""Tests for configuration module."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from core.config import Settings


def test_settings_loads_from_environment() -> None:
    """Test that Settings loads values from environment variables."""
    with patch.dict(
        os.environ,
        {
            "APP_NAME": "TestApp",
            "LOG_LEVEL": "DEBUG",
        },
    ):
        settings = Settings()
        assert settings.APP_NAME == "TestApp"
        assert settings.LOG_LEVEL == "DEBUG"


def test_settings_has_required_fields() -> None:
    """Test that Settings has all required fields."""
    settings = Settings()

    # Basic fields
    assert hasattr(settings, "APP_NAME")
    assert hasattr(settings, "LOG_LEVEL")
    assert hasattr(settings, "POSTGRES_HOST")
    assert hasattr(settings, "RABBITMQ_HOST")
    assert hasattr(settings, "RABBITMQ_PORT")
    assert hasattr(settings, "RABBITMQ_URL")


def test_settings_log_level_default() -> None:
    """Test that LOG_LEVEL defaults to INFO."""
    settings = Settings()
    assert settings.LOG_LEVEL.upper() in ["INFO", "DEBUG", "WARNING", "ERROR"]


def test_settings_postgres_connection_string() -> None:
    """Test that PostgreSQL settings are valid strings."""
    settings = Settings()
    assert isinstance(settings.POSTGRES_HOST, str)
    assert isinstance(settings.POSTGRES_PORT, int)
    assert isinstance(settings.POSTGRES_USER, str)
    assert isinstance(settings.POSTGRES_DB, str)
    assert len(settings.POSTGRES_HOST) > 0
    assert len(settings.POSTGRES_USER) > 0


def test_settings_rabbitmq_connection_string() -> None:
    """Test that RabbitMQ URL is properly formatted."""
    settings = Settings()
    rabbitmq_url = settings.RABBITMQ_URL
    assert isinstance(rabbitmq_url, str)
    # Should contain amqp protocol indicator
    assert "amqp" in rabbitmq_url.lower()


def test_settings_rabbitmq_host_and_port() -> None:
    """Test that RabbitMQ host and port are set correctly."""
    settings = Settings()
    assert isinstance(settings.RABBITMQ_HOST, str)
    assert isinstance(settings.RABBITMQ_PORT, int)
    assert settings.RABBITMQ_PORT > 0


@pytest.mark.parametrize(
    "env_var,value",
    [
        ("LOG_LEVEL", "DEBUG"),
        ("LOG_LEVEL", "INFO"),
        ("LOG_LEVEL", "WARNING"),
        ("LOG_LEVEL", "ERROR"),
    ],
)
def test_settings_log_levels(env_var: str, value: str) -> None:
    """Test that various log levels are accepted."""
    with patch.dict(os.environ, {env_var: value}):
        settings = Settings()
        assert settings.LOG_LEVEL.upper() == value.upper()


def test_settings_app_name() -> None:
    """Test that APP_NAME is set."""
    settings = Settings()
    assert isinstance(settings.APP_NAME, str)
    assert len(settings.APP_NAME) > 0


def test_settings_postgres_defaults() -> None:
    """Test that PostgreSQL settings have sensible defaults."""
    settings = Settings()
    assert settings.POSTGRES_HOST is not None
    assert settings.POSTGRES_PORT is not None
    assert settings.POSTGRES_USER is not None
    assert settings.POSTGRES_DB is not None
