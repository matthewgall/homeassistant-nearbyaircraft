"""Tests for ADSB Nearby Aircraft aircraft processing helpers."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adsb_nearby.coordinator import ADSBDataUpdateCoordinator


def make_coordinator(hass):
    """Return a coordinator with a mocked config entry."""
    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    with patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock):
        return ADSBDataUpdateCoordinator(hass, entry)


async def test_process_aircraft_populates_known_fields(hass) -> None:
    """_process_aircraft copies common aircraft fields."""
    coordinator = make_coordinator(hass)
    plane = {
        "hex": "40825f",
        "flight": "EXS51NW",
        "r": "G-SUNU",
        "t": "A21N",
        "desc": "AIRBUS A-321neo",
        "lat": 51.47,
        "lon": -0.46,
        "alt_baro": 35975,
        "alt_geom": 37525,
        "gs": 427.1,
        "track": 1.21,
        "baro_rate": 0,
        "squawk": "1056",
        "emergency": "none",
        "category": "A3",
        "messages": 1000,
        "seen": 0.1,
        "rssi": -11.7,
    }

    result = coordinator._process_aircraft(plane, distance_km=12.5)

    assert result["hex"] == "40825f"
    assert result["flight"] == "EXS51NW"
    assert result["tail"] == "G-SUNU"
    assert result["aircraft_type"] == "A21N"
    assert result["description"] == "AIRBUS A-321neo"
    assert result["altitude_ft"] == 35975
    assert result["altitude_geom"] == 37525
    assert result["speed_kts"] == 427.1
    assert result["heading"] == 1.21
    assert result["vertical_rate_fpm"] == 0
    assert result["squawk"] == "1056"
    assert result["category"] == "A3"
    assert result["messages"] == 1000
    assert result["seen"] == 0.1
    assert result["rssi"] == -11.7
    assert result["distance_km"] == 12.5
    assert result["distance_display"] == "12.5 km"


async def test_process_aircraft_emergency_recorded(hass) -> None:
    """_process_aircraft records non-'none' emergency values."""
    coordinator = make_coordinator(hass)
    plane = {
        "hex": "abc",
        "flight": "SOS1",
        "emergency": "fire",
    }

    result = coordinator._process_aircraft(plane, distance_km=5.0)
    assert result["emergency"] == "fire"


async def test_process_aircraft_strips_flight(hass) -> None:
    """_process_aircraft strips whitespace from flight numbers."""
    coordinator = make_coordinator(hass)
    plane = {"hex": "abc", "flight": "BA123   "}

    result = coordinator._process_aircraft(plane, distance_km=5.0)
    assert result["flight"] == "BA123"
