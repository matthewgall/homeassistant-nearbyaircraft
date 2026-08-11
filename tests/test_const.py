"""Tests for ADSB Nearby Aircraft constants."""

from custom_components.adsb_nearby.const import (
    ADSB_FI_API_HOST,
    ADSB_FI_API_PATH_TEMPLATE,
    ADSB_FI_API_PORT,
    ADSB_FI_API_SCHEME,
    ADSB_LOL_API_HOST,
    ADSB_LOL_API_PATH_TEMPLATE,
    ADSB_LOL_API_SCHEME,
    AIRPLANES_LIVE_API_HOST,
    AIRPLANES_LIVE_API_PATH_TEMPLATE,
    AIRPLANES_LIVE_API_PORT,
    AIRPLANES_LIVE_API_SCHEME,
    SOURCE_TYPE_ADSBEXCHANGE,
    SOURCE_TYPE_ADSB_FI,
    SOURCE_TYPE_ADSB_LOL,
    SOURCE_TYPE_AIRPLANES_LIVE,
    SOURCE_TYPE_LOCAL,
)


def test_source_types_exist() -> None:
    """All expected source-type constants should be defined."""
    assert SOURCE_TYPE_LOCAL == "local"
    assert SOURCE_TYPE_ADSB_LOL == "adsb_lol"
    assert SOURCE_TYPE_ADSB_FI == "adsb_fi"
    assert SOURCE_TYPE_AIRPLANES_LIVE == "airplanes_live"
    assert SOURCE_TYPE_ADSBEXCHANGE == "adsbexchange"


def test_adsb_fi_api_constants() -> None:
    """adsb.fi API constants point to the documented endpoint."""
    assert ADSB_FI_API_SCHEME == "https"
    assert ADSB_FI_API_HOST == "opendata.adsb.fi"
    assert ADSB_FI_API_PORT == 443
    assert ADSB_FI_API_PATH_TEMPLATE == "/api/v3/lat/{lat}/lon/{lon}/dist/{dist}"


def test_airplanes_live_api_constants() -> None:
    """airplanes.live API constants point to the documented endpoint."""
    assert AIRPLANES_LIVE_API_SCHEME == "https"
    assert AIRPLANES_LIVE_API_HOST == "api.airplanes.live"
    assert AIRPLANES_LIVE_API_PORT == 443
    assert AIRPLANES_LIVE_API_PATH_TEMPLATE == "/v2/point/{lat}/{lon}/{dist}"


def test_adsb_lol_api_constants_unchanged() -> None:
    """Existing adsb.lol constants remain intact."""
    assert ADSB_LOL_API_SCHEME == "https"
    assert ADSB_LOL_API_HOST == "api.adsb.lol"
    assert ADSB_LOL_API_PATH_TEMPLATE == "/v2/lat/{lat}/lon/{lon}/dist/{dist}"
