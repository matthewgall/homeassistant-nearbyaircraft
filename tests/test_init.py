"""Tests for ADSB Nearby Aircraft setup/unload lifecycle."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adsb_nearby import async_reload_entry, async_setup_entry, async_unload_entry
from custom_components.adsb_nearby.const import DOMAIN
from custom_components.adsb_nearby.coordinator import ADSBDataUpdateCoordinator


@pytest.fixture
def sample_data() -> dict:
    """Return sample coordinator data."""
    return {
        "aircraft": [{"hex": "abc"}],
        "aircraft_count": 1,
        "total_messages": 100,
        "radius_km": 50.0,
        "home_latitude": 51.47,
        "home_longitude": -0.46,
        "last_update": 1_700_000_000.0,
    }


async def test_async_setup_entry_loads_platforms(hass, sample_data) -> None:
    """Setting up the entry creates a coordinator and forwards to platforms."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)

    with (
        patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock),
        patch.object(
            ADSBDataUpdateCoordinator, "_async_update_data", new_callable=AsyncMock, return_value=sample_data
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock) as mock_forward,
    ):
        assert await async_setup_entry(hass, entry) is True

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    await coordinator.async_shutdown()

    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
    assert "coordinator" in hass.data[DOMAIN][entry.entry_id]
    mock_forward.assert_awaited_once()


async def test_async_unload_entry(hass, sample_data) -> None:
    """Unloading the entry removes stored coordinator data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)

    with (
        patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock),
        patch.object(
            ADSBDataUpdateCoordinator, "_async_update_data", new_callable=AsyncMock, return_value=sample_data
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock),
    ):
        await async_setup_entry(hass, entry)

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    await coordinator.async_shutdown()

    with patch.object(hass.config_entries, "async_unload_platforms", new_callable=AsyncMock, return_value=True):
        assert await async_unload_entry(hass, entry) is True

    assert entry.entry_id not in hass.data[DOMAIN]


async def test_async_reload_entry(hass, sample_data) -> None:
    """Reloading the entry re-creates the coordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)

    with (
        patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock),
        patch.object(
            ADSBDataUpdateCoordinator, "_async_update_data", new_callable=AsyncMock, return_value=sample_data
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock),
    ):
        await async_setup_entry(hass, entry)
        old_coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await old_coordinator.async_shutdown()

    with (
        patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock),
        patch.object(
            ADSBDataUpdateCoordinator, "_async_update_data", new_callable=AsyncMock, return_value=sample_data
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock),
    ):
        await async_reload_entry(hass, entry)

    new_coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    await new_coordinator.async_shutdown()

    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
