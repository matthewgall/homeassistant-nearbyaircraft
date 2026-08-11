"""Tests for ADSB Nearby Aircraft platform setup helpers."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adsb_nearby.binary_sensor import async_setup_entry as bs_setup
from custom_components.adsb_nearby.const import DOMAIN
from custom_components.adsb_nearby.coordinator import ADSBDataUpdateCoordinator
from custom_components.adsb_nearby.sensor import async_setup_entry as sensor_setup


def make_coordinator(hass):
    """Return a coordinator with sample data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)
    with patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock):
        coordinator = ADSBDataUpdateCoordinator(hass, entry)
    coordinator.data = {
        "aircraft": [{"hex": "abc"}],
        "aircraft_count": 1,
        "radius_km": 50.0,
    }
    return coordinator


async def test_sensor_setup_creates_entities(hass) -> None:
    """Sensor setup creates the three expected sensor entities."""
    entry = MockConfigEntry(domain=DOMAIN, data={"source_type": "adsb_lol"})
    entry.add_to_hass(hass)
    coordinator = make_coordinator(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    added = []
    def add_entities(entities):
        added.extend(entities)

    await sensor_setup(hass, entry, add_entities)
    assert len(added) == 3


async def test_binary_sensor_setup_creates_entities(hass) -> None:
    """Binary sensor setup creates the two expected binary sensor entities."""
    entry = MockConfigEntry(domain=DOMAIN, data={"source_type": "adsb_lol"})
    entry.add_to_hass(hass)
    coordinator = make_coordinator(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    added = []
    def add_entities(entities):
        added.extend(entities)

    await bs_setup(hass, entry, add_entities)
    assert len(added) == 2
