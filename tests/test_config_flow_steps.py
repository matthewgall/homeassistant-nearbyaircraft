"""Tests for the ADSB Nearby Aircraft config flow step_config paths."""
from __future__ import annotations

import pytest

from custom_components.adsb_nearby.config_flow import (
    ConfigFlow,
    SOURCE_TYPE_ADSB_FI,
    SOURCE_TYPE_AIRPLANES_LIVE,
    SOURCE_TYPE_LOCAL,
)
from custom_components.adsb_nearby.const import DOMAIN


def make_flow(hass, source_type: str):
    """Return a manually constructed ConfigFlow instance for testing."""
    flow = object.__new__(ConfigFlow)
    flow.hass = hass
    flow.context = {"source": "user"}
    flow.handler = DOMAIN
    flow._flow_id = "test-flow-id"  # noqa: SLF001
    flow._source_type = source_type  # noqa: SLF001
    return flow


async def test_step_config_adsb_fi_success(hass, aioclient_mock) -> None:
    """Config flow creates an adsb.fi entry when validation succeeds."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    aioclient_mock.get(
        "https://opendata.adsb.fi/api/v3/lat/51.47/lon/-0.46/dist/27",
        json={"ac": [{"hex": "abc"}], "total": 1, "now": 1_700_000_000},
    )
    flow = make_flow(hass, SOURCE_TYPE_ADSB_FI)

    result = await flow.async_step_config(
        user_input={"radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "ADSB Nearby (adsb.fi)"
    assert result["data"]["source_type"] == SOURCE_TYPE_ADSB_FI


async def test_step_config_airplanes_live_success(hass, aioclient_mock) -> None:
    """Config flow creates an airplanes.live entry when validation succeeds."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    aioclient_mock.get(
        "https://api.airplanes.live/v2/point/51.47/-0.46/27",
        json={"ac": [{"hex": "abc"}], "total": 1, "now": 1_700_000_000},
    )
    flow = make_flow(hass, SOURCE_TYPE_AIRPLANES_LIVE)

    result = await flow.async_step_config(
        user_input={"radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "ADSB Nearby (airplanes.live)"


async def test_step_config_adsb_fi_invalid_data(hass, aioclient_mock) -> None:
    """Config flow returns form with error when adsb.fi validation fails."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46
    aioclient_mock.get(
        "https://opendata.adsb.fi/api/v3/lat/51.47/lon/-0.46/dist/27",
        json={"total": 0},  # missing ac
    )
    flow = make_flow(hass, SOURCE_TYPE_ADSB_FI)

    result = await flow.async_step_config(
        user_input={"radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0}
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_adsb_data"


async def test_step_config_local_success(hass, aioclient_mock) -> None:
    """Config flow creates a local source entry when validation succeeds."""
    aioclient_mock.get(
        "http://192.168.1.10/data/aircraft.json",
        json={"now": 1_700_000_000, "messages": 1, "aircraft": [{"hex": "abc"}]},
    )
    flow = make_flow(hass, SOURCE_TYPE_LOCAL)

    result = await flow.async_step_config(
        user_input={
            "host": "192.168.1.10",
            "scheme": "http",
            "port": 80,
            "path": "/data/aircraft.json",
            "verify_ssl": False,
            "radius": 20,
            "update_interval": 10,
            "enable_routes": False,
            "min_altitude": 0,
        }
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "ADSB Nearby (192.168.1.10)"


async def test_step_config_unknown_source(hass, aioclient_mock) -> None:
    """Config flow handles unknown source types gracefully."""
    flow = make_flow(hass, "not_a_source")

    result = await flow.async_step_config(
        user_input={"radius": 50, "update_interval": 10, "enable_routes": False, "min_altitude": 0}
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_step_config_no_input_returns_form(hass) -> None:
    """Calling step_config with no input returns the configuration form."""
    flow = make_flow(hass, SOURCE_TYPE_ADSB_FI)

    result = await flow.async_step_config(user_input=None)

    assert result["type"] == "form"
    assert "source_type" not in result["data_schema"].schema


async def test_step_config_local_form_fields(hass) -> None:
    """Local source form includes host, scheme, port, path, and verify_ssl."""
    flow = make_flow(hass, SOURCE_TYPE_LOCAL)

    result = await flow.async_step_config(user_input=None)
    schema = result["data_schema"].schema

    assert "host" in schema
    assert "scheme" in schema
    assert "port" in schema
    assert "path" in schema
    assert "verify_ssl" in schema
