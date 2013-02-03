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

"""Main friends-service module.

This gets turned into a script by `python3 setup.py install`.
"""


__all__ = [
    'main',
    ]


import sys
import dbus
import logging

from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import Gio, GLib, GObject

GObject.threads_init(None)

from friends.service.dispatcher import Dispatcher, DBUS_INTERFACE
from friends.utils.avatar import Avatar
from friends.utils.base import _OperationThread, Base, initialize_caches
from friends.utils.logging import initialize
from friends.utils.model import Model, prune_model
from friends.utils.options import Options


# Optional performance profiling module.
yappi = None


# Logger must be initialized before it can be used.
log = None


def main():
    global log
    global yappi
    # Initialize command line options.
    args = Options().parser.parse_args()

    if args.list_protocols:
        from friends.utils.manager import protocol_manager
        for name in sorted(protocol_manager.protocols):
            cls = protocol_manager.protocols[name]
            package, dot, class_name = cls.__name__.rpartition('.')
            print(class_name)
        return

    if args.test:
        global Dispatcher
        from friends.service.mock_service import Dispatcher

    # Set up the DBus main loop.
    DBusGMainLoop(set_as_default=True)
    loop = GLib.MainLoop()

    # Our threading implementation needs to know how to quit the
    # application once all threads have completed.
    _OperationThread.shutdown = loop.quit

    # Disallow multiple instances of friends-service
    bus = dbus.SessionBus()
    obj = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
    iface = dbus.Interface(obj, 'org.freedesktop.DBus')
    if DBUS_INTERFACE in iface.ListNames():
        sys.exit('friends-service is already running! Abort!')

    if args.performance:
        try:
            import yappi
        except ImportError:
            pass
        else:
            yappi.start()

    # Expire old Avatars. Without this we would never notice when
    # somebody changes their avatar, we would just keep the stale old
    # one forever.
    Avatar.expire_old_avatars()

    # Initialize the logging subsystem.
    gsettings = Gio.Settings.new('com.canonical.friends')
    initialize(console=args.console,
               debug=args.debug or gsettings.get_boolean('debug'))
    log = logging.getLogger(__name__)
    log.info('Friends backend service starting')

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

    # Don't initialize caches until the model is synchronized
    Model.connect('notify::synchronized', setup, gsettings, loop)

    try:
        log.info('Starting friends-service main loop')
        loop.run()
    except KeyboardInterrupt:
        log.info('Stopped friends-service main loop')

    # This bit doesn't run until after the mainloop exits.
    if args.performance and yappi is not None:
        yappi.print_stats(sys.stdout, yappi.SORTTYPE_TTOT)

def setup(model, param, gsettings, loop):
    """Continue friends-service initialization after the DeeModel has synced."""
    # mhr3 says that we should not let a Dee.SharedModel exceed 8mb in
    # size, because anything larger will have problems being transmitted
    # over DBus. I have conservatively calculated our average row length
    # to be 500 bytes, which means that we shouldn't let our model exceed
    # approximately 16,000 rows. However, that seems like a lot to me, so
    # I'm going to set it to 8,000 for now and we can tweak this later if
    # necessary. Do you really need more than 8,000 tweets in memory at
    # once? What are you doing with all these tweets?
    prune_model(8000)

    # This builds two different indexes of our persisted Dee.Model
    # data for the purposes of faster duplicate checks.
    initialize_caches()

    # Startup the dispatcher. We assign it to an unused class in order
    # to avoid pyflakes complaining about unused local variables.
    class services:
        dispatcher = Dispatcher(gsettings, loop)

if __name__ == '__main__':
    # Use this with `python3 -m friends.main`
    main()
