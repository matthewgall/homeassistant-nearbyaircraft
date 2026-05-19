"""Device tracker for ADSB Nearby Aircraft."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ADSBDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ADSB device trackers from config entry."""
    coordinator: ADSBDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    @callback
    def _async_add_new_trackers() -> None:
        """Add device trackers for newly seen aircraft."""
        new_trackers = coordinator.get_new_device_trackers(config_entry)
        if new_trackers:
            async_add_entities(new_trackers)

    # Add initial trackers
    initial_trackers = coordinator.get_new_device_trackers(config_entry)
    if initial_trackers:
        async_add_entities(initial_trackers)

    # Listen for coordinator updates to add new trackers
    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_add_new_trackers)
    )


class ADSBAircraftDeviceTracker(CoordinatorEntity, TrackerEntity):
    """Device tracker for a single aircraft."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: ADSBDataUpdateCoordinator,
        config_entry: ConfigEntry,
        hex_code: str,
    ) -> None:
        """Initialize the aircraft tracker."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.hex_code = hex_code

        self._attr_unique_id = f"{config_entry.entry_id}_tracker_{hex_code}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"ADSB Nearby ({coordinator.url})",
            manufacturer="ADSB Nearby",
            model="Aircraft Tracker",
            configuration_url=coordinator.url,
        )

        # Store last known position so entity stays on map when aircraft leaves radius
        self._last_latitude: float | None = None
        self._last_longitude: float | None = None
        self._last_name: str = f"Aircraft {hex_code}"

    async def async_added_to_hass(self) -> None:
        """Register entity for cleanup tracking."""
        await super().async_added_to_hass()
        entry_data = self.hass.data[DOMAIN][self.config_entry.entry_id]
        entry_data["device_trackers"][self.hex_code.upper()] = self
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Unregister entity from cleanup tracking."""
        entry_data = self.hass.data[DOMAIN][self.config_entry.entry_id]
        entry_data["device_trackers"].pop(self.hex_code.upper(), None)
        await super().async_will_remove_from_hass()

    @property
    def name(self) -> str | None:
        """Return the name of the aircraft."""
        plane = self._get_aircraft_data()
        if not plane:
            return self._last_name
        flight = plane.get("flight")
        if flight:
            self._last_name = f"{flight} ({self.hex_code})"
            return self._last_name
        tail = plane.get("tail")
        if tail:
            self._last_name = f"{tail} ({self.hex_code})"
            return self._last_name
        self._last_name = f"Aircraft {self.hex_code}"
        return self._last_name

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return latitude."""
        plane = self._get_aircraft_data()
        if plane:
            lat = plane.get("latitude")
            if lat is not None:
                self._last_latitude = float(lat)
                return self._last_latitude
        return self._last_latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude."""
        plane = self._get_aircraft_data()
        if plane:
            lon = plane.get("longitude")
            if lon is not None:
                self._last_longitude = float(lon)
                return self._last_longitude
        return self._last_longitude

    @property
    def location_name(self) -> str | None:
        """Return the location name."""
        return None

    @property
    def available(self) -> bool:
        """Return True (entity persists with last known position)."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return aircraft details."""
        plane = self._get_aircraft_data()
        if not plane:
            return None

        attrs: dict[str, Any] = {}
        for key in (
            "flight", "tail", "aircraft_type", "aircraft_description",
            "operator", "operator_country", "weight_class",
            "altitude_ft", "speed_kts", "heading",
            "distance_km", "distance_display",
            "squawk", "emergency", "route_string",
            "origin_icao", "origin_iata",
            "destination_icao", "destination_iata",
        ):
            val = plane.get(key)
            if val is not None and val != "Unknown":
                attrs[key] = val
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    def _get_aircraft_data(self) -> dict[str, Any] | None:
        """Get this aircraft from coordinator data."""
        if not self.coordinator.data:
            return None
        for plane in self.coordinator.data.get("aircraft", []):
            if plane.get("hex", "").upper() == self.hex_code.upper():
                return plane
        return None
