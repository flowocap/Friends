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

"""Main friends-dispatcher module.

This gets turned into a script by `python3 setup.py install`.
"""


__all__ = [
    'main',
    ]


import sys
import dbus
import logging


# Set up the DBus main loop.
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

DBusGMainLoop(set_as_default=True)
loop = GLib.MainLoop()


# Short-circuit everything else if we are going to enter test-mode.
from friends.utils.options import Options
args = Options().parser.parse_args()

if args.test:
    import os
    import tempfile
    import shutil

    from friends.service.mock_service import Dispatcher
    from friends.utils.mocks import TestModel
    from gi.repository import Dee

    temp_cache = tempfile.mkdtemp()
    root = JsonCache._root = os.path.join(temp_cache, '{}.json')
    account = FakeAccount()
    protocol = Facebook(self.account)
    protocol.source_registry = EDSRegistry()
    with mock.patch('friends.utils.http.Soup.Message',
                    FakeSoupMessage('friends.tests.data',
                                    'facebook-login.dat')) as fb:

    Dispatcher()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass

    shutil.rmtree(temp_cache)
    sys.exit(0)


# Continue with normal loading...
from gi.repository import Gio, GObject

GObject.threads_init(None)

from friends.service.dispatcher import Dispatcher, DBUS_INTERFACE
from friends.utils.base import _OperationThread, _publish_lock
from friends.utils.base import Base, initialize_caches
from friends.utils.model import Model, prune_model
from friends.utils.logging import initialize
from friends.utils.avatar import Avatar


# Optional performance profiling module.
yappi = None


# Logger must be initialized before it can be used.
log = None


def main():
    global log
    global yappi

    if args.list_protocols:
        from friends.utils.manager import protocol_manager
        for name in sorted(protocol_manager.protocols):
            cls = protocol_manager.protocols[name]
            package, dot, class_name = cls.__name__.rpartition('.')
            print(class_name)
        return

    # Our threading implementation needs to know how to quit the
    # application once all threads have completed.
    _OperationThread.shutdown = loop.quit

    # Disallow multiple instances of friends-dispatcher
    bus = dbus.SessionBus()
    obj = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
    iface = dbus.Interface(obj, 'org.freedesktop.DBus')
    if DBUS_INTERFACE in iface.ListNames():
        sys.exit('friends-dispatcher is already running! Abort!')

    if args.performance:
        try:
            import yappi
        except ImportError:
            pass
        else:
            yappi.start()

    # Initialize the logging subsystem.
    gsettings = Gio.Settings.new('com.canonical.friends')
    initialize(console=args.console,
               debug=args.debug or gsettings.get_boolean('debug'))
    log = logging.getLogger(__name__)
    log.info('Friends backend dispatcher starting')

    # ensure friends-service is available to provide the Dee.SharedModel
    server = bus.get_object(
        'com.canonical.Friends.Service',
        '/com/canonical/friends/Service')

    # Determine which messages to notify for.
    notify_level = gsettings.get_string('notifications')
    if notify_level == 'all':
        Base._do_notify = lambda protocol, stream: True
    elif notify_level == 'none':
        Base._do_notify = lambda protocol, stream: False
    else:
        Base._do_notify = lambda protocol, stream: stream in (
            'mentions',
            'private',
            )

    # We need to acquire the publish lock so that the dispatcher
    # doesn't try to publish rows into an uninitialized model...
    # basically this prevents duplicates from showing up.
    _publish_lock.acquire()
    Dispatcher(gsettings, loop)

    # Don't initialize caches until the model is synchronized
    Model.connect('notify::synchronized', setup)

    try:
        log.info('Starting friends-dispatcher main loop')
        loop.run()
    except KeyboardInterrupt:
        pass

    log.info('Stopped friends-dispatcher main loop')

    # This bit doesn't run until after the mainloop exits.
    if args.performance and yappi is not None:
        yappi.print_stats(sys.stdout, yappi.SORTTYPE_TTOT)


def setup(model, param):
    """Continue friends-dispatcher init after the DeeModel has synced."""
    # mhr3 says that we should not let a Dee.SharedModel exceed 8mb in
    # size, because anything larger will have problems being transmitted
    # over DBus. I have conservatively calculated our average row length
    # to be 500 bytes, which means that we shouldn't let our model exceed
    # approximately 16,000 rows. However, that seems like a lot to me, so
    # I'm going to set it to 2,000 for now and we can tweak this later if
    # necessary. Do you really need more than 2,000 tweets in memory at
    # once? What are you doing with all these tweets?
    prune_model(2000)

    # This builds two different indexes of our persisted Dee.Model
    # data for the purposes of faster duplicate checks.
    initialize_caches()

    # Allow publishing.
    _publish_lock.release()


if __name__ == '__main__':
    # Use this with `python3 -m friends.main`
    main()
