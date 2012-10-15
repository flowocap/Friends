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

"""Test the Flickr plugin."""

__all__ = [
    'TestFlickr',
    ]


import unittest

from gi.repository import Dee

from friends.protocols.flickr import Flickr
from friends.testing.helpers import FakeAccount
from friends.testing.mocks import FakeSoupMessage, LogMock
from friends.utils.base import Base
from friends.utils.model import COLUMN_INDICES, COLUMN_TYPES

try:
    # Python 3.3
    from unittest import mock
except ImportError:
    import mock


# Create a test model that will not interfere with the user's environment.
# We'll use this object as a mock of the real model.
TestModel = Dee.SharedModel.new('com.canonical.Friends.TestSharedModel')
TestModel.set_schema_full(COLUMN_TYPES)


@mock.patch('friends.utils.download._soup', mock.Mock())
class TestFlickr(unittest.TestCase):
    """Test the Flickr API."""

    def setUp(self):
        self.account = FakeAccount()
        self.protocol = Flickr(self.account)
        # Enable sub-thread synchronization, and mock out the loggers.
        Base._SYNCHRONIZE = True
        self.log_mock = LogMock('friends.utils.base',
                                'friends.protocols.flickr')

    def tearDown(self):
        # Stop log mocking, and return sub-thread operation to asynchronous.
        self.log_mock.stop()
        Base._SYNCHRONIZE = False
        # Reset the database.
        TestModel.clear()

    def test_features(self):
        # The set of public features.
        self.assertEqual(Flickr.get_features(), ['receive'])

    def test_failed_login(self):
        # Force the Flickr login to fail.
        with mock.patch.object(self.protocol, '_get_nsid', return_value=None):
            self.protocol('receive')
        self.assertEqual(self.log_mock.empty(), """\
Flickr: No NSID available
Friends operation exception:
 Traceback (most recent call last):
 ...
friends.errors.AuthorizationError:\
 No Flickr user id available (account: faker/than fake)
""")

    @mock.patch('friends.utils.download.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-nophotos.dat'))
    @mock.patch('friends.utils.base.Model', TestModel)
    def test_already_logged_in(self):
        # Try to get the data when already logged in.
        self.account.user_id = 'anne'
        # There's no data, and no way to test that the user_nsid was actually
        # used, except for the side effect of not getting an
        # AuthorizationError.
        self.protocol('receive')
        # No error messages.
        self.assertEqual(self.log_mock.empty(), '')
        # But also no photos.
        self.assertEqual(TestModel.get_n_rows(), 0)

    @mock.patch('friends.utils.download.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-nophotos.dat'))
    def test_unsuccessful_login(self):
        # The user is not already logged in, but the act of logging in
        # fails.
        def side_effect():
            # Sorry, the login is unsuccessful, even though it adds a user_id
            # key to the account.
            self.account.user_id = 'bart'
            return False
        with mock.patch.object(self.protocol, '_login',
                               side_effect=side_effect):
            self.protocol('receive')
        self.assertEqual(self.log_mock.empty(), """\
Friends operation exception:
 Traceback (most recent call last):
 ...
friends.errors.AuthorizationError:\
 No Flickr user id available (account: faker/than fake)
""")

    @mock.patch('friends.utils.download.Soup.Message',
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
            self.protocol('receive')
        # No error message.
        self.assertEqual(self.log_mock.empty(), '')
        # But also no photos.
        self.assertEqual(TestModel.get_n_rows(), 0)

    @mock.patch('friends.utils.download.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-nophotos.dat'))
    @mock.patch('friends.utils.authentication.Authentication.login',
                # No AccessToken, so for all intents-and-purposes; fail!
                return_value=dict(username='Bob Dobbs',
                                  user_nsid='bob',
                                  TokenSecret='abc'))
    def test_login_unsuccessful_authentication(self, mock):
        # Logging in required communication with the account service to get an
        # AccessToken, but this fails.
        self.protocol('receive')
        self.assertEqual(self.log_mock.empty(), """\
No AccessToken in Flickr session:\
 {'TokenSecret': 'abc', 'username': 'Bob Dobbs', 'user_nsid': 'bob'}
Flickr: No NSID available
Friends operation exception:
 Traceback (most recent call last):
 ...
friends.errors.AuthorizationError:\
 No Flickr user id available (account: faker/than fake)
""")

    @mock.patch('friends.utils.download.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-nophotos.dat'))
    @mock.patch('friends.utils.authentication.Authentication.login',
                # login() callback never happens.
                return_value=None)
    def test_login_unsuccessful_authentication_no_callback(self, mock):
        # Logging in required communication with the account service to get an
        # AccessToken, but this fails.
        self.protocol('receive')
        self.assertEqual(self.log_mock.empty(), """\
No Flickr authentication results received.
Flickr: No NSID available
Friends operation exception:
 Traceback (most recent call last):
 ...
friends.errors.AuthorizationError:\
 No Flickr user id available (account: faker/than fake)
""")

    @mock.patch('friends.utils.download.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-nophotos.dat'))
    @mock.patch('friends.utils.authentication.Authentication.login',
                return_value=dict(username='Bob Dobbs',
                                  user_nsid='bob',
                                  AccessToken='123',
                                  TokenSecret='abc'))
    def test_login_successful_authentication(self, mock):
        # Logging in required communication with the account service to get an
        # AccessToken, but this fails.
        self.protocol('receive')
        # Make sure our account data got properly updated.
        self.assertEqual(self.account.user_name, 'Bob Dobbs')
        self.assertEqual(self.account.user_id, 'bob')
        self.assertEqual(self.account.access_token, '123')
        self.assertEqual(self.account.secret_token, 'abc')

    def test_get(self):
        # Make sure that the REST GET url looks right.
        with mock.patch.object(self.protocol, '_get_nsid', return_value='jim'):
            with mock.patch('friends.protocols.flickr.get_json',
                            return_value={}) as cm:
                self.protocol('receive')
        # Unpack the arguments that the mock was called with and test that the
        # arguments, especially to the GET are what we expected.
        all_call_args = cm.call_args_list
        # GET was called once.
        self.assertEqual(len(all_call_args), 1)
        url, GET_args = all_call_args[0][0]
        self.assertEqual(url, 'http://api.flickr.com/services/rest')
        self.assertEqual(GET_args, dict(
            extras='date_updated,owner_name,icon_server',
            user_id='jim',
            format='json',
            nojsoncallback='1',
            api_key='36f660117e6555a9cbda4309cfaf72d0',
            method='flickr.photos.getContactsPublicPhotos',
            ))

    @mock.patch('friends.utils.download.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-nophotos.dat'))
    @mock.patch('friends.utils.base.Model', TestModel)
    def test_no_photos(self):
        # The JSON data in response to the GET request returned no photos.
        with mock.patch.object(self.protocol, '_get_nsid', return_value='jim'):
            # No photos are returned in the JSON data.
            self.protocol('receive')
        self.assertEqual(TestModel.get_n_rows(), 0)

    @mock.patch('friends.utils.download.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'flickr-full.dat'))
    @mock.patch('friends.utils.base.Model', TestModel)
    def test_flickr_data(self):
        # Test the undocumented and apparently crufty reformatting of the raw
        # JSON Flickr data into the format expected internally.
        #
        # Start by setting up a fake account id.
        self.account.id = 'lerxst'
        with mock.patch.object(self.protocol, '_get_nsid', return_value='jim'):
            self.protocol('receive')
        self.assertEqual(TestModel.get_n_rows(), 3)
        # Image 1 data in the first row.
        row = list(TestModel.get_row(0))
        # For convenience.
        def col(name):
            return row[COLUMN_INDICES[name]]
        self.assertEqual(col('message'), 'ant')
        self.assertEqual(col('html'), 'ant')
        self.assertEqual(col('message_ids'), [['flickr', 'lerxst', '801']])
        self.assertEqual(col('sender'), '123')
        self.assertEqual(col('timestamp'), '2012-05-10T13:36:45')
        self.assertFalse(col('from_me'))
        row = list(TestModel.get_row(1))
        # Image 2 data.  The image is from the account owner.
        self.assertEqual(col('message'), 'bee')
        self.assertEqual(col('html'), 'bee')
        self.assertEqual(col('message_ids'), [['flickr', 'lerxst', '802']])
        self.assertEqual(col('sender'), '456')
        self.assertEqual(col('sender_nick'), 'Alex Lifeson')
        self.assertTrue(col('from_me'))
        # Image 3 data.  This data set has some additional entries that allow
        # various image urls and other keys to be added.
        row = list(TestModel.get_row(2))
        self.assertEqual(col('message'), 'cat')
        self.assertEqual(col('html'), 'cat')
        self.assertEqual(
            col('img_url'),
            'http://farmanimalz.static.flickr.com/1/789_ghi_b.jpg')
        self.assertEqual(
            col('img_src'),
            'http://farmanimalz.static.flickr.com/1/789_ghi_m.jpg')
        self.assertEqual(
            col('img_thumb'),
            'http://farmanimalz.static.flickr.com/1/789_ghi_t.jpg')
        self.assertEqual(col('sender'), '789')
        self.assertEqual(
            col('icon_uri'),
            'http://farmiconz.static.flickr.com/9/buddyicons/789.jpg')
        self.assertFalse(col('from_me'))
        self.assertEqual(col('sender'), '789')
        self.assertEqual(col('sender_nick'), 'Bob Dobbs')
        self.assertEqual(col('url'), 'http://www.flickr.com/people/789')