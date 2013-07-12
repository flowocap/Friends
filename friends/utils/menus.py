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

"""Manage the Unity and indicator menus over dbus."""

import logging
import subprocess


from friends.errors import ignored

MessagingMenu = None
""" Disable messaging menu integration until we have some sort of handler
with ignored(ImportError):
    from gi.repository import MessagingMenu
"""


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
    """Manage the indicator menus over dbus."""
    messaging = None

    def __init__(self, refresh_callback, shutdown_callback):
        self._refresh = refresh_callback
        self._shutdown = shutdown_callback
        # Only do the menu initializations if they are available.
        if MessagingMenu:
            self.init_messaging_menu()

    def init_messaging_menu(self):
        self.messaging = MessagingMenu.App(desktop_id='gwibber.desktop')
        self.messaging.register()

    def update_unread_count(self, count):
        """Update the unread count. If zero, make it invisible."""
        if not self.messaging:
            return

        if self.messaging.has_source('unread') and count > 0:
            self.messaging.set_source_count('unread', count)
        elif count > 0:
            self.messaging.append_source_with_count(
                'unread',
                None,
                'Unread',
                count)
        elif self.messaging.has_source('unread') and count < 1:
            self.messaging.remove_source('unread')
