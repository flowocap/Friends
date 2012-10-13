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

"""ur1.ca URL shortener for Friends

macno (Michele Azzolari) - 02/13/2008
"""

__all__ = [
    'PROTOCOL_INFO',
    'URLShortener',
    ]


from xml.etree.ElementTree import fromstring

from friends.shorteners.base import ProtocolBase
from friends.utils.download import Downloader


class _PROTOCOL_INFO(ProtocolBase):
    name = 'ur1.ca'
    version = 0.1
    fqdn = 'http://ur1.ca'


PROTOCOL_INFO = _PROTOCOL_INFO()


class URLShortener:
    def shorten(self, url):
        downloader = Downloader(
            'http://ur1.ca',
            dict(submit='Make it an ur1!', longurl=url))
        response = downloader.get_string()
        # Apparently, the page returned by ur1.ca cannot be parsed, e.g. by
        # xml.etree because of mismatched tags.  Instead, we have to search
        # for a landmark and extract the text manually.  In some sense, this
        # is even more fragile to service changes.
        start = response.index('<p class="success">')
        end = response.index('</p>', start)
        substring = response[start:end+4]
        # Now substring should be parseable.
        element = fromstring(substring)
        return element.find('a').text
