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
from friends.errors import FriendsError


log = logging.getLogger(__name__)


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
        self._account.user_name = '{firstName} {lastName}'.format(**result)

    def _publish_entry(self, entry, stream='messages'):
        """Publish a single update into the Dee.SharedModel."""
        message_id = entry.get('updateKey')

        content = entry.get('updateContent', {})
        person = content.get('person', {})
        name = '{firstName} {lastName}'.format(**person)
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
        values = result.get('values')
        for update in values:
            self._publish_entry(update)
        return self._get_n_rows()

    @feature
    def receive(self):
        """Gather and publish all incoming messages."""
        return self.home()

    def _create_contact(self, connection_json):
        """Build a VCard based on a dict representation of a contact."""
        user_id = connection_json.get('id', '')

        user_fullname = '{firstName} {lastName}'.format(**connection_json)
        user_link = connection_json.get(
            'siteStandardProfileRequest', {}).get('url', '')

        attrs = { 'linkedin-id':   user_id,
                  'linkedin-name': user_fullname,
                  'X-URIS':        user_link }

        return super()._create_contact(user_fullname, None, attrs)

    @feature
    def contacts(self):
        """Retrieve a list of up to 500 LinkedIn connections."""
        # http://developer.linkedin.com/documents/connections-api
        url = self._api_base.format(
            endpoint='people/~/connections',
            token=self._get_access_token())
        result = Downloader(url).get_json()
        connections = result.get('values', [])
        source = self._get_eds_source()

        for connection in connections:
            connection_id = connection.get('id')
            if connection_id != 'private':
                if not self._previously_stored_contact(
                        source, 'linkedin-id', connection_id):
                    self._push_to_eds(self._create_contact(connection))

        return len(connections)

    def delete_contacts(self):
        source = self._get_eds_source()
        return self._delete_service_contacts(source)
