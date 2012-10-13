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

"""Test the time parsing utilities."""

__all__ = [
    'TestParseTime',
    ]


import unittest

from friends.utils.time import iso8601utc, parsetime


class TestParseTime(unittest.TestCase):
    def test_type(self):
        # parsetime() should always return int seconds since the epoch.
        self.assertTrue(isinstance(parsetime('2012-05-10T13:36:45'), int))

    def test_parse_naive(self):
        # ISO 8601 standard format without timezone.
        self.assertEqual(parsetime('2012-05-10T13:36:45'), 1336657005)

    def test_parse_utctz(self):
        # ISO 8601 standard format with UTC timezone.
        self.assertEqual(parsetime('2012-05-10T13:36:45 +0000'), 1336657005)

    def test_parse_naive_altsep(self):
        # ISO 8601 alternative format without timezone.
        self.assertEqual(parsetime('2012-05-10 13:36:45'), 1336657005)

    def test_parse_utctz_altsep(self):
        # ISO 8601 alternative format with UTC timezone.
        self.assertEqual(parsetime('2012-05-10T13:36:45 +0000'), 1336657005)

    def test_bad_time_string(self):
        # Odd unsupported format.
        self.assertRaises(ValueError, parsetime, '2012/05/10 13:36:45')

    def test_non_utc(self):
        # Non-UTC timezones are get converted to UTC, before conversion to
        # epoch seconds.
        self.assertEqual(parsetime('2012-05-10T13:36:45 -0400'), 1336671405)

    def test_nonstandard_twitter(self):
        # Sigh.  Twitter has to be different.
        self.assertEqual(parsetime('Thu May 10 13:36:45 +0000 2012'),
                         1336657005)

    def test_nonstandard_twitter_non_utc(self):
        # Sigh.  Twitter has to be different.
        self.assertEqual(parsetime('Thu May 10 13:36:45 -0400 2012'),
                         1336671405)

    def test_nonstandard_facebook(self):
        # Sigh.  Facebook gets close, but no cigar.
        self.assertEqual(parsetime('2012-05-10T13:36:45+0000'), 1336657005)

    def test_identica(self):
        self.assertEqual(parsetime('Fri, 05 Oct 2012 08:46:39'), 1349426799)

    def test_multiple_timezones(self):
        # Multiple timezone strings are not supported.
        self.assertRaises(ValueError, parsetime,
                          '2012-05-10T13:36:45 +0000 -0400')

    def test_iso8601_utc(self):
        # Convert a Unix epoch time seconds in UTC (the default) to an ISO
        # 8601 UTC date time string.
        self.assertEqual(iso8601utc(1336657005), '2012-05-10T13:36:45')

    def test_iso8601_utc_with_sep(self):
        # Convert a Unix epoch time seconds in UTC (the default) to an ISO
        # 8601 UTC date time string with a different separator.
        self.assertEqual(iso8601utc(1336657005, sep=' '),
                         '2012-05-10 13:36:45')

    def test_iso8601_west_of_utc(self):
        # Convert a Unix epoch time seconds plus an offset to an ISO 8601 UTC
        # date time string.
        self.assertEqual(iso8601utc(1336657005, -400), '2012-05-10T17:36:45')

    def test_iso8601_west_of_utc_with_sep(self):
        # Convert a Unix epoch time seconds plus an offset to an ISO 8601 UTC
        # date time string, with a different separator.
        self.assertEqual(iso8601utc(1336657005, -400, sep= ' '),
                         '2012-05-10 17:36:45')

    def test_iso8601_east_of_utc(self):
        # Convert a Unix epoch time seconds plus an offset to an ISO 8601 UTC
        # date time string.
        self.assertEqual(iso8601utc(1336657005, 130), '2012-05-10T12:06:45')

    def test_iso8601_east_of_utc_with_sep(self):
        # Convert a Unix epoch time seconds plus an offset to an ISO 8601 UTC
        # date time string, with a different separator.
        self.assertEqual(iso8601utc(1336657005, 130, sep= ' '),
                         '2012-05-10 12:06:45')
