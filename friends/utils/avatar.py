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

from gi.repository import Gio, GLib, GdkPixbuf
from tempfile import gettempdir
from hashlib import sha1

from friends.utils.http import Downloader
from friends.errors import ignored


CACHE_DIR = os.path.join(gettempdir(), 'friends-avatars')


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

        with ignored(FileNotFoundError):
            size = os.stat(local_path).st_size

        if size == 0:
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
