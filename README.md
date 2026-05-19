# ADSB Nearby Aircraft

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

A Home Assistant custom integration that connects to aircraft data sources and shows aircraft within a specified radius of your Home Assistant home location.

## Features

- **Multiple data sources**:
  - [adsb.lol](https://adsb.lol) (free, global, no API key required — **default**)
  - Local [dump1090](https://github.com/flightaware/dump1090) / [tar1090](https://github.com/wiedehopf/tar1090) instances
  - [ADS-B Exchange](https://adsbexchange.com) (requires API key)
- Configurable host, port, protocol, and path for local sources
- Filters aircraft by distance from your Home Assistant home location using the haversine formula (for local sources) or using the source's pre-computed distances (for online sources)
- Supports both metric (km) and imperial (miles) units based on your Home Assistant settings
- Shows closest aircraft, total count, and nearest aircraft list
- SSL verification can be disabled for local self-signed certificates

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to **Custom repositories**
3. Add `https://github.com/matthewgall/homeassistant-nearbyaircraft` and select **Integration** as the category
4. Click **Install**
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/adsb_nearby/` directory to your Home Assistant `custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings > Devices & Services**
2. Click **Add Integration**
3. Search for "ADSB Nearby Aircraft"
4. Select your data source and configure:

### Source: adsb.lol (default)

| Option | Description | Example |
|--------|-------------|---------|
| **Radius** | Maximum distance from your home location | `50` (miles or km based on HA settings) |
| **Update Interval** | How often to refresh data (seconds) | `10` |

No host, port, or API key required. The integration automatically queries the adsb.lol API using your Home Assistant home location coordinates. This is the fastest way to get started.

### Source: Local dump1090 / tar1090

| Option | Description | Example |
|--------|-------------|---------|
| **Host** | IP address or hostname of your ADSB feeder | `192.168.0.6` |
| **Protocol** | HTTP or HTTPS | `HTTP` |
| **Port** | Port number your feeder listens on | `80` |
| **Path** | Path to the `aircraft.json` endpoint | `/tar1090/data/aircraft.json` |
| **Radius** | Maximum distance from your home location | `50` (miles or km based on HA settings) |
| **Update Interval** | How often to refresh data (seconds) | `10` |
| **Verify SSL** | Enable/disable SSL certificate verification | `true` |

### Source: ADS-B Exchange

| Option | Description | Example |
|--------|-------------|---------|
| **API Key** | Your ADS-B Exchange API key | `your-api-key-here` |
| **Radius** | Maximum distance from your home location | `50` (miles or km based on HA settings) |
| **Update Interval** | How often to refresh data (seconds) | `10` |

Requires an API key from ADS-B Exchange. Obtain one from their [Developer Hub](https://www.adsbexchange.com/api/).

### Common Local Configurations

| Feeder | Host | Protocol | Port | Path |
|--------|------|----------|------|------|
| tar1090 (default) | `192.168.0.6` | HTTP | `80` | `/data/aircraft.json` |
| tar1090 (subpath) | `192.168.0.6` | HTTP | `80` | `/tar1090/data/aircraft.json` |
| dump1090 | `192.168.0.6` | HTTP | `8080` | `/data/aircraft.json` |
| Readsb | `adsb.example.com` | HTTPS | `443` | `/data/aircraft.json` |

## Sensors

The integration creates the following sensors:

- **Closest Aircraft**: The nearest aircraft to your home location, with detailed attributes
- **Aircraft in Range**: Total number of aircraft within the configured radius
- **Nearest Aircraft**: List of up to 10 nearest aircraft with full details in attributes

## Aircraft JSON Format

### Local Source (dump1090 / tar1090)

The integration expects data in the standard dump1090/tar1090 `aircraft.json` format:

```json
{
  "now": 1779134579.1,
  "messages": 3911783,
  "aircraft": [
    {
      "hex": "440005",
      "flight": "EJU92XV",
      "alt_baro": 11050,
      "gs": 320.7,
      "track": 108.5,
      "lat": 50.794510,
      "lon": -1.161878,
      "rssi": -23.1
    }
  ]
}
```

### adsb.lol / ADS-B Exchange

These online APIs return pre-filtered aircraft data with distance and direction already calculated from your home location.

## Requirements

- Home Assistant 2024.1.0 or newer
- For **local**: a dump1090, tar1090, or readsb instance accessible from your Home Assistant server
- For **adsb.lol**: no additional requirements (free, public API)
- For **ADS-B Exchange**: an active API key from ADS-B Exchange

## Troubleshooting

- **Connection refused** (local): Verify the host and port, and ensure the ADSB feeder is running and accessible
- **Timeout**: Check network connectivity between Home Assistant and the data source
- **SSL errors** (local): If using HTTPS with a self-signed certificate, disable SSL verification
- **No aircraft** (local): Verify the path to `aircraft.json` is correct and the URL returns valid JSON with an `aircraft` array
- **No aircraft in range**: Increase the radius or verify your Home Assistant home location is set correctly
- **Invalid API key** (ADS-B Exchange): Verify your key is correct and your subscription is active

## License

MIT
