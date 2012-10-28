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

"""Time utilities."""

__all__ = [
    'parsetime',
    'iso8601utc',
    ]


import re
import time
import locale

from calendar import timegm
from contextlib import contextmanager
from datetime import datetime, timedelta


# Date time formats.  Assume no microseconds and no timezone.
ISO8601_FORMAT = '%Y-%m-%dT%H:%M:%S'
ISO8601_UTC_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
TWITTER_FORMAT = '%a %b %d %H:%M:%S %Y'
IDENTICA_FORMAT = '%a, %d %b %Y %H:%M:%S'


@contextmanager
def _c_locale():
    locale.setlocale(locale.LC_TIME, 'C')
    try:
        yield
    finally:
        locale.setlocale(locale.LC_TIME, '')


def _from_iso8601(t):
    return datetime.strptime(t, ISO8601_FORMAT)


def _from_iso8601_utc(t):
    return datetime.strptime(t, ISO8601_UTC_FORMAT)


def _from_iso8601alt(t):
    return datetime.strptime(t, ISO8601_FORMAT.replace('T', ' '))


def _from_twitter(t):
    return datetime.strptime(t, TWITTER_FORMAT)


def _from_identica(t):
    return datetime.strptime(t, IDENTICA_FORMAT)


def _fromutctimestamp(t):
    return datetime.utcfromtimestamp(float(t))


PARSERS = (_from_iso8601, _from_iso8601_utc, _from_iso8601alt, _from_twitter,
           _from_identica, _fromutctimestamp)


def parsetime(t):
    """Parse an ISO 8601 datetime string and return seconds since epoch.

    This accepts either a naive (i.e. timezone-less) string or a timezone
    aware string.  The timezone must start with a + or - and must be followed
    by exactly four digits.  This string is parsed and converted to UTC.  This
    value is then converted to an integer seconds since epoch.
    """
    with _c_locale():
        # In Python 3.2, strptime() is implemented in Python, so in order to
        # parse the UTC timezone (e.g. +0000), you'd think we could just
        # append %z on the format.  We can't rely on it though because of the
        # non-ISO 8601 formats that some APIs use (I'm looking at you Twitter
        # and Facebook).  We'll use a regular expression to tear out the
        # timezone string and do the conversion ourselves.
        tz_offset = None
        def capture_tz(match_object):
            nonlocal tz_offset
            tz_string = match_object.group('tz')
            if tz_string is not None:
                # It's possible that we'll see more than one substring
                # matching the timezone pattern.  It should be highly unlikely
                # so we won't test for that here, at least not now.
                #
                # The tz_offset is positive, so it must be subtracted from the
                # naive datetime in order to return it to UTC.  E.g.
                #
                #   13:00 -0400 is 17:00 +0000
                # or
                #   1300 - (-0400 / 100)
                if tz_offset is not None:
                    # This is not the first time we're seeing a timezone.
                    raise ValueError('Unsupported time string: {0}'.format(t))
                tz_offset = timedelta(hours=int(tz_string) / 100)
            # Return the empty string so as to remove the timezone pattern
            # from the string we're going to parse.
            return ''
        # Parse the time string, calling capture_tz() for each timezone match
        # group we find.  The callback itself will ensure we see no more
        # than one timezone string.
        naive_t = re.sub(r'[ ]*(?P<tz>[-+]\d{4})', capture_tz, t)
        if tz_offset is None:
            # No timezone string was found.
            tz_offset = timedelta()
        for parser in PARSERS:
            try:
                parsed_dt = parser(naive_t)
            except ValueError:
                pass
            else:
                break
        else:
            # Nothing matched.
            raise ValueError('Unsupported time string: {0}'.format(t))
        # We must have gotten a valid datetime.  Normalize out the timezone
        # offset and convert it to Epoch seconds.  Use timegm() to give us
        # UTC-based conversion from a struct_time to seconds-since-epoch.
        utc_dt = parsed_dt - tz_offset
        timetup = utc_dt.timetuple()
        return int(timegm(timetup))


def iso8601utc(timestamp, timezone_offset=0, sep='T'):
    """Convert from a Unix epoch timestamp to an ISO 8601 date time string.

    :param timestamp: Unix epoch timestamp in seconds.
    :type timestamp: float
    :param timezone_offset: Offset in hours*100 east/west of UTC.  E.g. -400
        means 4 hours west of UTC; 130 means 1.5 hours east of UTC.
    :type timezone_offset: int
    :param sep: ISO 8601 separator placed between the date and time portions
        of the result.
    :type sep: string of length 1.
    :return: ISO 8601 datetime string.
    :rtype: string
    """
    dt = datetime.utcfromtimestamp(timestamp)
    hours_east, minutes_east = divmod(timezone_offset, 100)
    correction = timedelta(hours=hours_east, minutes=minutes_east)
    # Subtract the correction to move closer to UTC, since the offset is
    # positive when east of UTC and negative when west of UTC.
    return (dt - correction).isoformat(sep=sep) + ('Z' if sep == 'T' else '')
