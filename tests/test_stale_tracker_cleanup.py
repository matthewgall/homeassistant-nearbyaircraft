"""Tests for ADSB Nearby Aircraft stale tracker cleanup."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adsb_nearby import async_setup_entry
from custom_components.adsb_nearby.const import DOMAIN
from custom_components.adsb_nearby.coordinator import ADSBDataUpdateCoordinator


async def test_stale_tracker_cleanup_removes_gone_aircraft(hass) -> None:
    """Stale aircraft device tracker entities are removed when aircraft leave range."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"source_type": "adsb_lol", "radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0},
    )
    entry.add_to_hass(hass)

    sample_data = {
        "aircraft": [{"hex": "ABC123"}],
        "aircraft_count": 1,
        "total_messages": 1,
        "radius_km": 50.0,
        "home_latitude": 51.0,
        "home_longitude": -0.1,
        "last_update": 1_700_000_000.0,
    }

    with (
        patch.object(ADSBDataUpdateCoordinator, "_async_load_databases", new_callable=AsyncMock),
        patch.object(
            ADSBDataUpdateCoordinator, "_async_update_data", new_callable=AsyncMock, return_value=sample_data
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock),
    ):
        await async_setup_entry(hass, entry)

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator._tracker_hexes.add("ABC123")

    fake_entity = MagicMock()
    fake_entity.domain = "device_tracker"
    fake_entity.unique_id = f"{entry.entry_id}_tracker_ABC123"
    fake_entity.entity_id = "device_tracker.adsb_aircraft_abc123"

    registry = MagicMock()
    registry.async_remove = MagicMock()

    with patch.object(er, "async_get", return_value=registry), \
         patch.object(er, "async_entries_for_config_entry", return_value=[fake_entity]):
        coordinator.data = {"aircraft": []}
        coordinator.async_set_updated_data(coordinator.data)

    registry.async_remove.assert_called_once_with("device_tracker.adsb_aircraft_abc123")
    assert "ABC123" not in coordinator._tracker_hexes
    await coordinator.async_shutdown()
