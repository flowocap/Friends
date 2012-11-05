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

"""Convenient uploading."""


__all__ = [
    'Uploader',
    ]


import json
import logging

from base64 import encodebytes
from gi.repository import Soup, GdkPixbuf
from urllib.parse import urlencode

from friends.utils.download import _soup, _get_charset


log = logging.getLogger(__name__)


class Uploader:
    """Convenient uploading wrapper."""

    def __init__(self, url, filename, description=''):
        self.url = url
        self.filename = filename
        self.description = description

    def send(self):
        data = GdkPixbuf.Pixbuf.new_from_file(self.filename)
        jpeg = data.save_to_bufferv('jpeg', [], [])[1]
        body = Soup.Buffer.new([byte for byte in jpeg])

        multipart = Soup.Multipart.new('multipart/form-data')
        multipart.append_form_string('message', self.description)
        multipart.append_form_file(
            'source', self.filename, 'image/jpeg', body)
        message = Soup.form_request_new_from_multipart(self.url, multipart)
        _soup.send_message(message)
        if message.status_code != 200:
            log.error(
                '{}: {} {}'.format(
                    self.url,
                    message.status_code,
                    message.reason_phrase))
        return message

    def get_json(self):
        # TODO this is very similar to Downloader.get_json, need to
        # generalize these.
        message = self.send()
        payload = message.response_body.flatten().get_data()
        charset = _get_charset(message)
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
