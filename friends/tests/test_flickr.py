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

"""Test the Flickr plugin."""

__all__ = [
    'TestFlickr',
    ]


import unittest

from gi.repository import GLib

from friends.errors import AuthorizationError, FriendsError
from friends.protocols.flickr import Flickr
from friends.tests.mocks import FakeAccount, FakeSoupMessage, LogMock
from friends.tests.mocks import TestModel, mock


@mock.patch('friends.utils.http._soup', mock.Mock())
@mock.patch('friends.utils.base.notify', mock.Mock())
class TestFlickr(unittest.TestCase):
    """Test the Flickr API."""

    def setUp(self):
        self.maxDiff = None
        self.account = FakeAccount()
        self.protocol = Flickr(self.account)
        self.protocol._get_oauth_headers = lambda *ignore, **kwignore: {}
        self.log_mock = LogMock('friends.utils.base',
                                'friends.protocols.flickr')

    def tearDown(self):
        self.log_mock.stop()
        # Reset the database.
        TestModel.clear()

    def test_features(self):
        # The set of public features.
        self.assertEqual(Flickr.get_features(), ['receive', 'upload'])

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-nophotos.dat'))
    @mock.patch('friends.utils.base.Model', TestModel)
    def test_already_logged_in(self):
        # Try to get the data when already logged in.
        self.account.access_token = 'original token'
        # There's no data, and no way to test that the user_nsid was actually
        # used, except for the side effect of not getting an
        # AuthorizationError.
        self.protocol.receive()
        # No error messages.
        self.assertEqual(self.log_mock.empty(), '')
        # But also no photos.
        self.assertEqual(TestModel.get_n_rows(), 0)

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-nophotos.dat'))
    @mock.patch('friends.utils.base.Model', TestModel)
    def test_successful_login(self):
        # The user is not already logged in, but the act of logging in
        # succeeds.
        def side_effect():
            # Perform a successful login.
            self.account.user_id = 'cate'
            return True
        with mock.patch.object(self.protocol, '_login',
                               side_effect=side_effect):
            self.protocol.receive()
        # No error message.
        self.assertEqual(self.log_mock.empty(), '')
        # But also no photos.
        self.assertEqual(TestModel.get_n_rows(), 0)

    @mock.patch.dict('friends.utils.authentication.__dict__', LOGIN_TIMEOUT=1)
    @mock.patch('friends.utils.authentication.Signon.AuthSession.new')
    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-nophotos.dat'))
    def test_login_unsuccessful_authentication_no_callback(self, *mocks):
        # Logging in required communication with the account service to get an
        # AccessToken, but this fails.
        self.assertRaises(AuthorizationError, self.protocol.receive)

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-nophotos.dat'))
    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(username='Bob Dobbs',
                                  user_nsid='bob',
                                  AccessToken='123',
                                  TokenSecret='abc'))
    def test_login_successful_authentication(self, mock):
        # Logging in required communication with the account service to get an
        # AccessToken, but this fails.
        self.protocol.receive()
        # Make sure our account data got properly updated.
        self.assertEqual(self.account.user_name, 'Bob Dobbs')
        self.assertEqual(self.account.user_id, 'bob')
        self.assertEqual(self.account.access_token, '123')
        self.assertEqual(self.account.secret_token, 'abc')

    @mock.patch('friends.utils.base.Model', TestModel)
    def test_get(self):
        # Make sure that the REST GET url looks right.
        token = self.protocol._get_access_token = mock.Mock()
        class fake:
            def get_json(*ignore):
                return {}
        with mock.patch('friends.protocols.flickr.Downloader') as cm:
            cm.return_value = fake()
            self.assertEqual(self.protocol.receive(), 0)
        token.assert_called_once_with()
        # GET was called once.
        cm.assert_called_once_with(
            'http://api.flickr.com/services/rest',
            method='GET',
            params=dict(
                extras='date_upload,owner_name,icon_server,geo',
                format='json',
                nojsoncallback='1',
                api_key='consume',
                method='flickr.photos.getContactsPhotos',
                ),
            headers={})

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-nophotos.dat'))
    @mock.patch('friends.utils.base.Model', TestModel)
    def test_no_photos(self):
        # The JSON data in response to the GET request returned no photos.
        with mock.patch.object(
            self.protocol, '_get_access_token', return_value='token'):
            # No photos are returned in the JSON data.
            self.assertEqual(self.protocol.receive(), 0)
        self.assertEqual(TestModel.get_n_rows(), 0)

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-full.dat'))
    @mock.patch('friends.utils.base.Model', TestModel)
    def test_flickr_data(self):
        # Start by setting up a fake account id.
        self.account.id = 69
        with mock.patch.object(self.protocol, '_get_access_token',
                               return_value='token'):
            self.assertEqual(self.protocol.receive(), 10)
        self.assertEqual(TestModel.get_n_rows(), 10)

        self.assertEqual(
            list(TestModel.get_row(0)),
            ['flickr',
             69,
             '8552892154',
             'images',
             'raise my voice',
             '47303164@N00',
             'raise my voice',
             True,
             '2013-03-12T19:51:42Z',
             '',
             GLib.get_user_cache_dir() +
             '/friends/avatars/7b30ff0140dd9b80f2b1782a2802c3ce785fa0ce',
             'http://www.flickr.com/people/47303164@N00',
             0,
             False,
             'http://farm9.static.flickr.com/8378/47303164@N00_a_m.jpg',
             '',
             'http://farm9.static.flickr.com/8378/47303164@N00_a_b.jpg',
             '',
             'Chocolate chai #yegcoffee',
             'http://farm9.static.flickr.com/8378/47303164@N00_a_t.jpg',
             '',
             0.0,
             0.0,
             ])

        self.assertEqual(
            list(TestModel.get_row(4)),
            ['flickr',
             69,
             '8550829193',
             'images',
             'Nelson Webb',
             '27204141@N05',
             'Nelson Webb',
             True,
             '2013-03-12T13:54:10Z',
             '',
             GLib.get_user_cache_dir() +
             '/friends/avatars/cae2939354a33fea5f008df91bb8e25920be5dc3',
             'http://www.flickr.com/people/27204141@N05',
             0,
             False,
             'http://farm9.static.flickr.com/8246/27204141@N05_e_m.jpg',
             '',
             'http://farm9.static.flickr.com/8246/27204141@N05_e_b.jpg',
             '',
             'St. Michael - The Archangel',
             'http://farm9.static.flickr.com/8246/27204141@N05_e_t.jpg',
             '',
             53.833156,
             -112.330784,
             ])

    @mock.patch('friends.utils.http.Soup.form_request_new_from_multipart',
                lambda *ignore: FakeSoupMessage('friends.tests.data',
                                                'flickr-xml.dat'))
    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.http.Gio.File')
    @mock.patch('friends.protocols.flickr.time.time', lambda: 1361292793)
    def test_upload(self, gfile):
        self.account.user_name = 'freddyjimbobjones'
        gfile.new_for_uri().load_contents.return_value = [True, 'data'.encode()]
        token = self.protocol._get_access_token = mock.Mock()
        publish = self.protocol._publish = mock.Mock()
        avatar = self.protocol._get_avatar = mock.Mock()
        avatar.return_value = '/path/to/cached/avatar'

        self.assertEqual(
            self.protocol.upload(
                'file:///path/to/some.jpg',
                'Beautiful photograph!'),
            'http://www.flickr.com/photos/freddyjimbobjones/8488552823')

        token.assert_called_with()
        publish.assert_called_with(
            message='Beautiful photograph!',
            timestamp='2013-02-19T16:53:13Z',
            stream='images',
            message_id='8488552823',
            from_me=True,
            sender=None,
            sender_nick='freddyjimbobjones',
            icon_uri='/path/to/cached/avatar',
            url='http://www.flickr.com/photos/freddyjimbobjones/8488552823',
            sender_id=None)

    @mock.patch('friends.utils.http.Soup.form_request_new_from_multipart',
                lambda *ignore: FakeSoupMessage('friends.tests.data',
                                                'flickr-xml-error.dat'))
    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.http.Gio.File')
    def test_failing_upload(self, gfile):
        gfile.new_for_uri().load_contents.return_value = [True, 'data'.encode()]
        token = self.protocol._get_access_token = mock.Mock()
        publish = self.protocol._publish = mock.Mock()

        self.assertRaises(
            FriendsError,
            self.protocol.upload,
            'file:///path/to/some.jpg',
            'Beautiful photograph!')

        token.assert_called_with()
        self.assertEqual(publish.call_count, 0)
