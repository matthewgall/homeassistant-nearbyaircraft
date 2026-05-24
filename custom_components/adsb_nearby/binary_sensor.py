"""Binary sensors for ADSB Nearby Aircraft."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ADSBDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

EMERGENCY_SQUAWKS = {"7700", "7600", "7500"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ADSB binary sensors from config entry."""
    coordinator: ADSBDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities = [
        ADSBAircraftNearbyBinarySensor(coordinator, config_entry),
        ADSBEmergencyAircraftBinarySensor(coordinator, config_entry),
    ]

    async_add_entities(entities)


class ADSBBinarySensorBase(CoordinatorEntity, BinarySensorEntity):
    """Base class for ADSB binary sensors."""

    def __init__(
        self,
        coordinator: ADSBDataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.sensor_type = sensor_type

        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"ADSB Nearby ({coordinator.url})",
            manufacturer="Matthew Gall",
            model="Aircraft Tracker",
            configuration_url=coordinator.url,
        )


class ADSBAircraftNearbyBinarySensor(ADSBBinarySensorBase):
    """Binary sensor indicating aircraft are in range."""

    def __init__(
        self,
        coordinator: ADSBDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize aircraft nearby sensor."""
        super().__init__(coordinator, config_entry, "aircraft_nearby")
        self._attr_name = "Aircraft Nearby"
        self._attr_icon = "mdi:airplane-marker"
        self._attr_device_class = None

    @property
    def is_on(self) -> bool:
        """Return True if aircraft are in range."""
        if not self.coordinator.data:
            return False
        return self.coordinator.data.get("aircraft_count", 0) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {"status": "No data"}

        return {
            "aircraft_count": self.coordinator.data.get("aircraft_count", 0),
            "radius_km": round(self.coordinator.data.get("radius_km", 0), 1),
        }


class ADSBEmergencyAircraftBinarySensor(ADSBBinarySensorBase):
    """Binary sensor indicating an emergency aircraft is in range."""

    def __init__(
        self,
        coordinator: ADSBDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize emergency aircraft sensor."""
        super().__init__(coordinator, config_entry, "emergency_aircraft")
        self._attr_name = "Emergency Aircraft"
        self._attr_icon = "mdi:alert-octagon"
        self._attr_device_class = "safety"

    @property
    def is_on(self) -> bool:
        """Return True if an emergency aircraft is in range."""
        if not self.coordinator.data:
            return False

        aircraft_list = self.coordinator.data.get("aircraft", [])
        for plane in aircraft_list:
            squawk = str(plane.get("squawk", "")).strip()
            if squawk in EMERGENCY_SQUAWKS:
                return True
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return emergency aircraft details."""
        if not self.coordinator.data:
            return {"status": "No data"}

        emergencies = []
        for plane in self.coordinator.data.get("aircraft", []):
            squawk = str(plane.get("squawk", "")).strip()
            if squawk in EMERGENCY_SQUAWKS:
                emergencies.append({
                    "flight": plane.get("flight") or plane.get("hex", "Unknown"),
                    "squawk": squawk,
                    "distance": plane.get("distance_display"),
                    "altitude_ft": plane.get("altitude_ft"),
                    "latitude": plane.get("latitude"),
                    "longitude": plane.get("longitude"),
                })

        return {
            "emergency_count": len(emergencies),
            "emergencies": emergencies,
        }
