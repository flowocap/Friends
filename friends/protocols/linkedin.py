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


import time
import logging

from friends.utils.avatar import Avatar
from friends.utils.base import Base, feature
from friends.utils.cache import JsonCache
from friends.utils.http import Downloader, Uploader
from friends.utils.time import parsetime, iso8601utc
from friends.errors import FriendsError

log = logging.getLogger(__name__)

class LinkedIn(Base):
    _api_base = 'https://api.linkedin.com/v1/{endpoint}?format=json&secure-urls=true&oauth2_access_token={token}'

    def _whoami(self, authdata):
        """Identify the authenticating user."""
        url = self._api_base.format(
            endpoint='people/~:(id,first-name,last-name)',
            token=self._get_access_token())
        result = Downloader(url).get_json()
        self._account.user_id = result.get('id')
        self._account.user_full_name = '{firstName} {lastName}'.format(**result)

    @feature    
    def receive(self):
        self._get_access_token()
