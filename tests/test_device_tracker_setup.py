"""Tests for ADSB Nearby Aircraft device tracker setup."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adsb_nearby.const import DOMAIN
from custom_components.adsb_nearby.coordinator import ADSBDataUpdateCoordinator
from custom_components.adsb_nearby.device_tracker import async_setup_entry


def sample_coordinator(hass, data=None):
    """Return a coordinator with optional data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    with patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock):
        coordinator = ADSBDataUpdateCoordinator(hass, entry)
    coordinator.data = data or {
        "aircraft": [
            {"hex": "ABC123", "lat": 51.0, "lon": -0.1, "flight": "TEST1"},
        ],
    }
    return coordinator


async def test_device_tracker_setup_adds_initial_trackers(hass) -> None:
    """async_setup_entry adds device trackers for current aircraft."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    coordinator = sample_coordinator(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    added = []
    def add_entities(entities, update_before_add=False):
        added.extend(entities)

    await async_setup_entry(hass, entry, add_entities)

    assert len(added) == 1
    assert added[0].hex_code == "ABC123"
    await coordinator.async_shutdown()


async def test_device_tracker_setup_no_aircraft(hass) -> None:
    """async_setup_entry does not crash when no aircraft are present."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    coordinator = sample_coordinator(hass, data={"aircraft": []})
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    added = []
    def add_entities(entities, update_before_add=False):
        added.extend(entities)

    await async_setup_entry(hass, entry, add_entities)

    assert added == []
    await coordinator.async_shutdown()


async def test_device_tracker_setup_registers_listener(hass) -> None:
    """async_setup_entry registers a coordinator update listener."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    coordinator = sample_coordinator(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    def add_entities(entities, update_before_add=False):
        pass

    unregister = MagicMock()
    with patch.object(coordinator, "async_add_listener", return_value=unregister) as mock_listener:
        await async_setup_entry(hass, entry, add_entities)

    mock_listener.assert_called_once()
    await coordinator.async_shutdown()
