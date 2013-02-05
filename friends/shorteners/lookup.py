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

"""Look up a URL shortener by name."""


__all__ = [
    'PROTOCOLS',
    'is_shortened',
    'lookup',
    ]


from friends.shorteners import cligs
from friends.shorteners import isgd
#from friends.shorteners import snipurlcom
from friends.shorteners import tinyurlcom
from friends.shorteners import ur1ca
#from friends.shorteners import zima


PROTOCOLS = {
    'cli.gs': cligs,
    'is.gd': isgd,
    #'snipurl.com': snipurlcom,
    'tinyurl.com': tinyurlcom,
    'ur1.ca': ur1ca,
    #'zi.ma': zima,
    }


class NoShortener:
    """The default URL 'shortener' which doesn't shorten at all.

    If the chosen shortener isn't found, or is disabled, then this one is
    returned.  It supports the standard API but just returns the original URL
    unchanged.
    """

    def shorten(self, url):
        return url


def lookup(name):
    """Look up a URL shortener by name.

    :param name: The name of a shortener.
    :type name: string
    :return: An object supporting the `shorten(url)` method.
    """
    module = PROTOCOLS.get(name)
    if module is None:
        return NoShortener()
    return module.URLShortener()


def is_shortened(url):
    """True if the URL has been shortened by a known shortener."""
    # What if we tried to URL shorten http://tinyurl.com/something???
    for module in PROTOCOLS.values():
        if url.startswith(module.PROTOCOL_INFO.fqdn):
            return True
    return False
