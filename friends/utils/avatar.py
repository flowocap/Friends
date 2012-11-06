# friends-service -- send & receive messages from any social network
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
import errno
import logging

from datetime import date, timedelta
from gi.repository import Gio, GLib, GdkPixbuf
from hashlib import sha1

from friends.utils.http import Downloader


CACHE_DIR = os.path.realpath(os.path.join(
    GLib.get_user_cache_dir(), 'friends', 'avatars'))
CACHE_AGE = timedelta(weeks=4)


log = logging.getLogger(__name__)


class Avatar:
    @staticmethod
    def get_path(url):
        if not os.path.isdir(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        # XXX Two considerations for the future.  What if the image data
        # changes but the url stays the same?  Perhaps the contents of the
        # image data should contribute to the cache.  Also, there's no API for
        # invalidating the cache or evicting entries, so eventually there
        # should be a way to do that, or check the timestamp of the files and
        # ignore the cache when they age.
        return os.path.join(CACHE_DIR, sha1(url.encode('utf-8')).hexdigest())

    @staticmethod
    def get_image(url):
        if not url:
            return url
        local_path = Avatar.get_path(url)
        try:
            size = os.stat(local_path).st_size
        except OSError as error:
            if error.errno != errno.ENOENT:
                # Some other error occurred, so propagate it up.
                raise
            # Treat a missing file as zero length.
            size = 0
        if size == 0:
            log.debug('Getting: {}'.format(url))
            image_data = Downloader(url).get_bytes()
            input_stream = Gio.MemoryInputStream.new_from_data(
                image_data, None)
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(
                    input_stream, 100, 100, True, None)
                pixbuf.savev(local_path, 'png', [], [])
            except GLib.GError:
                log.error('Failed to save image: {}'.format(url))
                return ''
        return local_path

    @staticmethod
    def expire_old_avatars():
        """Evict old files from the cache."""
        limit = date.today() - CACHE_AGE
        for filename in os.listdir(CACHE_DIR):
            path = os.path.join(CACHE_DIR, filename)
            mtime = date.fromtimestamp(os.stat(path).st_mtime)
            if mtime < limit:
                # The file's last modification time is earlier than the oldest
                # time we'll allow in the cache.  However, due to race
                # conditions, ignore it if the file has already been removed.
                try:
                    log.debug('Expiring: {}'.format(path))
                    os.remove(path)
                except OSError as error:
                    if error.errno != errno.ENOENT:
                        raise
