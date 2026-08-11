"""Tests for config flow validation of online ADSB sources."""
from __future__ import annotations

import pytest
from aiohttp import ClientError

from custom_components.adsb_nearby.config_flow import (
    CannotConnect,
    InvalidADSBData,
    _validate_adsb_fi,
    _validate_airplanes_live,
)


async def test_validate_adsb_fi_success(hass, aioclient_mock) -> None:
    """Successful adsb.fi validation returns expected metadata."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    aioclient_mock.get(
        "https://opendata.adsb.fi/api/v3/lat/51.47/lon/-0.46/dist/27",
        json={"ac": [{"hex": "abc"}], "total": 1, "now": 1_700_000_000_000},
    )

    info = await _validate_adsb_fi(hass, radius=50, update_interval=10)

    assert info["title"] == "ADSB Nearby (adsb.fi)"
    assert info["aircraft_count"] == 1
    assert info["last_update"] == 1_700_000_000_000


async def test_validate_adsb_fi_missing_ac(hass, aioclient_mock) -> None:
    """adsb.fi response missing the aircraft array raises an error."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    aioclient_mock.get(
        "https://opendata.adsb.fi/api/v3/lat/51.47/lon/-0.46/dist/27",
        json={"total": 0, "now": 1_700_000_000_000},
    )

    with pytest.raises(InvalidADSBData, match="Missing aircraft"):
        await _validate_adsb_fi(hass, radius=50, update_interval=10)


async def test_validate_adsb_fi_http_error(hass, aioclient_mock) -> None:
    """Non-200 adsb.fi response raises InvalidHost."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    aioclient_mock.get(
        "https://opendata.adsb.fi/api/v3/lat/51.47/lon/-0.46/dist/27",
        status=500,
    )

    with pytest.raises(Exception):
        await _validate_adsb_fi(hass, radius=50, update_interval=10)


async def test_validate_airplanes_live_success(hass, aioclient_mock) -> None:
    """Successful airplanes.live validation returns expected metadata."""
    hass.config.latitude = 60.3179
    hass.config.longitude = 24.9496
    aioclient_mock.get(
        "https://api.airplanes.live/v2/point/60.3179/24.9496/13",
        json={"ac": [{"hex": "def"}], "total": 1, "now": 1_700_000_000_000},
    )

    info = await _validate_airplanes_live(hass, radius=25, update_interval=10)

    assert info["title"] == "ADSB Nearby (airplanes.live)"
    assert info["aircraft_count"] == 1


async def test_validate_airplanes_live_ac_not_list(hass, aioclient_mock) -> None:
    """airplanes.live response with non-list ac raises an error."""
    hass.config.latitude = 60.3179
    hass.config.longitude = 24.9496
    aioclient_mock.get(
        "https://api.airplanes.live/v2/point/60.3179/24.9496/13",
        json={"ac": "not-a-list", "total": 0},
    )

    with pytest.raises(InvalidADSBData, match="not a list"):
        await _validate_airplanes_live(hass, radius=25, update_interval=10)


async def test_validate_airplanes_live_connection_error(hass, aioclient_mock) -> None:
    """Connection errors to airplanes.live raise CannotConnect."""
    hass.config.latitude = 60.3179
    hass.config.longitude = 24.9496
    aioclient_mock.get(
        "https://api.airplanes.live/v2/point/60.3179/24.9496/13",
        exc=ClientError("boom"),
    )

    with pytest.raises(CannotConnect):
        await _validate_airplanes_live(hass, radius=25, update_interval=10)
