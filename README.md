# 📦 Release 2.0 — Standalone Weather Poster & Major Refactor

This release transforms the weather poster from a WeeWX service extension into a **standalone, production-ready script**. The new version features improved scheduling, richer weather data integration, smarter caching, enhanced descriptive output, and full support for Twitter/X posting.

---

## ✨ Highlights

- 🚀 Complete refactor from WeeWX service extension to a **standalone Python 3.9+ script**.
- 🌤️ Supports **current conditions, daily forecasts, and snowfall** from WeatherAPI and Open-Meteo.
- 🌙 Displays **moon phase emoji** for easy visual reference.
- 📊 Computes **pressure trends** from WeeWX SQLite database.
- 🧠 Built-in **caching and retry logic** for robust API calls.
- 📸 Supports **posting local or remote images**.
- 🕒 Fully **scheduled posting** with optional test modes (`--test` and `--test-now`).

---

## 🛠️ Improvements & Fixes

### 🧱 Architecture
- Migrated from a **WeeWX-bound procedural script** to a standalone, class-based design.
- Configurable **via `config.json`** or environment variables for API keys, locations, and tweet options.
- Internal scheduling replaces dependency on cron or WeeWX event triggers.

### 🌐 Weather Data
- Added **Open-Meteo support** for snow rate and accumulation.
- Enhanced **UV index calculation** with configurable solar calibration.
- Improved **sky condition and precipitation logic** with descriptive emoji mapping.
- Added **wind descriptors** based on speed and gusts.
- Daily rain totals converted to **mm** for consistent reporting.
- Handles missing data gracefully: temperature, wind, clouds, rain, and astronomy info.

### 🖼️ Twitter/X Integration
- Supports **media upload for local or remote images**.
- Uses **Tweepy v2** for simplified and reliable posting.
- Built-in **rate limit handling** and error retries.

### 🧩 Caching & Reliability
- Smart **local caching** reduces unnecessary API calls.
- Robust **retry logic** for both WeatherAPI/Open-Meteo and Twitter/X endpoints.
- Logs activity and errors with Python `logging`.

### ⏱️ Scheduling & Test Modes
- **Scheduled posts** at specified Atlantic Time hours.
- Test options:
  - `--test`: Preview scheduled tweets without posting.
  - `--test-now`: Immediate preview with latest data.

---

## ❌ Removed / Deprecated

| Old Behavior | New Replacement |
|--------------|----------------|
| Dependent on WeeWX service (`weewx_x.py`) | Standalone Python script |
| Legacy WeatherAPI-only logic | Optional Open-Meteo integration for snow, clouds, and weather codes |
| Global procedural code | Class-based, modular design |
| Twitter v1.1/v2 dual handling | Simplified Tweepy v2 workflow |
| Queue/threaded processing tied to WeeWX | Internal scheduling with robust caching and retry |

---

## 🐦 Example Tweet

🪟 Now—Partly cloudy and mild, light winds

🌡️ Temp: 15.9°, Feels: 16.6°
💧 Dewpoint: 13.4°, Humidity: 85%
🌬️ Wind: E at 2km/h, Gust: 4km/h
↔️ Pressure: 1020mb (steady)
☁️ Cloud: 16%
😎 UV: 0, 35W/m²

🌅 7:20 AM, 🌇 6:43 PM
🌕 Full

ℹ️ https://awebsite.com

--- 

## 🐦 During precipitation events, when wind is calm, etc

🪟 Now—Rain and mild, light winds

🌡️ Temp: 15.9°, Feels: 16.6°
💧 Dewpoint: 13.4°, Humidity: 85%
🌬️ Wind: calm
↔️ Pressure: 1020mb (steady)
🌧️ Rain: 4.0mm/h, Total: 5mm, Cloud: 100%
😎 UV: 0, 35W/m²

🌅 7:20 AM, 🌇 6:43 PM
🌕 Full

ℹ️ https://awebsite.com

---

## 📦 Migration Notes

- Ensure **Python 3.9+** for `zoneinfo` timezone support.
- Set Twitter/X credentials as environment variables:  
  `TWITTER_APP_KEY`, `TWITTER_APP_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET`.
- Optional environment variables: `WEATHERAPI_KEY`, `WEATHER_LOCATION`, `OPENMETEO_LAT`, `OPENMETEO_LON`.
- Logs to console and file; review for troubleshooting and validation.

---

## ✅ Summary

Release **2.0** transforms the weather poster into a **fully automated, standalone, production-ready script**. It’s more reliable, flexible, and capable of handling modern weather data and social posting workflows — perfect for long-term automated deployments.
