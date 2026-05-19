"""Data update coordinator for ADSB Nearby Aircraft."""
from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

import re

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
    CONF_MIN_ALTITUDE,
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
    DEFAULT_TIMEOUT,
    DEFAULT_ENABLE_ROUTES,
    DEFAULT_MIN_ALTITUDE,
    MAX_RETRIES,
    RETRY_BACKOFF,
    ADSB_LOL_API_SCHEME,
    ADSB_LOL_API_HOST,
    ADSB_LOL_API_PATH_TEMPLATE,
    ADSBEXCHANGE_API_SCHEME,
    ADSBEXCHANGE_API_HOST,
    ADSBEXCHANGE_API_PATH_TEMPLATE,
    NM_TO_KM,
    OPERATORS_DB_URL,
    TYPES_DB_URL,
    WEIGHT_CLASS_MAP,
    ROUTE_API_URL,
    ROUTE_CACHE_TTL,
)

_LOGGER = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in km."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


class ADSBDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching ADSB aircraft data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize coordinator."""
        self.config_entry = config_entry

        # Aircraft metadata databases (loaded on first update)
        self._operators_db: dict[str, list[str]] | None = None
        self._types_db: dict[str, list[str]] | None = None
        self._db_loaded = False

        # Route cache: {callsign: {"route": {...}, "expires": timestamp}}
        self._route_cache: dict[str, dict[str, Any]] = {}

        # Track which hex codes already have device_tracker entities
        self._tracker_hexes: set[str] = set()

        update_interval = timedelta(
            seconds=self._get_config_value(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
            )
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    def _get_config_value(self, key: str, default: Any) -> Any:
        """Return a config value, preferring options over data."""
        return self.config_entry.options.get(
            key, self.config_entry.data.get(key, default)
        )

    @property
    def source_type(self) -> str:
        """Return the configured source type."""
        return self._get_config_value(CONF_SOURCE_TYPE, DEFAULT_SOURCE_TYPE)

    @property
    def radius(self) -> int:
        """Return the configured radius."""
        return self._get_config_value(CONF_RADIUS, DEFAULT_RADIUS)

    @property
    def enable_routes(self) -> bool:
        """Return whether route lookup is enabled."""
        return self._get_config_value(CONF_ENABLE_ROUTES, DEFAULT_ENABLE_ROUTES)

    @property
    def min_altitude(self) -> int:
        """Return the configured minimum altitude in feet."""
        return self._get_config_value(CONF_MIN_ALTITUDE, DEFAULT_MIN_ALTITUDE)

    @property
    def home_location(self) -> tuple[float, float]:
        """Return the Home Assistant configured home location."""
        return (self.hass.config.latitude, self.hass.config.longitude)

    @property
    def is_metric(self) -> bool:
        """Return True if Home Assistant uses metric units."""
        units = self.hass.config.units
        length_unit = getattr(units, "length_unit", getattr(units, "length", ""))
        return length_unit == "km"

    def _radius_km(self) -> float:
        """Return the configured radius in kilometres."""
        return self.radius if self.is_metric else self.radius * 1.60934

    def _radius_nm(self) -> float:
        """Return the configured radius in nautical miles."""
        return self._radius_km() / NM_TO_KM

    def _is_above_min_altitude(self, plane: dict[str, Any]) -> bool:
        """Check if aircraft is above the configured minimum altitude."""
        min_alt = self.min_altitude
        if min_alt <= 0:
            return True

        alt = plane.get("alt_baro")
        if alt is None:
            alt = plane.get("alt_geom")

        if alt is None:
            return True  # Keep aircraft with unknown altitude

        if alt == "ground":
            return False

        try:
            return float(alt) >= min_alt
        except (TypeError, ValueError):
            return True

    def convert_distance(self, km: float) -> float:
        """Convert km to the Home Assistant unit system."""
        if self.is_metric:
            return km
        return km / 1.60934

    def format_distance(self, km: float | None) -> str:
        """Format distance with appropriate unit."""
        if km is None:
            return "Unknown"
        if self.is_metric:
            return f"{km:.1f} km"
        return f"{km / 1.60934:.1f} mi"

    @property
    def url(self) -> str:
        """Construct and return the API URL based on source type."""
        if self.source_type == SOURCE_TYPE_LOCAL:
            scheme = self._get_config_value(CONF_SCHEME, DEFAULT_SCHEME)
            host = self._get_config_value(CONF_HOST, "").strip()
            port = self._get_config_value(CONF_PORT, DEFAULT_PORT)
            path = self._get_config_value(CONF_PATH, DEFAULT_PATH).strip()

            if not path.startswith("/"):
                path = "/" + path

            if (scheme == "http" and port == 80) or (
                scheme == "https" and port == 443
            ):
                return f"{scheme}://{host}{path}"
            return f"{scheme}://{host}:{port}{path}"

        elif self.source_type == SOURCE_TYPE_ADSB_LOL:
            home_lat, home_lon = self.home_location
            radius_nm = self._radius_nm()
            path = ADSB_LOL_API_PATH_TEMPLATE.format(
                lat=home_lat,
                lon=home_lon,
                dist=f"{radius_nm:.0f}",
            )
            return f"{ADSB_LOL_API_SCHEME}://{ADSB_LOL_API_HOST}{path}"

        elif self.source_type == SOURCE_TYPE_ADSBEXCHANGE:
            home_lat, home_lon = self.home_location
            radius_nm = self._radius_nm()
            path = ADSBEXCHANGE_API_PATH_TEMPLATE.format(
                lat=home_lat,
                lon=home_lon,
                dist=f"{radius_nm:.0f}",
            )
            return f"{ADSBEXCHANGE_API_SCHEME}://{ADSBEXCHANGE_API_HOST}{path}"

        return ""

    @property
    def _api_headers(self) -> dict[str, str]:
        """Return API headers for authenticated sources."""
        if self.source_type == SOURCE_TYPE_ADSBEXCHANGE:
            api_key = self._get_config_value(CONF_API_KEY, "")
            if api_key:
                return {"api-auth": api_key}
        return {}

    @property
    def _verify_ssl(self) -> bool:
        """Return whether to verify SSL."""
        if self.source_type == SOURCE_TYPE_LOCAL:
            return self._get_config_value(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        return True

    def _sanitize_url(self, url: str) -> str:
        """Sanitize URL for logging by removing coordinates."""
        sanitized = re.sub(r"/lat/[^/]+", "/lat/XXX", url)
        sanitized = re.sub(r"/lon/[^/]+", "/lon/XXX", sanitized)
        return sanitized

    async def _async_fetch_data(
        self, url: str, headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Fetch data from URL with retry logic and improved timeout handling."""
        session = async_get_clientsession(
            self.hass, verify_ssl=self._verify_ssl
        )
        sanitized_url = self._sanitize_url(url)
        request_headers = headers or {}

        last_error: Exception | None = None
        retry_delay: int | None = None

        for attempt in range(MAX_RETRIES + 1):
            retry_delay = None
            try:
                async with asyncio.timeout(DEFAULT_TIMEOUT):
                    async with session.get(
                        url, headers=request_headers
                    ) as response:
                        if response.status == 200:
                            return await response.json()

                        # Don't retry on client errors (4xx)
                        if 400 <= response.status < 500:
                            raise UpdateFailed(
                                f"Error fetching ADSB data: HTTP {response.status}"
                            )

                        # Retry on server errors (5xx)
                        last_error = aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                        )
                        _LOGGER.warning(
                            "Server error %d from %s (attempt %d/%d), "
                            "retrying in %ds",
                            response.status,
                            sanitized_url,
                            attempt + 1,
                            MAX_RETRIES + 1,
                            RETRY_BACKOFF[attempt],
                        )
                        retry_delay = RETRY_BACKOFF[attempt]

            except asyncio.TimeoutError as err:
                last_error = err
                if attempt < MAX_RETRIES:
                    _LOGGER.warning(
                        "Timeout fetching ADSB data from %s (attempt %d/%d), "
                        "retrying in %ds",
                        sanitized_url,
                        attempt + 1,
                        MAX_RETRIES + 1,
                        RETRY_BACKOFF[attempt],
                    )
                    retry_delay = RETRY_BACKOFF[attempt]
                else:
                    _LOGGER.error(
                        "Timeout fetching ADSB data from %s after %d attempts",
                        sanitized_url,
                        MAX_RETRIES + 1,
                    )
                    raise UpdateFailed(
                        f"Timeout fetching ADSB data from {sanitized_url}"
                    ) from err

            except aiohttp.ClientError as err:
                last_error = err
                if attempt < MAX_RETRIES:
                    _LOGGER.warning(
                        "Connection error from %s (attempt %d/%d): %s, "
                        "retrying in %ds",
                        sanitized_url,
                        attempt + 1,
                        MAX_RETRIES + 1,
                        err,
                        RETRY_BACKOFF[attempt],
                    )
                    retry_delay = RETRY_BACKOFF[attempt]
                else:
                    raise UpdateFailed(
                        f"Error fetching ADSB data from {sanitized_url}: {err}"
                    ) from err

            if retry_delay is not None:
                await asyncio.sleep(retry_delay)

        # All retries exhausted for server errors
        if last_error is not None:
            raise UpdateFailed(
                f"Error fetching ADSB data from {sanitized_url}: {last_error}"
            )

        raise UpdateFailed("Unexpected error in fetch retry logic")

    async def _async_load_databases(self) -> None:
        """Download and cache open aircraft metadata databases."""
        if self._db_loaded:
            return

        session = async_get_clientsession(self.hass, verify_ssl=True)

        async def _fetch_db(url: str, name: str) -> dict[str, Any]:
            """Fetch a single JSON database.

            Uses text() + json.loads() because GitHub raw serves JSON
            with Content-Type text/plain; charset=utf-8, which causes
            response.json() to raise ContentTypeError.
            """
            try:
                async with asyncio.timeout(30):
                    async with session.get(url) as response:
                        if response.status == 200:
                            text = await response.text()
                            data = json.loads(text)
                            _LOGGER.info(
                                "Loaded %s database: %d entries", name, len(data)
                            )
                            return data
                        _LOGGER.warning(
                            "Failed to load %s database: HTTP %d", name, response.status
                        )
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout loading %s database", name)
            except aiohttp.ClientError as err:
                _LOGGER.warning("Error loading %s database: %s", name, err)
            except json.JSONDecodeError as err:
                _LOGGER.warning("Failed to decode %s database JSON: %s", name, err)
            except Exception as err:
                _LOGGER.warning("Unexpected error loading %s database: %s", name, err)
            return {}

        # Fetch both databases concurrently
        operators_data, types_data = await asyncio.gather(
            _fetch_db(OPERATORS_DB_URL, "operators"),
            _fetch_db(TYPES_DB_URL, "types"),
        )

        self._operators_db = operators_data
        self._types_db = types_data
        self._db_loaded = True

    def _lookup_operator(self, flight: str | None) -> dict[str, str]:
        """Look up operator information from the operators database."""
        if not flight or not self._operators_db:
            return {}

        # ICAO operator code is the first 3 letters of the flight number
        operator_code = flight[:3].upper()
        operator_info = self._operators_db.get(operator_code)

        if operator_info and len(operator_info) >= 2:
            return {
                "operator": operator_info[0],
                "operator_country": operator_info[1] if len(operator_info) > 1 else "",
            }
        return {}

    def _lookup_type(self, aircraft_type: str | None) -> dict[str, str]:
        """Look up aircraft type description from the types database."""
        if not aircraft_type or not self._types_db:
            return {}

        type_info = self._types_db.get(aircraft_type.upper())

        if type_info and len(type_info) >= 1:
            result: dict[str, str] = {
                "aircraft_description": type_info[0],
            }
            if len(type_info) > 2:
                weight_code = type_info[2]
                result["weight_class"] = WEIGHT_CLASS_MAP.get(weight_code, weight_code)
            return result
        return {}

    def _get_cached_route(self, callsign: str) -> dict[str, Any] | None:
        """Return cached route if still valid."""
        entry = self._route_cache.get(callsign)
        if entry and entry.get("expires", 0) > asyncio.get_event_loop().time():
            return entry.get("route")
        return None

    async def _lookup_routes(
        self, aircraft_list: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Batch-lookup flight routes via adsb.im API.

        Returns a mapping of callsign -> route info.
        """
        if not self.enable_routes:
            return {}

        now = asyncio.get_event_loop().time()
        callsigns_to_fetch: list[dict[str, Any]] = []
        results: dict[str, dict[str, Any]] = {}

        for plane in aircraft_list:
            flight = plane.get("flight")
            if not flight:
                continue
            flight = flight.strip()
            cached = self._get_cached_route(flight)
            if cached is not None:
                results[flight] = cached
                continue
            lat = plane.get("latitude")
            lon = plane.get("longitude")
            if lat is None or lon is None:
                continue
            callsigns_to_fetch.append(
                {"callsign": flight, "lat": lat, "lng": lon}
            )

        if not callsigns_to_fetch:
            return results

        session = async_get_clientsession(self.hass, verify_ssl=True)
        request_body = json.dumps({"planes": callsigns_to_fetch})

        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                async with session.post(
                    ROUTE_API_URL,
                    data=request_body,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status == 200:
                        text = await response.text()
                        routes = json.loads(text)
                        if isinstance(routes, list):
                            for route in routes:
                                if not route or not isinstance(route, dict):
                                    continue
                                cs = route.get("callsign", "").strip()
                                if not cs:
                                    continue
                                airports = route.get("_airports", [])
                                route_info: dict[str, Any] = {
                                    "origin_icao": airports[0]["icao"] if len(airports) > 0 else "Unknown",
                                    "origin_iata": airports[0]["iata"] if len(airports) > 0 else "Unknown",
                                    "destination_icao": airports[1]["icao"] if len(airports) > 1 else "Unknown",
                                    "destination_iata": airports[1]["iata"] if len(airports) > 1 else "Unknown",
                                    "route_string": self._format_route_string(airports),
                                }
                                self._route_cache[cs] = {
                                    "route": route_info,
                                    "expires": now + ROUTE_CACHE_TTL,
                                }
                                results[cs] = route_info
                        else:
                            _LOGGER.warning(
                                "Unexpected route API response format: %s",
                                type(routes).__name__,
                            )
                    else:
                        _LOGGER.warning(
                            "Route API returned HTTP %d", response.status
                        )
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout fetching flight routes")
        except aiohttp.ClientError as err:
            _LOGGER.warning("Error fetching flight routes: %s", err)
        except json.JSONDecodeError as err:
            _LOGGER.warning("Failed to decode route API response: %s", err)
        except Exception as err:
            _LOGGER.warning("Unexpected error fetching routes: %s", err)

        return results

    def _format_route_string(
        self, airports: list[dict[str, Any]]
    ) -> str:
        """Build a human-readable route string from airport list."""
        if not airports:
            return "Unknown"
        parts = []
        for ap in airports:
            iata = ap.get("iata", "")
            icao = ap.get("icao", "")
            parts.append(iata if iata else icao)
        return " - ".join(parts) if len(parts) > 1 else parts[0] if parts else "Unknown"

    def get_new_device_trackers(
        self, config_entry: ConfigEntry
    ) -> list[Any]:
        """Return device tracker entities for aircraft not yet tracked."""
        from .device_tracker import ADSBAircraftDeviceTracker

        if not self.data or not self.data.get("aircraft"):
            return []

        new_trackers = []
        for plane in self.data["aircraft"]:
            hex_code = plane.get("hex", "").strip().upper()
            if not hex_code:
                continue
            if hex_code in self._tracker_hexes:
                continue
            self._tracker_hexes.add(hex_code)
            new_trackers.append(
                ADSBAircraftDeviceTracker(self, config_entry, hex_code)
            )

        return new_trackers

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch aircraft data from the configured source."""
        # Ensure metadata databases are loaded
        await self._async_load_databases()

        if self.source_type == SOURCE_TYPE_LOCAL:
            return await self._update_local()
        elif self.source_type == SOURCE_TYPE_ADSB_LOL:
            return await self._update_adsb_lol()
        elif self.source_type == SOURCE_TYPE_ADSBEXCHANGE:
            return await self._update_adsbexchange()
        else:
            raise UpdateFailed(f"Unknown source type: {self.source_type}")

    async def _update_local(self) -> dict[str, Any]:
        """Fetch data from a local dump1090 / tar1090 source."""
        data = await self._async_fetch_data(self.url)

        if "aircraft" not in data:
            raise UpdateFailed("Invalid ADSB data: missing aircraft array")

        home_lat, home_lon = self.home_location
        radius_km = self._radius_km()

        aircraft_list = data["aircraft"]
        processed_aircraft = []

        for plane in aircraft_list:
            lat = plane.get("lat")
            lon = plane.get("lon")

            if lat is None or lon is None:
                continue

            distance_km = haversine_distance(home_lat, home_lon, lat, lon)

            if distance_km > radius_km:
                continue

            if not self._is_above_min_altitude(plane):
                continue

            processed_aircraft.append(
                self._process_aircraft(plane, distance_km)
            )

        processed_aircraft.sort(key=lambda x: x["distance_km"])

        await self._enrich_routes(processed_aircraft)

        return {
            "aircraft": processed_aircraft,
            "aircraft_count": len(processed_aircraft),
            "last_update": data.get("now"),
            "total_messages": data.get("messages", 0),
            "home_latitude": home_lat,
            "home_longitude": home_lon,
            "radius_km": radius_km,
        }

    async def _update_adsb_lol(self) -> dict[str, Any]:
        """Fetch data from adsb.lol API."""
        data = await self._async_fetch_data(self.url)

        if "ac" not in data:
            raise UpdateFailed("Invalid ADSB data: missing ac array")

        aircraft_list = data["ac"]
        processed_aircraft = []

        for plane in aircraft_list:
            if not self._is_above_min_altitude(plane):
                continue

            dst_nm = plane.get("dst")
            if dst_nm is None:
                # Fallback to haversine if dst missing
                lat = plane.get("lat")
                lon = plane.get("lon")
                if lat is None or lon is None:
                    continue
                home_lat, home_lon = self.home_location
                distance_km = haversine_distance(
                    home_lat, home_lon, lat, lon
                )
            else:
                distance_km = dst_nm * NM_TO_KM

            processed_aircraft.append(
                self._process_aircraft(plane, distance_km)
            )

        processed_aircraft.sort(key=lambda x: x["distance_km"])

        await self._enrich_routes(processed_aircraft)

        now = data.get("now")
        if now and now > 1e10:
            # adsb.lol returns timestamp in milliseconds
            now = now / 1000.0

        return {
            "aircraft": processed_aircraft,
            "aircraft_count": len(processed_aircraft),
            "last_update": now,
            "total_messages": data.get("total", 0),
            "home_latitude": self.hass.config.latitude,
            "home_longitude": self.hass.config.longitude,
            "radius_km": self._radius_km(),
        }

    async def _update_adsbexchange(self) -> dict[str, Any]:
        """Fetch data from ADS-B Exchange API."""
        data = await self._async_fetch_data(self.url, headers=self._api_headers)

        aircraft_key = "ac" if "ac" in data else "aircraft"
        if aircraft_key not in data:
            raise UpdateFailed(
                f"Invalid ADSB data: missing {aircraft_key} array"
            )

        aircraft_list = data[aircraft_key]
        processed_aircraft = []

        for plane in aircraft_list:
            if not self._is_above_min_altitude(plane):
                continue

            dst_nm = plane.get("dst")
            if dst_nm is None:
                lat = plane.get("lat")
                lon = plane.get("lon")
                if lat is None or lon is None:
                    continue
                home_lat, home_lon = self.home_location
                distance_km = haversine_distance(
                    home_lat, home_lon, lat, lon
                )
            else:
                distance_km = dst_nm * NM_TO_KM

            processed_aircraft.append(
                self._process_aircraft(plane, distance_km)
            )

        processed_aircraft.sort(key=lambda x: x["distance_km"])

        await self._enrich_routes(processed_aircraft)

        now = data.get("now")
        if now and now > 1e10:
            now = now / 1000.0

        return {
            "aircraft": processed_aircraft,
            "aircraft_count": len(processed_aircraft),
            "last_update": now,
            "total_messages": data.get("total", 0),
            "home_latitude": self.hass.config.latitude,
            "home_longitude": self.hass.config.longitude,
            "radius_km": self._radius_km(),
        }

    async def _enrich_routes(self, aircraft_list: list[dict[str, Any]]) -> None:
        """Lookup and attach route info to processed aircraft."""
        if not self.enable_routes or not aircraft_list:
            return

        # Use original plane dicts for lookup (need lat/lon)
        routes = await self._lookup_routes(aircraft_list)

        for plane in aircraft_list:
            flight = plane.get("flight")
            if flight and flight in routes:
                route = routes[flight]
                plane.update(route)
            else:
                plane["origin_icao"] = "Unknown"
                plane["origin_iata"] = "Unknown"
                plane["destination_icao"] = "Unknown"
                plane["destination_iata"] = "Unknown"
                plane["route_string"] = "Unknown"

    def _process_aircraft(
        self, plane: dict[str, Any], distance_km: float
    ) -> dict[str, Any]:
        """Process and enrich individual aircraft data."""
        flight = plane.get("flight")
        if flight:
            flight = flight.strip()

        aircraft_type = plane.get("t")

        # Enrich with open database lookups
        operator_info = self._lookup_operator(flight)
        type_info = self._lookup_type(aircraft_type)

        result: dict[str, Any] = {
            "hex": plane.get("hex"),
            "latitude": plane.get("lat"),
            "longitude": plane.get("lon"),
            "distance_km": round(distance_km, 2),
            "distance_display": self.format_distance(distance_km),
        }

        if plane.get("r"):
            result["tail"] = plane["r"]
        if flight:
            result["flight"] = flight
        if aircraft_type:
            result["aircraft_type"] = aircraft_type
        if plane.get("desc"):
            result["description"] = plane["desc"]
        if operator_info.get("operator"):
            result["operator"] = operator_info["operator"]
        if operator_info.get("operator_country"):
            result["operator_country"] = operator_info["operator_country"]
        if type_info.get("aircraft_description"):
            result["aircraft_description"] = type_info["aircraft_description"]
        if type_info.get("weight_class"):
            result["weight_class"] = type_info["weight_class"]
        if plane.get("alt_baro") is not None:
            result["altitude_ft"] = plane["alt_baro"]
        if plane.get("alt_geom") is not None:
            result["altitude_geom"] = plane["alt_geom"]
        if plane.get("gs") is not None:
            result["speed_kts"] = plane["gs"]
        if plane.get("track") is not None:
            result["heading"] = plane["track"]
        if plane.get("baro_rate") is not None:
            result["vertical_rate_fpm"] = plane["baro_rate"]
        if plane.get("squawk"):
            result["squawk"] = plane["squawk"]
        if plane.get("emergency") and plane["emergency"] != "none":
            result["emergency"] = plane["emergency"]
        if plane.get("category"):
            result["category"] = plane["category"]
        if plane.get("messages"):
            result["messages"] = plane["messages"]
        if plane.get("seen") is not None:
            result["seen"] = plane["seen"]
        if plane.get("rssi") is not None:
            result["rssi"] = plane["rssi"]

        return result
