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
    'SHORTENERS',
    'is_shortened',
    'lookup',
    ]


import re

from urllib.parse import quote

from friends.utils.http import Downloader


class Shortener:
    """Each instance of this class represents a unique shortening service.

    Once instantiated, you can call the .shorten(url) instance method
    to have your URLs shortened easily.
    """
    def __init__(self, template):
        """Define which shortening service this instance will use."""
        self.template = template

    def shorten(self, url):
        """Return the shortened URL by querying the shortening service."""
        if is_shortened(url):
            return url
        return Downloader(
            self.template.format(quote(url, safe=''))).get_string().strip()


class NullShortener(Shortener):
    """The default URL 'shortener' which doesn't shorten at all.

    If the chosen shortener isn't found, or is disabled, then this one is
    returned.  It supports the standard API but just returns the original URL
    unchanged.
    """
    def shorten(self, url):
        return url


# These strings define the shortening services. If you want to add a
# new shortener to this list, the shortening service must take the URL
# as a parameter, and return the plaintext URL as the result. No JSON
# or XML parsing is supported. The strings below must contain exactly
# one instance of '{}' to represent where the long URL goes in the
# service. This is typically at the very end, but doesn't have to be.
URLS = {
    'is.gd':       'http://is.gd/api.php?longurl={}',
    'linkee.com':  'http://api.linkee.com/1.0/shorten?format=text&input={}',
    'ou.gd':       'http://ou.gd/api.php?format=simple&action=shorturl&url={}',
    'tinyurl.com': 'http://tinyurl.com/api-create.php?url={}',
    }


# Returns None if the URL does not begin with a known shortener,
# returns a match object otherwise. The match object evaluates as
# True, so the return value here can be truth-tested if all you care
# about is "matched or not?"
is_shortened = re.compile(
    r'https?://({})/'.format('|'.join(sorted(URLS)))).match


SHORTENERS = {domain: Shortener(url) for domain, url in URLS.items()}


def lookup(domain):
    """Look up a URL shortener by domain name."""
    return SHORTENERS.get(domain, NullShortener(None))
