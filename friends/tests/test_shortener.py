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

from friends.utils.shorteners import lookup, is_shortened
from friends.tests.mocks import FakeSoupMessage, mock


@mock.patch('friends.utils.http._soup', mock.Mock())
class TestShorteners(unittest.TestCase):
    """Test the various shorteners, albeit via mocks."""

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_isgd(self):
        # Test the shortener.
        self.assertEqual(
            lookup('is.gd').shorten('http://www.python.org'),
            'http://sho.rt/')

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_ougd(self):
        # Test the shortener.
        self.assertEqual(
            lookup('ou.gd').shorten('http://www.python.org'),
            'http://sho.rt/')

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_linkeecom(self):
        # Test the shortener.
        self.assertEqual(
            lookup('linkee.com').shorten('http://www.python.org'),
            'http://sho.rt/')

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_tinyurlcom(self):
        # Test the shortener.
        self.assertEqual(
            lookup('tinyurl.com').shorten('http://www.python.org'),
            'http://sho.rt/')

    def test_missing_or_disabled_lookup(self):
        # Looking up a non-existent or disabled shortener gives you one that
        # returns the original url back unchanged.
        self.assertEqual(
            lookup('nonexistant').shorten('http://www.python.org'),
            'http://www.python.org')

    def test_is_shortened(self):
        # Test a URL that has been shortened.
        self.assertTrue(is_shortened('http://tinyurl.com/foo'))
        self.assertTrue(is_shortened('http://is.gd/foo'))
        self.assertTrue(is_shortened('http://linkee.com/foo'))
        self.assertTrue(is_shortened('http://ou.gd/foo'))

    def test_is_not_shortened(self):
        # Test a URL that has not been shortened.
        self.assertFalse(is_shortened('http://www.python.org/bar'))

    @mock.patch('friends.utils.shorteners.Downloader')
    def test_isgd_quoted_properly(self, dl_mock):
        lookup('is.gd').shorten('http://example.com/~user/stuff/+things')
        dl_mock.assert_called_once_with(
            'http://is.gd/api.php?longurl=http%3A%2F%2Fexample.com'
            '%2F%7Euser%2Fstuff%2F%2Bthings')

    @mock.patch('friends.utils.shorteners.Downloader')
    def test_ougd_quoted_properly(self, dl_mock):
        lookup('ou.gd').shorten('http://example.com/~user/stuff/+things')
        dl_mock.assert_called_once_with(
            'http://ou.gd/api.php?format=simple&action=shorturl&url='
            'http%3A%2F%2Fexample.com%2F%7Euser%2Fstuff%2F%2Bthings')

    @mock.patch('friends.utils.shorteners.Downloader')
    def test_linkeecom_quoted_properly(self, dl_mock):
        lookup('linkee.com').shorten('http://example.com/~user/stuff/+things')
        dl_mock.assert_called_once_with(
            'http://api.linkee.com/1.0/shorten?format=text&input='
            'http%3A%2F%2Fexample.com%2F%7Euser%2Fstuff%2F%2Bthings')

    @mock.patch('friends.utils.shorteners.Downloader')
    def test_tinyurl_quoted_properly(self, dl_mock):
        lookup('tinyurl.com').shorten('http://example.com/~user/stuff/+things')
        dl_mock.assert_called_once_with(
            'http://tinyurl.com/api-create.php?url=http%3A%2F%2Fexample.com'
            '%2F%7Euser%2Fstuff%2F%2Bthings')

    @mock.patch('friends.utils.shorteners.Downloader')
    def test_dont_over_shorten(self, dl_mock):
        lookup('tinyurl.com').shorten('http://tinyurl.com/page_id')
        lookup('linkee.com').shorten('http://ou.gd/page_id')
        lookup('is.gd').shorten('http://is.gd/page_id')
        lookup('ou.gd').shorten('http://linkee.com/page_id')
        self.assertEqual(dl_mock.call_count, 0)
