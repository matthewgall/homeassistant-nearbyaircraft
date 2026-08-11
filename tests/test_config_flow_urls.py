"""Tests for URL building helpers in the ADSB Nearby Aircraft config flow."""
from __future__ import annotations

from custom_components.adsb_nearby.config_flow import (
    _build_adsb_fi_url,
    _build_airplanes_live_url,
)


def test_build_adsb_fi_url_metric(hass) -> None:
    """adsb.fi URL uses nautical-mile radius from HA location."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46

    url = _build_adsb_fi_url(hass, radius=50, is_metric=True)

    assert url == "https://opendata.adsb.fi/api/v3/lat/51.47/lon/-0.46/dist/27"


def test_build_adsb_fi_url_imperial(hass) -> None:
    """adsb.fi URL converts imperial radius to nautical miles."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46

    url = _build_adsb_fi_url(hass, radius=50, is_metric=False)

    # 50 miles -> 80.467 km -> 43.45 NM -> rounded to 43
    assert url == "https://opendata.adsb.fi/api/v3/lat/51.47/lon/-0.46/dist/43"


def test_build_airplanes_live_url_metric(hass) -> None:
    """airplanes.live URL uses the documented lat/lon/radius path."""
    hass.config.latitude = 60.3179
    hass.config.longitude = 24.9496

    url = _build_airplanes_live_url(hass, radius=25, is_metric=True)

    # 25 km -> 13.5 NM -> rounded to 13
    assert url == "https://api.airplanes.live/v2/point/60.3179/24.9496/13"


def test_build_airplanes_live_url_imperial(hass) -> None:
    """airplanes.live URL rounds distance correctly for imperial input."""
    hass.config.latitude = 51.47
    hass.config.longitude = -0.46

    url = _build_airplanes_live_url(hass, radius=50, is_metric=False)

    assert url == "https://api.airplanes.live/v2/point/51.47/-0.46/43"
