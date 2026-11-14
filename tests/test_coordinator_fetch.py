"""Tests for ADSB Nearby Aircraft coordinator fetch and route logic."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adsb_nearby.coordinator import ADSBDataUpdateCoordinator


def make_coordinator(hass):
    """Return a coordinator with an adsb.lol config entry."""
    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    with patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock):
        return ADSBDataUpdateCoordinator(hass, entry)


async def test_async_fetch_data_retry_then_success(hass) -> None:
    """_async_fetch_data retries on 5xx and succeeds on second attempt."""
    coordinator = make_coordinator(hass)
    ok_response = MagicMock()
    ok_response.status = 200
    ok_response.json = AsyncMock(return_value={"ac": []})

    fail_response = MagicMock()
    fail_response.status = 503
    fail_response.request_info = MagicMock()
    fail_response.history = ()
    fail_response.headers = {}

    session_mock = MagicMock()
    session_mock.get = MagicMock()
    session_mock.get.return_value.__aenter__ = AsyncMock(side_effect=[fail_response, ok_response])
    session_mock.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "custom_components.adsb_nearby.coordinator.async_get_clientsession",
        return_value=session_mock,
    ):
        result = await coordinator._async_fetch_data("https://example.com/data")

    assert result == {"ac": []}
    assert session_mock.get.call_count == 2


async def test_async_fetch_data_4xx_raises_update_failed(hass) -> None:
    """_async_fetch_data does not retry on 4xx errors."""
    coordinator = make_coordinator(hass)
    fail_response = MagicMock()
    fail_response.status = 404
    fail_response.request_info = MagicMock()
    fail_response.history = ()
    fail_response.headers = {}

    session_mock = MagicMock()
    session_mock.get = MagicMock()
    session_mock.get.return_value.__aenter__ = AsyncMock(return_value=fail_response)
    session_mock.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "custom_components.adsb_nearby.coordinator.async_get_clientsession",
            return_value=session_mock,
        ),
        pytest.raises(UpdateFailed, match="HTTP 404"),
    ):
        await coordinator._async_fetch_data("https://example.com/data")


async def test_async_fetch_data_timeout_after_retries(hass) -> None:
    """_async_fetch_data raises UpdateFailed after timeouts exhaust retries."""
    import asyncio

    coordinator = make_coordinator(hass)

    session_mock = MagicMock()
    session_mock.get = MagicMock()
    session_mock.get.return_value.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
    session_mock.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "custom_components.adsb_nearby.coordinator.async_get_clientsession",
            return_value=session_mock,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_fetch_data("https://example.com/data")


async def test_lookup_routes_api_success(hass, aioclient_mock) -> None:
    """_lookup_routes fetches and caches routes from the bulk adsb.im API."""
    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": True, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    with patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock):
        coordinator = ADSBDataUpdateCoordinator(hass, entry)

    aioclient_mock.post(
        "http://adsb.im/api/0/routeset",
        json=[{
            "callsign": "BA123",
            "_airports": [
                {"icao": "EGLL", "iata": "LHR"},
                {"icao": "KLAX", "iata": "LAX"},
            ],
        }],
    )

    routes = await coordinator._lookup_routes([{"hex": "abc", "flight": "BA123", "latitude": 51.0, "longitude": -0.1}])

    assert routes["BA123"]["origin_icao"] == "EGLL"
    assert routes["BA123"]["destination_icao"] == "KLAX"
    assert routes["BA123"]["route_string"] == "LHR - LAX"


async def test_lookup_routes_adsbdb_fallback(hass, aioclient_mock) -> None:
    """_lookup_routes falls back to adsbdb single lookup when bulk is empty."""
    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": True, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    with patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock):
        coordinator = ADSBDataUpdateCoordinator(hass, entry)

    # adsb.im returns no route data
    aioclient_mock.post("http://adsb.im/api/0/routeset", json=[])
    # adsbdb fills in the missing route
    aioclient_mock.get(
        "https://api.adsbdb.com/v0/callsign/BA123",
        json={
            "response": {
                "flightroute": {
                    "origin": {"icao_code": "EGLL", "iata_code": "LHR"},
                    "destination": {"icao_code": "KLAX", "iata_code": "LAX"},
                }
            }
        },
    )

    routes = await coordinator._lookup_routes([{"hex": "abc", "flight": "BA123", "latitude": 51.0, "longitude": -0.1}])

    assert routes["BA123"]["origin_icao"] == "EGLL"
    assert routes["BA123"]["destination_icao"] == "KLAX"


async def test_lookup_routes_adsbdb_unknown_caches(hass, aioclient_mock) -> None:
    """_lookup_routes caches an Unknown route from adsbdb unknown responses."""
    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": True, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    with patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock):
        coordinator = ADSBDataUpdateCoordinator(hass, entry)

    aioclient_mock.post("http://adsb.im/api/0/routeset", json=[])
    aioclient_mock.get(
        "https://api.adsbdb.com/v0/callsign/NOSUCH",
        json={"response": "unknown callsign"},
    )

    routes = await coordinator._lookup_routes([{"hex": "abc", "flight": "NOSUCH", "latitude": 0.0, "longitude": 0.0}])

    assert routes["NOSUCH"]["origin_icao"] == "Unknown"
    assert routes["NOSUCH"]["route_string"] == "Unknown"
    # A second lookup should use the cache without another HTTP request
    aioclient_mock.clear_requests()
    routes2 = await coordinator._lookup_routes([{"hex": "abc", "flight": "NOSUCH", "latitude": 0.0, "longitude": 0.0}])
    assert routes2["NOSUCH"]["origin_icao"] == "Unknown"


async def test_lookup_routes_bulk_403_backoff_uses_adsbdb(hass, aioclient_mock) -> None:
    """A 403 from adsb.im bulk triggers backoff and adsbdb fallback."""
    entry = MockConfigEntry(
        domain="adsb_nearby",
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": True, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    with patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock):
        coordinator = ADSBDataUpdateCoordinator(hass, entry)

    aioclient_mock.post("http://adsb.im/api/0/routeset", status=403)
    aioclient_mock.get(
        "https://api.adsbdb.com/v0/callsign/BA456",
        json={
            "response": {
                "flightroute": {
                    "origin": {"icao_code": "KJFK", "iata_code": "JFK"},
                    "destination": {"icao_code": "EGLL", "iata_code": "LHR"},
                }
            }
        },
    )

    routes = await coordinator._lookup_routes([{"hex": "def", "flight": "BA456", "latitude": 40.7, "longitude": -74.0}])

    assert routes["BA456"]["origin_icao"] == "KJFK"
    assert routes["BA456"]["destination_icao"] == "EGLL"
    assert coordinator._route_bulk_backoff_until > asyncio.get_event_loop().time()


