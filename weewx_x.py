# weewx_x.py
# Modernized Twitter/X extension for WeeWX with reliable repeated tweeting
# Supports local paths and remote URLs
# Uses Twitter API v1.1 for media upload and API v2 for tweeting
# Requires tweepy>=4.14 and requests: pip install tweepy requests

import os
import re
import sys
import time
import queue
import tempfile
import requests

import weewx
import weewx.restx
import weewx.units
from weeutil.weeutil import to_bool

import tweepy

VERSION = "0.30"

# --- Logging ---
try:
    import weeutil.logger
    import logging
    log = logging.getLogger(__name__)
    def logdbg(msg): log.debug(msg)
    def loginf(msg): log.info(msg)
    def logerr(msg): log.error(msg)
except ImportError:
    import syslog
    def logmsg(level, msg): syslog.syslog(level, 'Twitter: %s' % msg)
    def logdbg(msg): logmsg(syslog.LOG_DEBUG, msg)
    def loginf(msg): logmsg(syslog.LOG_INFO, msg)
    def logerr(msg): logmsg(syslog.LOG_ERR, msg)


def _dir_to_ord(x, ordinals):
    try:
        return ordinals[int(round(x / 22.5))]
    except (ValueError, IndexError):
        return ordinals[17]


class Twitter(weewx.restx.StdRESTbase):
    _DEFAULT_FORMAT = '{station:%.8s}: Ws: {windSpeed:%.1f}; Wd: {windDir:%03.0f}; Wg: {windGust:%.1f}; oT: {outTemp:%.1f}; oH: {outHumidity:%.2f}; P: {barometer:%.3f}; R: {rain:%.3f}'
    _DEFAULT_FORMAT_NONE = 'calm'
    _DEFAULT_ORDINALS = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S',
                         'SSW','SW','WSW','W','WNW','NW','NNW','N','-']

    def __init__(self, engine, config_dict):
        super(Twitter, self).__init__(engine, config_dict)
        loginf('WeeWX Twitter service v%s' % VERSION)

        site_dict = weewx.restx.get_site_dict(config_dict, 'Twitter',
                                              'app_key', 'app_key_secret',
                                              'oauth_token', 'oauth_token_secret')
        if site_dict is None:
            loginf("Twitter: no site_dict found, service disabled")
            return

        site_dict.setdefault('station', engine.stn_info.location)
        site_dict.setdefault('format', self._DEFAULT_FORMAT)
        site_dict.setdefault('format_None', self._DEFAULT_FORMAT_NONE)
        site_dict.setdefault('ordinals', self._DEFAULT_ORDINALS)
        site_dict.setdefault('format_utc', False)
        site_dict['format_utc'] = to_bool(site_dict.get('format_utc'))

        # Unit system
        usn = site_dict.get('unit_system')
        if usn is not None:
            site_dict['unit_system'] = weewx.units.unit_constants[usn]
            loginf('Units will be converted to %s' % usn)

        # Image paths / URLs
        image_paths = site_dict.get('image_paths', '')
        if isinstance(image_paths, list):
            site_dict['image_paths'] = [str(p).strip() for p in image_paths if str(p).strip()]
        else:
            site_dict['image_paths'] = [p.strip() for p in str(image_paths).split(',') if p.strip()]
        if site_dict['image_paths']:
            loginf('Image paths configured: %s' % site_dict['image_paths'])

        # Binding
        binding = site_dict.pop('binding', 'archive')
        if isinstance(binding, list):
            binding = ','.join(binding)
        loginf('Binding is %s' % binding)

        self.data_queue = queue.Queue()
        data_thread = TwitterThread(self.data_queue, **site_dict)
        data_thread.start()

        if 'loop' in binding.lower():
            self.bind(weewx.NEW_LOOP_PACKET, self.handle_new_loop)
        if 'archive' in binding.lower():
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.handle_new_archive)

        loginf("Data will be tweeted for %s" % site_dict['station'])

    def handle_new_loop(self, event):
        packet = dict(event.packet)
        packet['binding'] = 'loop'
        self.data_queue.put(packet)

    def handle_new_archive(self, event):
        record = dict(event.record)
        record['binding'] = 'archive'
        self.data_queue.put(record)


class TwitterThread(weewx.restx.RESTThread):
    def __init__(self, queue,
                 app_key, app_key_secret, oauth_token, oauth_token_secret,
                 station, format, format_None, ordinals,
                 format_utc=True, unit_system=None, skip_upload=False,
                 log_success=True, log_failure=True,
                 post_interval=None, max_backlog=sys.maxsize, stale=None,
                 timeout=60, max_tries=3, retry_wait=5,
                 image_paths=None):

        super(TwitterThread, self).__init__(queue,
                                            protocol_name='Twitter',
                                            manager_dict=None,
                                            post_interval=post_interval,
                                            max_backlog=max_backlog,
                                            stale=stale,
                                            log_success=log_success,
                                            log_failure=log_failure,
                                            max_tries=max_tries,
                                            timeout=timeout,
                                            retry_wait=retry_wait)

        self.app_key = app_key
        self.app_key_secret = app_key_secret
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret
        self.station = station
        self.format = format
        self.format_None = format_None
        self.ordinals = ordinals
        self.format_utc = format_utc
        self.unit_system = unit_system
        self.skip_upload = to_bool(skip_upload)
        self.image_paths = image_paths or []

    def format_tweet(self, record):
        msg = self.format
        for obs in record:
            oldstr = None
            fmt = '%s'
            pattern = "{%s}" % obs
            m = re.search(pattern, msg)
            if m:
                oldstr = m.group(0)
            else:
                pattern = "{%s:([^}]+)}" % obs
                m = re.search(pattern, msg)
                if m:
                    oldstr = m.group(0)
                    fmt = m.group(1)
            if oldstr is not None:
                if obs == 'dateTime':
                    ts = time.gmtime(record[obs]) if self.format_utc else time.localtime(record[obs])
                    newstr = time.strftime(fmt, ts)
                elif record[obs] is None:
                    newstr = self.format_None
                elif obs == 'windDir' and fmt.lower() == 'ord':
                    newstr = _dir_to_ord(record[obs], self.ordinals)
                else:
                    try:
                        newstr = fmt % record[obs]
                    except Exception:
                        newstr = str(record[obs])
                msg = msg.replace(oldstr, newstr)
        logdbg('Tweet text: %s' % msg)
        return msg

    def process_record(self, record, dummy_manager):
        if self.unit_system is not None:
            record = weewx.units.to_std_system(record, self.unit_system)
        record['station'] = self.station

        msg = self.format_tweet(record)
        if self.skip_upload:
            loginf('Skipping upload')
            return

        ntries = 0
        while ntries < self.max_tries:
            ntries += 1
            try:
                # --- Tweepy auth setup ---
                # API v1.1 (media upload)
                auth = tweepy.OAuth1UserHandler(
                    consumer_key=self.app_key,
                    consumer_secret=self.app_key_secret,
                    access_token=self.oauth_token,
                    access_token_secret=self.oauth_token_secret
                )
                api = tweepy.API(auth)

                # API v2 (tweet publishing)
                client = tweepy.Client(
                    consumer_key=self.app_key,
                    consumer_secret=self.app_key_secret,
                    access_token=self.oauth_token,
                    access_token_secret=self.oauth_token_secret
                )

                # Collect media IDs
                media_ids = []
                for path_or_url in self.image_paths:
                    tmp_file_path = None
                    if path_or_url.lower().startswith(("http://", "https://")):
                        try:
                            with requests.get(path_or_url, stream=True, timeout=15) as resp:
                                resp.raise_for_status()
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                                    for chunk in resp.iter_content(chunk_size=8192):
                                        tmp_file.write(chunk)
                                    tmp_file_path = tmp_file.name
                            media = api.media_upload(tmp_file_path)
                            media_ids.append(media.media_id)
                        except Exception as e:
                            logerr(f"Failed to download/upload image from URL {path_or_url}: {e}")
                        finally:
                            if tmp_file_path and os.path.exists(tmp_file_path):
                                try:
                                    os.remove(tmp_file_path)
                                except Exception:
                                    pass
                    else:
                        if os.path.exists(path_or_url):
                            try:
                                media = api.media_upload(path_or_url)
                                media_ids.append(media.media_id)
                            except Exception as e:
                                logerr(f"Failed to upload image {path_or_url}: {e}")

                # Post the tweet (v2)
                if media_ids:
                    client.create_tweet(text=msg, media_ids=media_ids)
                else:
                    client.create_tweet(text=msg)

                loginf("Tweet posted successfully")
                return

            except tweepy.TweepyException as e:
                logerr("Failed attempt %d of %d: %s" % (ntries, self.max_tries, e))
                logdbg("Waiting %d seconds before retry" % self.retry_wait)
                time.sleep(self.retry_wait)

        raise weewx.restx.FailedPost("Max retries (%d) exceeded" % self.max_tries)
