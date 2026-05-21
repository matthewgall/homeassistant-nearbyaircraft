"""ADSB Nearby Aircraft integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import ADSBDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ADSB Nearby Aircraft from a config entry."""

    coordinator = ADSBDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Clean up stale device tracker entities after each update
    @callback
    def _async_remove_stale_trackers() -> None:
        """Remove device tracker entities for aircraft no longer in range."""
        if not coordinator.data:
            return

        current_hexes = {
            p.get("hex", "").strip().upper()
            for p in coordinator.data.get("aircraft", [])
        }

        registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)

        removed = 0
        for entity in entities:
            if entity.domain != "device_tracker":
                continue
            prefix = f"{entry.entry_id}_tracker_"
            if not entity.unique_id.startswith(prefix):
                continue

            hex_code = entity.unique_id[len(prefix):].upper()
            if hex_code not in current_hexes:
                registry.async_remove(entity.entity_id)
                coordinator._tracker_hexes.discard(hex_code)
                removed += 1

        if removed:
            _LOGGER.debug("Removed %d stale aircraft tracker(s)", removed)

    coordinator.async_add_listener(_async_remove_stale_trackers)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
