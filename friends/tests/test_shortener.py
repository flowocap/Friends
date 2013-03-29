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

from friends.utils.shorteners import Short
from friends.tests.mocks import FakeSoupMessage, mock


@mock.patch('friends.utils.http._soup', mock.Mock())
class TestShorteners(unittest.TestCase):
    """Test the various shorteners, albeit via mocks."""

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_isgd(self):
        self.assertEqual(
            Short('is.gd').make('http://www.python.org'),
            'http://sho.rt/')

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_ougd(self):
        self.assertEqual(
            Short('ou.gd').make('http://www.python.org'),
            'http://sho.rt/')

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_linkeecom(self):
        self.assertEqual(
            Short('linkee.com').make('http://www.python.org'),
            'http://sho.rt/')

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'short.dat'))
    def test_tinyurlcom(self):
        self.assertEqual(
            Short('tinyurl.com').make('http://www.python.org'),
            'http://sho.rt/')

    def test_missing_or_disabled_lookup(self):
        # Looking up a non-existent or disabled shortener gives you one that
        # returns the original url back unchanged.
        self.assertEqual(
            Short('nonexistant').make('http://www.python.org'),
            'http://www.python.org')
        self.assertEqual(
            Short().make('http://www.python.org'),
            'http://www.python.org')

    def test_is_shortened(self):
        # Test URLs that have been shortened.
        self.assertTrue(Short.already('http://tinyurl.com/foo'))
        self.assertTrue(Short.already('http://is.gd/foo'))
        self.assertTrue(Short.already('http://linkee.com/foo'))
        self.assertTrue(Short.already('http://ou.gd/foo'))

    def test_is_not_shortened(self):
        # Test a URL that has not been shortened.
        self.assertFalse(Short.already('http://www.python.org/bar'))

    @mock.patch('friends.utils.shorteners.Downloader')
    def test_isgd_quoted_properly(self, dl_mock):
        Short('is.gd').make('http://example.com/~user/stuff/+things')
        dl_mock.assert_called_once_with(
            'http://is.gd/api.php?longurl=http%3A%2F%2Fexample.com'
            '%2F%7Euser%2Fstuff%2F%2Bthings')

    @mock.patch('friends.utils.shorteners.Downloader')
    def test_ougd_quoted_properly(self, dl_mock):
        Short('ou.gd').make('http://example.com/~user/stuff/+things')
        dl_mock.assert_called_once_with(
            'http://ou.gd/api.php?format=simple&action=shorturl&url='
            'http%3A%2F%2Fexample.com%2F%7Euser%2Fstuff%2F%2Bthings')

    @mock.patch('friends.utils.shorteners.Downloader')
    def test_linkeecom_quoted_properly(self, dl_mock):
        Short('linkee.com').make(
            'http://example.com/~user/stuff/+things')
        dl_mock.assert_called_once_with(
            'http://api.linkee.com/1.0/shorten?format=text&input='
            'http%3A%2F%2Fexample.com%2F%7Euser%2Fstuff%2F%2Bthings')

    @mock.patch('friends.utils.shorteners.Downloader')
    def test_tinyurl_quoted_properly(self, dl_mock):
        Short('tinyurl.com').make(
            'http://example.com/~user/stuff/+things')
        dl_mock.assert_called_once_with(
            'http://tinyurl.com/api-create.php?url=http%3A%2F%2Fexample.com'
            '%2F%7Euser%2Fstuff%2F%2Bthings')

    @mock.patch('friends.utils.shorteners.Downloader')
    def test_dont_over_shorten(self, dl_mock):
        Short('tinyurl.com').make('http://tinyurl.com/page_id')
        Short('linkee.com').make('http://ou.gd/page_id')
        Short('is.gd').make('http://is.gd/page_id')
        Short('ou.gd').make('http://linkee.com/page_id')
        self.assertEqual(dl_mock.call_count, 0)
