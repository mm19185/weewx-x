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
