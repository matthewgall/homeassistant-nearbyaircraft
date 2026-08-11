"""Tests for config flow helpers across all ADSB source types."""
from __future__ import annotations

import pytest

from custom_components.adsb_nearby.config_flow import (
    _build_adsbexchange_url,
    _build_adsb_lol_url,
    _build_local_url,
)
from custom_components.adsb_nearby.const import DOMAIN, DEFAULT_PATH


def test_build_local_url_default_port(hass) -> None:
    """Local URL omits default HTTP port."""
    data = {
        "scheme": "http",
        "host": "192.168.1.5",
        "port": 80,
        "path": DEFAULT_PATH,
    }
    assert _build_local_url(data) == "http://192.168.1.5/data/aircraft.json"


def test_build_local_url_https_custom_port(hass) -> None:
    """Local URL includes custom HTTPS port."""
    data = {
        "scheme": "https",
        "host": "adsb.example.com",
        "port": 8443,
        "path": "/tar1090/data/aircraft.json",
    }
    assert _build_local_url(data) == "https://adsb.example.com:8443/tar1090/data/aircraft.json"


def test_build_local_url_adds_leading_slash(hass) -> None:
    """Local URL builder normalises path to start with /."""
    data = {
        "scheme": "http",
        "host": "192.168.1.5",
        "port": 8080,
        "path": "data/aircraft.json",
    }
    assert _build_local_url(data) == "http://192.168.1.5:8080/data/aircraft.json"


def test_build_adsb_lol_url(hass) -> None:
    """adsb.lol URL uses HA home location and nautical-mile radius."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46

    url = _build_adsb_lol_url(hass, radius=50, is_metric=True)

    assert url == "https://api.adsb.lol/v2/lat/51.47/lon/-0.46/dist/27"


def test_build_adsbexchange_url(hass) -> None:
    """ADS-B Exchange URL uses HA home location and nautical-mile radius."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46

    url = _build_adsbexchange_url(hass, radius=50, is_metric=True)

    assert url == "https://adsbexchange.com/api/aircraft/json/lat/51.47/lon/-0.46/dist/27/"


async def test_config_flow_user_shows_all_sources(hass) -> None:
    """The source-type picker includes all known sources."""
    from custom_components.adsb_nearby.config_flow import ConfigFlow

    flow = object.__new__(ConfigFlow)
    flow.hass = hass
    flow.context = {"source": "user"}
    flow.handler = DOMAIN
    flow._flow_id = "test-flow-id"  # noqa: SLF001

    result = await flow.async_step_user()

    assert result["type"] == "form"
    choices = result["data_schema"].schema["source_type"].container
    assert "adsb_lol" in choices
    assert "adsb_fi" in choices
    assert "airplanes_live" in choices
    assert "adsbexchange" in choices
    assert "local" in choices
