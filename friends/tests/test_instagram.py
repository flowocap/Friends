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

"""Test the Instagram plugin."""


__all__ = [
    'TestInstagram',
    ]


import os
import tempfile
import unittest
import shutil

from gi.repository import GLib
from pkg_resources import resource_filename

from friends.protocols.instagram import Instagram
from friends.tests.mocks import FakeAccount, FakeSoupMessage, LogMock
from friends.tests.mocks import TestModel, mock
from friends.tests.mocks import EDSBookClientMock, EDSSource, EDSRegistry
from friends.errors import ContactsError, FriendsError, AuthorizationError
from friends.utils.cache import JsonCache


@mock.patch('friends.utils.http._soup', mock.Mock())
@mock.patch('friends.utils.base.notify', mock.Mock())
class TestInstagram(unittest.TestCase):
    """Test the Instagram API."""

    def setUp(self):
        self._temp_cache = tempfile.mkdtemp()
        self._root = JsonCache._root = os.path.join(
            self._temp_cache, '{}.json')
        self.account = FakeAccount()
        self.protocol = Instagram(self.account)
        self.protocol.source_registry = EDSRegistry()

    def tearDown(self):
        TestModel.clear()
        shutil.rmtree(self._temp_cache)

    def test_features(self):
        # The set of public features.
        self.assertEqual(Instagram.get_features(),
            ['home', 'like', 'receive', 'send_thread', 'unlike'])

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Accounts')
    @mock.patch('friends.utils.authentication.Authentication.__init__',
                return_value=None)
    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(AccessToken='abc'))
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'instagram-login.dat'))
    def test_successful_login(self, *mock):
        # Test that a successful response from instagram.com returning
        # the user's data, sets up the account dict correctly.
        self.protocol._login()
        self.assertEqual(self.account.access_token, 'abc')
        self.assertEqual(self.account.user_name, 'bpersons')
        self.assertEqual(self.account.user_id, '801')

    @mock.patch('friends.utils.authentication.manager')
    @mock.patch('friends.utils.authentication.Accounts')
    @mock.patch.dict('friends.utils.authentication.__dict__', LOGIN_TIMEOUT=1)
    @mock.patch('friends.utils.authentication.Signon.AuthSession.new')
    def test_login_unsuccessful_authentication(self, *mock):
        # The user is not already logged in, but the act of logging in fails.
        self.assertRaises(AuthorizationError, self.protocol._login)
        self.assertIsNone(self.account.access_token)
        self.assertIsNone(self.account.user_name)

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'instagram-full.dat'))
    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.protocols.instagram.Instagram._login',
                return_value=True)
    def test_receive(self, *mocks):
        # Receive the feed for a user.
        self.maxDiff = None
        self.account.access_token = 'abc'
        self.assertEqual(self.protocol.receive(), 14)
        self.assertEqual(TestModel.get_n_rows(), 14)
        self.assertEqual(list(TestModel.get_row(0)), [
            'instagram',
            88,
            '431474591469914097_223207800',
            'messages',
            'Josh',
            '223207800',
            'joshwolp',
            False,
            '2013-04-11T04:50:01Z',
            'joshwolp shared a picture on Instagram.',
            GLib.get_user_cache_dir() +
            '/friends/avatars/ca55b643e7b440762c7c6292399eed6542a84b90',
            'http://instagram.com/joshwolp',
            8,
            False,
            'http://distilleryimage9.s3.amazonaws.com/44ad8486a26311e2872722000a1fd26f_5.jpg',
            '',
            'http://instagram.com/p/X859raK8fx/',
            '',
            '',
            '',
            '',
            0.0,
            0.0,
            ])
        self.assertEqual(list(TestModel.get_row(3)), [
            'instagram',
            88,
            '431462132263145102',
            'reply_to/431438012683111856_5891266',
            'Syd',
            '5917696',
            'squidneylol',
            False,
            '2013-04-11T04:25:15Z',
            'I remember pushing that little guy of the swings a few times....',
            GLib.get_user_cache_dir() +
            '/friends/avatars/e61c8d91e37fec3e1dec9325fa4edc52ebeb96bb',
            '',
            0,
            False,
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            0.0,
            0.0,
            ])

    @mock.patch('friends.protocols.instagram.Downloader')
    def test_send_thread(self, dload):
        dload().get_json.return_value = dict(id='comment_id')
        token = self.protocol._get_access_token = mock.Mock(
            return_value='abc')
        publish = self.protocol._publish_entry = mock.Mock(
            return_value='http://instagram.com/p/post_id')

        self.assertEqual(
            self.protocol.send_thread('post_id', 'Some witty response!'),
            'http://instagram.com/p/post_id')
        token.assert_called_once_with()
        publish.assert_called_with(entry={'id': 'comment_id'},
                                   stream='reply_to/post_id')
        self.assertEqual(
            dload.mock_calls,
            [mock.call(),
             mock.call(
                    'https://api.instagram.com/v1/media/post_id/comments?access_token=abc',
                    method='POST',
                    params=dict(
                        access_token='abc',
                        text='Some witty response!')),
             mock.call().get_json(),
             mock.call('https://api.instagram.com/v1/media/post_id/comments?access_token=abc',
                       params=dict(access_token='abc')),
             mock.call().get_json(),
             ])

    @mock.patch('friends.protocols.instagram.Downloader')
    def test_like(self, dload):
        dload().get_json.return_value = True
        token = self.protocol._get_access_token = mock.Mock(
            return_value='insta')
        inc_cell = self.protocol._inc_cell = mock.Mock()
        set_cell = self.protocol._set_cell = mock.Mock()

        self.assertEqual(self.protocol.like('post_id'), 'post_id')

        inc_cell.assert_called_once_with('post_id', 'likes')
        set_cell.assert_called_once_with('post_id', 'liked', True)
        token.assert_called_once_with()
        dload.assert_called_with(
            'https://api.instagram.com/v1/media/post_id/likes?access_token=insta',
            method='POST',
            params=dict(access_token='insta'))

    @mock.patch('friends.protocols.instagram.Downloader')
    def test_unlike(self, dload):
        dload.get_json.return_value = True
        token = self.protocol._get_access_token = mock.Mock(
            return_value='insta')
        dec_cell = self.protocol._dec_cell = mock.Mock()
        set_cell = self.protocol._set_cell = mock.Mock()

        self.assertEqual(self.protocol.unlike('post_id'), 'post_id')

        dec_cell.assert_called_once_with('post_id', 'likes')
        set_cell.assert_called_once_with('post_id', 'liked', False)
        token.assert_called_once_with()
        dload.assert_called_once_with(
            'https://api.instagram.com/v1/media/post_id/likes?access_token=insta',
            method='DELETE',
            params=dict(access_token='insta'))
