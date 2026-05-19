"""Constants for ADSB Nearby Aircraft integration."""

DOMAIN = "adsb_nearby"

# Configuration keys
CONF_SOURCE_TYPE = "source_type"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCHEME = "scheme"
CONF_PATH = "path"
CONF_RADIUS = "radius"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_VERIFY_SSL = "verify_ssl"
CONF_API_KEY = "api_key"
CONF_ENABLE_ROUTES = "enable_routes"

# Source types
SOURCE_TYPE_LOCAL = "local"
SOURCE_TYPE_ADSB_LOL = "adsb_lol"
SOURCE_TYPE_ADSBEXCHANGE = "adsbexchange"

# Sensor types
SENSOR_CLOSEST_AIRCRAFT = "closest_aircraft"
SENSOR_AIRCRAFT_COUNT = "aircraft_count"
SENSOR_NEAREST_AIRCRAFT = "nearest_aircraft"

# Default values
DEFAULT_SOURCE_TYPE = SOURCE_TYPE_ADSB_LOL
DEFAULT_SCHEME = "http"
DEFAULT_PORT = 80
DEFAULT_PATH = "/data/aircraft.json"
DEFAULT_RADIUS = 50
DEFAULT_UPDATE_INTERVAL = 10
DEFAULT_VERIFY_SSL = True
DEFAULT_TIMEOUT = 30
DEFAULT_ENABLE_ROUTES = False

# Route API
ROUTE_API_URL = "https://adsb.im/api/0/routeset"
ROUTE_CACHE_TTL = 21600  # 6 hours in seconds

# Retry settings
MAX_RETRIES = 2
RETRY_BACKOFF = [5, 15]  # seconds between retries

# adsb.lol API
ADSB_LOL_API_HOST = "api.adsb.lol"
ADSB_LOL_API_SCHEME = "https"
ADSB_LOL_API_PORT = 443
ADSB_LOL_API_PATH_TEMPLATE = "/v2/lat/{lat}/lon/{lon}/dist/{dist}"

# ADS-B Exchange API
ADSBEXCHANGE_API_HOST = "adsbexchange.com"
ADSBEXCHANGE_API_SCHEME = "https"
ADSBEXCHANGE_API_PORT = 443
ADSBEXCHANGE_API_PATH_TEMPLATE = "/api/aircraft/json/lat/{lat}/lon/{lon}/dist/{dist}/"

# Conversion constants
NM_TO_KM = 1.852
NM_TO_MI = 1.15078

# Open aircraft databases (public, no auth required)
# Operators DB: { "ICAO_CODE": ["Operator Name", "Country", "Callsign"] }
# Types DB: { "TYPE_CODE": ["Description", "EngineCode", "WeightClass"] }
OPERATORS_DB_URL = (
    "https://raw.githubusercontent.com/Mictronics/readsb-protobuf/"
    "dev/webapp/src/db/operators.json"
)
TYPES_DB_URL = (
    "https://raw.githubusercontent.com/Mictronics/readsb-protobuf/"
    "dev/webapp/src/db/types.json"
)

# Weight class mapping from ICAO WTC codes
WEIGHT_CLASS_MAP = {
    "L": "Light",
    "M": "Medium",
    "H": "Heavy",
    "J": "Super",
}
