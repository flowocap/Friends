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

"""Test the URL shorteners."""

__all__ = [
    'TestShorteners',
    ]


import unittest

from operator import getitem

from friends.shorteners import cligs
from friends.shorteners import isgd
from friends.shorteners import lookup
from friends.shorteners import snipurlcom
from friends.shorteners import tinyurlcom
from friends.shorteners import ur1ca
from friends.shorteners import zima
from friends.testing.mocks import FakeOpen, FakeSoupMessage

try:
    # Python 3.3
    from unittest import mock
except ImportError:
    import mock


@mock.patch('friends.utils.download._soup', mock.Mock())
class TestShorteners(unittest.TestCase):
    """Test the various shorteners, albeit via mocks."""

    @mock.patch('friends.shorteners.base.urlopen', FakeOpen)
    def test_cligs(self):
        # Test the shortener.
        self.assertEqual(
            cligs.URLShortener().shorten('http://www.python.org'),
            '26bfd1ce3401eb01c327ae3385f0c350')

    def test_cligs_protocol(self):
        # Test the PROTOCOL_INFO API.
        self.assertEqual(cligs.PROTOCOL_INFO['name'], 'cli.gs')
        self.assertEqual(cligs.PROTOCOL_INFO['version'], 0.1)
        self.assertEqual(cligs.PROTOCOL_INFO['fqdn'], 'http://cli.gs')
        self.assertEqual(cligs.PROTOCOL_INFO.name, 'cli.gs')
        self.assertEqual(cligs.PROTOCOL_INFO.version, 0.1)
        self.assertEqual(cligs.PROTOCOL_INFO.fqdn, 'http://cli.gs')

    def test_cligs_protocol_missing(self):
        # Bad attributes.
        self.assertRaises(KeyError, getitem, cligs.PROTOCOL_INFO, 'bogus')
        self.assertRaises(AttributeError,
                          getattr, cligs.PROTOCOL_INFO, 'bogus')

    @mock.patch('friends.shorteners.base.urlopen', FakeOpen)
    def test_isgd(self):
        # Test the shortener.
        self.assertEqual(
            isgd.URLShortener().shorten('http://www.python.org'),
            'f6738884feb0d0721c654bb5d09460a4')

    def test_isgd_protocol(self):
        # Test the PROTOCOL_INFO API.
        self.assertEqual(isgd.PROTOCOL_INFO['name'], 'is.gd')
        self.assertEqual(isgd.PROTOCOL_INFO['version'], 0.1)
        self.assertEqual(isgd.PROTOCOL_INFO['fqdn'], 'http://is.gd')
        self.assertEqual(isgd.PROTOCOL_INFO.name, 'is.gd')
        self.assertEqual(isgd.PROTOCOL_INFO.version, 0.1)
        self.assertEqual(isgd.PROTOCOL_INFO.fqdn, 'http://is.gd')

    def test_isgd_protocol_missing(self):
        # Bad attributes.
        self.assertRaises(KeyError, getitem, isgd.PROTOCOL_INFO, 'bogus')
        self.assertRaises(AttributeError,
                          getattr, isgd.PROTOCOL_INFO, 'bogus')

    @mock.patch('friends.shorteners.base.urlopen', FakeOpen)
    def test_snipurlcom(self):
        # Test the shortener.
        self.assertEqual(
            snipurlcom.URLShortener().shorten('http://www.python.org'),
            'c302cf647e1f99efec11cb7f7028154d')

    def test_snipurlcom_protocol(self):
        # Test the PROTOCOL_INFO API.
        self.assertEqual(snipurlcom.PROTOCOL_INFO['name'], 'snipurl.com')
        self.assertEqual(snipurlcom.PROTOCOL_INFO['version'], 0.1)
        self.assertEqual(snipurlcom.PROTOCOL_INFO['fqdn'], 'http://snipr.com')
        self.assertEqual(snipurlcom.PROTOCOL_INFO.name, 'snipurl.com')
        self.assertEqual(snipurlcom.PROTOCOL_INFO.version, 0.1)
        self.assertEqual(snipurlcom.PROTOCOL_INFO.fqdn, 'http://snipr.com')

    def test_snipurlcom_protocol_missing(self):
        # Bad attributes.
        self.assertRaises(KeyError, getitem, snipurlcom.PROTOCOL_INFO, 'bogus')
        self.assertRaises(AttributeError,
                          getattr, snipurlcom.PROTOCOL_INFO, 'bogus')

    @mock.patch('friends.shorteners.base.urlopen', FakeOpen)
    def test_tinyurlcom(self):
        # Test the shortener.
        self.assertEqual(
            tinyurlcom.URLShortener().shorten('http://www.python.org'),
            '485c4e53bf5372c1b4c161624b4b374d')

    def test_tinyurlcom_protocol(self):
        # Test the PROTOCOL_INFO API.
        self.assertEqual(tinyurlcom.PROTOCOL_INFO['name'], 'tinyurl.com')
        self.assertEqual(tinyurlcom.PROTOCOL_INFO['version'], 0.1)
        self.assertEqual(tinyurlcom.PROTOCOL_INFO['fqdn'],
                         'http://tinyurl.com')
        self.assertEqual(tinyurlcom.PROTOCOL_INFO.name, 'tinyurl.com')
        self.assertEqual(tinyurlcom.PROTOCOL_INFO.version, 0.1)
        self.assertEqual(tinyurlcom.PROTOCOL_INFO.fqdn, 'http://tinyurl.com')

    def test_tinyurlcom_protocol_missing(self):
        # Bad attributes.
        self.assertRaises(KeyError, getitem, tinyurlcom.PROTOCOL_INFO, 'bogus')
        self.assertRaises(AttributeError,
                          getattr, tinyurlcom.PROTOCOL_INFO, 'bogus')

    @mock.patch('friends.utils.download.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'ur1ca.html'))
    def test_ur1ca(self):
        # Test the shortener.
        self.assertEqual(
            ur1ca.URLShortener().shorten('http://www.python.org'),
            'http://ur1.ca/0jk9n')

    def test_ur1ca_protocol(self):
        # Test the PROTOCOL_INFO API.
        self.assertEqual(ur1ca.PROTOCOL_INFO['name'], 'ur1.ca')
        self.assertEqual(ur1ca.PROTOCOL_INFO['version'], 0.1)
        self.assertEqual(ur1ca.PROTOCOL_INFO['fqdn'], 'http://ur1.ca')
        self.assertEqual(ur1ca.PROTOCOL_INFO.name, 'ur1.ca')
        self.assertEqual(ur1ca.PROTOCOL_INFO.version, 0.1)
        self.assertEqual(ur1ca.PROTOCOL_INFO.fqdn, 'http://ur1.ca')

    def test_ur1ca_protocol_missing(self):
        # Bad attributes.
        self.assertRaises(KeyError, getitem, ur1ca.PROTOCOL_INFO, 'bogus')
        self.assertRaises(AttributeError,
                          getattr, ur1ca.PROTOCOL_INFO, 'bogus')

    @mock.patch('friends.shorteners.base.urlopen', FakeOpen)
    def test_zima(self):
        # Test the shortener.
        self.assertEqual(
            zima.URLShortener().shorten('http://www.python.org'),
            '0e66bcfd91c5a01308bbe7508c660f3e')

    def test_zima_protocol(self):
        # Test the PROTOCOL_INFO API.
        self.assertEqual(zima.PROTOCOL_INFO['name'], 'zi.ma')
        self.assertEqual(zima.PROTOCOL_INFO['version'], 0.1)
        self.assertEqual(zima.PROTOCOL_INFO['fqdn'], 'http://zi.ma')
        self.assertEqual(zima.PROTOCOL_INFO.name, 'zi.ma')
        self.assertEqual(zima.PROTOCOL_INFO.version, 0.1)
        self.assertEqual(zima.PROTOCOL_INFO.fqdn, 'http://zi.ma')

    def test_zima_protocol_missing(self):
        # Bad attributes.
        self.assertRaises(KeyError, getitem, zima.PROTOCOL_INFO, 'bogus')
        self.assertRaises(AttributeError,
                          getattr, zima.PROTOCOL_INFO, 'bogus')

    @mock.patch('friends.shorteners.base.urlopen', FakeOpen)
    def test_enabled_lookup(self):
        # Look up an enabled shortener.
        shortener = lookup.lookup('tinyurl.com')
        self.assertEqual(
            shortener.shorten('http://www.python.org'),
            '485c4e53bf5372c1b4c161624b4b374d')

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

    def test_is_not_shortened(self):
        # Test a URL that has not been shortened.
        self.assertFalse(lookup.is_shortened('http://www.python.org/bar'))
