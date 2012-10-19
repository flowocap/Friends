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

"""The FourSquare protocol plugin."""

__all__ = [
    'FourSquare',
    ]


import logging

from friends.errors import AuthorizationError
from friends.utils.base import Base, feature
from friends.utils.download import get_json
from friends.utils.time import iso8601utc


log = logging.getLogger(__name__)


# The '&v=YYYYMMDD' defines the date that the API was last confirmed to be
# functional, and is used by foursquare to indicate how old our software is.
# In the event that they change their API, an old 'v' date will tell them to
# give us the old, deprecated API behaviors, giving us some time to be
# notified of API breakage and update accordingly.  If you're working on this
# code and you don't see any bugs with foursquare then feel free to update the
# date here.
API_BASE = 'https://api.foursquare.com/v2/'
TOKEN ='?oauth_token={access_token}&v=20120917'
SELF_URL = API_BASE + 'users/self' + TOKEN
CHECKIN_URL = API_BASE + 'checkins/{checkin_id}' + TOKEN
RECENT_URL = API_BASE + 'checkins/recent' + TOKEN

HTML_PREFIX = 'https://foursquare.com/'
USER_URL = HTML_PREFIX + 'user/{user_id}'
VENUE_URL = HTML_PREFIX + 'venue/{venue_id}'
SPACE = ' '


def _full_name(user):
    names = (user.get('firstName'), user.get('lastName'))
    return SPACE.join(name for name in names if name)


class FourSquare(Base):
    def _whoami(self, authdata):
        """Identify the authenticating user."""
        data = get_json(
            SELF_URL.format(access_token=self._account.access_token))
        user = data.get('response', {}).get('user', {})
        self._account.secret_token = authdata.get('TokenSecret')
        self._account.user_name = _full_name(user)
        self._account.user_id = user.get('id')

    @feature
    def receive(self):
        """Gets a list of each friend's most recent check-ins."""
        token = self._get_access_token()
        if token is None:
            raise AuthorizationError(
                self._account, 'No FourSquare user id available')
        # We are successfully logged in.
        result = get_json(RECENT_URL.format(access_token=token))

        response_code = result.get('meta', {}).get('code')
        if response_code != 200:
            log.error('FourSquare: Error: {}'.format(result))
            return

        checkins = result.get('response', {}).get('recent', [])
        for checkin in checkins:
            user = checkin.get('user', {})
            avatar = user.get('photo', {})
            avatar_url = '{prefix}100x100{suffix}'.format(**avatar)
            checkin_id = checkin.get('id', '')
            tz_offset = checkin.get('timeZoneOffset', 0)
            epoch = checkin.get('createdAt', 0)
            self._publish(
                message_id=checkin_id,
                stream='messages',
                sender=_full_name(user),
                from_me=(user.get('relationship') == 'self'),
                timestamp=iso8601utc(epoch, tz_offset),
                message=checkin.get('shout', ''),
                likes=checkin.get('likes', {}).get('count', 0),
                icon_uri=avatar_url,
                url=CHECKIN_URL.format(access_token=token,
                                       checkin_id=checkin_id),
                )
