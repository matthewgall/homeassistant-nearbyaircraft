"""Tests for config flow validation of local and ADS-B Exchange sources."""
from __future__ import annotations

import pytest
from aiohttp import ClientError

from custom_components.adsb_nearby.config_flow import (
    CannotConnect,
    InvalidADSBData,
    InvalidAPIKey,
    InvalidHost,
    _validate_adsbexchange,
    _validate_local,
)


async def test_validate_local_success(hass, aioclient_mock) -> None:
    """Successful local validation returns expected metadata."""
    aioclient_mock.get(
        "http://192.168.1.5:8080/data/aircraft.json",
        json={
            "now": 1_700_000_000,
            "messages": 123,
            "aircraft": [{"hex": "abc"}],
        },
    )

    data = {
        "scheme": "http",
        "host": "192.168.1.5",
        "port": 8080,
        "path": "data/aircraft.json",
        "verify_ssl": False,
    }
    info = await _validate_local(hass, data)

    assert info["title"] == "ADSB Nearby (192.168.1.5)"
    assert info["aircraft_count"] == 1
    assert info["last_update"] == 1_700_000_000


async def test_validate_local_missing_aircraft(hass, aioclient_mock) -> None:
    """Local response missing aircraft array raises InvalidADSBData."""
    aioclient_mock.get(
        "http://192.168.1.5:8080/data/aircraft.json",
        json={"now": 1_700_000_000, "messages": 123},
    )

    data = {
        "scheme": "http",
        "host": "192.168.1.5",
        "port": 8080,
        "path": "/data/aircraft.json",
        "verify_ssl": False,
    }
    with pytest.raises(InvalidADSBData, match="Missing aircraft"):
        await _validate_local(hass, data)


async def test_validate_local_http_error(hass, aioclient_mock) -> None:
    """Local endpoint returning 404 raises InvalidHost."""
    aioclient_mock.get(
        "http://192.168.1.5:8080/data/aircraft.json",
        status=404,
    )

    data = {
        "scheme": "http",
        "host": "192.168.1.5",
        "port": 8080,
        "path": "/data/aircraft.json",
        "verify_ssl": False,
    }
    with pytest.raises(InvalidHost, match="HTTP 404"):
        await _validate_local(hass, data)


async def test_validate_local_connection_error(hass, aioclient_mock) -> None:
    """Local connection failure raises CannotConnect."""
    aioclient_mock.get(
        "http://192.168.1.5:8080/data/aircraft.json",
        exc=ClientError("boom"),
    )

    data = {
        "scheme": "http",
        "host": "192.168.1.5",
        "port": 8080,
        "path": "/data/aircraft.json",
        "verify_ssl": False,
    }
    with pytest.raises(CannotConnect):
        await _validate_local(hass, data)


async def test_validate_adsbexchange_success(hass, aioclient_mock) -> None:
    """Successful ADS-B Exchange validation returns expected metadata."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    aioclient_mock.get(
        "https://adsbexchange.com/api/aircraft/json/lat/51.47/lon/-0.46/dist/27/",
        json={"ac": [{"hex": "abc"}], "now": 1_700_000_000},
    )

    info = await _validate_adsbexchange(hass, api_key="key123", radius=50, update_interval=10)

    assert info["title"] == "ADSB Nearby (ADS-B Exchange)"
    assert info["aircraft_count"] == 1


async def test_validate_adsbexchange_unauthorized(hass, aioclient_mock) -> None:
    """ADS-B Exchange 401 response raises InvalidAPIKey."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    aioclient_mock.get(
        "https://adsbexchange.com/api/aircraft/json/lat/51.47/lon/-0.46/dist/27/",
        status=401,
    )

    with pytest.raises(InvalidAPIKey):
        await _validate_adsbexchange(hass, api_key="badkey", radius=50, update_interval=10)


async def test_validate_adsbexchange_aircraft_key(hass, aioclient_mock) -> None:
    """ADS-B Exchange can use either 'ac' or 'aircraft' response key."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    aioclient_mock.get(
        "https://adsbexchange.com/api/aircraft/json/lat/51.47/lon/-0.46/dist/27/",
        json={"aircraft": [{"hex": "xyz"}], "now": 1_700_000_000},
    )

    info = await _validate_adsbexchange(hass, api_key="key", radius=50, update_interval=10)
    assert info["aircraft_count"] == 1
