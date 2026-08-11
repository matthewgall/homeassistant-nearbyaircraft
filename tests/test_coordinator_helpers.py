"""Tests for ADSB Nearby Aircraft coordinator helper functions."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.adsb_nearby.coordinator import (
    ADSBDataUpdateCoordinator,
    haversine_distance,
)
from custom_components.adsb_nearby.const import (
    SOURCE_TYPE_LOCAL,
    SOURCE_TYPE_ADSBEXCHANGE,
)


def test_haversine_distance_known_value() -> None:
    """Haversine distance between two nearby points is approximately correct."""
    # London to a point ~111 km north
    dist = haversine_distance(51.5, -0.1, 52.5, -0.1)
    assert dist == pytest.approx(111.2, rel=0.02)


def test_haversine_distance_same_point() -> None:
    """Distance from a point to itself is zero."""
    assert haversine_distance(10.0, 20.0, 10.0, 20.0) == 0.0


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_update_local_filters_by_radius(mock_load_db, hass) -> None:
    """Local source filters aircraft outside configured radius."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={
            "source_type": SOURCE_TYPE_LOCAL,
            "host": "192.168.1.100",
            "scheme": "http",
            "port": 80,
            "path": "/data/aircraft.json",
            "radius": 10,
            "update_interval": 10,
            "verify_ssl": True,
            "enable_routes": False,
            "min_altitude": 0,
        },
    )
    entry.add_to_hass(hass)
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    fetch_data = {
        "now": 1_700_000_000,
        "messages": 1234,
        "aircraft": [
            {"hex": "near", "lat": 51.47, "lon": -0.46, "alt_baro": 5000},
            {"hex": "far", "lat": 52.0, "lon": -1.0, "alt_baro": 5000},
        ],
    }

    with patch.object(
        ADSBDataUpdateCoordinator, "_async_fetch_data", new_callable=AsyncMock, return_value=fetch_data
    ):
        result = await coordinator._update_local()

    assert result["aircraft_count"] == 1
    assert result["aircraft"][0]["hex"] == "near"


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_update_local_missing_aircraft_raises(mock_load_db, hass) -> None:
    """Local update raises when aircraft array is missing."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={
            "source_type": SOURCE_TYPE_LOCAL,
            "host": "192.168.1.100",
            "scheme": "http",
            "port": 80,
            "path": "/data/aircraft.json",
            "radius": 10,
            "update_interval": 10,
            "verify_ssl": True,
            "enable_routes": False,
            "min_altitude": 0,
        },
    )
    entry.add_to_hass(hass)
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    with (
        patch.object(
            ADSBDataUpdateCoordinator, "_async_fetch_data", new_callable=AsyncMock, return_value={}
        ),
        pytest.raises(UpdateFailed, match="missing aircraft array"),
    ):
        await coordinator._update_local()


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_update_adsbexchange_uses_api_key(mock_load_db, hass) -> None:
    """ADS-B Exchange update sends the api-auth header."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={
            "source_type": SOURCE_TYPE_ADSBEXCHANGE,
            "api_key": "secret123",
            "radius": 50,
            "update_interval": 10,
            "enable_routes": False,
            "min_altitude": 0,
        },
    )
    entry.add_to_hass(hass)
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    fetch_data = {
        "ac": [{"hex": "abc", "dst": 10.0, "alt_baro": 10000}],
        "now": 1_700_000_000,
        "total": 1,
    }

    with patch.object(
        ADSBDataUpdateCoordinator, "_async_fetch_data", new_callable=AsyncMock, return_value=fetch_data
    ) as mock_fetch:
        result = await coordinator._update_adsbexchange()

    assert result["aircraft_count"] == 1
    call_args = mock_fetch.call_args
    assert call_args[1]["headers"] == {"api-auth": "secret123"}


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_format_distance_metric(mock_load_db, hass) -> None:
    """Distance formatting respects metric unit system."""
    from homeassistant.util.unit_system import METRIC_SYSTEM
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    hass.config.units = METRIC_SYSTEM
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    assert coordinator.format_distance(10.0) == "10.0 km"


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_format_distance_imperial(mock_load_db, hass) -> None:
    """Distance formatting respects imperial unit system."""
    from homeassistant.util.unit_system import IMPERIAL_SYSTEM
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    hass.config.units = IMPERIAL_SYSTEM
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    assert coordinator.format_distance(16.09) == "10.0 mi"


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_lookup_routes_skipped_when_disabled(mock_load_db, hass) -> None:
    """Route lookup returns empty when disabled."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    routes = await coordinator._lookup_routes([{"hex": "abc", "flight": "BA123", "lat": 51.0, "lon": -0.1}])
    assert routes == {}


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_lookup_routes_uses_cache(mock_load_db, hass) -> None:
    """Route lookup returns cached routes without calling the API."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": True, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    coordinator = ADSBDataUpdateCoordinator(hass, entry)
    coordinator._route_cache["BA123"] = {
        "route": {"origin_icao": "EGLL", "destination_icao": "KLAX"},
        "expires": 9999999999.0,
    }

    routes = await coordinator._lookup_routes([{"hex": "abc", "flight": "BA123", "lat": 51.0, "lon": -0.1}])
    assert routes["BA123"]["origin_icao"] == "EGLL"
