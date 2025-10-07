#!/usr/bin/env python3
"""
Standalone Twitter/X Current Conditions Poster
Posts at specified hours (auto-converted to UTC)
Schedule times: 1am, 5am, 9am, 11am, 1pm, 3pm, 5pm, 7pm, 9pm
With **Open-Meteo snow support**, **smart caching**, and **Atlantic UV calibration**
"""

import os
import sys
import time
import tempfile
import requests
import sqlite3
from datetime import datetime, timezone, timedelta
import logging
from dotenv import load_dotenv
import argparse
import json
from pathlib import Path

# For timezone conversion (Python 3.9+)
try:
    from zoneinfo import ZoneInfo
except ImportError:
    print("❌ Python 3.9+ required for zoneinfo.")
    sys.exit(1)

# Load environment variables
load_dotenv()

# --- Configuration ---
VERSION = "2.2"
ATLANTIC_TZ = ZoneInfo("America/Halifax")
SCHEDULED_TIMES_ATLANTIC = [
    "01:00", "05:00", "09:00", "11:00", "13:00",
    "15:00", "17:00", "21:00"
]
DB_PATH = "/var/lib/weewx/weewx.sdb"
WEATHER_CACHE_PATH = "/tmp/weatherapi_cache.json"

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()

def logdbg(msg): logger.debug(msg)
def loginf(msg): logger.info(msg)
def logerr(msg): logger.error(msg)

def cache_weather_data(data, cache_path=WEATHER_CACHE_PATH):
    """Save WeatherAPI response with timestamp."""
    try:
        with open(cache_path, "w") as f:
            json.dump({"timestamp": time.time(), "data": data}, f)
    except Exception as e:
        logerr(f"Failed to cache weather data: {e}")

def load_cached_weather(cache_path=WEATHER_CACHE_PATH, max_age_hours=1):
    """Load cached weather data if fresh."""
    try:
        if not os.path.exists(cache_path):
            return None
        with open(cache_path) as f:
            cached = json.load(f)
        if time.time() - cached.get("timestamp", 0) < max_age_hours * 3600:
            return cached["data"]
    except Exception as e:
        logerr(f"Failed to load weather cache: {e}")
    return None

# --- Emoji mapping (WeatherAPI codes) ---
WEATHER_CODE_ICONS = {
    1000: lambda is_day: "☀️" if is_day else "🌙",
    1003: lambda is_day: "🌤️" if is_day else "☁️",
    1006: lambda is_day: "☁️",
    1009: lambda is_day: "☁️",
    1030: lambda is_day: "🌫️",
    1063: lambda is_day: "🌦️" if is_day else "🌧️",
    1066: lambda is_day: "🌨️",
    1069: lambda is_day: "🌨️",
    1072: lambda is_day: "🌧️",
    1087: lambda is_day: "⛈️",
    1114: lambda is_day: "❄️",
    1117: lambda is_day: "❄️",
    1135: lambda is_day: "🌫️",
    1147: lambda is_day: "🌫️",
    1150: lambda is_day: "🌧️",
    1153: lambda is_day: "🌧️",
    1168: lambda is_day: "🌧️",
    1171: lambda is_day: "🌧️",
    1180: lambda is_day: "🌦️" if is_day else "🌧️",
    1183: lambda is_day: "🌧️",
    1186: lambda is_day: "🌧️",
    1189: lambda is_day: "🌧️",
    1192: lambda is_day: "🌧️",
    1195: lambda is_day: "🌧️",
    1198: lambda is_day: "🌧️",
    1201: lambda is_day: "🌧️",
    1204: lambda is_day: "🌨️",
    1207: lambda is_day: "🌨️",
    1210: lambda is_day: "🌨️",
    1213: lambda is_day: "🌨️",
    1216: lambda is_day: "🌨️",
    1219: lambda is_day: "🌨️",
    1222: lambda is_day: "❄️",
    1225: lambda is_day: "❄️",
    1237: lambda is_day: "🧊",
    1240: lambda is_day: "🌧️",
    1243: lambda is_day: "🌧️",
    1246: lambda is_day: "🌧️",
    1249: lambda is_day: "🌨️",
    1252: lambda is_day: "🌨️",
    1255: lambda is_day: "🌨️",
    1258: lambda is_day: "❄️",
    1261: lambda is_day: "🧊",
    1264: lambda is_day: "🧊",
    1273: lambda is_day: "⛈️",
    1276: lambda is_day: "⛈️",
    1279: lambda is_day: "❄️",
    1282: lambda is_day: "❄️"
}

_DEFAULT_ORDINALS = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S',
                     'SSW','SW','WSW','W','WNW','NW','NNW','N','-']

def _dir_to_ord(x, ordinals):
    try:
        return ordinals[int(round(x / 22.5)) % len(ordinals)]
    except (ValueError, IndexError, TypeError):
        return ordinals[-1] if ordinals else '-'

def describe_temperature(temp_c):
    if temp_c is None:
        return ""
    if temp_c <= -13:
        return "and bitter cold"
    elif temp_c <= -9:
        return "and frigid"
    elif temp_c <= 0:
        return "and nippy"
    elif temp_c <= 4:
        return "and chilly"
    elif temp_c <= 8:
        return "and brisk"
    elif temp_c <= 13:
        return "and cool"
    elif temp_c <= 18:
        return "and mild"
    elif temp_c <= 28:
        return "and warm"
    else:
        return "and hot"

class WeatherAPIClient:
    BASE_URL = "http://api.weatherapi.com/v1"
    def __init__(self, api_key, location):
        self.api_key = api_key
        self.location = location

    def get_current(self):
        try:
            resp = requests.get(f"{self.BASE_URL}/current.json",
                                params={'key': self.api_key, 'q': self.location, 'aqi': 'no'}, timeout=10)
            resp.raise_for_status()
            data = resp.json().get('current', {})
            logdbg(f"WeatherAPI /current response: {data}")
            cache_weather_data({"current": data})
            return data
        except Exception as e:
            logerr(f"WeatherAPI current failed: {e}")
            cached = load_cached_weather()
            if cached and "current" in cached:
                loginf("Using cached WeatherAPI current data")
                return cached["current"]
            return {}

    def get_astronomy(self):
        try:
            resp = requests.get(f"{self.BASE_URL}/astronomy.json",
                                params={'key': self.api_key, 'q': self.location}, timeout=10)
            resp.raise_for_status()
            full_data = resp.json()
            astro = full_data.get('astronomy', {}).get('astro', {})
            phase_map = {
                "New Moon": "🌑 New", "Waxing Crescent": "🌒 Wax Cres", "First Quarter": "🌓 1st Qtr",
                "Waxing Gibbous": "🌔 Wax Gib", "Full Moon": "🌕 Full", "Waning Gibbous": "🌖 Wan Gib",
                "Last Quarter": "🌗 Last Qtr", "Waning Crescent": "🌘 Wan Cres"
            }
            astro['moon_phase'] = phase_map.get(astro.get('moon_phase', ''), astro.get('moon_phase', 'N/A'))
            cache_weather_data({"astronomy": astro})
            return astro
        except Exception as e:
            logerr(f"WeatherAPI astronomy failed: {e}")
            cached = load_cached_weather()
            if cached and "astronomy" in cached:
                loginf("Using cached WeatherAPI astronomy data")
                return cached["astronomy"]
            return {}

def get_openmeteo_data(lat, lon, cache_dir="/tmp", cache_hours=1):
    """Fetch Open-Meteo data with simple file caching."""
    cache_path = Path(cache_dir) / "openmeteo_cache.json"
    now = time.time()

    if cache_path.exists():
        try:
            with open(cache_path) as f:
                cached = json.load(f)
            if now - cached.get("timestamp", 0) < cache_hours * 3600:
                return cached["data"]
        except Exception:
            pass

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ["snowfall", "weather_code", "cloud_cover"],
        "hourly": "snowfall",
        "past_days": 1,
        "forecast_days": 1,
        "timezone": "auto",
        "past_minutely_15": 96,
    }
    try:
        resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        cache_path.parent.mkdir(exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump({"timestamp": now, "data": data}, f)
        return data
    except Exception as e:
        logerr(f"Open-Meteo fetch failed: {e}")
        return None

def post_tweet(tweet_text, media_ids, config):
    loginf("\n=== Tweet to be posted ===\n" + tweet_text + "\n=========================")
    loginf(f"Tweet character count: {len(tweet_text)}/280")
    if len(tweet_text) > 280:
        logerr("⚠️ Tweet will be truncated!")

    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=config['app_key'],
            consumer_secret=config['app_key_secret'],
            access_token=config['oauth_token'],
            access_token_secret=config['oauth_token_secret']
        )

        final_media_ids = None
        if media_ids:
            auth = tweepy.OAuth1UserHandler(
                config['app_key'],
                config['app_key_secret'],
                config['oauth_token'],
                config['oauth_token_secret']
            )
            api = tweepy.API(auth)
            final_media_ids = []
            for path in media_ids:
                try:
                    clean_path = path.strip()
                    if clean_path.lower().startswith(('http://', 'https://')):
                        with requests.get(clean_path, stream=True, timeout=15) as r:
                            r.raise_for_status()
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as f:
                                for chunk in r.iter_content(8192):
                                    f.write(chunk)
                                tmp_path = f.name
                        media = api.media_upload(tmp_path)
                        final_media_ids.append(media.media_id_string)
                        os.unlink(tmp_path)
                    elif os.path.exists(clean_path):
                        media = api.media_upload(clean_path)
                        final_media_ids.append(media.media_id_string)
                except Exception as e:
                    logerr(f"Media upload failed for {clean_path}: {e}")

        response = client.create_tweet(text=tweet_text, media_ids=final_media_ids or None)
        tweet_id = response.data['id']
        url = f"https://twitter.com/user/status/{tweet_id}"
        loginf(f"✅ Tweet posted: {url}")
        return True

    except tweepy.errors.TooManyRequests:
        logerr("❌ Twitter rate limit exceeded")
        return False
    except Exception as e:
        logerr(f"❌ Tweet failed: {e}")
        import traceback
        logerr(traceback.format_exc())
        return False

def get_pressure_trend(db_path, hours_back=3):
    def inhg_to_mb(inhg): return inhg * 33.8639
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        now = int(time.time())
        past = now - int(hours_back * 3600)

        cur.execute("""
            SELECT dateTime, barometer FROM archive
            WHERE barometer IS NOT NULL
            ORDER BY dateTime DESC LIMIT 1
        """)
        current_row = cur.fetchone()
        if not current_row:
            conn.close()
            return None, "❓", "N/A"

        current_time, current_inhg = current_row
        current_mb = inhg_to_mb(current_inhg)

        cur.execute("""
            SELECT barometer FROM archive
            WHERE dateTime BETWEEN ? AND ? AND barometer IS NOT NULL
            ORDER BY ABS(dateTime - ?) LIMIT 1
        """, (past - 1800, past + 1800, past))

        past_row = cur.fetchone()
        conn.close()

        if not past_row:
            return current_mb, "↔️", "steady"

        past_mb = inhg_to_mb(past_row[0])
        delta = current_mb - past_mb
        if delta > 1.0:
            return current_mb, "📈", "rising"
        elif delta < -1.0:
            return current_mb, "📉", "falling"
        else:
            return current_mb, "↔️", "steady"

    except Exception as e:
        logerr(f"Failed to compute pressure trend: {e}")
        return None, "❓", "error"

def get_daily_rain_accumulation(db_path):
    """Get daily rain total from 'dayRain' column (in inches), convert to mm."""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT dayRain FROM archive WHERE dayRain IS NOT NULL ORDER BY dateTime DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if row and row[0] is not None:
            daily_rain_in = row[0]
            daily_rain_mm = daily_rain_in * 25.4
            return daily_rain_mm if daily_rain_mm > 0.05 else None
        return None
    except Exception as e:
        logerr(f"Failed to get daily rain: {e}")
        return None

def format_rain_value(mm):
    """Format: 1 decimal if <1, else whole number."""
    return f"{mm:.1f}" if mm < 1 else str(round(mm))

def build_and_post_tweet(record, config, test_mode=False):
    weather_client = WeatherAPIClient(config.get('weatherapi_key'), config.get('weather_location')) \
                     if config.get('weatherapi_key') else None
    current_weather = weather_client.get_current() if weather_client else {}
    astronomy = weather_client.get_astronomy() if weather_client else {}

    def strip_leading_zero(time_str):
        if time_str and isinstance(time_str, str) and time_str.startswith('0'):
            return time_str[1:]
        return time_str

    sunrise = strip_leading_zero(astronomy.get('sunrise', 'N/A'))
    sunset = strip_leading_zero(astronomy.get('sunset', 'N/A'))

    # Unit conversions
    def f_to_c(f): return (f - 32) * 5.0 / 9.0
    def inhg_to_mb(inhg): return inhg * 33.8639
    def mph_to_kph(mph): return mph * 1.60934
    def inhr_to_mmhr(inhr): return inhr * 25.4

    outTemp = f_to_c(record.get('outTemp')) if record.get('outTemp') is not None else None
    dewpoint = f_to_c(record.get('dewpoint')) if record.get('dewpoint') is not None else None
    radiation = record.get('radiation')
    UV_api = record.get('UV')
    outHumidity = record.get('outHumidity')
    windSpeed = mph_to_kph(record.get('windSpeed')) if record.get('windSpeed') is not None else None
    # Prefer 10-minute average wind direction
    windDir = record.get('winddir_avg10m')
    if windDir is None:
        windDir = record.get('windDir')
    windGust = mph_to_kph(record.get('windGust')) if record.get('windGust') is not None else None
    rainRate_inhr = record.get('rainRate') or 0.0
    rainRate = rainRate_inhr * 25.4
    appTemp = f_to_c(record.get('appTemp')) if record.get('appTemp') is not None else outTemp

    # === Open-Meteo Integration ===
    om_data = None
    om_snow_rate_mm = None
    om_daily_snow_mm = None
    om_weather_code = None
    om_cloud_cover = None

    om_lat = config.get('openmeteo_lat')
    om_lon = config.get('openmeteo_lon')
    if om_lat and om_lon:
        om_data = get_openmeteo_data(om_lat, om_lon)
        if om_data:
            current = om_data.get("current", {})
            om_snow_rate_mm = current.get("snowfall")
            om_weather_code = current.get("weather_code")
            om_cloud_cover = current.get("cloud_cover")

            hourly_snow = om_data.get("hourly", {}).get("snowfall", [])
            if hourly_snow:
                om_daily_snow_mm = sum(v for v in hourly_snow if v is not None and v > 0)

    # Cloud cover
    if om_cloud_cover is not None:
        cloud_cover_pct = int(om_cloud_cover)
    else:
        cloud_cover_raw = current_weather.get('cloud') if current_weather else None
        cloud_cover_pct = cloud_cover_raw if isinstance(cloud_cover_raw, int) else None

    cloud_str = f"{cloud_cover_pct}%" if cloud_cover_pct is not None else "N/A"

    # === Precip Type Detection ===
    def get_precip_type_icon_from_wmo(wmo_code):
        wmo = int(wmo_code)
        if wmo in [70, 71, 72, 73, 74, 75, 76, 77, 78, 85, 86]:
            return "snow", "❄️"
        elif wmo in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 68, 69, 80, 81, 82]:
            return "rain", "🌧️"
        else:
            return "none", "☁️"

    precip_type = "none"
    precip_icon = "☁️"
    if om_weather_code is not None:
        precip_type, precip_icon = get_precip_type_icon_from_wmo(om_weather_code)
    else:
        if current_weather:
            code = current_weather.get('condition', {}).get('code', 0)
            if code in [1201, 1204, 1207, 1210, 1213, 1216, 1219, 1222, 1225]:
                precip_type, precip_icon = "snow", "❄️"
            elif code in [1150, 1153, 1168, 1171, 1180, 1183, 1186, 1189, 1192, 1195, 1198, 1201, 1240, 1243, 1246]:
                precip_type, precip_icon = "rain", "🌧️"

    # === Build Precip Line ===
    daily_rain = get_daily_rain_accumulation(DB_PATH)

    if precip_type == "snow":
        rate_str = "0"
        if om_snow_rate_mm is not None and om_snow_rate_mm >= 0.1:
            rate_str = f"{format_rain_value(om_snow_rate_mm)}cm/h"
        total_str = ""
        if om_daily_snow_mm is not None and om_daily_snow_mm > 0:
            total_val = f"{om_daily_snow_mm:.1f}" if om_daily_snow_mm < 1 else str(round(om_daily_snow_mm))
            total_str = f", Total: {total_val}cm"
        precip_line = f"{precip_icon} Snow: {rate_str}{total_str}"

    elif precip_type == "rain":
        rain_rate_str = "0" if rainRate < 0.1 else f"{format_rain_value(rainRate)}mm/h"
        rain_accum_str = ""
        if daily_rain is not None and daily_rain > 0:
            rain_accum_str = f", Total: {format_rain_value(daily_rain)}mm"
        precip_line = f"{precip_icon} Rain: {rain_rate_str}{rain_accum_str}"

    else:  # dry
        precip_line = f"{precip_icon} Cloud: {cloud_str}"
        cloud_line = ""  # avoid duplication

    # Wind
    if windSpeed is not None and windSpeed < 1:
        wind_str = "🌬️ Wind: Calm"
    elif windSpeed is not None:
        dir_str = _dir_to_ord(windDir, _DEFAULT_ORDINALS) if windDir is not None else "?"
        wind_str = f"🌬️ Wind: {dir_str} at {round(windSpeed)}km/h"
        if windGust is not None and windGust >= 1:
            wind_str += f", Gust: {round(windGust)}km/h"
    else:
        wind_str = "🌬️ Wind: N/A"

    # Pressure
    current_mb, trend_emoji, trend_text = get_pressure_trend(DB_PATH)
    if current_mb is not None:
        pressure_line = f"{trend_emoji} Pressure: {round(current_mb)}mb ({trend_text})"
    else:
        pressure_line = "❓ Pressure: N/A"

    # === UV & Solar (Atlantic Canada calibrated) ===
    def solar_to_uv(solar_wpm2):
        if solar_wpm2 is None or solar_wpm2 < 10:
            return 0
        return max(0, min(round(solar_wpm2 / 95), 9))  # Based on your 474 W/m² ≈ UV 5

    UV = solar_to_uv(radiation)
    uv_str = str(UV) if UV >= 1 else "0"
    solar_str = "0" if radiation is None or radiation < 1 else str(round(radiation))

    # === Descriptive phrase with fallback ===
    condition_text = "N/A"
    descriptive_phrase = "N/A"
    if current_weather:
        cond = current_weather.get('condition', {})
        condition_text = cond.get('text', 'N/A')
        is_day = bool(current_weather.get('is_day', 1))
        code = cond.get('code')
        if code in WEATHER_CODE_ICONS:
            condition_icon = WEATHER_CODE_ICONS[code](is_day)
        else:
            condition_icon = "🕛"

        temp_desc = describe_temperature(outTemp)
        wind_desc = ""
        if windGust is not None:
            if windGust >= 64:
                wind_desc = ", storm force winds"
            elif windGust >= 48:
                wind_desc = ", very windy"
            elif windGust >= 32:
                wind_desc = ", windy"
            elif windGust >= 24:
                wind_desc = ", breezy"
            elif windGust >= 8:
                wind_desc = ", gentle breezes"
            elif windGust >= 2:
                wind_desc = ", light winds"
            else:
                wind_desc = ", calm"
        # === Enhanced Sky Condition Logic ===
        # Start with a base sky state from cloud cover
        if cloud_cover_pct is not None:
            if cloud_cover_pct <= 25:
                sky_base = "Clear"
            elif cloud_cover_pct <= 50:
                sky_base = "Partly cloudy"
            elif cloud_cover_pct <= 75:
                sky_base = "Mostly cloudy"
            else:
                sky_base = "Cloudy"
        else:
            # Fallback to WeatherAPI text if no cloud % available
            condition_map = {
                "Clear": "Clear", "Sunny": "Clear", "Partly cloudy": "Partly cloudy",
                "Cloudy": "Cloudy", "Overcast": "Cloudy",
                "Mist": "Fog", "Fog": "Fog", "Haze": "Hazy"
            }
            sky_base = next((v for k, v in condition_map.items() if k.lower() in condition_text.lower()), "Cloudy")

        # Override sky_base if active precipitation or storms
        if precip_type == "rain":
            if "Thunder" in condition_text or om_weather_code in [95, 96, 99]:
                sky_base = "Storms"
            else:
                sky_base = "Rain"
        elif precip_type == "snow":
            sky_base = "Snow"

        descriptive_phrase = f"{sky_base} {temp_desc}{wind_desc}".strip(", ")
    else:
        # Fallback using WeeWX data
        temp_desc = describe_temperature(outTemp)
        wind_desc = ""
        if windGust is not None:
            if windGust >= 64:
                wind_desc = ", storm force winds"
            elif windGust >= 48:
                wind_desc = ", very windy"
            elif windGust >= 32:
                wind_desc = ", windy"
            elif windGust >= 24:
                wind_desc = ", breezy"
            elif windGust >= 8:
                wind_desc = ", gentle breezes"
            elif windGust >= 2:
                wind_desc = ", light winds"
        radiation_val = radiation or 0
        cloud_val = cloud_cover_pct or 0
        if radiation_val > 100:
            sky = "Clear" if cloud_val < 25 else "Partly cloudy"
        else:
            sky = "Cloudy" if cloud_val > 75 else "Overcast"
        descriptive_phrase = f"{sky} {temp_desc}{wind_desc}".strip(", ")

    moon_phase = astronomy.get('moon_phase', 'N/A')

    # Build tweet
    lines = [
        f"🪟 Now—{descriptive_phrase}\n\n",
        f"🌡️ Temp: {outTemp:.1f}°, Feels: {appTemp:.1f}°" if outTemp is not None else "🌡️ Temp: N/A",
        f"💧 Dewpoint: {dewpoint:.1f}°, Humidity: {outHumidity:.0f}%" if (dewpoint is not None and outHumidity is not None) else "💧 Dewpoint/Humidity: N/A",
        wind_str,
        pressure_line,
        precip_line,
        f"😎 UV: {uv_str}, {solar_str}W/m²\n\n",
        f"🌅 {sunrise}, 🌇 {sunset}" if sunrise != 'N/A' else "",
        f"{moon_phase}\n" if moon_phase != 'N/A' else "",
        "ℹ️ https://wx.cityofdartmouth.ca"
    ]

    tweet_text = "\n".join(line for line in lines if line.strip() or line == "\n")

    if len(tweet_text) > 279:
        tweet_text = tweet_text[:279] + " "

    image_paths = [p.strip() for p in (config.get('image_paths') or [])]

    if test_mode:
        loginf("🧪 TEST MODE: Skipping actual tweet post.")
        print("\n" + "="*60)
        print("🐦 TWEET PREVIEW (TEST MODE)")
        print("="*60)
        print(tweet_text)
        print("="*60)
        loginf(f"Tweet length: {len(tweet_text)} chars")
        return True
    else:
        return post_tweet(tweet_text, image_paths, config)

def get_latest_record(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM archive ORDER BY dateTime DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if not row:
            raise ValueError("No data in archive")
        columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))
    except Exception as e:
        logerr(f"Failed to read from DB: {e}")
        raise

def schedule_loop(config, local_times, local_tz, test_mode=False):
    while True:
        now_local = datetime.now(local_tz)
        next_target_local = None
        min_wait = float('inf')

        for t_str in local_times:
            hour, minute = map(int, t_str.split(":"))
            candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now_local:
                candidate += timedelta(days=1)
            wait_sec = (candidate - now_local).total_seconds()
            if wait_sec < min_wait:
                min_wait = wait_sec
                next_target_local = candidate

        if next_target_local is None:
            logerr("No valid schedule found. Exiting.")
            break

        next_utc = next_target_local.astimezone(timezone.utc)
        loginf(f"Next post at {next_target_local.strftime('%Y-%m-%d %H:%M %Z')} "
               f"({next_utc.strftime('%H:%M UTC')}). Sleeping {min_wait/60:.1f} min...")

        time.sleep(min_wait)

        try:
            record = get_latest_record(DB_PATH)
            build_and_post_tweet(record, config, test_mode=test_mode)
        except Exception as e:
            logerr(f"Posting failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="Post weather tweet at scheduled Atlantic times.")
    parser.add_argument('--test', action='store_true', help="Run in test mode: no tweets sent (scheduled).")
    parser.add_argument('--test-now', action='store_true', help="Generate and preview tweet immediately using latest data, then exit.")
    args = parser.parse_args()

    IMAGE_PATHS = [
        "https://www.website.com/path/to/your/image1.png",
        "https://www.website.com/path/to/your/image2.png",
        "https://www.website.com/path/to/your/image3.webp",
        "https://www.website.com/path/to/your/image4.webp"
    ]

    config = {
        'app_key': os.getenv('TWITTER_APP_KEY'),
        'app_key_secret': os.getenv('TWITTER_APP_SECRET'),
        'oauth_token': os.getenv('TWITTER_ACCESS_TOKEN'),
        'oauth_token_secret': os.getenv('TWITTER_ACCESS_SECRET'),
        'weatherapi_key': os.getenv('WEATHERAPI_KEY'),
        'weather_location': os.getenv('WEATHER_LOCATION', 'YOUR_LOC'),
        'openmeteo_lat': os.getenv('OPENMETEO_LAT', 'YOUR_LAT'),
        'openmeteo_lon': os.getenv('OPENMETEO_LON', 'YOUR_LON'),
        'image_paths': IMAGE_PATHS,
    }

    missing = [k for k, v in config.items() if v is None and k not in ('weatherapi_key', 'openmeteo_lat', 'openmeteo_lon')]
    if missing:
        logerr(f"❌ Missing env vars: {missing}")
        sys.exit(1)

    if args.test_now:
        loginf("🧪 Immediate test mode: generating tweet preview using latest data...")
        try:
            record = get_latest_record(DB_PATH)
            build_and_post_tweet(record, config, test_mode=True)
            loginf("✅ Immediate test completed.")
        except Exception as e:
            logerr(f"❌ Immediate test failed: {e}")
            sys.exit(1)
        return

    loginf(f"✅ Standalone Twitter poster v{VERSION} started.")
    loginf(f"🕒 Posting at Atlantic times: {', '.join(SCHEDULED_TIMES_ATLANTIC)}")
    if args.test:
        loginf("🧪 Scheduled test mode: will preview tweets at posting times (no posts sent).")

    try:
        schedule_loop(config, SCHEDULED_TIMES_ATLANTIC, ATLANTIC_TZ, test_mode=args.test)
    except KeyboardInterrupt:
        loginf("🛑 Script stopped by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()
