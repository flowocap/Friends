# friends-dispatcher -- send & receive messages from any social network
# Copyright (C) 2012  Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Utils for downloading, sizing, and caching of avatar images."""

__all__ = [
    'Avatar',
    ]


import os
import logging

from datetime import date, timedelta
from gi.repository import Gio, GLib, GdkPixbuf
from hashlib import sha1

from friends.utils.http import Downloader
from friends.errors import ignored


CACHE_DIR = os.path.realpath(os.path.join(
    GLib.get_user_cache_dir(), 'friends', 'avatars'))
AGE_LIMIT = date.today() - timedelta(weeks=4)


with ignored(FileExistsError):
    os.makedirs(CACHE_DIR)


log = logging.getLogger(__name__)


class Avatar:
    @staticmethod
    def get_path(url):
        return os.path.join(CACHE_DIR, sha1(url.encode('utf-8')).hexdigest())

    @staticmethod
    def get_image(url):
        if not url:
            return url
        local_path = Avatar.get_path(url)
        size = 0
        mtime = date.fromtimestamp(0)

        with ignored(FileNotFoundError):
            stat = os.stat(local_path)
            size = stat.st_size
            mtime = date.fromtimestamp(stat.st_mtime)

        if size == 0 or mtime < AGE_LIMIT:
            log.debug('Getting: {}'.format(url))
            image_data = Downloader(url).get_bytes()

            # Save original size at canonical URI
            with open(local_path, 'wb') as fd:
                fd.write(image_data)

            # Append '.100px' to filename and scale image there.
            input_stream = Gio.MemoryInputStream.new_from_data(
                image_data, None)
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(
                    input_stream, 100, 100, True, None)
                pixbuf.savev(local_path + '.100px', 'png', [], [])
            except GLib.GError:
                log.error('Failed to scale image: {}'.format(url))
        return local_path

    @staticmethod
    def expire_old_avatars():
        """Evict old files from the cache."""
        log.debug('Checking if anything needs to expire.')
        for filename in os.listdir(CACHE_DIR):
            path = os.path.join(CACHE_DIR, filename)
            mtime = date.fromtimestamp(os.stat(path).st_mtime)
            if mtime < AGE_LIMIT:
                # The file's last modification time is earlier than the oldest
                # time we'll allow in the cache.  However, due to race
                # conditions, ignore it if the file has already been removed.
                with ignored(FileNotFoundError):
                    log.debug('Expiring: {}'.format(path))
                    os.remove(path)
