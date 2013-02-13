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

"""Test the URL shorteners."""

__all__ = [
    'TestShorteners',
    ]


import unittest

from operator import getitem

from friends.shorteners import isgd, ougd, linkeecom, lookup, tinyurlcom
from friends.tests.mocks import FakeSoupMessage, mock


@mock.patch('friends.utils.http._soup', mock.Mock())
class TestShorteners(unittest.TestCase):
    """Test the various shorteners, albeit via mocks."""

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_isgd(self):
        # Test the shortener.
        self.assertEqual(
            isgd.URLShortener().shorten('http://www.python.org'),
            'http://sho.rt/')

    def test_isgd_protocol(self):
        self.assertEqual(isgd.URLShortener.name, 'is.gd')
        self.assertEqual(isgd.URLShortener.fqdn, 'http://is.gd')

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_ougd(self):
        # Test the shortener.
        self.assertEqual(
            ougd.URLShortener().shorten('http://www.python.org'),
            'http://sho.rt/')

    def test_ougd_protocol(self):
        self.assertEqual(ougd.URLShortener.name, 'ou.gd')
        self.assertEqual(ougd.URLShortener.fqdn, 'http://ou.gd')

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_linkeecom(self):
        # Test the shortener.
        self.assertEqual(
            linkeecom.URLShortener().shorten('http://www.python.org'),
            'http://sho.rt/')

    def test_linkeecom_protocol(self):
        self.assertEqual(linkeecom.URLShortener.name, 'linkee.com')
        self.assertEqual(linkeecom.URLShortener.fqdn, 'http://linkee.com')

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_tinyurlcom(self):
        # Test the shortener.
        self.assertEqual(
            tinyurlcom.URLShortener().shorten('http://www.python.org'),
            'http://sho.rt/')

    def test_tinyurlcom_protocol(self):
        self.assertEqual(tinyurlcom.URLShortener.name, 'tinyurl.com')
        self.assertEqual(tinyurlcom.URLShortener.fqdn, 'http://tinyurl.com')

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_enabled_lookup(self):
        # Look up an enabled shortener.
        shortener = lookup.lookup('tinyurl.com')
        self.assertEqual(
            shortener.shorten('http://www.python.org'),
            'http://sho.rt/')

    def test_missing_or_disabled_lookup(self):
        # Looking up a non-existent or disabled shortener gives you one that
        # returns the original url back unchanged.
        shortener = lookup.lookup('dummy')
        self.assertEqual(
            shortener.shorten('http://www.python.org'),
            'http://www.python.org')

    def test_is_shortened(self):
        # Test a URL that has been shortened.
        self.assertTrue(lookup.is_shortened('http://tinyurl.com/foo'))
        self.assertTrue(lookup.is_shortened('http://is.gd/foo'))
        self.assertTrue(lookup.is_shortened('http://linkee.com/foo'))
        self.assertTrue(lookup.is_shortened('http://ou.gd/foo'))

    def test_is_not_shortened(self):
        # Test a URL that has not been shortened.
        self.assertFalse(lookup.is_shortened('http://www.python.org/bar'))
