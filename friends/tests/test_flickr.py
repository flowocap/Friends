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

from gi.repository import GLib, Dee

from friends.errors import AuthorizationError, FriendsError
from friends.protocols.flickr import Flickr
from friends.tests.mocks import FakeAccount, FakeSoupMessage, LogMock, mock
from friends.utils.model import COLUMN_INDICES, COLUMN_TYPES


# Create a test model that will not interfere with the user's environment.
# We'll use this object as a mock of the real model.
TestModel = Dee.SharedModel.new('com.canonical.Friends.TestSharedModel')
TestModel.set_schema_full(COLUMN_TYPES)


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
                extras='date_upload,owner_name,icon_server',
                format='json',
                nojsoncallback='1',
                api_key='fake',
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
            self.assertEqual(self.protocol.receive(), 3)
        self.assertEqual(TestModel.get_n_rows(), 3)

        self.assertEqual(
            list(TestModel.get_row(0)),
            ['flickr',
             69,
             '801',
             'images',
             '',
             '123',
             '',
             False,
             '2012-05-10T13:36:45Z',
             '',
             '',
             '',
             0,
             False,
             '',
             '',
             '',
             '',
             'ant',
             '',
             0.0,
             0.0,
             ])

        self.assertEqual(
            list(TestModel.get_row(1)),
            ['flickr',
             69,
             '802',
             'images',
             'Alex Lifeson',
             '456',
             'Alex Lifeson',
             True,
             '',
             '',
             '',
             '',
             0,
             False,
             '',
             '',
             '',
             '',
             'bee',
             '',
             0.0,
             0.0,
             ])

        self.assertEqual(
            list(TestModel.get_row(2)),
            ['flickr',
             69,
             '803',
             'images',
             'Bob Dobbs',
             '789',
             'Bob Dobbs',
             False,
             '',
             '',
             GLib.get_user_cache_dir() +
             '/friends/avatars/b913501d6face9d13f3006b731a711b596d23099',
             'http://www.flickr.com/people/789',
             0,
             False,
             'http://farmanimalz.static.flickr.com/1/789_ghi_m.jpg',
             '',
             'http://farmanimalz.static.flickr.com/1/789_ghi_b.jpg',
             '',
             'cat',
             'http://farmanimalz.static.flickr.com/1/789_ghi_t.jpg',
             0.0,
             0.0,
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
