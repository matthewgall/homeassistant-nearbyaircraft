"""Tests for ADSB Nearby Aircraft coordinator updates."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adsb_nearby.const import (
    SOURCE_TYPE_ADSB_FI,
    SOURCE_TYPE_AIRPLANES_LIVE,
)
from custom_components.adsb_nearby.coordinator import ADSBDataUpdateCoordinator


def make_config(source_type: str, **kwargs) -> MockConfigEntry:
    """Return a MockConfigEntry for the given source type."""
    return MockConfigEntry(
        domain="adsb_nearby",
        data={
            "source_type": source_type,
            "radius": 50,
            "update_interval": 10,
            "enable_routes": False,
            "min_altitude": 0,
            **kwargs,
        },
    )


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_update_adsb_fi_uses_dst(mock_load_db, hass) -> None:
    """adsb.fi update converts pre-computed dst from NM to km."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    entry = make_config(SOURCE_TYPE_ADSB_FI)
    entry.add_to_hass(hass)
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    fetch_data = {
        "ac": [
            {
                "hex": "40825f",
                "flight": "EXS51NW ",
                "lat": 51.47,
                "lon": -0.46,
                "dst": 10.0,  # NM
                "alt_baro": 10000,
            },
        ],
        "now": 1_700_000_000_000,
        "total": 1,
    }

    with patch.object(
        ADSBDataUpdateCoordinator, "_async_fetch_data", new_callable=AsyncMock, return_value=fetch_data
    ):
        result = await coordinator._update_adsb_fi()

    assert result["aircraft_count"] == 1
    assert result["total_messages"] == 1
    assert result["last_update"] == 1_700_000_000.0  # ms -> s
    assert result["aircraft"][0]["distance_km"] == pytest.approx(18.52, rel=1e-2)


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_update_airplanes_live_fallback_haversine(mock_load_db, hass) -> None:
    """airplanes.live update falls back to haversine when dst is missing."""
    hass.config.latitude = 60.0
    hass.config.longitude = 24.0
    entry = make_config(SOURCE_TYPE_AIRPLANES_LIVE)
    entry.add_to_hass(hass)
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    fetch_data = {
        "ac": [
            {
                "hex": "abc123",
                "lat": 60.0,
                "lon": 24.1,
                # dst intentionally missing
                "alt_baro": 5000,
            },
        ],
        "now": 1_700_000_000,
        "total": 1,
    }

    with patch.object(
        ADSBDataUpdateCoordinator, "_async_fetch_data", new_callable=AsyncMock, return_value=fetch_data
    ):
        result = await coordinator._update_airplanes_live()

    assert result["aircraft_count"] == 1
    # ~ 111 km per degree of longitude at 60N, scaled by cos(lat)
    assert result["aircraft"][0]["distance_km"] == pytest.approx(5.5, rel=0.1)


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_update_adsb_fi_filters_altitude(mock_load_db, hass) -> None:
    """adsb.fi update respects the minimum altitude filter."""
    entry = make_config(SOURCE_TYPE_ADSB_FI, min_altitude=5000)
    entry.add_to_hass(hass)
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    fetch_data = {
        "ac": [
            {"hex": "high", "dst": 5.0, "alt_baro": 10000},
            {"hex": "low", "dst": 5.0, "alt_baro": 1000},
        ],
        "now": 1_700_000_000,
        "total": 2,
    }

    with patch.object(
        ADSBDataUpdateCoordinator, "_async_fetch_data", new_callable=AsyncMock, return_value=fetch_data
    ):
        result = await coordinator._update_adsb_fi()

    assert result["aircraft_count"] == 1
    assert result["aircraft"][0]["hex"] == "high"


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_update_adsb_fi_sorts_by_distance(mock_load_db, hass) -> None:
    """adsb.fi update returns aircraft sorted by distance."""
    entry = make_config(SOURCE_TYPE_ADSB_FI)
    entry.add_to_hass(hass)
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    fetch_data = {
        "ac": [
            {"hex": "far", "dst": 20.0, "alt_baro": 10000},
            {"hex": "near", "dst": 5.0, "alt_baro": 10000},
        ],
        "now": 1_700_000_000,
        "total": 2,
    }

    with patch.object(
        ADSBDataUpdateCoordinator, "_async_fetch_data", new_callable=AsyncMock, return_value=fetch_data
    ):
        result = await coordinator._update_adsb_fi()

    assert [p["hex"] for p in result["aircraft"]] == ["near", "far"]


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_update_airplanes_live_missing_ac_raises(mock_load_db, hass) -> None:
    """airplanes.live update raises when the ac array is missing."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    entry = make_config(SOURCE_TYPE_AIRPLANES_LIVE)
    entry.add_to_hass(hass)
    hass.config.latitude = 60.0
    hass.config.longitude = 24.0
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    with (
        patch.object(
            ADSBDataUpdateCoordinator, "_async_fetch_data", new_callable=AsyncMock, return_value={}
        ),
        pytest.raises(UpdateFailed, match="missing ac array"),
    ):
        await coordinator._update_airplanes_live()


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_update_adsb_fi_url(mock_load_db, hass) -> None:
    """adsb.fi coordinator builds the correct API URL."""
    entry = make_config(SOURCE_TYPE_ADSB_FI)
    entry.add_to_hass(hass)
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    assert coordinator.url == "https://opendata.adsb.fi/api/v3/lat/51.47/lon/-0.46/dist/27"


@patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock)
async def test_update_airplanes_live_url(mock_load_db, hass) -> None:
    """airplanes.live coordinator builds the correct API URL."""
    entry = make_config(SOURCE_TYPE_AIRPLANES_LIVE)
    entry.add_to_hass(hass)
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    coordinator = ADSBDataUpdateCoordinator(hass, entry)

    assert coordinator.url == "https://api.airplanes.live/v2/point/51.47/-0.46/27"
