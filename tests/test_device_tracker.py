"""Tests for ADSB Nearby Aircraft device tracker entity."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.device_tracker import SourceType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adsb_nearby.coordinator import ADSBDataUpdateCoordinator
from custom_components.adsb_nearby.device_tracker import ADSBAircraftDeviceTracker


@pytest.fixture
def sample_coordinator(hass):
    """Return a coordinator with sample aircraft data."""
    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    with patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock):
        coordinator = ADSBDataUpdateCoordinator(hass, entry)
    return coordinator


async def test_device_tracker_properties(hass, sample_coordinator) -> None:
    """Device tracker exposes position and metadata for its aircraft."""
    sample_coordinator.data = {
        "aircraft": [
            {
                "hex": "40825F",
                "flight": "EXS51NW",
                "latitude": 51.47,
                "longitude": -0.46,
                "altitude_ft": 10000,
                "distance_display": "5 km",
            },
        ],
    }
    tracker = ADSBAircraftDeviceTracker(sample_coordinator, sample_coordinator.config_entry, "40825F")

    assert tracker.available is True
    assert tracker.latitude == 51.47
    assert tracker.longitude == -0.46
    assert tracker.source_type == SourceType.GPS
    assert "EXS51NW" in tracker.name
    assert tracker.entity_id == "device_tracker.adsb_aircraft_40825f"


async def test_device_tracker_falls_back_to_tail(hass, sample_coordinator) -> None:
    """Device tracker name falls back to tail number when flight is missing."""
    sample_coordinator.data = {
        "aircraft": [
            {"hex": "40825F", "tail": "G-SUNU", "latitude": 51.0, "longitude": -0.1},
        ],
    }
    tracker = ADSBAircraftDeviceTracker(sample_coordinator, sample_coordinator.config_entry, "40825F")
    assert tracker.name == "G-SUNU (40825F)"


async def test_device_tracker_unavailable(hass, sample_coordinator) -> None:
    """Device tracker is unavailable when aircraft leaves range."""
    sample_coordinator.data = {"aircraft": []}
    tracker = ADSBAircraftDeviceTracker(sample_coordinator, sample_coordinator.config_entry, "40825F")

    assert tracker.available is False
    assert tracker.latitude is None
    assert tracker.name == "Aircraft 40825F"
