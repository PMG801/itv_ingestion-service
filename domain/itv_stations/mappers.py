"""Mappers for transforming input data to ITVStation models."""

from typing import Any

from .models import ITVStation


class ITVStationMapper:
    """Base mapper for ITV station transformations."""

    @staticmethod
    def map_to_station(raw_data: dict[str, Any], source_system: str) -> ITVStation:
        """
        Transform raw data to ITVStation model.

        Args:
            raw_data: Raw input data
            source_system: Source system identifier

        Returns:
            ITVStation: Normalized station model
        """
        raise NotImplementedError("Subclasses must implement map_to_station")
