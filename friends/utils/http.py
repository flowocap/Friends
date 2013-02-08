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

"""Convenient up- and down-loading."""

__all__ = [
    'Downloader',
    'Uploader',
    'BaseRateLimiter',
    ]


import json
import logging

from contextlib import contextmanager
from gi.repository import Gio, Soup, SoupGNOME
from urllib.parse import urlencode

from friends.errors import FriendsError

log = logging.getLogger(__name__)


# Global libsoup session instance.
_soup = Soup.SessionSync()
# Enable this for full requests and responses dumped to STDOUT.
#_soup.add_feature(Soup.Logger.new(Soup.LoggerLogLevel.BODY, -1))
_soup.add_feature(SoupGNOME.ProxyResolverGNOME())


def _get_charset(message):
    """Extract charset from Content-Type header in a Soup Message."""
    type_header = message.response_headers.get_content_type()[1]
    if not type_header:
        return None
    return type_header.get('charset')


class BaseRateLimiter:
    """Base class for the rate limiting API.

    By default, this class does no rate limiting.  Subclass from this and
    override the `wait()` and `update()` methods for protocol specific
    rate-limiting functionality.
    """
    def wait(self, message):
        """Wait an appropriate amount of time before returning.

        Downloading is blocked until this method returns.  This does not block
        the entire application since downloading always happens in a
        sub-thread.  If no wait is necessary, return immediately.

        :param message: The constructed but unsent libSoup Message.
        :type message: Soup.Message
        """
        pass

    def update(self, message):
        """Update any rate limiting values based on the service's response.

        :param message: The same libSoup Message complete with response
            headers.
        :type message: Soup.Message
        """
        pass


class HTTP:
    """Parent class for Uploader and Downloader."""

    @contextmanager
    def _transfer(self):
        """Perform the download, as a context manager."""
        message = self._build_request()
        if message is None:
            raise ValueError('Failed to build this HTTP request.')
        _soup.send_message(message)
        if message.status_code != 200:
            log.error('{}: {} {}'.format(self.url,
                                         message.status_code,
                                         message.reason_phrase))
        yield message
        self._rate_limiter.update(message)

    def get_json(self):
        """Interpret and return the results as JSON data."""
        with self._transfer() as message:
            payload = message.response_body.flatten().get_data()
            charset = _get_charset(message)

        if not payload:
            raise FriendsError('Got zero-length response from server.')

        if len(payload) < 4 and charset is None:
            charset = 'utf-8' # Safest assumption

        # RFC 4627 $3.  JSON text SHALL be encoded in Unicode.  The default
        # encoding is UTF-8.  Since the first two characters of a JSON text
        # will always be ASCII characters [RFC0020], it is possible to
        # determine whether an octet stream is UTF-8, UTF-16 (BE or LE), or
        # UTF-32 (BE or LE) by looking at the pattern of nulls in the first
        # four octets.
        if charset is None:
            octet_0, octet_1, octet_2, octet_3 = payload[:4]
            if 0 not in (octet_0, octet_1, octet_2, octet_3):
                charset = 'utf-8'
            elif (octet_1 == octet_3 == 0) and octet_2 != 0:
                charset = 'utf-16le'
            elif (octet_0 == octet_2 == 0) and octet_1 != 0:
                charset = 'utf-16be'
            elif (octet_1 == octet_2 == octet_3 == 0):
                charset = 'utf-32le'
            elif (octet_0 == octet_1 == octet_2 == 0):
                charset = 'utf-32be'

        return json.loads(payload.decode(charset))

    def get_bytes(self):
        """Return the results as a bytes object."""
        with self._transfer() as message:
            return message.response_body.flatten().get_data()

    def get_string(self):
        """Return the results as a string, decoded as per the response."""
        with self._transfer() as message:
            payload = message.response_body.flatten().get_data()
            charset = _get_charset(message)
            if charset:
                return payload.decode(charset)
            else:
                return payload.decode()


class Downloader(HTTP):
    """Convenient downloading wrapper."""

    def __init__(self, url, params=None, method='GET',
                 headers=None, rate_limiter=None):
        self.url = url
        self.method = method
        self.params = ({} if params is None else params)
        self.headers = ({} if headers is None else headers)
        self._rate_limiter = (BaseRateLimiter() if rate_limiter is None
                              else rate_limiter)

    def _build_request(self):
        """Return a libsoup message, with all the right headers.

        :return: A constructed but unsent libsoup message.
        :rtype: Soup.Message
        """
        data = None
        url = self.url

        # urlencode() does not have an option to use quote() instead of
        # quote_plus(), but Twitter requires percent-encoded spaces, and
        # this is harmless to any other protocol.
        params = urlencode(self.params).replace('+', '%20')
        if params:
            if self.method == 'GET':
                # Do a GET with an encoded query string.
                url = '{}?{}'.format(self.url, params)
            else:
                data = params

        message = Soup.Message.new(self.method, url)
        for header, value in self.headers.items():
            message.request_headers.append(header, value)
        if data is not None:
            message.set_request(
                'application/x-www-form-urlencoded; charset=utf-8',
                Soup.MemoryUse.COPY, data, len(data))

        # Possibly do some rate limiting.
        self._rate_limiter.wait(message)
        return message


class Uploader(HTTP):
    """Convenient uploading wrapper."""

    def __init__(self, url, filename, desc, picture_key, desc_key, **kwargs):
        self.url = url
        self.filename = filename
        self.description = desc
        self.picture_key = picture_key
        self.description_key = desc_key
        self.extra_keys = kwargs
        self._rate_limiter = BaseRateLimiter()

    def _build_request(self):
        gfile = Gio.File.new_for_uri(self.filename)
        data = gfile.load_contents(None)[1]
        body = Soup.Buffer.new([byte for byte in data])

        multipart = Soup.Multipart.new('multipart/form-data')
        for key, value in self.extra_keys.items():
            multipart.append_form_string(key, value)
        multipart.append_form_string(self.description_key, self.description)
        multipart.append_form_file(
           self.picture_key, self.filename, 'application/octet-stream', body)
        message = Soup.form_request_new_from_multipart(self.url, multipart)
        return message
