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

"""Test generic protocol support."""

__all__ = [
    'TestProtocolManager',
    'TestProtocols',
    ]


import unittest
import threading

from gi.repository import Dee

from friends.protocols.flickr import Flickr
from friends.protocols.twitter import Twitter
from friends.tests.mocks import FakeAccount, LogMock, mock
from friends.utils.base import Base, feature
from friends.utils.manager import ProtocolManager
from friends.utils.model import (
    COLUMN_INDICES, COLUMN_NAMES, COLUMN_TYPES, Model)


# Create a test model that will not interfere with the user's environment.
# We'll use this object as a mock of the real model.
TestModel = Dee.SharedModel.new('com.canonical.Friends.TestSharedModel')
TestModel.set_schema_full(COLUMN_TYPES)


class TestProtocolManager(unittest.TestCase):
    """Test the protocol finder."""

    def setUp(self):
        self.manager = ProtocolManager()
        self.log_mock = LogMock('friends.utils.base')

    def tearDown(self):
        self.log_mock.stop()

    def test_find_all_protocols(self):
        # The manager can find all the protocol classes.
        self.assertEqual(self.manager.protocols['flickr'], Flickr)
        self.assertEqual(self.manager.protocols['twitter'], Twitter)

    def test_doesnt_find_base(self):
        # Make sure that the base protocol class isn't returned.
        self.assertNotIn('base', self.manager.protocols)
        for protocol_class in self.manager.protocols.values():
            self.assertNotEqual(protocol_class, Base)


class MyProtocol(Base):
    """Simplest possible protocol implementation to allow testing of Base."""

    def noop(self, one=None, two=None):
        return '{}:{}'.format(one, two)

    # A non-public method that cannot be called through __call__()
    _private = noop

    def _locked_login(self, old_token):
        self._account.access_token = 'fake_token'

    # Two features and two non-features for testing purposes.

    @feature
    def feature_1(self): pass

    @feature
    def feature_2(self): pass

    def non_feature_1(self): pass

    def non_feature_2(self): pass


@mock.patch('friends.utils.base.notify', mock.Mock())
class TestProtocols(unittest.TestCase):
    """Test protocol implementations."""

    def setUp(self):
        TestModel.clear()

    def test_no_operation(self):
        # Trying to call a protocol with a missing operation raises an
        # AttributeError exception.
        fake_account = object()
        my_protocol = MyProtocol(fake_account)
        with self.assertRaises(NotImplementedError) as cm:
            my_protocol('give_me_a_pony')
        self.assertEqual(str(cm.exception), 'give_me_a_pony')

    def test_private_operation(self):
        # Trying to call a protocol with a non-public operation raises an
        # AttributeError exception.
        fake_account = object()
        my_protocol = MyProtocol(fake_account)
        # We can call the method directly.
        result = my_protocol._private('ant', 'bee')
        self.assertEqual(result, 'ant:bee')
        # But we cannot call the method through the __call__ interface.
        with self.assertRaises(NotImplementedError) as cm:
            my_protocol('_private', 'cat', 'dog')
        self.assertEqual(str(cm.exception), '_private')

    def test_basic_api_synchronous(self):
        # Protocols get instantiated with an account, and the instance gets
        # called to perform an operation.
        fake_account = object()
        my_protocol = MyProtocol(fake_account)
        result = my_protocol.noop(one='foo', two='bar')
        self.assertEqual(result, 'foo:bar')

    def test_basic_api_asynchronous(self):
        fake_account = object()
        my_protocol = MyProtocol(fake_account)
        success = mock.Mock()
        failure = mock.Mock()
        # Using __call__ makes invocation happen asynchronously in a thread.
        my_protocol('noop', 'one', 'two',
                    success=success,
                    failure=failure)
        for thread in threading.enumerate():
            # Join all but the main thread.
            if thread != threading.current_thread():
                thread.join()

        success.assert_called_once_with('one:two')
        self.assertEqual(failure.call_count, 0)

    @mock.patch('friends.utils.base.Model', TestModel)
    def test_shared_model_successfully_mocked(self):
        count = Model.get_n_rows()
        self.assertEqual(TestModel.get_n_rows(), 0)
        base = Base(FakeAccount())
        base._publish(message_id='alpha', message='a')
        base._publish(message_id='beta', message='b')
        base._publish(message_id='omega', message='c')
        self.assertEqual(Model.get_n_rows(), count)
        self.assertEqual(TestModel.get_n_rows(), 3)

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_seen_dicts_successfully_instantiated(self):
        from friends.utils.base import _seen_ids
        from friends.utils.base import initialize_caches
        self.assertEqual(TestModel.get_n_rows(), 0)
        base = Base(FakeAccount())
        base._publish(message_id='alpha', sender='a', message='a')
        base._publish(message_id='beta', sender='a', message='a')
        base._publish(message_id='omega', sender='a', message='b')
        self.assertEqual(TestModel.get_n_rows(), 3)
        _seen_ids.clear()
        initialize_caches()
        self.assertEqual(
            _seen_ids,
            dict(alpha=0,
                 beta=1,
                 omega=2,
                 )
            )

    @mock.patch('friends.utils.base.Model', TestModel)
    def test_invalid_argument(self):
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        with self.assertRaises(TypeError) as cm:
            base._publish(message_id='message_id', invalid_argument='not good')
        self.assertEqual(str(cm.exception),
                         'Unexpected keyword arguments: invalid_argument')

    @mock.patch('friends.utils.base.Model', TestModel)
    def test_invalid_arguments(self):
        # All invalid arguments are mentioned in the exception message.
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        with self.assertRaises(TypeError) as cm:
            base._publish(message_id='p.middy', bad='no', wrong='yes')
        self.assertEqual(str(cm.exception),
                         'Unexpected keyword arguments: bad, wrong')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_one_message(self):
        # Test that publishing a message inserts a row into the model.
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertTrue(base._publish(
            message_id='1234',
            stream='messages',
            sender='fred',
            sender_nick='freddy',
            from_me=True,
            timestamp='today',
            message='hello, @jimmy',
            likes=10,
            liked=True))
        self.assertEqual(1, TestModel.get_n_rows())
        row = TestModel.get_row(0)
        self.assertEqual(
            list(row),
            ['base',
             88,
             '1234',
             'messages',
             'fred',
             '',
             'freddy',
             True,
             'today',
             'hello, @jimmy',
             '',
             '',
             10,
             True,
             '',
             '',
             '',
             '',
             '',
             '',
             0.0,
             0.0,
             ])

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_unpublish(self):
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertTrue(base._publish(
            message_id='1234',
            sender='fred',
            message='hello, @jimmy'))
        self.assertTrue(base._publish(
            message_id='1234',
            sender='fred',
            message='hello, @jimmy'))
        self.assertTrue(base._publish(
            message_id='5678',
            sender='fred',
            message='hello, +jimmy'))
        self.assertEqual(2, TestModel.get_n_rows())
        base._unpublish('1234')
        self.assertEqual(1, TestModel.get_n_rows())
        base._unpublish('5678')
        self.assertEqual(0, TestModel.get_n_rows())

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_unpublish_all(self):
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertTrue(base._publish(
            message_id='1234',
            sender='fred',
            message='hello, @jimmy'))
        self.assertTrue(base._publish(
            message_id='1235',
            sender='fred',
            message='hello, @jimmy'))
        self.assertTrue(base._publish(
            message_id='5678',
            sender='fred',
            message='hello, +jimmy'))
        self.assertEqual(3, TestModel.get_n_rows())
        base._unpublish_all()
        self.assertEqual(0, TestModel.get_n_rows())

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_unpublish_all_preserves_others(self):
        base = Base(FakeAccount())
        other = Base(FakeAccount())
        other._account.id = 69
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertTrue(base._publish(
            message_id='1234',
            sender='fred',
            message='hello, @jimmy'))
        self.assertTrue(base._publish(
            message_id='1235',
            sender='fred',
            message='hello, @jimmy'))
        self.assertTrue(other._publish(
            message_id='5678',
            sender='fred',
            message='hello, +jimmy'))
        self.assertEqual(3, TestModel.get_n_rows())
        base._unpublish_all()
        self.assertEqual(1, TestModel.get_n_rows())

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_duplicate_messages_identified(self):
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertTrue(base._publish(
            message_id='1234',
            stream='messages',
            sender='fred',
            sender_nick='freddy',
            from_me=True,
            timestamp='today',
            message='hello, @jimmy',
            likes=10,
            liked=True))
        # Duplicate
        self.assertTrue(base._publish(
            message_id='1234',
            stream='messages',
            sender='fred',
            sender_nick='freddy',
            from_me=True,
            timestamp='today',
            message='hello jimmy',
            likes=10,
            liked=False))
        # See, we get only one row in the table.
        self.assertEqual(1, TestModel.get_n_rows())
        # The first published message wins.
        row = TestModel.get_row(0)
        self.assertEqual(row[COLUMN_INDICES['message']], 'hello, @jimmy')

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_duplicate_ids_not_duplicated(self):
        # When two messages are actually identical (same ids and all),
        # we need to avoid duplicating the id in the sharedmodel.
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        self.assertTrue(base._publish(
            message_id='1234',
            stream='messages',
            sender='fred',
            message='hello, @jimmy'))
        self.assertTrue(base._publish(
            message_id='1234',
            stream='messages',
            sender='fred',
            message='hello, @jimmy'))
        self.assertEqual(1, TestModel.get_n_rows())
        row = TestModel.get_row(0)
        self.assertEqual(
            list(row),
            ['base',
             88,
             '1234',
             'messages',
             'fred',
             '',
             '',
             False,
             '',
             'hello, @jimmy',
             '',
             '',
             0,
             False,
             '',
             '',
             '',
             '',
             '',
             '',
             0.0,
             0.0,
             ])

    @mock.patch('friends.utils.base.Model', TestModel)
    @mock.patch('friends.utils.base._seen_ids', {})
    def test_similar_messages_allowed(self):
        # Because both the sender and message contribute to the unique key we
        # use to identify messages, if two messages are published with
        # different senders, both are inserted into the table.
        base = Base(FakeAccount())
        self.assertEqual(0, TestModel.get_n_rows())
        # The key for this row is 'fredhellojimmy'
        self.assertTrue(base._publish(
            message_id='1234',
            stream='messages',
            sender='fred',
            sender_nick='freddy',
            from_me=True,
            timestamp='today',
            message='hello, @jimmy',
            likes=10,
            liked=True))
        self.assertEqual(1, TestModel.get_n_rows())
        # The key for this row is 'tedtholomewhellojimmy'
        self.assertTrue(base._publish(
            message_id='34567',
            stream='messages',
            sender='tedtholomew',
            sender_nick='teddy',
            from_me=False,
            timestamp='today',
            message='hello, @jimmy',
            likes=10,
            liked=True))
        # See?  Two rows in the table.
        self.assertEqual(2, TestModel.get_n_rows())
        # The first row is the message from fred.
        self.assertEqual(TestModel.get_row(0)[COLUMN_INDICES['sender']],
                         'fred')
        # The second row is the message from tedtholomew.
        self.assertEqual(TestModel.get_row(1)[COLUMN_INDICES['sender']],
                         'tedtholomew')

    def test_basic_login(self):
        # Try to log in twice.  The second login attempt returns False because
        # it's already logged in.
        my_protocol = MyProtocol(FakeAccount())
        self.assertTrue(my_protocol._login())
        self.assertFalse(my_protocol._login())

    def test_failing_login(self):
        # The first login attempt fails because _locked_login() does not set
        # an access token.
        class FailingProtocol(MyProtocol):
            def _locked_login(self, old_token):
                pass
        my_protocol = FailingProtocol(FakeAccount())
        self.assertFalse(my_protocol._login())

    # XXX I think there's a threading test that should be performed, but it
    # hurts my brain too much.  See the comment at the bottom of the
    # with-statement in Base._login().

    def test_features(self):
        self.assertEqual(MyProtocol.get_features(), ['feature_1', 'feature_2'])
