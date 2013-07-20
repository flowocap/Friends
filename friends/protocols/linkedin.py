# friends-dispatcher -- send & receive messages from any social network
# Copyright (C) 2013  Canonical Ltd
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

"""The LinkedIn protocol plugin."""


__all__ = [
    'LinkedIn',
    ]


import logging

from friends.utils.base import Base, feature
from friends.utils.http import Downloader
from friends.utils.time import iso8601utc


log = logging.getLogger(__name__)


def make_fullname(firstName=None, lastName=None, **ignored):
    """Converts dict(firstName='Bob', lastName='Loblaw') into 'Bob Loblaw'."""
    return ' '.join(name for name in (firstName, lastName) if name)


class LinkedIn(Base):
    _api_base = ('https://api.linkedin.com/v1/{endpoint}?format=json' +
                 '&secure-urls=true&oauth2_access_token={token}')

    def _whoami(self, authdata):
        """Identify the authenticating user."""
        # http://developer.linkedin.com/documents/profile-fields
        url = self._api_base.format(
            endpoint='people/~:(id,first-name,last-name)',
            token=self._get_access_token())
        result = Downloader(url).get_json()
        self._account.user_id = result.get('id')
        self._account.user_name = make_fullname(**result)

    def _publish_entry(self, entry, stream='messages'):
        """Publish a single update into the Dee.SharedModel."""
        message_id = entry.get('updateKey')

        content = entry.get('updateContent', {})
        person = content.get('person', {})
        name = make_fullname(**person)
        person_id = person.get('id', '')
        status = person.get('currentStatus')
        picture = person.get('pictureUrl', '')
        url = person.get('siteStandardProfileRequest', {}).get('url', '')
        timestamp = entry.get('timestamp', 0)
        # We need to divide by 1000 here, as LinkedIn's timestamps have
        # milliseconds.
        iso_time = iso8601utc(int(timestamp/1000))

        likes = entry.get('numLikes', 0)

        if None in (message_id, status):
            # Something went wrong; just ignore this malformed message.
            return

        args = dict(
             message_id=message_id,
             stream=stream,
             message=status,
             likes=likes,
             sender_id=person_id,
             sender=name,
             icon_uri=picture,
             url=url,
             timestamp=iso_time
             )

        self._publish(**args)

    @feature
    def home(self):
        """Gather and publish public timeline messages."""
        url = self._api_base.format(
            endpoint='people/~/network/updates',
            token=self._get_access_token()) + '&type=STAT'
        result = Downloader(url).get_json()
        for update in result.get('values', []):
            self._publish_entry(update)
        return self._get_n_rows()

    @feature
    def receive(self):
        """Gather and publish all incoming messages."""
        return self.home()

    @feature
    def contacts(self):
        """Retrieve a list of up to 500 LinkedIn connections."""
        # http://developer.linkedin.com/documents/connections-api
        connections = Downloader(
            url=self._api_base.format(
                endpoint='people/~/connections',
                token=self._get_access_token())
        ).get_json().get('values', [])

        for connection in connections:
            connection_id = connection.get('id', 'private')
            fullname = make_fullname(**connection)
            if connection_id != 'private' and not self._previously_stored_contact(connection_id):
                self._push_to_eds(self._create_contact({
                    'linkedin-id': connection_id,
                    'linkedin-name': fullname,
                    'X-URIS': connection.get(
                        'siteStandardProfileRequest', {}).get('url'),
                    'X-FOLKS-WEB-SERVICES-IDS': {
                        'remote-full-name': fullname,
                        'linkedin-id': connection_id,
                    }}))

        return len(connections)
