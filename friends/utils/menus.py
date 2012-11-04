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

"""Manage the Unity and indicator menus over dbus."""

import logging
import subprocess

from gettext import gettext as _

Unity = None
Dbusmenu = None
try:
    from gi.repository import Unity, Dbusmenu
except ImportError:
    pass


MessagingMenu = None
try:
    from gi.repository import MessagingMenu
except ImportError:
    pass


DESKTOP_ID = 'friends.desktop'
log = logging.getLogger(__name__)


def helper(executable):
    """Return a callback that executes something in a subprocess.

    :param executable: The name of the system executable to run.  It will be
        searched for on the parent process's $PATH.
    :type executable: string
    :return: A callable useful as a connection function.
    """
    def _helper(*ignore):
        try:
            output = subprocess.check_output(
                [executable],
                # Open stdin, stdout, and stderr as text streams.
                stderr=subprocess.PIPE, universal_newlines=True)
        except subprocess.CallProcessError:
            log.exception(helper)
        # Only log the output if there is any.
        if len(output) > 0:
            log.info('{}: {}', helper, output)
    # Return a suitable closure.
    return _helper


class MenuManager:
    """Manage the Unity and indicator menus over dbus."""
    messaging = None
    launcher = None

    def __init__(self, refresh_callback, shutdown_callback):
        self._refresh = refresh_callback
        self._shutdown = shutdown_callback
        # Only do the menu initializations if they are available.
        if MessagingMenu:
            self.init_messaging_menu()
        if Unity and Dbusmenu:
            self.init_dbus_menu()

    def init_messaging_menu(self):
        self.messaging = MessagingMenu.App(desktop_id=DESKTOP_ID)
        self.messaging.register()

    def init_dbus_menu(self):
        self.launcher = Unity.LauncherEntry.get_for_desktop_id(DESKTOP_ID)
        quicklist = Dbusmenu.Menuitem.new()
        # The update status menu item.
        post_menu = Dbusmenu.Menuitem.new()
        post_menu.property_set(Dbusmenu.MENUITEM_PROP_LABEL,
                               _('Update Status'))
        post_menu.connect('item-activated', helper('friends-poster'))
        # The refresh menu item.
        refresh_menu = Dbusmenu.Menuitem.new()
        refresh_menu.property_set(Dbusmenu.MENUITEM_PROP_LABEL, _('Refresh'))
        refresh_menu.connect('item-activated', self._refresh)
        # The preferences menu item.
        preferences_menu = Dbusmenu.Menuitem.new()
        preferences_menu.property_set(Dbusmenu.MENUITEM_PROP_LABEL,
                                      _('Preferences'))
        preferences_menu.connect('item-activated',
                                 helper('friends-preferences'))
        # The quit menu item.
        quit_menu = Dbusmenu.Menuitem.new()
        quit_menu.property_set(Dbusmenu.MENUITEM_PROP_LABEL, _('Quit'))
        quit_menu.connect('item-activated', self._shutdown)
        # Make all the menu items visible.
        for menu in (post_menu, refresh_menu, preferences_menu, quit_menu):
            menu.property_set_bool(Dbusmenu.MENUITEM_PROP_VISIBLE, True)
            quicklist.child_append(menu)
        # Initialize the unread count to zero.
        self.launcher.set_property('quicklist', quicklist)
        self.update_unread_count(0)

    def update_unread_count(self, count):
        """Update the unread count.  If zoer, make it invisible."""
        if self.launcher:
            self.launcher.set_property('count', count)
            self.launcher.set_property('count_visible', bool(count))


# XXX This bit allows you to test this file by running it.  This doesn't fit
# very well into the larger testsuite architecture so we could probably
# improve this somehow, but I'm not sure how.
#
# In the meantime, run this like so (from the directory containing the
# setup.py file):
#
#   $ python3 -m friends.utils.menus
#
# You should see the Friends icon in the launcher and switcher get the value
# '20'.  If Friends is not running, pass in a second positional argument which
# is the name of a desktop file for an application that is running, e.g.:
#
#   $ python3 -m friends.utils.menus gnome-terminal.desktop
#
# Pass in another argument to set some number other than 20.  If you pass in
# 0, the count will not be visible.
#
# Hit C-c to quit.

if __name__ == '__main__':
    import sys
    from gi.repository import GObject

    if len(sys.argv) > 1:
        DESKTOP_ID = sys.argv[1]
    if len(sys.argv) > 2:
        count = int(sys.argv[2])
    else:
        count = 20

    def stub(*ignore):
        pass

    menu = MenuManager(stub, stub)
    menu.update_unread_count(count)

    try:
        GObject.MainLoop().run()
    except KeyboardInterrupt:
        pass
