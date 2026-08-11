"""Tests for ADSB Nearby Aircraft sensor entities."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adsb_nearby.coordinator import ADSBDataUpdateCoordinator
from custom_components.adsb_nearby.sensor import (
    ADSBAircraftCountSensor,
    ADSBClosestAircraftSensor,
    ADSBNearestAircraftSensor,
)


def sample_aircraft() -> list[dict]:
    return [
        {
            "hex": "40825f",
            "flight": "EXS51NW",
            "tail": "G-SUNU",
            "distance_km": 5.0,
            "distance_display": "5.0 km",
            "altitude_ft": 10000,
        },
        {
            "hex": "4caf35",
            "flight": "RYR6ZM",
            "distance_km": 20.0,
            "distance_display": "20.0 km",
            "altitude_ft": 15000,
        },
    ]


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
    coordinator.data = {
        "aircraft": sample_aircraft(),
        "aircraft_count": 2,
        "total_messages": 100,
        "radius_km": 50.0,
        "home_latitude": 51.47,
        "home_longitude": -0.46,
        "last_update": 1_700_000_000.0,
    }
    return coordinator


async def test_closest_aircraft_sensor_value(hass, sample_coordinator) -> None:
    """Closest aircraft sensor shows the nearest flight."""
    sensor = ADSBClosestAircraftSensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.native_value == "EXS51NW"


async def test_closest_aircraft_sensor_falls_back_to_tail(hass, sample_coordinator) -> None:
    """Closest aircraft sensor falls back to tail when flight is unavailable."""
    sample_coordinator.data["aircraft"][0].pop("flight")
    sensor = ADSBClosestAircraftSensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.native_value == "G-SUNU"


async def test_closest_aircraft_sensor_falls_back_to_hex(hass, sample_coordinator) -> None:
    """Closest aircraft sensor falls back to hex code when no flight or tail."""
    sample_coordinator.data["aircraft"][0].pop("flight")
    sample_coordinator.data["aircraft"][0].pop("tail")
    sensor = ADSBClosestAircraftSensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.native_value == "40825f"


async def test_closest_aircraft_sensor_no_data(hass, sample_coordinator) -> None:
    """Closest aircraft sensor handles empty data gracefully."""
    sample_coordinator.data = {"aircraft": [], "aircraft_count": 0}
    sensor = ADSBClosestAircraftSensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.native_value == "No aircraft"


async def test_aircraft_count_sensor_value(hass, sample_coordinator) -> None:
    """Aircraft count sensor reflects coordinator count."""
    sensor = ADSBAircraftCountSensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.native_value == 2
    attrs = sensor.extra_state_attributes
    assert attrs["total_messages"] == 100
    assert attrs["radius_km"] == 50.0


async def test_nearest_aircraft_sensor_summary(hass, sample_coordinator) -> None:
    """Nearest aircraft sensor shows a count summary."""
    sensor = ADSBNearestAircraftSensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.native_value == "2 aircraft detected"


async def test_nearest_aircraft_sensor_empty(hass, sample_coordinator) -> None:
    """Nearest aircraft sensor reports when no aircraft are detected."""
    sample_coordinator.data = {"aircraft": [], "aircraft_count": 0}
    sensor = ADSBNearestAircraftSensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.native_value == "No aircraft detected"
