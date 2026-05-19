"""ADSB Nearby Aircraft sensors."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_CLOSEST_AIRCRAFT, SENSOR_AIRCRAFT_COUNT, SENSOR_NEAREST_AIRCRAFT
from .coordinator import ADSBDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ADSB sensors from config entry."""
    coordinator: ADSBDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities = [
        ADSBClosestAircraftSensor(coordinator, config_entry),
        ADSBAircraftCountSensor(coordinator, config_entry),
        ADSBNearestAircraftSensor(coordinator, config_entry),
    ]

    async_add_entities(entities)


class ADSBSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for ADSB sensors."""

    def __init__(
        self,
        coordinator: ADSBDataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.sensor_type = sensor_type

        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"ADSB Nearby ({coordinator.url})",
            manufacturer="ADSB Nearby",
            model="Aircraft Tracker",
            configuration_url=coordinator.url,
        )


class ADSBClosestAircraftSensor(ADSBSensorBase):
    """Sensor for closest aircraft details."""

    def __init__(
        self,
        coordinator: ADSBDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize closest aircraft sensor."""
        super().__init__(coordinator, config_entry, SENSOR_CLOSEST_AIRCRAFT)
        self._attr_name = "Closest Aircraft"
        self._attr_icon = "mdi:airplane-marker"

    @property
    def native_value(self) -> str | None:
        """Return the closest aircraft identifier."""
        aircraft = self._get_closest_aircraft()
        if not aircraft:
            return "No aircraft"

        if aircraft.get("flight"):
            return aircraft["flight"]
        elif aircraft.get("tail"):
            return aircraft["tail"]
        else:
            return aircraft.get("hex", "Unknown")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return closest aircraft details as attributes."""
        aircraft = self._get_closest_aircraft()
        if not aircraft:
            return {"status": "No aircraft detected"}

        return {k: v for k, v in aircraft.items() if v is not None}

    def _get_closest_aircraft(self) -> dict[str, Any] | None:
        """Get the closest aircraft from coordinator data."""
        if not self.coordinator.data or not self.coordinator.data.get("aircraft"):
            return None

        aircraft_list = self.coordinator.data["aircraft"]
        return aircraft_list[0] if aircraft_list else None


class ADSBAircraftCountSensor(ADSBSensorBase):
    """Sensor for total aircraft count."""

    def __init__(
        self,
        coordinator: ADSBDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize aircraft count sensor."""
        super().__init__(coordinator, config_entry, SENSOR_AIRCRAFT_COUNT)
        self._attr_name = "Aircraft in Range"
        self._attr_icon = "mdi:airplane"
        self._attr_native_unit_of_measurement = "aircraft"

    @property
    def native_value(self) -> int | None:
        """Return the number of aircraft in range."""
        if not self.coordinator.data:
            return 0

        return self.coordinator.data.get("aircraft_count", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {"status": "No data"}

        return {
            "total_messages": self.coordinator.data.get("total_messages", 0),
            "last_update": self.coordinator.data.get("last_update"),
            "home_latitude": self.coordinator.data.get("home_latitude"),
            "home_longitude": self.coordinator.data.get("home_longitude"),
            "radius_km": round(self.coordinator.data.get("radius_km", 0), 1),
            "source_url": self.coordinator.url,
        }


class ADSBNearestAircraftSensor(ADSBSensorBase):
    """Sensor for top nearest aircraft."""

    def __init__(
        self,
        coordinator: ADSBDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize nearest aircraft sensor."""
        super().__init__(coordinator, config_entry, SENSOR_NEAREST_AIRCRAFT)
        self._attr_name = "Nearest Aircraft"
        self._attr_icon = "mdi:format-list-numbered"

    @property
    def native_value(self) -> str | None:
        """Return summary of nearest aircraft."""
        if not self.coordinator.data or not self.coordinator.data.get("aircraft"):
            return "No aircraft detected"

        aircraft_list = self.coordinator.data["aircraft"]
        count = len(aircraft_list)

        if count == 0:
            return "No aircraft detected"
        elif count == 1:
            return "1 aircraft detected"
        else:
            return f"{count} aircraft detected"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return nearest aircraft as attributes."""
        if not self.coordinator.data or not self.coordinator.data.get("aircraft"):
            return {"status": "No aircraft detected"}

        aircraft_list = self.coordinator.data["aircraft"]
        attributes = {}

        for i, aircraft in enumerate(aircraft_list[:10], 1):
            attributes[f"aircraft_{i}"] = {k: v for k, v in aircraft.items() if v is not None}

        return attributes
