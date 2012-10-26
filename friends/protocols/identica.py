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

"""The Identi.ca protocol plugin."""

__all__ = [
    'Identica',
    ]


from friends.protocols.twitter import Twitter


class Identica(Twitter):
    _api_base = 'http://identi.ca/api/{endpoint}.json'

    _timeline = _api_base.format(endpoint='statuses/{}_timeline')
    _user_timeline = _timeline.format('user') + '?screen_name={}'
    _mentions_timeline = _api_base.format(endpoint='statuses/mentions')

    _destroy = _api_base.format(endpoint='statuses/destroy/{}')
    _retweet = _api_base.format(endpoint='statuses/retweet/{}')

    _search = _api_base.format(endpoint='search')
    _search_result_key = 'results'

    _tweet_permalink = 'http://identi.ca/notice/{tweet_id}'

    def _whoami(self, authdata):
        """Identify the authenticating user."""
        self._account.secret_token = authdata.get('TokenSecret')
        url = self._api_base.format(endpoint='users/show')
        result = self._get_url(url)
        self._account.user_id = result.get('id')
        self._account.user_name = result.get('screen_name')

    def list(self, list_id):
        """Identi.ca does not have this feature."""
        raise NotImplementedError

    def lists(self):
        """Identi.ca does not have this feature."""
        raise NotImplementedError

    def like(self, tweet_id):
        """I get 404s on this in spite of Identi.ca's claim to support it."""
        raise NotImplementedError

    def unlike(self, tweet_id):
        """I get 404s on this in spite of Identi.ca's claim to support it."""
        raise NotImplementedError

    def tag(self, tweet_id):
        """Searching for hashtags gives non-hashtags in the results.

        Eg, whereas twitter.tag('bike') only gives you tweets
        containing '#bike', identica.tag('bike') gives results
        containing both 'bike' and '#bike', which is essentially
        useless. Just use search() instead.
        """
        raise NotImplementedError
