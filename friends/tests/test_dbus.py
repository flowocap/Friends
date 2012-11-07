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

"""Test the Friends service via dbus over a separate test bus."""


__all__ = [
    'TestDBus',
    ]


import dbus
import json
import unittest

from friends.testing.dbus import Controller


_controller = None


def is_runnable():
    """Are the dbus integration tests runnable?

    This sets up the controller, i.e. the dbus environment, for the tests in
    the following TestCase.  If the environment cannot be set up, the entire
    test class is skipped.  The test class must shutdown the controller when
    it's done.  Start up cannot happen in the setUpClass() method because that
    happens *after* the @skip decorator is checked.
    """
    global _controller
    _controller = Controller()
    _controller.start()
    if not _controller.is_runnable:
        _controller.shutdown()
        return False
    return True


@unittest.skipUnless(is_runnable(),
                     'Integration tests must run inside a virtualenv')
class TestDBus(unittest.TestCase):
    """Test the Friends URL service via dbus.

    This is actually an integration test, and requires the Friends service to
    be set up in a virtualenv.  If not, these tests are just skipped.

    It's also important to understand that unless you set up proxies manually,
    these tests hit the real services!  The primary purpose of these tests is
    to ensure that the dbus service end-points work properly.
    """

    @classmethod
    def tearDownClass(cls):
        _controller.shutdown()

    def setUp(self):
        self.session_bus = dbus.SessionBus()

    def test_shorten(self):
        obj = self.session_bus.get_object(
            'com.canonical.Friends.URLShorten',
            '/com/canonical/friends/URLShorten')
        iface = dbus.Interface(obj, 'com.canonical.Friends.URLShorten')
        short_url = iface.Shorten('http://www.python.org')
        self.assertIsInstance(short_url, dbus.String)

    def test_connection_is_connected(self):
        # Test whether the network manager is connected or not.  This uses the
        # standard system service, and we can't guarantee its state will be
        # connected, so just ensure that we get a boolean back.
        obj = self.session_bus.get_object(
            'com.canonical.Friends.Connection',
            '/com/canonical/friends/Connection')
        iface = dbus.Interface(obj, 'com.canonical.Friends.Connection')
        answer = iface.isConnected()
        self.assertIsInstance(answer, dbus.Boolean)

    def test_connection_internal_signals(self):
        obj = self.session_bus.get_object(
            'com.canonical.Friends.Test',
            '/com/canonical/friends/Test')
        test_iface = dbus.Interface(obj, 'com.canonical.Friends.Test')
        # Now, trigger the appropriate internal signaling and see what the
        # counter values are.  +1 for on and -1 for off.
        self.assertEqual(test_iface.SignalTestOn(), 1)
        self.assertEqual(test_iface.SignalTestOn(), 2)
        self.assertEqual(test_iface.SignalTestOff(), 1)
        self.assertEqual(test_iface.SignalTestOff(), 0)

    # XXX Need tests for the ConnectionOnline and ConnectionOffline signals in
    # com.canonical.Friends.Connection, and also for proper reaction to the
    # StateChanged signal of org.freedesktop.NetworkManager.  It wouldn't hurt
    # to have tests for various failure modes in ConnectionMonitor.__init__()
    # and .isConnected().

    def test_get_features(self):
        obj = self.session_bus.get_object(
            'com.canonical.Friends.Service',
            '/com/canonical/friends/Service')
        iface = dbus.Interface(obj, 'com.canonical.Friends.Service')
        # TODO Add more cases as more protocols are added.
        self.assertEqual(json.loads(iface.GetFeatures('facebook')),
                         ['contacts', 'delete', 'like', 'receive', 'search', 
                          'send', 'send_thread', 'unlike', 'upload'])
        self.assertEqual(json.loads(iface.GetFeatures('twitter')),
                         ['delete', 'follow', 'home', 'like', 'list', 'lists',
                          'mentions', 'private', 'receive', 'retweet',
                          'search', 'send', 'send_private', 'send_thread',
                          'tag', 'unfollow', 'unlike', 'user'])
        self.assertEqual(json.loads(iface.GetFeatures('identica')),
                         ['delete', 'follow', 'home', 'mentions', 'private',
                          'receive', 'retweet', 'search', 'send',
                          'send_private', 'send_thread', 'unfollow', 'user'])
        self.assertEqual(json.loads(iface.GetFeatures('flickr')), ['receive'])
        self.assertEqual(json.loads(iface.GetFeatures('foursquare')),
                         ['receive'])
