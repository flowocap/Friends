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

"""Test the Identica plugin."""


__all__ = [
    'TestIdentica',
    ]


import os
import tempfile
import unittest
import shutil

from friends.protocols.identica import Identica
from friends.tests.mocks import FakeAccount, LogMock, TestModel, mock
from friends.utils.cache import JsonCache
from friends.errors import AuthorizationError


@mock.patch('friends.utils.http._soup', mock.Mock())
@mock.patch('friends.utils.base.notify', mock.Mock())
@mock.patch('friends.utils.base.Model', TestModel)
class TestIdentica(unittest.TestCase):
    """Test the Identica API."""

    def setUp(self):
        self._temp_cache = tempfile.mkdtemp()
        self._root = JsonCache._root = os.path.join(
            self._temp_cache, '{}.json')
        self.account = FakeAccount()
        self.protocol = Identica(self.account)
        self.log_mock = LogMock('friends.utils.base',
                                'friends.protocols.twitter')

    def tearDown(self):
        # Ensure that any log entries we haven't tested just get consumed so
        # as to isolate out test logger from other tests.
        self.log_mock.stop()
        shutil.rmtree(self._temp_cache)

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Accounts')
    @mock.patch.dict('friends.utils.authentication.__dict__', LOGIN_TIMEOUT=1)
    @mock.patch('friends.utils.authentication.Signon.AuthSession.new')
    @mock.patch('friends.utils.http.Downloader.get_json',
                return_value=None)
    def test_unsuccessful_authentication(self, *mocks):
        self.assertRaises(AuthorizationError, self.protocol._login)
        self.assertIsNone(self.account.user_name)
        self.assertIsNone(self.account.user_id)

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Accounts')
    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(AccessToken='some clever fake data',
                                  TokenSecret='sssssshhh!'))
    def test_successful_authentication(self, *mocks):
        get_url = self.protocol._get_url = mock.Mock(
            return_value=dict(id='1234', screen_name='therealrobru'))
        self.assertTrue(self.protocol._login())
        self.assertEqual(self.account.user_name, 'therealrobru')
        self.assertEqual(self.account.user_id, '1234')
        self.assertEqual(self.account.access_token, 'some clever fake data')
        self.assertEqual(self.account.secret_token, 'sssssshhh!')
        get_url.assert_called_once_with('http://identi.ca/api/users/show.json')

    def test_mentions(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.mentions()

        publish.assert_called_with('tweet', stream='mentions')
        get_url.assert_called_with(
            'http://identi.ca/api/statuses/mentions.json?count=50')

    def test_user(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.user()

        publish.assert_called_with('tweet', stream='messages')
        get_url.assert_called_with(
            'http://identi.ca/api/statuses/user_timeline.json?screen_name=')

    def test_list(self):
        self.protocol._get_url = mock.Mock(return_value=['tweet'])
        self.protocol._publish_tweet = mock.Mock()
        self.assertRaises(NotImplementedError,
                          self.protocol.list, 'some_list_id')

    def test_lists(self):
        self.protocol._get_url = mock.Mock(
            return_value=[dict(id_str='twitlist')])
        self.protocol.list = mock.Mock()
        self.assertRaises(NotImplementedError, self.protocol.lists)

    def test_private(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=['tweet'])
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.private()

        publish.assert_called_with('tweet', stream='private')
        self.assertEqual(
            get_url.mock_calls,
            [mock.call('http://identi.ca/api/direct_messages.json?count=50'),
             mock.call('http://identi.ca/api/direct_messages' +
                       '/sent.json?count=50')])

    def test_send_private(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.send_private('pumpichank', 'Are you mocking me?')

        publish.assert_called_with('tweet', stream='private')
        get_url.assert_called_with(
            'http://identi.ca/api/direct_messages/new.json',
            dict(text='Are you mocking me?', screen_name='pumpichank'))

    def test_send(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.send('Hello, twitterverse!')

        publish.assert_called_with('tweet')
        get_url.assert_called_with(
            'http://identi.ca/api/statuses/update.json',
            dict(status='Hello, twitterverse!'))

    def test_send_thread(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.send_thread(
            '1234',
            'Why yes, I would love to respond to your tweet @pumpichank!')

        publish.assert_called_with('tweet')
        get_url.assert_called_with(
            'http://identi.ca/api/statuses/update.json',
            dict(status=
                 'Why yes, I would love to respond to your tweet @pumpichank!',
                 in_reply_to_status_id='1234'))

    def test_delete(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._unpublish = mock.Mock()

        self.protocol.delete('1234')

        publish.assert_called_with('1234')
        get_url.assert_called_with(
            'http://identi.ca/api/statuses/destroy/1234.json',
            dict(trim_user='true'))

    def test_retweet(self):
        get_url = self.protocol._get_url = mock.Mock(return_value='tweet')
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.retweet('1234')

        publish.assert_called_with('tweet')
        get_url.assert_called_with(
            'http://identi.ca/api/statuses/retweet/1234.json',
            dict(trim_user='true'))

    def test_unfollow(self):
        get_url = self.protocol._get_url = mock.Mock()

        self.protocol.unfollow('pumpichank')

        get_url.assert_called_with(
            'http://identi.ca/api/friendships/destroy.json',
            dict(screen_name='pumpichank'))

    def test_follow(self):
        get_url = self.protocol._get_url = mock.Mock()

        self.protocol.follow('pumpichank')

        get_url.assert_called_with(
            'http://identi.ca/api/friendships/create.json',
            dict(screen_name='pumpichank', follow='true'))

    def test_like(self):
        self.protocol._get_url = mock.Mock()
        self.assertRaises(NotImplementedError, self.protocol.like, '1234')

    def test_unlike(self):
        self.protocol._get_url = mock.Mock()
        self.assertRaises(NotImplementedError, self.protocol.unlike, '1234')

    def test_tag(self):
        self.protocol._get_url = mock.Mock(
            return_value=dict(statuses=['tweet']))
        self.protocol._publish_tweet = mock.Mock()
        self.assertRaises(NotImplementedError, self.protocol.tag, 'hashtag')

    def test_search(self):
        get_url = self.protocol._get_url = mock.Mock(
            return_value=dict(results=['tweet']))
        publish = self.protocol._publish_tweet = mock.Mock()

        self.protocol.search('hello')

        publish.assert_called_with('tweet', stream='search/hello')
        get_url.assert_called_with(
            'http://identi.ca/api/search.json?q=hello')

    def test_getfriendsids(self):
        get_url = self.protocol._get_url = mock.Mock(return_value=[1,2,3])
        ids = self.protocol._getfriendsids()

        get_url.assert_called_with(
            'http://identi.ca/api/friends/ids.json'
            )
        self.assertEqual(ids, [1,2,3])

    def test_showuser(self):
        get_url = self.protocol._get_url = mock.Mock(return_value={"name":"Alice"})
        userdata = self.protocol._showuser(1)

        get_url.assert_called_with(
            'http://identi.ca/api/users/show.json?user_id=1'
            )
        self.assertEqual(userdata, {"name":"Alice"})

    def test_create_contact(self, *mocks):
        # Receive the users friends.
        bare_contact = {'name': 'Alice Bob',
                        'screen_name': 'alice_bob',
                        'id': 13579}

        eds_contact = self.protocol._create_contact(bare_contact)
        twitter_id_attr = eds_contact.get_attribute('twitter-id')
        self.assertEqual(twitter_id_attr.get_value(), '13579')
        twitter_name_attr = eds_contact.get_attribute('twitter-name')
        self.assertEqual(twitter_name_attr.get_value(), 'Alice Bob')
        web_service_addrs = eds_contact.get_attribute('X-FOLKS-WEB-SERVICES-IDS')
        params= web_service_addrs.get_params()
        self.assertEqual(len(params), 2)

        test_remote_name = False
        test_twitter_id = False

        for p in params:
            if p.get_name() == 'remote-full-name':
                self.assertEqual(len(p.get_values()), 1)
                self.assertEqual(p.get_values()[0], 'Alice Bob')
                test_remote_name = True
            if p.get_name() == 'twitter-id':
                self.assertEqual(len(p.get_values()), 1)
                self.assertEqual(p.get_values()[0], '13579')
                test_twitter_id = True

        self.assertTrue(test_remote_name and test_twitter_id)
