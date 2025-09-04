# WeeWX-X
Twitter Poster with Image Support

This is a WeeWX extension that posts current weather conditions directly to X (formerly Twitter).  
It supports custom text templates, automatic retries, and attaching one or more images (local paths or URLs).  

Perfect for sharing live weather snapshots, radar images, or forecast graphics alongside your data tweets.

---

## ✨ Features

- ✅ Post formatted WeeWX data directly to X/Twitter  
- ✅ Support for local or remote images (auto-downloaded)  
- ✅ Automatic retries on connection/auth failures  
- ✅ Configurable via `weewx.conf` (`[StdRESTful]` → `[[TwitterX]]`)  
- ✅ Compatible with X API v1.1 media upload  

---

## 📦 Installation

1. Copy `weewx_x.py` into your WeeWX extensions directory (usually `/etc/weewx/user/bin/`, perhaps `/usr/share/weewx/user/` ).
2. Add the following section to your `weewx.conf` under `[StdRESTful]`:

   ```ini
   [StdRESTful]
       [[Weewx-x]]
           app_key = YOUR_APP_KEY
           app_key_secret = YOUR_APP_KEY_SECRET
           oauth_token = YOUR_OAUTH_TOKEN
           oauth_token_secret = YOUR_OAUTH_SECRET
           format = {station}: 🌡 {outTemp:%.1f}°C; 💧 {outHumidity:%.1f}%; 🌬 {windSpeed:%.1f} km/h
           image_url = /home/weewx/current.png, https://example.com/radar.png
           post_interval = 3600
3. Restart WeeWX
   ```ini
   sudo systemctl restart weewx

## ⚙️ Configuration

`app_key / app_key_secret / oauth_token / oauth_token_secret`
Get these from your X Developer Portal app.

`format`
Custom tweet text template. Any WeeWX observation can be included.

`image_url`
Comma-separated list of local paths or URLs. Remote images will be downloaded before posting.

`post_interval`
Minimum time in seconds between posts (e.g., 3600 = every 1 hours).

## 🖼 Example Tweet

My Station: 🌡 19.6°C; 💧 72%; 🌬 0.0 km/h; 🌀 1023 mbar
Attached image(s): station snapshot, radar image, satellite image (or any other graphics within the confines of X's API)
