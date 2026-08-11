"""Tests for ADSB Nearby Aircraft binary sensor entities."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adsb_nearby.binary_sensor import (
    ADSBAircraftNearbyBinarySensor,
    ADSBEmergencyAircraftBinarySensor,
)
from custom_components.adsb_nearby.coordinator import ADSBDataUpdateCoordinator


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


async def test_aircraft_nearby_on(hass, sample_coordinator) -> None:
    """Aircraft nearby sensor is on when aircraft are present."""
    sample_coordinator.data = {"aircraft": [{"hex": "abc"}], "aircraft_count": 1, "radius_km": 50.0}
    sensor = ADSBAircraftNearbyBinarySensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.is_on is True
    attrs = sensor.extra_state_attributes
    assert attrs["aircraft_count"] == 1


async def test_aircraft_nearby_off(hass, sample_coordinator) -> None:
    """Aircraft nearby sensor is off when no data is available."""
    sample_coordinator.data = None
    sensor = ADSBAircraftNearbyBinarySensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.is_on is False


async def test_emergency_aircraft_7700(hass, sample_coordinator) -> None:
    """Emergency sensor triggers on squawk 7700."""
    sample_coordinator.data = {
        "aircraft": [{"hex": "abc", "squawk": "7700", "flight": "SOS1", "distance_display": "5 km", "altitude_ft": 10000}],
    }
    sensor = ADSBEmergencyAircraftBinarySensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.is_on is True
    attrs = sensor.extra_state_attributes
    assert attrs["emergency_count"] == 1
    assert attrs["emergencies"][0]["squawk"] == "7700"


async def test_emergency_aircraft_7600(hass, sample_coordinator) -> None:
    """Emergency sensor triggers on radio failure squawk 7600."""
    sample_coordinator.data = {
        "aircraft": [{"hex": "abc", "squawk": "7600", "flight": "RDOFAIL"}],
    }
    sensor = ADSBEmergencyAircraftBinarySensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.is_on is True


async def test_emergency_aircraft_7500(hass, sample_coordinator) -> None:
    """Emergency sensor triggers on hijack squawk 7500."""
    sample_coordinator.data = {
        "aircraft": [{"hex": "abc", "squawk": "7500"}],
    }
    sensor = ADSBEmergencyAircraftBinarySensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.is_on is True


async def test_emergency_aircraft_none(hass, sample_coordinator) -> None:
    """Emergency sensor is off when no emergency squawks are present."""
    sample_coordinator.data = {
        "aircraft": [{"hex": "abc", "squawk": "1234"}],
    }
    sensor = ADSBEmergencyAircraftBinarySensor(sample_coordinator, sample_coordinator.config_entry)
    assert sensor.is_on is False
    attrs = sensor.extra_state_attributes
    assert attrs["emergency_count"] == 0
