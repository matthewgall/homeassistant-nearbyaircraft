"""Config flow for ADSB Nearby Aircraft integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_SOURCE_TYPE,
    CONF_HOST,
    CONF_PORT,
    CONF_SCHEME,
    CONF_PATH,
    CONF_RADIUS,
    CONF_UPDATE_INTERVAL,
    CONF_VERIFY_SSL,
    CONF_API_KEY,
    CONF_ENABLE_ROUTES,
    SOURCE_TYPE_LOCAL,
    SOURCE_TYPE_ADSB_LOL,
    SOURCE_TYPE_ADSBEXCHANGE,
    DEFAULT_SOURCE_TYPE,
    DEFAULT_SCHEME,
    DEFAULT_PORT,
    DEFAULT_PATH,
    DEFAULT_RADIUS,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DEFAULT_ENABLE_ROUTES,
    ADSB_LOL_API_SCHEME,
    ADSB_LOL_API_HOST,
    ADSB_LOL_API_PORT,
    ADSB_LOL_API_PATH_TEMPLATE,
    ADSBEXCHANGE_API_SCHEME,
    ADSBEXCHANGE_API_HOST,
    ADSBEXCHANGE_API_PORT,
    ADSBEXCHANGE_API_PATH_TEMPLATE,
    NM_TO_KM,
)

_LOGGER = logging.getLogger(__name__)


def _get_length_unit(hass: HomeAssistant | None) -> str:
    """Safely get the length unit string from Home Assistant."""
    if hass is None:
        return ""
    # Modern HA (2024+): unit_system is a string like "metric" or "imperial"
    unit_system = getattr(hass.config, "unit_system", None)
    if isinstance(unit_system, str):
        return "km" if unit_system == "metric" else "mi"
    # Older HA: units object with .length (enum) or .length_unit (string)
    try:
        units = hass.config.units
        length = getattr(units, "length", None)
        if length is not None:
            length_str = str(length).lower()
            if "kilometer" in length_str or length_str == "km":
                return "km"
            if "mile" in length_str:
                return "mi"
        length_unit = getattr(units, "length_unit", None)
        if length_unit is not None:
            return length_unit
    except Exception:
        pass
    return ""


def _source_type_name(source_type: str) -> str:
    """Return human-readable source type name."""
    return {
        SOURCE_TYPE_LOCAL: "Local dump1090 / tar1090",
        SOURCE_TYPE_ADSB_LOL: "adsb.lol (free, global)",
        SOURCE_TYPE_ADSBEXCHANGE: "ADS-B Exchange (requires API key)",
    }.get(source_type, source_type)


def _build_local_url(data: dict[str, Any]) -> str:
    """Build the aircraft.json URL from config components."""
    scheme = data.get(CONF_SCHEME, DEFAULT_SCHEME)
    host = data[CONF_HOST].strip()
    port = data.get(CONF_PORT, DEFAULT_PORT)
    path = data.get(CONF_PATH, DEFAULT_PATH).strip()

    if not path.startswith("/"):
        path = "/" + path

    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        return f"{scheme}://{host}{path}"
    return f"{scheme}://{host}:{port}{path}"


def _build_adsb_lol_url(hass: HomeAssistant, radius: int, is_metric: bool) -> str:
    """Build the adsb.lol API URL from Home Assistant location."""
    home_lat = hass.config.latitude
    home_lon = hass.config.longitude
    radius_km = radius if is_metric else radius * 1.60934
    radius_nm = radius_km / NM_TO_KM

    path = ADSB_LOL_API_PATH_TEMPLATE.format(
        lat=home_lat,
        lon=home_lon,
        dist=f"{radius_nm:.0f}",
    )
    return f"{ADSB_LOL_API_SCHEME}://{ADSB_LOL_API_HOST}{path}"


def _build_adsbexchange_url(hass: HomeAssistant, radius: int, is_metric: bool) -> str:
    """Build the ADS-B Exchange API URL from Home Assistant location."""
    home_lat = hass.config.latitude
    home_lon = hass.config.longitude
    radius_km = radius if is_metric else radius * 1.60934
    radius_nm = radius_km / NM_TO_KM

    path = ADSBEXCHANGE_API_PATH_TEMPLATE.format(
        lat=home_lat,
        lon=home_lon,
        dist=f"{radius_nm:.0f}",
    )
    return f"{ADSBEXCHANGE_API_SCHEME}://{ADSBEXCHANGE_API_HOST}{path}"


def _get_max_radius(hass: HomeAssistant | None) -> int:
    """Get max radius based on Home Assistant unit system."""
    radius_unit = "km" if _get_length_unit(hass) == "km" else "miles"
    return 500 if radius_unit == "km" else 310


async def _validate_local(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate local ADSB source."""
    url = _build_local_url(data)
    verify_ssl = data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)

    try:
        async with asyncio.timeout(10):
            async with session.get(url) as response:
                if response.status != 200:
                    raise InvalidHost(f"HTTP {response.status}")
                json_data = await response.json()
                if "aircraft" not in json_data:
                    raise InvalidADSBData("Missing aircraft data in response")
                if not isinstance(json_data["aircraft"], list):
                    raise InvalidADSBData("Aircraft data is not a list")
                return {
                    "title": f"ADSB Nearby ({data[CONF_HOST]})",
                    "aircraft_count": len(json_data["aircraft"]),
                    "last_update": json_data.get("now"),
                }
    except asyncio.TimeoutError as err:
        raise ConnectionTimeout(f"Timeout connecting to {url}") from err
    except aiohttp.ClientConnectorError as err:
        raise CannotConnect(f"Cannot connect to {url}: {err}") from err
    except aiohttp.ClientError as err:
        raise CannotConnect(f"Connection error: {err}") from err


async def _validate_adsb_lol(
    hass: HomeAssistant, radius: int, update_interval: int
) -> dict[str, Any]:
    """Validate adsb.lol API."""
    is_metric = _get_length_unit(hass) == "km"
    url = _build_adsb_lol_url(hass, radius, is_metric)
    session = async_get_clientsession(hass, verify_ssl=True)

    try:
        async with asyncio.timeout(10):
            async with session.get(url) as response:
                if response.status != 200:
                    raise InvalidHost(f"HTTP {response.status}")
                json_data = await response.json()
                if "ac" not in json_data:
                    raise InvalidADSBData("Missing aircraft data in response")
                if not isinstance(json_data["ac"], list):
                    raise InvalidADSBData("Aircraft data is not a list")
                return {
                    "title": "ADSB Nearby (adsb.lol)",
                    "aircraft_count": json_data.get("total", 0),
                    "last_update": json_data.get("now"),
                }
    except asyncio.TimeoutError as err:
        raise ConnectionTimeout(f"Timeout connecting to adsb.lol") from err
    except aiohttp.ClientError as err:
        raise CannotConnect(f"Connection error: {err}") from err


async def _validate_adsbexchange(
    hass: HomeAssistant,
    api_key: str,
    radius: int,
    update_interval: int,
) -> dict[str, Any]:
    """Validate ADS-B Exchange API."""
    is_metric = _get_length_unit(hass) == "km"
    url = _build_adsbexchange_url(hass, radius, is_metric)
    session = async_get_clientsession(hass, verify_ssl=True)

    headers = {"api-auth": api_key}

    try:
        async with asyncio.timeout(10):
            async with session.get(url, headers=headers) as response:
                if response.status == 401:
                    raise InvalidAPIKey("Invalid API key")
                if response.status != 200:
                    raise InvalidHost(f"HTTP {response.status}")
                json_data = await response.json()
                aircraft_key = "ac" if "ac" in json_data else "aircraft"
                if aircraft_key not in json_data:
                    raise InvalidADSBData("Missing aircraft data in response")
                if not isinstance(json_data[aircraft_key], list):
                    raise InvalidADSBData("Aircraft data is not a list")
                return {
                    "title": "ADSB Nearby (ADS-B Exchange)",
                    "aircraft_count": len(json_data[aircraft_key]),
                    "last_update": json_data.get("now"),
                }
    except asyncio.TimeoutError as err:
        raise ConnectionTimeout(f"Timeout connecting to ADS-B Exchange") from err
    except aiohttp.ClientError as err:
        raise CannotConnect(f"Connection error: {err}") from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ADSB Nearby Aircraft."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - source type selection."""
        if user_input is not None:
            self._source_type = user_input[CONF_SOURCE_TYPE]
            return await self.async_step_config()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SOURCE_TYPE, default=DEFAULT_SOURCE_TYPE
                ): vol.In(
                    {
                        SOURCE_TYPE_LOCAL: _source_type_name(SOURCE_TYPE_LOCAL),
                        SOURCE_TYPE_ADSB_LOL: _source_type_name(SOURCE_TYPE_ADSB_LOL),
                        SOURCE_TYPE_ADSBEXCHANGE: _source_type_name(
                            SOURCE_TYPE_ADSBEXCHANGE
                        ),
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    async def async_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the configuration step based on source type."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge with source_type from previous step
            full_data = {CONF_SOURCE_TYPE: self._source_type, **user_input}

            try:
                if self._source_type == SOURCE_TYPE_LOCAL:
                    info = await _validate_local(self.hass, full_data)
                    unique_id = f"{full_data.get(CONF_SCHEME, DEFAULT_SCHEME)}://{full_data[CONF_HOST]}:{full_data.get(CONF_PORT, DEFAULT_PORT)}"
                elif self._source_type == SOURCE_TYPE_ADSB_LOL:
                    info = await _validate_adsb_lol(
                        self.hass,
                        full_data.get(CONF_RADIUS, DEFAULT_RADIUS),
                        full_data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                    )
                    unique_id = f"adsb_lol_{self.hass.config.latitude}_{self.hass.config.longitude}"
                elif self._source_type == SOURCE_TYPE_ADSBEXCHANGE:
                    info = await _validate_adsbexchange(
                        self.hass,
                        full_data[CONF_API_KEY],
                        full_data.get(CONF_RADIUS, DEFAULT_RADIUS),
                        full_data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                    )
                    unique_id = f"adsbexchange_{self.hass.config.latitude}_{self.hass.config.longitude}"
                else:
                    raise CannotConnect(f"Unknown source type: {self._source_type}")

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=full_data,
                )

            except ConnectionRefused:
                errors["base"] = "connection_refused"
            except ConnectionTimeout:
                errors["base"] = "timeout"
            except CannotResolve:
                if self._source_type == SOURCE_TYPE_LOCAL:
                    errors[CONF_HOST] = "cannot_resolve"
                else:
                    errors["base"] = "cannot_resolve"
            except SSLValidationError:
                errors["base"] = "ssl_error"
            except InvalidAPIKey:
                errors[CONF_API_KEY] = "invalid_api_key"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["base"] = "invalid_host"
            except InvalidADSBData:
                errors["base"] = "invalid_adsb_data"
            except Exception:
                _LOGGER.exception("Unexpected exception during validation")
                errors["base"] = "unknown"

        # Build schema based on source type
        schema_fields = {}

        if self._source_type == SOURCE_TYPE_LOCAL:
            schema_fields[vol.Required(CONF_HOST)] = str
            schema_fields[
                vol.Optional(CONF_SCHEME, default=DEFAULT_SCHEME)
            ] = vol.In({"http": "HTTP", "https": "HTTPS"})
            schema_fields[
                vol.Optional(CONF_PORT, default=DEFAULT_PORT)
            ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))
            schema_fields[
                vol.Optional(CONF_PATH, default=DEFAULT_PATH)
            ] = str
            schema_fields[
                vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL)
            ] = bool
        elif self._source_type == SOURCE_TYPE_ADSBEXCHANGE:
            schema_fields[vol.Required(CONF_API_KEY)] = str

        # Common fields for all source types
        max_radius = _get_max_radius(self.hass)
        schema_fields[
            vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS)
        ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=max_radius))
        schema_fields[
            vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL)
        ] = vol.All(vol.Coerce(int), vol.Range(min=5, max=300))
        schema_fields[
            vol.Optional(CONF_ENABLE_ROUTES, default=DEFAULT_ENABLE_ROUTES)
        ] = bool

        # Build the actual voluptuous schema
        vol_schema = {}
        for key, value in schema_fields.items():
            vol_schema[key] = value

        return self.async_show_form(
            step_id="config",
            data_schema=vol.Schema(vol_schema),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for ADSB Nearby Aircraft."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial options step."""
        if user_input is not None:
            self._source_type = user_input[CONF_SOURCE_TYPE]
            return await self.async_step_config()

        current_source = self._entry.data.get(
            CONF_SOURCE_TYPE, DEFAULT_SOURCE_TYPE
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_TYPE, default=current_source): vol.In(
                    {
                        SOURCE_TYPE_LOCAL: _source_type_name(SOURCE_TYPE_LOCAL),
                        SOURCE_TYPE_ADSB_LOL: _source_type_name(SOURCE_TYPE_ADSB_LOL),
                        SOURCE_TYPE_ADSBEXCHANGE: _source_type_name(
                            SOURCE_TYPE_ADSBEXCHANGE
                        ),
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )

    async def async_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the configuration options step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Include source_type selected in step_init so it is persisted
            source_type = getattr(
                self, "_source_type",
                self._entry.data.get(CONF_SOURCE_TYPE, DEFAULT_SOURCE_TYPE)
            )
            user_input[CONF_SOURCE_TYPE] = source_type
            return self.async_create_entry(title="", data=user_input)

        current_data = self._entry.data
        current_options = self._entry.options
        source_type = getattr(
            self, "_source_type", current_data.get(CONF_SOURCE_TYPE, DEFAULT_SOURCE_TYPE)
        )

        # Build schema based on source type
        schema_fields = {}

        if source_type == SOURCE_TYPE_LOCAL:
            current_host = current_options.get(
                CONF_HOST, current_data.get(CONF_HOST, "")
            )
            current_scheme = current_options.get(
                CONF_SCHEME, current_data.get(CONF_SCHEME, DEFAULT_SCHEME)
            )
            current_port = current_options.get(
                CONF_PORT, current_data.get(CONF_PORT, DEFAULT_PORT)
            )
            current_path = current_options.get(
                CONF_PATH, current_data.get(CONF_PATH, DEFAULT_PATH)
            )
            current_verify_ssl = current_options.get(
                CONF_VERIFY_SSL, current_data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
            )

            schema_fields[vol.Optional(CONF_HOST, default=current_host)] = str
            schema_fields[
                vol.Optional(CONF_SCHEME, default=current_scheme)
            ] = vol.In({"http": "HTTP", "https": "HTTPS"})
            schema_fields[
                vol.Optional(CONF_PORT, default=current_port)
            ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))
            schema_fields[
                vol.Optional(CONF_PATH, default=current_path)
            ] = str
            schema_fields[
                vol.Optional(CONF_VERIFY_SSL, default=current_verify_ssl)
            ] = bool
        elif source_type == SOURCE_TYPE_ADSBEXCHANGE:
            current_api_key = current_options.get(
                CONF_API_KEY, current_data.get(CONF_API_KEY, "")
            )
            schema_fields[vol.Optional(CONF_API_KEY, default=current_api_key)] = str

        # Common fields
        current_radius = current_options.get(
            CONF_RADIUS, current_data.get(CONF_RADIUS, DEFAULT_RADIUS)
        )
        current_interval = current_options.get(
            CONF_UPDATE_INTERVAL,
            current_data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )

        radius_unit = "km" if _get_length_unit(self.hass) == "km" else "miles"
        max_radius = 500 if radius_unit == "km" else 310

        schema_fields[
            vol.Optional(CONF_RADIUS, default=current_radius)
        ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=max_radius))
        schema_fields[
            vol.Optional(CONF_UPDATE_INTERVAL, default=current_interval)
        ] = vol.All(vol.Coerce(int), vol.Range(min=5, max=300))

        current_enable_routes = current_options.get(
            CONF_ENABLE_ROUTES,
            current_data.get(CONF_ENABLE_ROUTES, DEFAULT_ENABLE_ROUTES),
        )
        schema_fields[
            vol.Optional(CONF_ENABLE_ROUTES, default=current_enable_routes)
        ] = bool

        vol_schema = {}
        for key, value in schema_fields.items():
            vol_schema[key] = value

        return self.async_show_form(
            step_id="config",
            data_schema=vol.Schema(vol_schema),
            errors=errors,
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class ConnectionRefused(Exception):
    """Error to indicate the connection was actively refused."""


class ConnectionTimeout(Exception):
    """Error to indicate the connection timed out."""


class CannotResolve(Exception):
    """Error to indicate hostname resolution failed."""


class InvalidHost(Exception):
    """Error to indicate there is an invalid response."""


class InvalidADSBData(Exception):
    """Error to indicate invalid ADSB data format."""


class SSLValidationError(Exception):
    """Error to indicate SSL certificate validation failed."""


class InvalidAPIKey(Exception):
    """Error to indicate an invalid API key."""
